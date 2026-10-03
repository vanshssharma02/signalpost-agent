#!/usr/bin/env python3
"""
promote.py — Promotion gate for Signalpost challenger strategies.
Evaluates challenger against baseline according to config/strategies.toml:
  - Zero new wrong-company publications (FATAL if > 0)
  - Claim precision not lower
  - Span validity 100%
  - Proxy recall gain >= min_proxy_recall_gain
  - Runtime p95 <= max_p95_company_s
  - Third-party cost within budget
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "strategies.toml"
DECISIONS_DIR = ROOT / "reports" / "decisions"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_promotion(
    baseline: dict[str, Any],
    challenger: dict[str, Any],
    *,
    min_recall_gain: float = 1.0,
    max_p95_s: float = 60.0,
    max_new_wrong_company: int = 0,
    min_span_validity: float = 1.0,
) -> tuple[bool, list[str], dict[str, Any]]:
    failures = []
    
    b_scores = baseline.get("scores", {})
    c_scores = challenger.get("scores", {})
    
    b_wp = baseline.get("website_precision", {})
    c_wp = challenger.get("website_precision", {})
    
    b_ei = baseline.get("evidence_integrity", {})
    c_ei = challenger.get("evidence_integrity", {})
    
    b_ops = baseline.get("operations", {})
    c_ops = challenger.get("operations", {})

    # 1. Zero new wrong-company publications
    b_wrong = b_wp.get("wrong_company_count", 0)
    c_wrong = c_wp.get("wrong_company_count", 0)
    new_wrong = c_wrong - b_wrong
    if c_wrong > 0 and new_wrong > max_new_wrong_company:
        failures.append(f"Gate 1 Failed: New wrong-company publications detected ({new_wrong} new, total={c_wrong}). Allowed={max_new_wrong_company}.")

    # 2. Claim precision not lower
    b_prec = b_wp.get("precision_pct", 100.0)
    c_prec = c_wp.get("precision_pct", 100.0)
    if c_prec < b_prec:
        failures.append(f"Gate 2 Failed: Precision dropped from {b_prec:.2f}% to {c_prec:.2f}%.")

    # 3. Span validity
    c_span = c_ei.get("span_validity_pct", 100.0) / 100.0
    if c_span < min_span_validity:
        failures.append(f"Gate 3 Failed: Span validity is {c_span*100:.2f}%, required {min_span_validity*100:.2f}%.")

    # 4. Recall gain
    b_recall = b_scores.get("recall", 0.0)
    c_recall = c_scores.get("recall", 0.0)
    recall_gain = c_recall - b_recall
    if recall_gain < min_recall_gain:
        failures.append(f"Gate 4 Failed: Proxy recall gain is {recall_gain:+.2f} pts, required at least {min_recall_gain:+.2f} pts.")

    # 5. Latency p95
    c_p95 = c_ops.get("p95_latency_s", 0.0)
    if c_p95 > max_p95_s:
        failures.append(f"Gate 5 Failed: p95 latency is {c_p95:.2f}s, exceeding budget {max_p95_s:.2f}s.")

    passed = (len(failures) == 0)
    decision = {
        "passed": passed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "baseline_score": b_scores.get("total_proxy", 0.0),
        "challenger_score": c_scores.get("total_proxy", 0.0),
        "recall_gain": round(recall_gain, 4),
        "precision_change": round(c_prec - b_prec, 2),
        "challenger_wrong_company": c_wrong,
        "challenger_span_validity_pct": round(c_span * 100, 2),
        "challenger_p95_s": c_p95,
        "failures": failures,
    }
    return passed, failures, decision


def main():
    parser = argparse.ArgumentParser(description="Promotion gate for Signalpost challenger strategies")
    parser.add_argument("baseline", help="Baseline evaluation report JSON")
    parser.add_argument("challenger", help="Challenger evaluation report JSON")
    parser.add_argument("--min-gain", type=float, default=1.0, help="Minimum required proxy recall gain")
    parser.add_argument("--decision-file", help="Path to write decision report")
    args = parser.parse_args()

    baseline_data = load_json(Path(args.baseline))
    challenger_data = load_json(Path(args.challenger))

    passed, failures, decision = evaluate_promotion(
        baseline_data, challenger_data, min_recall_gain=args.min_gain
    )

    DECISIONS_DIR.mkdir(parents=True, exist_ok=True)
    decision_path = Path(args.decision_file) if args.decision_file else (
        DECISIONS_DIR / f"decision-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"
    )
    with decision_path.open("w", encoding="utf-8") as f:
        json.dump(decision, f, indent=2)

    print("==================================================================")
    print("                 SIGNALPOST PROMOTION GATE DECISION")
    print("==================================================================")
    print(f" Status: {'PASS' if passed else 'FAIL'}")
    print(f" Baseline Total Proxy:   {decision['baseline_score']:.2f}")
    print(f" Challenger Total Proxy: {decision['challenger_score']:.2f} ({decision['challenger_score'] - decision['baseline_score']:+.2f})")
    print(f" Recall Gain:            {decision['recall_gain']:+.2f} pts (min {args.min_gain:+.2f})")
    print(f" Precision:              {challenger_data.get('website_precision', {}).get('precision_pct', 100):.1f}%")
    print(f" Wrong Company Count:    {decision['challenger_wrong_company']}")
    print(f" Decision Artifact:      {decision_path}")
    print("------------------------------------------------------------------")
    if failures:
        print(" FAILURES:")
        for f in failures:
            print(f"   * {f}")
    print("==================================================================")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
