# Known Technical Limitations — Signalpost

This document details known limitations, architectural boundaries, and scope constraints of the Signalpost Norwegian company research agent.

## 1. Hiring Family Scope
- **Source**: NAV Arbeidsplassen public feed (`pam-stilling-feed`) and company-owned career pages.
- **Limitation**: Private job boards that forbid scraping (such as Finn.no, LinkedIn Jobs, Indeed, and Glassdoor) are **strictly excluded** in accordance with Rule N5.
- **Coverage Impact**: Job openings posted exclusively on Finn.no or LinkedIn without cross-listing on NAV or the company website are not ingested. Signalpost records this state explicitly as `not_available` with reason code `no_active_nav_listings`.
- **Privacy Enforcement**: Inactive ads are pruned immediately. Contact person names, direct telephone lines, and personal email addresses (`contactList`) are discarded per NAV data protection terms.

## 2. Social Media & External Profiles
- **Rule N5 Enforcement**: Signalpost **never** fetches, scrapes, or queries platform pages directly (LinkedIn company pages, Facebook profiles, Instagram accounts, X/Twitter handles, YouTube channels).
- **Evidence Boundary**: Social profiles are recorded **only** if explicitly declared as outbound links on a verified company website (post-identity proof).
- **Result**: The profile URL is published as a verified claim anchored in the company's HTML homepage snapshot, but metrics like follower count, engagement, and feed posts are not extracted.

## 3. Press, News & Media Monitoring
- **Limitation**: Third-party paywalled news portals (Dagens Næringsliv, E24, Finansavisen) and Google News RSS feeds are **forbidden and excluded**.
- **Evidence Boundary**: Corporate press releases, news items, and blog posts are sourced exclusively from verified company-owned RSS/Atom feeds, WordPress REST APIs (`/wp-json`), and company newsrooms. Companies without an RSS feed or open sitemap yield `not_available` (`no_company_feed_found`).

## 4. Search API Dependency & Transient Discovery
- **Discovery Strategy**: When candidates are not found in the Brønnøysund registry (`hjemmeside`, email domain, subunit domains) or legal name probing, search APIs (e.g., Brave Search) may suggest candidate domains.
- **Transient Policy**: Queries, titles, snippets, and ranks are **never** stored or used as evidence. Every candidate domain must independently prove identity by exhibiting the company's 9-digit organisation number on the fetched page (Rule N2).
- **Coverage Impact**: If a company's website does not display its 9-digit organisation number anywhere on its pages (e.g. footer, impressum, privacy policy, contact page), Signalpost conservatively classifies the domain as unverified (`ambiguous` or `not_available`). A wrong company is fatal; an abstention preserves a 0% false-positive rate.

## 5. Language Support
- **Primary Languages**: Norwegian (Bokmål / Nynorsk) and English.
- **Multilingual Web**: Text extraction and synthesis operate on Unicode normalized text (handling Norwegian characters `æ`, `ø`, `å`). Sites solely in other languages (German, Swedish, Polish) are processed using structural JSON-LD schemas and exact organisation number patterns without semantic translation.

## 6. Financial Snapshots & PDF OCR
- **Primary Source**: Regnskapsregisteret open API.
- **PDF Filing Fallback**: When API data is delayed or incomplete, annual report PDF filings are parsed using `pypdf`. Scanned image-only PDFs lacking embedded text layers require OCR engines which are excluded to keep execution lightweight, deterministic, and free of heavy external binary runtimes.
