# Identity Resolution & Exact-Entity Proof Specification

This document details the exact-company proof framework and website discovery ladder implemented for Signalpost (Workflow `/03`), adhering strictly to **Rule N2** and **Rule N3** of `AGENTS.md`.

---

## 1. Core Principles

1. **The Organisation Number is the Only Key**:
   - Norwegian corporate law (*foretaksregisterloven* § 10-2, *ehandelsloven* § 8) requires commercial websites to clearly display the company's organisation number, legal name, and physical address.
   - We treat the organisation number as the primary cryptographic key for domain verification.
   - Name similarity, Google/Bing search rankings, and LLM assertions are **candidates only**, never proof.
   - LLMs never decide identity.
2. **Zero Wrong-Company Tolerance**:
   - In the Builderr scoring rubric, an unverified or material wrong-company publication is fatal.
   - If evidence is ambiguous, contradictory, or absent, the field state MUST be recorded as `ambiguous` or `not_available`. Never guess.
3. **Verbatim Traceable Evidence**:
   - Every published website claim is accompanied by an immutable content-hash snapshot (`content_sha256`), retrieval timestamp, source class (`company_owned`), and a verbatim `claim_span` present in the snapshot.

---

## 2. Proof Ladder & Verification Levels

| Proof Level | Verdict | Confidence | Criteria | Publication Field |
| :--- | :--- | :--- | :--- | :--- |
| **P1 Exact** | `exact` | 1.00 | Modulo-11 valid target org number present in visible text or JSON-LD (`vatID`, `taxID`, `identifier`) on the **same registrable domain**, AND **no conflicting foreign labelled organisation number** outside the corporate family. | `official_website` |
| **P2 Strong** | `strong_combo` | 0.90 | **Zero organisation numbers** on the entire page/site, plus the conjunction of: <br>1. All distinctive legal name tokens in title, H1, or JSON-LD.<br>2. Registered street address AND 4-digit postal code in text.<br>3. Registered phone number OR official email domain matching site domain OR registered role holder name in text. | `official_website` |
| **Rejected** | `rejected` | 0.00 | Does not satisfy P1 or P2, or triggers any rejection barrier. | Dropped / `not_available` |

---

## 3. Website Discovery Ladder

Candidates are evaluated hierarchically across 6 rungs. Evaluation halts at the earliest rung yielding a verified site:

1. **Rung 1 (S-A) — Registry Homepage (`registry_homepage`)**:
   - Hjemmeside recorded in Brønnøysund Enhetsregisteret bulk snapshot or live API.
   - Stripped of tracking parameters, normalized scheme, rejected if host is blocklisted.
2. **Rung 2 (S-B) — Registry Email Domain (`registry_email_domain`)**:
   - Domain extracted from registered `epostadresse`.
   - Consumer webmail providers (`@gmail.com`, `@online.no`, `@hotmail.com`, etc.) are filtered out via `email_domain_candidate`.
3. **Rung 3 (S-C) — Subunit Sites & Emails (`subunit_homepage`)**:
   - Subunit (`underenheter`) registered homepages and email domains from the Brønnøysund subunits registry.
4. **Rung 4 (S-D) — NAV Job Ad Employer Homepage (`nav_employer_homepage`)**:
   - Verified employer homepage attached to active job postings where `employer.orgnr == target_orgnr`.
5. **Rung 5 (S-E) — Deterministic Legal-Name Domain Guessing (`domain_guess`)**:
   - Generated using `candidate_hosts(legal_name)` (ASCII folding, Norwegian vowel normalization `ae`/`oe`/`aa`, hyphenated and concatenated variants, testing `.no` then `.com`, up to 12 candidates).
   - Fast 3-second DNS pre-check drops NXDOMAINs before issuing HTTP requests.
6. **Rung 6 (S-F) — Transient Search Queries (`search_orgnr`)**:
   - Enabled only when `SEARCH_API_KEY` is configured in the environment.
   - Executes exact queries for spaced and compact org numbers (`"985 821 585"`, `"985821585"`) and legal name with postal town.
   - Top 5 candidate URLs are collected; raw search responses, snippets, and query text are immediately discarded without persisting to disk or envelopes.

---

## 4. Rejection Reason Codes

When a candidate fails verification, the engine logs a structured reason code to `out/discovery_trace.jsonl`:

| Reason Code | Description |
| :--- | :--- |
| `host_blocklisted` | Domain belongs to a known directory, social media platform, or generic hosting service. |
| `parked_page` | Page contains domain parking, for-sale, or expiration markers (Norwegian or English). |
| `other_org_labelled` | A valid organisation number with explicit label (`org.nr`, `organisasjonsnummer`, `MVA`) belonging to an unrelated entity is found. |
| `group_or_portfolio_page` | Page displays $\ge 3$ distinct valid organisation numbers (e.g. web agency customer lists, supplier directories). |
| `belongs_to_parent_or_sister`| A family organisation number (parent or sister entity) is present, but target orgnr is absent. Published separately as `related_group_site` if desired, never `official_website`. |
| `name_only_match` | Company name tokens appear, but address and tertiary signals are missing (fails P2). |
| `address_only_match` | Address matches, but company name or tertiary signals are missing (fails P2). |
| `no_proof` | Candidate page loads, but displays no identity proof markers. |
| `dns_resolution_failed` | Domain does not resolve in DNS (NXDOMAIN or DNS timeout). |
| `robots_disallowed` | Robots exclusion protocol (`robots.txt`) forbids crawler access. |
| `blocked_url` | URL targets private/local IP, loopback, non-standard port, or exceeds redirect bounds. |
| `wrong_language_or_empty` | Page returned less than 30 characters of text or empty body. |
| `redirected_to_different_company` | Redirect resolves to an unrelated third-party domain. |

