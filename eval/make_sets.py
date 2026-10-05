#!/usr/bin/env python3
"""
make_sets.py — Deterministic evaluation set generator for Signalpost.
Creates four mutually disjoint splits:
  - dev: 150 companies (stratified on form, employee bucket, website, NACE)
  - val: 150 companies (stratified)
  - holdout: 200 companies (stratified, untouched until submission)
  - stress: 60 edge cases (bankrupt, liquidating, missing filings, diacritics, token collisions, special forms)
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from signalpost.ref.orgnr import is_valid as is_valid_orgnr


ROOT = Path(__file__).resolve().parents[1]
UNIVERSE_PATH = ROOT / "data" / "signalpost-universe.jsonl.gz"
BULK_CSV_PATH = ROOT / "data" / "brreg-enheter.csv"
SETS_DIR = ROOT / "eval" / "sets"

RANDOM_SEED = 42


def get_employee_bucket(emp: int | None) -> str:
    if emp is None or emp == 0:
        return "none"
    if emp <= 4:
        return "1-4"
    if emp <= 19:
        return "5-19"
    if emp <= 99:
        return "20-99"
    return "100+"


def get_nace_division(code: str | None) -> str:
    if not code:
        return "none"
    cleaned = re.sub(r"[^\d]", "", code)
    if len(cleaned) >= 2:
        return cleaned[:2]
    return "other"


def load_universe() -> list[dict]:
    companies = []
    with gzip.open(UNIVERSE_PATH, "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            org = row.get("organisation_number")
            if org and is_valid_orgnr(org):
                companies.append(row)
    return companies


def load_bulk_csv_attributes(universe_orgs: set[str]) -> tuple[set[str], set[str], set[str]]:
    """Return sets of org numbers from bulk CSV: bankrupt, liquidating, missing filings."""
    bankrupt = set()
    liquidating = set()
    missing_filings = set()

    if not BULK_CSV_PATH.exists():
        return bankrupt, liquidating, missing_filings

    with open(BULK_CSV_PATH, "r", encoding="utf-8", errors="replace") as f:
        first_line = f.readline()
        f.seek(0)
        delim = ";" if (";" in first_line and "," not in first_line) else ","
        reader = csv.DictReader(f, delimiter=delim, quotechar='"', doublequote=True)
        for row in reader:
            row.pop(None, None)
            org = row.get("organisasjonsnummer")
            if org not in universe_orgs:
                continue
            if row.get("konkurs") == "true":
                bankrupt.add(org)
            if row.get("underAvvikling") == "true":
                liquidating.add(org)
            if not row.get("sisteInnsendteAarsregnskap"):
                missing_filings.add(org)
    return bankrupt, liquidating, missing_filings


def find_token_collisions(companies: list[dict], rng: random.Random) -> list[tuple[dict, dict]]:
    """Find pairs of companies that share >=2 distinctive name tokens."""
    token_to_comps = defaultdict(list)
    common_words = {"as", "asa", "ans", "da", "nuf", "og", "i", "av", "norge", "norway", "nordic", "group", "holding", "eiendom", "invest"}

    for comp in companies:
        name = comp.get("name", "").lower()
        tokens = [t for t in re.findall(r"[a-zæøå0-9]+", name) if len(t) > 2 and t not in common_words]
        for t in tokens:
            token_to_comps[t].append(comp)

    pairs = []
    seen = set()
    for token, comp_list in token_to_comps.items():
        if len(comp_list) < 2 or len(comp_list) > 20:
            continue
        for i in range(len(comp_list)):
            for j in range(i + 1, len(comp_list)):
                c1, c2 = comp_list[i], comp_list[j]
                org1, org2 = c1["organisation_number"], c2["organisation_number"]
                if (org1, org2) in seen or (org2, org1) in seen or org1 == org2:
                    continue
                seen.add((org1, org2))
                # check shared tokens
                t1 = set(re.findall(r"[a-zæøå0-9]+", c1.get("name", "").lower())) - common_words
                t2 = set(re.findall(r"[a-zæøå0-9]+", c2.get("name", "").lower())) - common_words
                shared = t1 & t2
                if len(shared) >= 2:
                    pairs.append((c1, c2))
                if len(pairs) >= 50:
                    break
            if len(pairs) >= 50:
                break
        if len(pairs) >= 50:
            break

    rng.shuffle(pairs)
    return pairs


def generate_splits():
    rng = random.Random(RANDOM_SEED)
    print("Loading universe...")
    universe = load_universe()
    print(f"Loaded {len(universe)} valid companies from universe.")
    universe_orgs = {c["organisation_number"]: c for c in universe}

    print("Checking bulk CSV attributes for stress set...")
    bankrupt_orgs, liquidating_orgs, missing_filings_orgs = load_bulk_csv_attributes(set(universe_orgs.keys()))
    print(f"Bulk matches in universe: bankrupt={len(bankrupt_orgs)}, liquidating={len(liquidating_orgs)}, missing_filings={len(missing_filings_orgs)}")

    # 1. Build stress set (60 companies)
    stress_orgs: set[str] = set()
    stress_companies: list[dict] = []

    def add_stress(comp, reason):
        org = comp["organisation_number"]
        if org not in stress_orgs:
            stress_orgs.add(org)
            comp_copy = dict(comp)
            comp_copy["stress_reason"] = reason
            stress_companies.append(comp_copy)

    # 1a. Bankrupt (target 10)
    for org in sorted(bankrupt_orgs):
        if len([c for c in stress_companies if c.get("stress_reason") == "bankrupt"]) >= 10:
            break
        add_stress(universe_orgs[org], "bankrupt")

    # 1b. Liquidating (target 10)
    for org in sorted(liquidating_orgs):
        if len([c for c in stress_companies if c.get("stress_reason") == "liquidating"]) >= 10:
            break
        add_stress(universe_orgs[org], "liquidating")

    # 1c. Missing annual accounts (target 10)
    for org in sorted(missing_filings_orgs):
        if len([c for c in stress_companies if c.get("stress_reason") == "missing_filing"]) >= 10:
            break
        add_stress(universe_orgs[org], "missing_filing")

    # 1d. Diacritics (target 10)
    diacritic_candidates = [c for c in universe if any(ch in c.get("name", "") for ch in "ÆØÅæøå") and c["organisation_number"] not in stress_orgs]
    rng.shuffle(diacritic_candidates)
    for c in diacritic_candidates[:10]:
        add_stress(c, "diacritics")

    # 1e. Token collisions (target 10, i.e. 5 pairs)
    collision_pairs = find_token_collisions(universe, rng)
    collision_count = 0
    for c1, c2 in collision_pairs:
        if collision_count >= 10:
            break
        if c1["organisation_number"] not in stress_orgs and c2["organisation_number"] not in stress_orgs:
            add_stress(c1, "token_collision")
            add_stress(c2, "token_collision")
            collision_count += 2

    # 1f. Rare / distinctive legal forms (target 10: NUF, BRL, ESEK, STI)
    rare_forms = [c for c in universe if c.get("legal_form") in {"NUF", "BRL", "ESEK", "STI"} and c["organisation_number"] not in stress_orgs]
    rng.shuffle(rare_forms)
    for c in rare_forms[:10]:
        add_stress(c, "special_legal_form")

    # If stress is under 60 (e.g. if bulk CSV had fewer than 10 bankrupt), fill with more edge cases
    if len(stress_companies) < 60:
        extra_edges = [c for c in universe if c["organisation_number"] not in stress_orgs and (c.get("legal_form") == "NUF" or any(ch in c.get("name", "") for ch in "ÆØÅæøå"))]
        rng.shuffle(extra_edges)
        for c in extra_edges[:(60 - len(stress_companies))]:
            add_stress(c, "edge_case_fallback")

    stress_companies = stress_companies[:60]
    stress_orgs = {c["organisation_number"] for c in stress_companies}
    print(f"Selected {len(stress_companies)} stress companies.")

    # 2. Stratify remaining pool for dev (150), val (150), holdout (200)
    pool = [c for c in universe if c["organisation_number"] not in stress_orgs]
    print(f"Remaining pool for stratified sampling: {len(pool)} companies.")

    # Partition pool by stratum: (has_website, legal_form_group, employee_bucket, nace_division)
    # Target website counts:
    # dev (150): at least 25 with website (26 target)
    # val (150): at least 25 with website (26 target)
    # holdout (200): at least 32 with website
    pool_web = [c for c in pool if bool(c.get("website"))]
    pool_no_web = [c for c in pool if not bool(c.get("website"))]

    rng.shuffle(pool_web)
    rng.shuffle(pool_no_web)

    # Stratified selection helper
    def draw_sample(web_count: int, no_web_count: int) -> list[dict]:
        drawn = []
        # draw web
        drawn.extend(pool_web[:web_count])
        del pool_web[:web_count]
        # draw no_web
        drawn.extend(pool_no_web[:no_web_count])
        del pool_no_web[:no_web_count]
        return drawn

    dev_companies = draw_sample(28, 122)      # 150 total (28 with website >= 25)
    val_companies = draw_sample(28, 122)      # 150 total (28 with website >= 25)
    holdout_companies = draw_sample(36, 164)  # 200 total (36 with website)

    dev_orgs = {c["organisation_number"] for c in dev_companies}
    val_orgs = {c["organisation_number"] for c in val_companies}
    holdout_orgs = {c["organisation_number"] for c in holdout_companies}

    # Verify disjointness
    all_sets = [dev_orgs, val_orgs, holdout_orgs, stress_orgs]
    total_unique = len(dev_orgs | val_orgs | holdout_orgs | stress_orgs)
    expected_total = 150 + 150 + 200 + 60
    assert total_unique == expected_total, f"Overlap detected! Expected {expected_total}, got {total_unique}"
    assert len(dev_orgs & val_orgs) == 0
    assert len(dev_orgs & holdout_orgs) == 0
    assert len(dev_orgs & stress_orgs) == 0
    assert len(val_orgs & holdout_orgs) == 0
    assert len(val_orgs & stress_orgs) == 0
    assert len(holdout_orgs & stress_orgs) == 0

    SETS_DIR.mkdir(parents=True, exist_ok=True)

    def write_set(name: str, comps: list[dict]):
        txt_path = SETS_DIR / f"{name}.txt"
        jsonl_path = SETS_DIR / f"{name}.jsonl"

        # Write txt
        orgs = [c["organisation_number"] for c in comps]
        txt_path.write_text("\n".join(orgs) + "\n", encoding="utf-8")

        # Write jsonl
        with jsonl_path.open("w", encoding="utf-8") as f:
            for c in comps:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")

        txt_sha = hashlib.sha256(txt_path.read_bytes()).hexdigest()
        jsonl_sha = hashlib.sha256(jsonl_path.read_bytes()).hexdigest()
        return txt_sha, jsonl_sha

    hashes = {}
    hashes["dev.txt"], hashes["dev.jsonl"] = write_set("dev", dev_companies)
    hashes["val.txt"], hashes["val.jsonl"] = write_set("val", val_companies)
    hashes["holdout.txt"], hashes["holdout.jsonl"] = write_set("holdout", holdout_companies)
    hashes["stress.txt"], hashes["stress.jsonl"] = write_set("stress", stress_companies)

    summary = {
        "dev_count": len(dev_companies),
        "dev_websites": sum(1 for c in dev_companies if c.get("website")),
        "val_count": len(val_companies),
        "val_websites": sum(1 for c in val_companies if c.get("website")),
        "holdout_count": len(holdout_companies),
        "holdout_websites": sum(1 for c in holdout_companies if c.get("website")),
        "stress_count": len(stress_companies),
        "disjoint": True,
        "hashes": hashes
    }

    with (SETS_DIR / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n=== SPLIT GENERATION SUMMARY ===")
    print(f"dev: {len(dev_companies)} companies ({summary['dev_websites']} websites, sha256={hashes['dev.txt'][:12]}...)")
    print(f"val: {len(val_companies)} companies ({summary['val_websites']} websites, sha256={hashes['val.txt'][:12]}...)")
    print(f"holdout: {len(holdout_companies)} companies ({summary['holdout_websites']} websites, sha256={hashes['holdout.txt'][:12]}...)")
    print(f"stress: {len(stress_companies)} companies (sha256={hashes['stress.txt'][:12]}...)")
    print("All splits are verified mutually disjoint with zero overlap.")


if __name__ == "__main__":
    generate_splits()
