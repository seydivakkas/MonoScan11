"""Native CLI alias; preserves existing tools/monoscan.py validate/demo semantics.

Run from project directory: python -m monoscan_core.cli reconstruct <session>.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from monoscan import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
