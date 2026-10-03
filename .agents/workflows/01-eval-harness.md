---
description: Phase 1 - build the evaluation harness (sets, labels, metrics, promotion gate) and measure the unmodified starter as the baseline.
---

# /01-eval-harness  (about half a day, plus about 2 hours of human labelling)

Goal: be able to say, with numbers, whether a change helps. Everything later is accepted or rejected by this harness (rule N10). Official scoring uses hidden batches; our proxy is only a compass.

## What the official score rewards (do not forget)
Recall (50) = per field family 0.7 x (share of companies covered) + 0.3 x (share of individual claims found), measured against the pooled union of all verified findings. Evidence (30) = exact identity + valid source/date/span; Synthesis (12); UX (8). A wrong-company publication blocks an official run.

## Steps

1. Sets (`eval/make_sets.py`, fixed seeds, committed as eval/sets/*.txt, one orgnr per line):
   - `dev` 150, `val` 150, `holdout` 200, plus `stress` 60. All disjoint; `holdout` is touched only by /07.
   - Stratify on legal form, employee bucket (missing, 1-4, 5-19, 20-99, 100+), registry-website present/absent (about 14 percent present in the real universe; keep that realism but guarantee at least 25 present in dev), and NACE division (include holding companies, NACE 64.2xx, because they are numerous and rarely have sites).
   - `stress` = hand-picked collision traps found by script: groups of companies sharing at least 2 distinctive name tokens; names ending in a city or "Norge/Norway"; franchise-like names; ENK with a personal name; NUF; ESEK/BRL; very small or new companies.
2. Labels (`eval/label.py`): generates a static HTML sheet (eval/labels/sheet.html) listing for each dev company: registry facts, then the candidate website(s) produced by the current strategy, with buttons same-company / different-company / cannot-tell, and a free-text field for the true official site if known. The human saves JSON to eval/gold/dev_labels.jsonl. Gold fields: official_website (url or "none"), has_open_jobs (y/n/unknown), has_recent_news (y/n/unknown). Label only dev (150) now; val after the first working version. Expect about 1.5 minutes per company; tell the human the estimate.
3. Metrics (`eval/score.py`) computed from a run's envelopes plus gold:
   - per family: company coverage, claim count, claims per covered company;
   - proxy recall per family = 0.7 x company_recall + 0.3 x claim_recall against the pool = union of (all strategy runs so far) and gold truths; label it PROXY in every report;
   - precision: published websites that are same-company / published (must be 100 percent), wrong-company publications (count, list them), cannot-tell count;
   - evidence validity via `python -m signalpost.ref.validate` (span check needs --snapshots);
   - field_state distribution per family (six states) and top reasons;
   - operations: requests, bytes, p50/p95 seconds per company, third_party_cost_usd, peak RSS.
4. Promotion gate (`eval/promote.py baseline.json challenger.json`): PASS only if all hold: zero new wrong-company publications; claim precision not lower; span validity 100 percent; proxy recall up by at least the declared minimum (default +1.0 point of proxy per family touched); runtime p95 and cost within budget; the strategy is registered in config/strategies.toml with a version. Output a signed-off decision file under reports/decisions/. Failing challengers stay in the registry as `disabled`.
5. Baseline. Run the UNMODIFIED starter pipeline (scripts/run_competition_batch.py with modules registry,accounting_obligation,registry_live,financials,roles,group,locations,website) on `dev`. Convert its output with a throw-away adapter into the metrics format. Write reports/baseline-dev.json and docs/BASELINE.md including: share of dev companies with a registry website, share with a website that passed the starter's gate, share with roles, subunits, financials; runtime and request counts; and a table of where the starter output does not match OUTPUT_CONTRACT.md (states, claims[], evidence[], changes[], errors[], operations{}).
6. Leaderboard calibration. docs/BASELINE.md must restate: unmodified starters score about 42.2 (Recall 12.89, Evidence 18.92, Synthesis 7.20, UX 3.20) on Builderr's board of 1 Oct 2026; the best entry is 45.59; qualification needs 65. Our goal list by category lives in docs/MASTER_PLAN.md section 2.

## Acceptance
- `uv run pytest -q eval` green (tests for stratification determinism, metric math on a tiny synthetic example, promotion gate pass/fail cases).
- `uv run python -m eval.score --envelopes <baseline> --set dev` prints a table; reports/baseline-dev.json exists.
- Human has been given the label sheet; labelling status recorded in docs/DECISIONS.md.
- The statement "registry website present for X percent of dev" is in docs/BASELINE.md with the real number.

Stop and report with real output.
