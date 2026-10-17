"""N9 Apple RAW downloader tests; NO network or actual iPhone images."""
import tempfile
import unittest
from pathlib import Path
import zipfile

from scripts.n9_fetch_arkitscenes import (
    DatasetFetchError, _safe_extract, download_one_sequence, source_urls
)


class PublicResearchDownloadTests(unittest.TestCase):
    def test_explicit_source_and_no_legal_consent_bypass(self):
        urls = source_urls("41069046", "Validation")
        self.assertEqual(set(urls), {"lowres_wide.zip", "lowres_wide_intrinsics.zip",
                                    "lowres_wide.traj"})
        self.assertTrue(all("docs-assets.developer.apple.com" in u for u in urls.values()))
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(DatasetFetchError, "terms"):
                download_one_sequence("41069046", "Validation", Path(td)/"not_downloaded")
            self.assertFalse((Path(td)/"not_downloaded").exists())

    def test_bad_id_and_split_rejected(self):
        with self.assertRaisesRegex(DatasetFetchError, "eight digits"):
            source_urls("iPhone11", "Validation")
        with self.assertRaisesRegex(DatasetFetchError, "split"):
            source_urls("41069046", "../../Training")

    def test_archive_traversal_and_mismatched_video_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/"unsafe.zip"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("../evil.png", b"not-valid")
            with self.assertRaisesRegex(DatasetFetchError, "Unexpected"):
                _safe_extract(path, Path(td)/"dest", "lowres_wide", "41069046")
            self.assertFalse((Path(td)/"evil.png").exists())
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("lowres_wide/00000000_1000.0.png", b"a")
            with self.assertRaisesRegex(DatasetFetchError, "Unexpected"):
                _safe_extract(path, Path(td)/"dest", "lowres_wide", "41069046")


if __name__ == "__main__":
    unittest.main()
