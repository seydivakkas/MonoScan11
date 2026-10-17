"""N9-A temporal real-image comparison and N5/N6 field-software trial.

Download ONCE to ephemeral GitHub Actions only after explicit terms review.
Predeclare three bounded temporal groups plus historical full-session
uniform baseline; report ALL outcomes including errors (no cherry-picking).
Real Apple ARKitScenes is iPad Pro, not iPhone11. No real RGB, K or
reconstruction binaries are ever exported from the CI worker.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.n9_fetch_arkitscenes import download_one_sequence
from monoscan_core.n9_public_adapter import prepare_arkitscenes_session
from monoscan_core.n9a_acceptance import evaluate_proxy_session, sha256_file
from monoscan_core.workflow import run_command


PREDECLARED_COHORTS = (
    ("uniform-baseline", "uniform", 0.0),
    ("early-window", "temporal-window", 0.10),
    ("mid-window", "temporal-window", 0.45),
    ("late-window", "temporal-window", 0.78),
)
N9B_NOT_TESTED = "NOT_TESTED"


def _public_summary(summary):
    allowed = (
        "engine", "state", "stage", "image_count", "registered_images",
        "point_count", "observation_count", "candidate_pair_matches",
        "median_reprojection_error_px", "mean_reprojection_error_px",
        "pre_ba_median_reprojection_error_px", "post_ba_median_reprojection_error_px",
        "pre_ba_p90_reprojection_error_px", "post_ba_p90_reprojection_error_px",
        "fused_voxel_points", "mesh_faces", "mesh_vertices", "image_count",
        "depth_units", "scale_status", "metric_scale_known",
        "pose_covariance_available", "real_world_validated",
        "bundle_adjustment_status", "bundle_adjustment_success",
    )
    return {key: summary[key] for key in allowed if key in summary}


def _written_model(run):
    run = Path(run).resolve()
    required = ["summary.json"]
    if not all((run / p).is_file() for p in required):
        raise ValueError("Native run lacks summary")
    s = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    known = ("summary.json", "sparse.ply", "tracks.json", "cameras.json",
             "optimization.json", "dense.ply", "mesh.obj", "depth_maps.npz")
    hashes = {name: sha256_file(run / name)
              for name in known if (run / name).is_file()}
    return s, hashes


def _depth_from_real_sparse(model_run):
    """Depth-search range derived from *actual sparse camera/track estimates*.

    Uses uncalibrated ARKit nominal scale, not surveyed ground truth.
    Rejects depths that cannot be estimated. This is a sweep HYPOTHESIS,
    never independent true distance.
    """
    run = Path(model_run)
    cams = json.loads((run / "cameras.json").read_text(encoding="utf-8"))["cameras"]
    tracks = json.loads((run / "tracks.json").read_text(encoding="utf-8"))
    depths = []
    for camera in cams:
        pose = np.asarray(camera["camera_to_world_cv"], dtype=float)
        r, center = pose[:3, :3], pose[:3, 3]
        for track in tracks:
            x = np.asarray(track["xyz"], dtype=float)
            depth = float((r.T @ (x-center))[2])
            if math.isfinite(depth) and depth > 0.05 and depth < 100:
                depths.append(depth)
    if len(depths) < 24:
        raise ValueError("Insufficient actual positive sparse depths to justify N6 sweep")
    low, high = np.percentile(depths, [10, 90])
    low = max(0.05, float(low) * 0.8)
    high = min(100.0, float(high) * 1.25)
    if not (0 < low < high and high/low > 1.03):
        raise ValueError("Degenerate sparse-depth quantile range")
    return round(low, 5), round(high, 5), len(depths)


def real_temporal_trial(output, *, license_reviewed=False, video_id="41069046",
                        split="Validation", max_frames=16, window_seconds=4.0):
    if not license_reviewed:
        raise ValueError("Manual research-data terms review is required")
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("Evidence file already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    report = {
        "protocol": "N9-A-temporal-comparison-v1",
        "utc": datetime.now(timezone.utc).isoformat(),
        "original_dataset": "Apple ARKitScenes",
        "video_id": video_id, "split": split,
        "capture_device": "iPad Pro (not iPhone11)",
        "data_license_attested_for_research": True,
        "selection_rule_predeclared": [
            {"name": k, "strategy": s, "window_start_fraction": q}
            for k, s, q in PREDECLARED_COHORTS
        ],
        "selection_claim": "temporal proximity and observed VIO motion; visual overlap NOT proven in advance",
        "max_frames_per_cohort": max_frames, "window_seconds": window_seconds,
        "source_downloaded": False, "cohorts": [], "best_cohort": None,
        "n5": {"status": "NOT_ATTEMPTED"},
        "n6": {"status": "NOT_ATTEMPTED"},
        "result": "RUNNING",
        "real_world_validated": False, "metric_scale_known": False,
        "independent_survey_used": False,
        "n9b_physical_iphone11": N9B_NOT_TESTED,
        "n9b_physical_windows": N9B_NOT_TESTED,
        "third_party_source_pixels_uploaded": False,
        "limitations": [
            "True Apple iPad Pro real RGB; NOT iPhone11 physical test.",
            "No LiDAR depth used as an input and no Faro independent reference used.",
            "N5 and N6 are experimental; residual/error values are not physical accuracy.",
            "All groups (success, partial, failure) reported, do not select evidence after outcome.",
        ],
    }
    def checkpoint():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    checkpoint()
    with tempfile.TemporaryDirectory(prefix="n9a-apple-original-") as td:
        root = Path(td)
        try:
            source, downloaded = download_one_sequence(video_id, split, root/"original",
                                                       license_reviewed=True)
            report["source_downloaded"] = True
            report["official_original_asset_sha256"] = downloaded["sha256"]
            report["result"] = "DATASET_AVAILABLE"
            checkpoint()
            available = []
            for label, strategy, fraction in PREDECLARED_COHORTS:
                cohort = {
                    "name": label, "strategy": strategy,
                    "start_fraction": fraction if strategy != "uniform" else None,
                    "state": "RUNNING", "real_registered_views": 0,
                    "original_input_sha256": {}, "error": None,
                }
                report["cohorts"].append(cohort)
                checkpoint()
                try:
                    session, audit = prepare_arkitscenes_session(
                        source, root/("session-"+label), video_id=video_id,
                        max_frames=max_frames, selection_strategy=strategy,
                        window_start_fraction=fraction, window_seconds=window_seconds)
                    cohort["selection_audit"] = audit["selection"]
                    cohort["input_original_hashes_sha256"] = hashlib.sha256(
                        json.dumps({v["file"]:v["original_image_sha256"]
                                    for v in audit["images"]},
                                   sort_keys=True).encode()).hexdigest()
                    cohort["image_count"] = len(audit["images"])
                    # Do not emit timestamps/images that could expose a private scene.
                    proxy = evaluate_proxy_session(
                        session, root/("evidence-"+label),
                        mode="arkit-guided", rights_reviewed=True)
                    cohort["native_result"] = proxy["result"]
                    cohort["stage_count"] = len(proxy["events"])
                    rec = next((e for e in proxy["events"]
                                if e["stage"] == "reconstruct"), None)
                    if rec:
                        raw, hashes = _written_model(rec["run"])
                        cohort["native_summary"] = _public_summary(raw)
                        cohort["artifact_sha256"] = hashes
                        cohort["real_registered_views"] = int(raw.get("registered_images", 0))
                        cohort["registration_ratio"] = cohort["real_registered_views"]/cohort["image_count"]
                        cohort["sparse_point_count"] = int(raw.get("point_count", 0))
                        cohort["unregistered_view_count"] = (
                            cohort["image_count"]-cohort["real_registered_views"])
                        cohort["state"] = "PARTIAL" if raw.get("state") == "PARTIAL" else raw.get("state", "UNKNOWN")
                        available.append((cohort, Path(rec["run"]), session))
                    else:
                        cohort["state"] = "FAIL"
                        cohort["error"] = str(proxy.get("failure", {}).get("reason", "No native model"))[:400]
                except Exception as exc:
                    cohort["state"] = "FAIL"
                    cohort["error"] = (type(exc).__name__ + ": " + str(exc).replace(str(root), "<EPHEMERAL>"))[:420]
                checkpoint()
            if not available:
                report["result"] = "FAIL_NO_VALID_SPARSE_MODEL"
            else:
                ranked = sorted(available, key=lambda e: (
                    e[0]["real_registered_views"],
                    e[0].get("sparse_point_count", 0),
                    e[0].get("registration_ratio", 0),
                    -float(e[0].get("native_summary", {}).get("median_reprojection_error_px") or 1000),
                ), reverse=True)
                top, sparse, session = ranked[0]
                report["best_cohort"] = top["name"]
                report["best_selection_rule"] = "maximum registered real views then points then fraction then reprojection residual"
                report["n5"] = {"status":"RUNNING", "source_cohort":top["name"]}
                checkpoint()
                n5path = None
                try:
                    t = time.monotonic()
                    result = run_command(["refine", sparse], timeout=360)
                    n5path = Path(result["run"])
                    s, sha = _written_model(n5path)
                    report["n5"] = {
                        "status": "OUTPUT_REVIEW_REQUIRED",
                        "duration_seconds":round(time.monotonic()-t,3),
                        "summary":_public_summary(s),
                        "artifact_sha256":sha,
                        "physical_accuracy_confirmed":False,
                    }
                except Exception as exc:
                    report["n5"] = {"status":"FAIL", "error":str(exc)[:650]}
                checkpoint()
                registered = top["real_registered_views"]
                if registered < 3 or registered > 8:
                    report["n6"] = {
                        "status":"SKIPPED_UNSUPPORTED_CAMERA_COUNT",
                        "registered_camera_count":registered,
                        "required_registered_cameras":"3–8",
                    }
                else:
                    report["n6"] = {"status":"RUNNING",
                                    "source":"N5 if available else N4"}
                    checkpoint()
                    try:
                        from_run = n5path if n5path else sparse
                        minimum, maximum, count = _depth_from_real_sparse(from_run)
                        report["n6"]["depth_interval"] = [minimum, maximum]
                        report["n6"]["depth_derivation"] = (
                            "N4/N5 observed positive camera-depth 10th/90th percentiles "
                            "with 20%/25% guard bands; ARKit nominal units, NOT physical reference"
                        )
                        report["n6"]["positive_sparse_depth_samples"] = count
                        t = time.monotonic()
                        out = run_command(
                            ["dense", from_run, session,
                             "--min-depth", minimum, "--max-depth", maximum,
                             "--planes", 24, "--max-side", 96,
                             "--voxel-size", 0.08], timeout=360)
                        summary, hashes = _written_model(out["run"])
                        report["n6"].update({
                            "status":"EXPERIMENTAL_GEOMETRY_REVIEW_REQUIRED",
                            "duration_seconds":round(time.monotonic()-t,3),
                            "summary":_public_summary(summary),
                            "artifact_sha256":hashes,
                            "real_world_validated":False,
                        })
                    except Exception as exc:
                        report["n6"].update({"status":"FAIL", "error":str(exc)[:650]})
                report["result"] = (
                    "PROXY_PARTIAL_REVIEW_REQUIRED" if
                    top["real_registered_views"] < top["image_count"]
                    or report["n5"]["status"] != "OUTPUT_REVIEW_REQUIRED"
                    or report["n6"]["status"] != "EXPERIMENTAL_GEOMETRY_REVIEW_REQUIRED"
                    else "PROXY_GEOMETRY_PRODUCED_REVIEW_REQUIRED"
                )
        except Exception as exc:
            report["result"] = "FAIL_SOURCE_OR_PROTOCOL"
            report["error"] = (type(exc).__name__ + ": " + str(exc).replace(str(root), "<EPHEMERAL>"))[:650]
        finally:
            report["wall_time_seconds"] = round(time.monotonic()-t0,3)
            report["n9b_physical_iphone11"] = N9B_NOT_TESTED
            report["real_world_validated"] = False
            checkpoint()
    return report


def main():
    p=argparse.ArgumentParser(description="N9-A real Apple ARKitScenes multiwindow native pipeline")
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--video-id",default="41069046")
    p.add_argument("--split",choices=("Validation","Training"),default="Validation")
    p.add_argument("--max-frames",type=int,default=16)
    p.add_argument("--window-seconds",type=float,default=4.0)
    p.add_argument("--license-reviewed",action="store_true")
    a=p.parse_args()
    result=real_temporal_trial(a.output,license_reviewed=a.license_reviewed,
                               video_id=a.video_id,split=a.split,
                               max_frames=a.max_frames,window_seconds=a.window_seconds)
    print(json.dumps({
        "result":result["result"],
        "dataset":result["original_dataset"],
        "cohorts":[{"name":c["name"],"state":c["state"],
                    "registered":c.get("real_registered_views"),
                    "images":c.get("image_count")}
                   for c in result["cohorts"]],
        "best":result["best_cohort"],
        "N5":result["n5"]["status"],
        "N6":result["n6"]["status"],
        "N9_B":"NOT_TESTED",
        "report":str(a.output)
    },indent=2))
    return 0 if result["result"] in (
        "PROXY_PARTIAL_REVIEW_REQUIRED","PROXY_GEOMETRY_PRODUCED_REVIEW_REQUIRED"
    ) else 1


if __name__=="__main__":
    raise SystemExit(main())
