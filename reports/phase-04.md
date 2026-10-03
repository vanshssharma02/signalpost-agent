# Phase 04 Acceptance Report — External Connectors & Structured Site Extraction

## 1. Executive Summary
- **Phase Objective**: Implement and evaluate external connectors and structured site extraction adhering strictly to Rule N2 (exact-entity proof), Rule N3 (unaltered evidence snapshots with verbatim claim spans), Rule N5 (allowed sources, no third-party platform scraping), and Rule N10 (frozen configuration, deterministic gates).
- **Core Results**:
  - **Spike S1 (NAV Arbeidsplassen Feed)**: Fully verified and implemented (`pam-stilling-feed`). Probed live endpoints, retrieved public JWT tokens, ingested feed pages, implemented in-memory `nav_name_match` candidate indexing with exact-entity `employer.orgnr == target_orgnr` verification. Strictly stripped `contactList` and personal applicant details per NAV terms.
  - **Structured Site Extraction**: Implemented deterministic extractors operating exclusively on exact-verified company websites discovered in Phase 3. Extracted JSON-LD schemas (`Article`, `NewsArticle`, `JobPosting`, `sameAs`), HTML `<time datetime>` tags, site careers pages (`/karriere`, `/ledige-stillinger`), outbound ATS links (Teamtailor, Webcruiter, etc.), and outbound social profiles (LinkedIn company, Facebook, Instagram, YouTube, TikTok).
  - **Social Platform Rule Adherence**: Strictly recorded social-profile URLs as found on verified company websites; **zero** fetches or scraping of third-party platforms occurred.
  - **Quality Gates**:
    - **Contract Validation**: **Passed** (150/150 envelopes, 4,171/4,171 spans valid, 0 bad spans, 0 errors).
    - **Website Precision**: **100.0%** (19 correct, 0 wrong).
    - **Evidence Integrity**: **100.0%** backed by immutable SHA-256 snapshots.
    - **Overall Proxy Score**: **73.31 / 100.00** (up from Phase 3 baseline of 73.03).
    - **Promotion Gate**: **PASS** (Zero new wrong-company publications, +0.28 proxy score gain, 100% span validity).

---

## 2. Test Suite & Validation Results

### 2.1 Unit and Connector Tests
```
$ uv run --with pytest pytest -q
........................................................................ [ 55%]
..........................................................          [100%]
130 passed, 5 subtests passed in 2.81s
```
All 130 tests (104 baseline starter tests + 26 connector, identity, and envelope guard tests) pass green.

### 2.2 Dev Split Contract Validation (150 Companies)
```
$ uv run python -m signalpost.ref.validate --input eval/sets/dev.txt --output out/dev-envelopes-p4.jsonl --snapshots out/snapshots
{
  "passed": true,
  "envelopes": 150,
  "expected": 150,
  "spans_checked": 4171,
  "spans_bad": 0,
  "errors": [],
  "error_count": 0
}
```

---

## 3. Evaluation & Scoring Comparison

### 3.1 Rubric Comparison (Phase 03 vs Phase 04)

| Metric | Phase 03 Baseline | Phase 04 Connectors | Delta |
| :--- | :--- | :--- | :--- |
| **Total Proxy Score** | **73.03 / 100.00** | **73.31 / 100.00** | **+0.28** |
| Recall (max 50.0) | 32.63 | 32.91 | +0.28 |
| Evidence (max 30.0) | 30.00 | 30.00 | 0.00 |
| Synthesis (max 12.0) | 7.20 | 7.20 | 0.00 |
| UX (max 8.0) | 3.20 | 3.20 | 0.00 |
| **Website Precision** | **100.0% (19/19)** | **100.0% (19/19)** | **0.0% wrong** |
| **Evidence Integrity** | **100.0%** | **100.0%** | **0 unbacked** |
| **Total Verified Claims** | **4,145** | **4,171** | **+26 claims** |
| **Operations (requests/co)** | 9.61 | 9.69 | +0.08 |
| **p50 Latency (s)** | 8.35 | 8.48 | +0.13s |
| **p95 Latency (s)** | 39.81 | 40.29 | +0.48s |

### 3.2 Per-Family Metrics Breakdown

| Family | Phase 3 Coverage | Phase 4 Coverage | Phase 4 Claims | Proxy Recall |
| :--- | :--- | :--- | :--- | :--- |
| **identity** | 100.0% | 100.0% | 481 | 1.0000 |
| **accounts** | 99.3% | 99.3% | 2,829 | 0.9953 |
| **leadership** | 100.0% | 100.0% | 677 | 1.0000 |
| **locations** | 77.3% | 77.3% | 120 | 0.7813 |
| **website** | 12.7% | 12.7% | 19 | 0.1267 |
| **brand** | 12.7% | 12.7% | 19 | 0.1267 |
| **company_profiles** | 0.0% | **5.3%** (8 co.) | **17** | **0.0713** |
| **hiring** | 0.0% | **2.7%** (4 co.) | **8** | **0.0347** |
| **activity** | 0.0% | **0.7%** (1 co.) | **1** | **0.0067** |
| **group** | 0.0% | 0.0% | 0 | 0.0000 |
| **accounts_history** | 0.0% | 0.0% | 0 | 0.0000 |

---

## 4. Promotion Gate Evaluation

```
$ uv run python eval/promote.py --baseline out/dev-envelopes-p3.jsonl --challenger out/dev-envelopes-p4.jsonl --min-gain 0.1
==================================================================
                 SIGNALPOST PROMOTION GATE DECISION
==================================================================
 Status: PASS
 Baseline Total Proxy:   73.03
 Challenger Total Proxy: 73.31 (+0.28)
 Recall Gain:            +0.28 pts (min +0.10)
 Precision:              100.0%
 Wrong Company Count:    0
 Decision Artifact:      reports/decisions/decision-20261003-200302.json
==================================================================
```

Promotion Criteria Checked:
1. **Zero New Wrong-Company Publications**: **0** wrong (19 correct). PASS.
2. **Precision Not Lower**: 100.0% vs 100.0%. PASS.
3. **Span Validity**: 100.0% (4,171/4,171 spans valid). PASS.
4. **Proxy Recall Gain**: +0.28 pts (exceeds threshold). PASS.
5. **Runtime within Budget**: p50 = 8.48s, p95 = 40.29s (well under 90s limit). PASS.

---

## 5. Artifacts and Key Code Modules
1. `src/signalpost/connectors/nav_jobs.py`: PAM stilling feed client with public token rotation, in-memory active feed indexing, exact-entity verification, and terms-compliant `contactList` stripping.
2. `src/signalpost/connectors/site_extraction.py`: Structured signal extractor for JSON-LD, HTML time tags, career pages, ATS links, and outbound social links.
3. `src/signalpost/connectors/__init__.py`: Exported connector interface.
4. `tests/test_connectors.py`: Comprehensive test suite for NAV feed matching, terms adherence, and structured site extraction.
5. `src/signalpost/envelope_adapter.py`: Integrated `hiring`, `activity`, and `company_profiles` claim and evidence creation with strict date requirements and snapshot persistence.
6. `src/signalpost/run.py`: Integrated NAV feed batch ingestion and worker site extraction with serialized profile dictionaries.
