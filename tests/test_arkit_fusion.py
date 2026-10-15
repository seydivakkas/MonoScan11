"""N4 synthetic-only validation; no real photograph or device calibration is implied."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from monoscan_core.arkit_fusion import (
    ARKitFusionError, PosePrior, align_pose_centers,
    load_arkit_priors, pose_baselines,
)
from monoscan_core.arkit_guided import reconstruct_arkit_guided
from monoscan_core.camera import project
from monoscan_core.vision import FrameFeatures


D = np.diag([1, -1, -1, 1])


def make_pose(center):
    pose = np.eye(4)
    pose[:3, 3] = center
    return pose


def synth_session(path, centers, *, tracking=None):
    """Creates real JSON v1, but ONLY synthetic frame matrices and dummy image bytes."""
    path = Path(path)
    folder = path / "images"
    folder.mkdir(parents=True, exist_ok=True)
    k = [[850., 0., 400.], [0., 850., 300.], [0., 0., 1.]]
    records = []
    files = []
    for i, center in enumerate(centers):
        name = f"frame_{i:04d}.png"
        file = folder / name
        file.write_bytes(b"synthetic - not a decodable photograph")
        files.append(file)
        cv_pose = make_pose(center)
        # Camera axes ARKit -Z and CV +Z, same world origin.
        apple_pose = cv_pose @ D
        rec = {
            "file": name, "timestamp": float(i + 1),
            "width": 800, "height": 600,
            "intrinsics": k,
            "cameraToWorld": apple_pose.tolist(),
        }
        if tracking is not None:
            rec["trackingState"] = tracking
        records.append(rec)
    (path / "session.json").write_text(
        json.dumps({"schemaVersion": 1, "frames": records}), encoding="utf-8")
    return files, k


def fake_features(names, centers, k, *, seed=88):
    rng = np.random.default_rng(seed)
    n = 150
    xyz = np.column_stack([
        rng.uniform(-1, 1, n), rng.uniform(-0.8, 0.8, n),
        rng.uniform(3.0, 6.0, n),
    ])
    descriptors = rng.normal(size=(n, 128)).astype(np.float32)
    descriptors /= np.linalg.norm(descriptors, axis=1)[:, None]
    frames = []
    for name, center in zip(names, centers):
        pixels = project(xyz, k, make_pose(center))
        image = np.zeros((600, 800, 3), np.uint8)
        frames.append(FrameFeatures(name, image, np.asarray(k, float), pixels,
                                    descriptors.copy()))
    return frames


class ARKitFusionTests(unittest.TestCase):
    def test_manifest_cv_axes_and_unknown_covariance(self):
        with tempfile.TemporaryDirectory() as td:
            files, _ = synth_session(td, [[0, 0, 0], [0.3, 0, 0], [0, 0.3, 0]])
            priors = load_arkit_priors(Path(td), [p.name for p in files])
            self.assertEqual(len(priors), 3)
            pose = priors[files[0].name]
            np.testing.assert_allclose(pose.cv_camera_to_world, np.eye(4), atol=1e-10)
            self.assertEqual(pose.tracking_state, "unreported")
            self.assertIsNone(pose.translation_sigma_m)
            self.assertIsNone(pose.rotation_sigma_deg)
            self.assertGreater(pose_baselines(priors), 0.3)

    def test_tracking_quality_exclusion_and_missing_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ARKitFusionError, "requires session"):
                load_arkit_priors(Path(td))
            synth_session(td, [[0, 0, 0], [0.3, 0, 0]], tracking="limited")
            with self.assertRaisesRegex(ARKitFusionError, "tracking state"):
                load_arkit_priors(Path(td))

    def test_zero_motion_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            synth_session(td, [[0, 0, 0], [0, 0, 0], [0, 0, 0]])
            with self.assertRaisesRegex(ARKitFusionError, "baseline"):
                pose_baselines(load_arkit_priors(Path(td)))

    def test_nonfinite_and_duplicate_manifest_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            synth_session(td, [[0, 0, 0], [0.3, 0, 0], [0, 0.3, 0]])
            path = Path(td) / "session.json"
            raw = json.loads(path.read_text())
            raw["frames"][1]["file"] = raw["frames"][0]["file"]
            path.write_text(json.dumps(raw))
            with self.assertRaisesRegex(ARKitFusionError, "Duplicate"):
                load_arkit_priors(Path(td))

    def test_sim3_robust_scale_rotation_translation_with_outlier(self):
        rng = np.random.default_rng(3)
        src_centers = rng.uniform(-1, 1, size=(9, 3))
        angle = np.deg2rad(22)
        rot = np.array([[np.cos(angle), -np.sin(angle), 0],
                        [np.sin(angle), np.cos(angle), 0],
                        [0, 0, 1.]])
        scale, shift = 2.4, np.array([0.5, -1.2, 0.1])
        dst = scale * src_centers @ rot.T + shift
        dst[8] += [1.8, 2, 3.5]  # deliberately corrupted pose
        priors = {}
        sources = {}
        for i in range(9):
            name = f"im{i}"
            priors[name] = PosePrior(name, float(i), make_pose(dst[i]), np.eye(3),
                                     "unreported")
            sources[name] = make_pose(src_centers[i])
        report = align_pose_centers(sources, priors)
        self.assertEqual(report["inlier_count"], 8)
        self.assertIn("im8", report["outlier_images"])
        self.assertAlmostEqual(report["scale"], scale, places=5)
        np.testing.assert_allclose(report["rotation"], rot, atol=1e-5)
        np.testing.assert_allclose(report["translation"], shift, atol=1e-5)
        self.assertFalse(report["sensor_covariance_known"])
        self.assertFalse(report["real_world_validated"])

    def test_sim3_collinear_rejected(self):
        source = {}
        priors = {}
        for i in range(7):
            n = f"im{i}"
            pt = [0.3 * i, 0, 0]
            source[n] = make_pose(pt)
            priors[n] = PosePrior(n, float(i), make_pose(pt), np.eye(3), "normal")
        with self.assertRaisesRegex(ARKitFusionError, "consensus|Degenerate"):
            align_pose_centers(source, priors)


class ARKitGuidedTests(unittest.TestCase):
    def test_synthetic_3_camera_guided_sparse_run(self):
        centers = [[0, 0, 0], [0.35, 0, 0], [-0.15, 0.09, 0]]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            files, k = synth_session(root, centers)
            frames = fake_features([p.name for p in files], centers, k)
            with mock.patch("monoscan_core.arkit_guided.load_frames",
                            return_value=(files, frames, [], True)):
                run, report = reconstruct_arkit_guided(root)
            self.assertEqual(report["mode_used"], "arkit-guided")
            self.assertGreaterEqual(report["point_count"], 24)
            self.assertGreaterEqual(report["registered_images"], 2)
            self.assertLess(report["median_reprojection_error_px"], 0.1)
            self.assertFalse(report["metric_scale_known"])
            self.assertFalse(report["real_world_validated"])
            self.assertIsNone(report["translation_sigma_m"])
            self.assertIn("frame_0000.png", report["tracking_state_unreported_images"])
            self.assertEqual(len(list((root / "reconstruction" / "runs").iterdir())), 1)
            cameras = json.loads((run / "cameras.json").read_text())["cameras"]
            self.assertTrue(all(x["pose_source"] == "arkit_vio" for x in cameras))
            tracks = json.loads((run / "tracks.json").read_text())
            self.assertTrue(all(len(x["observations"]) >= 2 for x in tracks))
            self.assertTrue((run / "sparse.ply").exists())

    def test_missing_session_does_not_create_false_success(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ARKitFusionError):
                reconstruct_arkit_guided(Path(td))
            self.assertFalse((Path(td) / "reconstruction").exists())

    def test_zero_arkit_baseline_fails_closed_before_images(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            synth_session(root, [[0, 0, 0]] * 3)
            with mock.patch("monoscan_core.arkit_guided.load_frames",
                            return_value=([], [], [], True)):
                with self.assertRaisesRegex(ARKitFusionError, "mismatch|baseline"):
                    reconstruct_arkit_guided(root)
            self.assertFalse((root / "reconstruction").exists())


if __name__ == "__main__":
    unittest.main()
