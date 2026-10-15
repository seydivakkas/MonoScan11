"""N4: ARKit VIO pose priors and SfM/ARKit Sim(3) diagnostics.

Existing session.json v1 does NOT carry calibrated pose covariance.
Reported residuals are geometric consistency statistics, NOT pose uncertainty
estimates, device accuracy, or independent metrological validation.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path

import numpy as np

from .camera import CameraGeometryError, arkit_to_cv_pose, intrinsics


class ARKitFusionError(ValueError):
    """Rejected pose input, degeneracy or ungrounded alignment."""


@dataclass(frozen=True)
class PosePrior:
    image: str
    timestamp: float
    cv_camera_to_world: np.ndarray
    k: np.ndarray
    tracking_state: str  # normal / unreported (v1 does not record it)
    translation_sigma_m: None = None  # explicitly UNKNOWN, do not infer
    rotation_sigma_deg: None = None


def load_arkit_priors(session_dir: Path, image_names: list[str] | None = None):
    """Read v1 manifest and convert Apple camera axes into CV axes.

    Missing per-frame tracking state is UNKNOWN, not assumed normal.
    An explicitly non-normal frame is rejected rather than silently trusted.
    """
    path = Path(session_dir) / "session.json"
    if not path.is_file():
        raise ARKitFusionError("ARKit-guided mode requires session.json v1")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"),
                         parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
        if not isinstance(raw, dict) or raw.get("schemaVersion") != 1:
            raise ARKitFusionError("Unsupported ARKit session schema")
        frames = raw.get("frames")
        if not isinstance(frames, list) or not frames:
            raise ARKitFusionError("Missing ARKit frame records")
        priors = {}
        previous = -math.inf
        for record in frames:
            if not isinstance(record, dict):
                raise ARKitFusionError("Malformed frame record")
            name, stamp = record.get("file"), record.get("timestamp")
            if not isinstance(name, str) or not name or Path(name).name != name or "/" in name or "\\" in name:
                raise ARKitFusionError("Unsafe image name in ARKit manifest")
            if name in priors:
                raise ARKitFusionError("Duplicate ARKit image name")
            if type(stamp) not in (int, float) or not math.isfinite(stamp) or stamp <= previous:
                raise ARKitFusionError("ARKit timestamps must increase")
            previous = stamp
            tracking = record.get("trackingState", "unreported")
            if tracking not in ("normal", "unreported"):
                raise ARKitFusionError("Non-normal/invalid ARKit tracking state: " + name)
            if "poseCovariance" in record or "translationSigmaM" in record or "rotationSigmaDeg" in record:
                raise ARKitFusionError("Unverified pose covariance fields require a new reviewed schema")
            try:
                pose = arkit_to_cv_pose(record["cameraToWorld"])
                k = intrinsics(record["intrinsics"])
            except (KeyError, TypeError, ValueError, CameraGeometryError) as exc:
                raise ARKitFusionError("Invalid camera prior: " + name) from exc
            priors[name] = PosePrior(name, float(stamp), pose, k, tracking)
        if image_names is not None and set(image_names) != set(priors):
            raise ARKitFusionError("ARKit frame names do not match image collection")
        return priors
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
        if isinstance(exc, ARKitFusionError):
            raise
        raise ARKitFusionError("Cannot parse ARKit session: " + str(exc)) from exc


def pose_baselines(priors: dict[str, PosePrior]):
    if len(priors) < 2:
        raise ARKitFusionError("At least 2 ARKit camera poses required")
    centers = np.asarray([p.cv_camera_to_world[:3, 3] for p in priors.values()])
    delta = centers[:, None] - centers[None, :]
    maximum = float(np.max(np.linalg.norm(delta, axis=2)))
    if maximum < 0.05:  # only a conservative engineering guard, not device accuracy
        raise ARKitFusionError("Insufficient ARKit translation baseline (< 0.05 nominal m)")
    return maximum


def _umeyama(src: np.ndarray, dst: np.ndarray):
    """Proper similarity mapping src to dst: Y = scale * X @ R.T + t."""
    if src.shape != dst.shape or src.ndim != 2 or src.shape[1] != 3 or len(src) < 3:
        raise ARKitFusionError("Need three or more paired 3D camera centers")
    if not np.isfinite(src).all() or not np.isfinite(dst).all():
        raise ARKitFusionError("Nonfinite camera centers")
    x0, y0 = np.mean(src, axis=0), np.mean(dst, axis=0)
    x, y = src - x0, dst - y0
    # Rank 2 permits planar trajectories; rank 1 is unobservable/collinear.
    singular_x = np.linalg.svd(x, compute_uv=False)
    singular_y = np.linalg.svd(y, compute_uv=False)
    if (singular_x[0] < 1e-10 or singular_y[0] < 1e-10
            or singular_x[1] / singular_x[0] < 1e-3
            or singular_y[1] / singular_y[0] < 1e-3):
        raise ARKitFusionError("Degenerate or collinear camera trajectory")
    cov = (y.T @ x) / len(src)
    u, d, vt = np.linalg.svd(cov)
    signs = np.eye(3)
    signs[-1, -1] = np.linalg.det(u @ vt)
    rotation = u @ signs @ vt
    variance = float(np.sum(x * x) / len(src))
    scale = float(np.sum(d * np.diag(signs)) / variance)
    if not np.isfinite(scale) or scale <= 1e-10:
        raise ARKitFusionError("Invalid Sim(3) scale")
    translation = y0 - scale * (rotation @ x0)
    return scale, rotation, translation


def align_pose_centers(source: dict[str, np.ndarray], priors: dict[str, PosePrior],
                       *, min_correspondences=4, relative_threshold=0.05,
                       seed=4, max_trials=128):
    """Robustly align PHOTO_ONLY camera centers to ARKit world coordinates.

    Independent validation is intentionally NOT inferred from small residuals.
    Non-collinear camera motion and a sufficiently large consensus are required.
    """
    names = sorted(set(source) & set(priors))
    if len(names) < min_correspondences or min_correspondences < 4:
        raise ARKitFusionError("At least 4 paired camera centers required")
    src = np.asarray([np.asarray(source[n], dtype=float)[:3, 3] for n in names])
    dst = np.asarray([priors[n].cv_camera_to_world[:3, 3] for n in names])
    if not np.isfinite(src).all() or not np.isfinite(dst).all():
        raise ARKitFusionError("Nonfinite pose center")
    extent = float(np.max(np.linalg.norm(dst[:, None] - dst[None, :], axis=2)))
    if extent < 0.05:
        raise ARKitFusionError("ARKit trajectory has insufficient motion")
    if not 0 < relative_threshold < 0.5:
        raise ARKitFusionError("Invalid alignment threshold")
    tolerance = extent * relative_threshold
    rng = np.random.default_rng(seed)
    best = None
    # Deterministic RANSAC; scores support first, then inlier RMSE.
    for _ in range(max_trials):
        choice = rng.choice(len(names), size=3, replace=False)
        try:
            s, r, t = _umeyama(src[choice], dst[choice])
        except ARKitFusionError:
            continue
        residual = np.linalg.norm(s * (src @ r.T) + t - dst, axis=1)
        inliers = residual <= tolerance
        if int(np.sum(inliers)) < min_correspondences:
            continue
        score = (int(np.sum(inliers)), -float(np.mean(residual[inliers] ** 2)))
        if best is None or score > best[0]:
            best = (score, inliers)
    if best is None:
        raise ARKitFusionError("No consensus Sim(3) alignment; pose disagreement")
    _, inliers = best
    s, r, t = _umeyama(src[inliers], dst[inliers])
    residual = np.linalg.norm(s * (src @ r.T) + t - dst, axis=1)
    accepted = residual <= tolerance
    if int(np.sum(accepted)) < min_correspondences:
        raise ARKitFusionError("Sim(3) refinement lost consensus")
    s, r, t = _umeyama(src[accepted], dst[accepted])
    residual = np.linalg.norm(s * (src @ r.T) + t - dst, axis=1)
    accepted = residual <= tolerance
    if int(np.sum(accepted)) < min_correspondences:
        raise ARKitFusionError("Unstable Sim(3) refinement")
    if int(np.sum(accepted)) / len(names) < 0.65:
        raise ARKitFusionError("Excessive pose outliers")
    return {
        "source_convention": "PHOTO_ONLY CV +Z camera, arbitrary SfM world",
        "target_convention": "ARKit world, CV camera axes, nominal meters",
        "scale": s, "rotation": r.tolist(), "translation": t.tolist(),
        "inlier_count": int(np.sum(accepted)), "paired_count": len(names),
        "inlier_images": [n for n, ok in zip(names, accepted) if ok],
        "outlier_images": [n for n, ok in zip(names, accepted) if not ok],
        "median_inlier_residual_nominal_m": float(np.median(residual[accepted])),
        "max_inlier_residual_nominal_m": float(np.max(residual[accepted])),
        "consensus_tolerance_nominal_m": tolerance,
        "sensor_covariance_known": False, "real_world_validated": False,
        "metric_accuracy_certified": False,
        "note": "Alignment agreement is not calibrated ARKit covariance or absolute measurement accuracy",
    }


def align_run_to_arkit(run_directory: Path, session_directory: Path):
    """Read already-produced PHOTO_ONLY model; return diagnostic dict, no mutation."""
    run = Path(run_directory)
    try:
        camera_doc = json.loads((run / "cameras.json").read_text(encoding="utf-8"))
        summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
        if summary.get("mode_used") != "photo-only" or summary.get("engine") != "monoscan-native":
            raise ARKitFusionError("Alignment diagnostic requires native PHOTO_ONLY run")
        cameras = camera_doc["cameras"]
        source = {}
        for record in cameras:
            name = record["image"]
            if name in source:
                raise ARKitFusionError("Duplicate reconstructed camera")
            # This pose convention was exported by the N3 engine.
            from .camera import camera_to_world
            source[name] = camera_to_world(record["camera_to_world_cv"])
        priors = load_arkit_priors(session_directory)
        return align_pose_centers(source, priors)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        if isinstance(exc, ARKitFusionError):
            raise
        raise ARKitFusionError("Cannot read native SfM run for alignment") from exc
