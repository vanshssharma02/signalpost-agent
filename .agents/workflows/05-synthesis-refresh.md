---
description: Phase 5 - source-grounded synthesis (what the company does, what changed, what is unknown) plus idempotent refresh and change events.
---

# /05-synthesis-refresh  (about 1.5 days)

Goal: Synthesis (12 points) and the refresh/idempotency requirements. Baseline entries score about 7.2 of 12 on synthesis, so this is cheap, deterministic points. Idempotency is a qualification requirement: the same source snapshot must never create duplicate records or false changes.

## A. Synthesis object (envelope.synthesis; schema is fixed, validate it)
{ "generator": "template-v1" | "llm-v1", "language": "en", "headline": str, "what_it_does": str, "business_model": str|null, "size_and_financials": str, "leadership_and_structure": str, "locations": str, "hiring_signal": str, "recent_activity": str, "what_changed": str, "unknowns": [ {"topic": str, "why": str, "checked": [source names]} ], "sentences": [ {"id": "s1", "text": str, "claim_ids": [..]} ] }
Every factual sentence cites at least one claim_id that exists in the same envelope; sentences without a claim (framing words) contain no facts. The `unknowns` list is mandatory and built from field_states: not just "no website" but "website: registry field empty; business e-mail domain none; 12 domain guesses unreachable or unproven; search not configured" (use the real reason codes). Say plainly when something could not be verified, never fill the gap with plausible text.
1. Deterministic composer (src/signalpost/synthesis.py), always runs, needs no key:
   - what_it_does from, in this order: registry purpose/activity text if the probe in /00 showed those fields (vedtektsfestetFormaal, aktivitet), NACE labels, the verified site's meta description / JSON-LD description (labelled "according to its website"). If only a NACE label exists say "classified under <label>"; do not invent a product.
   - business_model: only what legal form + NACE + facts support (e.g. "limited company, X employees registered, B2B services classification"); otherwise null and listed in unknowns.
   - size_and_financials: employees; latest fiscal year revenue, operating result, result, equity, assets, with period and currency (NOK); derived metrics only when inputs exist and are labelled derived with a formula: revenue growth YoY, operating margin, equity ratio. Qualitative words only from fixed thresholds in config (growing > +10 percent, shrinking < -10 percent, loss-making when result < 0, otherwise stable).
   - leadership_and_structure: chair/CEO/board counts from roller, parent/subsidiary counts from konsernstruktur.
   - locations: number and municipalities of registered subunits, head office address.
   - hiring_signal: number of active NAV ads with newest publish date; "none found in NAV feed" is not "not hiring".
   - recent_activity: newest company-owned news items with dates, labelled as company-published.
   - what_changed: from `changes` of this run (empty on a first run: say "first observation on <date>; no earlier snapshot").
   Write natural English, short sentences, numbers formatted with thousands separators, dates ISO. Keep the whole synthesis under 250 words.
2. Optional LLM rewriter (experiment, off by default, `--no-llm` always wins): input is ONLY the verified claims JSON (no page text, no search snippets, so no prompt-injection surface), temperature 0, strict JSON schema, every output sentence must carry claim_ids. A verifier rejects the output and falls back to the template when any number, date, name or url in a sentence is not present in its cited claims, when a claim_id does not exist, or when the text asserts something listed in `unknowns`. Cache by sha256 of the input claims; hard cost cap per run; declare model and cost per run in docs/SOURCES.md. Promote only if a blind comparison of 20 company summaries by the human prefers it and the verifier fallback rate is under 5 percent.
3. Tests: every sentence cites existing claims; numbers in text equal numbers in claims; no synthesis mentions a fact absent from claims (property test over dev envelopes); empty-data company yields an honest short summary with a long unknowns list; determinism (same claims, same text).

## B. Refresh and idempotency
1. Claim store: state/claims.jsonl (or sqlite) keyed by claim_id; use src/signalpost/ref/claims.merge_claims. Same key + same value: only last_verified_at moves. Same key + new value: one `changed` event, old value kept in history. New key: `added`. Missing from a SUCCESSFUL re-check of its family: `removed` with removed_at (history kept). Missing because the source failed: keep the last supported value, no event.
2. Claim keys must be stable across runs and machines: claim_key(orgnr, field, discriminator). Discriminators: fiscal year, role id (or name+role code), subunit orgnr, job uuid, canonical URL (lowercase host, no tracking params, no trailing slash, no fragment). Normalise values before hashing (NFC, trimmed, numbers as numbers, dates ISO, lists sorted where order is meaningless).
3. Snapshots are immutable and content-addressed (sha256). Unchanged bytes -> same hash -> no new evidence row; changed bytes -> new snapshot, old one kept referenced by history.
4. `--previous` reads an earlier envelopes file or state dir; without it the run behaves as a first observation and still writes state/ for next time. If the harness gives no previous data, keep first_observed_at = last_verified_at = now.
5. Change events (envelope.changes and out/changes.jsonl): {type: new_filing|new_role|role_ended|new_location|location_closed|new_job|closed_job|new_website|website_changed|news_item_added|profile_added|description_changed|status_changed, orgnr, field, claim_id, old, new, old_evidence_id, new_evidence_id, detected_at, material: bool}. Both sides carry evidence ids. Cosmetic differences (whitespace, ordering, tracking params) are never events.
6. Extend scripts/run_refresh_replay.py (starter) so it also replays OUR pipeline on two recorded snapshot sets (old/new) per family and prints true positives, false positives, false negatives for change detection; goal: 0 false positives on unchanged input, every injected change detected once.
7. Tests: unchanged rerun gives zero changes and identical claim ids (use ref.validate.compare_runs); one injected change gives exactly one event with both evidence ids; shuffled input order and reordered JSON keys give no events; failed source keeps last value; re-added job gets a new event but the same claim_id; run twice at different clock times changes only last_verified_at and run fields.

## Acceptance (paste real output)
- `uv run pytest -q` green; `uv run python scripts/run_refresh_replay.py ...` prints false_positive 0 and idempotent_rerun true for the starter fixture AND for our fixtures.
- On `dev`: 100 percent of envelopes have a synthesis that passes the schema and citation checks; show 5 full examples (one rich, one sparse, one with a company site, one NUF/ENK, one with many NAV ads) and word counts.
- Two consecutive dev runs on frozen fixtures: compare_runs idempotent true, changes empty.
- Tag `phase5`. Stop and report.
