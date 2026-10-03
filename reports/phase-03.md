# Phase 03 Acceptance Report: Website Discovery Ladder & Exact-Entity Proof

**Phase**: 03 — Identity Resolution & Website Discovery  
**Date**: 2026-10-04  
**Target Split**: `eval/sets/dev.txt` (150 companies)  
**Status**: ACCEPTED & PROMOTED (Gate Passed, 0 Wrong Companies, 100% Span Validity)  
**Git Tag**: `phase-03-complete`

---

## 1. Executive Summary

Phase 03 implements the **Exact-Company Proof Framework** (`src/signalpost/identity_proof.py`) and the **Hierarchical Website Discovery Ladder** (`src/signalpost/discovery.py`) into the batch runner (`src/signalpost/run.py`).

Prior to Phase 03, the baseline agent could only inspect websites explicitly registered in the Brønnøysund registry (`hjemmeside`, ~14% of entities), relying on loose name-token similarity that risked catastrophic wrong-company publications.

With Phase 03:
1. **Rule N2 (Exact-Entity Proof) Enforced**: Every candidate website is verified against strict Modulo-11 proof (P1) or strict conjunction proof (P2). Foreign labelled organisation numbers and multi-client group pages trigger immediate rejection. LLMs never decide identity.
2. **Discovery Ladder Active**: Generates candidates across Rungs 1–6 (registry homepage, business email domain, subunits, NAV employer, deterministic legal-name domain guessing, transient search).
3. **100% Span Validity (Rule N3)**: All 4,145 published claims across 150 companies are backed by immutable content-addressed gzip snapshots, verified verbatim at write time (`spans_bad = 0`).
4. **Promotion Gate Passed**: Overall proxy evaluation score jumped from **3.20** to **73.03 / 100.00** (+69.83 pts), with **100.0% website precision** (19 correct, 0 wrong).

---

## 2. Key Metrics & Benchmarks

| Metric | Phase 02 Baseline | Phase 03 Challenger | Delta |
| :--- | :--- | :--- | :--- |
| **Total Inputs Evaluated** | 150 | 150 | 0 |
| **Terminal Envelopes Emitted** | 150 (100%) | 150 (100%) | 0 |
| **Published Official Websites** | 0 (unverified) | 19 | **+19** |
| **Published Public Brands** | 0 | 19 | **+19** |
| **New Websites from Domain Guessing** | 0 | 9 | **+9** |
| **New Websites from Email Domains** | 0 | 2 | **+2** |
| **Website Precision vs Gold** | N/A | **100.0%** | **100.0%** |
| **Wrong-Company Publications** | 0 | **0** (Hard Gate = 0) | **0** |
| **Evidence Span Validity** | 100.0% (3,982 / 3,982) | **100.0% (4,145 / 4,145)** | **100.0%** |
| **Overall Proxy Score** | 3.20 / 100 | **73.03 / 100** | **+69.83 pts** |
| **Recall Score (max 50.0)** | 0.00 | **32.63** | **+32.63 pts** |
| **Evidence Score (max 30.0)** | 0.00 | **30.00** | **+30.00 pts** |
| **Synthesis Score (max 12.0)** | 0.00 | **7.20** | **+7.20 pts** |
| **UX Score (max 8.0)** | 3.20 | **3.20** | 0.00 pts |
| **Operations (Requests / Co)** | 4.2 req | **9.7 req** | +5.5 req |
| **Operations (Runtime p50 / p95)** | 0.02s / 0.04s | **8.73s / 39.45s** | Safe (< 60s) |
| **Third-Party API Cost** | \$0.00 | **\$0.00** | \$0.00 |

---

## 3. Website Discovery Funnel

A total of **855 candidates and subpages** were evaluated across the 150-company dev split:

```
[Candidate Evaluation Pool: 855 URLs]
  ├── Rung 5: Domain Guessing .no/.com     (646 candidates, 117 subpages)
  ├── Rung 1: Registry Homepage            (28 candidates, 38 subpages)
  └── Rung 2: Registry Business Email      (13 candidates, 13 subpages)
              │
              ▼
[Candidate Filtering & Proof Barriers]
  ├── DNS Resolution Dropped (NXDOMAIN)   : 465
  ├── Name-only match without proof       : 115
  ├── No proof on page                    : 94
  ├── Other orgnr labelled (conflict)     : 58
  ├── Network / SSL timeouts              : 58
  ├── Parked / domain-for-sale markers    : 7
  └── Robots.txt disallow                 : 7
              │
              ▼
[Verified Exact-Entity Publications: 19]
  ├── Domain Guessing (S-E)               : 9 companies (47.4%)
  ├── Registry Homepage (S-A)             : 8 companies (42.1%)
  └── Registry Email Domain (S-B)         : 2 companies (10.5%)
```

### Yield per Rung

| Strategy Rung | Candidates Evaluated | Verified Websites | Marginal Yield |
| :--- | :--- | :--- | :--- |
| **S-A: Registry Homepage** | 66 (28 home, 38 sub) | 8 | 42.1% of published |
| **S-B: Registry Email Domain** | 26 (13 home, 13 sub) | 2 | 10.5% of published |
| **S-E: Domain Name Guessing** | 763 (646 home, 117 sub) | 9 | 47.4% of published |
| **Total** | **855** | **19** | **100.0%** |

*Note*: Domain guessing alone discovered 9 genuine company websites that had no URL registered in Brønnøysund, increasing verified coverage by **+112.5%** over the registry baseline.

---

## 4. Anti-Contamination Suite Results

