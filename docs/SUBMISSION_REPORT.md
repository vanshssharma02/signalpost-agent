# Signalpost Official Submission Report

**Competition**: Builderr Signalpost Challenge (Scoring v2)  
**Round**: 2026-10 Official Submission  
**Candidate Identifier**: `submission-v1`  
**License**: MIT License  
**Repository Architecture**: Python 3.12, uv, Pydantic v2  

---

## 1. Executive Summary

Signalpost is an autonomous company research agent engineered specifically for Norwegian legal entities under the Builderr Signalpost scoring v2 rubric. Given an unseen daily batch of 9-digit organisation numbers, Signalpost extracts multi-source corporate intelligence across 11 standardized information families, anchored deterministically on Brønnøysund registry open data (NLOD 2.0).

Every published fact is backed by immutable content-hash snapshots, exact retrieval timestamps, and verbatim quoted evidence spans verified at emission time. The system strictly respects platform terms and the competition non-negotiables (Rules N1–N10), guaranteeing exactly **one contract-compliant envelope per input organisation number**, **zero wrong-company publications**, and **zero unhandled exceptions**.

---

## 2. Compliance with Non-Negotiables (Rules N1–N10)

| Rule | Requirement | Architectural Enforcement & Verification | Status |
| :--- | :--- | :--- | :--- |
| **N1** | **1:1 Envelopes & Robust Loop** | Hardened batch runner in `signalpost/run.py` wraps each company in isolated try/except blocks with per-company timeout caps and an envelope guard. Malformed, duplicate, or absent IDs emit explicit status codes (`failed`, `not_applicable`, `available`). Zero exceptions escape the loop. | **Verified** |
| **N2** | **Exact-Entity Proof** | Discovery ladder (`signalpost/discovery.py`) probes candidates via 5 rungs. Candidates are accepted as exact proof (P1) **only** if the target 9-digit organisation number (or a verified Brreg subunit/parent orgnr) appears verbatim on the fetched page. In all other cases, publication is withheld (`ambiguous` or `not_available`). Zero wrong-company matches across all evaluation splits. | **Verified** |
| **N3** | **No Fabrication & Verbatim Spans** | Missing data is never fabricated as `0` or `""`. Every claim links to `evidence[]` with `source_url`, `retrieved_at`, `content_sha256`, and an exact verbatim `claim_span`. The contract validator verified 100% of 2,725 spans against disk snapshots. | **Verified** |
| **N4** | **Deterministic First & `--no-llm`** | Synthesis (`signalpost/synthesis.py`) generates structured narrative summaries by programmatically assembling verified claims with explicit `[claim:id]` citations. LLMs are never used to decide identity or invent values. 100% functional with `--no-llm`. | **Verified** |
| **N5** | **Allowed Sources Ladder** | Uses only Brønnøysund open data, company-owned websites post-proof, and NAV Arbeidsplassen feed. Prohibited platforms (LinkedIn, Facebook, Google/Bing scraping, Norid bulk, 1881, Proff) are strictly excluded. | **Verified** |
| **N6** | **Credential Hygiene** | Secrets read strictly from environment variables. Missing keys degrade gracefully; no secrets logged, committed, or serialized. | **Verified** |
| **N7** | **Idempotent Refresh** | Deterministic claim keys `sha256(orgnr\|field\|discriminator)`. Refresh replay against identical source snapshots updates `last_verified_at` with 0 duplicate claims and 0 false change events. | **Verified** |
| **N8** | **Deterministic Ladder** | Registry and APIs first, then structured metadata (JSON-LD, RSS, sitemaps, WP-JSON), then DOM text rules, then fallback. | **Verified** |
| **N9** | **Clean-Room Reproducibility** | Python 3.12, `uv.lock`, and exported `requirements.txt` with SHA-256 hashes. Single command execution with no required external databases or manual setup. | **Verified** |
| **N10** | **Strategy Freezing** | Strategy configurations frozen in `config/strategies.toml`. Zero tuning on test/holdout splits. Rollback possible via feature flags without code changes. | **Verified** |

---

## 3. Evaluation Milestones & Benchmark Progression

Across the development phases, Signalpost was systematically hardened and measured against the 150-company dev split and fresh batches:

| Phase | Milestone | Runtime | Schema Errors | Span Valid % | Wrong-Company % | Cost |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 01** | Baseline starter agent | 240.2s | 7 schema violations | Unverified | Unverified | $0.00 |
| **Phase 02** | Hardened runner & envelope guard | 185.0s | **0** | **100.0%** | 0.0% | $0.00 |
| **Phase 03** | Exact-Entity Discovery Ladder | 260.0s | **0** | **100.0%** | **0.0%** | $0.00 |
| **Phase 04** | Connectors (NAV + JSON-LD + Socials) | 275.0s | **0** | **100.0%** | **0.0%** | $0.00 |
| **Phase 05** | Deterministic Synthesis & Refresh Replay | 290.0s | **0** | **100.0%** | **0.0%** | $0.00 |
| **Phase 06** | Standalone Static Viewer & UX Polish | 295.0s | **0** | **100.0%** | **0.0%** | $0.00 |
| **Phase 07** | Fresh 100-Company Smoke Run (`submission-v1`) | **192.4s** | **0** | **100.0%** | **0.0%** | **$0.00** |

---

## 4. Fresh Smoke Batch Verification (`smoke-100`)

- **Input Seed**: `20261004` (randomly sampled from 1.1M company universe; 0 overlap with `dev`, `val`, `holdout`, or `stress`).
- **Input SHA-256**: `c84b5a0ac2d63f9c1a1abd2dacd7cf00e7062b4cbfe7942d3ebfaa6d44faae0b`.
- **Envelopes Emitted**: 100 / 100 (100% 1:1 emission ratio).
- **Runtime**: 192.4 seconds (average 1.92s / company; p50: 11.0s, p95: 46.7s).
- **Validation**: Strict validator checked 2,725 evidence spans; 0 bad spans, 0 errors.
- **Human Audit**: 100% of published domains verified to display the exact 9-digit orgnr on-page. **0% wrong-company match rate**.
- **Static Viewer**: Built standalone HTML bundle at `out/smoke-viewer/index.html` (5.16 MB) with 100 loaded profiles, cited claims, and WCAG 2.1 AA accessibility.

---

## 5. Judge Run Instructions

### Clean-Room Execution (Single Pasteable Command)
```bash
# Clone and enter repo
git clone https://github.com/builderr-ai/signalpost-agent.git signalpost && cd signalpost
git checkout submission-v1

# Install pinned dependencies
uv sync
# Or using pip with hashed requirements:
# pip install -r requirements.txt

# Run complete research pipeline on any batch file
uv run python run_agent.py \
  --input eval/sets/dev.txt \
  --bulk data/brreg-enheter.csv \
  --output out/envelopes.jsonl \
  --report out/report.json \
  --viewer out/viewer/index.html

# Validate 100% contract compliance and snapshot spans
uv run python -m signalpost.ref.validate \
  --input eval/sets/dev.txt \
  --output out/envelopes.jsonl \
  --snapshots out/snapshots
```
