"""N9-A real public-image proxy runner; explicit scope N9-A, never N9-B."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from monoscan_core.n9a_acceptance import N9AError, evaluate_proxy_session


def main():
    p = argparse.ArgumentParser(description="N9-A real-image public proxy trial, NOT iPhone11 acceptance")
    p.add_argument("--session", type=Path, required=True,
                   help="N9 adapter output with validated n9_source_audit.json")
    p.add_argument("--report-dir", type=Path, required=True,
                   help="New, separate evidence folder; never overwritten")
    p.add_argument("--mode", choices=("photo-only", "arkit-guided"), required=True)
    p.add_argument("--focal-px", type=float,
                   help="Explicit separately calibrated PHOTO_ONLY focal length in pixels")
    p.add_argument("--rights-reviewed", action="store_true",
                   help="Attest you independently checked permission to use these source images")
    p.add_argument("--refine", action="store_true")
    p.add_argument("--dense", action="store_true")
    p.add_argument("--min-depth", type=float)
    p.add_argument("--max-depth", type=float)
    p.add_argument("--preflight-only", action="store_true",
                   help="Inspect original source ledger, execute NO reconstruction")
    args = p.parse_args()
    try:
        result = evaluate_proxy_session(
            args.session, args.report_dir, mode=args.mode,
            focal_px=args.focal_px, rights_reviewed=args.rights_reviewed,
            run_refine=args.refine, run_dense=args.dense,
            min_depth=args.min_depth, max_depth=args.max_depth,
            dry_run=args.preflight_only)
    except (N9AError, OSError, ValueError) as exc:
        print(json.dumps({"protocol": "N9-A v1",
                          "result": "BLOCKED_PREREQUISITE",
                          "detail": str(exc), "real_world_validated": False,
                          "n9b_status": "NOT_TESTED"}, indent=2))
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result["result"] in (
        "SOURCE_PREFLIGHT_ONLY", "PROXY_PROCESSING_COMPLETED_REVIEW_REQUIRED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
