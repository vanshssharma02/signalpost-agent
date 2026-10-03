# DECISIONS.md — Signalpost Engineering Log & Decisions

## Rules as I understand them (N1–N10)
- **N1**: Exactly one result envelope per input organization number; never let an exception leave the batch loop; malformed/duplicate/missing inputs yield explicit terminal states rather than crashing.
- **N2**: Organization number is the sole entity key; publish websites/profiles/jobs only with exact-entity proof; name similarity is never proof.
- **N3**: Absolute zero fabrication; missing is never 0 or ""; every claim has source URL, retrieved_at, SHA256, reporting period/published date, and verbatim claim span verified in snapshot.
- **N4**: LLMs may only propose candidates or rewrite verified claims; never decide identity or invent values; must work with `--no-llm`.
- **N5**: Allowed sources only (Brreg open data, verified company-owned sites, NAV Arbeidsplassen feed, search API for transient candidates only).
- **N6**: Secrets via environment variables only; missing keys degrade gracefully without crashing.
- **N7**: Idempotent refresh using stable claim keys, immutable snapshots, and merge semantics; identical runs produce zero new claims and zero false changes.
- **N8**: Deterministic sources first (APIs, structured data JSON-LD/RSS, DOM, text rules, LLM last).
- **N9**: Clean-room reproducibility (Python 3.12, pinned dependencies, no local state reliance).
- **N10**: Freeze strategies in config/strategies.toml; never tune on the test split; promote challengers only with zero wrong-company errors and verified gains.

## Tool Versions
- Python: 3.12.15 (CPython x86_64)
- uv: 0.12.22

## Phase 0: Bootstrap, Environment & Probe Findings

### Data Checksums & Files
1. **Universe Dataset (`data/signalpost-universe.jsonl.gz`)**:
   - Download URL: `https://builderr.ai/signalpost-company-universe-2025.jsonl.gz`
   - Archive SHA-256: `1c89710e5b01f8617e86d09fbdff4a52f2f8dbbba297e74f7164b5984f5a0384` (Exact match)
   - Decompressed SHA-256: `b82d6a3e7231d1759a958c282bc4366b80ec2fab8095053d8ed7fa9cd01bc838` (Exact match)
   - Line count: 411,160 rows
   - Sample rows:
     - `{"organisation_number":"810034882","name":"SANDNES ELEKTRISKE AS","legal_form":"AS","employees":11,"bankrupt":false,"liquidating":false,"municipality":"SANDNES","municipality_number":"1108","industry_code":"43.210","industry_label":"Elektrisk installasjonsarbeid","website":"","latest_submitted_accounts":"2025"}`
     - `{"organisation_number":"810059672","name":"AASEN & FARSTAD AS","legal_form":"AS","employees":null,"bankrupt":false,"liquidating":false,"municipality":"MOLDE","municipality_number":"1506","industry_code":"68.200","industry_label":"Utleie av egen eller leid fast eiendom","website":"","latest_submitted_accounts":"2025"}`
     - `{"organisation_number":"810094532","name":"ALSTRAY AS","legal_form":"AS","employees":null,"bankrupt":false,"liquidating":false,"municipality":"ARENDAL","municipality_number":"4203","industry_code":"68.200","industry_label":"Utleie av egen eller leid fast eiendom","website":"","latest_submitted_accounts":"2025"}`

