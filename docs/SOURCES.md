# Allowed Sources & Rate Limits — Signalpost

This document details the permitted and forbidden sources in accordance with Rule N5 of `AGENTS.md`.

## 1. Permitted Sources Ladder

### 1. Brønnøysund Register Centre Open Data (NLOD 2.0)
- **Authority**: The Brønnøysund Register Centre (Brønnøysundregistrene).
- **Licence**: Norwegian Licence for Open Government Data (NLOD 2.0).
- **Permitted Endpoints**:
  - `https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}` (Enhetsregisteret live API)
  - `https://data.brreg.no/enhetsregisteret/api/underenheter?overordnetEnhet={orgnr}` (Subunits)
  - `https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}/roller` (Role registry)
  - `https://data.brreg.no/enhetsregisteret/api/konsernstruktur/{orgnr}` (Corporate group structure)
  - `https://data.brreg.no/regnskapsregisteret/regnskap/{orgnr}` (Regnskapsregisteret annual accounts)
  - `https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv` (Bulk downloadable snapshots)
- **Rate Limits & Etiquette**:
  - Max ~30 requests per minute on live registry endpoints.
  - Bulk datasets preferred for full-universe filtering.
  - Custom User-Agent identifying the agent (`signalpost-research-agent/1.0`).

### 2. Company-Owned Websites (Post-Identity Proof Only)
- **Authority**: Self-published by the company on verified domains.
- **Access Rule**: Published ONLY AFTER exact-entity proof (org-number-on-page or name + address mod-11 validation, Workflow /03).
- **Scope**: Homepages, about/contact pages, RSS/Atom feeds, `/wp-json` endpoints, JSON-LD schema, outbound social links.
- **Safety**:
  - Strictly observe `robots.txt`.
  - Assert public URLs only (no private IPs or SSRF).
  - Bounded fetch limits: max 5 bounded pages per company, timeout 10 seconds.
  - Social platform links found on site recorded as outbound profile URLs only; the platform page is NEVER fetched.

### 3. NAV Arbeidsplassen Official Job Feed (`pam-stilling-feed`)
- **Authority**: The Norwegian Labour and Welfare Administration (Arbeids- og velferdsetaten - NAV).
- **Access**: Official public feed. Ads are keyed by `employer.orgnr`.
- **Compliance Rules**:
  - Inactive ads are pruned/dropped immediately upon termination.
  - The `contactList` field is NEVER persisted or published (privacy protection).

### 4. Search API (Brave Search / Similar)
- **Role**: Candidate domain discovery ONLY.
- **Rule**: Search results are transient. Search queries, snippets, ranks, and titles are NEVER written to disk or result envelopes.
- **Evidence**: Evidence is exclusively the independently fetched company page after identity proof.

---

## 2. Forbidden Sources (Zero Tolerance)
The following sources and mechanisms are strictly forbidden by contest rules:
1. **Restricted Platform Scraping**:
   - LinkedIn, Facebook, Instagram, Glassdoor, Indeed, Finn.no (scraping or unofficial APIs).
2. **Search Engine Result Scraping**:
   - Google or Bing HTML search result scraping.
3. **Registry Bulk Scraping & Norid**:
   - Proff.no, Allabolag, 1881.no, Gulesider scraping.
   - Bulk Norid or WHOIS lookups (Norid's terms explicitly forbid storing or bulk harvesting).
4. **Access Restrictions**:
   - Anything behind a login, paywall, CAPTCHA, or anti-bot protection.
   - Any bypass of `robots.txt`.
5. **Personal Data Restrictions**:
   - Personal email addresses, personal phone numbers, and birth dates of individuals.
