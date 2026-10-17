"""N9-A authorized public real-RGB CI research trial (Apple ARKitScenes iPad).

This is not a simulated data trial and not an iPhone11 physical test.
The script downloads to an ephemeral CI directory. Only anonymized source
hashes and diagnostic JSON are saved as build artifacts; photos, poses,
trajectories, camera data, and reconstructed models are NOT uploaded.

Provider: https://github.com/apple-aiml-research/ARKitScenes
License: https://github.com/apple-aiml-research/ARKitScenes/blob/main/LICENSE
Official documented download scheme: .../v1/raw/Validation/41069046/

Only execute after a person reviews the provider's actual terms for this
specific use. The command line must include --license-reviewed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.n9_fetch_arkitscenes import download_one_sequence, DatasetFetchError
from monoscan_core.n9_public_adapter import prepare_arkitscenes_session, RealDatasetError
from monoscan_core.n9a_acceptance import evaluate_proxy_session, N9AError


def _save(path, report):
    Path(path).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _scrub(message, root):
    """Do not leak personal runner paths or private archive locations."""
    return str(message).replace(str(root), "<EPHEMERAL_DATA>").replace(
        str(root).replace("/", "\\"), "<EPHEMERAL_DATA>")[:750]


def execute_trial(output, *, license_reviewed, video_id="41069046",
                  split="Validation", max_frames=16, max_runtime_seconds=900):
    if not license_reviewed:
        raise ValueError("Explicit license review is required for public-data processing")
    if not 3 <= max_frames <= 32:
        raise ValueError("CI research frame count must be 3–32")
    if not 60 <= max_runtime_seconds <= 1800:
        raise ValueError("CI research budget must be 60–1800 seconds")
    start = time.monotonic()
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("Do not overwrite previous N9-A public evidence")
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "protocol": "N9-A-public-real-images-v1",
        "utc": datetime.now(timezone.utc).isoformat(),
        "dataset": "Apple ARKitScenes", "captured_on": "iPad Pro (not iPhone11)",
        "source_video_id": video_id, "split": split,
        "source_repository": "https://github.com/apple-aiml-research/ARKitScenes",
        "dataset_terms": "Reviewed for limited non-redistributed local CI research use",
        "license_reviewed_researcher_attestation": True,
        "real_original_rgb_downloaded": None,
        "real_original_rgb_processed": None,
        "real_native_stages_completed": 0,
        "run_geometry_successful": False,
        "result": "RUNNING",
        "n9b_physical_device": "NOT_TESTED",
        "iphone11_model_accepted": False, "physical_windows_accepted": False,
        "independent_survey_accuracy_accepted": False, "real_world_validated": False,
        "third_party_pixels_uploaded_to_github": False,
        "stage_evidence": [],
    }
    _save(output, report)
    with tempfile.TemporaryDirectory(prefix="monoscan-n9a-realdata-") as scratch:
        root = Path(scratch)
        try:
            def budget(stage):
                if time.monotonic()-start > max_runtime_seconds:
                    raise TimeoutError("Configured N9-A overall runtime cap reached before " + stage)
            budget("public download")
            report["result"] = "DOWNLOADING_REAL_PUBLIC_RGB"
            _save(output, report)
            source, meta = download_one_sequence(
                video_id, split, root / "official-public-assets",
                license_reviewed=license_reviewed)
            report["official_source_hashes"] = meta["sha256"]
            report["real_original_rgb_downloaded"] = True
            report["result"] = "SOURCE_DOWNLOADED"
            _save(output, report)
            budget("RGB/pose/intrinsics adaptation")
            session, ledger = prepare_arkitscenes_session(
                source, root / "native-session", video_id=video_id,
                max_frames=max_frames)
            report["real_original_rgb_processed"] = len(ledger["images"])
            report["input_image_sha256"] = {
                rec["file"]: rec["original_image_sha256"]
                for rec in ledger["images"]
            }
            report["pose_time_gap_seconds"] = {
                rec["file"]: rec["pose_time_gap_seconds"]
                for rec in ledger["images"]
            }
            report["result"] = "SOURCE_PREFLIGHT_SUCCEEDED"
            _save(output, report)
            budget("real native N4 reconstruction")
            original = evaluate_proxy_session(
                session, root / "native-research-report",
                mode="arkit-guided", rights_reviewed=True)
            report["real_native_stages_completed"] = len(original.get("events", []))
            report["real_native_report"] = {
                "classification": original.get("classification"),
                "result": original.get("result"),
                "events": [
                    {
                        "stage": e.get("stage"),
                        "state": e.get("state"),
                        "reported_state": e.get("reported_state"),
                        "duration_seconds": e.get("duration_seconds"),
                        "artifact_sha256": e.get("artifact_sha256", {}),
                    }
                    for e in original.get("events", [])
                ],
                "failure": _scrub(original.get("failure", {}).get("reason", ""), root)
                if original.get("failure") else None,
            }
            report["run_geometry_successful"] = (
                original.get("result") in {
                    "PROXY_PARTIAL_REVIEW_REQUIRED",
                    "PROXY_PROCESSING_COMPLETED_REVIEW_REQUIRED",
                } and any(e.get("stage") == "reconstruct" for e in original.get("events", []))
            )
            report["result"] = original.get("result", "UNRECOGNIZED")
        except (DatasetFetchError, RealDatasetError, N9AError,
                RuntimeError, TimeoutError, OSError, ValueError) as exc:
            report["result"] = (
                "BLOCKED_REMOTE_DATA_ACCESS" if not report["real_original_rgb_downloaded"]
                else ("REAL_SOURCE_INVALID" if report["real_original_rgb_processed"] is None
                      else "PROXY_FAILED")
            )
            report["failure_type"] = type(exc).__name__
            report["failure_detail"] = _scrub(exc, root)
        except Exception as exc:
            report["result"] = "UNEXPECTED_TRIAL_FAILURE"
            report["failure_type"] = type(exc).__name__
            report["failure_detail"] = _scrub(exc, root)
        finally:
            report["elapsed_seconds"] = round(time.monotonic()-start, 3)
            report["real_world_validated"] = False
            report["iphone11_model_accepted"] = False
            report["physical_windows_accepted"] = False
            report["n9b_physical_device"] = "NOT_TESTED"
            _save(output, report)
    return report


def main():
    parser = argparse.ArgumentParser(description="N9-A Apple iPad RGB real-data CI probe, not iPhone11")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--video-id", default="41069046")
    parser.add_argument("--split", choices=("Validation", "Training"), default="Validation")
    parser.add_argument("--max-frames", type=int, default=16)
    parser.add_argument("--max-runtime-seconds", type=int, default=900)
    parser.add_argument("--license-reviewed", action="store_true",
                        help="I have reviewed Apple's dataset terms for this trial; no redistribution")
    args = parser.parse_args()
    outcome = execute_trial(
        args.output, license_reviewed=args.license_reviewed,
        video_id=args.video_id, split=args.split,
        max_frames=args.max_frames, max_runtime_seconds=args.max_runtime_seconds)
    print(json.dumps({
        "result": outcome["result"],
        "source": outcome["dataset"],
        "real_images_processed": outcome["real_original_rgb_processed"],
        "stages_completed": outcome["real_native_stages_completed"],
        "n9b_physical_device": outcome["n9b_physical_device"],
        "third_party_pixels_uploaded_to_github": False,
        "evidence_report": str(args.output),
    }, indent=2))
    # We want blocked/failed public trials to be visible RED in Actions,
    # without calling these legitimate failures "successful geometry."
    return 0 if outcome["result"] in {
        "PROXY_PARTIAL_REVIEW_REQUIRED",
        "PROXY_PROCESSING_COMPLETED_REVIEW_REQUIRED",
    } else 1


if __name__ == "__main__":
    raise SystemExit(main())
