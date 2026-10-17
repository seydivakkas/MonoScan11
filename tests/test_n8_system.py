"""N8 synthetic-only integration gates: packaging, recovery, subprocess, UI audit.

The expensive real N4->N6 procedural pipeline runs in a separate CI job
(scripts/n8_synthetic_acceptance.py) to keep fast matrix regressions bounded.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from monoscan_core.workspace import ProjectCatalog, WorkspaceError
from monoscan_core import workspace as ws, workflow as workflow
from monoscan_core.workflow import PipelineCancelled, PipelineError, run_command
from scripts.package_n8_windows import build_source_bundle, verify_bundle, PackageError


class N8PackageTests(unittest.TestCase):
    def test_reproducible_source_only_archive_and_integrity(self):
        with tempfile.TemporaryDirectory() as td:
            path1 = Path(td) / "source_a.zip"
            path2 = Path(td) / "source_b.zip"
            result = build_source_bundle(path1)
            build_source_bundle(path2)
            self.assertEqual(path1.read_bytes(), path2.read_bytes())
            manifest = verify_bundle(path1)
            self.assertTrue(manifest["not_standalone"])
            self.assertFalse(manifest["contains_user_data"])
            self.assertFalse(manifest["real_world_validated"])
            self.assertIn("monoscan_core/desktop.py", manifest["sha256"])
            self.assertIn("scripts/n8_synthetic_acceptance.py", manifest["sha256"])
            self.assertFalse(any("/images/" in name or "/reconstruction/" in name
                                 for name in manifest["sha256"]))
            self.assertFalse(result["standalone_windows_executable"])

    def test_source_archive_refuses_unsafe_overwrite_or_tampering(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "source.zip"
            build_source_bundle(out)
            with self.assertRaisesRegex(PackageError, "overwrite"):
                build_source_bundle(out)
            content = out.read_bytes()
            # Damage archive payload; verifier cannot quietly certify it.
            out.write_bytes(content[:200] + b"X" + content[201:])
            with self.assertRaises((PackageError, ValueError)):
                verify_bundle(out)


class N8RecoveryTests(unittest.TestCase):
    def test_unfinished_import_and_unindexed_sources_are_reported_not_deleted(self):
        with tempfile.TemporaryDirectory() as td:
            catalog = ProjectCatalog(Path(td) / "workspace")
            temp_import = catalog.root / "sessions" / ".import-crashed"
            temp_import.mkdir(parents=True)
            (temp_import / "important-user-bytes.dat").write_bytes(b"must not delete")
            orphan = catalog.root / "sessions" / "unindexed-original"
            orphan.mkdir()
            (orphan / "session.json").write_text("{}")
            index_tmp = catalog.root / ".index-crashed.json"
            index_tmp.write_text("[ not done")
            findings = catalog.recovery_findings()
            self.assertEqual({x["kind"] for x in findings},
                             {"interrupted_import", "unindexed_session", "uncommitted_catalog_temp"})
            self.assertEqual((temp_import / "important-user-bytes.dat").read_bytes(),
                             b"must not delete")
            self.assertTrue(index_tmp.exists())
            self.assertTrue(orphan.joinpath("session.json").exists())
            self.assertEqual(catalog.projects(), [])

    def test_interrupted_import_rolls_back_staging_without_publishing(self):
        from test_desktop_workstation import create_fixture, build_zip
        with tempfile.TemporaryDirectory() as td:
            source, manifest, images = create_fixture(td)
            archive = Path(td) / "synthetic.zip"
            build_zip(archive, manifest, images)
            catalog = ProjectCatalog(Path(td) / "workspace")
            with mock.patch.object(ws, "native_validate", side_effect=WorkspaceError("synthetic interruption")):
                with self.assertRaisesRegex(WorkspaceError, "interruption"):
                    catalog.import_zip(archive)
            self.assertEqual(catalog.projects(), [])
            self.assertFalse(list((catalog.root / "sessions").iterdir()))
            self.assertTrue(archive.exists())
            self.assertTrue(source.joinpath("session.json").is_file())


class N8ProcessTests(unittest.TestCase):
    def test_parent_drains_large_child_stderr_without_hanging(self):
        native_popen = subprocess.Popen
        def fake(_argv, **kwargs):
            script = ("import sys;"
                      "sys.stderr.write('warn'*100000);sys.stderr.flush();"
                      "print('{\"images\":3}')")
            return native_popen([sys.executable, "-c", script], **kwargs)
        with mock.patch.object(workflow.subprocess, "Popen", side_effect=fake):
            result = run_command(["validate", "unused"], timeout=8)
        self.assertEqual(result["images"], 3)

    def test_cancelled_child_is_reaped_with_no_fake_success(self):
        native_popen = subprocess.Popen
        def fake(_argv, **kwargs):
            return native_popen([sys.executable, "-c",
                                 "import time;time.sleep(6)"], **kwargs)
        cancel = threading.Event()
        def set_cancel():
            time.sleep(0.25)
            cancel.set()
        thread = threading.Thread(target=set_cancel)
        thread.start()
        try:
            with mock.patch.object(workflow.subprocess, "Popen", side_effect=fake):
                with self.assertRaises(PipelineCancelled):
                    run_command(["validate", "unused"], cancel=cancel, timeout=5)
        finally:
            thread.join(timeout=2)

    def test_zero_time_budget_kills_stalled_process(self):
        native_popen = subprocess.Popen
        def fake(_argv, **kwargs):
            return native_popen([sys.executable, "-c",
                                 "import time;time.sleep(6)"], **kwargs)
        with mock.patch.object(workflow.subprocess, "Popen", side_effect=fake):
            with self.assertRaisesRegex(PipelineError, "time limit"):
                run_command(["validate", "unused"], timeout=0.2)


class N8AccessibilityTests(unittest.TestCase):
    @staticmethod
    def ratio(a, b):
        def luminance(color):
            nums = [int(color[i:i+2], 16)/255 for i in (1, 3, 5)]
            adjusted = [v/12.92 if v <= 0.04045 else ((v+0.055)/1.055)**2.4
                        for v in nums]
            return sum(q*w for q, w in zip(adjusted, (0.2126, 0.7152, 0.0722)))
        x, y = luminance(a), luminance(b)
        return (max(x,y)+0.05)/(min(x,y)+0.05)

    def test_workstation_text_palette_meets_wcag_aa_contrast(self):
        from monoscan_core.desktop import BG, PANEL, INK, MUTED, ACCENT
        for fg, bg in [(INK, PANEL), (MUTED, PANEL), (ACCENT, PANEL),
                       (INK, BG), (MUTED, BG)]:
            self.assertGreaterEqual(self.ratio(fg, bg), 4.5)

    @unittest.skipUnless(sys.platform == "win32", "Tk smoke test on Windows only")
    def test_keyboard_bindings_focus_and_no_fake_content(self):
        from monoscan_core.desktop import MonoScanDesktop
        with tempfile.TemporaryDirectory() as td:
            win = MonoScanDesktop(root=Path(td))
            try:
                win.withdraw()
                win.update_idletasks()
                for binding in ("<Control-o>", "<Control-l>", "<Control-r>",
                                "<F5>", "<Escape>", "<F1>", "<Control-plus>"):
                    self.assertTrue(win.bind_all(binding), binding)
                self.assertEqual(str(win.canvas.cget("takefocus")), "1")
                self.assertIsNone(win.preview_model)
                yaw = win.yaw
                win._key_rotate(0.10, 0)
                self.assertAlmostEqual(win.yaw, yaw+0.10)
            finally:
                win.destroy()


if __name__ == "__main__":
    unittest.main()
