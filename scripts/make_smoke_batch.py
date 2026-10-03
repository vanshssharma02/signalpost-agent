#!/usr/bin/env python3
"""make_smoke_batch.py — Generate a 100-company smoke split with zero split overlap.
Seed: 20261004.
Asserts zero overlap with dev, val, holdout, stress.
Saves to out/smoke-100-input.jsonl and out/smoke-100-input.txt.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from signalpost.ref.orgnr import is_valid as is_valid_orgnr

UNIVERSE_PATH = ROOT / "data" / "signalpost-universe.jsonl.gz"
SETS_DIR = ROOT / "eval" / "sets"
DEFAULT_OUTPUT = ROOT / "out" / "smoke-100-input.jsonl"


def load_existing_orgnrs() -> set[str]:
    existing = set()
    for name in ("dev.txt", "val.txt", "holdout.txt", "stress.txt"):
        p = SETS_DIR / name
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                org = line.strip()
                if org:
                    existing.add(org)
    return existing


def generate_smoke_batch(seed: int = 20261004, count: int = 100, output_path: Path = DEFAULT_OUTPUT) -> dict:
    existing_orgnrs = load_existing_orgnrs()
    print(f"Loaded {len(existing_orgnrs)} existing organisation numbers across dev/val/holdout/stress.")

    candidates = []
    with gzip.open(UNIVERSE_PATH, "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            org = str(row.get("organisation_number", "")).strip()
            if not org or not is_valid_orgnr(org):
                continue
            if org in existing_orgnrs:
                continue
            candidates.append(row)

    print(f"Eligible universe candidate pool: {len(candidates)} companies.")

    rng = random.Random(seed)
    rng.shuffle(candidates)
    sampled = candidates[:count]

    # Verification assertions
    sampled_orgnrs = [str(r["organisation_number"]) for r in sampled]
    assert len(sampled) == count, f"Expected {count} companies, got {len(sampled)}"
    assert len(set(sampled_orgnrs)) == count, "Duplicates found in smoke batch"
    overlap = set(sampled_orgnrs) & existing_orgnrs
    assert len(overlap) == 0, f"Overlap detected with existing splits: {overlap}"
    for org in sampled_orgnrs:
        assert is_valid_orgnr(org), f"Invalid mod11 orgnr: {org}"

    # Write JSONL
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for row in sampled:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # Also write plain txt of orgnrs
    txt_path = output_path.with_suffix(".txt")
    with txt_path.open("w", encoding="utf-8") as f:
        for org in sampled_orgnrs:
            f.write(f"{org}\n")

    # Compute SHA-256
    file_bytes = output_path.read_bytes()
    sha256 = hashlib.sha256(file_bytes).hexdigest()

    summary = {
        "seed": seed,
        "count": count,
        "candidates_pool": len(candidates),
        "existing_split_exclusions": len(existing_orgnrs),
        "overlap_with_existing": 0,
        "jsonl_path": str(output_path),
        "txt_path": str(txt_path),
        "sha256": sha256,
        "first_5_orgnrs": sampled_orgnrs[:5],
    }
    return summary


def main():
    parser = argparse.ArgumentParser(description="Generate fresh 100-company smoke split")
    parser.add_argument("--seed", type=int, default=20261004)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    summary = generate_smoke_batch(seed=args.seed, count=args.count, output_path=Path(args.output))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
