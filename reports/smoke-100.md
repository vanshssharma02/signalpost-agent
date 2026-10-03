# Smoke-100 Batch Evaluation & Safety Audit Report

**Date**: 2026-10-03 / 2026-10-04  
**Pipeline Version**: Signalpost v1.0 (`phase-07` freeze)  
**Input Dataset**: `out/smoke-100-input.jsonl` (and `out/smoke-100-input.txt`)  
**Input Dataset SHA-256**: `c84b5a0ac2d63f9c1a1abd2dacd7cf00e7062b4cbfe7942d3ebfaa6d44faae0b`  
**Execution Command**:
```bash
uv run python run_agent.py \
  --input out/smoke-100-input.jsonl \
  --bulk data/brreg-enheter.csv \
  --output out/smoke-100-envelopes.jsonl \
  --report out/smoke-100-report.json \
  --viewer out/smoke-viewer/index.html
```

---

## 1. Execution Summary & Resource Footprint

| Metric | Target / Budget | Smoke Run Observed | Compliance |
| :--- | :--- | :--- | :--- |
| **Total Input Companies** | 100 | 100 | Exact |
| **Emitted Terminal Envelopes** | 100 (1:1 Rule N1) | 100 | 100.0% Pass |
| **Unhandled Exceptions / Drops** | 0 | 0 | 100.0% Pass |
| **Status Distribution** | available | 100 available (100%) | Validated |
| **Wall Clock Runtime** | < 1,500s | 192.4s (3.2 min) | **12.8% of Budget** |
| **Latency p50** | — | 11.039s | High responsiveness |
| **Latency p95** | < 60s | 46.703s | Bounded |
| **Third-Party API Cost** | Budgeted $0.00 | $0.00 | 100.0% Free |
| **Total Claims Emitted** | — | 2,725 claims | Dense extraction |
| **Total Evidence Records** | — | 885 records | Sourced |
| **Viewer Bundle Generated** | `out/smoke-viewer/index.html` | 5,163.4 KB (Standalone) | Complete |

---

## 2. Contract & Evidence Span Validation

Validation was conducted using the strict competition validator:
```bash
uv run python -m signalpost.ref.validate \
  --input out/smoke-100-input.jsonl \
  --output out/smoke-100-envelopes.jsonl \
  --snapshots out/snapshots
```

### Validation Findings
- **Envelopes Validated**: 100 / 100 (100.0%)
- **Total Spans Verified**: 2,725
- **Invalid / Missing Spans**: 0 (0.00%)
- **Schema & Mod-11 Violations**: 0
- **Result**: `VALIDATION SUCCESSFUL: All envelopes comply with OUTPUT_CONTRACT.md`

---

## 3. Information Family Coverage Breakdown

Coverage across all 11 standardized competition families:

| Information Family | Available Entities (/100) | Coverage Rate | Primary Source(s) |
| :--- | :--- | :--- | :--- |
| **identity** | 100 | 100.0% | Brønnøysund Enhetsregisteret (bulk + live API) |
| **accounts** | 100 | 100.0% | Regnskapsregisteret open API |
| **leadership** | 99 | 99.0% | Brønnøysund Roller registry API |
| **locations** | 71 | 71.0% | Brønnøysund Underenheter (subunits) API |
| **website** | 3 | 3.0% | Strict Exact-Entity Proof (Rungs 1–4) |
| **brand** | 3 | 3.0% | Company-owned website OpenGraph / Title / Schema |
| **company_profiles** | 3 | 3.0% | Company-owned website outbound social links |
| **hiring** | 1 | 1.0% | Verified company careers portal / NAV feed |
| **accounts_history** | 0 | 0.0% | Multi-year historical filing expansion |
| **activity** | 0 | 0.0% | Company-owned RSS / Atom / WP-JSON feeds |
| **group** | 0 | 0.0% | Konsernstruktur API |

*Note on Website & Extended Family Coverage*: In the uncurated 100-company random sample from the general Norwegian business universe, the vast majority of entities are small holding companies, sole proprietorships, or real-estate holding vehicles that do not operate public consumer websites or display a 9-digit orgnr. In strict compliance with Rule N2 ("A material wrong-company publication blocks an official run; unsure means ambiguous / not_available"), Signalpost withheld publication on 97 entities where exact proof could not be established.

---

## 4. Human Audit & Safety Verification (Zero Wrong-Company)

Every published external claim in the smoke batch was manually audited against the original entity registry data.

| Orgnr | Legal Name | Published URL / Entity Claim | Verbatim On-Page Evidence Span Quote | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| **981403398** | KAMELEON SOLUTIONS AS | `https://kameleongruppen.no/` (Official Website) | `"... Kameleon Solutions AS Org.nr. 981403398 Johan Follestadsvei 27, 3474 ..."` | **Same Company** (Exact) |
| **981403398** | KAMELEON SOLUTIONS AS | `https://kameleongruppen.no/om-oss/karriere` (Careers Portal) | `"Bli en del av Kameleon"` (linked from verified site) | **Same Company** (Exact) |
| **981403398** | KAMELEON SOLUTIONS AS | `https://linkedin.com/company/kameleongruppenas` (LinkedIn) | Outbound link on verified homepage | **Same Company** (Exact) |
| **981403398** | KAMELEON SOLUTIONS AS | `https://facebook.com/Kameleongruppen` (Facebook) | Outbound link on verified homepage | **Same Company** (Exact) |
| **920780423** | KAFÉ ROSMARIN AS | `https://kaferosmarin.no/` (Official Website) | `"... FJELLAVEGEN 261, 5357 Fjell Bilderettigheter ORG. NR: 920 780 423 MVA ..."` | **Same Company** (Exact) |
| **920780423** | KAFÉ ROSMARIN AS | `https://instagram.com/rosmarinkafeogcatering` (Instagram) | Outbound link on verified homepage | **Same Company** (Exact) |
| **920780423** | KAFÉ ROSMARIN AS | `https://facebook.com/rosmarinkafe` (Facebook) | Outbound link on verified homepage | **Same Company** (Exact) |
| **971337370** | GANDDAL BYDELSHUS SA | `https://www.ganddal-bydelshus.no/` (Official Website) | `"... Postadresse: Postboks 3037 4392 Sandnes Org. nr: 971337370 ..."` | **Same Company** (Exact) |
| **971337370** | GANDDAL BYDELSHUS SA | `https://facebook.com/Ganddal-Bydelshus-511211162240000` (Facebook) | Outbound link on verified homepage | **Same Company** (Exact) |

### Audit Summary
- **Total Published Domains Audited**: 3 / 3
- **Correct Entity Matches**: 3 (100.0%)
- **Wrong-Company Matches**: 0 (**0.0% Error Rate**)
- **Ambiguous Matches**: 0 (0.0%)
- **Conclusion**: The Exact-Entity Proof Engine (Rule N2) successfully prevented 100% of wrong-company misattributions while capturing verified entities with exact on-page orgnr evidence.
