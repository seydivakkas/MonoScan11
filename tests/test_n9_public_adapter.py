"""N9 source adapter tests use synthetic arrays ONLY, no downloaded assets."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from monoscan_core.n9_public_adapter import (
    RealDatasetError, parse_arkitscenes_traj, parse_pincam,
    prepare_arkitscenes_session,
)
from monoscan_core.arkit_fusion import load_arkit_priors
from monoscan_core.camera import camera_to_world
from monoscan_core.workspace import native_validate


def make_official_format_fixture(folder, *, video_id="41069046", frames=12,
                                 bad_calibration=False, tiny_motion=False):
    root = Path(folder) / video_id
    (root / "lowres_wide").mkdir(parents=True)
    (root / "lowres_wide_intrinsics").mkdir()
    pose_rows = []
    rng = np.random.default_rng(7011)
    texture = rng.integers(0, 256, (192, 256, 3), dtype=np.uint8)
    for i in range(frames):
        timestamp = 1000.0 + i * 0.1
        # Official .traj is world-to-camera: t is the NEGATIVE of a CV center.
        center = 0.01 * i if tiny_motion else 0.075 * i
        pose_rows.append(f"{timestamp:.5f} 0 0 0 {-center:.6f} 0 0")
        filename = f"{video_id}_{timestamp:.5f}"
        target = root / "lowres_wide" / (filename + ".png")
        shifted = np.roll(texture, i * 4, axis=1)
        self_ok = cv2.imwrite(str(target), shifted)
        if not self_ok:
            raise RuntimeError("Cannot write procedural PNG fixture")
        dims = ("255 192" if bad_calibration else "256 192")
        (root / "lowres_wide_intrinsics" / (filename + ".pincam")).write_text(
            dims + " 200 200 128 96", encoding="utf-8"
        )
    (root / "lowres_wide.traj").write_text("\n".join(pose_rows)+"\n", encoding="utf-8")
    return root


class N9PublicAdapterTests(unittest.TestCase):
    def test_official_traj_world_to_camera_inversion(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_official_format_fixture(td)
            poses = parse_arkitscenes_traj(root / "lowres_wide.traj")
            self.assertEqual(len(poses), 12)
            np.testing.assert_allclose(poses[8][1][:3, 3], [0.6, 0., 0.], atol=1e-8)
            np.testing.assert_allclose(poses[8][1][:3, :3], np.eye(3))

    def test_pincam_resolution_and_intrinsics(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_official_format_fixture(td)
            kfile = next((root / "lowres_wide_intrinsics").glob("*.pincam"))
            width, height, k = parse_pincam(kfile)
            self.assertEqual((width, height), (256, 192))
            np.testing.assert_allclose(k, [[200, 0, 128], [0, 200, 96], [0, 0, 1]])

    def test_real_format_adaptation_preserves_rgb_bytes_and_unknown_tracking(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_official_format_fixture(td)
            dest = Path(td) / "n9-public-dataset-adapted"
            _, audit = prepare_arkitscenes_session(
                root, dest, video_id="41069046", max_frames=5)
            self.assertTrue(dest.joinpath("session.json").is_file())
            report = native_validate(dest)
            self.assertEqual(report["images"], 5)
            self.assertEqual(report["pose_records"], 5)
            self.assertFalse(audit["is_iphone_11_capture"])
            self.assertFalse(audit["real_world_validated"])
            self.assertFalse(audit["physical_device_accepted"])
            manifest = json.loads(dest.joinpath("session.json").read_text())
            priors = load_arkit_priors(dest)
            for rec in manifest["frames"]:
                self.assertEqual(rec["trackingState"], "unreported")
                self.assertEqual(priors[rec["file"]].tracking_state, "unreported")
                expected = hashlib.sha256((root / "lowres_wide" / rec["file"]).read_bytes()).hexdigest()
                got = hashlib.sha256((dest / "images" / rec["file"]).read_bytes()).hexdigest()
                self.assertEqual(expected, got)
                camera_to_world(priors[rec["file"]].cv_camera_to_world)
            self.assertEqual(len(audit["images"]), 5)
            self.assertTrue(dest.joinpath("n9_source_audit.json").is_file())
            with self.assertRaisesRegex(RealDatasetError, "overwrite"):
                prepare_arkitscenes_session(root, dest, video_id="41069046")

    def test_intrinsic_resolution_mismatch_has_no_partial_publish(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_official_format_fixture(td, bad_calibration=True)
            dest = Path(td) / "failed"
            with self.assertRaisesRegex(RealDatasetError, "dimensions"):
                prepare_arkitscenes_session(root, dest, video_id="41069046")
            self.assertFalse(dest.exists())

    def test_nonmonotonic_pose_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_official_format_fixture(td)
            traj = root / "lowres_wide.traj"
            data = traj.read_text().splitlines()
            data[3] = data[2]
            traj.write_text("\n".join(data))
            with self.assertRaisesRegex(RealDatasetError, "Nonmonotonic"):
                parse_arkitscenes_traj(traj)

    def test_timestamp_gap_must_not_be_guessed(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_official_format_fixture(td)
            traj = root / "lowres_wide.traj"
            data = []
            for row in traj.read_text().splitlines():
                fields = row.split()
                fields[0] = f"{float(fields[0])+0.05:.5f}"
                data.append(" ".join(fields))
            traj.write_text("\n".join(data))
            dest = Path(td) / "no_matches"
            with self.assertRaisesRegex(RealDatasetError, "Fewer than three"):
                prepare_arkitscenes_session(root, dest, video_id="41069046")
            self.assertFalse(dest.exists())

    def test_wrong_device_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_official_format_fixture(td)
            dest = Path(td) / "wrong_device"
            with self.assertRaisesRegex(RealDatasetError, "eight-digit"):
                prepare_arkitscenes_session(root, dest, video_id="iPhone11")
            self.assertFalse(dest.exists())


if __name__ == "__main__":
    unittest.main()
