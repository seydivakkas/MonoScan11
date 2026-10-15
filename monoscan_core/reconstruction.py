"""N3: experimental native PHOTO_ONLY SfM (no COLMAP/pycolmap calls).

Incremental feature tracks through a seed-pair anchor, essential-matrix
initialization, 3D/2D PnP registration and multiview landmark triangulation.
No bundle adjustment yet; intentionally reports incomplete reconstructions.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import uuid

import cv2
import numpy as np

from .camera import adjusted_intrinsics, camera_to_world, intrinsics, project, world_to_camera
from .vision import VisionError, extract, match, read_image


class ReconstructionError(ValueError):
    pass


def load_frames(root: Path, focal_px: float | None):
    image_dir = root / "images"
    if not image_dir.is_dir():
        raise ReconstructionError("Missing images directory")
    files = sorted(p for p in image_dir.iterdir()
                   if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    if len(files) < 3 or len(files) > 150:
        raise ReconstructionError("Expected 3–150 JPEG/PNG images")
    if len({p.name.casefold() for p in files}) != len(files):
        raise ReconstructionError("Case-colliding image names")
    manifest_path = root / "session.json"
    records = {}
    if manifest_path.exists():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            if payload.get("schemaVersion") != 1 or not isinstance(payload.get("frames"), list):
                raise ValueError("Unsupported session schema")
            records = {x["file"]: x for x in payload["frames"]}
            if set(records) != {p.name for p in files} or len(payload["frames"]) != len(files):
                raise ValueError("Session image list differs from image folder")
        except (ValueError, KeyError, TypeError) as exc:
            raise ReconstructionError(f"Invalid session.json: {exc}") from exc
    if not records and (focal_px is None or not math.isfinite(focal_px) or focal_px <= 0):
        raise ReconstructionError("PHOTO_ONLY without session.json requires calibrated --focal-px")
    frames = []
    missing_texture = []
    for file in files:
        image, original_size = read_image(file)
        w, h = original_size
        if records:
            rec = records[file.name]
            if (rec.get("width"), rec.get("height")) != (w, h):
                raise ReconstructionError(f"Image/K dimensions mismatch: {file.name}")
            camera_to_world(rec["cameraToWorld"])  # validates; poses NOT used in PHOTO_ONLY
            k = intrinsics(rec["intrinsics"])
        else:
            k = intrinsics([[focal_px, 0, w / 2], [0, focal_px, h / 2], [0, 0, 1]])
        height2, width2 = image.shape[:2]
        k = adjusted_intrinsics(k, (w, h), (width2, height2))
        try:
            frames.append(extract(file.name, image, k))
        except VisionError:
            missing_texture.append(file.name)
            frames.append(None)
    return files, frames, missing_texture, bool(records)


def _normalized(frame, keypoint_ids):
    uv = frame.points[np.asarray(keypoint_ids, dtype=np.int32)]
    return cv2.undistortPoints(uv.reshape(-1, 1, 2), frame.k, None).reshape(-1, 2)


def _triangulated(a, b, keys_a, keys_b, extrinsic_a, extrinsic_b):
    """Return accepted Nx3 positions, kept input offsets and pixel reprojection errors."""
    if len(keys_a) == 0:
        return np.empty((0, 3)), [], []
    pa, pb = _normalized(a, keys_a), _normalized(b, keys_b)
    hom = cv2.triangulatePoints(extrinsic_a[:3], extrinsic_b[:3], pa.T, pb.T)
    good_w = np.abs(hom[3]) > 1e-10
    xyz = np.zeros((len(keys_a), 3), dtype=float)
    xyz[good_w] = (hom[:3, good_w] / hom[3, good_w]).T
    ca = -extrinsic_a[:3, :3].T @ extrinsic_a[:3, 3]
    cb = -extrinsic_b[:3, :3].T @ extrinsic_b[:3, 3]
    kept, err = [], []
    for i, x in enumerate(xyz):
        if not good_w[i] or not np.isfinite(x).all():
            continue
        za = (extrinsic_a[:3, :3] @ x + extrinsic_a[:3, 3])[2]
        zb = (extrinsic_b[:3, :3] @ x + extrinsic_b[:3, 3])[2]
        if min(za, zb) <= 1e-6:
            continue
        ray_a, ray_b = x - ca, x - cb
        cosine = np.clip(float(np.dot(ray_a, ray_b) /
                               (np.linalg.norm(ray_a) * np.linalg.norm(ray_b))), -1, 1)
        angle = math.degrees(math.acos(cosine))
        if angle < 1.0:
            continue
        # Pixel-domain reprojection error, not independent metric accuracy.
        q1 = a.k @ (extrinsic_a[:3, :3] @ x + extrinsic_a[:3, 3])
        q2 = b.k @ (extrinsic_b[:3, :3] @ x + extrinsic_b[:3, 3])
        e1 = np.linalg.norm(q1[:2] / q1[2] - a.points[keys_a[i]])
        e2 = np.linalg.norm(q2[:2] / q2[2] - b.points[keys_b[i]])
        if max(e1, e2) <= 3:
            kept.append(i)
            err.append((float(e1) + float(e2)) / 2)
    return xyz, kept, err


def _seed(a, b):
    pairs = match(a, b)
    if len(pairs) < 45:
        return None
    norm_a = _normalized(a, pairs[:, 0])
    norm_b = _normalized(b, pairs[:, 1])
    focal = (a.k[0, 0] + b.k[0, 0]) / 2
    essential, mask = cv2.findEssentialMat(
        norm_a, norm_b, np.eye(3), cv2.RANSAC, 0.999,
        max(0.0005, 1.5 / focal))
    if essential is None or mask is None:
        return None
    essential = essential[:3, :3]  # OpenCV may return stacked 3x3 candidates.
    inliers, rotation, translation, good = cv2.recoverPose(
        essential, norm_a, norm_b, np.eye(3), mask=mask)
    if inliers < 30:
        return None
    use = np.flatnonzero(good.ravel() > 0)
    k1, k2 = pairs[use, 0], pairs[use, 1]
    ext1 = np.eye(4)
    ext2 = np.eye(4)
    ext2[:3, :3], ext2[:3, 3] = rotation, translation.reshape(3)
    xyz, kept, errors = _triangulated(a, b, k1, k2, ext1, ext2)
    if len(kept) < 24:
        return None
    return k1[kept], k2[kept], xyz[kept], ext1, ext2, errors


def _pose_from_extrinsic(ext):
    return np.linalg.inv(ext)


def _write_ply(path, points):
    with path.open("w", encoding="ascii", newline="\n") as out:
        out.write("ply\nformat ascii 1.0\ncomment PHOTO_ONLY arbitrary scale; not LiDAR\n")
        out.write(f"element vertex {len(points)}\n")
        out.write("property float x\nproperty float y\nproperty float z\n")
        out.write("property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n")
        for p in points.values():
            x, y, z = p["xyz"]
            r, g, b = p["rgb"]
            out.write(f"{x:.10g} {y:.10g} {z:.10g} {r} {g} {b}\n")


def reconstruct(root: Path, *, focal_px: float | None = None):
    root = Path(root).resolve()
    files, frames, no_features, has_session = load_frames(root, focal_px)
    # Candidate pair window balances coverage with quadratic work; not globally optimal.
    best = None
    for i, a in enumerate(frames):
        if a is None:
            continue
        for j in range(i + 1, min(len(frames), i + 9)):
            b = frames[j]
            if b is None:
                continue
            result = _seed(a, b)
            if result is not None and (best is None or len(result[2]) > len(best[2])):
                best = (i, j, *result)
    if best is None:
        raise ReconstructionError("No geometrically valid initial pair; texture/parallax/overlap insufficient")
    i, j, key_a, key_b, xyz, ext_a, ext_b, seed_err = best
    poses = {i: _pose_from_extrinsic(ext_a), j: _pose_from_extrinsic(ext_b)}
    points, observed = {}, {i: {}, j: {}}
    next_id = 0

    def add_point(x, im_a, kp_a, im_b, kp_b):
        nonlocal next_id
        pixel = np.rint(frames[im_a].points[kp_a]).astype(int)
        image = frames[im_a].image
        yy = np.clip(pixel[1], 0, image.shape[0] - 1)
        xx = np.clip(pixel[0], 0, image.shape[1] - 1)
        bgr = image[yy, xx]
        points[next_id] = {"xyz": x.tolist(), "rgb": [int(bgr[2]), int(bgr[1]), int(bgr[0])]}
        observed.setdefault(im_a, {})[int(kp_a)] = next_id
        observed.setdefault(im_b, {})[int(kp_b)] = next_id
        next_id += 1

    for kp_a, kp_b, x in zip(key_a, key_b, xyz):
        add_point(x, i, kp_a, j, kp_b)

    remaining = {n for n, frame in enumerate(frames) if frame is not None} - set(poses)
    for _ in range(len(frames)):
        progress = False
        for target in sorted(remaining):
            frame = frames[target]
            associations = {}
            anchor_pairs = {}
            for anchor in list(poses):
                pairs = match(frames[anchor], frame)
                anchor_pairs[anchor] = pairs
                for aidx, tidx in pairs:
                    landmark = observed[anchor].get(int(aidx))
                    if landmark is not None and int(tidx) not in associations:
                        associations[int(tidx)] = landmark
            if len(associations) < 12:
                continue
            items = sorted(associations.items())
            object_points = np.asarray([points[p]["xyz"] for _, p in items], np.float64)
            image_points = np.asarray([frame.points[t] for t, _ in items], np.float64)
            ok, rv, tv, inlier_idx = cv2.solvePnPRansac(
                object_points, image_points, frame.k, None,
                iterationsCount=400, reprojectionError=4.0, confidence=0.999)
            if not ok or inlier_idx is None or len(inlier_idx) < 12:
                continue
            r, _ = cv2.Rodrigues(rv)
            ext = np.eye(4)
            ext[:3, :3], ext[:3, 3] = r, tv.reshape(3)
            poses[target] = _pose_from_extrinsic(ext)
            observed[target] = {items[q][0]: items[q][1] for q in inlier_idx.ravel()}
            remaining.remove(target)
            progress = True
            # Add new landmarks observed in an earlier registered frame.
            for anchor, pairs in anchor_pairs.items():
                new_pairs = [(int(ai), int(ti)) for ai, ti in pairs
                             if int(ai) not in observed[anchor]
                             and int(ti) not in observed[target]]
                if not new_pairs:
                    continue
                ia, ib = map(list, zip(*new_pairs))
                xyz_new, kept, _ = _triangulated(
                    frames[anchor], frame, ia, ib, world_to_camera(poses[anchor]), ext)
                for q in kept:
                    ai, ti = new_pairs[q]
                    if ai not in observed[anchor] and ti not in observed[target]:
                        add_point(xyz_new[q], anchor, ai, target, ti)
        if not progress:
            break
    if len(points) < 24 or len(poses) < 2:
        raise ReconstructionError("Sparse model below minimum geometric support")

    errors = []
    for frame_id, local in observed.items():
        frame = frames[frame_id]
        for feature_id, landmark_id in local.items():
            try:
                reproj = project(np.asarray([points[landmark_id]["xyz"]]), frame.k, poses[frame_id])[0]
                errors.append(float(np.linalg.norm(reproj - frame.points[feature_id])))
            except ValueError:
                continue
    if not errors or not np.isfinite(errors).all():
        raise ReconstructionError("No valid reprojection residuals")

    scale_status = "arbitrary"
    summary = {
        "engine": "monoscan-native", "stage": "N3 experimental, no bundle adjustment",
        "state": "SUCCESS_SPARSE" if len(poses) == len(files) else "PARTIAL",
        "mode_requested": "photo-only", "mode_used": "photo-only",
        "registered_images": len(poses), "image_count": len(files),
        "point_count": len(points), "observation_count": sum(map(len, observed.values())),
        "mean_reprojection_error_px": float(np.mean(errors)),
        "median_reprojection_error_px": float(np.median(errors)),
        "scale_status": scale_status, "metric_scale_known": False,
        "real_world_validated": False,
        "warnings": (["Camera intrinsics supplied via --focal-px; check calibration."] if not has_session else [])
                    + ["Only the available matched/registered images are reconstructed.",
                       "Bundle adjustment and dense MVS are not implemented.",
                       "Photos have not been independently validated against real measurements."],
        "unregistered_images": [f.name for idx, f in enumerate(files) if idx not in poses],
        "insufficient_texture_images": no_features,
        "input_sha256": {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
    }
    run_root = root / "reconstruction" / "runs"
    run_root.mkdir(parents=True, exist_ok=True)
    tmp = run_root / (".tmp-" + uuid.uuid4().hex)
    dest = run_root / ("run-" + uuid.uuid4().hex)
    tmp.mkdir()
    try:
        _write_ply(tmp / "sparse.ply", points)
        cameras = [{
            "image": files[idx].name, "camera_to_world_cv": pose.tolist(),
            "K": frames[idx].k.tolist()
        } for idx, pose in sorted(poses.items())]
        (tmp / "cameras.json").write_text(json.dumps({
            "pose_convention": "CV +Z forward; seed camera frame world; arbitrary scale",
            "cameras": cameras}, indent=2), encoding="utf-8")
        tracks = [{
            "id": key, **point,
            "observations": [{"image": files[f].name, "keypoint": kp,
                              "uv": frames[f].points[kp].tolist()}
                             for f, obs in observed.items() for kp, lid in obs.items() if lid == key]
        } for key, point in sorted(points.items())]
        (tmp / "tracks.json").write_text(json.dumps(tracks), encoding="utf-8")
        (tmp / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            import shutil
            shutil.rmtree(tmp)
    return dest, summary
