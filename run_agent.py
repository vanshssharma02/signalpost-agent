#!/usr/bin/env python3
"""Entry point for Signalpost agent."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from signalpost.run import main

if __name__ == "__main__":
    main()
