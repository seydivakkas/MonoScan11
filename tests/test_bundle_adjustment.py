"""Synthetic-only N5 sparse Bundle Adjustment regression tests.

All point clouds, observations and camera poses are generated numerically.
No user photos, image datasets, iPhone build or real measurements are used.
"""
import json
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np

from monoscan_core.bundle_adjustment import BundleAdjustmentError, bundle_adjust


def synthetic_run(folder, mode="photo-only", outlier=False, seed=107):
    rng = np.random.default_rng(seed)
    root = Path(folder)
    raw = root / "native-input"
    raw.mkdir()
    k = np.asarray([[820, 0, 400], [0, 820, 300], [0, 0, 1]], dtype=float)
    centers = np.asarray([[0.0, 0, 0], [0.38, 0, 0], [0.02, 0.36, 0],
                          [-0.25, 0.12, 0.08]], float)
    xyz = np.column_stack([rng.uniform(-0.8, 0.8, 34),
                           rng.uniform(-0.7, 0.7, 34),
                           rng.uniform(2.5, 5.0, 34)])
    cameras = []
    for i, center in enumerate(centers):
        # Original first camera is the gauge anchor and exact.
        c = center.copy() if i == 0 else center + rng.normal(0, 0.025, 3)
        pose = np.eye(4)
        pose[:3, 3] = c
        camera = {"image": f"image_{i:04}.png", "camera_to_world_cv": pose.tolist(),
                  "K": k.tolist()}
        if mode == "arkit-guided":
            camera.update({"pose_source": "arkit_vio", "translation_sigma_m": None,
                           "rotation_sigma_deg": None})
        cameras.append(camera)
    tracks = []
    for p, truth in enumerate(xyz):
        observations = []
        for j, center in enumerate(centers):
            local = truth - center
            uv = (local[:2] / local[2] * 820) + [400, 300]
            uv = uv + rng.normal(0, 0.3, 2)
            if outlier and p == 0 and j == 2:
                uv += [30, -35]
            observations.append({"image": f"image_{j:04}.png",
                                 "keypoint": p, "uv": uv.tolist()})
        tracks.append({"id": p, "xyz": (truth + rng.normal(0, .055, 3)).tolist(),
                       "rgb": [140, 160, 180], "observations": observations})
    (raw / "cameras.json").write_text(json.dumps({"cameras": cameras}))
    (raw / "tracks.json").write_text(json.dumps(tracks))
    (raw / "summary.json").write_text(json.dumps({
        "engine": "monoscan-native", "mode_used": mode,
        "mode_requested": mode, "scale_status": (
            "arbitrary" if mode == "photo-only" else "arkit_nominal_meters_unverified"
        ), "real_world_validated": False, "warnings": [],
    }))
    return raw


class SparseBATests(unittest.TestCase):
    def test_photo_only_jointly_refines_points_and_camera_poses(self):
        with tempfile.TemporaryDirectory() as td:
            source = synthetic_run(td)
            originals = {
                n: (source / n).read_bytes()
                for n in ("cameras.json", "tracks.json", "summary.json")
            }
            target, summary = bundle_adjust(source, max_nfev=90)
            self.assertTrue((target / "sparse.ply").is_file())
            self.assertTrue((target / "optimization.json").is_file())
            self.assertLess(summary["post_ba_median_reprojection_error_px"],
                            summary["pre_ba_median_reprojection_error_px"] * 0.8)
            self.assertEqual(summary["bundle_adjustment"], "applied")
            self.assertFalse(summary["metric_scale_known"])
            self.assertFalse(summary["real_world_validated"])
            self.assertIn("initial_baseline", summary["bundle_adjustment_gauge"])
            old_cameras = json.loads(originals["cameras.json"])["cameras"]
            new_cameras = json.loads((target / "cameras.json").read_text())["cameras"]
            np.testing.assert_allclose(new_cameras[0]["camera_to_world_cv"],
                                       old_cameras[0]["camera_to_world_cv"], atol=1e-9)
            self.assertNotEqual(new_cameras[2]["camera_to_world_cv"],
                                old_cameras[2]["camera_to_world_cv"])
            old_tracks = json.loads(originals["tracks.json"])
            new_tracks = json.loads((target / "tracks.json").read_text())
            self.assertNotEqual(old_tracks[12]["xyz"], new_tracks[12]["xyz"])
            for name, data in originals.items():
                self.assertEqual((source / name).read_bytes(), data)
            self.assertEqual(len(list((source / "refinements").glob("n5-*"))), 1)

    def test_arkit_mode_has_only_uncalibrated_pose_priors(self):
        with tempfile.TemporaryDirectory() as td:
            source = synthetic_run(td, mode="arkit-guided")
            target, report = bundle_adjust(source, prior_weight=6, max_nfev=90)
            self.assertEqual(report["mode_used"], "arkit-guided")
            self.assertFalse(report["bundle_adjustment_pose_covariance_calibrated"])
            self.assertEqual(report["bundle_adjustment_prior_weight_heuristic"], 6)
            self.assertFalse(report["real_world_validated"])
            self.assertLess(report["post_ba_median_reprojection_error_px"],
                            report["pre_ba_median_reprojection_error_px"])
            updated = json.loads((target / "cameras.json").read_text())["cameras"]
            self.assertTrue(all(c["sensor_pose_covariance_known"] is False for c in updated))
            self.assertTrue(all(c["pose_regularization_type"] == "uncalibrated_heuristic"
                                for c in updated))

    def test_outlier_robust_loss_and_refined_run_immutable(self):
        with tempfile.TemporaryDirectory() as td:
            source = synthetic_run(td, outlier=True)
            target, report = bundle_adjust(source, max_nfev=90)
            self.assertTrue(target.is_dir())
            self.assertFalse(report["real_world_validated"])
            self.assertEqual(report["bundle_adjustment_method"], "scipy_trf_sparse_soft_l1")
            second, report2 = bundle_adjust(source, max_nfev=90)
            self.assertNotEqual(target, second)
            self.assertTrue((target / "tracks.json").exists())
            self.assertTrue((second / "tracks.json").exists())

    def test_reject_invalid_provenance_before_any_output(self):
        with tempfile.TemporaryDirectory() as td:
            source = synthetic_run(td, mode="arkit-guided")
            p = source / "cameras.json"
            doc = json.loads(p.read_text())
            del doc["cameras"][1]["pose_source"]
            p.write_text(json.dumps(doc))
            with self.assertRaisesRegex(BundleAdjustmentError, "provenance"):
                bundle_adjust(source)
            self.assertFalse((source / "refinements").exists())

    def test_reject_missing_geometry_and_failed_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(BundleAdjustmentError):
                bundle_adjust(Path(td))
            source = synthetic_run(td)
            doc = json.loads((source / "tracks.json").read_text())
            doc[1]["observations"][1]["keypoint"] = doc[0]["observations"][1]["keypoint"]
            (source / "tracks.json").write_text(json.dumps(doc))
            with self.assertRaisesRegex(BundleAdjustmentError, "Duplicate"):
                bundle_adjust(source)
            self.assertFalse((source / "refinements").exists())

    def test_negative_depth_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            source = synthetic_run(td)
            path = source / "tracks.json"
            doc = json.loads(path.read_text())
            doc[0]["xyz"][2] = -2
            path.write_text(json.dumps(doc))
            with self.assertRaisesRegex(BundleAdjustmentError, "behind-camera"):
                bundle_adjust(source)
            self.assertFalse((source / "refinements").exists())


if __name__ == "__main__":
    unittest.main()
