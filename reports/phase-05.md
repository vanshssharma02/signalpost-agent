# Phase 05 Report — Source-Grounded Synthesis & Idempotent Refresh

## 1. Executive Summary
Phase 05 achieves source-grounded deterministic synthesis and idempotent refresh replay capabilities:
- **Deterministic Synthesis Engine (`src/signalpost/synthesis.py`)**: Generates structured, 100% claim-cited profile summaries conforming strictly to the fixed schema (`generator`, `language`, `headline`, `what_it_does`, `business_model`, `size_and_financials`, `leadership_and_structure`, `locations`, `hiring_signal`, `recent_activity`, `what_changed`, `unknowns`, `sentences`).
- **Grounding (Rules N3 & N4)**: 100% of envelopes in the 150-company dev split have valid synthesis. Every factual sentence cites at least one valid `claim_id` present in the same envelope. Total citations across dev: 3,529 with **0 bad/dangling citations**. All summaries strictly respect the **< 250 words** cap (mean: 172 words, max: 193 words).
- **Standardized Unknowns**: Explicitly catalogs missing or unverified fields with real reason codes (e.g., `website: discovery_ladder_exhausted_unverified`, `hiring: none_in_nav_feed_or_site`) alongside checked source names.
- **Idempotent Refresh Engine (`src/signalpost/envelope_adapter.py`, `src/signalpost/ref/claims.py`)**: Enforces stable claim keys (`sha256(orgnr|field|discriminator)[:20]`). Running with `--previous` preserves `first_observed_at`, advances `last_verified_at`, produces **0 duplicate claims**, and emits **0 false change events**.
- **Replay & Idempotency Verification**:
  - Starter fixture replay (`tests/fixtures/refresh-snapshots.json`): `false_positive: 0`, `idempotent_rerun: true`, `qualification_passed: true`.
  - Signalpost multi-module fixture replay (`tests/fixtures/signalpost-refresh-fixtures.json`): `false_positive: 0`, `precision: 1.0`, `recall: 1.0`, `idempotent_rerun: true`, `qualification_passed: true`.
  - Consecutive runs on frozen fixtures: `compare_runs` returned `idempotent: true`, `problems: []`.
- **Score Progression**: Total proxy score reached **78.11 / 100.00** (up from 73.31 in Phase 4), awarding full **12.00 / 12.00** for synthesis.
- **Contract & Guard**: All 150 dev envelopes passed contract validation with 4,171 spans checked and 0 errors.

---

## 2. Synthesis Engine Architecture & Metrics

### Schema Compliance
```json
{
  "generator": "template-v1",
  "language": "en",
  "headline": "SAFE4 SECURITY GROUP AS (AS, org.nr 912569608)",
  "what_it_does": "...",
  "business_model": "...",
  "size_and_financials": "...",
  "leadership_and_structure": "...",
  "locations": "...",
  "hiring_signal": "...",
  "recent_activity": "...",
  "what_changed": "...",
  "unknowns": [{"topic": "...", "why": "...", "checked": [...]}],
  "sentences": [{"id": "s1", "text": "...", "claim_ids": [...]}]
}
```

### Dev Split Synthesis Metrics (150 Companies)
- Total envelopes: 150
- Compliant synthesis objects: 150 (100.0%)
- Total sentences: 2,155
- Total claim citations: 3,529
- Invalid / dangling citations: 0 (100.0% citation validity)
- Word count distribution:
  - Minimum: 104 words
  - Median: 174 words
  - Mean: 172.4 words
  - Maximum: 193 words (strictly under 250 words cap)

---

## 3. Representative Synthesis Examples

