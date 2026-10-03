"""
test_eval.py — Tests for Signalpost evaluation harness.
Covers:
  1. Stratification determinism & split disjointness (dev, val, holdout, stress).
  2. Metric calculation on tiny synthetic envelopes.
  3. Promotion gate pass & fail invariant checks.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from eval.promote import evaluate_promotion
from eval.score import score_envelopes
from signalpost.ref.orgnr import is_valid as is_valid_orgnr

ROOT = Path(__file__).resolve().parents[1]
SETS_DIR = ROOT / "eval" / "sets"


class TestEvaluationSets(unittest.TestCase):
    def test_splits_exist_and_counts_match(self):
        dev = [l.strip() for l in (SETS_DIR / "dev.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
        val = [l.strip() for l in (SETS_DIR / "val.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
        holdout = [l.strip() for l in (SETS_DIR / "holdout.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
        stress = [l.strip() for l in (SETS_DIR / "stress.txt").read_text(encoding="utf-8").splitlines() if l.strip()]

        self.assertEqual(len(dev), 150)
        self.assertEqual(len(val), 150)
        self.assertEqual(len(holdout), 200)
        self.assertEqual(len(stress), 60)

    def test_splits_are_mutually_disjoint(self):
        dev = set((SETS_DIR / "dev.txt").read_text(encoding="utf-8").splitlines())
        val = set((SETS_DIR / "val.txt").read_text(encoding="utf-8").splitlines())
        holdout = set((SETS_DIR / "holdout.txt").read_text(encoding="utf-8").splitlines())
        stress = set((SETS_DIR / "stress.txt").read_text(encoding="utf-8").splitlines())

        self.assertEqual(len(dev & val), 0)
        self.assertEqual(len(dev & holdout), 0)
        self.assertEqual(len(dev & stress), 0)
        self.assertEqual(len(val & holdout), 0)
        self.assertEqual(len(val & stress), 0)
        self.assertEqual(len(holdout & stress), 0)

    def test_all_orgnrs_are_valid_mod11(self):
        for name in ["dev", "val", "holdout", "stress"]:
            lines = (SETS_DIR / f"{name}.txt").read_text(encoding="utf-8").splitlines()
            for org in lines:
                org = org.strip()
                if org:
                    self.assertTrue(is_valid_orgnr(org), f"Invalid organisation number: {org} in {name}")

    def test_dev_contains_minimum_required_websites(self):
        manifest_path = SETS_DIR / "manifest.json"
        self.assertTrue(manifest_path.exists())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertGreaterEqual(manifest["dev_websites"], 25)
        self.assertGreaterEqual(manifest["val_websites"], 25)


class TestMetricMath(unittest.TestCase):
    def test_score_envelopes_on_synthetic_example(self):
        org1 = "985821585"
        org2 = "988077917"
        expected = [org1, org2]

        env1 = {
            "organisation_number": org1,
            "claims": [
                {
                    "claim_id": f"{org1}|legal_name",
                    "field": "legal_name",
                    "family": "identity",
                    "value": "Company One AS",
                    "availability": "available",
                    "evidence_ids": ["ev-1"]
                },
                {
                    "claim_id": f"{org1}|official_website",
                    "field": "official_website",
                    "family": "website",
                    "value": "https://example.no",
                    "availability": "available",
                    "evidence_ids": ["ev-2"]
                }
            ],
            "evidence": [
                {
                    "id": "ev-1",
                    "source_url": "https://data.brreg.no/api/enheter/985821585",
                    "retrieved_at": "2026-10-01T00:00:00Z",
                    "content_sha256": "abc123hash",
                    "claim_span": "Company One AS 985821585"
                },
                {
                    "id": "ev-2",
                    "source_url": "https://example.no",
                    "retrieved_at": "2026-10-01T00:00:00Z",
                    "content_sha256": "def456hash",
                    "claim_span": "Welcome to Company One Org 985821585"
                }
            ],
            "field_states": {
                "legal_name": {"state": "available"},
                "official_website": {"state": "available"}
            },
            "operations": {"requests": 3, "runtime_ms": 1500, "third_party_cost_usd": 0.0}
        }

        env2 = {
            "organisation_number": org2,
            "claims": [
                {
                    "claim_id": f"{org2}|legal_name",
                    "field": "legal_name",
                    "family": "identity",
                    "value": "Company Two AS",
                    "availability": "available",
                    "evidence_ids": ["ev-3"]
                }
            ],
            "evidence": [
                {
                    "id": "ev-3",
                    "source_url": "https://data.brreg.no/api/enheter/988077917",
                    "retrieved_at": "2026-10-01T00:00:00Z",
                    "content_sha256": "ghi789hash",
                    "claim_span": "Company Two AS 988077917"
                }
            ],
            "field_states": {
                "legal_name": {"state": "available"},
                "official_website": {"state": "not_available"}
            },
            "operations": {"requests": 2, "runtime_ms": 1000, "third_party_cost_usd": 0.0}
        }

        gold = {
            org1: {"organisation_number": org1, "official_website": "https://example.no"},
            org2: {"organisation_number": org2, "official_website": "none"}
        }

        report = score_envelopes([env1, env2], expected, gold)
        self.assertEqual(report["cohort_size"], 2)
        self.assertEqual(report["envelopes_count"], 2)

        # Identity coverage: 2/2 = 100%
        self.assertEqual(report["families"]["identity"]["covered_companies"], 2)
        self.assertEqual(report["families"]["identity"]["company_coverage_pct"], 100.0)

        # Website coverage: 1/2 = 50%
        self.assertEqual(report["families"]["website"]["covered_companies"], 1)
        self.assertEqual(report["families"]["website"]["company_coverage_pct"], 50.0)

        # Website precision: 1 correct, 0 wrong -> 100%
        self.assertEqual(report["website_precision"]["precision_pct"], 100.0)
        self.assertEqual(report["website_precision"]["wrong_company_count"], 0)

        # Span validity: 100%
        self.assertEqual(report["evidence_integrity"]["span_validity_pct"], 100.0)


class TestPromotionGate(unittest.TestCase):
    def setUp(self):
        self.base_report = {
            "scores": {"recall": 12.0, "evidence": 18.0, "synthesis": 7.2, "ux": 3.2, "total_proxy": 40.4},
            "website_precision": {"precision_pct": 100.0, "wrong_company_count": 0},
            "evidence_integrity": {"span_validity_pct": 100.0},
            "operations": {"p95_latency_s": 5.0}
        }

    def test_promotion_passes_on_improvement(self):
        challenger = {
            "scores": {"recall": 14.5, "evidence": 19.0, "synthesis": 7.2, "ux": 3.2, "total_proxy": 43.9},
            "website_precision": {"precision_pct": 100.0, "wrong_company_count": 0},
            "evidence_integrity": {"span_validity_pct": 100.0},
            "operations": {"p95_latency_s": 6.0}
        }
        passed, failures, decision = evaluate_promotion(self.base_report, challenger, min_recall_gain=1.0)
        self.assertTrue(passed)
        self.assertEqual(len(failures), 0)

    def test_promotion_fails_on_wrong_company(self):
        challenger = {
            "scores": {"recall": 16.0, "evidence": 19.0, "synthesis": 7.2, "ux": 3.2, "total_proxy": 45.4},
            "website_precision": {"precision_pct": 90.0, "wrong_company_count": 1},
            "evidence_integrity": {"span_validity_pct": 100.0},
            "operations": {"p95_latency_s": 6.0}
        }
        passed, failures, decision = evaluate_promotion(self.base_report, challenger)
        self.assertFalse(passed)
        self.assertTrue(any("wrong-company" in f.lower() for f in failures))

    def test_promotion_fails_on_insufficient_gain(self):
        challenger = {
            "scores": {"recall": 12.3, "evidence": 18.0, "synthesis": 7.2, "ux": 3.2, "total_proxy": 40.7},
            "website_precision": {"precision_pct": 100.0, "wrong_company_count": 0},
            "evidence_integrity": {"span_validity_pct": 100.0},
            "operations": {"p95_latency_s": 5.0}
        }
        passed, failures, decision = evaluate_promotion(self.base_report, challenger, min_recall_gain=1.0)
        self.assertFalse(passed)
        self.assertTrue(any("gain" in f.lower() for f in failures))

    def test_promotion_fails_on_latency_exceeded(self):
        challenger = {
            "scores": {"recall": 15.0, "evidence": 18.0, "synthesis": 7.2, "ux": 3.2, "total_proxy": 43.4},
            "website_precision": {"precision_pct": 100.0, "wrong_company_count": 0},
            "evidence_integrity": {"span_validity_pct": 100.0},
            "operations": {"p95_latency_s": 75.0}
        }
        passed, failures, decision = evaluate_promotion(self.base_report, challenger, max_p95_s=60.0)
        self.assertFalse(passed)
        self.assertTrue(any("latency" in f.lower() for f in failures))


if __name__ == "__main__":
    unittest.main()
