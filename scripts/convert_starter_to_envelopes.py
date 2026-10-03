#!/usr/bin/env python3
"""Convert starter profile JSONL output to OUTPUT_CONTRACT compliant envelopes."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from signalpost.envelope_adapter import profile_to_envelope
from signalpost.ref.envelope import utc_now


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert starter profiles to contract envelopes")
    parser.add_argument("--input", required=True, help="Input profiles or envelopes JSONL")
    parser.add_argument("--output", required=True, help="Output envelopes JSONL")
    parser.add_argument("--run-id", default="baseline-dev")
    args = parser.parse_args()

    run_meta = {
        "run_id": args.run_id,
        "started_at": utc_now(),
        "terminal_status": "completed",
        "agent": {
            "name": "norway-company-agent-starter",
            "version": "0.1.0",
            "git_commit": "baseline",
        },
        "strategy_set": "starter",
    }

    in_path = Path(args.input)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with in_path.open("r", encoding="utf-8") as fin, out_path.open("w", encoding="utf-8") as fout:
        for line in fin:
            if not line.strip():
                continue
            item = json.loads(line)
            profile = item.get("profile", item)
            env = profile_to_envelope(profile, run=run_meta)
            fout.write(json.dumps(env, ensure_ascii=False) + "\n")
            count += 1

    print(f"Converted {count} starter profiles to {out_path}")


if __name__ == "__main__":
    main()
