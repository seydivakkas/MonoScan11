"""Deterministic N2-N3 checks; synthetic imagery is NOT real scan acceptance."""
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from monoscan_core.reconstruction import ReconstructionError, _seed, reconstruct
from monoscan_core.vision import FrameFeatures, VisionError, extract, match


class NativeReconstructionTests(unittest.TestCase):
    def test_textured_image_matches_translated_image(self):
        rng = np.random.default_rng(44)
        textured = rng.integers(0, 256, (400, 520, 3), dtype=np.uint8)
        shifted = np.zeros_like(textured)
        shifted[:, 14:] = textured[:, :-14]
        k = np.array([[580, 0, 260], [0, 580, 200], [0, 0, 1]], float)
        a = extract("a", textured, k)
        b = extract("b", shifted, k)
        pairs = match(a, b)
        self.assertGreater(len(pairs), 35)
        self.assertEqual(len(pairs), len(np.unique(pairs[:, 0])))
        self.assertEqual(len(pairs), len(np.unique(pairs[:, 1])))

    def test_seed_recovers_geometric_support(self):
        rng = np.random.default_rng(112)
        n = 160
        xyz = np.column_stack([rng.uniform(-1, 1, n), rng.uniform(-0.8, 0.8, n),
                               rng.uniform(3, 6, n)])
        k = np.array([[850., 0., 400.], [0., 850., 300.], [0., 0., 1.]])
        shift = np.array([0.30, 0, 0])
        p = (xyz[:, :2] / xyz[:, 2:] * 850) + [400, 300]
        qcam = xyz - shift
        q = (qcam[:, :2] / qcam[:, 2:] * 850) + [400, 300]
        descriptor = rng.normal(size=(n, 128)).astype(np.float32)
        descriptor /= np.linalg.norm(descriptor, axis=1, keepdims=True)
        blank = np.zeros((600, 800, 3), np.uint8)
        a = FrameFeatures("a", blank, k, p, descriptor)
        b = FrameFeatures("b", blank, k, q, descriptor.copy())
        initial = _seed(a, b)
        self.assertIsNotNone(initial)
        self.assertGreaterEqual(len(initial[2]), 30)
        self.assertTrue(np.isfinite(initial[2]).all())

    def test_blank_images_do_not_create_fake_cloud(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "images"
            folder.mkdir()
            for i in range(3):
                cv2.imwrite(str(folder / f"img_{i}.png"),
                            np.zeros((100, 140, 3), np.uint8))
            with self.assertRaisesRegex(ReconstructionError, "focal"):
                reconstruct(root)
            with self.assertRaisesRegex(ReconstructionError, "initial pair"):
                reconstruct(root, focal_px=500)
            self.assertFalse((root / "reconstruction").exists())


    def test_synthetic_three_view_pipeline_writes_recoverable_artifacts(self):
        from unittest import mock
        import json
        rng = np.random.default_rng(61)
        n = 180
        xyz = np.column_stack([rng.uniform(-1.2, 1.2, n),
                               rng.uniform(-0.8, 0.8, n),
                               rng.uniform(3, 6, n)])
        k = np.array([[850., 0., 400.], [0., 850., 300.], [0., 0., 1.]])
        des = rng.normal(size=(n, 128)).astype(np.float32)
        des /= np.linalg.norm(des, axis=1, keepdims=True)
        centers = ([0., 0., 0.], [0.35, 0, 0], [-0.2, 0.06, 0])
        frames = []
        image = np.zeros((600, 800, 3), np.uint8)
        for index, center in enumerate(centers):
            local = xyz - center
            px = (local[:, :2] / local[:, 2:] * 850) + [400, 300]
            frames.append(FrameFeatures(f"im{index}.png", image, k, px, des.copy()))
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            images = root / "images"
            images.mkdir()
            files = []
            for i in range(3):
                file = images / f"im{i}.png"
                file.write_bytes(b"synthetic fixture, not valid photograph")
                files.append(file)
            with mock.patch("monoscan_core.reconstruction.load_frames",
                            return_value=(files, frames, [], False)):
                run, report = reconstruct(root, focal_px=850)
            self.assertGreaterEqual(report["registered_images"], 2)
            self.assertGreaterEqual(report["point_count"], 24)
            self.assertEqual(report["engine"], "monoscan-native")
            self.assertFalse(report["metric_scale_known"])
            self.assertFalse(report["real_world_validated"])
            for output in ["sparse.ply", "tracks.json", "cameras.json", "summary.json"]:
                self.assertTrue((run / output).is_file(), output)
            self.assertEqual(json.loads((run / "summary.json").read_text())["engine"],
                             "monoscan-native")

    def test_no_colmap_contract(self):
        from monoscan_core import reconstruction
        self.assertFalse(hasattr(reconstruction, "commands_for"))


if __name__ == "__main__":
    unittest.main()
