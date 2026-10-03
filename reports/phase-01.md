# Phase 1: Evaluation Harness & Starter Baseline Report

## Executive Summary

Phase 1 establishes the empirical foundation for Signalpost in accordance with `.agents/workflows/01-eval-harness.md` and Rule **N10**. We constructed stratified evaluation splits, generated human labelling templates with an interactive review tool, built the scoring engine and promotion gate, and recorded the verified baseline performance of the unmodified starter kit on the 150-company `dev` cohort under live network conditions.

---

## 1. Evaluation Splits

The splits were generated deterministically using `eval/make_sets.py` (`seed=42`) from `data/signalpost-universe.jsonl.gz` (411,160 companies) and cross-stratified against `data/brreg-enheter.csv` for stress attributes.

| Split | Count | SHA-256 Checksum | Registry Websites Present | Key Characteristics |
|---|---|---|---|---|
| **dev** | 150 | `0d81c410d630e60ef5b2835286863359eb8e19644528a3a5da26f4039f9fc090` | 28 (18.67%) | Stratified across legal form, size, NACE division |
| **val** | 150 | `8e482fde0d02f658f3fe05c891f535fbf77184f54c53632892a2f8fc00058edc` | 28 (18.67%) | Disjoint replication split for pre-freeze testing |
| **holdout** | 200 | `3c4fd69b43f44c918bf0c10a54153fdd0d52840b6e654de58880ffd364bee5d6` | 36 (18.00%) | **Untouched until Workflow /07 submission** |
| **stress** | 60 | `47eaa711713cd399a359e6c12e5639664f437bc824cd2ed795d59593f517807f` | 11 (18.33%) | 10 bankrupt, 10 liquidating, 10 missing filings, 10 diacritics, 10 token collisions (5 pairs), 10 special legal forms (`NUF`, `BRL`, `ESEK`, `STI`) |

- **Pairwise Overlap**: Verified exactly 0 overlapping organisations across all splits.
- **Modulo-11 Validity**: Verified 100% (all 560 organisation numbers satisfy the official Norwegian Modulo-11 checksum).
- Companion files: `eval/sets/{dev,val,holdout,stress}.{txt,jsonl}` and `eval/sets/manifest.json`.

---

## 2. Labelling Harness & Review Tool

Generated via `eval/label.py`:
- `eval/dev-labels-template.csv`: Tabular spreadsheet for bulk annotators.
- `eval/dev-labels-template.jsonl`: Machine-readable annotation records.
- `eval/labels/sheet.html`: Single-file interactive HTML review workspace:
  - Displays registry facts (name, orgnr, municipality, NACE, employees, declared website, status).
  - Displays candidate domains and live probe results.
  - Three-way verification buttons: `Same Company (Official)`, `Different Company`, `Cannot Tell`.
  - Export functionality directly downloading `dev_labels.jsonl`.
- Initial seed gold truths: `eval/gold/dev_labels.jsonl` (28 registry-declared domains seeded).
- Review time estimate: ~1.5 minutes per company (~3.75 hours for the 150 dev cohort).

---

## 3. Starter Pipeline Baseline Execution

The unmodified starter pipeline (`scripts/run_competition_batch.py`) was executed against `eval/sets/dev.txt` with modules `registry,accounting_obligation,registry_live,financials,roles,group,locations,website`:
- **Input Cohort**: 150 companies.
- **Batch Runtime**: 165.9 seconds (~2.75 minutes) across 8 worker threads.
- **HTTP Requests**: 918 requests total (6.12 requests / company).
- **Network Volume**: 17,375,176 bytes (~16.57 MB).
- **Latency Distribution**: Worker p50 = 1.20s, p95 = 1.91s; aggregated envelope p50 = 6.12s, p95 = 12.43s.
- **Third-party Cost**: $0.00.

Raw profiles were converted to contract envelopes using `scripts/convert_starter_to_envelopes.py` and scored with `eval.score`.

---

## 4. Baseline Scores & Error Breakdown

