"""N9 public iPhone13 ZIP adapter regression uses synthetic JPEG bytes only."""
import hashlib
import tempfile
import unittest
from pathlib import Path
import zipfile

import cv2
import numpy as np

from scripts.n9_iphone_photo_proxy import (
    IPhoneImageProxyError, extract_photo_only_session,
    download_official_archive, OFFICIAL_ZIP_URL,
)
from monoscan_core.workspace import native_validate


def archive_fixture(path, *, unsafe=False):
    rng = np.random.default_rng(25)
    texture = rng.integers(0, 256, (220, 280, 3), dtype=np.uint8)
    with zipfile.ZipFile(path, "w") as out:
        for n in range(6):
            image = np.roll(texture, n*7, axis=1)
            valid, raw = cv2.imencode(".jpg", image)
            if not valid:
                raise RuntimeError("Cannot create synthetic JPEG")
            out.writestr(f"images/IMG_{n:03d}.JPG", raw.tobytes())
        if unsafe:
            out.writestr("../untrusted.jpg", b"malicious")
    return path


class N9IPhonePhotoProxyTests(unittest.TestCase):
    def test_real_iphone_dataset_adapter_has_no_fake_camera_pose(self):
        with tempfile.TemporaryDirectory() as td:
            file = archive_fixture(Path(td) / "synthetic.zip")
            result, audit = extract_photo_only_session(
                file, Path(td)/"native", terms_reviewed=True, frame_limit=4)
            report = native_validate(result)
            self.assertEqual(report["images"], 4)
            self.assertEqual(report["pose_records"], 0)
            self.assertEqual(len(list((result / "images").glob("*.jpg"))), 4)
            self.assertFalse((result / "session.json").exists())
            self.assertTrue(audit["not_iphone11"])
            self.assertTrue(audit["no_native_arkit_poses"])
            self.assertFalse(audit["real_world_validated"])
            self.assertEqual(audit["source_zip_sha256"],
                             hashlib.sha256(file.read_bytes()).hexdigest())

    def test_dataset_rights_must_be_acknowledged_and_no_download_is_started(self):
        with tempfile.TemporaryDirectory() as td:
            file = archive_fixture(Path(td) / "synthetic.zip")
            with self.assertRaisesRegex(IPhoneImageProxyError, "terms"):
                extract_photo_only_session(file, Path(td)/"unallowed", frame_limit=4)
            self.assertFalse((Path(td)/"unallowed").exists())
            with self.assertRaisesRegex(IPhoneImageProxyError, "terms"):
                download_official_archive(Path(td)/"unallowed-download.zip")
            self.assertIn("data.pix4d.com", OFFICIAL_ZIP_URL)

    def test_zip_traversal_is_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as td:
            file = archive_fixture(Path(td)/"synthetic-unsafe.zip", unsafe=True)
            dest = Path(td)/"blocked"
            with self.assertRaisesRegex(IPhoneImageProxyError, "Unsafe"):
                extract_photo_only_session(file, dest, terms_reviewed=True)
            self.assertFalse(dest.exists())
            self.assertFalse((Path(td)/"untrusted.jpg").exists())

    def test_duplicate_or_existing_output_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            file = archive_fixture(Path(td)/"synthetic.zip")
            result, _ = extract_photo_only_session(
                file, Path(td)/"native", terms_reviewed=True, frame_limit=5)
            with self.assertRaisesRegex(IPhoneImageProxyError, "overwrite"):
                extract_photo_only_session(file, result, terms_reviewed=True)


if __name__ == "__main__":
    unittest.main()
