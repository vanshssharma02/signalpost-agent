# Phase 06 Report — Static Mobile-First Company Viewer & UX

## 1. Executive Summary
Phase 06 delivers a standalone, mobile-first static viewer and full static site distribution (`site/` and `out/viewer/index.html`) engineered for the Builderr "Signalpost" challenge:
- **Zero External Runtime Dependencies**: Built with pure HTML5, vanilla CSS, and minimal vanilla JavaScript. Zero CDN scripts, zero external Google Fonts, and strict Content Security Policy (`default-src 'self' 'unsafe-inline' data:`). Fully operational over `file://` local file URIs and static HTTP hosts.
- **Dual Outputs**:
  - `out/viewer/index.html`: Self-contained standalone single-file viewer (7.6 MB) embedding the full 150-company dev dataset, instant real-time search, interactive evidence popovers, 3-way company compare, unknowns inspector, and raw contract JSON viewer.
  - `site/`: Serverless multi-page static site with compact index (`site/data/index.json` at **47.06 KB**, well under the 400 KB cap for 1,100 entities), individual company JSON envelopes (`site/data/<orgnr>.json`), pre-rendered zero-JS static company pages (`site/c/<orgnr>.html` averaging **32.5 KB**, well under the 150 KB cap), and bundled assets (`site/assets/style.css`).
- **WCAG 2.1 AA Standards**: High-contrast typography (>= 4.5:1 ratio in both dark and light modes), semantic HTML landmarks (`<header>`, `<main>`, `<aside>`, `<section>`, `role="region"`), keyboard skip link (`.skip-link:focus`), explicit accessible labels on all controls, 44px min tap targets, and text+icon status badges (never color alone).
- **Headless Visual Quality Verification**: Playwright headless screenshots captured at 1280x800 (desktop) and 390x844 (mobile) across 4 core states (directory, rich company `912569608`, sparse company `835606252`, and compare matrix).
- **Evaluation Score**: UX score elevated from baseline 3.20 to **8.00 / 8.00**, bringing the total Signalpost evaluation proxy score to **82.91 / 100.00** (well above the 65-point qualification threshold).
- **Test Suite**: 143 tests passing in 2.67s.

---

## 2. Core Interactive Features

| Feature | Desktop Implementation | Mobile Implementation |
|---|---|---|
| **Search & Filters** | Real-time search across legal name, 9-digit orgnr, municipality, and NACE industry. Filters by status, legal form, website, hiring, and sort. | Sticky header with full-width search input, collapsible filter grid, keyboard accessible. |
| **Synthesis Narrative** | Structured narrative with clickable numbered citation chips (`[5d66]`, `[d1c1]`). | Clickable inline chips with 44px tap targets; opens modal popover. |
| **Evidence Popover** | Modal displaying source URL (with `rel="noopener noreferrer"`), retrieval timestamp, content SHA-256 hash, source tier, and verbatim snapshot `claim_span` quote. | Full-screen responsive modal with accessible close button (`Esc` key supported). |
| **Facts Grid** | Multi-column responsive cards (Employees, Revenue, Operating Result, Equity, Municipality, NACE). | Stacked 2-column or 1-column cards with thousands-separated figures in NOK. |
| **Unknowns Inspector** | Dedicated panel cataloging missing/unverified families with standardized reason codes and checked sources. | High-contrast warning container with plain language and source audit lists. |
| **Company Comparison** | 3-column side-by-side comparison matrix of key metrics, status badges, financials, and website proof. | Stacked responsive comparison cards with clear separation and direct "Open Full Profile" action. |
| **What Changed** | Refresh audit log displaying detected change events (added, updated, ended) with timestamps. | Responsive cards table with clear diff types. |
| **Raw Contract Envelope** | Collapsible `<details>` drawer with syntax view, one-click copy button, and JSON download. | Horizontal scrolling code block with copy feedback (`✓ JSON Copied!`). |

---

## 3. Bundle Size, Performance & Standards Audit

### 3.1 Size Metrics
- **Compact Index (`site/data/index.json`)**: **47.06 KB** (Workflow budget: `< 400 KB` for 1,100 companies). Projected size for 1,100 companies is ~340 KB, meeting the budget with headroom.
- **Pre-rendered Static Pages (`site/c/<orgnr>.html`)**:
  - Minimum size: 23.6 KB
  - Mean size: **32.5 KB**
  - Maximum size: **41.0 KB**
  - Budget: `< 150 KB` per company page. **Passed with 72% margin**.
- **Standalone Offline File (`out/viewer/index.html`)**: **7.61 MB** containing the complete offline dataset (150 companies, 4,171 claims, all evidence spans, and all synthesis narratives).

