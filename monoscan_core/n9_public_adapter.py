"""N9 real-image dataset adapter — ARKitScenes (iPad Pro), never iPhone 11.

Source: https://github.com/apple-aiml-research/ARKitScenes, DATA.md and
threedod/benchmark_scripts/utils/tenFpsDataLoader.py. The .traj stores
WORLD->CAMERA CV angle-axis and translation, unlike ARKit camera-to-world.
This reader explicitly inverts that transform, then adjusts CV camera
basis to the existing MonoScan11 ARKit-camera v1 convention.

No network or automatic acceptance of a third-party license. Source images
are copied byte-for-byte; original dataset and source ZIP remain immutable.
This is a proxy photogrammetry trial only, never a physical iPhone11 pass.
"""
from __future__ import annotations

import bisect
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile

import cv2
import numpy as np

from .camera import CameraGeometryError, camera_to_world, intrinsics


CV_FROM_ARKIT = np.diag([1.0, -1.0, -1.0, 1.0])


class RealDatasetError(ValueError):
    pass


def parse_arkitscenes_traj(path):
    """Return sorted (timestamp, CV camera-to-world) from official .traj."""
    trajectory = []
    try:
        if Path(path).stat().st_size > 16 * 1024 * 1024:
            raise RealDatasetError("Trajectory exceeds safety limit")
        for n, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
            if not raw.strip():
                continue
            parts = raw.split()
            if len(parts) != 7:
                raise RealDatasetError(f"Malformed trajectory row {n}")
            values = np.asarray([float(x) for x in parts], dtype=np.float64)
            if not np.isfinite(values).all():
                raise RealDatasetError("Nonfinite trajectory value")
            timestamp = float(values[0])
            if trajectory and timestamp <= trajectory[-1][0]:
                raise RealDatasetError("Nonmonotonic ARKitScenes trajectory")
            r, _ = cv2.Rodrigues(values[1:4])
            w2c = np.eye(4)
            w2c[:3, :3] = r
            w2c[:3, 3] = values[4:7]
            # Official tenFpsDataLoader.TrajStringToMatrix() inverts this
            # world-to-camera transform for projection / point generation.
            pose = camera_to_world(np.linalg.inv(w2c))
            trajectory.append((timestamp, pose))
        if len(trajectory) < 3:
            raise RealDatasetError("Need three or more ARKitScenes pose records")
        return trajectory
    except (OSError, UnicodeError, ValueError, CameraGeometryError) as exc:
        if isinstance(exc, RealDatasetError):
            raise
        raise RealDatasetError("Cannot read official .traj file") from exc


def parse_pincam(path):
    """Official format: width height fx fy cx cy (on image pixel grid)."""
    try:
        tokens = Path(path).read_text(encoding="utf-8").split()
        if len(tokens) != 6:
            raise RealDatasetError("Malformed .pincam parameters")
        vals = [float(x) for x in tokens]
        width, height = vals[:2]
        if (not all(math.isfinite(x) for x in vals)
                or int(width) != width or int(height) != height
                or width < 32 or height < 32 or width > 8192 or height > 8192):
            raise RealDatasetError("Invalid .pincam image dimensions")
        k = intrinsics([[vals[2], 0, vals[4]],
                        [0, vals[3], vals[5]], [0, 0, 1]])
        return int(width), int(height), k
    except (OSError, UnicodeError, ValueError, CameraGeometryError) as exc:
        if isinstance(exc, RealDatasetError):
            raise
        raise RealDatasetError("Cannot read official .pincam") from exc


def _timestamp_from_filename(name, video_id):
    stem = Path(name).stem
    prefix = str(video_id) + "_"
    if not stem.startswith(prefix):
        raise RealDatasetError("RGB name does not contain expected video ID")
    suffix = stem[len(prefix):]
    try:
        value = float(suffix)
    except ValueError as exc:
        raise RealDatasetError("Unparseable RGB filename timestamp") from exc
    if not math.isfinite(value):
        raise RealDatasetError("Nonfinite RGB timestamp")
    return value