2. **Brønnøysund Bulk Enheter CSV (`data/brreg-enheter.csv`)**:
   - Download URL: `https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv`
   - Compressed GZ size: 154,840,540 bytes (~147.67 MB)
   - Decompressed CSV size: 842,334,024 bytes (~803.31 MB)
   - Download time: 362s (~6m 2s)
   - Row count: 1,471,344 rows
   - Total columns: 90 columns
   - Header line: `"organisasjonsnummer","navn","organisasjonsform.kode","organisasjonsform.beskrivelse","naeringskode1.kode","naeringskode1.beskrivelse","naeringskode2.kode","naeringskode2.beskrivelse","naeringskode3.kode","naeringskode3.beskrivelse","hjelpeenhetskode.kode","hjelpeenhetskode.beskrivelse","harRegistrertAntallAnsatte","antallAnsatte","registreringsdatoAntallAnsatteEnhetsregisteret","registreringsdatoantallansatteNAVAaregisteret","hjemmeside","epostadresse","telefon","mobil","postadresse.adresse","postadresse.poststed","postadresse.postnummer","postadresse.kommune","postadresse.kommunenummer","postadresse.land","postadresse.landkode","forretningsadresse.adresse","forretningsadresse.poststed","forretningsadresse.postnummer","forretningsadresse.kommune","forretningsadresse.kommunenummer","forretningsadresse.land","forretningsadresse.landkode","institusjonellSektorkode.kode","institusjonellSektorkode.beskrivelse","sisteInnsendteAarsregnskap","registreringsdatoenhetsregisteret","stiftelsesdato","registrertIMvaRegisteret","registreringsdatoMerverdiavgiftsregisteret","registreringsdatoMerverdiavgiftsregisteretEnhetsregisteret","frivilligMvaRegistrertBeskrivelser","registreringsdatoFrivilligMerverdiavgiftsregisteret","registrertIFrivillighetsregisteret","registreringsdatoFrivillighetsregisteret","registrertIForetaksregisteret","registreringsdatoForetaksregisteret","registrertIStiftelsesregisteret","registrertIPartiregisteret","registreringsdatoPartiregisteret","konkurs","konkursdato","underAvvikling","underAvviklingDato","underTvangsavviklingEllerTvangsopplosning","tvangsopplostPgaManglendeDagligLederDato","tvangsopplostPgaManglendeRevisorDato","tvangsopplostPgaManglendeRegnskapDato","tvangsopplostPgaMangelfulltStyreDato","tvangsavvikletPgaManglendeSlettingDato","overordnetEnhet","maalform","vedtektsdato","vedtektsfestetFormaal","aktivitet","paategninger","underUtenlandskInsolvensbehandlingDato","underRekonstruksjonsforhandlingDato","fravalgRevisjonDato","fravalgRevisjonBeslutningsDato","erIKonsern","kapital.belop","kapital.antallAksjer","kapital.type","kapital.bundet","kapital.valuta","kapital.innbetalt","kapital.fulltInnbetalt","kapital.innfortDato","registreringsnummerIHjemlandet","utenlandskRegisterNavn","utenlandskRegisterAdresse.land","utenlandskRegisterAdresse.poststed","utenlandskRegisterAdresse.adresse","underlagtLovgivningLand","underlagtLovgivningLandKode","foretaksformIHjemlandet.kode","foretaksformIHjemlandet.beskrivelse","foretaksformIHjemlandet.beskrivelseBokmaal"`

### Live Registry Key Probe Table
Probed 5 diverse organisation numbers from `data/signalpost-universe.jsonl.gz`:
- `810034882` (SANDNES ELEKTRISKE AS)
- `810059672` (AASEN & FARSTAD AS)
- `810324562` (SERVI GROUP AS)
- `810359862` (AUTOBJØRN A/S)
- `810363142` (BJØRNSTJERNE BJØRNSONSGATE AS)

