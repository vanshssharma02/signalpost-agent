# Operational Runbook & Incident Response — Signalpost

This runbook guides operators during daily batch runs, production triage, and competition submissions.

## 1. Quick Operations Reference

### Run Batch
```bash
# Standard daily batch execution
uv run python run_agent.py \
  --input /path/to/daily_batch.txt \
  --bulk data/brreg-enheter.csv \
  --output out/envelopes.jsonl \
  --report out/report.json \
  --viewer out/viewer/index.html
```

### Validate Batch
```bash
# Verify 100% strict contract conformance and snapshot spans
uv run python -m signalpost.ref.validate \
  --input /path/to/daily_batch.txt \
  --output out/envelopes.jsonl \
  --snapshots out/snapshots
```

### Build Standalone Viewer
```bash
uv run python scripts/build_viewer.py \
  --input out/envelopes.jsonl \
  --output out/viewer/index.html
```

---

## 2. Failure Signatures & Triage Procedures

| Failure Signature | Root Cause | Impact | Automated Remediation & Triage |
| :--- | :--- | :--- | :--- |
| **Malformed Orgnr** (e.g. 8 digits, letters, invalid Mod11) | Upstream dirty batch input | High risk of pipeline crash | Handled by `signalpost/run.py`: Emits terminal envelope with `status="failed"`, `error="invalid_orgnr"`. Never raises. |
| **Duplicate Orgnr** (same 9-digit ID in batch multiple times) | Duplicate rows in input batch | Violation of 1:1 emission | Runner deduplicates input set, processes company once, and replicates compliant envelope for each duplicate input key, guaranteeing exact 1:1 input/output length. |
| **Entity Not in Registry** | New entity or inactive entity not in bulk CSV | Missing registry anchor | Runner falls back to live Brreg API query `https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}`. If 404, emits envelope with `status="not_applicable"`, `error="entity_not_found"`. |
| **Target Website Down / 5xx / SSL Error** | Host server unreachable, dead link, TLS handshake fail | Potential network hang | Bounded fetch with 5s connect timeout and 10s read timeout. Yields `not_available` (`network_timeout` or `http_5xx`). |
| **Private IP / SSRF Trigger** | Company website redirects to loopback or RFC1918 IP | Security hazard | Intercepted by `assert_public_url` in `website.py`. Request aborted immediately; recorded as `failed` (`ssrf_blocked`). |
| **No 9-Digit Orgnr Found on Target Website** | Third-party or ambiguous domain | Risk of wrong-company publication (fatal) | Rule N2 Exact-Entity Proof rejects candidate. Domain marked as `ambiguous` or `not_available`. Domain is NEVER published without exact proof. |
| **NAV Feed Token Missing / Expired** | Environment variable `NAV_FEED_TOKEN` unset or expired | NAV hiring data unavailable | Degrades gracefully. Sets hiring field state to `not_available` (`missing_nav_token`). Batch execution proceeds without error. |
| **Watchdog Timer Exceeded (Budget Cap)** | Batch takes longer than configured maximum budget | Zero batch score | Global watchdog terminates remaining in-flight requests, finalizes partial envelopes, and flushes output before hard timeout. |

---

## 3. Daily Revision & Board Response Protocol

1. **Board Check**: Every morning, check the Builderr competition board for overnight batch scores and status.
2. **Error Report Ingestion**: If an official daily run fails or scores 0:
   - Request the failing input batch or error signature from the organizers.
   - Reproduce locally by saving the batch to `eval/sets/reproduce_issue.txt`.
   - Run batch through `run_agent.py` under debugger or with full logging.
3. **Rollback Strategy**:
   - If an experimental discovery or extraction strategy caused regressions or timeouts, revert via `config/strategies.toml` by disabling the specific module (zero code changes needed).
4. **Resubmission**:
   - Verify all unit and envelope guard tests pass: `uv run --with pytest pytest -q`.
   - Run clean smoke batch: `scripts/make_smoke_batch.py` + `run_agent.py` + `signalpost.ref.validate`.
   - Run `python scripts/make_submission.py` to get the updated commit hash and package details.
   - Push commit and submit the revised hash before the 2026-10-18 revision deadline.