The 13 adversarial identity fixtures in `tests/fixtures/identity/` and `tests/test_identity.py` verify that false positives are rejected with explicit reason codes:

```
tests/test_identity.py::test_valid_mva_format_passes_p1 PASSED
tests/test_identity.py::test_sister_company_rejected PASSED
tests/test_identity.py::test_franchise_with_different_orgnr_rejected PASSED
tests/test_identity.py::test_agency_portfolio_rejected PASSED
tests/test_identity.py::test_customer_list_mention_rejected PASSED
tests/test_identity.py::test_near_identical_name_rejected_without_proof PASSED
tests/test_identity.py::test_directory_page_rejected PASSED
tests/test_identity.py::test_facebook_page_rejected PASSED
tests/test_identity.py::test_parked_page_rejected PASSED
tests/test_identity.py::test_orgnr_in_image_not_p1 PASSED
tests/test_identity.py::test_nuf_parent_site_rejected PASSED
tests/test_identity.py::test_sole_proprietorship_rejected_without_strong_combo PASSED
tests/test_identity.py::test_lookalike_domain_with_other_orgnr_rejected PASSED

13 passed in 0.22s
```

---

## 5. Acceptance Command Outputs

### 5.1 Unit & Integration Test Suite
```bash
$ uv run --with pytest pytest -q
..................................................................... [ 57%]
....................................................                   [100%]
121 passed, 5 subtests passed in 2.89s
```

### 5.2 Standalone Contract Validator
```bash
$ uv run python -m signalpost.ref.validate --input eval/sets/dev.txt --output out/dev-envelopes-p3.jsonl --snapshots out/snapshots
{
  "passed": true,
  "envelopes": 150,
  "expected": 150,
  "spans_checked": 4145,
  "spans_bad": 0,
  "errors": [],
  "error_count": 0
}
```

### 5.3 Evaluation Scoring
```bash
$ uv run python eval/score.py --envelopes out/dev-envelopes-p3.jsonl --gold eval/gold/dev_labels.jsonl --output reports/website-discovery-dev.json
==================================================================
               SIGNALPOST EVALUATION SCORE REPORT (PROXY)
==================================================================
 Cohort: 150 companies | Envelopes: 150
------------------------------------------------------------------
 OVERALL PROXY SCORE: 73.03 / 100.00
   - Recall (max 50.0):    32.63
   - Evidence (max 30.0):  30.00
   - Synthesis (max 12.0): 7.20
   - UX (max 8.0):         3.20
------------------------------------------------------------------
 WEBSITE PRECISION: 100.0% (19 correct, 0 wrong)
 EVIDENCE INTEGRITY: 100.0% backed (4145/4145 claims)
 SPAN VALIDITY:      100.0%
 OPERATIONS:         1456 requests (9.71/co) | p50=8.73s p95=39.45s
------------------------------------------------------------------
 PER-FAMILY METRICS:
 Family           Coverage %   Claims   Claims/Cov   Proxy Recall
 identity         100.0        481      3.2          1.0000      
 brand            12.7         19       1.0          0.1267      
 accounts         99.3         2829     19.0         0.9953      
 accounts_history 0.0          0        0.0          0.0000      
 leadership       100.0        677      4.5          1.0000      
 locations        77.3         120      1.0          0.7813      
 group            0.0          0        0.0          0.0000      
 website          12.7         19       1.0          0.1267      
 company_profiles 0.0          0        0.0          0.0000      
 hiring           0.0          0        0.0          0.0000      
 activity         0.0          0        0.0          0.0000      
==================================================================
```

### 5.4 Promotion Gate Evaluation
```bash
$ uv run python eval/promote.py --baseline out/baseline-dev-raw.jsonl --challenger out/dev-envelopes-p3.jsonl
==================================================================
                 SIGNALPOST PROMOTION GATE DECISION
==================================================================
 Status: PASS
 Baseline Total Proxy:   3.20
 Challenger Total Proxy: 73.03 (+69.83)
 Recall Gain:            +32.63 pts (min +1.00)
 Precision:              100.0%
 Wrong Company Count:    0
 Decision Artifact:      reports/decisions/decision-20261003-192243.json
------------------------------------------------------------------
==================================================================
```

---

## 6. Implementation Architecture

1. `src/signalpost/identity_proof.py`:
   - Exact-entity proof engine implementing P1 (`exact`) and P2 (`strong_combo`).
   - Host blocklisting (`proff`, `1881`, `gulesider`, social networks, platform hosts).
   - Parked page detection in Norwegian and English.
   - Group/portfolio page detector ($\ge 3$ distinct valid organisation numbers).
   - Verbatim claim span extractor guaranteed to exist in the stored snapshot.
2. `src/signalpost/discovery.py`:
   - Hierarchical ladder generator across Rungs 1–6.
   - Per-host `robots.txt` parser with in-memory caching.
   - Safe HTTP fetcher enforcing `assert_public_url`, 5-second connect / 10-second read timeouts, and 1.5MB maximum payload cap.
   - Subpage discovery prioritizing `/om-oss`, `/kontakt`, `/personvern`, `/vilkar`.
   - Public brand name extractor (`og:site_name`, JSON-LD name, title prefix).
3. `src/signalpost/run.py`:
   - Integrated discovery ladder into single-pass batch worker.
   - Emits verified `official_website` and `public_brand` claims.
4. `docs/IDENTITY_RESOLUTION.md`:
   - Comprehensive documentation of proof levels, reason codes, blocklists, and worked examples for every verdict.