| Key Name | Present in Live API (`/enheter`) | Present in Bulk CSV | Notes / Findings |
|---|---|---|---|
| `hjemmeside` | 1/5 (`810359862`) | Yes (col `hjemmeside`) | Present only when company has declared a website. Only ~14-20% populate this. |
| `epostadresse` | 1/5 (`810034882`) | Yes (col `epostadresse`) | High value for domain discovery (extracting domain from email). |
| `telefon` | 4/5 | Yes (col `telefon`) | Common registry field. |
| `mobil` | 2/5 | Yes (col `mobil`) | Sparse, present on some entities. |
| `vedtektsfestetFormaal` | 4/5 | Yes (col `vedtektsfestetFormaal`) | Narrative purpose in Norwegian. |
| `aktivitet` | 4/5 | Yes (col `aktivitet`) | Narrative activity statement. |
| `naeringskode1` | 4/5 | Yes (`naeringskode1.kode`/`beskrivelse`) | Primary NACE industry classification code. |
| `naeringskode2` | 2/5 | Yes (`naeringskode2.kode`/`beskrivelse`) | Secondary NACE code where applicable. |
| `naeringskode3` | 1/5 | Yes (`naeringskode3.kode`/`beskrivelse`) | Tertiary NACE code where applicable. |
| `antallAnsatte` | 2/5 | Yes (col `antallAnsatte`) | Integer or omitted when 0/unreported. Missing is not zero. |
| `forretningsadresse` | 4/5 | Yes (`forretningsadresse.*`) | Nested object in API (adresse, postnummer, poststed, kommune, kommunenummer, land, landkode). |
| `postadresse` | 2/5 | Yes (`postadresse.*`) | Distinct from forretningsadresse when mail is routed elsewhere. |
| `institusjonellSektorkode` | 4/5 | Yes (`institusjonellSektorkode.kode`/`beskrivelse`) | Institutional sector (e.g. Private AS/foretak). |
| `registreringsdatoEnhetsregisteret` | 4/5 | Yes (`registreringsdatoenhetsregisteret`) | Registration date in Enhetsregisteret (ISO date). |
| `stiftelsesdato` | 4/5 | Yes (col `stiftelsesdato`) | Foundation / incorporation date. |
| `konkurs` | 4/5 | Yes (col `konkurs`) | Boolean flag. Adverse indicator. |
| `underAvvikling` | 4/5 | Yes (col `underAvvikling`) | Boolean flag. Adverse indicator. |
| `overordnetEnhet` | 0/5 | Yes (col `overordnetEnhet`) | Populated only on subunits (`underenheter`), not on main entities. |

### Extended Endpoints Probed
1. **Underenheter (`/underenheter?overordnetEnhet={orgnr}`)**:
   - `810034882` has 3 subunits. **Subunits carry both `hjemmeside` and `epostadresse`!** This confirms a vital discovery lever: subunits can provide domain proof even when the parent entity does not.
   - `810059672` has 1 subunit (no web/email).
   - `810324562` has 0 subunits.
   - `810359862` has 2 subunits.
   - `810363142` has 1 subunit.
2. **Roller (`/enheter/{orgnr}/roller`)**:
   - HTTP 200 for 4/5 entities, returning structured `rollegrupper` (DAGL, STYR, REVI, etc.).
   - Entity `810324562` returned HTTP 404 (no active roles recorded).
3. **Konsernstruktur (`/konsernstruktur/{orgnr}`)**:
   - HTTP 200 for `810363142` (confirming group / holding hierarchy).
   - HTTP 404 for the other 4 entities (not part of registered corporate group hierarchy).
4. **Regnskapsregisteret (`https://data.brreg.no/regnskapsregisteret/regnskap/{orgnr}`)**:
   - HTTP 200 for all 5 entities.
   - **Every entity returned exactly 3 accounting years** (2024, 2023, 2022) with full income statement and balance sheet lines.

### Removed Files (Source Policy & Forbidden Connectors)
Removed 10 legacy files adhering to AGENTS.md source policy (reason: `source policy: restricted platforms / obsolete`):
1. `scripts/run_linkedin_guest_experiment.py`
2. `scripts/run_linkedin_guest_jobs_connector.py`
3. `scripts/discover_linkedin_company_profiles.py`
4. `scripts/run_google_news_rss_connector.py`
5. `scripts/run_youtube_search_connector.py`
6. `scripts/normalize_google_maps_results.py`
7. `scripts/run_fagfolkguiden_reviews_connector.py`
8. `scripts/run_sentiment_model.py`
9. `src/norway_company_agent/sentiment.py`
10. `scripts/score_competition_v3.py` (scored obsolete 55/15/10/12/8 rubric)