### Example 1: Rich Entity (AS with 46 claims)
- **Organisation Number**: `912569608` (`SAFE4 SECURITY GROUP AS`)
- **Word Count**: 188 words
- **Claim Citations**: 29 citations (100% valid)
- **Unknowns**: 3 (accounts_history, group, hiring)
```text
Headline: SAFE4 SECURITY GROUP AS (AS, org.nr 912569608)
What it does: SAFE4 SECURITY GROUP AS is classified under NACE code 80.090 (unspecified). The company operates its verified website at https://www.safe4.com/. It operates publicly under the brand name 'Safe4 Security Group', according to its website.
Business model: Operates as a registered AS entity within the commercial sector.
Financials: For fiscal year 2025, SAFE4 SECURITY GROUP AS reported revenue of 123,621,771 NOK and an operating result of -29,284,425 NOK. Net result was -31,705,394 NOK, with total assets of 131,269,890 NOK and equity of 70,257,385 NOK. The company was loss-making in 2025. Revenue contracted by -36.4% year-over-year from 2024 (derived: YoY revenue change). Operating margin was -23.7% (derived: operating result / revenue).
Leadership: The board of directors is chaired by Arvid Engebretsen. Daily operations are led by general manager Sjur Jensen Bay. The entity has 15 registered role position(s) in the register of business enterprises. No corporate group hierarchy or parent company is registered.
Locations: The entity maintains 1 registered operating subunit(s) across Norway.
Hiring: No active job postings were found in the NAV feed or on verified site pages.
Recent activity: Published company announcement '13. august 2025' on 2025-08-13 (company-owned publication).
What changed: First observation on 2026-10-03; no earlier snapshot recorded.
```

### Example 2: Sparse Entity (AS with 10 claims, recently registered / no filings)
- **Organisation Number**: `835606252` (`SAHO AS`)
- **Word Count**: 115 words
- **Claim Citations**: 15 citations (100% valid)
- **Unknowns**: 7 (brand, accounts_history, group, website, company_profiles, hiring, activity)
```text
Headline: SAHO AS (AS, org.nr 835606252)
What it does: SAHO AS is classified under NACE code 00.000 (unspecified).
Business model: Operates as a registered AS entity within the commercial sector.
Financials: Net result was -30 NOK, with total assets of 29,970 NOK and equity of 29,970 NOK. The company was loss-making in 2025.
Leadership: The board of directors is chaired by June Sagli Holte. The entity has 1 registered role position(s) in the register of business enterprises. No corporate group hierarchy or parent company is registered.
Locations: The entity maintains 1 registered operating subunit(s) across Norway.
Hiring: No active job postings were found in the NAV feed or on verified site pages.
Recent activity: No recent news items were detected on verified company sources.
What changed: First observation on 2026-10-03; no earlier snapshot recorded.
```

### Example 3: Verified Company Site
- **Organisation Number**: `813055082` (`LPG AS`)
- **Word Count**: 183 words
- **Claim Citations**: 26 citations (100% valid)
- **Unknowns**: 5
```text
Headline: LPG AS (AS, org.nr 813055082)
What it does: LPG AS is classified under NACE code 46.490 (unspecified). The company operates its verified website at https://golfpremier.no/kontakt-oss. It operates publicly under the brand name 'Golfpremier.no', according to its website.
Business model: Operates as a registered AS entity within the commercial sector.
Financials: For fiscal year 2025, LPG AS reported revenue of 2,061,891 NOK and an operating result of -23,458 NOK. Net result was -17,669 NOK, with total assets of 350,826 NOK and equity of 143,680 NOK. The company was loss-making in 2025. Revenue contracted by -20.0% year-over-year from 2024 (derived: YoY revenue change). Operating margin was -1.1% (derived: operating result / revenue).
Leadership: The board of directors is chaired by Raymond Leon Dolata. Daily operations are led by general manager Raymond Leon Dolata. The entity has 3 registered role position(s) in the register of business enterprises. No corporate group hierarchy or parent company is registered.
Locations: The entity maintains 1 registered operating subunit(s) across Norway.
Hiring: No active job postings were found in the NAV feed or on verified site pages.
Recent activity: No recent news items were detected on verified company sources.
What changed: First observation on 2026-10-03; no earlier snapshot recorded.
```

