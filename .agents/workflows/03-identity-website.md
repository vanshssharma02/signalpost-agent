---
description: Phase 3 - exact-company proof and website discovery for the 85-90 percent of companies whose registry record lists no website. The biggest recall lever and the biggest risk.
---

# /03-identity-website  (about 2 days)

Goal: find and PROVE the official website of as many companies as possible with zero wrong-company publications. Only about 14 percent of the universe lists a website in the registry (138 of 1,000 in the kit's own submission sample, 25 of 250 in its extension sample), so the unmodified starter finds a site for roughly one company in seven. Everything else (profiles, news, careers, brand) hangs off a verified site.

## Principle
The organisation number is the key. Norwegian companies are expected to show their organisation number and name on their website (foretaksregisterloven / ehandelsloven, treat as a strong prior, not a guarantee; measure the hit rate on dev instead of trusting it). A candidate URL is NEVER evidence. A page is evidence only if it passes the proof below. LLMs never decide identity. If unsure: `ambiguous` or `not_available`, never publish.

## Candidate sources (register each as a strategy in config/strategies.toml with a version; build them in this order and measure each on `dev` before the next, rule N10)
S-A registry_homepage: hjemmeside from the registry record (normalise: add scheme, strip spaces/paths/utm, reject if host is a social, directory or marketplace domain; a Facebook page there is a profile candidate, not the website).
S-B registry_email_domain: domain of the registry epostadresse, only if it is a business domain (reference domains.email_domain_candidate rejects gmail, hotmail, ISP mail).
S-C subunit_homepage: hjemmeside/epostadresse of the company's subunits from the underenheter call you already make.
S-D nav_employer_homepage: employer.homepage from NAV job ads whose employer.orgnr equals the target (comes free from /04; wire the dict in later).
S-E domain_guess: reference domains.candidate_hosts(legal_name) (ascii-folded, no-/oe-variants, joined and hyphenated, .no then .com, max 12). DNS first (3 s timeout, drop NXDOMAIN), then HTTPS GET. Costs no money; hit rate unknown, measure it.
S-F search_orgnr: only if SEARCH_API_KEY is set. Query the organisation number in both spacings ("985 821 585" and "985821585") plus, second query, the legal name with postal code and town. Take at most the top 5 result URLs of each, drop blocklisted hosts, and treat them purely as candidates. Search results are transient: do not write titles, snippets, ranks, query text or raw responses to disk, envelopes or logs (Brave's terms forbid storing or caching results beyond transient operation). Evidence is only the page you fetch yourself. Log only counts and cost. No key: skip and set reason search_not_configured.
Not allowed: Norid/WHOIS lookups at scale (Norid forbids copying or storing its lookup data), scraping Google/Bing/DDG result pages, directories (proff, 1881, gulesider, allabolag...), LinkedIn/Facebook/Instagram pages.

## Effort allocation
Compute site_prior(company) from legal form, employee bucket, NACE division (holding companies 64.2xx and housing co-ops/condominiums BRL/ESEK rarely have sites), presence of a business email domain. Run S-E and S-F in descending prior until the time budget or the per-run search budget is spent. Learn the priors from `dev` labels only. A skipped company gets `not_available` with reason skipped_low_prior (honest: not checked deeply).

## Fetch policy (all candidates)
https first then http; at most 5 redirects, each hop through assert_public_url (no private/loopback/link-local IPs, ports 80/443 only); connect 5 s, read 10 s, max 1.5 MB, html/xml/json/text only; robots.txt respected and cached per host; User-Agent with a contact URL; per-host concurrency 2 and 1 request/second; honour 429 Retry-After once then give up with state blocked; 403/401/captcha markers = blocked (do not try to evade). Detect parked/for-sale pages (starter has a marker list; extend with Norwegian wording). Fetch the home page plus up to 5 legal/contact pages found by link text or path: /kontakt, /kontakt-oss, /om-oss, /om, /personvern, /personvernerklaering, /vilkar, /salgsvilkar, /betingelser, /cookies, /impressum, /about, /contact, /privacy, /terms. Footers are where org numbers live.

## Proof (implement in src/signalpost/identity_proof.py on top of ref.orgnr.assess_page)
Let family = target orgnr + its subunit orgnrs + parent/child orgnrs from konsernstruktur.
P1 exact: a mod-11-valid occurrence of the target number, in any accepted format ("Org.nr. 985 821 585", "NO 985.821.585 MVA", JSON-LD vatID/taxID/identifier), on a page of the SAME registrable domain, and no other valid organisation number that is labelled (org.nr / organisasjonsnummer / MVA) and outside `family` on the same page. Publish `official_website`.
P2 strong, only if the page has no org number at all: ALL of (a) all distinctive legal-name tokens in title/H1/footer/JSON-LD name, (b) the registered street address AND postal code in the text, (c) the registered phone, or the registry email domain equals the site domain, or a registry role holder name appears on the team/contact page. Confidence 0.9, identity_proof strong_combo. Anything weaker is rejected.
Rejections (record reason codes): host_blocklisted, parked_page, other_org_labelled, group_or_portfolio_page (3 or more distinct valid org numbers), belongs_to_parent_or_sister (family member's number present without ours), name_only_match, address_only_match, no_proof, dead, blocked, wrong_language_or_empty, redirected_to_different_company.
Group sites, franchise sites, agency portfolios and parent sites are NOT exact matches; if you want to keep them, publish a separate claim `related_group_site` that is clearly labelled, never `official_website`.

## Outcomes per company (field_state website)
available (>=1 candidate passed P1/P2, choose the one with the strongest proof, tie -> shortest registrable domain, ties across different domains -> ambiguous), ambiguous (two different registrable domains both pass, or only partial proof), blocked (every plausible candidate refused us), failed (network/our error after retries), not_available (ladder exhausted, nothing passed; say which sources ran), not_applicable (company deleted/bankrupt). Also emit `public_brand` claims (og:site_name, JSON-LD name/alternateName, title before the separator) from verified pages only.

## Anti-contamination tests (tests/test_identity.py; each fixture is a saved HTML file under tests/fixtures/identity/)
sister company on a shared group site; franchise sites with the same brand and different org numbers; agency portfolio listing 20 customer org numbers; two companies with near-identical legal names; directory page that prints the org number; Facebook page as registry homepage; domain-for-sale page; org number only inside an image (must NOT pass P1); org number in a different valid format; NUF branch pointing at the foreign parent's site; sole proprietorship with a personal name; page that mentions our org number once in a customer list among many others; look-alike TLD (.com vs .no) belonging to another firm. Expected verdicts are written down BEFORE the code. Every rejected fixture must have the right reason code.

## Measurement loop (rule N10)
For each strategy S-A ... S-F: run on `dev`, produce reports/website-<strategy>.json (published count, newly covered companies, wrong-company count from labels, cannot-tell count, requests, seconds, cost). Promote only if wrong-company = 0 and cannot-tell cases are resolved by reading the evidence span yourself. Ask the human to label every NEW publication on `dev` (the label sheet shows the stored claim_span). Print the funnel: candidates generated -> reachable -> proof P1 -> proof P2 -> published, per strategy. Keep a discovery trace file out/discovery_trace.jsonl (orgnr, strategy, candidate host, verdict, reason code, ms), never containing search titles/snippets.

## Acceptance (paste real output)
- All identity fixtures pass; `uv run pytest -q` green.
- On `dev`: wrong-company publications = 0 (hard stop otherwise), website coverage reported against the baseline from /01, per-strategy marginal coverage table, funnel, runtime and cost per company.
- Validator passes on the envelopes (every website claim has a verbatim claim_span containing the org number or the P2 evidence).
- docs/IDENTITY_RESOLUTION.md documents proof levels, reason codes, blocklist and thresholds, and one worked example per verdict.
- Tag `phase3`. Stop and report. If coverage gain is small, report the funnel honestly and propose the next experiment; do not lower the proof bar to inflate coverage.
