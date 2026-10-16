"""N7 UI-independent native pipeline, stage events and output discovery.

Only stage completion is observed: native N3-N6 do not expose measured
per-feature progress. No fake percentage, fake geometry or "success" on failure.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import time


class PipelineError(ValueError):
    pass


class PipelineCancelled(PipelineError):
    pass


RUN_REQUIRED = {
    "sparse": ("summary.json", "cameras.json", "tracks.json", "sparse.ply"),
    "refined": ("summary.json", "cameras.json", "tracks.json", "sparse.ply",
                "optimization.json"),
    "dense": ("summary.json", "dense.ply", "depth_maps.npz", "mesh.obj"),
}


def _read_summary(path):
    if path.stat().st_size > 2 * 1024 * 1024:
        raise PipelineError("Run summary exceeds safe UI inspection limit")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("engine") != "monoscan-native":
        raise PipelineError("Not a MonoScan11 native run")
    return raw


def discover_runs(session: Path):
    """Only fully published known N3–N6 output directories are shown."""
    session = Path(session).resolve()
    base = session / "reconstruction" / "runs"
    if not base.is_dir():
        return []
    result = []
    for sparse in sorted(base.glob("run-*"))[:250]:
        if not sparse.is_dir() or sparse.is_symlink():
            continue
        candidates = [(sparse, "sparse")]
        candidates += [(p, "refined") for p in sorted((sparse / "refinements").glob("n5-*"))[:250]
                       if p.is_dir() and not p.is_symlink()] if (sparse / "refinements").is_dir() else []
        for target, kind in list(candidates):
            dense_base = target / "dense"
            if dense_base.is_dir() and not dense_base.is_symlink():
                candidates += [(p, "dense") for p in sorted(dense_base.glob("n6-*"))[:250]
                               if p.is_dir() and not p.is_symlink()]
        for path, kind in candidates:
            if not all((path / file).is_file() for file in RUN_REQUIRED[kind]):
                continue
            try:
                summary = _read_summary(path / "summary.json")
            except (ValueError, OSError, UnicodeError, json.JSONDecodeError):
                continue
            result.append({
                "path": str(path), "kind": kind, "summary": summary,
                "modified_ns": path.stat().st_mtime_ns,
                "label": kind.upper() + " · " + path.name,
            })
    return sorted(result, key=lambda d: (d["modified_ns"], d["path"]), reverse=True)


def diagnostics(summary):
    """Surface observed metrics vs unknown physical accuracy without extrapolation."""
    if not isinstance(summary, dict):
        raise PipelineError("Missing run diagnostics")
    kind = summary.get("stage", "N3–N6 unknown")
    stage = str(kind)[:160]
    def number(key, digits=3):
        value = summary.get(key)
        return f"{float(value):.{digits}f}" if type(value) in (int, float) else "bilinmiyor"
    rows = [
        ("Aşama", stage),
        ("Durum", str(summary.get("state", "bilinmiyor"))),
        ("Mod", str(summary.get("mode_used", summary.get("source_mode", "bilinmiyor")))),
        ("Kayıtlı kamera", str(summary.get("registered_images",
                                         summary.get("image_count", "bilinmiyor")))),
        ("3B nokta", str(summary.get("point_count",
                                   summary.get("fused_voxel_points", "bilinmiyor")))),
        ("Ortanca reprojeksiyon (px)", number("median_reprojection_error_px")),
        ("BA sonrası ortanca (px)", number("post_ba_median_reprojection_error_px")),
        ("ARKit poz kovaryansı", "kalibre edilmedi / bilinmiyor"),
        ("Gerçek dünya ölçümü", "N9 — doğrulanmadı"),
        ("Ölçek", str(summary.get("scale_status", summary.get("depth_units", "bilinmiyor")))),
        ("Yüzey", str(summary.get("mesh_type", "mevcut değil"))),
    ]
    if summary.get("real_world_validated") is True:
        raise PipelineError("N7 cannot certify real-world scans; unexpected status")
    warnings = summary.get("warnings", [])
    if not isinstance(warnings, list):
        warnings = ["Invalid warning field"]
    return rows, [str(w)[:500] for w in warnings[:20]]


def run_command(arguments, *, cancel=None, timeout=1800):
    """Invoke only the repository-owned CLI; never a shell command."""
    args = [str(a) for a in arguments]
    if not args or args[0] not in ("validate", "reconstruct", "refine", "dense"):
        raise PipelineError("Unsupported native command")
    cli = Path(__file__).resolve().parents[1] / "tools" / "monoscan.py"
    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen(
        [sys.executable, str(cli), *args], stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, creationflags=flags)
    started = time.monotonic()
    try:
        while proc.poll() is None:
            if cancel is not None and cancel.is_set():
                proc.terminate()
                proc.communicate(timeout=10)
                raise PipelineCancelled("İşlem kullanıcı tarafından iptal edildi")
            if time.monotonic() - started > timeout:
                proc.kill()
                proc.communicate(timeout=10)
                raise PipelineError("Native processing exceeded time limit")
            time.sleep(0.075)
        stdout, stderr = proc.communicate()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate()
    if proc.returncode:
        text = stderr.decode("utf-8", "replace").strip()[:900]
        raise PipelineError(text or "Native stage returned a failure code")
    try:
        result = json.loads(stdout.decode("utf-8"))
        if not isinstance(result, dict):
            raise ValueError("Not a JSON object")
        return result
    except (UnicodeError, ValueError) as exc:
        raise PipelineError("Native CLI returned invalid result JSON") from exc


def run_pipeline(session, *, mode="photo-only", focal_px=None,
                 do_refine=False, do_dense=False, depth_min=1.0,
                 depth_max=5.0, planes=40, max_side=192,
                 voxel_size=0.08, prior_weight=2.0,
                 cancel=None, emit=None, execute=None):
    """Stage-accurate UI workflow, with explicit partial outputs on failure.

    The executor is injectable for synthetic UI tests, but production always
    calls the existing separate native process (N3–N6). No fabricated output.
    """
    if mode not in ("photo-only", "arkit-guided"):
        raise PipelineError("Unknown reconstruction mode")
    if do_dense and not do_refine:
        # Dense can consume N3/N4 directly, but N7's single guided
        # pipeline chooses N5 first for predictable stage ordering.
        raise PipelineError("Integrated dense workflow requires N5 enabled")
    if mode == "arkit-guided" and focal_px is not None:
        raise PipelineError("ARKit-guided cannot accept manual focal length")
    if focal_px is not None and (not 1 <= float(focal_px) <= 1e7):
        raise PipelineError("Invalid pixel focal length")
    if do_refine and (not math.isfinite(prior_weight) or not 0 < prior_weight <= 100):
        raise PipelineError("Invalid heuristic ARKit prior weight")
    if do_dense and (
            not math.isfinite(depth_min) or not math.isfinite(depth_max)
            or not 0 < depth_min < depth_max
            or not isinstance(planes, int) or not 8 <= planes <= 128
            or not isinstance(max_side, int) or not 48 <= max_side <= 384
            or not math.isfinite(voxel_size) or not 0 < voxel_size):
        raise PipelineError("Invalid CPU MVS depth/range/voxel limits")
    session = Path(session).resolve()
    runner = execute if execute is not None else run_command
    stages = ["validate", "reconstruct"] + (["refine"] if do_refine else []) + (
        ["dense"] if do_dense else []
    )
    def post(event, stage, **details):
        if emit is not None:
            emit({"event": event, "stage": stage, **details})
    current = None
    previous_run = None
    completed = []
    partial = []
    try:
        for stage in stages:
            if cancel is not None and cancel.is_set():
                raise PipelineCancelled("İşlem kullanıcı tarafından iptal edildi")
            if stage == "validate":
                argv = ["validate", session]
            elif stage == "reconstruct":
                argv = ["reconstruct", session, "--mode", mode]
                if focal_px is not None:
                    argv += ["--focal-px", str(focal_px)]
            elif stage == "refine":
                argv = ["refine", previous_run, "--prior-weight", str(prior_weight)]
            else:
                argv = ["dense", previous_run, session, "--min-depth", str(depth_min),
                        "--max-depth", str(depth_max), "--planes", str(planes),
                        "--max-side", str(max_side), "--voxel-size", str(voxel_size)]
            current = stage
            post("start", stage, completed=len(completed), total=len(stages))
            result = runner(argv, cancel=cancel)
            if not isinstance(result, dict):
                raise PipelineError("Stage did not return a JSON object")
            if stage != "validate":
                run = result.get("run")
                if not isinstance(run, str) or not Path(run).is_dir():
                    raise PipelineError("Native stage has no physically saved run directory")
                previous_run = Path(run).resolve()
            completed.append(stage)
            state = result.get("state", "validated")
            if state == "PARTIAL" or result.get("bundle_adjustment") == "partial_nonconverged":
                partial.append(stage)
            post("complete", stage, completed=len(completed), total=len(stages),
                 run=str(previous_run) if previous_run else None, status=state)
        overall = "PARTIAL" if partial else "COMPLETED_STAGES"
        post("finished", current, completed=len(completed), total=len(stages),
             status=overall, partial_stages=list(partial),
             run=str(previous_run) if previous_run else None)
        return {"completed": completed, "run": str(previous_run) if previous_run else None,
                "state": overall, "partial_stages": partial, "result": result}
    except (PipelineError, OSError, ValueError) as exc:
        post("cancelled" if isinstance(exc, PipelineCancelled) else "failed",
             current or "not_started", completed=len(completed), total=len(stages),
             run=str(previous_run) if previous_run else None, message=str(exc))
        raise


def launch_single_stage(stage, run, session, *, execute=None, emit=None, **settings):
    """Run N5/N6 on an existing verified run selected in the UI."""
    runner = execute or run_command
    run, session = Path(run).resolve(), Path(session).resolve()
    if stage not in ("refine", "dense"):
        raise PipelineError("Only N5 refine / N6 dense are supported")
    args = (["refine", run, "--prior-weight", str(settings.get("prior_weight", 2.0))]
            if stage == "refine" else
            ["dense", run, session, "--min-depth", str(settings.get("min_depth", 1.0)),
             "--max-depth", str(settings.get("max_depth", 5.0)),
             "--planes", str(settings.get("planes", 40)),
             "--max-side", str(settings.get("max_side", 192)),
             "--voxel-size", str(settings.get("voxel_size", 0.08))])
    if emit:
        emit({"event": "start", "stage": stage})
    try:
        result = runner(args, cancel=settings.get("cancel"))
        if not isinstance(result, dict) or not isinstance(result.get("run"), str):
            raise PipelineError("Native action returned no model directory")
        if not Path(result["run"]).is_dir():
            raise PipelineError("Native result is not present on disk")
        if emit:
            emit({"event": "complete", "stage": stage, "run": result["run"],
                  "status": result.get("state", "unknown")})
        return result
    except (PipelineError, OSError, ValueError) as exc:
        if emit:
            emit({"event": "failed", "stage": stage, "message": str(exc)})
        raise
