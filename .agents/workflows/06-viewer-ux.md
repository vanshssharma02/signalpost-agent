---
description: Phase 6 - static, mobile-first company viewer generated from the envelopes (UX is 8 points; most entries score 1.6-3.2).
---

# /06-viewer-ux  (about 1 day)

Goal: a person (or a reviewing model) can find a company, understand it in 20 seconds, compare it and verify every claim in two clicks, on a phone and on a desktop. Builderr checks "find, compare, verify" on desktop and mobile. We do not know whether they open a hosted URL or the files from a run, so produce both: a self-contained `site/` folder that works from file:// and is also published (GitHub Pages) with the link in README.

## Build
`python -m signalpost.viewer --envelopes out/envelopes.jsonl --out site/` (no network at build or view time, no external fonts/CDN, no framework required; plain HTML+CSS+small vanilla JS). Output: site/index.html, site/data/index.json (compact list), site/data/<orgnr>.json, site/c/<orgnr>.html (static, server-less), site/assets/. Keep index.json under 400 KB for 1,100 companies. HTML-escape everything (the data comes from the web; treat it as hostile), add a strict CSP meta tag, no inline event handlers from data.

## Pages
1. Directory: search box (name, organisation number, town, NACE), filters (status, family availability, legal form, has website, has jobs), sort (name, revenue, employees, evidence count), result count, sticky header on mobile, keyboard accessible, shareable URL state (hash).
2. Company page, top to bottom: legal name, orgnr (copy button), status badge (six states, text + icon, never colour alone), one-line headline; the synthesis with numbered citations that expand inline into evidence cards (source link opens in new tab, retrieved date, reporting period or published date, the verbatim snippet, short sha256, identity proof level); key facts grid (employees, latest revenue/result/equity with fiscal year, address, NACE, founded); sections per family each with its own state badge and reason, including a clear "Not verified" panel listing unknowns and what was checked; leadership table; locations list; hiring list (title, place, published, link); activity timeline; official website and company-declared profiles (labelled "declared by the company site"); "What changed" log; "Download this company as JSON" and "View raw envelope".
3. Compare: choose up to 3 companies from the directory; side-by-side table of the same rows; works as stacked cards on narrow screens.
4. About/How to verify: 6 lines on sources, the six states, how to check a claim, run date, git commit, strategy version, limitations.

## Quality bar
- Mobile first: usable at 360 px width, no horizontal scroll (tables become cards), tap targets at least 44 px, readable base font 16 px, dark and light via prefers-color-scheme, print stylesheet for a company page.
- Accessibility: semantic landmarks, skip link, heading order, labels for every control, focus outlines, contrast AA, aria-expanded on citations, no information by colour alone, lang attribute.
- Performance: a company page loads under 150 KB without images; first paint without JS; JS only enhances search/filters.
- Honesty: never show a fact without its badge and evidence link; never render a state `available` for a family without claims; "not found" language is precise ("none found in the NAV feed"), not "no jobs".

## Verification (paste evidence)
1. `uv run pytest -q` includes viewer unit tests: escaping (a company name containing `<script>` renders as text), every claim shown has an evidence card, status badges match field_states, index.json size cap.
2. Screenshots at 390x844 and 1280x800 of the directory, a rich company, a sparse company and the compare view, produced headlessly with Playwright (dev-only tool, not a runtime dependency; commit the PNGs under reports/ux/). Look at them and list every defect you see, fix, rerun.
3. HTML validity (python -m html5lib or `tidy -e`) with zero errors; link check: every internal link resolves; every evidence link has rel="noopener noreferrer".
4. Publish to GitHub Pages (docs/ folder or gh-pages branch) only after the human approves; put the URL in README.md and docs/SUBMISSION.md. The published site must contain only public data (it does) and a notice that it is a research demo.
5. README.md top section "Judge guide": what this is, 3-command run, where the viewer is, how to read a claim, known limitations. Under 60 lines.

## Acceptance
site/ builds from the dev envelopes in under 30 s; all checks above pass; screenshots reviewed; tag `phase6`. Stop and report.
