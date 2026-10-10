"""Dependency-free calibrated two-view triangulation research baseline.

Pinhole camera convention used *only in this module*: image x right, image y
 down, camera +Z forward. This is NOT ARKit's camera convention; ARKit's
 camera -Z forward needs a deliberate conversion before reusing these APIs.
 Distortion is assumed corrected. Nothing here implies LiDAR equivalence.
"""

from __future__ import annotations

import json
import math
from pathlib import Path


class GeometryError(ValueError):
    """Input contains degenerate or non-triangulable geometry."""


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def _mul(a, scale):
    return tuple(x * scale for x in a)


def _norm(v):
    return math.sqrt(_dot(v, v))


def _unit(v):
    n = _norm(v)
    if n < 1e-12 or not math.isfinite(n):
        raise GeometryError("Sıfır veya geçersiz vektör")
    return _mul(v, 1.0 / n)


def _valid_matrix(m, n):
    return (
        isinstance(m, (tuple, list))
        and len(m) == n
        and all(isinstance(row, (tuple, list)) and len(row) == n for row in m)
        and all(isinstance(x, (float, int)) and not isinstance(x, bool) and math.isfinite(x)
                for row in m for x in row)
    )


def world_ray(uv, intrinsics, camera_to_world):
    """Return world-space ray origin and unit direction for undistorted pixel.

    Pose is a row-major 4x4 rigid transform, camera +Z forward.
    """
    if not _valid_matrix(intrinsics, 3) or not _valid_matrix(camera_to_world, 4):
        raise GeometryError("K 3x3 ve camera_to_world 4x4 sonlu matrisler olmalı")
    fx, fy = intrinsics[0][0], intrinsics[1][1]
    if fx <= 0 or fy <= 0:
        raise GeometryError("Odak uzaklıkları pozitif olmalı")
    if len(uv) != 2 or any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in uv):
        raise GeometryError("Piksel koordinatları geçersiz")
    x = (uv[0] - intrinsics[0][2]) / fx
    y = (uv[1] - intrinsics[1][2]) / fy
    ray_camera = _unit((x, y, 1.0))
    ray_world = _unit(tuple(sum(camera_to_world[i][j] * ray_camera[j] for j in range(3)) for i in range(3)))
    origin = tuple(camera_to_world[i][3] for i in range(3))
    return origin, ray_world


def triangulate(uv1, uv2, k1, k2, pose1, pose2, *, min_angle_deg=0.5, max_gap=0.05):
    """Midpoint of two closest ray points; rejects near-parallel rays and bad fits.

    Returns {'xyz': [x,y,z], 'ray_gap_m': ..., 'angle_deg': ...} when camera
    poses are metric. If camera poses have arbitrary SfM scale, units do too.
    """
    o1, d1 = world_ray(uv1, k1, pose1)
    o2, d2 = world_ray(uv2, k2, pose2)
    baseline = _sub(o2, o1)
    if _norm(baseline) < 1e-9:
        raise GeometryError("İki kamera aynı merkezde: stereo baseline sıfır")
    cos_theta = max(-1.0, min(1.0, _dot(d1, d2)))
    angle = math.degrees(math.acos(cos_theta))
    den = 1.0 - cos_theta * cos_theta
    if angle < min_angle_deg or den < 1e-12:
        raise GeometryError("Işınlar neredeyse paralel; güvenilir derinlik yok")
    # Solve o1 + t*d1 ~= o2 + s*d2 via the closest-points solution.
    p = _dot(baseline, d1)
    q = _dot(baseline, d2)
    t = (p - cos_theta * q) / den
    s = (cos_theta * p - q) / den
    if t <= 0 or s <= 0:
        raise GeometryError("Nokta kameralardan en az birinin arkasında")
    p1 = _add(o1, _mul(d1, t))
    p2 = _add(o2, _mul(d2, s))
    gap = _norm(_sub(p1, p2))
    if gap > max_gap:
        raise GeometryError(f"Eşleşen ışınlar kesişmiyor (mesafe {gap:.4f})")
    return {"xyz": list(_mul(_add(p1, p2), 0.5)), "ray_gap_m": gap, "angle_deg": angle}


def project(xyz, intrinsics, camera_to_world):
    """Project a 3D point for pure-translation synthetic camera rigs only.

    For the synthetic baseline rotations are identity; other rotations are
    rejected rather than silently producing incorrect projections.
    """
    if any(abs(camera_to_world[i][j] - (1 if i == j else 0)) > 1e-9
           for i in range(3) for j in range(3)):
        raise GeometryError("Demo projektörü yalnızca paralel kamera düzenini destekliyor")
    v = _sub(xyz, tuple(camera_to_world[i][3] for i in range(3)))
    if v[2] <= 0:
        raise GeometryError("Nokta kameranın arkasında")
    return (intrinsics[0][0] * v[0] / v[2] + intrinsics[0][2],
            intrinsics[1][1] * v[1] / v[2] + intrinsics[1][2])


def write_ply(path: Path, points):
    """Write a minimal colored ASCII PLY file (synthetic or reconstructed points)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii", newline="\n") as out:
        out.write("ply\nformat ascii 1.0\n")
        out.write("comment MonoScan11 point cloud; units depend on input poses\n")
        out.write(f"element vertex {len(points)}\n")
        out.write("property float x\nproperty float y\nproperty float z\n")
        out.write("property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n")
        for x, y, z, r, g, b in points:
            if any(not math.isfinite(v) for v in (x, y, z)):
                raise GeometryError("PLY nokta koordinatlarında geçersiz sayı")
            out.write(f"{x:.9g} {y:.9g} {z:.9g} {int(r)} {int(g)} {int(b)}\n")


def synthetic_demo(out_dir: Path):
    """Deterministic geometry experiment. Not a real-world scan or SfM benchmark."""
    out_dir = Path(out_dir)
    intrinsics = [[850.0, 0, 640.0], [0, 850.0, 480.0], [0, 0, 1]]
    p1 = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    p2 = [[1, 0, 0, 0.25], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    points = []
    errors = []
    for ix in range(-6, 7):
        for iy in range(-4, 5):
            source = (ix * 0.12, iy * 0.12, 2.5 + (ix % 3) * 0.08)
            uv1 = project(source, intrinsics, p1)
            uv2 = project(source, intrinsics, p2)
            result = triangulate(uv1, uv2, intrinsics, intrinsics, p1, p2)
            errors.append(_norm(_sub(result["xyz"], source)))
            points.append((*result["xyz"], 54, 158, 221))
    write_ply(out_dir / "synthetic_points.ply", points)
    metrics = {
        "data_origin": "synthetic_two_view_pinhole_noiseless",
        "ground_truth": "synthetic_meters",
        "real_world_validated": False,
        "point_count": len(points),
        "baseline_m": 0.25,
        "mae_m": sum(errors) / len(errors),
        "rmse_m": math.sqrt(sum(e * e for e in errors) / len(errors)),
        "disclaimer": "İdeal ve gürültüsüz matematik örneğidir; gerçek telefon doğruluğunu göstermez.",
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return metrics