def prepare_arkitscenes_session(source: Path, output: Path, *,
                               video_id: str, max_frames=24,
                               max_timestamp_gap_seconds=0.02):
    """Convert an already-authorized local RAW/scene into native session v1.

    A scan must contain folders lowres_wide/, lowres_wide_intrinsics/,
    and lowres_wide.traj. No auto-download, no on-the-fly inference of K/pose.
    """
    source, output = Path(source).resolve(), Path(output).resolve()
    if not (str(video_id).isdigit() and len(str(video_id)) == 8):
        raise RealDatasetError("Expected official eight-digit ARKitScenes video ID")
    if not 3 <= max_frames <= 100:
        raise RealDatasetError("Must select between 3 and 100 observed frames")
    if not (0 < max_timestamp_gap_seconds <= 0.03):
        raise RealDatasetError("Timestamp tolerance must be explicit and at most 30 ms")
    if source == output or source in output.parents or output in source.parents:
        raise RealDatasetError("Source and destination must be independent")
    if output.exists():
        raise RealDatasetError("Refuse to overwrite an existing native session")
    rgb_dir, k_dir = source / "lowres_wide", source / "lowres_wide_intrinsics"
    if not all(p.is_dir() and not p.is_symlink() for p in [rgb_dir, k_dir]):
        raise RealDatasetError("Missing official RGB or per-frame intrinsic directory")
    trajectory = parse_arkitscenes_traj(source / "lowres_wide.traj")
    names = sorted(p for p in rgb_dir.glob("*.png")
                   if p.is_file() and not p.is_symlink() and p.name.startswith(str(video_id)+"_"))
    if not names:
        raise RealDatasetError("No official timestamped lowres RGB images")
    if len(names) > 30000:
        raise RealDatasetError("Too many source images; use a bounded dataset")
    times = [a for a, _ in trajectory]
    candidates, used = [], set()
    for path in names:
        timestamp = _timestamp_from_filename(path.name, video_id)
        i = bisect.bisect_left(times, timestamp)
        near = [j for j in (i-1, i) if 0 <= j < len(times)]
        if not near:
            continue
        nearest = min(near, key=lambda j: abs(times[j] - timestamp))
        gap = abs(times[nearest] - timestamp)
        if gap > max_timestamp_gap_seconds or nearest in used:
            continue
        k_path = k_dir / (path.stem + ".pincam")
        if not k_path.is_file() or k_path.is_symlink():
            continue
        width, height, k = parse_pincam(k_path)
        if path.stat().st_size > 40 * 1024 * 1024:
            raise RealDatasetError("Source frame too large")
        encoded = path.read_bytes()
        pixels = cv2.imdecode(np.frombuffer(encoded, np.uint8), cv2.IMREAD_COLOR)
        if pixels is None or pixels.shape[:2] != (height, width):
            raise RealDatasetError("RGB dimensions and intrinsics disagree")
        cv_pose = trajectory[nearest][1]
        # N4 expects ARKit camera axes. This basis conversion is ONLY for
        # adapting the official already-CV-convention data, NOT adding depth.
        arkit_pose = camera_to_world(cv_pose @ CV_FROM_ARKIT)
        used.add(nearest)
        candidates.append({
            "src": path,
            "src_pincam": k_path,
            "data": encoded, "file": path.name, "timestamp": timestamp,
            "pose_timestamp": times[nearest], "pose_time_gap_seconds": gap,
            "width": width, "height": height,
            "intrinsics": k.tolist(), "cameraToWorld": arkit_pose.tolist(),
            "sha256": hashlib.sha256(encoded).hexdigest(),
        })
    candidates.sort(key=lambda v: v["timestamp"])
    if len(candidates) < 3:
        raise RealDatasetError("Fewer than three exact/near-exact RGB+K+pose triples")
    # Include breadth of movement, not three adjacent poses by default.
    indices = np.linspace(0, len(candidates)-1, min(max_frames, len(candidates)))
    chosen = [candidates[i] for i in dict.fromkeys(int(round(x)) for x in indices)]
    centers = np.asarray([np.asarray(f["cameraToWorld"])[:3, 3] for f in chosen])
    extent = float(np.max(np.linalg.norm(centers[:, None]-centers[None, :], axis=2)))
    if extent < 0.05:
        raise RealDatasetError("Insufficient camera movement for ARKit guided SfM")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".n9-arkitscenes-", dir=output.parent))
    manifest = {
        "schemaVersion": 1,
        "acquisition": "third_party_public_arkitscenes_iPad_Pro_RGB_not_iPhone11",
        "cameraImageCoordinates": "official_ARKitScenes_lowres_wide_pincam",
        "cameraPoseConvention": "converted_from_trajectory_world_to_camera_CV_to_ARKit_camera_basis",
        "frames": [
            {key: f[key] for key in (
                "file", "timestamp", "width", "height", "intrinsics", "cameraToWorld"
            )} | {"trackingState": "unreported"} for f in chosen
        ],
    }
    sidecar = {
        "dataset": "ARKitScenes", "original_capture_device": "Apple iPad Pro / LiDAR",
        "test_device": "none", "is_iphone_11_capture": False,
        "test_class": "public_real_data_proxy_not_iPhone11_N9_acceptance",
        "pose_calibration": "official_traj_world_to_cv_camera inverted",
        "frame_pose_alignment": "nearest_timestamp_without_interpolation",
        "max_tolerance_seconds": max_timestamp_gap_seconds,
        "independent_ground_truth_used": False,
        "physical_device_accepted": False, "real_world_validated": False,
        "source_root": str(source), "video_id": video_id,
        "images": [
            {"file": f["file"], "original_image_sha256": f["sha256"],
             "pincam_sha256": hashlib.sha256(f["src_pincam"].read_bytes()).hexdigest(),
             "pose_time_gap_seconds": f["pose_time_gap_seconds"]} for f in chosen
        ],
    }
    try:
        (stage / "images").mkdir()
        for f in chosen:
            shutil.copyfile(f["src"], stage / "images" / f["file"])
            if hashlib.sha256((stage/"images"/f["file"]).read_bytes()).hexdigest() != f["sha256"]:
                raise RealDatasetError("Post-copy image SHA mismatch")
        (stage / "session.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        (stage / "n9_source_audit.json").write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
        os.replace(stage, output)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return output, sidecar
