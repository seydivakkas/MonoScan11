"""N7 headless synthetic-only Windows UI contract, ZIP security and workflow tests."""
import hashlib
import json
import sys
from pathlib import Path
import struct
import tempfile
import threading
import unittest
import zipfile
import zlib

from monoscan_core.preview import (
    PreviewError, geometry_for_run, load_ascii_ply, load_obj_mesh,
    project_preview,
)
from monoscan_core.workspace import (
    WorkspaceError, ProjectCatalog, validate_archive, native_validate,
)
from monoscan_core.workflow import (
    PipelineCancelled, PipelineError, diagnostics, discover_runs,
    run_pipeline, run_command,
)


def synthetic_png(w=64, h=48):
    """Actual valid PNG bytes, pixels procedurally calculated (not a photo)."""
    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload +
                struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            raw.extend(((x*7 + y*3) % 256, (y*11) % 256, (x*5) % 256))
    return (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def session_payload():
    images = {}
    frames = []
    for i in range(3):
        name = f"frame_{i:04d}.png"
        images[name] = synthetic_png()
        pose = [[1, 0, 0, 0.22*i], [0, 1, 0, 0],
                [0, 0, 1, 0], [0, 0, 0, 1]]
        frames.append({"file": name, "timestamp": float(i+1),
                       "width": 64, "height": 48,
                       "intrinsics": [[65., 0., 32.], [0., 65., 24.], [0., 0., 1.]],
                       "cameraToWorld": pose})
    return {"schemaVersion": 1, "frames": frames}, images


def create_fixture(folder):
    folder = Path(folder)
    session = folder / "test-session"
    images_dir = session / "images"
    images_dir.mkdir(parents=True)
    manifest, images = session_payload()
    (session / "session.json").write_text(json.dumps(manifest), encoding="utf-8")
    for name, image in images.items():
        (images_dir / name).write_bytes(image)
    return session, manifest, images


def build_zip(archive, manifest, images, *, extras=None, compression=zipfile.ZIP_STORED):
    with zipfile.ZipFile(archive, "w") as data:
        data.writestr("session.json", json.dumps(manifest), compress_type=compression)
        for name, payload in images.items():
            data.writestr("images/" + name, payload, compress_type=compression)
        for key, payload in (extras or {}).items():
            data.writestr(key, payload, compress_type=compression)


def fake_ply():
    return ("ply\nformat ascii 1.0\ncomment synthetic only\n"
            "element vertex 4\nproperty float x\nproperty float y\n"
            "property float z\nproperty uchar red\nproperty uchar green\n"
            "property uchar blue\nend_header\n"
            "0 0 2 255 0 0\n1 0 2 0 255 0\n"
            "0 1 2 0 0 255\n1 1 2 200 200 200\n")


def create_run(session, kind="sparse"):
    root = Path(session) / "reconstruction" / "runs" / "run-synthetic"
    root.mkdir(parents=True, exist_ok=True)
    (root / "summary.json").write_text(json.dumps({
        "engine": "monoscan-native", "mode_used": "arkit-guided",
        "state": "PARTIAL", "registered_images": 3,
        "metric_scale_known": False, "real_world_validated": False,
        "warnings": ["Synthetic only; not accepted on real iPhone"],
    }), encoding="utf-8")
    (root / "sparse.ply").write_text(fake_ply(), encoding="ascii")
    (root / "cameras.json").write_text('{"cameras":[]}', encoding="utf-8")
    (root / "tracks.json").write_text("[]", encoding="utf-8")
    if kind == "sparse":
        return root
    refined = root / "refinements" / "n5-synthetic"
    refined.mkdir(parents=True)
    for name in ("summary.json", "sparse.ply", "cameras.json", "tracks.json"):
        (refined / name).write_bytes((root / name).read_bytes())
    (refined / "optimization.json").write_text("{}", encoding="utf-8")
    if kind == "refined":
        return refined
    dense = refined / "dense" / "n6-synthetic"
    dense.mkdir(parents=True)
    (dense / "summary.json").write_text(json.dumps({
        "engine": "monoscan-native",
        "stage": "N6 experimental",
        "state": "SYNTHETIC_GEOMETRY_ONLY",
        "source_mode": "arkit-guided", "real_world_validated": False,
        "mesh_type": "single-view_open_triangulated_surface_not_watertight",
        "fused_voxel_points": 4,
    }), encoding="utf-8")
    (dense / "dense.ply").write_text(fake_ply(), encoding="ascii")
    (dense / "mesh.obj").write_text(
        "# open synthetic mesh\nv 0 0 2\nv 1 0 2\n"
        "v 0 1 2\nv 1 1 2\nf 1 2 3\nf 2 4 3\n", encoding="ascii")
    (dense / "depth_maps.npz").write_bytes(b"synthetic test placeholder")
    return dense


class WindowsDesktopSmokeTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Actual Tk window smoke test requires Windows")
    def test_real_tk_workstation_creates_and_renders_empty_state(self):
        from monoscan_core.desktop import MonoScanDesktop
        with tempfile.TemporaryDirectory() as td:
            window = MonoScanDesktop(root=Path(td) / "catalog")
            try:
                window.withdraw()
                window.update_idletasks()
                window.update()
                self.assertIn("MonoScan11", window.title())
                self.assertEqual(window.projects_list.size(), 0)
                self.assertEqual(window.stage_list.size(), 4)
                self.assertIsNone(window.preview_model)
                self.assertIn("Henüz", window.inspector.get("1.0", "end"))
                window._mark_stage("reconstruct", "KISMİ")
                self.assertIn("KISMİ", window.stage_list.get(1))
            finally:
                window.destroy()


class WorkspaceContractTests(unittest.TestCase):
    def test_swift_zipstore_compatible_synthetic_session_import(self):
        with tempfile.TemporaryDirectory() as td:
            source, manifest, images = create_fixture(td)
            archive = Path(td) / "iphone-export.zip"
            build_zip(archive, manifest, images,
                      extras={"project.json": '{"name":"synthetic"}',
                              "arkit_sparse.ply": fake_ply()})
            names, read = validate_archive(archive)
            self.assertEqual(read["schemaVersion"], 1)
            self.assertIn("images/frame_0000.png", names)
            catalog = ProjectCatalog(Path(td) / "workspace")
            project = catalog.import_zip(archive, name="Sentetik çekim")
            folder = catalog.session_path(project["id"])
            self.assertEqual(native_validate(folder)["images"], 3)
            self.assertEqual((folder / "images" / "frame_0002.png").read_bytes(),
                             images["frame_0002.png"])
            self.assertTrue((folder / "arkit_sparse.ply").is_file())
            self.assertEqual(ProjectCatalog(catalog.root).projects()[0]["name"],
                             "Sentetik çekim")
            catalog.remove(project["id"])
            self.assertEqual(catalog.projects(), [])
            self.assertTrue((folder / "session.json").exists())  # never delete user's data
            self.assertTrue(source.joinpath("session.json").exists())

    def test_linked_session_read_only_and_catalog_recovery(self):
        with tempfile.TemporaryDirectory() as td:
            root, _, _ = create_fixture(td)
            catalog = ProjectCatalog(Path(td) / "workspace")
            p = catalog.link_folder(root)
            self.assertEqual(catalog.session_path(p["id"]), root.resolve())
            self.assertEqual(p["origin"], "linked")
            catalog.remove(p["id"])
            self.assertTrue(root.is_dir())
            (catalog.root / "projects.json").write_text("{bad", encoding="utf-8")
            with self.assertRaisesRegex(WorkspaceError, "Corrupt"):
                ProjectCatalog(catalog.root)

    def test_zip_slip_and_compressed_content_rejected_without_side_effect(self):
        with tempfile.TemporaryDirectory() as td:
            _, manifest, images = create_fixture(td)
            zip_path = Path(td) / "bad.zip"
            build_zip(zip_path, manifest, images, extras={"../evil.txt": "attack"})
            with self.assertRaisesRegex(WorkspaceError, "Unsafe"):
                validate_archive(zip_path)
            catalog = ProjectCatalog(Path(td) / "workspace")
            with self.assertRaises(WorkspaceError):
                catalog.import_zip(zip_path)
            self.assertFalse((Path(td) / "evil.txt").exists())
            build_zip(zip_path, manifest, images, compression=zipfile.ZIP_DEFLATED)
            with self.assertRaisesRegex(WorkspaceError, "method-0"):
                validate_archive(zip_path)
            self.assertEqual(catalog.projects(), [])

    def test_zip_missing_image_or_duplicate_name_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            _, manifest, images = create_fixture(td)
            path = Path(td) / "bad.zip"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("session.json", json.dumps(manifest))
                for name, raw in images.items():
                    z.writestr("images/" + name, raw)
                z.writestr("images/frame_0000.png", images["frame_0000.png"])
            with self.assertRaisesRegex(WorkspaceError, "duplicate"):
                validate_archive(path)
            build_zip(path, manifest, dict(list(images.items())[:2]))
            with self.assertRaisesRegex(WorkspaceError, "match manifest"):
                validate_archive(path)

    def test_zip_nonfinite_pose_refused_by_native_validator(self):
        with tempfile.TemporaryDirectory() as td:
            _, manifest, images = create_fixture(td)
            manifest["frames"][0]["cameraToWorld"][0][0] = float("nan")
            archive = Path(td) / "invalid.zip"
            build_zip(archive, manifest, images)
            cat = ProjectCatalog(Path(td) / "workspace")
            with self.assertRaises(WorkspaceError):
                cat.import_zip(archive)
            self.assertFalse(any((cat.root / "sessions").glob("*.json")))


class WorkstationModelTests(unittest.TestCase):
    def test_real_disk_outputs_discovered_but_incomplete_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            session, _, _ = create_fixture(td)
            self.assertEqual(discover_runs(session), [])
            dense = create_run(session, "dense")
            outputs = discover_runs(session)
            self.assertEqual({x["kind"] for x in outputs}, {"sparse", "refined", "dense"})
            dense_item = next(x for x in outputs if x["kind"] == "dense")
            rows, warnings = diagnostics(dense_item["summary"])
            self.assertIn("N9", str(rows))
            self.assertIn("doğrulanmadı", str(rows))
            self.assertFalse(dense_item["summary"]["real_world_validated"])
            self.assertGreaterEqual(len(warnings), 0)
            (dense / "mesh.obj").unlink()
            self.assertNotIn("dense", {x["kind"] for x in discover_runs(session)})

    def test_empty_and_corrupt_preview_do_not_generate_fake_geometry(self):
        with tempfile.TemporaryDirectory() as td:
            ply = Path(td) / "synthetic.ply"
            ply.write_text(fake_ply(), encoding="ascii")
            model = load_ascii_ply(ply, max_points=50)
            self.assertEqual(len(model.points), 4)
            self.assertEqual(model.colors[0], "#ff0000")
            xy = project_preview(model.points, 800, 500, yaw=0.3, pitch=-0.2)
            self.assertEqual(len(xy), 4)
            self.assertTrue(all(0 < x < 800 and 0 < y < 500 for x, y, _ in xy))
            ply.write_text("ply\nformat ascii 1.0\nelement vertex 3\nend_header\n0 0 0\n")
            with self.assertRaisesRegex(PreviewError, "Truncated"):
                load_ascii_ply(ply)

    def test_sparse_dense_and_mesh_switch_use_only_real_files(self):
        with tempfile.TemporaryDirectory() as td:
            session, _, _ = create_fixture(td)
            out = create_run(session, "dense")
            records = discover_runs(session)
            sparse = next(x for x in records if x["kind"] == "sparse")
            refined = next(x for x in records if x["kind"] == "refined")
            dense = next(x for x in records if x["kind"] == "dense")
            self.assertEqual(len(geometry_for_run(sparse, "sparse").points), 4)
            self.assertEqual(len(geometry_for_run(refined, "refined").points), 4)
            self.assertEqual(len(geometry_for_run(dense, "dense").points), 4)
            open_mesh = geometry_for_run(dense, "mesh")
            self.assertEqual(open_mesh.kind, "mesh")
            self.assertEqual(len(open_mesh.faces), 2)
            with self.assertRaisesRegex(PreviewError, "only for N6"):
                geometry_for_run(sparse, "dense")

    def test_unverified_metric_claims_are_rejected(self):
        report = {"engine": "monoscan-native", "real_world_validated": True}
        with self.assertRaisesRegex(PipelineError, "cannot certify"):
            diagnostics(report)


class PipelineStageTests(unittest.TestCase):
    def test_actual_native_validator_on_procedural_png(self):
        with tempfile.TemporaryDirectory() as td:
            session, _, _ = create_fixture(td)
            result = run_command(["validate", session])
            self.assertEqual(result["images"], 3)
            self.assertEqual(result["pose_records"], 3)

    def test_injected_stage_executor_requires_saved_runs_and_reports_steps(self):
        with tempfile.TemporaryDirectory() as td:
            root, _, _ = create_fixture(td)
            calls, events = [], []
            def executor(arguments, *, cancel=None):
                stage = str(arguments[0])
                calls.append(stage)
                if stage == "validate":
                    return {"images": 3}
                model = root / "reconstruction" / stage
                model.mkdir(parents=True)
                return {"engine": "monoscan-native", "run": str(model), "state": "PARTIAL"}
            result = run_pipeline(
                root, mode="arkit-guided", do_refine=True, do_dense=True,
                emit=events.append, execute=executor)
            self.assertEqual(calls, ["validate", "reconstruct", "refine", "dense"])
            self.assertEqual(result["completed"], calls)
            self.assertEqual(len([x for x in events if x["event"] == "complete"]), 4)
            self.assertEqual(events[-1]["event"], "finished")
            self.assertTrue(Path(result["run"]).is_dir())
            self.assertEqual(events[3]["status"], "PARTIAL")
            self.assertEqual(result["state"], "PARTIAL")
            self.assertEqual(result["partial_stages"], ["reconstruct", "refine", "dense"])
            self.assertEqual(events[-1]["status"], "PARTIAL")

    def test_pipeline_propagates_failure_with_no_fake_success(self):
        with tempfile.TemporaryDirectory() as td:
            root, _, _ = create_fixture(td)
            stages = []
            def executor(argv, *, cancel=None):
                if argv[0] == "validate":
                    return {"images": 3}
                raise PipelineError("Synthetic geometric failure")
            with self.assertRaisesRegex(PipelineError, "Synthetic geometric"):
                run_pipeline(root, execute=executor, emit=stages.append)
            self.assertEqual(stages[-1]["event"], "failed")
            self.assertEqual(stages[-1]["stage"], "reconstruct")
            self.assertFalse(any(e["event"] == "finished" for e in stages))

    def test_cancelled_pipeline_never_reports_complete(self):
        with tempfile.TemporaryDirectory() as td:
            root, _, _ = create_fixture(td)
            flag = threading.Event()
            flag.set()
            events = []
            with self.assertRaises(PipelineCancelled):
                run_pipeline(root, cancel=flag, emit=events.append)
            self.assertEqual(events[-1]["event"], "cancelled")

    def test_arkit_focal_conflict_rejected(self):
        with self.assertRaisesRegex(PipelineError, "ARKit-guided"):
            run_pipeline("/not/existing", mode="arkit-guided", focal_px=500)
        with self.assertRaisesRegex(PipelineError, "requires N5"):
            run_pipeline("/not/existing", do_dense=True, do_refine=False)


if __name__ == "__main__":
    unittest.main()
