# AGENTS.md — Signalpost company-research agent (read before every task)

## Mission
Build an autonomous research agent for Norwegian companies for the Builderr "Signalpost" challenge (scoring v2).
Input: a batch of 9-digit organisation numbers (official batch about 1,000–1,100 companies, a new unseen batch each day).
Output: exactly ONE terminal result envelope per input company, every claim sourced.
Score (100): recall and coverage 50, precision and evidence 30, synthesis 12, UX 8. Qualify at 65 or more on an official run.
Dates: revisions close 2026-10-18; the round closes 2026-10-21. Do not slip.

## Scoring facts (already verified — do not re-derive)
- Recall is computed per information family: 70% = share of companies covered, 30% = share of individual claims, both against the pooled union of everyone's verified findings. Breadth across companies beats depth per company. Abstaining never counts as coverage.
- A material wrong-company publication blocks an official run and loses tie-breaks. A missed fact is cheap; a wrong one is fatal.
- Runs happen daily. A crash, timeout or missing row scores zero for that batch. The mean over batches ranks entries.

## Non-negotiables (if one is at risk: stop, fix, report)
N1 One envelope per input organisation number, always. Never let an exception leave the batch loop. Per-company try/except plus a hard per-company limit plus a global watchdog that finalises unfinished companies before the budget ends. Bad input (duplicate, malformed, absent from the registry snapshot) yields an envelope with an explicit state and error — never a raise. The unmodified starter raises on these; fix that.
N2 Identity: the organisation number is the only key. Publish a website, profile, job or news item only with exact-entity proof (workflow /03). Name similarity, search rank and LLM judgement are candidates, never proof. Unsure means `ambiguous` at field level.
N3 No fabrication. Missing is never 0 or "". Every published claim has source_url, retrieved_at, content_sha256 of a stored snapshot, reporting period or published date, extraction method and a verbatim `claim_span` that exists in the snapshot (verified at write time; if not found, drop the claim).
N4 LLMs may only (a) propose candidates or (b) rewrite already-verified claims, citing claim IDs. They never decide identity, never supply a value, temperature 0, and everything must work with `--no-llm`.
N5 Source rights: use only the allowed sources below; document terms and rate limits in docs/SOURCES.md.
N6 Secrets only via environment variables (NAV_FEED_TOKEN, SEARCH_API_KEY, LLM_API_KEY, ...). Never in the repo, logs, envelopes or screenshots. A missing key degrades gracefully; it never crashes a run.
N7 Idempotent refresh: stable claim keys (orgnr|field|discriminator), immutable content-hash snapshots, merge semantics of reference/signalpost_ref/claims.py. Identical snapshots give zero new claims and zero changes; only last_verified_at moves. A failed refresh keeps the last supported value.
N8 Deterministic first: registry and APIs, then structured data (JSON-LD, RSS, sitemap, WordPress REST), then DOM, then text rules, then an LLM last.
N9 Clean-room reproducible: Python 3.12, pinned dependencies (uv.lock plus exported requirements.txt with hashes), one run command, no reliance on local caches or on anything installed by hand.
N10 Never tune on the test split. Strategies, thresholds, prompts and budgets live in config/strategies.toml and are frozen before each submission. Promote a challenger only if: zero new wrong-company publications, no drop in claim precision, 100% span validity, coverage up by a declared minimum, runtime and cost within budget. Keep the previous strategy for rollback.

## Allowed sources (ladder: higher beats lower when they conflict)
1. Brønnøysund open data (NLOD): Enhetsregisteret bulk and API, roller, underenheter, konsernstruktur, Regnskapsregisteret (+ PDF copies).
2. Company-owned sites AFTER identity proof: pages, sitemap, RSS/Atom, WordPress REST (/wp-json), JSON-LD, outbound social links.
3. NAV Arbeidsplassen job feed (pam-stilling-feed): official, ad detail has employer.orgnr. Honour its terms: drop inactive ads, never store contactList.
4. A search API for CANDIDATE generation only. Results are transient: never write titles, snippets, ranks or query text to disk or envelopes. Evidence is the independently fetched page.
5. Stretch spikes (measure first, keep only with proven gain and zero new wrong-company): OSM tag ref:NO:orgnr via Overpass, Wikidata by organisation number, TED/Doffin awards.

## Forbidden
LinkedIn / Facebook / Instagram / Glassdoor / Indeed / Finn.no scraping or unofficial clients; Google or Bing result scraping; Norid or WHOIS lookups in bulk (Norid's terms forbid storing or bulk use); proff.no, allabolag, 1881, gulesider scraping; anything behind a login, paywall or anti-bot; ignoring robots.txt; personal e-mails, phones, birth dates of individuals; Google News RSS and review/sentiment sources in v1.
Record social-profile URLs only as found on a verified company site. Do not fetch the platform page.

## Reuse vs replace in the Builderr starter kit
Reuse: official.py (Brreg modules), http.py, website.py safety (assert_public_url, SafeRedirectHandler, robots), snapshots.py (SnapshotFetcher), sampling.py (iter_bulk), refresh.py ideas, scripts/run_refresh_replay.py, the 104 tests.
Replace or extend: batch.py (input handling raises; envelope shape), identity.py (name-token gate is NOT enough for discovered domains), website.py scope, research.py (becomes deterministic synthesis fallback), build_prototype.py (becomes the viewer).
Do not use: LinkedIn connectors, Google News RSS, YouTube/Google Places connectors, score_competition_v3.py (it scores an OLD rubric of 55/15/10/12/8 — not the current one).
Starter tests and the offline replay must stay green after every phase.

## Engineering conventions
Python 3.12, uv, pydantic v2, httpx (async) for new I/O, lxml/trafilatura/extruct for parsing, pytest. Package `src/signalpost/`; keep `norway_company_agent` importable. Type hints, small modules (<400 lines), no global mutable state except the rate limiters. Log JSON lines with run_id and orgnr; never log secrets or page bodies. Every network function takes a fetcher argument so tests can inject recorded fixtures (no live network in unit tests). Commit after each task with a message that names the phase.

## Working agreement
- Start each phase by writing a short plan in docs/DECISIONS.md, then implement.
- Run the acceptance commands of the phase and paste real output in your final message. Never claim "done" without it.
- Never invent URLs, numbers, API fields or test results. If an API response differs from these docs, trust the live response, record the difference in DECISIONS.md, and continue.
- Ask the human before: spending money, sending e-mail, registering accounts, adding a dependency with a non-permissive licence, or touching anything on the forbidden list.
- One phase at a time; stop at each phase's acceptance and report. Phases run via workflows /00-bootstrap … /07-submission.

## Repo map (target)
src/signalpost/{run,model,evidence,identity,discovery,connectors/,synthesis,viewer}.py · src/norway_company_agent/ (starter) · reference/signalpost_ref/ (tested helpers; /00 copies them to src/signalpost/ref/): orgnr proof, domain candidates, claim merge, envelope, guard, validate · eval/ · config/strategies.toml · docs/ · reports/ · site/ · tests/
