---
description: Phase 7 - stress tests, human audit, clean-room proof, freeze, submission package and the revision schedule. Run before EVERY submission or revision.
---

# /07-submission  (about 1 day for v1, 2-3 hours per revision)

Hard dates (check the live page https://builderr.ai/challenges/signalpost): revisions close 2026-10-18 (up to four revised commit hashes, five versions in total); the round closes 2026-10-21. A broken run scores zero for that daily batch and the ranking averages all scheduled batches, so never submit an untested build.

## 1. Gate (call /01-eval-harness gate on val; touch `holdout` once per freeze)
Zero wrong-company publications on dev+val+stress, validator 100 percent, span validity 100 percent, 1:1 envelopes, p95 per company and total runtime inside budget, cost declared. Any failure blocks the freeze; fix or disable the responsible strategy in config/strategies.toml (rollback = set enabled=false, no code change).

## 2. Stress and chaos (rerun /02 fault tests plus)
- Scale: 1,100 random universe companies not used elsewhere: wall time, requests, bytes, RSS peak, p50/p95, third-party cost. Total must be under 70 percent of the stated budget (default 1500 s unless Builderr says otherwise) with the watchdog never firing; if it fires, report which waves were cut.
- Network brownout: block 30 percent of hosts at random (use a local proxy or the fetcher's fault hook): still N envelopes, validator passes.
- Missing optional keys: run with and without NAV_FEED_TOKEN, SEARCH_API_KEY, LLM_API_KEY: no crash, clear reasons.
- Idempotency on the 1,100 run twice: compare_runs idempotent true.
- Security: grep the repo and logs for secrets, confirm .env is untracked, private-IP/redirect tests pass, robots honoured, User-Agent carries a contact URL.

## 3. Human audit (reports/audit-<date>.md; the human reads stored spans, you prepare the sheet)
Sample from val+holdout runs: 60 published websites, 30 near-miss rejections (P2 failures), 30 NAV job claims, 20 news items, 30 profile links, 20 synthesis texts. For each: verdict same company / wrong company / cannot tell. One wrong company is a release blocker. State honestly that a sample of this size can reveal systematic failure but cannot prove a 99.5 percent rate; the safety comes from the proof rules, not from the sample.

## 4. Clean-room proof (mandatory, paste output)
In a fresh container with no caches and no repo history except the clone: `docker run --rm -it -v $PWD/out:/out python:3.12-slim bash -lc "apt-get update -qq && apt-get install -y -qq git curl >/dev/null && git clone <repo> app && cd app && git checkout <commit> && pip install -r requirements.txt && python run_agent.py -i /out/batch100.txt -o /out/envelopes.jsonl"`. (If Builderr names uv instead of pip, test that.) Then validate the output. Record wall time and requests. If this does not work first time, that is the best bug report you will ever get.

## 5. Package (scripts/make_submission.py prints everything below with the live commit hash)
- docs/SOURCES.md: every source, why allowed, terms and rate limits honoured, what is stored vs transient (search results are transient and never stored), what is excluded and why (LinkedIn/Meta/Glassdoor/Indeed/Finn scraping, Norid/WHOIS at scale, proff/1881/allabolag, Google/Bing result scraping).
- docs/LIMITATIONS.md: honest list (hiring covers NAV only, social pages are declared links not fetched content, no press monitoring, search-dependent coverage, languages).
- docs/SECURITY.md: secrets via env only, SSRF protections, size/time caps, robots, UA.
- reports/smoke-100.json and .md: the required smoke test on 100 fresh companies (not dev/val/holdout), with status counts, per-family coverage, wrong-company audit of every published website, timings, cost.
- README.md judge guide, requirements.txt (hashed pins) and uv.lock, LICENSE (MIT unless a dependency forbids it; list licences via pip-licenses in docs/LICENSES.md).
- Submission fields (exact): repository URL, full commit hash, one pasteable command, models/APIs/licences, expected third-party cost per official run, contact. Print them; the human sends them.
- Tag `submission-vN`; the commit the human submits must equal the tag.

## 6. Revision schedule (adjust to reality, never beyond 18 Oct)
v1 ~9-10 Oct: robust runner + website ladder + NAV jobs + synthesis + viewer, every gate green. v2 ~12 Oct: best performing experiments from the measurement loop. v3 ~15 Oct: site extraction/profile refinements, UX polish. v4 ~17 Oct: final tuned build after audit. v5 18 Oct: reserve for a hotfix only, no features. Between versions: read the board, keep a CHANGELOG with measured deltas, rerun /07 sections 1-4. Do not tune on holdout; do not change strategies after freezing a version except through a new version.

## 7. Monitoring after a freeze
Each morning: check the board and any message from Builderr; if a batch failed, ask them for the error text, reproduce with the failing input shape, fix, run /07, submit a revision if any remain. Keep docs/RUNBOOK.md with the failure signatures found.

## Acceptance
Items 1-5 complete with pasted evidence, tag created, submission fields printed. Stop and hand the package to the human.
