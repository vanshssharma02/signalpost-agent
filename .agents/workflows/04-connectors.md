---
description: Phase 4 - NAV Arbeidsplassen job feed (official, keyed by organisation number) and structured extraction from verified company sites (activity, profiles, brand, careers).
---

# /04-connectors  (about 2 days)

Goal: add the external families that count for recall (hiring, dated public activity, company-owned profiles, brand) with exact-company precision. Breadth across companies beats depth per company: one verified, dated claim for many companies is worth more than many claims for a few.

## A. NAV Arbeidsplassen job feed (hiring family)
Read https://navikt.github.io/pam-stilling-feed/ FIRST and record the real endpoints, auth header, paging, If-Modified-Since behaviour and ad fields in docs/DECISIONS.md. Do not trust remembered URL paths. What the docs promise (verify): a public feed of ads from arbeidsplassen.nav.no (Finn.no ads are NOT included), bearer token auth, a public experiment token that rotates, ad detail with employer{name, orgnr, homepage}, drop ads that are no longer active, never store or expose the contact list.
1. Token: use env NAV_FEED_TOKEN; else fetch the public token at run time. Credentials tied to the entrant's personal account are not allowed in the official run (Builderr cannot reproduce them), so the public-token path must work, and the question "is the public token acceptable?" is in docs/BUILDERR_EMAIL.md. Missing/expired token = family `failed` (reason nav_token), never a crash.
2. Spike S1 (timebox 2 h, report numbers): how many feed entries and pages exist for If-Modified-Since = now - 30 days and now - 180 days, bytes, seconds, how many distinct active ads, how many dev companies have at least one ad. Decide between two strategies and register both:
   - nav_name_match: index feed entries by normalised businessName; for each target find entries whose normalised name equals or contains the normalised legal name or registered brand; fetch ad detail only for those; accept only if employer.orgnr == target exactly.
   - nav_full_detail: fetch every active ad detail (concurrency 8-16, ETag/If-Modified-Since) and index by employer.orgnr; exact, higher recall for brand-vs-legal-name mismatches, costs more requests. Pick by measured recall and runtime.
3. Claims, one per active ad: field job_posting, discriminator = ad uuid, value {title, employer_name, location, extent, engagement_type, published, expires, apply_by, source_ad_url}, published_at = published date, reporting_period = {from: published, to: expires}, evidence source_url = the public ad page (human-verifiable), claim_span = the verbatim JSON fragment with orgnr and title from the stored ad snapshot (hash it, store gz). identity_proof orgnr_exact, source_class public_platform_api. No personal data: drop contactList, applicant e-mails/phones.
4. States: feed read fully and zero ads for the orgnr -> `not_available` (reason none_in_nav_feed; say in the synthesis that Finn.no and private channels are not covered); feed failed -> `failed`; 401/403 -> `blocked`.
5. By-products: employer.homepage with the matching orgnr feeds website strategy S-D from /03 (still must pass proof). Job counts feed the hiring-signal sentence.
6. Tests with recorded feed fixtures: exact match; same-name different orgnr (must reject); ad with no employer.orgnr (reject); inactive ad (drop); duplicate ads (one claim per uuid); pagination; token expiry; rate limit.

## B. Extraction from verified company sites (families activity, company_profiles, brand, hiring, locations)
Only run on sites whose website claim passed proof (P1/P2). Everything is deterministic first:
1. JSON-LD via extruct (Organization/LocalBusiness: name, alternateName, legalName, address, telephone, sameAs; JobPosting; NewsArticle/BlogPosting/Article: headline, datePublished, url).
2. Feeds: `<link rel="alternate" type="application/rss+xml|atom+xml">`, /feed, /rss, /nyheter/feed; WordPress REST /wp-json/wp/v2/posts?per_page=5&_fields=link,title,date when the page signals WordPress.
3. Sitemap: /sitemap.xml and index files, `lastmod` for URLs under /nyheter, /aktuelt, /blogg, /news, /presse, /pressemeldinger, /artikler.
4. HTML listing pages: `<time datetime>`, og:article:published_time, `meta name=date`. Visible text dates in Norwegian ("12. september 2026") only as a last resort and flagged confidence 0.7.
5. Claims:
   - company_news_item: {title, url, published_at}, up to 5 newest within 24 months, discriminator canonical URL, evidence = page or feed snapshot with the verbatim title+date span; source_class company_owned, never labelled independent press.
   - careers_page and job_posting (site): JobPosting JSON-LD on /karriere, /jobb, /ledige-stillinger, /career(s); record ATS links (Webcruiter, Easycruit, Teamtailor, Recman, Varbi, Jobylon, Lever, Greenhouse) as careers_page claims; do not call their APIs in v1. If the same job appears in NAV and on the site, keep both claims (different sources, different claim_ids) and link them with a `duplicate_of_hint` in the value.
   - company_profile (linkedin, facebook, instagram, x, youtube, tiktok): URL declared by the verified site, normalised (lowercase host, strip tracking params and trailing slash, canonical linkedin.com/company/<slug>), evidence = the site page snapshot with the anchor markup as span. Never fetch the platform page itself (platform terms). Publish only if (a) in JSON-LD sameAs of the Organization node, or (b) in header/footer of at least two pages, or (c) handle shares a distinctive name token (starter rule). Reject share/intent/login links, links inside footer credits like "Design by", "Laget av", "Powered by", links to well-known agency or platform pages, personal profiles (linkedin.com/in/).
   - public_brand: og:site_name, JSON-LD name/alternateName, title before separator, when different from the legal name.
   - contact: organisation-level e-mail (post@, info@, kontakt@, firmapost@) and main phone only; never personal e-mails or personal mobile numbers.
   - locations: addresses on the contact page are CORROBORATION of registry subunits (claim `office_address_site` with identity from the verified site); never override registry.
6. Budget per site: at most 8 pages, 1.5 MB each, 40 s total; stop early when families are filled.
7. Precision rules: a page counts only if on the verified registrable domain (subdomains allowed if the apex is verified); content in iframes from other hosts ignored; text from cookie banners ignored.

## C. Stretch spikes (each timeboxed to half a day; keep only if the promotion gate passes and the source terms allow it; record terms in docs/SOURCES.md)
1. Registry change feed (Brreg /oppdateringer/enheter) as dated activity and as the refresh signal.
2. OpenStreetMap via Overpass: objects with ref:NO:orgnr and website/phone; the tag often holds a subunit number, map to the parent via underenheter; ODbL attribution required; check the harness network policy first.
3. TED/Doffin procurement awards that name the company by organisation number (dated public activity).
4. Wikidata items carrying the Norwegian organisation number (few small firms; low value, last).
Anything needing an outbound host the harness may block is useless; ask Builderr (docs/BUILDERR_EMAIL.md) before investing.

## Acceptance (paste real output)
- Fixture tests for A and B green; `uv run pytest -q` green.
- On `dev`: per family coverage table before/after, claims per covered company, wrong-company = 0, validator passed with --snapshots, runtime and request counts, S1 numbers, and the chosen NAV strategy with reasons.
- Human label check: 20 job claims, 20 news items, 30 profile links reviewed against stored spans; any wrong item is a blocker.
- Tag `phase4`. Stop and report.
