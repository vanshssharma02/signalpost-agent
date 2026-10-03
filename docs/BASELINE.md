# BASELINE.md — Baseline Starter Performance & Calibration Report

## 1. Executive Summary

This report establishes the verified baseline performance of the unmodified starter pipeline (`norway_company_agent`) on the 150-company `dev` split (`eval/sets/dev.txt`).
Measurements were taken under real network conditions against live Brønnøysund endpoints (`data.brreg.no`) and bulk register snapshot (`data/brreg-enheter.csv`).

Key Findings:
- **Registry Website Present**: 18.67% (28 / 150 companies).
- **Website Passing Starter Gate**: 16.67% (25 / 150 companies, 89.29% of declared websites).
- **Official Roles Coverage**: 100.0% (150 / 150 companies, 677 role claims, avg 4.51/co).
- **Subunits (Locations) Coverage**: 77.33% (116 / 150 companies, 120 claims).
- **Financial Accounts Coverage**: 82.67% (124 / 150 companies, 323 claims, avg 2.60/co).
- **Total Operations**: 918 HTTP requests (6.12 req/co), 17.38 MB transferred in 165.9 seconds across 8 worker threads.
- **Contract Compliance**: The unmodified starter output **fails** `OUTPUT_CONTRACT.md` specifications in 7 major areas (envelope schema, terminal states, atomic claims, immutable evidence, field states, changes, and per-envelope operations).

---

## 2. Starter Dev Benchmark Scores

Evaluated using `eval.score` with gold truth labels on `eval/sets/dev.txt`:

| Rubric Dimension | Max Score | Starter Score (Proxy) | Builderr Board Baseline (1 Oct 2026) | Target for Qualification |
|---|---|---|---|---|
| **Recall & Coverage** | 50.00 | **29.60** | 12.89 | 22.0 – 28.0 |
| **Evidence & Precision** | 30.00 | **30.00** | 18.92 | 23.0 – 27.0 |
| **Synthesis & Narrative** | 12.00 | **7.20** | 7.20 | 9.0 – 11.0 |
| **UX & Presentation** | 8.00 | **3.20** | 3.20 | 6.0 – 7.5 |
| **Total Score** | **100.00** | **70.00** | **42.21** | **65.0+** |

*Note on Proxy vs Leaderboard*: The evaluation harness proxy scores recall over the 11 known families. The starter achieves 29.60 on our proxy primarily from near-complete coverage of the 4 registry-backed families (identity, leadership, accounts, locations). On the official Builderr challenge board with unseen batches and broader external families, the unmodified starter scored **42.21**.

### Per-Family Coverage & Claim Density Breakdown

| Information Family | Companies Covered | Coverage % | Total Claims | Claims / Covered Co | Family Proxy Recall |
|---|---|---|---|---|---|
| `identity` | 150 / 150 | 100.0% | 300 | 2.00 | 0.9000 |
| `leadership` | 150 / 150 | 100.0% | 677 | 4.51 | 1.0000 |
| `accounts` | 124 / 150 | 82.7% | 323 | 2.60 | 0.7940 |
| `locations` | 116 / 150 | 77.3% | 120 | 1.03 | 0.7813 |
| `website` | 25 / 150 | 16.7% | 25 | 1.00 | 0.1667 |
| `accounts_history`| 0 / 150 | 0.0% | 0 | 0.00 | 0.0000 |
| `group` | 0 / 150 | 0.0% | 0 | 0.00 | 0.0000 |
| `brand` | 0 / 150 | 0.0% | 0 | 0.00 | 0.0000 |
| `hiring` | 0 / 150 | 0.0% | 0 | 0.00 | 0.0000 |
| `activity` | 0 / 150 | 0.0% | 0 | 0.00 | 0.0000 |
| `company_profiles`| 0 / 150 | 0.0% | 0 | 0.00 | 0.0000 |

### Precision & Evidence Metrics
- **Website Precision**: 88.0% (22 correct, 3 flagged in strict string comparison against gold: one subdomain/parent discrepancy, one path alias, one `.com` vs `.no` mirror).
- **Claim Evidence Backing**: 100.0% (1,445 / 1,445 claims backed by valid evidence IDs).
- **Span Validity**: 100.0% (1,161 / 1,161 evidence records contain non-empty verifiable text spans).

---

## 3. Discrepancies Between Starter Output and OUTPUT_CONTRACT.md

