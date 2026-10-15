"""N1: explicit camera geometry and ARKit-to-CV coordinate conversion.

World coordinates retain the input world's handedness/origin. CV camera axes
are x right, y down, +z forward; ARKit camera axes are x right, y up, -z forward.
All matrices are row-major; poses map camera coordinates into world coordinates.
"""
from __future__ import annotations

import numpy as np


class CameraGeometryError(ValueError):
    """Invalid or degenerate camera geometry."""


_ARKIT_FROM_CV = np.diag([1.0, -1.0, -1.0, 1.0])


def intrinsics(value) -> np.ndarray:
    k = np.asarray(value, dtype=np.float64)
    if k.shape != (3, 3) or not np.isfinite(k).all():
        raise CameraGeometryError("Expected finite 3x3 intrinsics")
    if k[0, 0] <= 0 or k[1, 1] <= 0 or not np.allclose(k[2], [0, 0, 1], atol=1e-8):
        raise CameraGeometryError("Invalid focal length or K bottom row")
    return k


def camera_to_world(value) -> np.ndarray:
    pose = np.asarray(value, dtype=np.float64)
    if pose.shape != (4, 4) or not np.isfinite(pose).all():
        raise CameraGeometryError("Expected finite 4x4 camera-to-world pose")
    r = pose[:3, :3]
    if (not np.allclose(pose[3], [0, 0, 0, 1], atol=1e-6)
            or not np.allclose(r.T @ r, np.eye(3), atol=1e-3)
            or abs(np.linalg.det(r) - 1.0) > 1e-3):
        raise CameraGeometryError("Camera pose must be proper rigid SE(3)")
    return pose


def arkit_to_cv_pose(arkit_camera_to_world) -> np.ndarray:
    """Return CV-camera-to-ARKit-world; this is NOT a global world rotation."""
    return camera_to_world(camera_to_world(arkit_camera_to_world) @ _ARKIT_FROM_CV)


def world_to_camera(cv_camera_to_world) -> np.ndarray:
    pose = camera_to_world(cv_camera_to_world)
    r = pose[:3, :3]
    inv = np.eye(4, dtype=np.float64)
    inv[:3, :3] = r.T
    inv[:3, 3] = -r.T @ pose[:3, 3]
    return inv


def project(points_world, k, cv_camera_to_world):
    """Project world points; fail if any point is behind the image plane."""
    k, extrinsic = intrinsics(k), world_to_camera(cv_camera_to_world)
    points = np.asarray(points_world, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3 or not np.isfinite(points).all():
        raise CameraGeometryError("Expected finite Nx3 points")
    cam = points @ extrinsic[:3, :3].T + extrinsic[:3, 3]
    if np.any(cam[:, 2] <= 1e-8):
        raise CameraGeometryError("Points behind camera")
    uvw = cam @ k.T
    return uvw[:, :2] / uvw[:, 2:3]


def bearing(pixels, k):
    """Normalized CV camera rays from undistorted pixel coordinates."""
    pix = np.asarray(pixels, dtype=np.float64)
    if pix.ndim != 2 or pix.shape[1] != 2 or not np.isfinite(pix).all():
        raise CameraGeometryError("Expected finite Nx2 pixel coordinates")
    hom = np.column_stack([pix, np.ones(len(pix))])
    rays = hom @ np.linalg.inv(intrinsics(k)).T
    lengths = np.linalg.norm(rays, axis=1)
    if np.any(lengths < 1e-12):
        raise CameraGeometryError("Degenerate bearing ray")
    return rays / lengths[:, None]


def adjusted_intrinsics(k, old_size, new_size):
    """Resize K for unrotated pixels; sizes are (width,height)."""
    ow, oh = old_size
    nw, nh = new_size
    if min(ow, oh, nw, nh) <= 0:
        raise CameraGeometryError("Invalid image size")
    scaled = intrinsics(k).copy()
    sx, sy = nw / ow, nh / oh
    scaled[0, :] *= sx
    scaled[1, :] *= sy
    return scaled
