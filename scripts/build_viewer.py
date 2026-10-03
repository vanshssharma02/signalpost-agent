#!/usr/bin/env python3
"""build_viewer.py — CLI to build the Signalpost static company viewer.
Compiles emitted JSONL envelopes into out/viewer/index.html and site/ distribution.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from signalpost.viewer import build_viewer_site


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile Signalpost Static HTML Viewer")
    parser.add_argument("--input", "-i", required=True, help="Input envelopes JSONL file path")
    parser.add_argument("--output", "-o", default="out/viewer/index.html", help="Output standalone HTML file")
    parser.add_argument("--site", default="site", help="Output directory for full static site")
    args = parser.parse_args()

    summary = build_viewer_site(
        envelopes_path=args.input,
        out_dir=args.site,
        standalone_path=args.output,
    )
    print(f"Viewer compiled successfully:")
    print(f"  Envelopes:  {summary['envelopes_count']}")
    print(f"  Index size: {summary['index_json_kb']} KB (< 400 KB limit)")
    print(f"  Standalone: {summary['standalone_path']}")
    print(f"  Site dir:   {summary['site_dir']}")


if __name__ == "__main__":
    main()