### Example 4: ENK (Enkeltpersonforetak Sole Proprietorship)
- **Organisation Number**: `988613304` (`RANDI THUE`)
- **Word Count**: 138 words
- **Claim Citations**: 20 citations (100% valid)
- **Unknowns**: 7
```text
Headline: RANDI THUE (ENK, org.nr 988613304)
What it does: RANDI THUE is classified under NACE code 69.202 (unspecified).
Business model: Operates as a registered ENK entity within the commercial sector.
Financials: For fiscal year 2025, RANDI THUE reported revenue of 839,980 NOK and an operating result of 739,590 NOK. Net result was 750,261 NOK, with total assets of 441,539 NOK and equity of 247,601 NOK. Revenue remained stable year-over-year from 2024 (derived: YoY revenue change within 10%). Operating margin was 88.0% (derived: operating result / revenue).
Leadership: The entity has 2 registered role position(s) in the register of business enterprises. No corporate group hierarchy or parent company is registered.
Locations: The entity maintains 1 registered operating subunit(s) across Norway.
Hiring: No active job postings were found in the NAV feed or on verified site pages.
Recent activity: No recent news items were detected on verified company sources.
What changed: First observation on 2026-10-03; no earlier snapshot recorded.
```

### Example 5: Hiring Signal Entity
- **Organisation Number**: `923352333` (`XOURCE GROUP AS`)
- **Word Count**: 171 words
- **Claim Citations**: 24 citations (100% valid)
- **Unknowns**: 3
```text
Headline: XOURCE GROUP AS (AS, org.nr 923352333)
What it does: XOURCE GROUP AS is classified under NACE code 70.200 (unspecified). The company operates its verified website at https://www.xource.no/. It operates publicly under the brand name 'Xource Group AS', according to its website.
Business model: Operates as a registered AS entity within the commercial sector.
Financials: For fiscal year 2025, XOURCE GROUP AS reported revenue of 16,000 NOK and an operating result of 9,422 NOK. Net result was 318 NOK, with total assets of 368,364 NOK and equity of 352,681 NOK. Revenue contracted by -99.2% year-over-year from 2024 (derived: YoY revenue change). Operating margin was 58.9% (derived: operating result / revenue).
Leadership: The board of directors is chaired by Waleed Aftab. Daily operations are led by general manager Waleed Aftab. The entity has 2 registered role position(s) in the register of business enterprises. No corporate group hierarchy or parent company is registered.
Locations: The entity maintains 1 registered operating subunit(s) across Norway.
Hiring: Maintains a verified careers portal at https://www.xource.no/karriere.html.
Recent activity: No recent news items were detected on verified company sources.
What changed: First observation on 2026-10-03; no earlier snapshot recorded.
```

---

## 4. Refresh Replay & Idempotency Verification

### 4.1 Starter Refresh Fixture Replay
```bash
uv run python scripts/run_refresh_replay.py --manifest tests/fixtures/refresh-snapshots.json --output out/refresh-test.json
```
**Output**:
```json
{
  "corpus": "evaluator-owned deterministic old/new source snapshot fixture",
  "profiles": 1,
  "modules": ["financials", "registry_live"],
  "old_requests": 2,
  "new_requests": 2,
  "expected_changes": 2,
  "observed_changes": 2,
  "true_positive": 2,
  "false_positive": 0,
  "false_negative": 0,
  "precision": 1.0,
  "recall": 1.0,
  "evidence_complete": true,
  "idempotent_rerun": true,
  "qualification_passed": true
}
```

### 4.2 Signalpost Multi-Module Fixture Replay
```bash
uv run python scripts/run_refresh_replay.py --manifest tests/fixtures/signalpost-refresh-fixtures.json --output out/signalpost-refresh-test.json
```
**Output**:
```json
{
  "corpus": "signalpost-pipeline multi-module refresh replay fixture",
  "profiles": 1,
  "modules": ["financials", "locations", "registry_live", "roles"],
  "old_requests": 4,
  "new_requests": 4,
  "expected_changes": 3,
  "observed_changes": 3,
  "true_positive": 3,
  "false_positive": 0,
  "false_negative": 0,
  "precision": 1.0,
  "recall": 1.0,
  "evidence_complete": true,
  "idempotent_rerun": true,
  "qualification_passed": true
}
```

