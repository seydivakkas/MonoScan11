"""N9 independent 3D reference evidence: rigid (not scale-fitting) holdout QA.

A claimed external reference is NEVER equated to certified truth automatically.
Train target landmarks determine R,t ONLY; holdout landmarks report unbiased
test errors without re-optimizing scale. Input measurements are supplied as
track-id correspondences to a separately surveyed reference frame.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


class ReferenceEvidenceError(ValueError):
    pass


def _triplet(value):
    try:
        arr = np.asarray(value, dtype=float)
    except (ValueError, TypeError) as exc:
        raise ReferenceEvidenceError("Invalid 3D reference coordinate") from exc
    if arr.shape != (3,) or not np.isfinite(arr).all():
        raise ReferenceEvidenceError("Expected finite XYZ coordinate")
    return arr


def _rigid_kabsch(source, target):
    """Estimate transform no free scale: target = source @ rotation.T + translation."""
    if len(source) < 4 or len(target) != len(source):
        raise ReferenceEvidenceError("At least 4 training correspondences required")
    sc, tc = np.mean(source, axis=0), np.mean(target, axis=0)
    centered = source-sc
    singular = np.linalg.svd(centered, compute_uv=False)
    if singular[0] < 1e-9 or singular[1] / singular[0] < 1e-3:
        raise ReferenceEvidenceError("Degenerate surveyed landmarks")
    u, _, vt = np.linalg.svd((target-tc).T @ centered)
    repair = np.eye(3)
    repair[2, 2] = np.linalg.det(u @ vt)
    rotation = u @ repair @ vt
    return rotation, tc - rotation @ sc


def evaluate_independent_reference(run_dir, manifest_file, *, output=None):
    """Evaluate explicitly separate calibration vs validation landmarks.

    External manifest:
    {
      "schema_version":1,
      "reference_provenance":"measured independently by ...",
      "reference_file_sha256":"64-char independent-source file hash",
      "unit":"meter",
      "calibration":[{"track_id":1,"reference_xyz_m":[...]} * 4],
      "holdout":[{"track_id":5,"reference_xyz_m":[...]} * 4]
    }
    No fitting on holdout. Scale remains fixed to 1 even for PHOTO_ONLY:
    arbitrary SfM scale is not silently converted into metric evidence.
    """
    run_dir = Path(run_dir).resolve()
    manifest_file = Path(manifest_file).resolve()
    try:
        input_bytes = manifest_file.read_bytes()
        if len(input_bytes) > 256000:
            raise ReferenceEvidenceError("Reference metadata too large")
        spec = json.loads(input_bytes)
        tracks_bytes = (run_dir / "tracks.json").read_bytes()
        summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        tracks = json.loads(tracks_bytes)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        if isinstance(exc, ReferenceEvidenceError):
            raise
        raise ReferenceEvidenceError("Missing or malformed independent reference input") from exc
    if (not isinstance(spec, dict) or spec.get("schema_version") != 1
            or spec.get("unit") != "meter"
            or not isinstance(spec.get("reference_provenance"), str)
            or len(spec["reference_provenance"].strip()) < 16
            or not isinstance(spec.get("reference_file_sha256"), str)
            or len(spec["reference_file_sha256"]) != 64
            or any(ch not in "0123456789abcdef" for ch in spec["reference_file_sha256"].lower())):
        raise ReferenceEvidenceError("Unverifiable independent reference provenance")
    if (summary.get("engine") != "monoscan-native"
            or summary.get("mode_used") != "arkit-guided"
            or summary.get("real_world_validated") is True):
        raise ReferenceEvidenceError("Only explicitly unverified ARKit-guided tracks may be compared")
    if not isinstance(tracks, list):
        raise ReferenceEvidenceError("Missing landmark track collection")
    try:
        model = {record["id"]: _triplet(record["xyz"])
                 for record in tracks}
    except (KeyError, TypeError, ReferenceEvidenceError) as exc:
        raise ReferenceEvidenceError("Invalid model landmark coordinates") from exc
    training, holdout, ids = [], [], set()
    for key, out in [("calibration", training), ("holdout", holdout)]:
        rows = spec.get(key)
        if not isinstance(rows, list) or not 4 <= len(rows) <= 200:
            raise ReferenceEvidenceError("Need at least four separate surveyed " + key + " landmarks")
        for row in rows:
            if not isinstance(row, dict) or type(row.get("track_id")) is not int:
                raise ReferenceEvidenceError("Invalid surveyed track identifier")
            track = row["track_id"]
            if track in ids or track not in model:
                raise ReferenceEvidenceError("Duplicate or unknown track across reference splits")
            ids.add(track)
            out.append((model[track], _triplet(row.get("reference_xyz_m"))))
    src = np.asarray([p[0] for p in training])
    gt = np.asarray([p[1] for p in training])
    r, t = _rigid_kabsch(src, gt)
    test_source = np.asarray([p[0] for p in holdout])
    test_ground_truth = np.asarray([p[1] for p in holdout])
    predicted = test_source @ r.T + t
    errors = np.linalg.norm(predicted-test_ground_truth, axis=1)
    if not np.isfinite(errors).all():
        raise ReferenceEvidenceError("Reference matching yielded nonfinite residuals")
    result = {
        "stage": "N9 independent reference candidate", "state": "REVIEW_REQUIRED",
        "reference_provenance_claim": spec["reference_provenance"],
        "reference_file_sha256_claim": spec["reference_file_sha256"],
        "reference_manifest_sha256": hashlib.sha256(input_bytes).hexdigest(),
        "tracks_sha256": hashlib.sha256(tracks_bytes).hexdigest(),
        "measured_unit": "meter", "similarity_scale_fitted": False,
        "rigid_scale_fixed": 1.0, "calibration_correspondences": len(training),
        "holdout_correspondences": len(holdout),
        "holdout_rmse_m": float(np.sqrt(np.mean(errors*errors))),
        "holdout_median_m": float(np.median(errors)),
        "holdout_p95_m": float(np.percentile(errors, 95)),
        "holdout_max_m": float(np.max(errors)),
        "holdout_per_landmark_error_m": errors.tolist(),
        "real_world_validated": False,
        "physical_iphone11_tested": False,
        "reference_independently_verified": False,
        "notes": [
            "Correspondence identity and reference trace must be reviewed independently.",
            "Fixed-scale rigid alignment prevents artificial metric success by Sim(3).",
            "No threshold or accuracy certification is assigned automatically.",
        ],
    }
    if output is not None:
        out = Path(output)
        if out.exists():
            raise ReferenceEvidenceError("Refusing to replace existing evidence")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    return result
