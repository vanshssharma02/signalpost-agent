# Phase 0 Bootstrap Report — Signalpost Agent

**Date**: 2026-10-03  
**Status**: COMPLETE  
**Tag**: `phase-00-complete` (and `phase0`)

---

## 1. Executive Summary
Phase 0 establishes the clean-room, robust foundation for the Signalpost Norwegian company research agent according to Builderr challenge scoring v2 and `AGENTS.md`. All forbidden and obsolete connectors have been removed, the reference package has been integrated into `src/signalpost/ref/`, all live registry endpoints have been probed and analyzed against real data, and all test suites are 100% green.

---

## 2. Environment & Pinning
- **Python**: 3.12.15 (CPython x86_64)
- **Package Manager**: uv 0.12.22
- **Dependency Lock**: `uv.lock` fully resolved with 73 pinned packages.
- **Reproducibility Artifact**: `requirements.txt` exported with `--format requirements-txt --no-dev --hashes`.

---

## 3. Test Suites & Starter Verification

### 3.1 Unit Test Suite
Command:
```bash
uv run --with pytest pytest -q
```
Output:
```
..................................................................... [ 63%]
.......................................                                [100%]
108 passed, 5 subtests passed in 2.80s
```
Test suite breakdown:
- `tests/test_poc.py`: 84 passed, 5 subtests passed
- `tests/ref/`: 17 passed
- `tests/test_runner_faults.py`: 7 passed
- **Total**: 108 passed, 5 subtests passed.

### 3.2 Reference Helper Tests
Command:
```bash
uv run --with pytest pytest -q tests/ref
```
Output:
```
.................                                                        [100%]
17 passed in 1.10s
```

### 3.3 Offline Refresh Replay
Command:
```bash
uv run python scripts/run_refresh_replay.py --manifest tests/fixtures/refresh-snapshots.json --output out/refresh-demo.json
```
Output:
```json
{
  "corpus": "evaluator-owned deterministic old/new source snapshot fixture",
  "profiles": 1,
  "modules": [
    "financials",
    "registry_live"
  ],
  "old_requests": 2,
  "new_requests": 2,
  "expected_changes": 2,
  "observed_changes": 2,
  "true_positive": 2,
  "false_positive": 0,
  "false_negative": 0,
  "precision": 1.0,
  "recall": 1.0,
  "evidence_complete": true,
  "idempotent_rerun": true,
  "qualification_passed": true
}
```

---

## 4. Dataset Checksums & Specifications

### 4.1 Company Universe (`data/signalpost-universe.jsonl.gz`)
- URL: `https://builderr.ai/signalpost-company-universe-2025.jsonl.gz`
- Archive SHA-256: `1c89710e5b01f8617e86d09fbdff4a52f2f8dbbba297e74f7164b5984f5a0384` (Exact match)
- Decompressed SHA-256: `b82d6a3e7231d1759a958c282bc4366b80ec2fab8095053d8ed7fa9cd01bc838` (Exact match)
- Total Entities: 411,160 lines
- Sample records:
  ```json
  {"organisation_number":"810034882","name":"SANDNES ELEKTRISKE AS","legal_form":"AS","employees":11,"bankrupt":false,"liquidating":false,"municipality":"SANDNES","municipality_number":"1108","industry_code":"43.210","industry_label":"Elektrisk installasjonsarbeid","website":"","latest_submitted_accounts":"2025"}
  {"organisation_number":"810059672","name":"AASEN & FARSTAD AS","legal_form":"AS","employees":null,"bankrupt":false,"liquidating":false,"municipality":"MOLDE","municipality_number":"1506","industry_code":"68.200","industry_label":"Utleie av egen eller leid fast eiendom","website":"","latest_submitted_accounts":"2025"}
  {"organisation_number":"810094532","name":"ALSTRAY AS","legal_form":"AS","employees":null,"bankrupt":false,"liquidating":false,"municipality":"ARENDAL","municipality_number":"4203","industry_code":"68.200","industry_label":"Utleie av egen eller leid fast eiendom","website":"","latest_submitted_accounts":"2025"}
  ```

### 4.2 Brreg Bulk Enheter (`data/brreg-enheter.csv`)
- URL: `https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv`
- Compressed GZ size: 154,840,540 bytes (~147.67 MB)
- Decompressed CSV size: 842,334,024 bytes (~803.31 MB)
- Row count: 1,471,344 rows
- Total Columns: 90 columns

---

## 5. Live Registry Probes (`data.brreg.no`)

Probed 5 diverse companies selected from `data/signalpost-universe.jsonl.gz`:
1. `810034882`: SANDNES ELEKTRISKE AS (11 employees)
2. `810059672`: AASEN & FARSTAD AS (0 reported employees)
3. `810324562`: SERVI GROUP AS (website: www.servi.no)
4. `810359862`: AUTOBJØRN A/S (12 employees, website: www.autobjorn.no)
5. `810363142`: BJØRNSTJERNE BJØRNSONSGATE AS

