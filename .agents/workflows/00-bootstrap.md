---
description: Phase 0 - set up the repo, prove the Builderr starter works, remove forbidden connectors, pin the environment. Run first.
---

# /00-bootstrap  (about 1-2 hours)

Goal: a clean git repo containing the Builderr starter kit plus this pack, all starter tests green, data downloaded and checked, forbidden connectors removed. No new features in this phase.

Before anything else read AGENTS.md and docs/MASTER_PLAN.md completely. Then write one line per rule N1-N10 into docs/DECISIONS.md under "Rules as I understand them". If a rule is unclear, ask the human instead of guessing.

## Steps

1. Layout. The repository root must contain the unpacked Builderr starter (src/norway_company_agent, scripts, tests, docs, data, pyproject.toml, uv.lock, README.md, OUTPUT_CONTRACT.md, select_entry_batch.py) AND the pack (AGENTS.md, .agents/, reference/, config/, docs/MASTER_PLAN.md, docs/KNOWN_STARTER_TRAPS.md, docs/BUILDERR_EMAIL.md). If the starter is missing, ask the human for signalpost-starter-kit.tar.gz (https://builderr.ai/signalpost-starter-kit.tar.gz). Ignore macOS "._*" files: `find . -name '._*' -delete`.
2. Git. `git init`, create .gitignore (out/, snapshots/, state/, .env, .venv/, data/*.csv, data/*.gz, data/*.jsonl, site/ only if generated, __pycache__/, *.partial), create .env.example listing NAV_FEED_TOKEN, SEARCH_API_KEY, LLM_API_KEY, SIGNALPOST_TIME_BUDGET_S (all optional, empty). Never create a real .env that is committed. First commit: "phase 0: starter + pack".
3. Environment. Python 3.12 required. Install uv if missing (https://docs.astral.sh/uv/). `uv sync`. Record `python --version` and `uv --version` in docs/DECISIONS.md.
4. Prove the starter. Run and paste real output:
   - `uv run --with pytest pytest -q`  -> expect "104 passed, 5 subtests passed".
   - `uv run python scripts/run_refresh_replay.py --manifest tests/fixtures/refresh-snapshots.json --output out/refresh-demo.json` -> expect observed_changes 2, false_positive 0, idempotent_rerun true.
   - `uv run --with pytest pytest -q reference/tests` (set PYTHONPATH=reference) -> expect 17 passed. These are the pack's own tests.
   If a number differs, stop and report; do not edit tests to make them pass.
5. Data. Download into data/ (gitignored):
   - `curl -L 'https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv' -o data/brreg-enheter.csv` (large; if the response is gzip, detect with `file` and decompress). Record size, row count, header line, download time in docs/DECISIONS.md.
   - `curl -L 'https://builderr.ai/signalpost-company-universe-2025.jsonl.gz' -o data/signalpost-universe.jsonl.gz`. Verify sha256 of the archive equals 1c89710e5b01f8617e86d09fbdff4a52f2f8dbbba297e74f7164b5984f5a0384 and sha256 of the decompressed bytes equals b82d6a3e7231d1759a958c282bc4366b80ec2fab8095053d8ed7fa9cd01bc838. A mismatch is a warning to report, not a blocker. Count lines (expect 411,160) and print 3 sample rows.
6. Probe the live registry (this is where the plan's assumptions meet reality). For 5 organisation numbers taken from the universe file, call https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr} and save raw JSON under docs/probes/. Write down in docs/DECISIONS.md which of these keys actually exist: hjemmeside, epostadresse, telefon, mobil, vedtektsfestetFormaal, aktivitet, naeringskode1/2/3, antallAnsatte, forretningsadresse, postadresse, institusjonellSektorkode, registreringsdatoEnhetsregisteret, stiftelsesdato, konkurs, underAvvikling, overordnetEnhet. Also check whether the same fields are columns of the bulk CSV. Also call /underenheter?overordnetEnhet={orgnr} for 5 companies and note whether subunits carry hjemmeside or epostadresse. Also call /roller, /konsernstruktur, and https://data.brreg.no/regnskapsregisteret/regnskap/{orgnr}; note how many accounting years the last one returns. Later phases depend on these answers; never assume them.
7. Remove forbidden or out-of-policy connectors from the submission tree (they scrape or depend on restricted platforms or are not needed): scripts/run_linkedin_guest_experiment.py, scripts/run_linkedin_guest_jobs_connector.py, scripts/discover_linkedin_company_profiles.py, scripts/run_google_news_rss_connector.py, scripts/run_youtube_search_connector.py, scripts/normalize_google_maps_results.py, scripts/run_fagfolkguiden_reviews_connector.py, scripts/run_sentiment_model.py, src/norway_company_agent/sentiment.py, the `sentiment` optional dependency group, and scripts/score_competition_v3.py (it scores an obsolete rubric). Delete the tests that exist only for those files, keep every test for registry, official, website, identity, refresh, batch, snapshots, sampling. The full suite must stay green; record the new test count and the list of removed files in docs/DECISIONS.md with the reason "source policy: restricted platforms / obsolete".
8. Pin. `uv lock` if needed; `uv export --format requirements-txt --no-dev --hashes -o requirements.txt`. Do not install anything that is not pinned.
9. Copy `reference/signalpost_ref` to `src/signalpost/ref/` (create src/signalpost/__init__.py), move its tests to tests/ref/, fix imports, make `pytest -q` run both starter and ref tests green. Keep reference/ as read-only documentation of intent; the code of record is now src/signalpost/ref.
10. Commit "phase 0 complete". Tag `phase0`.

## Acceptance (paste real output of all of these)
- `git status` clean, `git log --oneline` shows two commits.
- `uv run pytest -q` all green (state the count).
- docs/DECISIONS.md contains: rules N1-N10, tool versions, data checksums result, the registry key probe table, the removed-file list.
- No file under src/ or scripts/ mentions linkedin, facebook graph, glassdoor, indeed, finn.no scraping or google news (grep proves it; docs may mention them as forbidden).

Stop here and report. Do not start /01 until the human says so.
