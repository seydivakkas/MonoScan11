"""MonoScan11 N7 offline desktop entry point; no Mac, browser or cloud."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from monoscan_core.desktop import main


if __name__ == "__main__":
    main()
