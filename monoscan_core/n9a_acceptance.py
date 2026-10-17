"""N9-A: repeatable public *real-image* proxy evidence, separate from N9-B.

Requires already-authorized original data prepared by an N9 adapter.
Does not download assets, synthesize camera intrinsics, calibrate optics,
invent poses, or certify iPhone11. All native processing uses COLMAP-free core.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import time

from .workflow import run_command, PipelineError


class N9AError(ValueError):
    """An invalid or unavailable real-data evidence prerequisite."""


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while True:
            buf = stream.read(1024 * 1024)
            if not buf:
                break
            digest.update(buf)
    return digest.hexdigest()


def inspect_input(session, mode):
    """Fail-closed evidence inventory; never infer a physical capture device."""
    root = Path(session).expanduser().resolve()
    if mode not in ("photo-only", "arkit-guided"):
        raise N9AError("Unsupported real-data mode")
    audit_path = root / "n9_source_audit.json"
    if not audit_path.is_file() or audit_path.stat().st_size > 2_000_000:
        raise N9AError("MISSING_SOURCE_AUDIT: N9 adapter's source record is required")
    try:
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError, OSError) as exc:
        raise N9AError("Corrupt N9 real-data source audit") from exc
    if not isinstance(audit, dict) or audit.get("real_world_validated") is not False:
        raise N9AError("Source must explicitly remain physically unvalidated")
    if mode == "photo-only":
        if (audit.get("dataset") != "PIX4D Olympic Flame real JPEG example"
                or audit.get("not_iphone11") is not True
                or audit.get("no_native_arkit_poses") is not True
                or not isinstance(audit.get("source_zip_sha256"), str)
                or len(audit["source_zip_sha256"]) != 64
                or (root / "session.json").exists()):
            raise N9AError("Unknown PHOTO_ONLY public dataset/pose provenance")
        claims = audit.get("frames")
        sha_key = "sha256"
        origin = "Pix4D iPhone13 photo-only proxy"
    else:
        if (audit.get("dataset") != "ARKitScenes"
                or audit.get("is_iphone_11_capture") is not False
                or audit.get("original_capture_device") != "Apple iPad Pro / LiDAR"
                or not (root / "session.json").is_file()):
            raise N9AError("Unknown guided public dataset/pose provenance")
        claims = audit.get("images")
        sha_key = "original_image_sha256"
        origin = "Apple ARKitScenes iPadPro guided proxy"
    if not isinstance(claims, list) or not 3 <= len(claims) <= 150:
        raise N9AError("Insufficient explicitly recorded original RGB images")
    frames = []
    names = set()
    for rec in claims:
        if not isinstance(rec, dict) or not isinstance(rec.get("file"), str):
            raise N9AError("Invalid source image ledger")
        name = rec["file"]
        if (name in names or name.casefold() in {n.casefold() for n in names}
                or name in ("", ".", "..")
                or "/" in name or "\\" in name or Path(name).name != name):
            raise N9AError("Unsafe or repeated source image name")
        names.add(name)
        path = root / "images" / name
        if not path.is_file() or path.is_symlink():
            raise N9AError("Required original RGB missing: " + name)
        digest = sha256_file(path)
        if digest != rec.get(sha_key):
            raise N9AError("Source RGB SHA-256 mismatch: " + name)
        frames.append({"file": name, "sha256": digest, "size_bytes": path.stat().st_size})
    existing = {p.name for p in (root / "images").iterdir()
                if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png")}
    if existing != names:
        raise N9AError("Native image folder differs from imported evidence ledger")
    return {
        "source_dataset": audit["dataset"],
        "origin": origin,
        "mode": mode,
        "proxy_not_iphone11": True,
        "source_ledger_sha256": sha256_file(audit_path),
        "source_image_count": len(frames),
        "source_images": frames,
        "source_archive_sha256_claim": audit.get("source_zip_sha256"),
        "original_source_sha_external_verified": False,
    }


def _model_evidence(raw, mode):
    if not isinstance(raw, dict) or not isinstance(raw.get("run"), str):
        raise N9AError("Native runner did not report an existing run")
    run = Path(raw["run"]).expanduser().resolve()
    if not run.is_dir() or not (run / "summary.json").is_file():
        raise N9AError("Reported model does not exist")
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    if (summary.get("engine") != "monoscan-native"
            or summary.get("real_world_validated") is True):
        raise N9AError("Model is not a supported unverified MonoScan11 run")
    artifacts = {p.name: sha256_file(p) for p in run.iterdir()
                 if p.is_file() and p.name in {
                     "summary.json", "sparse.ply", "tracks.json",
                     "cameras.json", "dense.ply", "mesh.obj", "depth_maps.npz",
                     "optimization.json"
                 }}
    if "summary.json" not in artifacts:
        raise N9AError("Native artifacts have no provenance summary")
    return {
        "run": str(run), "reported_state": str(summary.get("state", "UNREPORTED")),
        "mode_recorded": summary.get("mode_used", summary.get("source_mode")),
        "artifact_sha256": artifacts,
        "real_world_validated": False,
    }


def evaluate_proxy_session(session, evidence_dir, *, mode, focal_px=None,
                           rights_reviewed=False, run_refine=False,
                           run_dense=False, min_depth=None, max_depth=None,
                           dry_run=False, execute=None):
    """Execute actual native modules and checkpoint each stage's real outcome.

    Injection is provided solely for isolated, labeled synthetic unit tests.
    All results are PROXY ONLY and never authorize N9-B physical acceptance.
    """
    if not rights_reviewed:
        raise N9AError("Dataset usage rights must be reviewed before the trial")
    if mode == "photo-only":
        if (focal_px is None or not isinstance(focal_px, (int, float))
                or isinstance(focal_px, bool)
                or not math.isfinite(focal_px) or not 1 <= focal_px <= 1e7):
            raise N9AError("PHOTO_ONLY requires a separately verified pixel focal length")
    elif focal_px is not None:
        raise N9AError("ARKit guided mode uses original per-frame intrinsics, not focal override")
    if run_dense and (min_depth is None or max_depth is None
                      or not all(math.isfinite(v) for v in [min_depth, max_depth])
                      or not 0 < min_depth < max_depth):
        raise N9AError("MVS interval must be explicitly justified for this proxy source")
    session = Path(session).resolve()
    inspected = inspect_input(session, mode)
    target = Path(evidence_dir).expanduser().resolve()
    if target == session or session in target.parents or target in session.parents:
        raise N9AError("Keep immutable N9-A evidence outside the input folder")
    if target.exists():
        raise N9AError("Refuse to replace an existing N9-A trial record")
    started = time.perf_counter()
    report = {
        "protocol": "N9-A v1",
        "classification": "SYNTHETIC_CONTRACT_TEST" if execute else "REAL_PUBLIC_IMAGE_PROXY",
        "result": "RUNNING",
        "source": inspected, "rights_reviewed_attested": True,
        "physical_iphone11_tested": False, "physical_windows_acceptance": False,
        "independent_reference_used": False, "metric_accuracy_certified": False,
        "real_world_validated": False, "n9b_status": "NOT_TESTED",
        "events": [],
        "limitations": [
            "Dataset capture device is not iPhone11.",
            "Dataset source/capture metadata are not independently metrologically verified.",
            "No successful proxy trial can close an N9-B physical requirement.",
        ],
    }
    target.mkdir(parents=True)
    report_path = target / "n9a_report.json"
    def save():
        report_path.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    save()
    if dry_run:
        report["result"] = "SOURCE_PREFLIGHT_ONLY"
        report["duration_seconds"] = round(time.perf_counter()-started, 4)
        save()
        return report
    runner = execute or run_command
    previous = None
    steps = [("validate", ["validate", session])]
    args = ["reconstruct", session, "--mode", mode]
    if mode == "photo-only":
        args += ["--focal-px", str(focal_px)]
    steps.append(("reconstruct", args))
    if run_refine:
        steps.append(("refine", None))
    if run_dense:
        steps.append(("dense", None))
    try:
        for stage, args in steps:
            if stage == "refine":
                args = ["refine", previous]
            if stage == "dense":
                args = ["dense", previous, session,
                        "--min-depth", str(min_depth), "--max-depth", str(max_depth)]
            tick = time.perf_counter()
            result = runner(args, timeout=1800)
            if not isinstance(result, dict):
                raise N9AError("Native stage returned non-JSON result")
            if stage != "validate":
                entry = _model_evidence(result, mode)
                # Physical run path must be owned by this source session.
                run = Path(entry["run"])
                if not run.is_relative_to(session / "reconstruction" / "runs"):
                    raise N9AError("Unexpected run outside source session")
                previous = run
            else:
                entry = {"validation_images": result.get("images"),
                         "recorded_pose_count": result.get("pose_records")}
                if entry["validation_images"] != inspected["source_image_count"]:
                    raise N9AError("Native validator/image provenance count differs")
            report["events"].append({
                "stage": stage, "state": "NATIVE_RETURNED",
                "duration_seconds": round(time.perf_counter()-tick, 4), **entry,
            })
            save()
        after = inspect_input(session, mode)
        if after["source_images"] != inspected["source_images"]:
            raise N9AError("Original RGB modified during real-data processing")
        report["result"] = "PROXY_PROCESSING_COMPLETED_REVIEW_REQUIRED"
    except (ValueError, OSError, KeyError, PipelineError, N9AError) as exc:
        report["result"] = "PROXY_FAILED"
        report["failure"] = {
            "attempted_stage": stage,
            "reason": str(exc)[:800],
        }
    report["duration_seconds"] = round(time.perf_counter()-started, 4)
    save()
    return report