### 4.3 Consecutive Frozen Dev Runs (`compare_runs`)
- **Run 1**: `uv run python run_agent.py --input eval/sets/dev.txt --bulk data/brreg-enheter.csv --output out/dev-envelopes-p5-offline1.jsonl --report out/dev-report-p5-offline1.json --offline`
- **Run 2**: `uv run python run_agent.py --input eval/sets/dev.txt --bulk data/brreg-enheter.csv --output out/dev-envelopes-p5-offline2.jsonl --report out/dev-report-p5-offline2.json --previous out/dev-envelopes-p5-offline1.jsonl --offline`
- **Validator**:
```bash
uv run python -c "from signalpost.ref.validate import compare_runs; import json, pathlib; a = [json.loads(l) for l in pathlib.Path('out/dev-envelopes-p5-offline1.jsonl').read_text('utf-8').splitlines()]; b = [json.loads(l) for l in pathlib.Path('out/dev-envelopes-p5-offline2.jsonl').read_text('utf-8').splitlines()]; print(json.dumps(compare_runs(a, b), indent=2))"
```
**Result**:
```json
{
  "idempotent": true,
  "problems": []
}
```
Zero false change events, identical claim IDs and values, and `first_observed_at` preserved.

---

## 5. Evaluation Score & Promotion Gate

### Score Report (`reports/synthesis-dev.json`)
```text
==================================================================
               SIGNALPOST EVALUATION SCORE REPORT (PROXY)
==================================================================
 Cohort: 150 companies | Envelopes: 150
------------------------------------------------------------------
 OVERALL PROXY SCORE: 78.11 / 100.00
   - Recall (max 50.0):    32.91
   - Evidence (max 30.0):  30.00
   - Synthesis (max 12.0): 12.00
   - UX (max 8.0):         3.20
------------------------------------------------------------------
 WEBSITE PRECISION: 100.0% (19 correct, 0 wrong)
 EVIDENCE INTEGRITY: 100.0% backed (4171/4171 claims)
 SPAN VALIDITY:      100.0%
 OPERATIONS:         1456 requests (9.71/co) | p50=8.97s p95=37.74s
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
 company_profiles 5.3          17       2.1          0.0713      
 hiring           2.7          8        2.0          0.0347      
 activity         0.7          1        1.0          0.0067      
==================================================================
```

### Promotion Gate Decision
```text
==================================================================
                 SIGNALPOST PROMOTION GATE DECISION
==================================================================
 Status: PASS
 Baseline Total Proxy:   73.31
 Challenger Total Proxy: 78.11 (+4.80)
 Recall Gain:            +0.00 pts (min +0.00)
 Precision:              100.0%
 Wrong Company Count:    0
 Decision Artifact:      reports/decisions/decision-20261003-205322.json
==================================================================
```

---

## 6. Items Skipped and Rationale

| Workflow Item | Status | Rationale |
|---|---|---|
| **A.2 Optional LLM rewriter** | Skipped | Marked explicitly as an "experiment, off by default, `--no-llm` always wins" in Workflow /05. Rule N4 and deterministic-first mandate prioritize zero-hallucination, zero-cost, zero-latency execution. The deterministic composer already scores 12.00 / 12.00 with 100% citation validity and 0 bad spans. |

---

## 7. Acceptance Checklist
- [x] Full unit test suite passes: `136 passed, 5 subtests passed in 2.77s`.
- [x] Starter refresh replay passes with `false_positive: 0` and `idempotent_rerun: true`.
- [x] Project refresh replay passes with `false_positive: 0` and `idempotent_rerun: true`.
- [x] 100% of envelopes have synthesis passing schema and citation checks.
- [x] 5 representative examples documented with word counts (< 250 words).
- [x] Two consecutive dev runs on frozen fixtures confirm `compare_runs` `idempotent: true` and `problems: []`.
- [x] Contract validator passes 150/150 with 0 errors.
- [x] Git tag `phase-05-complete` and `phase5`.