### 3.2 WCAG 2.1 AA Compliance Checklist
- [x] **Contrast**: All text meets or exceeds 4.5:1 contrast against surface background (tested across light and dark color schemes).
- [x] **Semantic Landmarks**: `<header>`, `<main>`, `<aside>`, `<section>`, `<details>`, `role="banner"`, `role="main"`, `role="region"`.
- [x] **Skip Link**: `<a href="#main" class="skip-link">Skip to main content</a>` visually reveals on `:focus`.
- [x] **Focus Indicators**: 2px solid border-focus outline with 2px offset on all interactive elements.
- [x] **Tap Target Sizing**: All buttons, inputs, and selects adhere to minimum 44px height/width touch targets.
- [x] **No Color Alone**: Every status badge pairs color with a symbol and text (e.g. `● Available`, `▲ Ambiguous`, `○ Not Available`, `⊘ Not Applicable`, `✕ Failed`).
- [x] **Security**: Strict CSP `<meta>` tag, zero inline JavaScript handlers from data, all text strings safely HTML-escaped. All external links contain `rel="noopener noreferrer"` and `target="_blank"`.

---

## 4. Playwright Headless Screenshots Review

Screenshots captured and committed under `reports/ux/`:
1. `reports/ux/directory-desktop.png` (1280x800): Directory view showing search input, filter controls, company list, and profile preview.
2. `reports/ux/directory-mobile.png` (390x844): Mobile directory layout with touch-friendly filter controls and company cards.
3. `reports/ux/rich-company-desktop.png` (1280x800): Profile of `SAFE4 SECURITY GROUP AS` (`912569608`) with 46 claims, narrative synthesis, inline citations, key facts grid, and leadership table.
4. `reports/ux/rich-company-mobile.png` (390x844): Mobile profile view showing zero horizontal scroll, legible typography, and responsive buttons.
5. `reports/ux/sparse-company-desktop.png` (1280x800): Profile of `SAHO AS` (`835606252`) showing loss-making 2025 financials, 1 role, and prominent Unknowns panel.
6. `reports/ux/sparse-company-mobile.png` (390x844): Mobile profile of sparse company showing responsive card stacking.
7. `reports/ux/compare-desktop.png` (1280x800): Side-by-side comparison matrix across `SAHO AS` and `SAFE4 SECURITY GROUP AS`.
8. `reports/ux/compare-mobile.png` (390x844): Mobile stacked comparison cards with clear separation and direct profile links.

### Defect Log & Resolution
- **Defect 1**: Mobile header controls wrapped awkwardly on 390px screens.  
  *Fix*: Added `@media (max-width: 640px)` rule stacking header actions into a full-width 2-column grid.
- **Defect 2**: Mobile scroll jumped past the company title due to the sticky header.  
  *Fix*: Added `scroll-margin-top: 115px;` to `main.profile-view`.
- **Defect 3**: Raw Python dictionary string printed in Leadership and Locations tables.  
  *Fix*: Added clean formatters extracting role holder names, role titles, and subunit locations before rendering.

---

## 5. Evaluation Scoring Progression

```text
==================================================================
               SIGNALPOST EVALUATION SCORE REPORT (PROXY)
==================================================================
 Cohort: 150 companies | Envelopes: 150
------------------------------------------------------------------
 OVERALL PROXY SCORE: 82.91 / 100.00
   - Recall (max 50.0):    32.91
   - Evidence (max 30.0):  30.00
   - Synthesis (max 12.0): 12.00
   - UX (max 8.0):         8.00  (+4.80)
------------------------------------------------------------------
 WEBSITE PRECISION: 100.0% (19 correct, 0 wrong)
 EVIDENCE INTEGRITY: 100.0% backed (4171/4171 claims)
 SPAN VALIDITY:      100.0%
 OPERATIONS:         1456 requests (9.71/co) | p50=8.97s p95=37.74s
------------------------------------------------------------------
```

| Rubric Metric (100) | Phase 4 (Connectors) | Phase 5 (Synthesis) | Phase 6 (Viewer UX) | Δ vs P5 |
|---|---|---|---|---|
| **Recall (50)** | 32.91 | 32.91 | 32.91 | +0.00 |
| **Evidence (30)** | 30.00 | 30.00 | 30.00 | +0.00 |
| **Synthesis (12)** | 7.20 | 12.00 | 12.00 | +0.00 |
| **UX (8)** | 3.20 | 3.20 | **8.00** | **+4.80** |
| **Total Proxy Score** | **73.31** | **78.11** | **82.91** | **+4.80** |

---

## 6. Items Skipped and Rationale

| Workflow Item | Status | Rationale |
|---|---|---|
| **B.4 Remote GitHub Pages publishing** | Pending approval | Workflow /06 explicitly mandates: *"Publish to GitHub Pages (docs/ folder or gh-pages branch) only after the human approves"*. The local `site/` distribution and standalone `out/viewer/index.html` are compiled and ready for deployment upon user confirmation. |

---

## 7. Acceptance Checklist
- [x] Standalone viewer compiled at `out/viewer/index.html` (zero CDN dependencies, works from `file://`).
- [x] Static site compiled under `site/` with `index.json` (47 KB < 400 KB) and static company pages (32.5 KB < 150 KB).
- [x] All 7 viewer tests pass; full suite passes (143 passed in 2.67s).
- [x] Playwright screenshots captured for desktop (1280x800) and mobile (390x844).
- [x] HTML validity and link security verified (0 bad rel tags, 0 broken links).
- [x] Top Judge Guide added to `README.md` (41 lines < 60 lines).
- [x] Evaluation harness UX score elevated to 8.00 / 8.00 (overall score: 82.91).
- [x] Git tagged `phase-06-complete` (and `phase6`).
