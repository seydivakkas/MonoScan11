"""N9 field research: real public ARKitScenes iPad proxy, never iPhone11 acceptance.

Launch only after authorized dataset assets are present locally.
Real stages may fail; every failure is recorded, no placeholder 3D generated.
The original source session and third-party datasets are never uploaded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from monoscan_core.n9_public_adapter import prepare_arkitscenes_session
from monoscan_core.workflow import run_command, PipelineError


def trial(source: Path, destination: Path, *, video_id: str,
          max_frames=24, run_refine=False, run_dense=False,
          depth_min=None, depth_max=None):
    if run_dense and (depth_min is None or depth_max is None
                      or not 0 < depth_min < depth_max):
        raise ValueError("Real depth hypothesis interval must be separately justified")
    destination = Path(destination).expanduser().resolve()
    if destination.exists():
        raise ValueError("N9 trial refuses to overwrite previous evidence")
    begun = time.perf_counter()
    path, source_audit = prepare_arkitscenes_session(
        source, destination, video_id=video_id, max_frames=max_frames)
    evidence = {
        "stage": "N9", "capture_device": "iPad Pro",
        "proxy_for_iphone11": True, "is_iphone11_capture": False,
        "data_origin": "public_real_scene_with_license_to_be_verified",
        "real_world_validated": False, "independent_metric_reference_used": False,
        "physical_iphone11_tested": False, "physical_windows_acceptance": False,
        "trial_status": "RUNNING", "public_source": source_audit,
        "stages": [], "last_run": None,
    }
    report_path = destination / "n9_trial_report.json"
    def checkpoint():
        report_path.write_text(json.dumps(evidence, indent=2)+"\n", encoding="utf-8")
    checkpoint()
    sequence = [
        ("validate", ["validate", path]),
        ("reconstruct", ["reconstruct", path, "--mode", "arkit-guided"]),
    ]
    try:
        for name, argv in sequence:
            started = time.perf_counter()
            result = run_command(argv, timeout=600)
            evidence["stages"].append({
                "stage": name, "state": "returned",
                "duration_seconds": round(time.perf_counter()-started, 4),
                "result_state": result.get("state", "unknown"),
            })
            if name == "reconstruct":
                evidence["last_run"] = result["run"]
                evidence["stages"][-1]["registered_images"] = result.get("registered_images")
                evidence["stages"][-1]["metric_scale_known"] = result.get("metric_scale_known")
            checkpoint()
        if run_refine:
            started = time.perf_counter()
            result = run_command(["refine", evidence["last_run"]], timeout=600)
            evidence["last_run"] = result["run"]
            evidence["stages"].append({
                "stage": "refine", "state": "returned",
                "duration_seconds": round(time.perf_counter()-started, 4),
                "result_state": result.get("state", "unknown"),
                "bundle_adjustment": result.get("bundle_adjustment"),
            })
            checkpoint()
        if run_dense:
            started = time.perf_counter()
            result = run_command([
                "dense", evidence["last_run"], path, "--min-depth", str(depth_min),
                "--max-depth", str(depth_max)
            ], timeout=900)
            evidence["last_run"] = result["run"]
            evidence["stages"].append({
                "stage": "dense", "state": "returned",
                "duration_seconds": round(time.perf_counter()-started, 4),
                "fused_voxel_points": result.get("fused_voxel_points"),
                "mesh_faces": result.get("mesh_faces"),
            })
            checkpoint()
        evidence["trial_status"] = "PROXY_COMPLETED_REVIEW_REQUIRED"
    except (KeyError, PipelineError, OSError, ValueError) as exc:
        evidence["trial_status"] = "FAILED"
        evidence["failure_reason"] = str(exc)[:800]
    evidence["total_seconds"] = round(time.perf_counter()-begun, 4)
    evidence["warnings"] = [
        "Public iPad Pro scans are not MonoScan11 iPhone 11 captures.",
        "ARKitScenes public data license must be verified by user/reviewer.",
        "ARKit / mobile LiDAR depth must not be counted as independent Faro survey.",
        "Physical iPhone11/Xcode, camera optics, actual Windows UI and reference accuracy are still open.",
    ]
    checkpoint()
    return evidence


def main():
    parser = argparse.ArgumentParser(description="N9 real iPad public-data proxy; NO automatic iPhone11 certification")
    parser.add_argument("--source", required=True, type=Path, help="Official local ARKitScenes RAW sequence")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--max-frames", type=int, default=24)
    parser.add_argument("--refine", action="store_true")
    parser.add_argument("--dense", action="store_true")
    parser.add_argument("--min-depth", type=float)
    parser.add_argument("--max-depth", type=float)
    args = parser.parse_args()
    result = trial(args.source, args.output, video_id=args.video_id,
                   max_frames=args.max_frames, run_refine=args.refine,
                   run_dense=args.dense, depth_min=args.min_depth,
                   depth_max=args.max_depth)
    print(json.dumps(result, indent=2))
    if result["trial_status"] == "FAILED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
