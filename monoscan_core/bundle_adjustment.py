"""N5 native sparse Bundle Adjustment (BA), synthetic-acceptance stage.

Joint optimization: Rodrigues camera rotations, world-to-camera translations,
and track positions. Intrinsics are fixed, as sensor calibration has not been
verified. Photo-only fixes camera 0 and a baseline gauge; ARKit-guided fixes
camera 0 and uses HEURISTIC nominal-meter/radian pose regularization. No
residual is interpreted as calibrated pose covariance or measurement accuracy.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import uuid

import cv2
import numpy as np
from scipy.optimize import least_squares
from scipy.sparse import lil_matrix

from .camera import CameraGeometryError, camera_to_world, intrinsics
from .reconstruction import _write_ply


class BundleAdjustmentError(ValueError):
    """Fail closed: invalid or unobservable BA input, optimizer or output."""


def _finite_vec(value, count, label):
    try:
        value = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise BundleAdjustmentError("Invalid " + label) from exc
    if value.shape != (count,) or not np.isfinite(value).all():
        raise BundleAdjustmentError("Expected finite " + label)
    return value


def _read_model(run):
    """Strict N3/N4 JSON contract, no untrusted pickle or external model formats."""
    run = Path(run).resolve()
    try:
        summary_raw = (run / "summary.json").read_bytes()
        camera_raw = (run / "cameras.json").read_bytes()
        track_raw = (run / "tracks.json").read_bytes()
        summary = json.loads(summary_raw)
        camera_doc = json.loads(camera_raw)
        tracks_raw = json.loads(track_raw)
    except (OSError, ValueError, UnicodeError) as exc:
        raise BundleAdjustmentError("Missing or corrupt native sparse JSON model") from exc
    if summary.get("engine") != "monoscan-native" or summary.get("mode_used") not in (
        "photo-only", "arkit-guided"
    ):
        raise BundleAdjustmentError("Only N3/N4 native PHOTO_ONLY or ARKit-guided runs are supported")
    cameras_raw = camera_doc.get("cameras")
    if not isinstance(cameras_raw, list) or not (2 <= len(cameras_raw) <= 150):
        raise BundleAdjustmentError("Expected 2-150 native camera records")
    if not isinstance(tracks_raw, list) or not 24 <= len(tracks_raw) <= 5000:
        raise BundleAdjustmentError("N5 supports 24-5000 landmarks per refinement; use smaller reconstruction windows")
    camera_names, ks, pose_w2c, original_cameras = [], [], [], []
    for item in cameras_raw:
        if not isinstance(item, dict) or not isinstance(item.get("image"), str):
            raise BundleAdjustmentError("Malformed camera record")
        name = item["image"]
        if not name or name in camera_names or Path(name).name != name or "/" in name or "\\" in name:
            raise BundleAdjustmentError("Invalid or duplicate camera name")
        try:
            pose = camera_to_world(item["camera_to_world_cv"])
            k = intrinsics(item["K"])
        except (KeyError, TypeError, CameraGeometryError, ValueError) as exc:
            raise BundleAdjustmentError("Invalid camera geometry: " + name) from exc
        extrinsic = np.linalg.inv(pose)
        rot, _ = cv2.Rodrigues(extrinsic[:3, :3])
        camera_names.append(name)
        ks.append(k)
        pose_w2c.append(np.r_[rot.ravel(), extrinsic[:3, 3]])
        original_cameras.append(item)
    camera_ids = {name: idx for idx, name in enumerate(camera_names)}
    points, point_meta, observations, point_ids = [], [], [], set()
    seen_features = set()
    for track in tracks_raw:
        if not isinstance(track, dict) or "id" not in track or "observations" not in track:
            raise BundleAdjustmentError("Malformed track")
        tid = track["id"]
        if not isinstance(tid, int) or tid in point_ids:
            raise BundleAdjustmentError("Invalid or duplicate track ID")
        point_ids.add(tid)
        pos = _finite_vec(track.get("xyz"), 3, "track XYZ")
        obs = track["observations"]
        if not isinstance(obs, list) or len(obs) < 2:
            raise BundleAdjustmentError("Each track requires at least two camera observations")
        views = set()
        for o in obs:
            if not isinstance(o, dict) or o.get("image") not in camera_ids:
                raise BundleAdjustmentError("Track references unknown camera")
            camera_id = camera_ids[o["image"]]
            feature_id = o.get("keypoint")
            if not isinstance(feature_id, int) or feature_id < 0:
                raise BundleAdjustmentError("Invalid feature ID")
            if camera_id in views or (camera_id, feature_id) in seen_features:
                raise BundleAdjustmentError("Duplicate track image/feature observation")
            seen_features.add((camera_id, feature_id))
            views.add(camera_id)
            observations.append((camera_id, len(points), _finite_vec(o.get("uv"), 2, "pixel")))
        points.append(pos)
        point_meta.append(track)
    # Require genuine multi-camera connectedness for the BA problem.
    graph = {i: set() for i in range(len(camera_names))}
    track_vis = {}
    for cam, pid, _ in observations:
        track_vis.setdefault(pid, set()).add(cam)
    for seen in track_vis.values():
        for i in seen:
            graph[i].update(seen - {i})
    visited = {0}
    stack = [0]
    while stack:
        camera = stack.pop()
        for neighbor in graph[camera]:
            if neighbor not in visited:
                visited.add(neighbor)
                stack.append(neighbor)
    if len(visited) != len(camera_names):
        raise BundleAdjustmentError("Disconnected camera-track visibility graph")
    if len(observations) < 48:
        raise BundleAdjustmentError("Insufficient BA reprojection observations")
    return {
        "run": run, "summary": summary, "names": camera_names,
        "original_cameras": original_cameras,
        "k": np.asarray(ks), "poses": np.asarray(pose_w2c), "points": np.asarray(points),
        "point_meta": point_meta,
        "cam_idx": np.asarray([v[0] for v in observations], dtype=np.int32),
        "pt_idx": np.asarray([v[1] for v in observations], dtype=np.int32),
        "uv": np.asarray([v[2] for v in observations], dtype=np.float64),
        "source_sha256": {
            "summary.json": hashlib.sha256(summary_raw).hexdigest(),
            "cameras.json": hashlib.sha256(camera_raw).hexdigest(),
            "tracks.json": hashlib.sha256(track_raw).hexdigest(),
        },
    }


def _rodrigues_projection(parameters, points, ks, cam_indices, point_indices):
    """Pixel reprojection, clipping z only to avoid optimizer NaNs."""
    predictions = np.empty((len(cam_indices), 2), dtype=np.float64)
    depths = np.empty(len(cam_indices), dtype=np.float64)
    for cam in np.unique(cam_indices):
        used = np.flatnonzero(cam_indices == cam)
        rotation, _ = cv2.Rodrigues(parameters[cam, :3])
        xyz = points[point_indices[used]] @ rotation.T + parameters[cam, 3:6]
        depths[used] = xyz[:, 2]
        z = np.maximum(xyz[:, 2], 1e-6)
        homogeneous = xyz @ ks[cam].T
        predictions[used] = homogeneous[:, :2] / z[:, None]
    return predictions, depths


def _camera_center(param):
    r, _ = cv2.Rodrigues(param[:3])
    return -(r.T @ param[3:6])


def _orientation_residual(current, reference):
    rc, _ = cv2.Rodrigues(current[:3])
    rr, _ = cv2.Rodrigues(reference[:3])
    delta, _ = cv2.Rodrigues(rc @ rr.T)
    return delta.ravel()


def _jacobian_pattern(cam_idx, pt_idx, n_cameras, n_points, mode):
    # First camera is fixed to eliminate global SE(3) gauge.
    free_camera_count = n_cameras - 1
    n_obs = len(cam_idx)
    priors = 6 * free_camera_count if mode == "arkit-guided" else 1
    pattern = lil_matrix((2 * n_obs + priors, 6 * free_camera_count + 3 * n_points),
                         dtype=np.int8)
    for o, (camera, point) in enumerate(zip(cam_idx, pt_idx)):
        if camera:
            pattern[2*o:2*o+2, 6*(camera-1):6*camera] = 1
        pattern[2*o:2*o+2, 6*free_camera_count+3*point:
                6*free_camera_count+3*(point+1)] = 1
    for camera in range(1, n_cameras):
        if mode == "arkit-guided":
            pattern[2*n_obs+6*(camera-1):2*n_obs+6*camera,
                    6*(camera-1):6*camera] = 1
    if mode == "photo-only":
        # The second camera's center distance depends on its six extrinsic params.
        pattern[-1, 0:6] = 1
    return pattern.tocsr()


def bundle_adjust(run, *, prior_weight=2.0, max_nfev=70, f_scale_px=2.0):
    """Optimize an immutable N3/N4 sparse run and create a separate N5 run.

    prior_weight is a dimensionless HEURISTIC numerical regularizer, never a
    precision, standard deviation or information matrix. It is used only in
    arkit-guided mode. The first pose is anchored; for photo-only, the first
    two cameras' initial center baseline fixes otherwise arbitrary scale.
    """
    model = _read_model(run)
    names, cameras, initial_points = model["names"], model["poses"], model["points"]
    n_cameras, n_points = cameras.shape[0], len(initial_points)
    mode = model["summary"]["mode_used"]
    if (not np.isfinite(prior_weight) or prior_weight <= 0
            or not isinstance(max_nfev, int) or max_nfev < 2 or max_nfev > 500
            or not np.isfinite(f_scale_px) or f_scale_px <= 0):
        raise BundleAdjustmentError("Invalid BA optimization settings")
    if mode == "arkit-guided":
        # Recorded ARKit v1 nominal world is the regularization reference.
        # Never read or invent pose covariance; no measured sigma exists.
        if any(c.get("pose_source") != "arkit_vio" for c in model["original_cameras"]):
            raise BundleAdjustmentError("ARKit-guided mode requires explicit ARKit VIO provenance")
    if n_points < 24 or n_cameras < 2:
        raise BundleAdjustmentError("Sparse model has insufficient geometric support")
    baseline = float(np.linalg.norm(_camera_center(cameras[1]) -
                                    _camera_center(cameras[0])))
    if baseline < 1e-6:
        raise BundleAdjustmentError("Zero-baseline camera gauge is unobservable")
    cam_idx, pt_idx, uv, ks = model["cam_idx"], model["pt_idx"], model["uv"], model["k"]
    n_free = n_cameras - 1
    x0 = np.r_[cameras[1:].ravel(), initial_points.ravel()]
    shape_cam = 6 * n_free

    def unpack(x):
        cur = cameras.copy()
        cur[1:] = x[:shape_cam].reshape(n_free, 6)
        xyz = x[shape_cam:].reshape(n_points, 3)
        return cur, xyz

    def residual(x):
        pose, xyz = unpack(x)
        px, z = _rodrigues_projection(pose, xyz, ks, cam_idx, pt_idx)
        # Deeply negative z must not masquerade as geometrically valid.
        image_residual = px - uv
        invalid_depth = np.minimum(z - 1e-4, 0)
        image_residual += invalid_depth[:, None] * 100.0
        if mode == "arkit-guided":
            extra = []
            for j in range(1, n_cameras):
                # The numeric scales (1 nominal meter and 1 rad) are public
                # engineering normalizers, NOT calibrated uncertainty.
                delta_center = _camera_center(pose[j]) - _camera_center(cameras[j])
                delta_angle = _orientation_residual(pose[j], cameras[j])
                extra.extend(prior_weight * delta_center)
                extra.extend(prior_weight * delta_angle)
            return np.r_[image_residual.ravel(), extra]
        gauge = 100.0 * (np.linalg.norm(
            _camera_center(pose[1]) - _camera_center(pose[0])) / baseline - 1.0)
        return np.r_[image_residual.ravel(), gauge]

    before_px, before_z = _rodrigues_projection(cameras, initial_points, ks, cam_idx, pt_idx)
    if np.sum(before_z <= 0) > 0:
        raise BundleAdjustmentError("Initial sparse model has behind-camera points")
    before = np.linalg.norm(before_px - uv, axis=1)
    if not np.isfinite(before).all():
        raise BundleAdjustmentError("Nonfinite initial reprojection errors")
    if float(np.median(before)) > 60:
        raise BundleAdjustmentError("Initial reconstruction is too inconsistent to optimize")
    sparsity = _jacobian_pattern(cam_idx, pt_idx, n_cameras, n_points, mode)
    result = least_squares(residual, x0, jac="2-point", jac_sparsity=sparsity,
                           method="trf", loss="soft_l1", f_scale=f_scale_px,
                           max_nfev=max_nfev, x_scale="jac")
    if not np.isfinite(result.x).all() or not np.isfinite(result.cost):
        raise BundleAdjustmentError("Optimizer produced nonfinite parameters")
    if not result.success:
        raise BundleAdjustmentError("BA did not converge within the configured iteration budget")
    optimized_poses, optimized_points = unpack(result.x)
    after_px, after_z = _rodrigues_projection(optimized_poses, optimized_points,
                                             ks, cam_idx, pt_idx)
    after = np.linalg.norm(after_px - uv, axis=1)
    if (np.any(after_z <= 1e-5) or not np.isfinite(after).all()
            or float(np.median(after)) > float(np.median(before)) + 1e-5):
        raise BundleAdjustmentError("BA rejected: negative depth or worse median reprojection")
    optimized_baseline = float(np.linalg.norm(_camera_center(optimized_poses[1]) -
                                             _camera_center(optimized_poses[0])))
    if not (0.95 <= optimized_baseline / baseline <= 1.05) and mode == "photo-only":
        raise BundleAdjustmentError("BA changed the arbitrary-scale baseline gauge")
    if optimized_baseline < baseline * 0.5 or optimized_baseline > baseline * 1.5:
        raise BundleAdjustmentError("BA produced an implausible camera baseline")
    # Ensure the optimization actually improved robust objective or no actual change.
    if result.cost > 0.5 * float(np.dot(residual(x0), residual(x0))) + 1e-6:
        raise BundleAdjustmentError("BA unexpectedly increased initial objective")

    pose_out = []
    for i, original in enumerate(model["original_cameras"]):
        r, _ = cv2.Rodrigues(optimized_poses[i, :3])
        ext = np.eye(4)
        ext[:3, :3], ext[:3, 3] = r, optimized_poses[i, 3:]
        pose = np.linalg.inv(ext)
        item = dict(original)
        item["camera_to_world_cv"] = pose.tolist()
        item["ba_pose_optimized"] = bool(i)
        item["sensor_pose_covariance_known"] = False
        item["pose_regularization_type"] = (
            "uncalibrated_heuristic" if mode == "arkit-guided" else "none"
        )
        pose_out.append(item)
    tracks_out = []
    for i, track in enumerate(model["point_meta"]):
        point = dict(track)
        point["xyz"] = optimized_points[i].tolist()
        tracks_out.append(point)
    source_summary = model["summary"]
    summary = dict(source_summary)
    summary.update({
        "stage": "N5 experimental sparse BA; synthetic acceptance only",
        "bundle_adjustment": "applied",
        "bundle_adjustment_method": "scipy_trf_sparse_soft_l1",
        "bundle_adjustment_optimizer_success": True,
        "bundle_adjustment_message": str(result.message),
        "bundle_adjustment_function_evals": int(result.nfev),
        "bundle_adjustment_first_camera_fixed": names[0],
        "bundle_adjustment_gauge": (
            "first-camera-fixed_and_initial_baseline" if mode == "photo-only"
            else "first-camera-fixed_with_heuristic_ARKit_pose_priors"
        ),
        "bundle_adjustment_prior_weight_heuristic": (
            float(prior_weight) if mode == "arkit-guided" else None
        ),
        "bundle_adjustment_pose_covariance_calibrated": False,
        "pre_ba_median_reprojection_error_px": float(np.median(before)),
        "post_ba_median_reprojection_error_px": float(np.median(after)),
        "pre_ba_mean_reprojection_error_px": float(np.mean(before)),
        "pre_ba_p90_reprojection_error_px": float(np.percentile(before, 90)),
        "post_ba_mean_reprojection_error_px": float(np.mean(after)),
        "post_ba_p90_reprojection_error_px": float(np.percentile(after, 90)),
        "median_reprojection_error_px": float(np.median(after)),
        "mean_reprojection_error_px": float(np.mean(after)),
        "metric_scale_known": False,
        "real_world_validated": False,
        "real_world_test_stage": "N9",
        "source_model_sha256": model["source_sha256"],
        "warnings": list(source_summary.get("warnings", [])) + [
            "Bundle adjustment residuals are internal reprojection statistics, not real accuracy.",
            "ARKit VIO covariance is unknown; priors are heuristic, not measured confidence.",
            "Physical iPhone/camera/lens and real photo acceptance are deferred to N9.",
        ],
    })
    parent = model["run"] / "refinements"
    parent.mkdir(exist_ok=True)
    tmp = parent / (".tmp-" + uuid.uuid4().hex)
    dest = parent / ("n5-" + uuid.uuid4().hex)
    tmp.mkdir()
    try:
        _write_ply(tmp / "sparse.ply", {int(t["id"]): t for t in tracks_out})
        (tmp / "cameras.json").write_text(json.dumps({
            "pose_convention": (
                "CV +Z camera; PHOTO_ONLY arbitrary" if mode == "photo-only"
                else "CV +Z camera, ARKit nominal world meters, unverified"
            ),
            "cameras": pose_out,
        }, indent=2), encoding="utf-8")
        (tmp / "tracks.json").write_text(json.dumps(tracks_out), encoding="utf-8")
        (tmp / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        (tmp / "optimization.json").write_text(json.dumps({
            "algorithm": "N5 sparse BA with SciPy TRF robust loss",
            "input_sha256": model["source_sha256"],
            "source_run": str(model["run"]),
            "optimized_camera_count": n_cameras - 1,
            "optimized_point_count": n_points,
            "observation_count": int(len(uv)),
            "gauge": summary["bundle_adjustment_gauge"],
            "prior_weight_heuristic": summary["bundle_adjustment_prior_weight_heuristic"],
            "pose_covariance_calibrated": False,
            "source_data_type": "unknown; tests are synthetic only",
            "real_world_validated": False,
        }, indent=2), encoding="utf-8")
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp)
    return dest, summary
