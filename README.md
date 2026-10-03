# Signalpost — Norwegian Company Intelligence Agent

## Judge Guide

### 1. What This Is
Signalpost is an autonomous company research agent for Norwegian legal entities (scoring v2, 100 pts). It inputs 9-digit organisation numbers, anchors identity solely on Brønnøysund registry keys, extracts verified claims with immutable content-hash snapshots and verbatim source quotes, and emits exactly ONE contract-compliant envelope per company.

### 2. 3-Command Run
```bash
# 1. Run evaluation batch (150 companies)
uv run python run_agent.py --input eval/sets/dev.txt --bulk data/brreg-enheter.csv --output out/envelopes.jsonl

# 2. Validate strict contract compliance & evidence spans
uv run python -m signalpost.ref.validate --input eval/sets/dev.txt --output out/envelopes.jsonl --snapshots out/snapshots

# 3. Build static, mobile-first viewer & score run
uv run python scripts/build_viewer.py --input out/envelopes.jsonl --output out/viewer/index.html
uv run python eval/score.py --envelopes out/envelopes.jsonl --gold eval/gold/dev_labels.jsonl --viewer out/viewer/index.html
```

### 3. Where the Viewer Is
- **Standalone Offline File**: `out/viewer/index.html` (zero external dependencies, open directly via `file://`).
- **Static Multi-page Site**: `site/index.html` and pre-rendered serverless company pages under `site/c/<orgnr>.html`.
- **Features**: Real-time directory search/filters, synthesis narrative with clickable claim citations, evidence popovers, 3-way company compare, unknowns inspector, and raw JSON envelope viewer. Fully responsive across desktop (1280px) and mobile (360px+), WCAG 2.1 AA compliant.

### 4. How to Read a Claim
Every published claim in `claims[]` adheres to Rule N3:
- `claim_id`: deterministic `sha256(orgnr|field|discriminator)[:20]`.
- `availability`: `available`, `ambiguous`, `not_available`, `not_applicable`, `failed` (never color alone).
- `evidence_ids`: pointers into `evidence[]`, which contains `source_url`, `retrieved_at`, `content_sha256` of an immutable snapshot, and an exact verbatim `claim_span` present in the snapshot. Missing values are never fabricated as `0` or `""`.

### 5. Known Limitations
- Respects strict robot terms and platform prohibitions: zero scraping of LinkedIn, Facebook, Instagram, Google/Bing result pages, or 1881.
- Social profile links are recorded only when declared on a verified company website.
- NAV job posting ingestion requires `NAV_FEED_TOKEN` for full live coverage; gracefully falls back to company career portals.

---

## Baseline Starter Archive


## What it already does

- reads a batch of Norwegian organisation numbers;
- anchors identity in the Brønnøysund bulk registry;
- fetches official financials, roles, group links and registered workplaces;
- visits the registry-listed website and rejects weak entity matches;
- emits one terminal JSONL envelope per input;
- records sources, retrieval times, content hashes, request counts and latency;
- supports checkpoint/resume and a deterministic refresh replay;
- includes examples for external-footprint discovery and an evidence-bounded research agent.

## First run: try one saved example

Requires Python 3.12+. Open a terminal inside this extracted folder.

Before downloading company data or running a full crawl, try the bundled public
sample. It uses saved responses: no API key, registry download or live web requests.

```bash
python3 scripts/run_refresh_replay.py \
  --manifest tests/fixtures/refresh-snapshots.json \
  --output out/refresh-demo.json
```

Open `out/refresh-demo.json`. The `events` list shows what changed between two
versions of one company profile and the source evidence for each change. The sample
should find two expected changes, no false changes, and no extra changes when the
same data is checked again.

The report's `qualification_passed` field refers only to this public sample check.
It does not qualify an entry for the competition or prove live information coverage.
The printed request counts are reads from saved responses, not network calls.

## Next: research live companies

Requires Python 3.12+ and `uv`. This step downloads data and makes live requests.
The manifest selector can create a local test batch of any size. Use 100 rows for the recommended smoke test before trying a larger batch.

```bash
uv sync
curl -L 'https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv' -o brreg-enheter.csv
curl -L 'https://builderr.ai/signalpost-company-universe-2025.jsonl.gz' -o signalpost-universe.jsonl.gz

uv run python select_entry_batch.py \
  --universe signalpost-universe.jsonl.gz \
  --count 100 \
  --output entry-companies.jsonl

# Use the 100-company batch as your smoke test.
cp entry-companies.jsonl smoke-companies.jsonl

uv run python scripts/run_competition_batch.py \
  --organisations smoke-companies.jsonl \
  --bulk brreg-enheter.csv \
  --profiles-output out/smoke-profiles.jsonl \
  --output out/smoke-envelopes.jsonl \
  --report out/smoke-report.json \
  --run-id smoke-001 \
  --expected-count 100

# You may test at larger scale locally, but Builderr supplies the official batch for scoring.
uv run python scripts/run_competition_batch.py \
  --organisations entry-companies.jsonl \
  --bulk brreg-enheter.csv \
  --profiles-output out/profiles.jsonl \
  --output out/envelopes.jsonl \
  --report out/run-report.json \
  --run-id local-001 \
  --expected-count 1000

uv run --with pytest pytest -q
```

The published archive was clean-room verified on August 24, 2026: 104 tests and 5 subtests passed, followed by a one-company live BRREG smoke run with one terminal envelope, five requests and zero silent drops.

Increase `--count` and `--expected-count` together for a larger local test. The 100-row smoke test above is practice only; Builderr supplies the companies for every official run.

## The improvement loop

1. Treat the organisation number as the anchor.
2. Generate site/profile candidates from official data, the company site, lawful search providers and named people.
3. Save every candidate and the evidence for or against it.
4. Publish only exact-entity matches. Parent, brand, franchise and similarly named companies are not exact.
5. Crawl static HTML first. Escalate to a browser only when a deterministic completeness check fails.
6. Measure added supported coverage, wrong-company claims, runtime, requests and cost.
7. Promote a strategy only when it improves coverage without weakening the accuracy gates.
8. Freeze strategies and thresholds before the daily evaluation run.

The strongest differentiator is external evidence that remains exact and auditable: official company pages, company-owned profiles, jobs, dated activity, ratings/reviews and permitted public signals. Do not trade accuracy for volume.

## Important source rule

Open-source code does not grant permission to scrape a platform. Follow each source's terms, robots policy, rate limits and licence. LinkedIn, Meta and Indeed are useful identity/discovery targets, but direct automated collection may be restricted. Use permitted APIs, licensed providers, company-owned outbound links, or return `blocked`/`not_available`.

Read `docs/competition-control-loop.md`, `docs/external-connectors.md` and the public source policy before adding connectors.

## Submission contract

Submit a repository with:

- a 100-company smoke-test result or report;
- one documented command that accepts a JSONL batch of organisation numbers;
- exactly one terminal envelope per input;
- pinned dependencies and reproducible setup;
- a previous-snapshot input and material-change output;
- a machine-readable run report with runtime, request count and third-party cost;
- declared models, APIs, licences and source-rights assumptions.

Email the repository URL, run command, models/APIs and expected cost per 100-company run to `submit@builderr.ai`.
