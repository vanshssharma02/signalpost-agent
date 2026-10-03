#!/usr/bin/env python3
"""
score.py — Evaluation harness metrics & scoring for Signalpost.
Calculates per-family coverage, claim density, proxy recall (0.7 company + 0.3 claims),
evidence validity, website precision vs gold truths, operations metrics,
and the Builderr competition rubric proxy:
  - Recall (50)
  - Evidence (30)
  - Synthesis (12)
  - UX (8)
Total: 100
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from signalpost.ref.envelope import FAMILIES, STATES


RUBRIC_MAX = {
    "recall": 50.0,
    "evidence": 30.0,
    "synthesis": 12.0,
    "ux": 8.0,
}

FAMILY_WEIGHTS = {
    "identity": 0.20,
    "accounts": 0.20,
    "leadership": 0.15,
    "locations": 0.10,
    "group": 0.05,
    "website": 0.15,
    "brand": 0.05,
    "hiring": 0.05,
    "activity": 0.05,
}


def load_envelopes(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_gold_labels(path: Path) -> dict[str, dict[str, Any]]:
    gold = {}
    if not path.exists():
        return gold
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                org = row.get("organisation_number")
                if org:
                    gold[org] = row
    return gold


def score_envelopes(
    envelopes: list[dict[str, Any]],
    expected_orgs: list[str],
    gold_labels: dict[str, dict[str, Any]] | None = None,
    viewer_path: Path | None = None,
) -> dict[str, Any]:
    gold_labels = gold_labels or {}
    total_expected = len(expected_orgs)
    env_by_org = {env.get("organisation_number"): env for env in envelopes}

    # Track per-family metrics
    family_covered_comps = defaultdict(set)
    family_claims_count = defaultdict(int)
    field_state_dist = Counter()

    # Evidence metrics
    total_claims = 0
    valid_evidence_claims = 0
    total_evidences = 0
    valid_evidences = 0

    # Website precision
    published_websites = {}
    wrong_company_count = 0
    same_company_count = 0
    cannot_tell_count = 0
    wrong_companies = []

    # Operations
    total_requests = 0
    total_bytes = 0
    latencies = []
    total_cost_usd = 0.0

    for org in expected_orgs:
        env = env_by_org.get(org)
        if not env:
            continue

        ops = env.get("operations") or {}
        total_requests += ops.get("requests", 0)
        total_bytes += ops.get("bytes", 0)
        total_cost_usd += float(ops.get("third_party_cost_usd", 0.0))
        if "runtime_ms" in ops:
            latencies.append(ops["runtime_ms"] / 1000.0)

        # Inspect field states
        for field, state_obj in (env.get("field_states") or {}).items():
            state = state_obj.get("state") if isinstance(state_obj, dict) else state_obj
            if state in STATES:
                field_state_dist[state] += 1

        # Inspect evidences
        ev_map = {}
        for ev in env.get("evidence") or []:
            total_evidences += 1
            ev_id = ev.get("id")
            # Evidence requires source_url, retrieved_at, content_sha256, claim_span
            has_url = bool(ev.get("source_url"))
            has_retrieved = bool(ev.get("retrieved_at"))
            has_hash = bool(ev.get("content_sha256"))
            has_span = bool(ev.get("claim_span"))
            if has_url and has_retrieved and has_hash and has_span:
                valid_evidences += 1
                ev_map[ev_id] = ev

        # Inspect claims
        for claim in env.get("claims") or []:
            total_claims += 1
            fam = claim.get("family", "identity")
            field = claim.get("field", "")
            avail = claim.get("availability", "available")

            if avail == "available":
                family_covered_comps[fam].add(org)
                family_claims_count[fam] += 1

            # Check evidence backing
            ev_ids = claim.get("evidence_ids") or []
            if ev_ids and all(eid in ev_map for eid in ev_ids):
                valid_evidence_claims += 1

            # Check website claim precision
            if field == "official_website" and avail == "available":
                val = claim.get("value")
                if val:
                    published_websites[org] = val
                    if org in gold_labels:
                        gold_val = gold_labels[org].get("official_website", "none")
                        if gold_val != "none":
                            # Compare domain / url
                            clean_pub = val.lower().rstrip("/").replace("https://", "").replace("http://", "").replace("www.", "")
                            clean_gold = gold_val.lower().rstrip("/").replace("https://", "").replace("http://", "").replace("www.", "")
                            if clean_pub == clean_gold or clean_pub in clean_gold or clean_gold in clean_pub:
                                same_company_count += 1
                            else:
                                wrong_company_count += 1
                                wrong_companies.append({"orgnr": org, "published": val, "gold": gold_val})
                        else:
                            # Gold says none, but we published
                            wrong_company_count += 1
                            wrong_companies.append({"orgnr": org, "published": val, "gold": "none"})

    # Compute family table
    families_report = {}
    weighted_recall_sum = 0.0

    for fam in FAMILIES:
        covered = len(family_covered_comps[fam])
        claims_cnt = family_claims_count[fam]
        comp_coverage = (covered / total_expected) if total_expected > 0 else 0.0
        # Reference claim density benchmark (expect ~1-4 claims per family)
        benchmark_claims_total = total_expected * (3 if fam in {"accounts", "identity", "leadership"} else 1)
        claim_coverage = min(1.0, (claims_cnt / benchmark_claims_total) if benchmark_claims_total > 0 else 0.0)

        # PROXY recall formula: 0.7 * comp_coverage + 0.3 * claim_coverage
        proxy_recall = 0.7 * comp_coverage + 0.3 * claim_coverage
        w = FAMILY_WEIGHTS.get(fam, 0.05)
        weighted_recall_sum += w * proxy_recall

        families_report[fam] = {
            "covered_companies": covered,
            "company_coverage_pct": round(comp_coverage * 100, 2),
            "claims_count": claims_cnt,
            "claims_per_covered": round(claims_cnt / covered, 2) if covered > 0 else 0.0,
            "proxy_recall": round(proxy_recall, 4),
        }

    # Precision
    total_eval_websites = same_company_count + wrong_company_count
    website_precision = (same_company_count / total_eval_websites) if total_eval_websites > 0 else 1.0

    # Evidence score (30)
    evidence_validity = (valid_evidence_claims / total_claims) if total_claims > 0 else 0.0
    evidence_score = round(evidence_validity * RUBRIC_MAX["evidence"] * (0.6 + 0.4 * (min(1.0, total_claims / max(1, total_expected * 5)))), 2)

    # Recall score (50)
    recall_score = round(weighted_recall_sum * RUBRIC_MAX["recall"], 2)

    # Synthesis score (12): baseline starter achieves ~7.2 (factor 0.6)
    valid_synthesis_count = 0
    for env in envelopes:
        synth = env.get("synthesis")
        if synth and isinstance(synth, dict) and synth.get("sentences"):
            cids = {c.get("claim_id") for c in env.get("claims", [])}
            all_cited = True
            for s in synth.get("sentences", []):
                for cid in s.get("claim_ids", []):
                    if cid not in cids:
                        all_cited = False
                        break
            if all_cited:
                valid_synthesis_count += 1

    if total_expected > 0 and valid_synthesis_count > 0:
        synth_ratio = valid_synthesis_count / total_expected
        synthesis_factor = 0.6 + 0.4 * synth_ratio
    else:
        synthesis_factor = 0.6 if total_claims > 0 else 0.0

    synthesis_score = round(synthesis_factor * RUBRIC_MAX["synthesis"], 2)

    # UX score (8): baseline starter achieves ~3.2 (factor 0.4)
    if viewer_path and Path(viewer_path).exists():
        viewer_text = Path(viewer_path).read_text(encoding="utf-8")
        has_doctype = "<!doctype html" in viewer_text.lower()
        has_search = 'type="search"' in viewer_text or "search" in viewer_text.lower()
        has_skip = "skip-link" in viewer_text
        has_evidence_modal = "evidence-modal" in viewer_text or "evidence-popover" in viewer_text
        has_responsive = "@media" in viewer_text
        if has_doctype and has_search and has_skip and has_evidence_modal and has_responsive:
            ux_factor = 1.0
        else:
            ux_factor = 0.7
    else:
        ux_factor = 0.4 if len(envelopes) == total_expected else 0.2

    ux_score = round(ux_factor * RUBRIC_MAX["ux"], 2)

    total_proxy_score = round(recall_score + evidence_score + synthesis_score + ux_score, 2)

    # Latencies
    latencies.sort()
    p50_s = round(latencies[len(latencies) // 2], 2) if latencies else 0.0
    p95_s = round(latencies[int(len(latencies) * 0.95)], 2) if latencies else 0.0

    return {
        "cohort_size": total_expected,
        "envelopes_count": len(envelopes),
        "scores": {
            "recall": recall_score,
            "evidence": evidence_score,
            "synthesis": synthesis_score,
            "ux": ux_score,
            "total_proxy": total_proxy_score,
        },
        "website_precision": {
            "published_count": len(published_websites),
            "same_company_count": same_company_count,
            "wrong_company_count": wrong_company_count,
            "precision_pct": round(website_precision * 100, 2),
            "wrong_companies": wrong_companies,
        },
        "evidence_integrity": {
            "total_claims": total_claims,
            "valid_evidence_claims": valid_evidence_claims,
            "claim_evidence_pct": round((valid_evidence_claims / total_claims * 100), 2) if total_claims > 0 else 0.0,
            "total_evidences": total_evidences,
            "valid_evidences": valid_evidences,
            "span_validity_pct": round((valid_evidences / total_evidences * 100), 2) if total_evidences > 0 else 100.0,
        },
        "operations": {
            "total_requests": total_requests,
            "requests_per_company": round(total_requests / total_expected, 2) if total_expected > 0 else 0.0,
            "p50_latency_s": p50_s,
            "p95_latency_s": p95_s,
            "third_party_cost_usd": total_cost_usd,
        },
        "field_states": dict(field_state_dist),
        "families": families_report,
    }


def format_cli_table(results: dict[str, Any]) -> str:
    s = results["scores"]
    ops = results["operations"]
    wp = results["website_precision"]
    ei = results["evidence_integrity"]

    lines = [
        "==================================================================",
        f"               SIGNALPOST EVALUATION SCORE REPORT (PROXY)",
        "==================================================================",
        f" Cohort: {results['cohort_size']} companies | Envelopes: {results['envelopes_count']}",
        "------------------------------------------------------------------",
        f" OVERALL PROXY SCORE: {s['total_proxy']:.2f} / 100.00",
        f"   - Recall (max 50.0):    {s['recall']:.2f}",
        f"   - Evidence (max 30.0):  {s['evidence']:.2f}",
        f"   - Synthesis (max 12.0): {s['synthesis']:.2f}",
        f"   - UX (max 8.0):         {s['ux']:.2f}",
        "------------------------------------------------------------------",
        f" WEBSITE PRECISION: {wp['precision_pct']:.1f}% ({wp['same_company_count']} correct, {wp['wrong_company_count']} wrong)",
        f" EVIDENCE INTEGRITY: {ei['claim_evidence_pct']:.1f}% backed ({ei['valid_evidence_claims']}/{ei['total_claims']} claims)",
        f" SPAN VALIDITY:      {ei['span_validity_pct']:.1f}%",
        f" OPERATIONS:         {ops['total_requests']} requests ({ops['requests_per_company']}/co) | p50={ops['p50_latency_s']}s p95={ops['p95_latency_s']}s",
        "------------------------------------------------------------------",
        " PER-FAMILY METRICS:",
        f" {'Family':<16} {'Coverage %':<12} {'Claims':<8} {'Claims/Cov':<12} {'Proxy Recall':<12}",
    ]
    for fam, f_data in results["families"].items():
        lines.append(
            f" {fam:<16} {f_data['company_coverage_pct']:<12.1f} {f_data['claims_count']:<8} {f_data['claims_per_covered']:<12.1f} {f_data['proxy_recall']:<12.4f}"
        )
    lines.append("==================================================================")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Evaluate Signalpost result envelopes")
    parser.add_argument("--envelopes", required=True, help="Path to terminal envelopes JSONL")
    parser.add_argument("--set", default="dev", choices=["dev", "val", "holdout", "stress"], help="Named evaluation set")
    parser.add_argument("--orgs", help="Path to custom text file of expected organisation numbers")
    parser.add_argument("--gold", help="Path to gold truth labels JSONL")
    parser.add_argument("--viewer", help="Path to compiled standalone viewer HTML file")
    parser.add_argument("--output", help="Path to write evaluation JSON report")
    args = parser.parse_args()

    # Load expected orgs
    if args.orgs:
        org_path = Path(args.orgs)
    else:
        org_path = ROOT / "eval" / "sets" / f"{args.set}.txt"
    expected_orgs = [line.strip() for line in org_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    # Load envelopes
    env_path = Path(args.envelopes)
    envelopes = load_envelopes(env_path)

    # Load gold
    if args.gold:
        gold_path = Path(args.gold)
    else:
        gold_path = ROOT / "eval" / "gold" / f"{args.set}_labels.jsonl"
    gold = load_gold_labels(gold_path)

    viewer_p = Path(args.viewer) if args.viewer else None
    results = score_envelopes(envelopes, expected_orgs, gold, viewer_path=viewer_p)
    print(format_cli_table(results))

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Saved evaluation report to {out_path}")


if __name__ == "__main__":
    main()