---

## 5. Blocklists & Guardrails

### 5.1 Host Blocklist (`BLOCKLISTED_HOSTS`)
The following registrable domains are never accepted as company websites:
- **Directories**: `proff.no`, `1881.no`, `gulesider.no`, `allabolag.se`, `purehelp.no`, `regnskapstall.no`, `dn.no`, `e24.no`, `brreg.no`.
- **Social Networks**: `facebook.com`, `fb.com`, `linkedin.com`, `instagram.com`, `twitter.com`, `x.com`, `tiktok.com`, `youtube.com`.
- **Platforms / Marketplaces**: `finn.no`, `mittanbud.no`, `tjenestetorget.no`, `github.com`, `gitlab.com`, `medium.com`, `wordpress.com`, `wixsite.com`, `squarespace.com`.

### 5.2 Parked Page Markers
Pages containing any of the following normalized phrases are rejected:
- *English*: "domain for sale", "buy this domain", "inquire about this domain", "parked domain", "domain has expired".
- *Norwegian*: "kjøp dette domenet", "domenet er til salgs", "domenet har utløpt", "websiden er under utvikling", "nettside kommer snart", "kommer snart".

---

## 6. Worked Examples per Verdict

### Example 1: Verdict `exact` (P1 Exact)
- **Target Company**: `985821585` (SANDNES ELEKTRISKE AS)
- **Candidate URL**: `https://sandneselektriske.no`
- **Page Snippet**: `<footer><p>Org.nr: NO 985.821.585 MVA | Fabrikkveien 1, 4306 Sandnes</p></footer>`
- **Assessment**: Target number matches Modulo-11, host is `sandneselektriske.no` (not blocklisted), no foreign orgnr labelled.
- **Verdict**: `exact` (`p1_exact`), claim span: `"Org.nr: NO 985.821.585 MVA | Fabrikkveien 1, 4306 Sandnes"`.

### Example 2: Verdict `strong_combo` (P2 Strong)
- **Target Company**: `912345678` (NORDIC SOLAR INSTALLASJON AS)
- **Registered Address**: `Solheimsveien 12, 5054 Bergen`
- **Role Holder**: `Kari Nordmann`
- **Candidate URL**: `https://nordicsolar.no`
- **Page Snippet**: `<h1>Nordic Solar Installasjon</h1><p>Besøk oss i Solheimsveien 12, 5054 Bergen. Daglig leder Kari Nordmann.</p>`
- **Assessment**: Page has 0 organisation numbers. Legal name tokens matched in H1; street address and postal code matched; role holder matched.
- **Verdict**: `strong_combo` (`p2_strong`), claim span: `"Solheimsveien 12, 5054 Bergen"`.

### Example 3: Rejected — `group_or_portfolio_page`
- **Target Company**: `985821585` (KUNDE A AS)
- **Candidate URL**: `https://saasnordic.no/kunder`
- **Page Snippet**: Agency page listing 20 customer logos with organisation numbers for each client.
- **Assessment**: $\ge 3$ distinct valid organisation numbers detected on page.
- **Verdict**: `rejected`, reason: `group_or_portfolio_page`.

### Example 4: Rejected — `other_org_labelled`
- **Target Company**: `980502155` (TIDETEC AS)
- **Candidate URL**: `https://tidetec.com`
- **Page Snippet**: `<h1>Tidetec</h1><footer>Org.nr. 998 877 665</footer>`
- **Assessment**: Page shows valid organisation number `998877665`, which does not equal target and is outside corporate family.
- **Verdict**: `rejected`, reason: `other_org_labelled`.

### Example 5: Rejected — `belongs_to_parent_or_sister`
- **Target Company**: `988077917` (SUBSIDIARY BETA AS)
- **Corporate Family**: Parent `985821585` (NORDIC GROUP AS)
- **Candidate URL**: `https://nordicgroup.no`
- **Page Snippet**: `<h1>Nordic Group</h1><footer>Org.nr: 985 821 585 MVA</footer>`
- **Assessment**: Parent organisation number is present, but subsidiary target number is missing. Target is not the group entity.
- **Verdict**: `rejected`, reason: `belongs_to_parent_or_sister`.

### Example 6: Rejected — `parked_page`
- **Target Company**: `985821585` (SANDNES ELEKTRISKE AS)
- **Candidate URL**: `https://sandneselektriske.no`
- **Page Snippet**: `<h1>sandneselektriske.no</h1><p>Domenet er til salgs. Kontakt megler.</p>`
- **Assessment**: Normalized text matches parked marker `domenet er til salgs`.
- **Verdict**: `rejected`, reason: `parked_page`.

### Example 7: Rejected — `host_blocklisted`
- **Target Company**: `985821585` (SANDNES ELEKTRISKE AS)
- **Candidate URL**: `https://proff.no/selskap/sandnes/985821585`
- **Assessment**: Registrable domain `proff.no` is in `BLOCKLISTED_HOSTS`.
- **Verdict**: `rejected`, reason: `host_blocklisted`.