## Phase 1: Evaluation Harness & Starter Baseline
- **Evaluation Splits**:
  - Deterministically stratified from `data/signalpost-universe.jsonl.gz` using fixed seed (`seed=42`).
  - `dev` (150 companies, SHA-256: `0d81c410d630e60ef5b2835286863359eb8e19644528a3a5da26f4039f9fc090`, guaranteed 28 registry websites).
  - `val` (150 companies, SHA-256: `8e482fde0d02f658f3fe05c891f535fbf77184f54c53632892a2f8fc00058edc`, 28 registry websites).
  - `holdout` (200 companies, SHA-256: `3c4fd69b43f44c918bf0c10a54153fdd0d52840b6e654de58880ffd364bee5d6`, 36 registry websites). Untouched until final submission.
  - `stress` (60 companies, SHA-256: `47eaa711713cd399a359e6c12e5639664f437bc824cd2ed795d59593f517807f`): 10 bankrupt, 10 liquidating, 10 missing filings, 10 diacritic-rich names, 10 token collision pairs (5 pairs), 10 special legal forms (`NUF`, `BRL`, `ESEK`, `STI`).
  - Verified 100% pairwise disjoint sets (0 duplicate organisations across splits).
  - All 560 organisation numbers verified Modulo-11 valid via `signalpost.ref.orgnr.is_valid`.
- **Manual Labelling Interface**:
  - Created `eval/label.py` generating `eval/dev-labels-template.csv`, `eval/dev-labels-template.jsonl`, and interactive browser review interface `eval/labels/sheet.html`.
  - Estimated labelling effort: ~1.5 min per company (~3.7 hours total for 150 companies).
  - Initial seed gold dataset committed at `eval/gold/dev_labels.jsonl`.
- **Metrics & Promotion Gate**:
  - Implemented `eval/score.py` computing family coverage, claim density, proxy recall (0.7 company + 0.3 claims), website precision against gold, evidence backing, and Builderr competition proxy.
  - Implemented `eval/promote.py` enforcing rule N10: 0 new wrong-company publications, non-decreasing precision, 100% span validity, +1.0 min recall gain, p95 <= 60s. Decision log saved under `reports/decisions/`.
  - Eval test suite: `eval/test_eval.py` (9 tests passing).
- **Baseline Starter Measurement**:
  - Executed unmodified starter batch against 150 dev companies (`out/baseline-dev-raw.jsonl`).
  - Runtime: 165.9 seconds across 8 worker threads; 918 HTTP requests (6.12 req/co), 17.38 MB.
  - Registry website present in dev: 18.67% (28 / 150 companies).
  - Passing starter identity gate: 16.67% (25 / 150 companies).
  - Roles coverage: 100.0% (150 / 150 companies, 677 claims).
  - Subunits coverage: 77.33% (116 / 150 companies, 120 claims).
  - Financials coverage: 82.67% (124 / 150 companies, 323 claims).
  - Proxy Score: Recall 29.60, Evidence 30.00, Synthesis 7.20, UX 3.20 (Total: 70.00).
  - Calibrated against Builderr official leaderboard baseline: Starter scores 42.21 (best entry 45.59; qualification target 65.0+).

## Phase 2: Batch Runner & Superset Result Envelope
- Integrated `signalpost.ref.guard` (`parse_inputs`, `Deadline`, `EnvelopeWriter`, `run_batch`) and `signalpost.ref.envelope` (`new_envelope`, `make_evidence`, `make_claim`, `finalize`, `failure_envelope`).
- Created `src/signalpost/envelope_adapter.py` mapping profile records into contract envelopes adhering to `OUTPUT_CONTRACT.md` and the 6 required terminal states: `available`, `not_available`, `blocked`, `not_applicable`, `ambiguous`, `failed`.
- Created `src/signalpost/run.py` and `run_agent.py` supporting CLI flags (`--organisations`/`--input`/`-i`, `--bulk`, `--output`/`-o`, `--report`, `--expected-count`, `--workers`, `--time-budget`, `--resume`, `--offline`, `--no-llm`).
- Ensured malformed inputs, duplicates, and missing organisation numbers never abort the run or raise unhandled exceptions.
- Added fault-injection test suite `tests/test_runner_faults.py` covering chaos inputs, worker failures, timeouts, resume idempotency, and SSRF prevention.
