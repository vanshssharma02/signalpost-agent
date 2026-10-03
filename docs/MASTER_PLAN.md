# Signalpost: verified master plan (written 3 Oct 2026)

Sources actually read: the live challenge page, the evaluation-harness document (scoring v2), the full brief, agent playbook, source policy and learning-harness documents, Builderr's guidelines, your starter kit (extracted, 104 tests run green, offline refresh replay run green), NAV's pam-stilling-feed docs, Norid's lookup terms, Brave's API terms. Not verified (my sandbox cannot reach Brreg or NAV): live API field names, NAV feed volume. Workflow /00 probes them first.

## 0. Bottom line

1. Gemini's diagnosis is wrong in a way that matters. The board you are chasing is not "perfect synthesis and UX, recall stuck at 12-17". On the live board (1 Oct 2026, 28 submissions, 17 assessed, 0 qualified) the best entry scores 45.59, and the typical unmodified-starter profile is Recall 12.89, Evidence 18.92, Synthesis 7.20, UX 3.20 = 42.21. There are about 20 points of headroom outside Recall (Evidence, Synthesis, UX), and those are cheaper than Recall points.
2. The real Recall bottleneck is website discovery. Only about 14 percent of companies list a website in the registry (138 of 1,000 in the kit's own submission sample; 25 of 250 in its extension sample). The starter finds sites for roughly one company in seven; everything downstream (profiles, news, careers, brand) hangs off a verified site. The tool for the other 86 percent is the organisation number itself: companies are expected to print it on their site, so it is both a search key and a proof of identity.
3. A second cheap, exact source Gemini never mentioned: NAV Arbeidsplassen's official job feed, whose ads carry employer.orgnr (and a homepage). Hiring becomes a precise, org-number-keyed family with no scraping.
4. The unmodified starter will crash or abort on a real batch (expected-count default 100, raising on odd ids, one exception kills the run, output written only at the end). A crashed batch scores zero and ranking averages daily batches. Robustness is a scoring feature.
5. Honest odds: nobody has qualified yet. I think 65 is reachable by banking Evidence, Synthesis and UX first and then pushing Recall, but my central estimate is about 66 with a wide band (60-73). That is a hypothesis, not a measurement; /01 gives you the instrument to find out.

## 1. Gemini's brief, checked

| Gemini said | Verdict | Reality (source) |
|---|---|---|
| 28 submissions, 19 evaluated, top 60.51, 0 qualified | Wrong/outdated | Board 1 Oct: 28 submissions, 17 assessed, 0 qualified, top 45.59 (challenge page). |
| Synthesis 11-12/12, UX 8/8, Precision 26-29/30 for most entries | Wrong | Typical: Synthesis 7.20, UX 1.60-3.20, Evidence about 18.9 of 30. |
| Recall 12-17/50 | Right | 12.89-17.86. |
| Recall = coverage 70 percent + fact density 30 percent, "10-25 facts per entity" | Partly | Weights right, mechanism wrong: computed per external field family, 70 percent company coverage + 30 percent claim coverage, against the pooled union of all verified findings (harness doc). More facts per company is not the metric; more companies covered per family is. |
| 65 to qualify | Right | Official run of 65/100 or more. |
| Single wrong-company match disqualifies | Close | Run cannot become official until corrected; also tie-break on fewer wrong-company publications. |
| Six statuses | Right names, wrong semantics | They apply per claim/field as well as per company: not_available = looked, nothing there; not_applicable = question does not apply; blocked = source refused; ambiguous = could not be sure it is this company; failed = our run broke. |
| Use Finn.no, LinkedIn for jobs | Not allowed | Source policy names LinkedIn/Meta/Glassdoor/Indeed as restricted; use NAV feed and company career pages. |
| Proff.no / Regnskapstall for financials | Unnecessary, risky | The official Regnskapsregisteret API is the source; EBITDA is not a registry field. |
| Validate via WHOIS | Don't | Norid's terms forbid copying/storing/bulk use of lookup data; use org-number-on-page proof. |
| Playwright fallback, LangChain/Instructor | Overkill | Deterministic first; LLM never decides identity; headless browsers are slow and brittle. |
| "15-30 s per company" | Wrong frame | A batch has a fixed total budget; concurrency, waves and a deadline watchdog matter. |
| Idempotency = refresh timestamps | Incomplete | Needs stable claim keys, content-hash snapshots, typed change events, failed-refresh-keeps-value (evaluation harness, refresh section). |
| Omitted | | Daily frozen batches, five versions, revision deadline 18 Oct, close 21 Oct, clean-room run, 100-company smoke report, declared cost, secrets via env, safe URL handling, source-rights documentation. |

## 2. What the contest actually measures

Facts: universe 411,160 active Norwegian entities; the official batch is about 1,000-1,100 companies, chosen after a daily cutoff and shared by all entrants; Builderr supplies organisation numbers, an output contract and a frozen registry snapshot, not websites or social identities; your submitted commit runs in a clean environment with one command, a fixed time and resource budget; a crashed or timed-out batch is not scored (zero for that batch); the ranking averages every scheduled daily batch while a frozen version is active; first submission is v1, then up to four revised commits before 18 Oct; the round closes 21 Oct. Prizes: $2,500 total ($1,200/$500/$300 main plus a $500 JBOX bonus; I could not find out what JBOX is, it is in the email). Builderr awards nothing if nobody clears the bar.

Scoring v2: Recall 50, Evidence 30, Synthesis 12, UX 8. Tie-breaks: fewer wrong-company publications, then weighted company recall, then lower declared third-party cost.

Where the points are (baseline numbers are from the live board; targets are my estimates):

| Category | Max | Starter | Best on board | Realistic target | Cheapest levers |
|---|---|---|---|---|---|
| Recall | 50 | 12.89 | 17.86 | 22-28 | website ladder, NAV jobs, site extraction, breadth across companies |
| Evidence | 30 | 18.92 | 18.93 | 23-27 | claim-level provenance, verbatim spans, reporting periods, zero unsupported facts |
| Synthesis | 12 | 7.20 | 7.20 | 9-11 | cited template synthesis with an explicit unknowns list |
| UX | 8 | 3.20 | 1.60 | 6-7.5 | static, mobile-first viewer with evidence popovers and compare |
| Total | 100 | 42.21 | 45.59 | 60-73 | |

What I do not know: how Builderr defines the external field families, how Evidence is split, how UX is opened. Questions 4 and 6 in the email.

## 3. The starter kit

Good: official.py (registry, roles, subunits, group, accounts), http.py, website.py safety (public-URL assertion, redirect handling, robots), snapshots.py, sampling.py, refresh.py, the offline replay, 104 tests. Traps and fixes: docs/KNOWN_STARTER_TRAPS.md. Delete the LinkedIn/Google News/YouTube/Maps/sentiment connectors and the obsolete scorer.

## 4. Ideas Gemini missed, ranked by expected value

1. Website discovery ladder with organisation-number proof (workflow /03). Order: registry homepage; business e-mail domain from the registry; subunit homepage/e-mail; employer.homepage from NAV ads; name-derived domain probing; search on the organisation number (only with a key, results transient). P1 proof: valid mod-11 number on a page of the same domain with no foreign labelled number; P2: name + street + postcode + phone/email/role holder; anything weaker is rejected. Biggest lever and biggest risk.
2. NAV job feed keyed by employer.orgnr (workflow /04A). Official, exact, dated, public ad link as evidence. Spike S1 measures feed size to choose name-match vs fetch-all.
3. Superset envelope + claim-level evidence with verbatim spans, validated by a script (workflow /02). Targets Evidence (30).
4. Crash-proof runner: tolerant input, per-company timeout, global watchdog, append-only output, resume, fault tests. Protects every batch.
5. Wave scheduler by value per second: registry for all, jobs for all, cheap site verification, then probing/search by site-prior, then extraction, history last (the history endpoint is rate limited to about 30 per minute).
6. Effort allocation by prior: holding companies, housing co-ops and condominium associations rarely have sites; spend probing/search on firms with employees, business e-mail and site-friendly NACE.
7. Company-site structured data harvest: JSON-LD, RSS/Atom, WordPress REST, sitemaps, `<time>` tags for dated activity; careers JSON-LD; company-declared profile links without fetching platforms.
8. Registry free text and derived metrics for synthesis: purpose/activity text (verify field presence), NACE, YoY growth, margin, equity ratio, group structure.
9. Static viewer (workflow /06): 4-5 UX points for about a day.
10. Evaluation harness with promotion gate and human audit (workflow /01, /07): the only defence against the disqualifying mistake and against self-deception.
11. Idempotent refresh with a claim store and typed change events; failed refresh never erases (workflow /05).
12. Stretch (spike only after the core works, gated by terms and the harness network policy): registry change feed, OSM `ref:NO:orgnr`, TED/Doffin awards, Wikidata.

## 5. Architecture

```
run_agent.py -> signalpost.run
  guard.parse_inputs -> rows (1:1, first-seen order)
  scheduler (waves, Deadline soft 80% / hard 92%)
    A registry, accounts, roles, subunits, group  (Brreg, 8 concurrent)
    B NAV feed index -> jobs
    C website candidates that need no search -> proof
    D probing + search for high-prior companies -> proof
    E extraction on verified sites (activity, profiles, brand, careers)
    F accounts_history, stretch connectors
    G synthesis -> envelopes -> viewer
  EnvelopeWriter (append-only partial -> atomic rewrite in input order)
  validator -> run-report.json
```
Deterministic code does identity, extraction and numbers; an LLM is optional and only rewrites verified claims. Python 3.12, uv, pydantic v2, httpx async for new I/O, lxml/trafilatura/extruct, pytest. Everything works with `--no-llm` and `--offline`.

## 6. Status semantics (per family and per company)

available: at least one verified claim. not_available: source checked successfully, nothing found (say which sources). blocked: refused (401/403/429-after-retry/robots/captcha); never evaded. not_applicable: the question does not apply (deleted/bankrupt/liquidating entity; no filing duty). ambiguous: two proof-passing domains or partial proof; nothing published. failed: our error or time budget (reason code `time_budget`, `company_timeout`, `worker_exception`). A family never checked is `failed` with reason `not_checked`. Company-level state: not_applicable if flagged, available if any claim, blocked/failed if nothing completed, else not_available (to be confirmed with Builderr).

## 7. Data contract (superset of OUTPUT_CONTRACT.md + legacy starter keys; code of record: reference/signalpost_ref/envelope.py)

```json
{"schema_version":"signalpost-envelope/1","organisation_number":"985821585",
 "status":"available","availability":"available","status_reason":"verified_claims_present",
 "run":{"run_id":"2026-10-09T06:00Z","started_at":"...","completed_at":"...","terminal_status":"completed","agent":{"git_commit":"..."}},
 "identity":{"legal_name":"...","claim_ids":["..."]},
 "field_states":{"website":{"availability":"available","reason":"verified","checked_sources":["registry_homepage"],"claim_ids":["..."]},
                 "hiring":{"availability":"not_available","reason":"none_in_nav_feed"}},
 "claims":[{"claim_id":"<sha256(orgnr|field|discriminator)[:20]>","field":"official_website","family":"website",
            "value":"https://example.no/","availability":"available","identity_proof":"orgnr_exact",
            "evidence_ids":["ev-1"],"first_observed_at":"...","last_verified_at":"..."}],
 "evidence":[{"id":"ev-1","source_url":"https://example.no/","retrieved_at":"...","content_sha256":"<64 hex>",
              "snapshot_ref":"snapshots/ab/....gz","claim_span":"Org.nr. 985 821 585","source_class":"company_owned"}],
 "synthesis":{"sentences":[{"id":"s1","text":"...","claim_ids":["..."]}],"unknowns":[...]},
 "changes":[],"errors":[],"operations":{"requests":14,"runtime_ms":8200,"third_party_cost_usd":0}}
```
`python -m signalpost.ref.validate` enforces it: 1:1 rows, six states, evidence fields, spans found in snapshots, periods on accounts, dates on jobs/news, "missing is not zero".

## 8. Idempotency

Stable claim_id (value excluded), content-addressed snapshots, `merge_claims` semantics: same value moves only last_verified_at; new value is one `changed` event with both evidence ids; missing after a successful family re-check is `removed`; missing after a failed refresh is kept. Tested in reference/tests and replayed in /05.

## 9. Synthesis and UX

Synthesis: template-v1 always, with sentence-level claim ids and a mandatory unknowns list built from real reason codes; LLM rewrite only as a gated experiment with a verifier that falls back on any unsupported number, date or name. UX: see /06; works from file://, mobile first, accessible, evidence two clicks away.

## 10. Evaluation and freeze

Sets dev 150 / val 150 / holdout 200 / stress 60 with fixed seeds; you label dev (about 2 hours). Proxy recall is a compass, not the score. Promotion gate: zero new wrong-company, span validity 100 percent, proxy gain, runtime/cost in budget. Audit sample before each freeze; a sample of about 200 items can reveal systematic failure but not prove 99.5 percent, so safety comes from the proof rules.

## 11. Timeline (today is 3 Oct; revisions close 18 Oct)

| Date | Work |
|---|---|
| 3 Oct | Send the email. Set up repo, /00. Start labelling when /01 produces the sheet. |
| 4-5 Oct | /01, then /02 (runner + envelope + fault tests). Everything else depends on this. |
| 6-8 Oct | /03 (website ladder) in the main branch; in parallel agents on separate branches: /04A NAV, /06 viewer, /05 template synthesis. |
| 9-10 Oct | /04B site extraction, merge, /07 gates and clean-room proof, submit v1 only if green. |
| 11-12 Oct | Experiments from the measurement loop; v2. |
| 13-15 Oct | Refinements, UX polish, optional LLM rewrite experiment; v3. |
| 16-17 Oct | Audit, final tuning; v4. |
| 18 Oct | Reserve v5: hotfix only. 21 Oct round closes. |

If time is short, the must-do order is /00, /02, /03 (A-E), /04A, /05 template, /06 basic viewer, /07. Cut: search API, LLM rewrite, history, stretch spikes.

## 12. Risks and open questions

Unknown harness CLI/budget/network policy (email 1-3); NAV public token acceptability; search key availability and cost; org-number-on-site rate lower than hoped (measure on dev; fall back to P2 only under strict rules); Evidence scoring mechanics hidden; JBOX unknown; Antigravity UI differences; one wrong-company item invalidates an official run, so the stop rule is: if in doubt, do not publish.

## 13. Sources

https://builderr.ai/challenges/signalpost ; https://builderr.ai/docs/signalpost-evaluation-harness.md ; https://builderr.ai/starter-briefs/signalpost.md ; .../signalpost-agent-playbook.md ; .../signalpost-sources.md ; .../signalpost-learning-harness.md ; https://builderr.ai/guidelines ; https://navikt.github.io/pam-stilling-feed/ ; https://www.norid.no/en/domeneoppslag/vilkar/ ; https://api-dashboard.search.brave.com/terms-of-service ; Antigravity rules/workflows docs (via search; 12,000-character limit per rules/workflow file, AGENTS.md at repo root, workflows invoked with /name, workspace folder `.agents/` with `.agent/` supported).
