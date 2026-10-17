"""N4 ARKit-guided sparse reconstruction: measured image correspondences with VIO pose priors.

Uses the existing native match/triangulation utilities; ARKit camera priors
replace PHOTO_ONLY pose estimation only for this opt-in mode. ARKit world units
are nominal meters, not independently calibrated measurements.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import uuid

import numpy as np

from .arkit_fusion import ARKitFusionError, load_arkit_priors, pose_baselines
from .camera import project, world_to_camera, CameraGeometryError
from .reconstruction import (
    ReconstructionError, _triangulated, _write_ply, load_frames,
)
from .vision import match


def reconstruct_arkit_guided(root: Path):
    root = Path(root).resolve()
    # Validate pose contract BEFORE any output directories are created.
    priors = load_arkit_priors(root)
    files, frames, no_features, has_session = load_frames(root, None)
    if not has_session:
        raise ARKitFusionError("ARKit-guided reconstruction requires session.json")
    ordered = [f.name for f in files]
    if set(ordered) != set(priors):
        raise ARKitFusionError("ARKit/image manifest mismatch")
    max_baseline = pose_baselines(priors)
    poses = {i: priors[name].cv_camera_to_world
             for i, name in enumerate(ordered) if frames[i] is not None}
    if len(poses) < 2:
        raise ReconstructionError("No image features across enough ARKit poses")
    observed = {i: {} for i in poses}
    points = {}
    candidate_matches = 0
    accepted_new = 0
    next_id = 0

    def maybe_extend(image_id, kp, landmark_id):
        """Extend only if independent projection agrees (no invented track links)."""
        if kp in observed[image_id]:
            return False
        xyz = np.asarray([points[landmark_id]["xyz"]])
        try:
            uv = project(xyz, frames[image_id].k, poses[image_id])[0]
        except CameraGeometryError:
            return False
        if np.linalg.norm(uv - frames[image_id].points[kp]) > 3.0:
            return False
        observed[image_id][kp] = landmark_id
        return True

    # Triangulate in ARKit world coordinates from each usable overlapping pair.
    # No outside SfM tool, GPU, pseudo depth, or monocular metric claim.
    for i in sorted(poses):
        for j in sorted(k for k in poses if i < k <= i + 8):
            baseline = np.linalg.norm(poses[i][:3, 3] - poses[j][:3, 3])
            if baseline < 0.05:
                continue
            a, b = frames[i], frames[j]
            pairs = match(a, b)
            candidate_matches += len(pairs)
            fresh_a, fresh_b = [], []
            for ai_raw, bj_raw in pairs:
                ai, bj = int(ai_raw), int(bj_raw)
                left = observed[i].get(ai)
                right = observed[j].get(bj)
                if left is not None and right is None:
                    maybe_extend(j, bj, left)
                elif right is not None and left is None:
                    maybe_extend(i, ai, right)
                elif left is None and right is None:
                    fresh_a.append(ai)
                    fresh_b.append(bj)
                # Disagreeing existing tracks are NOT merged without robust proof.
            if len(fresh_a) < 2:
                continue
            xyz, kept, errors = _triangulated(
                a, b, fresh_a, fresh_b,
                world_to_camera(poses[i]), world_to_camera(poses[j]),
            )
            for q in kept:
                ai, bj, point = fresh_a[q], fresh_b[q], xyz[q]
                if ai in observed[i] or bj in observed[j]:
                    continue
                uv = np.rint(a.points[ai]).astype(int)
                xx = int(np.clip(uv[0], 0, a.image.shape[1] - 1))
                yy = int(np.clip(uv[1], 0, a.image.shape[0] - 1))
                rgb = a.image[yy, xx, ::-1]
                points[next_id] = {
                    "xyz": [float(v) for v in point],
                    "rgb": [int(v) for v in rgb],
                }
                observed[i][ai] = next_id
                observed[j][bj] = next_id
                accepted_new += 1
                next_id += 1

    used = {idx: vals for idx, vals in observed.items() if len(vals) >= 8}
    if len(used) < 2:
        raise ReconstructionError("Not enough cross-view ARKit-guided feature tracks")
    supported = {pid for idx, obs in used.items() for pid in obs.values()}
    track_views = {pid: set() for pid in supported}
    errors = []
    for idx, assignments in used.items():
        frame = frames[idx]
        for kp, pid in assignments.items():
            if pid not in supported:
                continue
            try:
                uv = project([points[pid]["xyz"]], frame.k, poses[idx])[0]
            except CameraGeometryError:
                continue
            residual = float(np.linalg.norm(uv - frame.points[kp]))
            if np.isfinite(residual) and residual <= 4.0:
                track_views[pid].add(idx)
                errors.append(residual)
    keep = {pid for pid, views in track_views.items() if len(views) >= 2}
    if len(keep) < 24:
        raise ReconstructionError("ARKit pose/geometric evidence insufficient for sparse model")
    # Re-evaluate metrics only on genuine retained landmark observations.
    final_obs = {}
    reproj = []
    for idx, assignments in used.items():
        final_obs[idx] = {}
        for kp, pid in assignments.items():
            if pid not in keep:
                continue
            try:
                uv = project([points[pid]["xyz"]], frames[idx].k, poses[idx])[0]
            except CameraGeometryError:
                continue
            delta = float(np.linalg.norm(uv - frames[idx].points[kp]))
            if np.isfinite(delta) and delta <= 4:
                final_obs[idx][kp] = pid
                reproj.append(delta)
    registered = {idx for idx, obs in final_obs.items() if len(obs) >= 8}
    if len(registered) < 2 or not reproj:
        raise ReconstructionError("No stable multiview landmark observations")
    keep = {pid for idx in registered for pid in final_obs[idx].values()
            if sum(pid in final_obs[v].values() for v in registered) >= 2}
    if len(keep) < 24:
        raise ReconstructionError("Insufficient retained multiview tracks")
    result_points = {pid: p for pid, p in points.items() if pid in keep}
    final_obs = {idx: {kp: pid for kp, pid in final_obs[idx].items() if pid in keep}
                 for idx in registered}
    # Recompute residual on EXACT retained observations, no extrapolated metric claims.
    residuals = [
        float(np.linalg.norm(
            project([result_points[pid]["xyz"]], frames[idx].k, poses[idx])[0]
            - frames[idx].points[kp]
        ))
        for idx, obs in final_obs.items() for kp, pid in obs.items()
    ]
    if not residuals or not np.isfinite(residuals).all():
        raise ReconstructionError("Invalid ARKit reprojection diagnostics")
    per_camera_reprojection = {}
    for idx, obs in final_obs.items():
        local_residuals = [
            float(np.linalg.norm(
                project([result_points[pid]["xyz"]], frames[idx].k, poses[idx])[0]
                - frames[idx].points[kp]
            ))
            for kp, pid in obs.items()
        ]
        per_camera_reprojection[idx] = {
            "observation_count": len(local_residuals),
            "median_reprojection_error_px": (
                float(np.median(local_residuals)) if local_residuals else None
            ),
            "mean_reprojection_error_px": (
                float(np.mean(local_residuals)) if local_residuals else None
            ),
            "sensor_pose_covariance_known": False,
        }
    tracking_unknown = [name for name in ordered if priors[name].tracking_state == "unreported"]
    summary = {
        "engine": "monoscan-native",
        "stage": "N4 experimental ARKit-guided sparse; no bundle adjustment",
        "state": "SUCCESS_SPARSE" if len(registered) == len(files) else "PARTIAL",
        "mode_requested": "arkit-guided", "mode_used": "arkit-guided",
        "image_count": len(files), "registered_images": len(registered),
        "point_count": len(result_points),
        "observation_count": sum(map(len, final_obs.values())),
        "candidate_pair_matches": candidate_matches,
        "triangulated_candidates": accepted_new,
        "mean_reprojection_error_px": float(np.mean(residuals)),
        "median_reprojection_error_px": float(np.median(residuals)),
        "maximum_pose_baseline_nominal_m": max_baseline,
        "pose_prior_source": "ARKit VIO session.json v1",
        "pose_covariance_available": False,
        "translation_sigma_m": None, "rotation_sigma_deg": None,
        "tracking_state_unreported_images": tracking_unknown,
        "scale_status": "arkit_nominal_meters_unverified",
        "metric_scale_known": False, "real_world_validated": False,
        "unregistered_images": [n for idx, n in enumerate(ordered) if idx not in registered],
        "insufficient_texture_images": no_features,
        "warnings": [
            "ARKit VIO scale is approximate; no independent metrological calibration.",
            "Manifest v1 has no pose covariance; geometric residuals are not sensor uncertainty.",
            "No bundle adjustment, dense depth or independent real-device validation.",
        ],
        "input_sha256": {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
    }
    # Immutable session inputs; new run folder, transactional publishing.
    run_root = root / "reconstruction" / "runs"
    run_root.mkdir(parents=True, exist_ok=True)
    tmp = run_root / (".tmp-" + uuid.uuid4().hex)
    dest = run_root / ("run-" + uuid.uuid4().hex)
    tmp.mkdir()
    try:
        _write_ply(tmp / "sparse.ply", result_points)
        cameras = [
            {
                "image": ordered[idx],
                "camera_to_world_cv": poses[idx].tolist(),
                "K": frames[idx].k.tolist(),
                "pose_source": "arkit_vio",
                "tracking_state": priors[ordered[idx]].tracking_state,
                "translation_sigma_m": None,
                "rotation_sigma_deg": None,
                "pose_quality_basis": "geometric_reprojection_only_not_covariance",
                "pose_diagnostics": per_camera_reprojection[idx],
            }
            for idx in sorted(registered)
        ]
        (tmp / "cameras.json").write_text(json.dumps({
            "pose_convention": "CV +Z camera, ARKit world nominal meters; not metrologically verified",
            "cameras": cameras,
        }, indent=2), encoding="utf-8")
        tracks = [
            {
                "id": pid, **p,
                "observations": [
                    {"image": ordered[idx], "keypoint": kp,
                     "uv": frames[idx].points[kp].tolist()}
                    for idx, obs in final_obs.items() for kp, point_id in obs.items()
                    if point_id == pid
                ],
            }
            for pid, p in sorted(result_points.items())
        ]
        (tmp / "tracks.json").write_text(json.dumps(tracks), encoding="utf-8")
        (tmp / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            import shutil
            shutil.rmtree(tmp)
    return dest, summary
