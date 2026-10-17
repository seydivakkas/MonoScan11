"""N9-A / N9-B split must not produce fake real-device success.

Only procedural PNG/JPEG artifacts are used as fixtures; no web downloads,
real people's photographs, real calibrations, or physical device tests.
"""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from monoscan_core.n9a_acceptance import N9AError, evaluate_proxy_session, inspect_input
from monoscan_core.n9b_acceptance import GATES, N9BError, audit_physical_evidence
from test_n9_iphone_photo_proxy import archive_fixture
from scripts.n9_iphone_photo_proxy import extract_photo_only_session


class N9AProtocolTests(unittest.TestCase):
    def _session(self, root):
        archive = archive_fixture(Path(root) / "synthetic_input.zip")
        session, audit = extract_photo_only_session(
            archive, Path(root) / "adapted", terms_reviewed=True, frame_limit=5)
        return session, audit

    def test_missing_actual_source_is_not_success(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(N9AError, "MISSING_SOURCE_AUDIT"):
                inspect_input(td, "photo-only")

    def test_preflight_verifies_source_bytes_without_running_sfM(self):
        with tempfile.TemporaryDirectory() as td:
            session, audit = self._session(td)
            result = evaluate_proxy_session(
                session, Path(td) / "evidence", mode="photo-only",
                focal_px=650., rights_reviewed=True, dry_run=True,
                execute=lambda *a, **kw: self.fail("No native processing permitted in preflight"))
            self.assertEqual(result["result"], "SOURCE_PREFLIGHT_ONLY")
            self.assertEqual(result["source"]["source_image_count"], 5)
            self.assertEqual(result["n9b_status"], "NOT_TESTED")
            self.assertFalse(result["physical_iphone11_tested"])
            self.assertFalse(result["real_world_validated"])
            self.assertTrue((Path(td) / "evidence" / "n9a_report.json").is_file())

    def test_refuses_fabricated_intrinsics_and_unreviewed_rights(self):
        with tempfile.TemporaryDirectory() as td:
            session, _ = self._session(td)
            with self.assertRaisesRegex(N9AError, "rights"):
                evaluate_proxy_session(session, Path(td) / "evidence",
                                       mode="photo-only", focal_px=500)
            with self.assertRaisesRegex(N9AError, "focal"):
                evaluate_proxy_session(session, Path(td) / "evidence",
                                       mode="photo-only", rights_reviewed=True)
            self.assertFalse((Path(td) / "evidence").exists())

    def test_modified_source_byte_fails_before_running_a_model(self):
        with tempfile.TemporaryDirectory() as td:
            session, _ = self._session(td)
            first = next((session / "images").iterdir())
            first.write_bytes(first.read_bytes() + b"modified")
            with self.assertRaisesRegex(N9AError, "SHA-256 mismatch"):
                inspect_input(session, "photo-only")

    def test_existing_real_proxy_folder_not_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            session, _ = self._session(td)
            evidence = Path(td) / "report"
            evidence.mkdir()
            with self.assertRaisesRegex(N9AError, "replace"):
                evaluate_proxy_session(session, evidence, mode="photo-only",
                                       focal_px=500, rights_reviewed=True, dry_run=True)

    def test_real_native_runner_failure_persisted_as_failure(self):
        with tempfile.TemporaryDirectory() as td:
            session, _ = self._session(td)
            calls = []
            def fake(args, timeout):
                calls.append(args[0])
                if args[0] == "validate":
                    return {"images": 5, "pose_records": 0}
                raise ValueError("deliberately failed synthetic SfM fixture")
            report = evaluate_proxy_session(
                session, Path(td) / "trial", mode="photo-only",
                focal_px=600, rights_reviewed=True, execute=fake)
            self.assertEqual(calls, ["validate", "reconstruct"])
            self.assertEqual(report["classification"], "SYNTHETIC_CONTRACT_TEST")
            self.assertEqual(report["result"], "PROXY_FAILED")
            self.assertEqual(report["failure"]["attempted_stage"], "reconstruct")
            self.assertFalse(report["real_world_validated"])
            self.assertEqual(report["n9b_status"], "NOT_TESTED")
            persistent = json.loads((Path(td) / "trial" / "n9a_report.json").read_text())
            self.assertEqual(persistent["result"], "PROXY_FAILED")

    def test_native_partial_results_never_claim_real_device_success(self):
        with tempfile.TemporaryDirectory() as td:
            session, _ = self._session(td)
            def fake(args, timeout):
                if args[0] == "validate":
                    return {"images": 5, "pose_records": 0}
                folder = session / "reconstruction" / "runs" / "run-test-only"
                folder.mkdir(parents=True, exist_ok=True)
                (folder / "summary.json").write_text(json.dumps({
                    "engine": "monoscan-native", "mode_used": "photo-only",
                    "state": "PARTIAL", "real_world_validated": False
                }))
                for name in ("sparse.ply", "tracks.json", "cameras.json"):
                    (folder / name).write_text("nongeometric test placeholder")
                return {"run": str(folder)}
            result = evaluate_proxy_session(
                session, Path(td) / "trial", mode="photo-only",
                focal_px=650, rights_reviewed=True, execute=fake)
            self.assertEqual(result["classification"], "SYNTHETIC_CONTRACT_TEST")
            self.assertEqual(result["result"], "PROXY_PARTIAL_REVIEW_REQUIRED")
            self.assertEqual(len(result["events"]), 2)
            self.assertIn("sparse.ply", result["events"][1]["artifact_sha256"])
            self.assertFalse(result["real_world_validated"])
            self.assertEqual(result["n9b_status"], "NOT_TESTED")

    def test_native_returned_model_must_be_local_and_unverified(self):
        with tempfile.TemporaryDirectory() as td:
            session, _ = self._session(td)
            def fake(args, timeout):
                if args[0] == "validate":
                    return {"images": 5, "pose_records": 0}
                bad = Path(td) / "foreign_model"
                bad.mkdir(exist_ok=True)
                (bad / "summary.json").write_text(json.dumps({
                    "engine":"monoscan-native", "mode_used":"photo-only",
                    "state":"PARTIAL", "real_world_validated":False}))
                for name in ("sparse.ply", "tracks.json", "cameras.json"):
                    (bad / name).write_text("synthetic test artifact")
                return {"run":str(bad)}
            report = evaluate_proxy_session(
                session, Path(td) / "trial", mode="photo-only",
                focal_px=650, rights_reviewed=True, execute=fake)
            self.assertEqual(report["result"], "PROXY_FAILED")
            self.assertIn("outside", report["failure"]["reason"])


class N9BProtocolTests(unittest.TestCase):
    def test_all_physical_gates_remain_open_without_user_data(self):
        with tempfile.TemporaryDirectory() as td:
            result = audit_physical_evidence(td)
            self.assertEqual(len(result["gates"]), 8)
            self.assertEqual(result["number_not_tested"], 8)
            self.assertEqual(result["number_physical_gates_automatically_passed"], 0)
            self.assertFalse(result["physical_iphone11_accepted"])
            self.assertFalse(result["physical_windows_accepted"])

    def test_hashed_file_is_pending_independent_review_never_pass(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            image = root / "example.bin"
            image.write_bytes(b"synthetic evidence fixture, no actual device")
            idx = root / "index.json"
            idx.write_text(json.dumps({
                "schema_version": 1,
                "records": {"B01": [{"filename": image.name,
                                     "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                                     "note": "synthetic fixture not a device measurement"}]}
            }))
            result = audit_physical_evidence(root, idx)
            self.assertEqual(result["gates"]["B01"]["status"],
                             "EVIDENCE_PRESENT_REVIEW_REQUIRED")
            self.assertEqual(result["number_physical_gates_automatically_passed"], 0)
            self.assertFalse(result["physical_iphone11_accepted"])
            self.assertEqual(result["number_not_tested"], 7)

    def test_corrupted_evidence_cannot_be_promoted_to_success(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "wrong.bin").write_bytes(b"x")
            idx = root / "index.json"
            idx.write_text(json.dumps({
                "schema_version": 1,
                "records": {"B06": [{"filename": "wrong.bin", "sha256": "0"*64}]}
            }))
            result = audit_physical_evidence(root, idx)
            self.assertEqual(result["gates"]["B06"]["status"], "INVALID_EVIDENCE")
            self.assertFalse(result["real_world_validated"])

    def test_rejects_unsafe_external_paths(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            idx = root / "index.json"
            idx.write_text(json.dumps({
                "schema_version": 1,
                "records": {"B01": [{"filename": "../outside.jpg", "sha256": "0"*64}]}
            }))
            result = audit_physical_evidence(root, idx)
            self.assertEqual(result["gates"]["B01"]["status"], "INVALID_EVIDENCE")
            self.assertEqual(len(GATES), 8)


if __name__ == "__main__":
    unittest.main()
