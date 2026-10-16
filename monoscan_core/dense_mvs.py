"""N6 experimental CPU plane-sweep MVS from calibrated synthetic image views.

No ground-truth depth is read. Pixel-domain matching, depth reciprocity,
voxel fusion and an open grid mesh are independent algorithmic steps.
Photometric agreement does not establish physical measurement accuracy.
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

from .camera import adjusted_intrinsics, camera_to_world, intrinsics, world_to_camera
from .vision import read_image, VisionError


class DenseMVSError(ValueError):
    """Invalid input or insufficient geometric evidence. No result is published."""


def _read_views(run, session, max_side):
    try:
        run, session = Path(run).resolve(), Path(session).resolve()
        sbytes = (run / "summary.json").read_bytes()
        cbytes = (run / "cameras.json").read_bytes()
        summary, document = json.loads(sbytes), json.loads(cbytes)
        if summary.get("engine") != "monoscan-native" or summary.get("mode_used") not in (
            "photo-only", "arkit-guided"
        ):
            raise DenseMVSError("Only N3/N4/N5 native sparse inputs are accepted")
        cameras = document.get("cameras")
        if not isinstance(cameras, list) or not (3 <= len(cameras) <= 8):
            raise DenseMVSError("N6 CPU prototype requires 3-8 calibrated registered cameras")
        inputs = summary.get("input_sha256")
        if not isinstance(inputs, dict) or not inputs:
            raise DenseMVSError("Missing original image hash manifest in sparse model")
        views, found = [], set()
        image_dir = (session / "images").resolve()
        if not image_dir.is_dir():
            raise DenseMVSError("Missing session/images directory")
        for record in cameras:
            if not isinstance(record, dict):
                raise DenseMVSError("Malformed camera")
            name = record.get("image")
            if (not isinstance(name, str) or not name or name != Path(name).name
                    or "/" in name or "\\" in name or name in found):
                raise DenseMVSError("Unsafe or duplicate camera image name")
            found.add(name)
            if name not in inputs or not isinstance(inputs[name], str):
                raise DenseMVSError("Camera image is absent from source integrity manifest")
            path = image_dir / name
            if not path.is_file() or path.is_symlink() or path.resolve().parent != image_dir:
                raise DenseMVSError("Missing or unsafe camera image: " + name)
            actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual_hash != inputs[name]:
                raise DenseMVSError("Image SHA-256 changed since sparse reconstruction: " + name)
            k = intrinsics(record["K"])
            pose = camera_to_world(record["camera_to_world_cv"])
            decoded, original_size = read_image(path, max_side=max_side)
            w, h = original_size
            kh = adjusted_intrinsics(k, (w, h),
                                     (decoded.shape[1], decoded.shape[0]))
            views.append({
                "name": name, "image": decoded, "gray": cv2.cvtColor(
                    decoded, cv2.COLOR_BGR2GRAY).astype(np.float32),
                "k": kh, "pose": pose, "ext": world_to_camera(pose),
                "hash": actual_hash,
            })
        if len({(v["image"].shape[0], v["image"].shape[1]) for v in views}) != 1:
            raise DenseMVSError("N6 initial CPU pipeline requires same-sized processed views")
        centers = np.asarray([v["pose"][:3, 3] for v in views])
        distances = np.linalg.norm(centers[:, None] - centers[None, :], axis=2)
        if float(np.max(distances)) < 1e-5:
            raise DenseMVSError("Insufficient multiview camera baseline")
        return run, views, summary, {
            "summary.json": hashlib.sha256(sbytes).hexdigest(),
            "cameras.json": hashlib.sha256(cbytes).hexdigest(),
        }
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, VisionError) as exc:
        if isinstance(exc, DenseMVSError):
            raise
        raise DenseMVSError("Invalid native depth input: " + str(exc)) from exc


def _grid_rays(view):
    h, w = view["gray"].shape
    y, x = np.indices((h, w), dtype=np.float64)
    uv1 = np.stack([x, y, np.ones_like(x)], axis=-1)
    return uv1 @ np.linalg.inv(view["k"]).T


def _world_at_depth(view, rays, depth):
    local = rays * depth[..., None] if np.ndim(depth) else rays * depth
    return local @ view["pose"][:3, :3].T + view["pose"][:3, 3]


def _project_world(view, xyz):
    local = xyz @ view["ext"][:3, :3].T + view["ext"][:3, 3]
    z = local[..., 2]
    projected = local @ view["k"].T
    with np.errstate(divide="ignore", invalid="ignore"):
        u = projected[..., 0] / z
        v = projected[..., 1] / z
    return u, v, z


def _warp_cost(reference, target, xyz, window):
    u, v, z = _project_world(target, xyz)
    h, w = target["gray"].shape
    valid = (z > 1e-5) & (u >= 1) & (u < w-2) & (v >= 1) & (v < h-2)
    ux = np.where(valid, u, -100).astype(np.float32)
    vy = np.where(valid, v, -100).astype(np.float32)
    warped = cv2.remap(target["gray"], ux, vy, cv2.INTER_LINEAR,
                       borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    discrepancy = np.abs(reference["gray"] - warped)
    # Disallow windows crossing invalid target projections.
    local_valid = cv2.boxFilter(valid.astype(np.float32), -1, (window, window),
                                normalize=True, borderType=cv2.BORDER_CONSTANT)
    cost = cv2.boxFilter(discrepancy.astype(np.float32), -1, (window, window),
                         normalize=True, borderType=cv2.BORDER_REFLECT)
    good = local_valid > 0.97
    return cost, good


def plane_sweep(views, *, min_depth, max_depth, planes=40, window=5,
                min_texture=5.0, min_margin=0.12, max_photometric_cost=40.0):
    """Estimate every view's depth by sampling *images*, not procedural truth.

    Two independently projected target frames must support each candidate.
    Returns unfiltered depth arrays; multiview checks are performed later.
    """
    if (not 0 < min_depth < max_depth or not np.isfinite([min_depth, max_depth]).all()
            or planes < 8 or planes > 256 or window < 3 or window % 2 != 1
            or window > 15 or min_margin <= 0 or min_texture <= 0):
        raise DenseMVSError("Invalid N6 plane-sweep settings")
    if len(views) < 3:
        raise DenseMVSError("At least three camera views needed for N6")
    depth_planes = np.linspace(min_depth, max_depth, planes)
    results = []
    for ref_i, ref in enumerate(views):
        h, w = ref["gray"].shape
        rays = _grid_rays(ref)
        mean = cv2.blur(ref["gray"], (window, window))
        variance = cv2.blur(ref["gray"] ** 2, (window, window)) - mean ** 2
        textured = np.sqrt(np.maximum(variance, 0)) >= min_texture
        best = np.full((h, w), np.inf, np.float32)
        second = np.full_like(best, np.inf)
        selected = np.full((h, w), -1, np.int16)
        support = np.zeros((h, w), np.uint8)
        for p, z in enumerate(depth_planes):
            xyz = _world_at_depth(ref, rays, float(z))
            total = np.zeros((h, w), np.float32)
            valid_count = np.zeros((h, w), np.uint8)
            for tgt_i, tgt in enumerate(views):
                if tgt_i == ref_i:
                    continue
                if np.linalg.norm(ref["pose"][:3, 3] - tgt["pose"][:3, 3]) < 1e-5:
                    continue
                cost, mask = _warp_cost(ref, tgt, xyz, window)
                total += np.where(mask, cost, 0)
                valid_count += mask.astype(np.uint8)
            candidate = np.where(valid_count >= 2, total / np.maximum(valid_count, 1),
                                 np.inf).astype(np.float32)
            better = candidate < best
            second = np.where(better, best, np.minimum(second, candidate))
            best = np.where(better, candidate, best)
            selected = np.where(better, p, selected)
            support = np.where(better, valid_count, support)
        margin = np.zeros_like(best)
        finite_score = np.isfinite(best) & np.isfinite(second)
        np.subtract(second, best, out=margin, where=finite_score)
        eligible = (selected > 0) & (selected < planes - 1) & textured & (
            margin >= min_margin) & (best <= max_photometric_cost) & np.isfinite(best)
        depth = np.where(eligible, depth_planes[np.maximum(selected, 0)], 0).astype(np.float32)
        margin = np.where(eligible, margin, 0).astype(np.float32)
        support = np.where(eligible, support, 0).astype(np.uint8)
        results.append({"depth": depth, "margin": margin,
                        "support": support, "unfiltered_valid_pixels": int(np.count_nonzero(depth))})
    return results


def cross_view_consistency(views, raw_maps, *, relative_tolerance=0.07,
                           minimum_agreeing_views=1):
    """Compare sampled source-view depth with reference->source predicted z."""
    if (not 0 < relative_tolerance < 0.5
            or minimum_agreeing_views < 1
            or minimum_agreeing_views > len(views)-1):
        raise DenseMVSError("Invalid cross-view consistency thresholds")
    output = []
    for i, (view, raw) in enumerate(zip(views, raw_maps)):
        depth = raw["depth"]
        rays = _grid_rays(view)
        xyz = _world_at_depth(view, rays, depth)
        consensus = np.zeros(depth.shape, dtype=np.uint8)
        for j, target in enumerate(views):
            if i == j:
                continue
            u, v, expected_z = _project_world(target, xyz)
            target_depth = raw_maps[j]["depth"]
            h, w = target_depth.shape
            valid = ((depth > 0) & (expected_z > 1e-5)
                     & (u >= 1) & (u < w-2) & (v >= 1) & (v < h-2))
            sx = np.where(valid, u, -10).astype(np.float32)
            sy = np.where(valid, v, -10).astype(np.float32)
            # Nearest depth avoids interpolation through invalid/no-depth holes.
            source_z = cv2.remap(target_depth, sx, sy, cv2.INTER_NEAREST,
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            agreeing = valid & (source_z > 0) & (
                np.abs(source_z - expected_z) <=
                relative_tolerance * np.maximum(expected_z, source_z))
            consensus += agreeing.astype(np.uint8)
        good = (depth > 0) & (consensus >= minimum_agreeing_views)
        output.append({
            "depth": np.where(good, depth, 0).astype(np.float32),
            "support": np.where(good, consensus, 0).astype(np.uint8),
            "margin": np.where(good, raw["margin"], 0).astype(np.float32),
            "valid_pixels": int(np.count_nonzero(good)),
        })
    return output


def fuse_voxels(views, checked, *, voxel_size=0.08, min_unique_views=2,
                sampling_stride=1):
    """Fuse geometrically checked depth samples with unique camera support."""
    if not (np.isfinite(voxel_size) and voxel_size > 0
            and 1 <= min_unique_views <= len(views)
            and isinstance(sampling_stride, int) and 1 <= sampling_stride <= 8):
        raise DenseMVSError("Invalid voxel-fusion settings")
    voxels = {}
    for i, (view, result) in enumerate(zip(views, checked)):
        mask = result["depth"] > 0
        grid = np.zeros_like(mask)
        grid[::sampling_stride, ::sampling_stride] = True
        mask &= grid
        if not np.any(mask):
            continue
        coords = _world_at_depth(view, _grid_rays(view), result["depth"])[mask]
        bgr = view["image"][mask]
        indices = np.floor(coords / voxel_size).astype(np.int64)
        for key, xyz, color in zip(map(tuple, indices), coords, bgr):
            current = voxels.setdefault(key, {"sum": np.zeros(3), "rgb": np.zeros(3),
                                              "count": 0, "views": set()})
            current["sum"] += xyz
            current["rgb"] += color[::-1]
            current["count"] += 1
            current["views"].add(i)
    points = []
    for voxel in voxels.values():
        if len(voxel["views"]) >= min_unique_views:
            points.append((voxel["sum"] / voxel["count"],
                           np.clip(np.rint(voxel["rgb"] / voxel["count"]), 0, 255).astype(int),
                           len(voxel["views"])))
    return points


def grid_mesh(view, checked, *, max_relative_edge=0.10):
    """Open, per-reference-view triangulation; no watertightness or closure claim."""
    if not 0 < max_relative_edge < 0.5:
        raise DenseMVSError("Invalid mesh edge threshold")
    depth = checked["depth"]
    xyz = _world_at_depth(view, _grid_rays(view), depth)
    h, w = depth.shape
    good = depth > 0
    indices = np.full((h, w), -1, dtype=np.int64)
    indices[good] = np.arange(int(np.count_nonzero(good)))
    vertices = xyz[good]
    faces = []
    for y in range(h-1):
        for x in range(w-1):
            for coords in [((y, x), (y+1, x), (y, x+1)),
                           ((y+1, x), (y+1, x+1), (y, x+1))]:
                if not all(good[p] for p in coords):
                    continue
                ids = [int(indices[p]) for p in coords]
                tri = vertices[ids]
                edges = np.linalg.norm(tri - np.roll(tri, -1, axis=0), axis=1)
                depths = [float(depth[p]) for p in coords]
                if (max(edges) <= max_relative_edge * min(depths)
                        and max(depths) - min(depths) <= max_relative_edge * min(depths)):
                    faces.append(tuple(q+1 for q in ids))
    return vertices, faces


def _write_dense_ply(path, points):
    with path.open("w", encoding="ascii", newline="\n") as stream:
        stream.write("ply\nformat ascii 1.0\ncomment N6 CPU synthetic-acceptance; NOT LiDAR\n")
        stream.write(f"element vertex {len(points)}\n")
        stream.write("property float x\nproperty float y\nproperty float z\n")
        stream.write("property uchar red\nproperty uchar green\nproperty uchar blue\n")
        stream.write("end_header\n")
        for xyz, rgb, _ in points:
            stream.write(" ".join(f"{x:.9g}" for x in xyz) + " " +
                         " ".join(str(int(v)) for v in rgb) + "\n")


def reconstruct_dense(run, session, *, min_depth=1.0, max_depth=5.0,
                      planes=40, max_side=192, voxel_size=0.08,
                      min_fused_points=24, min_mesh_faces=12):
    """Read immutable N3/N4/N5 model; publish independent N6 run on success."""
    if (not isinstance(max_side, int) or not 48 <= max_side <= 384
            or not isinstance(planes, int) or not 8 <= planes <= 128
            or not isinstance(min_fused_points, int) or min_fused_points < 12
            or not isinstance(min_mesh_faces, int) or min_mesh_faces < 1):
        raise DenseMVSError("N6 CPU runtime limits exceeded")
    run, views, sparse_summary, sha = _read_views(run, session, max_side)
    raw = plane_sweep(views, min_depth=min_depth, max_depth=max_depth, planes=planes)
    checked = cross_view_consistency(views, raw)
    fused = fuse_voxels(views, checked, voxel_size=voxel_size)
    if len(fused) < min_fused_points:
        raise DenseMVSError("Cross-view support insufficient for fused dense geometry")
    # One reference only: duplicate, overlapping surfaces are NOT reported as watertight.
    selected = max(range(len(checked)), key=lambda i: checked[i]["valid_pixels"])
    vertices, faces = grid_mesh(views[selected], checked[selected])
    if len(faces) < min_mesh_faces:
        raise DenseMVSError("No connected mesh with sufficient depth continuity")
    summary = {
        "engine": "monoscan-native", "stage": "N6 experimental CPU plane-sweep MVS",
        "state": "SYNTHETIC_GEOMETRY_ONLY",
        "source_mode": sparse_summary["mode_used"],
        "data_origin": "not independently verified; CI fixtures are procedural_synthetic",
        "real_world_validated": False, "metric_scale_known": False,
        "scale_status": sparse_summary.get("scale_status", "unknown_unverified"),
        "depth_units": ("arbitrary_photo_only_units" if sparse_summary["mode_used"] == "photo-only"
                        else "arkit_nominal_meters_unverified"),
        "image_count": len(views), "sweep_planes": planes,
        "processed_size": list(views[0]["gray"].shape[::-1]),
        "depth_range": [float(min_depth), float(max_depth)],
        "valid_depth_pixels_by_view": {v["name"]: r["valid_pixels"]
                                       for v, r in zip(views, checked)},
        "fused_voxel_points": len(fused),
        "fusion_min_unique_views": 2,
        "mesh_reference_image": views[selected]["name"],
        "mesh_vertices": len(vertices), "mesh_faces": len(faces),
        "mesh_type": "single-view_open_triangulated_surface_not_watertight",
        "depth_consistency_type": "projected_camera_z_bidirectional",
        "lens_distortion_calibrated": False,
        "pose_covariance_calibrated": False,
        "source_model_sha256": sha,
        "input_image_sha256": {v["name"]: v["hash"] for v in views},
        "warnings": [
            "Photometric and reprojection consistency are not real-world dimensional accuracy.",
            "N6 creates an open grid mesh, not a watertight object or LiDAR equivalent.",
            "Lens calibration, real images and independent iPhone acceptance remain N9.",
        ],
    }
    dest_root = run / "dense"
    dest_root.mkdir(parents=True, exist_ok=True)
    tmp = dest_root / (".tmp-" + uuid.uuid4().hex)
    dest = dest_root / ("n6-" + uuid.uuid4().hex)
    tmp.mkdir()
    try:
        _write_dense_ply(tmp / "dense.ply", fused)
        with (tmp / "mesh.obj").open("w", encoding="ascii", newline="\n") as file:
            file.write("# MonoScan11 N6: OPEN mesh, metric accuracy not validated\n")
            for point in vertices:
                file.write("v " + " ".join(f"{v:.9g}" for v in point) + "\n")
            for face in faces:
                file.write("f " + " ".join(map(str, face)) + "\n")
        maps = {}
        for i, rec in enumerate(checked):
            maps[f"depth_{i}"] = rec["depth"]
            maps[f"support_{i}"] = rec["support"]
            maps[f"margin_{i}"] = rec["margin"]
        np.savez_compressed(tmp / "depth_maps.npz", **maps)
        (tmp / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp)
    return dest, summary
