"""N9 reference maths: synthetic test geometry, NOT a measured real device."""
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from monoscan_core.n9_reference import (
    ReferenceEvidenceError, evaluate_independent_reference,
)


def fixture(folder, *, mode="arkit-guided"):
    root = Path(folder)
    model = root / "unverified-native-run"
    model.mkdir()
    np_rng = np.random.default_rng(69)
    truth = np_rng.normal(0, 1, (12, 3)) * [1, 0.8, 0.9] + [0, 0, 4]
    # simulated reference global pose is rigid transform, scale=1.
    angle = 0.3
    r = np.asarray([[np.cos(angle), -np.sin(angle), 0],
                    [np.sin(angle), np.cos(angle), 0], [0, 0, 1]])
    translation = np.asarray([0.4, -0.6, 0.22])
    reference = truth @ r.T + translation
    measured = reference.copy()
    measured[8:] += np.asarray([[0.01, -.02, .02], [-.02, 0, .0],
                                 [0.015, .01, -.01], [-.02, -.01, .03]])
    tracks = [{"id": i, "xyz": xyz.tolist()} for i, xyz in enumerate(truth)]
    (model / "tracks.json").write_text(json.dumps(tracks))
    (model / "summary.json").write_text(json.dumps({
        "engine": "monoscan-native", "mode_used": mode,
        "real_world_validated": False,
    }))
    spec = {
        "schema_version": 1, "unit": "meter",
        "reference_provenance": "synthetic numeric mock of independent survey only",
        "reference_file_sha256": "a" * 64,
        "calibration": [
            {"track_id": i, "reference_xyz_m": measured[i].tolist()}
            for i in range(8)
        ],
        "holdout": [
            {"track_id": i, "reference_xyz_m": measured[i].tolist()}
            for i in range(8, 12)
        ],
    }
    manifest = root / "reference_synthetic_only.json"
    manifest.write_text(json.dumps(spec))
    return model, manifest, spec


class N9ReferenceTests(unittest.TestCase):
    def test_holdout_separate_from_calibration_with_fixed_scale(self):
        with tempfile.TemporaryDirectory() as td:
            model, manifest, _ = fixture(td)
            target = Path(td) / "evidence.json"
            result = evaluate_independent_reference(model, manifest, output=target)
            self.assertEqual(result["calibration_correspondences"], 8)
            self.assertEqual(result["holdout_correspondences"], 4)
            self.assertLess(result["holdout_rmse_m"], 0.04)
            self.assertGreater(result["holdout_rmse_m"], 0.01)
            self.assertFalse(result["similarity_scale_fitted"])
            self.assertEqual(result["rigid_scale_fixed"], 1.0)
            self.assertFalse(result["reference_independently_verified"])
            self.assertFalse(result["physical_iphone11_tested"])
            self.assertFalse(result["real_world_validated"])
            self.assertTrue(target.is_file())

    def test_duplicate_holdout_track_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            model, manifest, spec = fixture(td)
            spec["holdout"][0]["track_id"] = 0
            manifest.write_text(json.dumps(spec))
            with self.assertRaisesRegex(ReferenceEvidenceError, "Duplicate"):
                evaluate_independent_reference(model, manifest)

    def test_unverified_photo_only_scale_is_not_presented_as_metric(self):
        with tempfile.TemporaryDirectory() as td:
            model, manifest, spec = fixture(td, mode="photo-only")
            with self.assertRaisesRegex(ReferenceEvidenceError, "ARKit"):
                evaluate_independent_reference(model, manifest)

    def test_missing_provenance_and_bad_reference_fail(self):
        with tempfile.TemporaryDirectory() as td:
            model, manifest, spec = fixture(td)
            spec["reference_file_sha256"] = "not-real-sha"
            manifest.write_text(json.dumps(spec))
            with self.assertRaisesRegex(ReferenceEvidenceError, "provenance"):
                evaluate_independent_reference(model, manifest)
            spec["reference_file_sha256"] = "b" * 64
            spec["holdout"][0]["reference_xyz_m"] = [float("nan"), 0, 1]
            manifest.write_text(json.dumps(spec))
            with self.assertRaisesRegex(ReferenceEvidenceError, "finite"):
                evaluate_independent_reference(model, manifest)


if __name__ == "__main__":
    unittest.main()
