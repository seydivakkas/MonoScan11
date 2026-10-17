"""N9-B immutable physical acceptance evidence ledger — NO automated PASS.

A real Windows computer, actual iPhone 11, real iOS/Xcode logs and
independent measuring instruments must be witnessed by a reviewer.
This utility only inventories actual submitted evidence and SHA-256.
Presence of a file is NOT proof of accuracy, compatibility, or consent.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


class N9BError(ValueError):
    pass


GATES = {
    "B01": "Physical iPhone 11 model, iOS version and device inventory",
    "B02": "Signed Xcode build/install and actual iPhone11 launch log",
    "B03": "iPhone11 wide RGB lens, distortion and intrinsics calibration",
    "B04": "iPhone11 original multiview RGB+ARKit poses with timestamp and SHA",
    "B05": "Independent dimensions/point survey and blind holdout residuals",
    "B06": "Physical Windows 10/11 install, long-run memory/performance/crash",
    "B07": "Screen reader NVDA/UIA, DPI, keyboard and human accessibility",
    "B08": "Offline wheelhouse/installer, dependency licenses and distribution",
}


def _sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()


def audit_physical_evidence(root, manifest=None):
    """Return pending/review-required statuses without claiming physical passes.

    Optional manifest format:
      {"schema_version": 1,
       "records": {
         "B01": [{"filename": "iphone11-device-photo.jpg",
                  "sha256": "...", "note": "..."}], ...
       }}
    Evidence files must live directly in root (never external arbitrary path).
    Reviewers still must actually check capture origin, instruments and records.
    """
    root = Path(root).expanduser().resolve()
    if manifest is None:
        declared = {}
    else:
        source = Path(manifest).expanduser().resolve()
        try:
            if source.stat().st_size > 256000:
                raise N9BError("Physical evidence manifest too large")
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            if isinstance(exc, N9BError):
                raise
            raise N9BError("Cannot load N9-B physical evidence index") from exc
        if (not isinstance(payload, dict) or payload.get("schema_version") != 1
                or not isinstance(payload.get("records"), dict)
                or any(k not in GATES for k in payload["records"])):
            raise N9BError("Invalid N9-B evidence contract")
        declared = payload["records"]
    per_gate = {}
    for key, description in GATES.items():
        entries = declared.get(key, [])
        if not isinstance(entries, list) or len(entries) > 30:
            raise N9BError("Invalid gate evidence entries: " + key)
        if not entries:
            per_gate[key] = {"requirement": description,
                             "status": "NOT_TESTED", "files": []}
            continue
        verified, problems = [], []
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("filename"), str):
                problems.append("Malformed evidence entry")
                continue
            name = entry["filename"]
            if (not name or name in (".", "..") or "/" in name
                    or "\\" in name or Path(name).name != name):
                problems.append("Unsafe evidence filename")
                continue
            file = root / name
            if (not file.is_file() or file.is_symlink()
                    or not isinstance(entry.get("sha256"), str)
                    or len(entry["sha256"]) != 64):
                problems.append("Missing file or SHA proof: " + name)
                continue
            if _sha256(file) != entry["sha256"].lower():
                problems.append("Evidence SHA mismatch: " + name)
                continue
            verified.append({
                "file": name, "sha256": entry["sha256"].lower(),
                "content_hash_matches": True,
                "origin_and_accuracy_independently_verified": False,
            })
        per_gate[key] = {
            "requirement": description,
            "status": "EVIDENCE_PRESENT_REVIEW_REQUIRED" if verified and not problems
                      else "INVALID_EVIDENCE",
            "files": verified, "problems": problems,
        }
    return {
        "protocol": "N9-B v1",
        "physical_iphone11_accepted": False,
        "real_world_validated": False,
        "physical_windows_accepted": False,
        "independent_metric_accuracy_accepted": False,
        "reviewer_decision": "PENDING_EXTERNAL_INDEPENDENT_REVIEW",
        "gates": per_gate,
        "number_not_tested": sum(x["status"] == "NOT_TESTED" for x in per_gate.values()),
        "number_evidence_present_unreviewed": sum(
            x["status"] == "EVIDENCE_PRESENT_REVIEW_REQUIRED"
            for x in per_gate.values()),
        "number_physical_gates_automatically_passed": 0,
        "warnings": [
            "SHA match proves byte consistency only; not a camera model, license, physical inspection or measurement.",
            "N9-A public iPhone13/iPad proxy results never close an N9-B gate.",
            "Physical field reviews and independent acceptance signatures must be recorded outside this automated engine.",
        ],
    }