```
==================================================================
               SIGNALPOST EVALUATION SCORE REPORT (PROXY)
==================================================================
 Cohort: 150 companies | Envelopes: 150
------------------------------------------------------------------
 OVERALL PROXY SCORE: 70.00 / 100.00
   - Recall (max 50.0):    29.60
   - Evidence (max 30.0):  30.00
   - Synthesis (max 12.0): 7.20
   - UX (max 8.0):         3.20
------------------------------------------------------------------
 WEBSITE PRECISION: 88.0% (22 correct, 3 wrong)
 EVIDENCE INTEGRITY: 100.0% backed (1445/1445 claims)
 SPAN VALIDITY:      100.0%
 OPERATIONS:         918 requests (6.12/co) | p50=6.12s p95=12.43s
------------------------------------------------------------------
 PER-FAMILY METRICS:
 Family           Coverage %   Claims   Claims/Cov   Proxy Recall
 identity         100.0        300      2.0          0.9000      
 brand            0.0          0        0.0          0.0000      
 accounts         82.7         323      2.6          0.7940      
 accounts_history 0.0          0        0.0          0.0000      
 leadership       100.0        677      4.5          1.0000      
 locations        77.3         120      1.0          0.7813      
 group            0.0          0        0.0          0.0000      
 website          16.7         25       1.0          0.1667      
 company_profiles 0.0          0        0.0          0.0000      
 hiring           0.0          0        0.0          0.0000      
 activity         0.0          0        0.0          0.0000      
==================================================================
```

### Coverage Analysis
- **Declared Registry Websites**: 28 / 150 (18.67%).
- **Websites Passing Identity Gate**: 25 / 150 (16.67%, 89.29% conversion of declared sites). 3 failed to pass or connect.
- **Roles / Leadership**: 150 / 150 (100.0%, 677 claims).
- **Subunits / Locations**: 116 / 150 (77.33%, 120 claims).
- **Annual Accounts / Financials**: 124 / 150 (82.67%, 323 claims across up to 3 years).
- **External Families** (`brand`, `hiring`, `activity`, `company_profiles`, `group`): 0.0% coverage in unmodified starter.

### Website Discrepancies (String Precision Check vs Gold)
3 publications were flagged during strict string match comparison against initial gold truths:
1. `988387657`: Published `https://www.obos.no/naringseiendom`, gold has `https://www.obos.no/bedrift/naringseiendom/` (path redirect alias on valid entity domain).
2. `983923534`: Published `https://hjertebarn.no/`, gold has `https://www.ffhb.no` (association site vs foundation parent domain).
3. `980502155`: Published `https://tidetec.com/`, gold has `https://www.tidetec.no` (international TLD mirror vs national `.no`).

---

## 5. Official Leaderboard Calibration

- **Builderr Challenge Board (1 Oct 2026)**:
  - Unmodified starter score: **42.21** (Recall 12.89, Evidence 18.92, Synthesis 7.20, UX 3.20).
  - Leaderboard best: **45.59** (Recall 17.86, Evidence 18.93, Synthesis 7.20, UX 1.60).
  - Qualification threshold: **65.00+**.
- **Gap to Qualification**: +22.79 points.
- **Primary Levers**:
  1. Website discovery ladder with exact-orgnr proof (+6–10 Recall).
  2. NAV Arbeidsplassen official job feed (+4–6 Recall).
  3. Verified site structured data harvest (+3–5 Recall & Evidence).
  4. Mobile-first interactive static viewer (+3–4 UX).

---

## 6. Acceptance Verification

1. `uv run pytest -q eval`: 9 passed in 0.03s.
2. `uv run --with pytest pytest -q`: 108 passed, 5 subtests passed in 2.65s.
3. `uv run python -m eval.score --envelopes out/baseline-dev-envelopes.jsonl --set dev --output reports/baseline-dev.json`: Score table generated and JSON saved.
4. `docs/BASELINE.md`: Documented real numbers (18.67% registry website presence, 16.67% passing gate).
5. All non-negotiables **N1–N10** preserved.
