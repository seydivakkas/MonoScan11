"""N9-B physical acceptance inventory — never self-certifies an iPhone 11."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from monoscan_core.n9b_acceptance import N9BError, audit_physical_evidence


def main():
    parser = argparse.ArgumentParser(description="N9-B external physical validation evidence audit")
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, help="Optional local evidence manifest")
    parser.add_argument("--output", type=Path, help="New output path (never overwrite)")
    args = parser.parse_args()
    try:
        result = audit_physical_evidence(args.evidence_root, args.manifest)
    except (N9BError, OSError, ValueError) as exc:
        print(json.dumps({"protocol": "N9-B v1", "result": "INVALID_INPUT",
                          "real_world_validated": False, "detail": str(exc)}, indent=2))
        return 2
    if args.output:
        if args.output.exists():
            print(json.dumps({"result": "REFUSE_OVERWRITE", "real_world_validated": False}))
            return 2
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
