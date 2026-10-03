---
description: Phase 2 - the crash-proof batch runner, the superset result envelope, the time-budget scheduler and fault-injection tests.
---

# /02-runner-envelope  (about 1 day)

Goal: a runner that can NEVER lose a row, whatever the input, network or clock does, and that emits the contract envelope for the official registry facts (accounts, roles, subunits, group). External discovery comes in /03-/04. A crash, a timeout or one missing row scores ZERO for that daily batch, so this phase is the most important insurance in the project.

## Facts that shape the design
- Builderr supplies organisation numbers, the cutoff, an output contract, a frozen registry snapshot, a fixed time and resource budget and an unknown CLI. The exact arguments are an open question (docs/BUILDERR_EMAIL.md). So accept many spellings and never require optional flags.
- The unmodified starter has traps (docs/KNOWN_STARTER_TRAPS.md): `--expected-count` defaults to 100 and aborts a 1,000-row batch; duplicate or malformed ids raise; an id missing from the bulk snapshot raises; one exception in a worker kills the whole run; envelopes are written only at the very end; its states (complete, source_error, ...) are not the six required states. Fix all of them.

## Deliverables

1. Entry points (both must work): `python run_agent.py ...` at repo root and `python -m signalpost.run ...`. Flags (all optional except an input): `--organisations|--input|-i FILE` (txt, json, jsonl, strings or objects; use signalpost.ref.guard.parse_inputs), `--bulk FILE` (Brreg snapshot; env SIGNALPOST_BULK; if absent use per-entity API for registry facts and say so in the report), `--output|-o FILE` (default out/envelopes.jsonl), `--profiles-output`, `--report` (default out/run-report.json), `--run-id` (default UTC timestamp), `--expected-count N` (never fatal: a mismatch becomes a warning in the report), `--previous DIR|FILE` (earlier envelopes for refresh), `--snapshots-dir` (default out/snapshots), `--time-budget SECONDS` (env SIGNALPOST_TIME_BUDGET_S, default 1500), `--workers` (default 24), `--resume`, `--no-llm`, `--strategies config/strategies.toml`, `--offline` (no network; registry-from-bulk only). Unknown extra flags must be ignored with a warning, not an error (argparse parse_known_args).
2. Input rules (guard.parse_inputs): output order = first-seen input order; duplicates produce no second envelope and are listed in the report; a malformed row yields a `failed` envelope with organisation_number set to the raw text and error code malformed_input. An id absent from the bulk snapshot is looked up live; 404 or 410 gives status `not_applicable` (deleted) or `not_available` with reason absent_from_registry; it never raises.
3. Envelope (src/signalpost/ref/envelope.py is the schema of record): superset of OUTPUT_CONTRACT.md plus legacy starter keys. Every envelope has: schema_version, organisation_number, status and availability (the six states, same value), status_reason, run{run_id, started_at, completed_at, terminal_status, agent{name, version, git_commit}, strategy_set}, identity, field_states (one entry per family, six-state availability + reason + checked_sources + claim_ids), claims[], evidence[], synthesis, changes[], errors[], operations{requests, runtime_ms, third_party_cost_usd}. Never emit null where the contract wants a list. Never emit 0 for missing.
4. Claims and evidence, one per fact, never per module: claim_id = ref.claims.claim_key(orgnr, field, discriminator) (discriminator = fiscal year, role id, subunit orgnr, job uuid, canonical URL; the value is never part of the key). Evidence = source_url, final_url, http_status, retrieved_at, content_sha256 of the STORED snapshot, snapshot_ref, claim_span (verbatim substring of the snapshot, max 500 chars), span_locator, reporting_period or published_at where relevant, extractor and version. Snapshots go to snapshots/ab/<sha>.gz and are written before the envelope that references them. A claim whose span cannot be found in its snapshot is DROPPED and an error entry is added; the validator enforces this.
5. Mapping of the official modules to claims (verify field names against docs/probes from /00):
   - identity: legal_name, legal_form, business address, postal address, NACE codes+labels, registered employees, registration date, flags bankrupt/liquidating/deleted. A 410 means deleted: status `not_applicable`, drop cached copies.
   - accounts (family accounts): per fiscal year revenue, operating_result, profit_before_tax, annual_result, assets, equity, debt; reporting_period from the filing period, currency, account type. An endpoint 404 = `not_available` (reason no_filing_returned), a 5xx/timeout = `failed` (retryable). Zero is allowed only if the source span shows a standalone 0.
   - accounts_history: list of filing years + PDF copy URLs. This endpoint is rate limited to about 30 requests per minute; schedule it LAST and only with time left.
   - leadership: role holders (name, role, role code, since/last changed, active). Discard birth dates. Companies as role holders keep their orgnr.
   - locations: registered subunits (orgnr, name, address, industry, employees). group: parent and children from konsernstruktur (404 = `not_available`).
