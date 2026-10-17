"""N8 synthetic acceptance: procedural image->ZIP->N4->N5->N6->N7.

This deliberately invokes the *actual* native command pipeline and local
Swift-compatible ZIP reader, never mocks vision, pose, BA or MVS. Source
texture is generated with a fixed seed, NOT a real scene photograph.
Metrics are diagnostic only, not performance or dimensional certification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import tempfile
import time
import tracemalloc
import sys
import zipfile

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from monoscan_core.workspace import ProjectCatalog
from monoscan_core.workflow import discover_runs, run_pipeline, diagnostics
from monoscan_core.preview import geometry_for_run


def make_procedural_zip(destination: Path):
    width, height = 512, 384
    fx = fy = 470.0
    depth = 2.5
    k = [[fx, 0.0, width/2], [0.0, fy, height/2], [0.0, 0.0, 1.0]]
    cv_to_arkit = np.diag([1.0, -1.0, -1.0, 1.0])
    centers = [(0.0, 0.0, 0.0), (0.32, 0.0, 0.0),
               (-0.16, 0.25, 0.0), (0.18, -0.25, 0.0)]
    rng = np.random.default_rng(38042)
    texture = rng.integers(0, 256, size=(1024, 1024), dtype=np.uint8)
    texture = cv2.GaussianBlur(texture, (5, 5), 0.85)
    # Repeatable geometric landmarks for native SIFT/reciprocal matching.
    for _ in range(260):
        px, py = rng.integers(100, 924, size=2)
        radius = int(rng.integers(3, 9))
        cv2.circle(texture, (int(px), int(py)), radius,
                   255 if (px+py) % 2 else 0, thickness=-1,
                   lineType=cv2.LINE_AA)
    yy, xx = np.indices((height, width), dtype=np.float32)
    png_bytes, frames = {}, []
    for i, (x, y, z) in enumerate(centers):
        name = f"n8_frame_{i:02}.png"
        u = (x + (xx-width/2) * depth/fx) * 180 + 512
        v = (y + (yy-height/2) * depth/fy) * 180 + 512
        gray = cv2.remap(texture, u.astype(np.float32), v.astype(np.float32),
                         cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        image = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        ok, encoded = cv2.imencode(".png", image)
        if not ok:
            raise RuntimeError("Cannot encode N8 procedural image")
        png_bytes[name] = encoded.tobytes()
        cv_pose = np.eye(4)
        cv_pose[:3, 3] = (x, y, z)
        arkit_pose = cv_pose @ cv_to_arkit
        frames.append({
            "file": name, "timestamp": float(i+1), "width": width,
            "height": height, "intrinsics": k,
            "cameraToWorld": arkit_pose.tolist(),
        })
    manifest = {
        "schemaVersion": 1,
        "acquisition": "synthetic_procedural_N8_not_real_iPhone",
        "cameraImageCoordinates": "unrotated synthetic buffer K at 512x384",
        "cameraPoseConvention": "synthetic ARKit nominal-world camera_to_world",
        "frames": frames, "sparsePointCount": 0,
    }
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_STORED) as out:
        out.writestr("session.json", json.dumps(manifest, sort_keys=True))
        for name, image in sorted(png_bytes.items()):
            out.writestr("images/" + name, image)
    return {"source_kind": "procedural_synthetic", "images": 4,
            "ground_truth_plane_z_test_units_only": depth,
            "source_sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _signature(run):
    """Numerical/artifact repeatability within the same environment, not cross-CPU proof."""
    current = Path(run)
    sparse_ancestors = []
    while current.name and current.name.startswith(("n6-", "n5-")):
        sparse_ancestors.append(current)
        current = current.parent.parent
    model = current
    if not (model / "tracks.json").is_file():
        raise AssertionError("N4 source tracks disappeared")
    # Float artifacts are serialized by the same native code on the same host.
    members = {
        "n4_tracks": _sha256(model / "tracks.json"),
        "n4_sparse": _sha256(model / "sparse.ply"),
        "dense_ply": _sha256(Path(run) / "dense.ply"),
        "dense_obj": _sha256(Path(run) / "mesh.obj"),
    }
    if sparse_ancestors:
        for ancestor in sparse_ancestors:
            if ancestor.name.startswith("n5-"):
                members["n5_sparse"] = _sha256(ancestor / "sparse.ply")
                break
    return members


def _rss_snapshot():
    """Current process RSS only; N3-N6 child RSS is not captured on Windows."""
    if platform.system() == "Windows":
        import ctypes
        from ctypes import wintypes
        class Pmc(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]
        pmc = Pmc()
        pmc.cb = ctypes.sizeof(Pmc)
        psapi = ctypes.WinDLL("psapi")
        kernel = ctypes.WinDLL("kernel32")
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = (
            wintypes.HANDLE, ctypes.POINTER(Pmc), wintypes.DWORD
        )
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        if psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),
                                      ctypes.byref(pmc), pmc.cb):
            return {"parent_peak_working_set_bytes": int(pmc.PeakWorkingSetSize),
                    "child_peak_rss_bytes": None}
        return {"parent_peak_working_set_bytes": None, "child_peak_rss_bytes": None}
    import resource
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    self_ru = resource.getrusage(resource.RUSAGE_SELF)
    unit = 1 if platform.system() == "Darwin" else 1024
    return {
        "parent_peak_working_set_bytes": int(self_ru.ru_maxrss * unit),
        "child_peak_rss_bytes": int(children.ru_maxrss * unit),
    }


def run_acceptance(*, repeat=2, persist=None, min_depth=1.7, max_depth=3.1,
                   planes=36, max_side=112):
    if not 1 <= repeat <= 3:
        raise ValueError("N8 acceptance supports 1–3 repeated runs")
    started = time.perf_counter()
    scratch = tempfile.TemporaryDirectory(prefix="monoscan-n8-") if persist is None else None
    try:
        root = Path(scratch.name if scratch else persist).resolve()
        root.mkdir(parents=True, exist_ok=True)
        archive = root / "procedural_arkit.zip"
        metadata = make_procedural_zip(archive)
        catalog = ProjectCatalog(root / "workspace")
        project = catalog.import_zip(archive, name="N8 Procedural Geometry")
        session = catalog.session_path(project["id"])
        original = {p.name: _sha256(p) for p in (session / "images").iterdir()}
        events, signatures, measurements = [], [], []
        tracemalloc.start()
        try:
            for iteration in range(repeat):
                tic = time.perf_counter()
                stage_times = {}
                def emit(event):
                    now = time.perf_counter()
                    events.append(event)
                    if event["event"] == "start":
                        stage_times[event["stage"]] = {"start": now}
                    if event["event"] == "complete":
                        entry = stage_times[event["stage"]]
                        entry["seconds"] = round(now-entry["start"], 4)
                pipeline = run_pipeline(
                    session, mode="arkit-guided", do_refine=True, do_dense=True,
                    depth_min=min_depth, depth_max=max_depth, planes=planes,
                    max_side=max_side, voxel_size=0.10, emit=emit)
                if pipeline["completed"] != ["validate", "reconstruct", "refine", "dense"]:
                    raise AssertionError("N8 native stage sequence incomplete")
                run = Path(pipeline["run"])
                records = discover_runs(session)
                if {"sparse", "refined", "dense"} - {rec["kind"] for rec in records}:
                    raise AssertionError("N7 output discovery missing stages")
                dense = next(rec for rec in records if rec["path"] == str(run))
                if dense["summary"].get("real_world_validated") is not False:
                    raise AssertionError("N8 must never certify physical accuracy")
                rows, warnings = diagnostics(dense["summary"])
                if not any("N9" in text for label, text in rows):
                    raise AssertionError("N9 uncertainty was not shown")
                actual = geometry_for_run(dense, "dense")
                mesh = geometry_for_run(dense, "mesh")
                if len(actual.points) < 24 or not mesh.faces:
                    raise AssertionError("No real saved dense point cloud or open mesh")
                signatures.append(_signature(run))
                measurements.append({
                    "iteration": iteration + 1,
                    "total_seconds": round(time.perf_counter()-tic, 4),
                    "stage_seconds": {k: v.get("seconds") for k, v in stage_times.items()},
                    "sparse_status": pipeline["state"],
                    "dense_points_loaded": len(actual.points),
                    "mesh_faces_loaded": len(mesh.faces),
                    "warnings_count": len(warnings),
                })
            if any(signatures[0] != s for s in signatures[1:]):
                raise AssertionError("Native outputs are not reproducible on identical synthetic inputs")
            if {p.name: _sha256(p) for p in (session / "images").iterdir()} != original:
                raise AssertionError("N8 altered an imported iPhone session image")
            _, peak_python = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        return {
            "stage": "N8", "acceptance": "synthetic_only",
            "engine": "monoscan-native",
            "real_world_validated": False, "metric_scale_known": False,
            "physical_device_tested": False, "first_real_photo_analysis_stage": "N9",
            "mode": "arkit-guided",
            "source_fixture": metadata,
            "run_count": repeat, "same_host_artifact_sha256_equal": True if repeat > 1 else None,
            "duration_total_seconds": round(time.perf_counter()-started, 4),
            "python_tracemalloc_peak_bytes": int(peak_python),
            "rss": _rss_snapshot(),
            "memory_scope_notice": "Python heap is N8 orchestrator only; per-child peak RSS on Windows unknown",
            "runs": measurements,
        }
    finally:
        if scratch:
            scratch.cleanup()


def main():
    parser = argparse.ArgumentParser(description="MonoScan11 N8 procedural, NO real photos")
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--output", type=Path, help="Write report JSON; does not persist scan")
    parser.add_argument("--persist", type=Path, help="Optional explicit test output directory")
    parser.add_argument("--max-side", type=int, default=112)
    parser.add_argument("--planes", type=int, default=36)
    args = parser.parse_args()
    result = run_acceptance(repeat=args.repeat, persist=args.persist,
                            max_side=args.max_side, planes=args.planes)
    report = json.dumps(result, indent=2, ensure_ascii=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report+"\n", encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