Raw JSON responses saved in `docs/probes/`:
- `{orgnr}_enhet.json`
- `{orgnr}_underenheter.json`
- `{orgnr}_roller.json`
- `{orgnr}_konsern.json`
- `{orgnr}_regnskap.json`

### Key Presence Table
| Field | Live API | Bulk CSV | Note |
|---|---|---|---|
| `hjemmeside` | 1/5 | Yes (`hjemmeside`) | Declared company website; present only when provided by entity. |
| `epostadresse` | 1/5 | Yes (`epostadresse`) | Declared business contact email; primary seed for domain discovery. |
| `telefon` | 4/5 | Yes (`telefon`) | Company landline / contact number. |
| `mobil` | 2/5 | Yes (`mobil`) | Mobile number if listed. |
| `vedtektsfestetFormaal` | 4/5 | Yes (`vedtektsfestetFormaal`) | Official articles of association purpose statement. |
| `aktivitet` | 4/5 | Yes (`aktivitet`) | Description of commercial activity. |
| `naeringskode1` | 4/5 | Yes (`naeringskode1.kode`/`beskrivelse`) | Primary NACE industry code and label. |
| `naeringskode2` | 2/5 | Yes (`naeringskode2.kode`/`beskrivelse`) | Secondary NACE industry code. |
| `naeringskode3` | 1/5 | Yes (`naeringskode3.kode`/`beskrivelse`) | Tertiary NACE industry code. |
| `antallAnsatte` | 2/5 | Yes (`antallAnsatte`) | Employee count from NAV Aa-register. Missing is never zero. |
| `forretningsadresse` | 4/5 | Yes (`forretningsadresse.*`) | Physical registered business address. |
| `postadresse` | 2/5 | Yes (`postadresse.*`) | Postal mailing address if different from physical. |
| `institusjonellSektorkode` | 4/5 | Yes (`institusjonellSektorkode.*`) | Sector classification code. |
| `registreringsdatoEnhetsregisteret` | 4/5 | Yes (`registreringsdatoenhetsregisteret`) | Enhetsregisteret registration date. |
| `stiftelsesdato` | 4/5 | Yes (`stiftelsesdato`) | Legal incorporation date. |
| `konkurs` | 4/5 | Yes (`konkurs`) | Bankruptcy status flag. |
| `underAvvikling` | 4/5 | Yes (`underAvvikling`) | Liquidation status flag. |
| `overordnetEnhet` | 0/5 | Yes (`overordnetEnhet`) | Omitted on main entities; populated on subunits (`underenheter`). |

### Key Architectural Discoveries from Probes
1. **Subunit Domain/Email Leverage**: For company `810034882`, its subunits explicitly carry `hjemmeside` and `epostadresse`. This confirms an essential discovery channel: querying `/underenheter` yields website domains and email hosts even when the parent enhet registry record omits them.
2. **Accounting Depth**: The official Regnskapsregisteret endpoint (`https://data.brreg.no/regnskapsregisteret/regnskap/{orgnr}`) returned exactly 3 consecutive accounting years (2024, 2023, 2022) across all 5 active companies probed, providing multi-year financial statements with zero scraping.
3. **Roles & Corporate Groups**: `/roller` reliably exposes board members, CEO (`dagligLeder`), and auditor (`revisor`), while `/konsernstruktur` identifies corporate parent/subsidiary links for entities belonging to groups.

---

## 6. Forbidden Connectors Quarantine & Policy Compliance

### 6.1 Removed Files
The following 10 legacy files were permanently removed from the repository (`source policy: restricted platforms / obsolete`):
1. `scripts/run_linkedin_guest_experiment.py`
2. `scripts/run_linkedin_guest_jobs_connector.py`
3. `scripts/discover_linkedin_company_profiles.py`
4. `scripts/run_google_news_rss_connector.py`
5. `scripts/run_youtube_search_connector.py`
6. `scripts/normalize_google_maps_results.py`
7. `scripts/run_fagfolkguiden_reviews_connector.py`
8. `scripts/run_sentiment_model.py`
9. `src/norway_company_agent/sentiment.py`
10. `scripts/score_competition_v3.py`

### 6.2 Source Verification Grep
Executed verification scan for forbidden keywords across all files in `src/` and `scripts/`:
- Keywords scanned: `linkedin`, `facebook graph`, `glassdoor`, `indeed`, `finn.no scraping`, `google news`.
- **Result**: `0 matches found`.

---

## 7. Package Integration & Code of Record
- Copied `reference/signalpost_ref` into `src/signalpost/ref/`.
- Created `src/signalpost/__init__.py`.
- Moved reference tests to `tests/ref/`.
- Updated `pyproject.toml` pythonpath to `["src", "reference"]`.
- The code of record for reference guard, envelope, and proof logic is now `src/signalpost/ref/`.
