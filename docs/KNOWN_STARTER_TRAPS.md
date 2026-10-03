# Known traps in the Builderr starter kit (verified by reading the code and running it)

The starter is good infrastructure (104 tests pass, the offline refresh replay passes) but it is a lab kit, not a crash-proof submission. Fix these before anything else (workflow /02).

| # | Where | What happens | Fix |
|---|-------|--------------|-----|
| 1 | scripts/run_competition_batch.py `--expected-count` default 100 | Any batch whose size is not 100 aborts with SystemExit before doing work. Official batch is about 1,000-1,100. | Never fatal; mismatch becomes a report warning. |
| 2 | src/norway_company_agent/batch.py read_organisation_inputs | Raises ValueError for a malformed id or duplicates. | Tolerant parser (ref.guard.parse_inputs); malformed -> `failed` envelope; duplicates -> one envelope. |
| 3 | batch.py profiles_from_bulk | Raises ValueError if an id is absent from the registry snapshot. | Look up live; 404/410 -> `not_applicable`/`not_available` envelope. |
| 4 | run_competition_batch.py loop `future.result()` | One unexpected exception in one company stops the whole run. | Per-company try/except, timeout, watchdog (ref.guard.run_batch). |
| 5 | run_competition_batch.py | Envelopes are written at the end; a killed run leaves nothing. | Append-only partial file, fsync, atomic rewrite, `--resume`. |
| 6 | batch.py state vocabulary (complete, not_found, blocked_policy, source_error, submission_error) | Not the six required states; envelope has no claims[]/evidence[]/changes[]/errors[]/operations{}. | Superset envelope (ref.envelope) with the six states at company, family and claim level. |
| 7 | official.py history endpoint | Requests are spaced 2.1 s apart; 1,000 companies would need about 35 minutes for history alone. | Disabled by default; run last with leftover time. |
| 8 | website.py / identity.py | The website gate checks name tokens on the REGISTRY homepage only. Safe for that input, unsafe for discovered domains. | Organisation-number proof (workflow /03). Name similarity is never proof. |
| 9 | social identity gate | Quarantines company-declared links whose handle lacks name tokens (lost recall). | Accept links declared by a verified site under explicit rules (workflow /04). |
| 10 | scripts/*linkedin*, google_news_rss, youtube, google maps, fagfolkguiden, sentiment | Restricted platforms or out-of-policy sources; risk to Evidence score and to source-rights review. | Delete from the submission tree (workflow /00). |
| 11 | scripts/score_competition_v3.py | Scores an older rubric (55/15/10/12/8 split), not the current v2 (50/30/12/8). | Do not use; own proxy in eval/. |
| 12 | scripts/build_prototype.py | Produces a lab-style site and mentions LinkedIn discovery. | Replace with the viewer (workflow /06). |
| 13 | Registry homepage coverage | Only about 14 percent of sampled companies list a website (138/1000, and 25/250 in the extension sample). | This is the real recall bottleneck; workflow /03. |