The unmodified starter script (`scripts/run_competition_batch.py`) emits a legacy envelope that fails the required schema in `OUTPUT_CONTRACT.md`. The table below details every point of non-compliance:

| Schema Field / Requirement | `OUTPUT_CONTRACT.md` Specification | Starter Pipeline Output | Impact / Violation |
|---|---|---|---|
| **Top-level status** | Exactly one of: `available`, `not_available`, `ambiguous`, `not_applicable`, `failed` | `state: "complete"` or `"submission_error"` | Invalid enum; fails automated validation. |
| **Availability field** | Mirror of `status` string | Absent | Missing required top-level field. |
| **Status Reason** | Explicit snake_case reason code (e.g. `verified_claims_present`, `absent_from_registry`) | Absent | Missing diagnostic reason code. |
| **Claims Array (`claims[]`)** | Ordered list of atomic claims with `claim_id` (`sha256(orgnr\|field\|discriminator)`), `field`, `family`, `value`, `evidence_ids`, `method`, `identity_proof` | Absent; claims are buried as raw keys inside nested `profile` dictionary | Non-verifiable claims; cannot verify atomic provenance. |
| **Evidence Array (`evidence[]`)** | Ordered list of immutable evidence objects with `id`, `source_url`, `retrieved_at`, `content_sha256`, `claim_span`, `source_class` | Key-value dict `profile.evidence` mapping module names to ad-hoc status dicts | Missing sha256 hashes, exact claim spans, and source classes. |
| **Field States (`field_states{}`)** | Explicit state per family (`availability`, `reason`, `checked_sources`, `claim_ids`) across all 11 families | Unstructured `modules{}` mapping module names to `{state, retry_count, final_timestamp}` | Violates family-level visibility; ignores untracked families. |
| **Changes Array (`changes[]`)** | List of typed change events (`added`, `confirmed`, `updated`, `retracted`) | Absent | Non-idempotent refresh; cannot track mutations. |
| **Errors Array (`errors[]`)** | Explicit list of non-fatal errors or terminal failure cause | Raises unhandled exceptions on malformed/missing inputs | Violates rule N1; unhandled exceptions kill the batch loop. |
| **Operations (`operations{}`)** | Per-envelope record of `requests`, `runtime_ms`, `third_party_cost_usd` | Absent at envelope level (only logged in batch report) | Cost and latency cannot be audited per organisation. |

---

## 4. Leaderboard Calibration & Historical Anchors

Builderr Competition Leaderboard (as of 1 October 2026):

| Team / System | Total Score | Recall (50) | Evidence (30) | Synthesis (12) | UX (8) |
|---|---|---|---|---|---|
| **Best on Board** | **45.59** | 17.86 | 18.93 | 7.20 | 1.60 |
| **Unmodified Starter** | **42.21** | 12.89 | 18.92 | 7.20 | 3.20 |
| **Qualification Threshold** | **65.00** | — | — | — | — |
| **Signalpost Target** | **60.0 – 73.0** | 22.0 – 28.0 | 23.0 – 27.0 | 9.0 – 11.0 | 6.0 – 7.5 |

### Strategic Gap Analysis & Lever Targets

To advance from the baseline of **42.21** to the qualification target of **65.0+** (+22.79 points), our engineering focus is allocated across four primary levers:

1. **Website Discovery Ladder & Identity Gate (+6 to +10 Recall)**:
   - Only 18.67% of companies declare a website in Brreg.
   - Using email domain parsing from bulk, subunit websites/emails, and transient search candidates with strict organisation-number proof (P1: orgnr in footer/imprint; P2: postal address + role holder match) will expand website coverage from 16.7% to 40%+.
2. **NAV Arbeidsplassen Official Job Feed (+4 to +6 Recall)**:
   - Index the official PAM stilling feed keyed strictly by `employer.orgnr`.
   - Adds verified `hiring` family claims for active employers without scraping.
3. **Structured Site Extraction (+3 to +5 Recall & Evidence)**:
   - Extract JSON-LD (`Organization`, `PostalAddress`), RSS/Atom feeds, WordPress REST APIs, and outbound social profile links for verified company websites.
4. **Interactive Static Viewer (+3 to +4 UX)**:
   - Provide clean, mobile-first static HTML viewer with claim-level evidence popovers, diff comparisons, and download exports, elevating UX from 3.2 to 6.5+.