6. Scheduler (src/signalpost/scheduler.py): waves ordered by value per second, each wave checks the Deadline before every task. Wave A all companies: registry, accounts, roles, subunits, group. Wave B: NAV jobs (phase /04). Wave C: website verification for candidates that need no search. Wave D: discovery that needs probing or search. Wave E: extraction on verified sites. Wave F: accounts_history, stretch connectors. Wave G: synthesis, then viewer. Deadline: soft = 80 percent of budget (stop starting waves D-F), hard = 92 percent (cancel everything, finalise). Per-company cap 90 s, per-stage cap configurable. Per-host concurrency 2, global concurrency from config, Brreg API concurrency 8 with retry/backoff on 429/5xx (honour Retry-After).
7. Writer: use ref.guard.EnvelopeWriter (append-only partial file, fsync every 25 rows, atomic rewrite in input order at the end). Install a SIGTERM/SIGINT handler that finalises: any company without an envelope gets failure_envelope(code=time_budget or interrupted). `--resume` skips orgs already in the partial file.
8. Report (out/run-report.json): counts per status and per family state, error codes, requests, bytes, third-party cost, p50/p95 seconds per company, peak RSS, wave timings, duplicates/malformed list, warnings, git commit, strategy hash, and `validation` from the validator.
9. No LLM and no search in this phase. Offline mode must work.

## Fault-injection tests (tests/test_runner_faults.py), all with recorded fixtures, no live network
- chaos input: BOM, blank lines, duplicates, 8-digit ids, text junk, ids as ints, objects with orgnr keys;
- network totally down: N envelopes, registry facts from the bulk fixture, every external family `failed` with a reason, validator passes;
- one worker raises, one hangs, one returns garbage: only those rows are failed, others fine;
- tiny budget (`--time-budget 3`) on 200 fake companies: exits before the budget, 200 envelopes, rest marked time_budget;
- kill -9 after 30 rows then `--resume`: no duplicates, no loss;
- redirect to 127.0.0.1 or a private IP, and a DNS name resolving to a private IP: refused (reuse website.assert_public_url on every hop);
- 50 MB response, slow-loris, wrong encoding, gzip bomb: bounded by size/time caps;
- output run twice on identical fixtures: ref.validate.compare_runs says idempotent.

## Acceptance (paste real output)
- `uv run pytest -q` green, including all fault tests.
- Smoke: `uv run python run_agent.py -i eval/sets/dev.txt --bulk data/brreg-enheter.csv -o out/dev-envelopes.jsonl` then `uv run python -m signalpost.ref.validate --input eval/sets/dev.txt --output out/dev-envelopes.jsonl --snapshots out/snapshots` -> passed true, 150 of 150.
- `--time-budget 20` on the 150: finishes in under 25 s, 150 envelopes, validator passed.
- `--offline` on the 150: 150 envelopes, validator passed.
- docs/DECISIONS.md records measured p50/p95 and requests per company for Wave A.
- Tag `phase2`. Stop and report.
