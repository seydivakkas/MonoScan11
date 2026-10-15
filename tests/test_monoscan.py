import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from geometry import GeometryError, project, synthetic_demo, triangulate, world_ray
from monoscan import SessionError, image_dimensions, main, validate
from helpers import png_bytes


K = [[800, 0, 320], [0, 800, 240], [0, 0, 1]]
POSE = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "images").mkdir()
        for i in range(3):
            (self.root / "images" / f"frame_{i:04d}.png").write_bytes(png_bytes())

    def tearDown(self):
        self.tmp.cleanup()

    def add_manifest(self):
        names = sorted(p.name for p in (self.root / "images").iterdir())
        frames = [
            {"file": name, "timestamp": float(i + 1), "width": 16, "height": 12,
             "intrinsics": copy.deepcopy(K), "cameraToWorld": copy.deepcopy(POSE)} for i, name in enumerate(names)
        ]
        self.save_frames(frames)
        return frames

    def save_frames(self, frames):
        (self.root / "session.json").write_text(json.dumps({"schemaVersion": 1, "frames": frames}), encoding="utf-8")

    def test_photo_only_validated(self):
        report = validate(self.root)
        self.assertEqual(report["images"], 3)
        self.assertEqual(report["pose_records"], 0)
        self.assertEqual(report["image_formats"], {".png": 3})
        self.assertFalse(report["arkit_poses_used_by_native"])

    def test_valid_manifest(self):
        self.add_manifest()
        self.assertEqual(validate(self.root)["pose_records"], 3)

    def test_image_size_mismatch(self):
        frames = self.add_manifest()
        frames[0]["width"] = 20
        self.save_frames(frames)
        with self.assertRaisesRegex(SessionError, "boyutları uyuşmuyor"):
            validate(self.root)

    def test_bad_camera_intrinsics(self):
        frames = self.add_manifest()
        frames[1]["intrinsics"] = [[0, 0, 0], [0, 800, 240], [0, 0, 1]]
        self.save_frames(frames)
        with self.assertRaisesRegex(SessionError, "odak uzaklığı"):
            validate(self.root)

    def test_nonfinite_matrix(self):
        frames = self.add_manifest()
        frames[0]["intrinsics"][0][0] = float("nan")
        self.save_frames(frames)
        with self.assertRaises(SessionError):
            validate(self.root)

    def test_bad_rotation_determinant(self):
        frames = self.add_manifest()
        frames[0]["cameraToWorld"] = [[-1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
        self.save_frames(frames)
        with self.assertRaisesRegex(SessionError, "yönü"):
            validate(self.root)

    def test_non_increasing_timestamps(self):
        frames = self.add_manifest()
        frames[2]["timestamp"] = frames[1]["timestamp"]
        self.save_frames(frames)
        with self.assertRaisesRegex(SessionError, "zaman damgaları"):
            validate(self.root)

    def test_path_traversal(self):
        frames = self.add_manifest()
        frames[0]["file"] = "../frame_0000.png"
        self.save_frames(frames)
        with self.assertRaisesRegex(SessionError, "güvenli değil"):
            validate(self.root)

    def test_duplicate_frames(self):
        frames = self.add_manifest()
        frames[1]["file"] = frames[0]["file"]
        self.save_frames(frames)
        with self.assertRaisesRegex(SessionError, "tekrar eden"):
            validate(self.root)

    def test_missing_image(self):
        (self.root / "images" / "frame_0001.png").unlink()
        with self.assertRaisesRegex(SessionError, "en az 3"):
            validate(self.root)

    def test_fake_image_is_rejected(self):
        (self.root / "images" / "frame_0000.png").write_bytes(b"fake")
        with self.assertRaisesRegex(SessionError, "başlığı"):
            validate(self.root)

    def test_heic_only_error(self):
        for p in (self.root / "images").iterdir():
            p.unlink()
        (self.root / "images" / "IMG_0001.HEIC").write_bytes(b"heic")
        with self.assertRaisesRegex(SessionError, "HEIC"):
            validate(self.root)

    def test_windows_cp1252_console_can_print_json(self):
        import contextlib
        import io
        output = io.BytesIO()
        # Simulates default Windows console/redirect codepage without Turkish glyphs.
        console = io.TextIOWrapper(output, encoding="cp1252", write_through=True)
        with contextlib.redirect_stdout(console):
            self.assertEqual(main(["validate", str(self.root)]), 0)
        payload = json.loads(output.getvalue().decode("cp1252"))
        self.assertEqual(payload["images"], 3)

    def test_arkit_guided_dry_run_requires_session(self):
        self.assertEqual(main(["reconstruct", str(self.root), "--mode",
                               "arkit-guided", "--dry-run"]), 1)
        self.assertFalse((self.root / "reconstruction").exists())

    def test_png_header(self):
        self.assertEqual(image_dimensions(self.root / "images" / "frame_0000.png"), (16, 12))

    def test_cli_validate_and_demo(self):
        self.assertEqual(main(["validate", str(self.root)]), 0)
        out = self.root / "out"
        self.assertEqual(main(["demo", str(out)]), 0)
        self.assertEqual(main(["demo", str(out)]), 1)  # fail-closed on existing files


class GeometryTests(unittest.TestCase):
    def test_two_views_recover_depth(self):
        p2 = [[1, 0, 0, 0.2], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
        pt = (0.5, -0.3, 3.0)
        uv1 = project(pt, K, POSE)
        uv2 = project(pt, K, p2)
        result = triangulate(uv1, uv2, K, K, POSE, p2)
        for recovered, expected in zip(result["xyz"], pt):
            self.assertAlmostEqual(recovered, expected, places=8)
        self.assertAlmostEqual(result["ray_gap_m"], 0, places=8)

    def test_zero_baseline_rejected(self):
        with self.assertRaisesRegex(GeometryError, "baseline"):
            triangulate((320, 240), (319, 240), K, K, POSE, POSE)

    def test_near_parallel_rejected(self):
        p2 = [[1, 0, 0, 0.0001], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
        with self.assertRaisesRegex(GeometryError, "paralel"):
            triangulate((320, 240), (319.99, 240), K, K, POSE, p2)

    def test_behind_camera_rejected(self):
        p2 = [[1, 0, 0, 0.25], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
        with self.assertRaisesRegex(GeometryError, "arkasında"):
            triangulate((320, 240), (340, 240), K, K, POSE, p2)

    def test_invalid_focus_rejected(self):
        bad = [[0, 0, 320], [0, 800, 240], [0, 0, 1]]
        with self.assertRaises(GeometryError):
            world_ray((320, 240), bad, POSE)

    def test_synthetic_demo_ground_truth_labelled(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = synthetic_demo(Path(tmp))
            self.assertEqual(data["point_count"], 117)
            self.assertFalse(data["real_world_validated"])
            self.assertLess(data["rmse_m"], 1e-8)
            self.assertTrue((Path(tmp) / "synthetic_points.ply").is_file())


if __name__ == "__main__":
    unittest.main()
