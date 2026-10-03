# Phase 2: Batch Runner & Result Envelope Report

## Executive Summary

Phase 2 hardens the Signalpost batch runner in accordance with `.agents/workflows/02-runner-envelope.md` and Rule **N1**. The runner guarantees that no input row is ever dropped or unhandled regardless of network timeouts, corrupted inputs, or worker failures. All 7 schema discrepancies identified in `BASELINE.md` have been fully resolved. The result envelope now strictly complies with `OUTPUT_CONTRACT.md` and passes the contract validator with 100% span integrity against stored byte snapshots.

---

## 1. Acceptance Criteria Verification

### 1.1 Full Test Suites
```text
$ uv run --with pytest pytest -q
..................................................................... [ 63%]
.......................................                                [100%]
108 passed, 5 subtests passed in 2.63s

$ uv run --with pytest pytest -q eval
.........                                                                [100%]
9 passed in 0.03s
```
All baseline unit tests, envelope guard tests, and fault-injection scenarios pass green.

### 1.2 Full Online Dev Run & Contract Validation
Command executed:
```bash
uv run python run_agent.py -i eval/sets/dev.txt --bulk data/brreg-enheter.csv -o out/dev-envelopes.jsonl --snapshots-dir out/snapshots --workers 16
uv run python -m signalpost.ref.validate --input eval/sets/dev.txt --output out/dev-envelopes.jsonl --snapshots out/snapshots
```

Output:
```json
{
  "passed": true,
  "envelopes": 150,
  "expected": 150,
  "spans_checked": 4132,
  "spans_bad": 0,
  "errors": [],
  "error_count": 0
}
```
- **Inputs Expected**: 150 | **Envelopes Emitted**: 150 (1:1 emission ratio).
- **Spans Checked**: 4,132 verbatim spans checked against stored gzip snapshots in `out/snapshots/`.
- **Bad Spans**: 0 | **Errors**: 0.
- **Terminal Status Breakdown**: 148 `available`, 2 `not_applicable` (insolvent / deleted entities).

### 1.3 Time-Budget Watchdog (`--time-budget 20`)
```bash
uv run python run_agent.py -i eval/sets/dev.txt --bulk data/brreg-enheter.csv -o out/dev-budget-envelopes.jsonl --time-budget 20 --snapshots-dir out/snapshots --workers 16
```
- **Elapsed Runtime**: 17.0 seconds (safely under the 25.0s acceptance limit).
- **Envelopes Emitted**: 150 / 150.
- **Validator**: Passed with 0 errors.

### 1.4 Offline Run (`--offline`)
```bash
uv run python run_agent.py -i eval/sets/dev.txt --bulk data/brreg-enheter.csv -o out/dev-offline-envelopes.jsonl --offline --snapshots-dir out/snapshots
```
- **Elapsed Runtime**: 19.0 seconds (scanning bulk snapshot and producing 150 envelopes with 0 network calls).
- **Validator**: Passed with 0 errors (`spans_checked: 481`, `spans_bad: 0`).

---

## 2. Resolution of 7 Schema Violations

| # | Contract Dimension | Starter Kit State | Phase 2 Implemented State |
|---|---|---|---|
| 1 | **Status & Availability** | `state: "complete"` or `"submission_error"` | Exactly one of the 6 formal terminal states: `available`, `not_available`, `blocked`, `not_applicable`, `ambiguous`, `failed`. `availability` mirrors `status`. |
| 2 | **Atomic Claims (`claims[]`)** | Buried in nested unstructured dictionaries | Deterministic claim keys `sha256(orgnr\|field\|discriminator)[:20]`. Includes `field`, `family`, `value`, `evidence_ids`, `method`, `identity_proof`, `first_observed_at`, `last_verified_at`. |
| 3 | **Immutable Evidence (`evidence[]`)** | Ad-hoc dicts without hashes or spans | Evidence records include `source_url`, `final_url`, `http_status`, `retrieved_at`, `content_sha256`, `snapshot_ref`, `claim_span`, and `source_class`. |
| 4 | **Byte Snapshots Storage** | In-memory or absent | All response payloads saved to `out/snapshots/<sha[:2]>/<sha>.gz` before envelope emission. Verified 100% verbatim substring containment. |
| 5 | **Field States (`field_states{}`)** | Arbitrary `modules{}` mapping | Explicit entry for all 11 families (`identity`, `brand`, `accounts`, `accounts_history`, `leadership`, `locations`, `group`, `website`, `company_profiles`, `hiring`, `activity`) with `availability`, `reason`, `checked_sources`, `claim_ids`. |
| 6 | **Errors & Exception Safety** | Raised unhandled exceptions, crashed batch | Non-fatal error logs in `errors[]` array; Rule N1 catch-all ensures corrupt or missing IDs emit failure envelopes rather than crashing. |
| 7 | **Envelope-level Operations** | Only present at batch report level | `operations{}` in every envelope recording `requests`, `runtime_ms`, and `third_party_cost_usd`. |

---

## 3. Comparative Metric Performance on Dev (150 Cohort)

Scored via `eval.score`:

```text
==================================================================
               SIGNALPOST EVALUATION SCORE REPORT (PROXY)
==================================================================
 Cohort: 150 companies | Envelopes: 150
------------------------------------------------------------------
 OVERALL PROXY SCORE: 73.01 / 100.00  (Baseline Starter: 70.00)
   - Recall (max 50.0):    32.61      (+3.01 gain)
   - Evidence (max 30.0):  30.00      (Maintained 100% integrity)
   - Synthesis (max 12.0): 7.20
   - UX (max 8.0):         3.20
------------------------------------------------------------------
 WEBSITE PRECISION: 88.0% (22 correct, 3 wrong)
 EVIDENCE INTEGRITY: 100.0% backed (4132/4132 claims)
 SPAN VALIDITY:      100.0%
 OPERATIONS:         628 requests (4.19/co) | p50=4.79s p95=10.83s
------------------------------------------------------------------
 PER-FAMILY METRICS:
 Family           Coverage %   Claims   Claims/Cov   Proxy Recall
 identity         100.0        481      3.2          1.0000      
 brand            0.0          0        0.0          0.0000      
 accounts         99.3         2829     19.0         0.9953      
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

Key Improvements:
- **Total Claims**: Increased from **1,445** to **4,132** claims (+186% claim density).
- **Accounts**: Expanded from 323 claims (revenue only) to 2,829 claims across 7 financial metrics with valid `reporting_period` tags.
- **Identity**: Expanded from 300 claims to 481 claims (incorporating registered employees, industry codes, and registered addresses).
- **Latency**: Batch finished in 1m 25s across 16 workers (p50 = 4.80s, p95 = 10.83s per company).
