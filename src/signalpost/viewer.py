"""Static, mobile-first Norwegian company viewer for Signalpost.
Builds standalone and multi-page static sites conforming to WCAG 2.1 AA.
Zero external runtime CDN dependencies.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
from pathlib import Path
from typing import Any

from signalpost.ref.envelope import FAMILIES, STATES

STATUS_ICONS = {
    "available": "●",
    "not_available": "○",
    "ambiguous": "▲",
    "not_applicable": "⊘",
    "failed": "✕",
}

STATUS_LABELS = {
    "available": "Available",
    "not_available": "Not Available",
    "ambiguous": "Ambiguous",
    "not_applicable": "Not Applicable",
    "failed": "Failed",
}


def esc(text: Any) -> str:
    """Safely escape HTML entities."""
    if text is None:
        return ""
    return html.escape(str(text), quote=True)


def format_currency(val: Any) -> str:
    if val is None or val == "":
        return "—"
    try:
        num = float(val)
        return f"{num:,.0f} NOK".replace(",", " ")
    except (ValueError, TypeError):
        return str(val)


def extract_compact_index_entry(env: dict[str, Any]) -> dict[str, Any]:
    """Extract lightweight row for directory indexing (< 400 KB for 1,100 companies)."""
    org = str(env.get("organisation_number", ""))
    status = env.get("status", "available")
    claims = env.get("claims", [])
    evidences = env.get("evidence", [])
    synthesis = env.get("synthesis", {}) or {}

    c_map = {c.get("field"): c for c in claims if c.get("field")}

    name = c_map.get("legal_name", {}).get("value") or f"Entity {org}"
    form = c_map.get("legal_form", {}).get("value") or "—"
    ind_code = c_map.get("industry_code", {}).get("value") or ""
    emp = c_map.get("employees", {}).get("value")
    web = c_map.get("official_website", {}).get("value") or ""
    baddr = c_map.get("business_address", {}).get("value") or {}
    muni = baddr.get("municipality") or baddr.get("poststed") or ""

    # Financials
    fin_claims = [c for c in claims if c.get("family") in ("accounts", "financials") and c.get("field") == "revenue"]
    rev = fin_claims[0].get("value") if fin_claims else None
    year = fin_claims[0].get("reporting_period", {}).get("to", "")[:4] if fin_claims else ""

    res_claims = [c for c in claims if c.get("family") in ("accounts", "financials") and c.get("field") in ("operating_result", "annual_result")]
    res = res_claims[0].get("value") if res_claims else None

    # Job postings
    has_jobs = any(c.get("family") == "hiring" and c.get("availability") == "available" for c in claims)
    unknowns_cnt = len(synthesis.get("unknowns", []))

    return {
        "org": org,
        "name": name,
        "form": form,
        "status": status,
        "muni": muni,
        "nace": ind_code,
        "emp": emp,
        "rev": rev,
        "res": res,
        "year": year,
        "web": web,
        "has_jobs": has_jobs,
        "claims_cnt": len(claims),
        "ev_cnt": len(evidences),
        "unknowns_cnt": unknowns_cnt,
        "headline": synthesis.get("headline", f"{name} ({org})"),
    }


def get_viewer_css() -> str:
    """Self-contained CSS with dark/light themes, WCAG contrast, and mobile-first responsive layout."""
    return """
:root {
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  --bg-page: #f8fafc;
  --bg-card: #ffffff;
  --bg-card-hover: #f1f5f9;
  --bg-subtle: #f8fafc;
  --text-main: #0f172a;
  --text-muted: #475569;
  --border: #cbd5e1;
  --border-focus: #0284c7;
  --accent: #0369a1;
  --accent-light: #e0f2fe;
  --accent-text: #0284c7;
  --status-available-bg: #dcfce7;
  --status-available-text: #14532d;
  --status-ambiguous-bg: #fef3c7;
  --status-ambiguous-text: #78350f;
  --status-not-avail-bg: #f1f5f9;
  --status-not-avail-text: #334155;
  --status-failed-bg: #fee2e2;
  --status-failed-text: #7f1d1d;
  --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
  --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg-page: #0b0f19;
    --bg-card: #131b2e;
    --bg-card-hover: #1e293b;
    --bg-subtle: #0f172a;
    --text-main: #f8fafc;
    --text-muted: #94a3b8;
    --border: #334155;
    --border-focus: #38bdf8;
    --accent: #38bdf8;
    --accent-light: #082f49;
    --accent-text: #38bdf8;
    --status-available-bg: #064e3b;
    --status-available-text: #a7f3d0;
    --status-ambiguous-bg: #78350f;
    --status-ambiguous-text: #fde68a;
    --status-not-avail-bg: #1e293b;
    --status-not-avail-text: #cbd5e1;
    --status-failed-bg: #7f1d1d;
    --status-failed-text: #fecaca;
  }
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--font-sans);
  background-color: var(--bg-page);
  color: var(--text-main);
  line-height: 1.6;
  font-size: 16px;
  -webkit-font-smoothing: antialiased;
}

*:focus-visible {
  outline: 2px solid var(--border-focus);
  outline-offset: 2px;
}

.skip-link {
  position: absolute;
  top: -40px;
  left: 10px;
  background: var(--accent);
  color: #ffffff;
  padding: 8px 16px;
  z-index: 1000;
  border-radius: 4px;
  font-weight: 600;
  text-decoration: none;
  transition: top 0.15s;
}
.skip-link:focus {
  top: 10px;
}

header.app-header {
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  padding: 12px 20px;
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

@media (max-width: 640px) {
  header.app-header {
    flex-direction: column;
    align-items: stretch;
    padding: 10px 12px;
    gap: 8px;
  }
  .brand-wrap {
    justify-content: space-between;
    width: 100%;
  }
  .header-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    width: 100%;
  }
  .btn {
    padding: 6px 10px;
    font-size: 13px;
  }
  .layout-container {
    padding: 10px;
  }
  main.profile-view {
    scroll-margin-top: 115px;
  }
}

.brand-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-logo {
  font-size: 20px;
  font-weight: 800;
  color: var(--accent);
  display: flex;
  align-items: center;
  gap: 6px;
  text-decoration: none;
}

.brand-badge {
  font-size: 12px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 9999px;
  background: var(--accent-light);
  color: var(--accent);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 14px;
  min-height: 44px;
  min-width: 44px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text-main);
  text-decoration: none;
  transition: all 0.15s ease-in-out;
}

.btn:hover {
  background: var(--bg-card-hover);
  border-color: var(--accent);
}

.btn-primary {
  background: var(--accent);
  color: #ffffff;
  border-color: var(--accent);
}
.btn-primary:hover {
  filter: brightness(1.1);
}

.layout-container {
  max-width: 1560px;
  margin: 0 auto;
  padding: 18px;
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: 20px;
  align-items: start;
}

@media (max-width: 960px) {
  .layout-container {
    grid-template-columns: 1fr;
  }
}

/* Sidebar / Directory */
aside.directory-sidebar {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
  box-shadow: var(--shadow-sm);
  position: sticky;
  top: 76px;
  max-height: calc(100vh - 96px);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

@media (max-width: 960px) {
  aside.directory-sidebar {
    position: static;
    max-height: none;
  }
}

.search-box {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.search-input {
  width: 100%;
  min-height: 44px;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-subtle);
  color: var(--text-main);
  font-size: 15px;
}

.filter-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.filter-select {
  width: 100%;
  min-height: 44px;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-subtle);
  color: var(--text-main);
  font-size: 13px;
}

.result-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 500;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--border);
}

.company-list {
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-right: 4px;
  flex: 1;
  min-height: 200px;
}

.company-card-btn {
  display: block;
  width: 100%;
  text-align: left;
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px 12px;
  cursor: pointer;
  transition: all 0.15s ease-in-out;
  min-height: 44px;
  color: var(--text-main);
}

.company-card-btn:hover {
  background: var(--bg-card-hover);
  border-color: var(--accent);
}

.company-card-btn.active {
  background: var(--accent-light);
  border-color: var(--accent);
}

.card-title-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 6px;
}

.card-name {
  font-weight: 700;
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-sub-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}

/* Badges */
.badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  white-space: nowrap;
}

.badge-available { background: var(--status-available-bg); color: var(--status-available-text); }
.badge-ambiguous { background: var(--status-ambiguous-bg); color: var(--status-ambiguous-text); }
.badge-not_available { background: var(--status-not-avail-bg); color: var(--status-not-avail-text); }
.badge-not_applicable { background: var(--status-not-avail-bg); color: var(--status-not-avail-text); }
.badge-failed { background: var(--status-failed-bg); color: var(--status-failed-text); }

/* Main Profile Panel */
main.profile-view {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 24px;
  box-shadow: var(--shadow-sm);
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.profile-header {
  border-bottom: 1px solid var(--border);
  padding-bottom: 18px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 16px;
}

.company-title-area h1 {
  font-size: 26px;
  font-weight: 800;
  line-height: 1.2;
  margin-bottom: 6px;
}

.company-meta-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 14px;
  color: var(--text-muted);
}

.copy-btn {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 12px;
  cursor: pointer;
  color: var(--text-muted);
  min-height: 28px;
}
.copy-btn:hover {
  background: var(--bg-card-hover);
  color: var(--text-main);
}

/* Synthesis narrative box */
.synthesis-card {
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-left: 4px solid var(--accent);
  border-radius: 6px;
  padding: 16px 18px;
}

.synthesis-card h2 {
  font-size: 17px;
  font-weight: 700;
  margin-bottom: 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.synthesis-narrative {
  font-size: 15px;
  line-height: 1.7;
}

.citation-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  background: var(--accent-light);
  color: var(--accent);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 0 5px;
  margin: 0 2px;
  cursor: pointer;
  text-decoration: none;
  vertical-align: baseline;
  min-height: 22px;
}
.citation-chip:hover {
  background: var(--accent);
  color: #ffffff;
}

/* Key facts grid */
.facts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.fact-item {
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px;
}

.fact-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  font-weight: 700;
}

.fact-value {
  font-size: 18px;
  font-weight: 700;
  margin-top: 4px;
  word-break: break-word;
}

.fact-sub {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
}

/* Tab/Sections */
.section-block {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 16px;
  background: var(--bg-card);
}

.section-block h3 {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* Tables */
.data-table-wrap {
  width: 100%;
  overflow-x: auto;
}

table.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

table.data-table th, table.data-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  text-align: left;
}

table.data-table th {
  color: var(--text-muted);
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
  background: var(--bg-subtle);
}

@media (max-width: 640px) {
  table.responsive-cards-table thead {
    display: none;
  }
  table.responsive-cards-table,
  table.responsive-cards-table tbody,
  table.responsive-cards-table tr,
  table.responsive-cards-table td {
    display: block;
    width: 100%;
  }
  table.responsive-cards-table tr {
    margin-bottom: 10px;
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 8px;
    background: var(--bg-subtle);
  }
  table.responsive-cards-table td {
    border: none;
    padding: 4px 0;
    display: flex;
    justify-content: space-between;
  }
  table.responsive-cards-table td::before {
    content: attr(data-label);
    font-weight: 600;
    color: var(--text-muted);
  }
}

/* Unknowns & Evidence Cards */
.unknowns-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.unknown-item {
  background: var(--bg-subtle);
  border-left: 3px solid var(--border);
  padding: 8px 12px;
  font-size: 13px;
  border-radius: 0 4px 4px 0;
}

.evidence-card {
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px;
  margin-top: 10px;
  font-size: 13px;
}

.evidence-quote {
  font-family: var(--font-mono);
  font-size: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  padding: 8px;
  border-radius: 4px;
  margin: 6px 0;
  white-space: pre-wrap;
  word-break: break-word;
}

.compare-matrix {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
  margin-top: 14px;
}

.compare-col {
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 14px;
}

/* Raw JSON drawer */
details.json-drawer {
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px;
}
details.json-drawer summary {
  cursor: pointer;
  font-weight: 600;
  font-size: 14px;
}
pre.json-code {
  font-family: var(--font-mono);
  font-size: 12px;
  background: var(--bg-card);
  padding: 12px;
  border-radius: 4px;
  overflow-x: auto;
  margin-top: 8px;
  max-height: 400px;
}

/* Modal / Evidence Popover */
.evidence-popover {
  display: none;
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  z-index: 500;
  align-items: center;
  justify-content: center;
  padding: 16px;
}
.evidence-popover.active {
  display: flex;
}
.evidence-modal {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  max-width: 640px;
  width: 100%;
  max-height: 85vh;
  overflow-y: auto;
  padding: 20px;
  box-shadow: var(--shadow-md);
  position: relative;
}

/* Print styles */
@media print {
  body { background: #ffffff; color: #000000; font-size: 12pt; }
  header.app-header, aside.directory-sidebar, .btn, .copy-btn, .evidence-popover { display: none !important; }
  .layout-container { display: block; padding: 0; }
  main.profile-view { border: none; box-shadow: none; padding: 0; }
  .badge { border: 1px solid #000000; }
  a { text-decoration: underline; color: #000000; }
}
"""


def render_standalone_html(envelopes: list[dict[str, Any]], run_meta: dict[str, Any] | None = None) -> str:
    """Build single-file standalone index.html with embedded dataset, zero external dependencies."""
    run_meta = run_meta or {}
    compact_rows = [extract_compact_index_entry(e) for e in envelopes]
    
    # Store minimal claim and evidence lookup for instant interactive popovers and cards
    entity_details_map = {}
    for env in envelopes:
        org = str(env.get("organisation_number", ""))
        clean_evs = []
        for ev in env.get("evidence") or []:
            clean_evs.append({k: v for k, v in ev.items() if k not in ("page_html", "raw_body", "body")})
        clean_raw = {k: v for k, v in env.items() if k not in ("profile",)}
        clean_raw["evidence"] = clean_evs

        entity_details_map[org] = {
            "org": org,
            "status": env.get("status"),
            "synthesis": env.get("synthesis") or {},
            "claims": env.get("claims") or [],
            "evidence": clean_evs,
            "field_states": env.get("field_states") or {},
            "changes": env.get("changes") or [],
            "raw": clean_raw,
        }

    compact_json = json.dumps(compact_rows, ensure_ascii=False).replace("</", "<\\/")
    details_json = json.dumps(entity_details_map, ensure_ascii=False).replace("</", "<\\/")
    run_meta_json = json.dumps(run_meta, ensure_ascii=False).replace("</", "<\\/")

    css = get_viewer_css()

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="default-src 'self' 'unsafe-inline' data:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:;">
  <title>Signalpost — Norwegian Company Intelligence Viewer</title>
  <meta name="description" content="Autonomous Norwegian company intelligence grounded in official Brønnøysund registries and exact-entity web evidence.">
  <style>{css}</style>
</head>
<body>
  <a href="#main" class="skip-link">Skip to main content</a>
  <header class="app-header" role="banner">
    <div class="brand-wrap">
      <a href="#" class="brand-logo" aria-label="Signalpost Homepage">
        <span style="color:var(--accent);">◆</span> Signalpost
      </a>
      <span class="brand-badge">WCAG 2.1 AA</span>
      <span class="brand-badge" id="cohort-tag">{len(compact_rows)} entities</span>
    </div>
    <div class="header-actions">
      <button id="compare-btn" class="btn" type="button" aria-label="Open compare tray">
        <span>⚖</span> Compare (<span id="compare-count">0</span>)
      </button>
      <button id="about-btn" class="btn" type="button" aria-label="About Signalpost verification guidelines">
        <span>ℹ</span> About & Sources
      </button>
    </div>
  </header>

  <div class="layout-container">
    <aside class="directory-sidebar" role="region" aria-label="Company directory and filters">
      <div class="search-box">
        <label for="q-input" style="font-size:12px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">Search Companies</label>
        <input id="q-input" class="search-input" type="search" placeholder="Search name, orgnr, town, NACE..." aria-label="Search directory">
        <div class="filter-row">
          <select id="filter-status" class="filter-select" aria-label="Filter by Status">
            <option value="">All Statuses</option>
            <option value="available">● Available</option>
            <option value="ambiguous">▲ Ambiguous</option>
            <option value="not_available">○ Not Available</option>
            <option value="not_applicable">⊘ Not Applicable</option>
            <option value="failed">✕ Failed</option>
          </select>
          <select id="filter-form" class="filter-select" aria-label="Filter by Legal Form">
            <option value="">All Forms</option>
          </select>
        </div>
        <div class="filter-row">
          <select id="filter-web" class="filter-select" aria-label="Filter by Website presence">
            <option value="">Any Website</option>
            <option value="yes">Has Website</option>
            <option value="no">No Website</option>
          </select>
          <select id="filter-jobs" class="filter-select" aria-label="Filter by Job openings">
            <option value="">Any Hiring</option>
            <option value="yes">Has Job Postings</option>
          </select>
        </div>
        <div class="filter-row">
          <select id="sort-select" class="filter-select" aria-label="Sort companies by">
            <option value="name">Sort: Name (A-Z)</option>
            <option value="rev">Sort: Revenue (High to Low)</option>
            <option value="emp">Sort: Employees (High to Low)</option>
            <option value="claims">Sort: Evidence Claims</option>
          </select>
          <button id="reset-filters" class="btn" style="min-height:44px;" type="button">Reset</button>
        </div>
      </div>
      <div class="result-meta">
        <span id="results-count">{len(compact_rows)} companies</span>
        <span>Keyboard: <b>↑</b> <b>↓</b></span>
      </div>
      <div class="company-list" id="company-list" role="listbox" aria-label="Matching companies"></div>
    </aside>

    <main id="main" class="profile-view" role="main" aria-live="polite">
      <!-- Profile dynamically rendered here -->
    </main>
  </div>

  <!-- Evidence popover modal -->
  <div class="evidence-popover" id="evidence-modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
    <div class="evidence-modal" id="modal-content">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
        <h3 id="modal-title" style="font-size:17px; font-weight:800;">Evidence Provenance</h3>
        <button class="btn" id="modal-close-btn" style="min-height:36px; min-width:36px;" type="button" aria-label="Close evidence modal">✕</button>
      </div>
      <div id="modal-body"></div>
    </div>
  </div>

  <script>
    const COMPACT_DATA = {compact_json};
    const DETAILS_DATA = {details_json};
    const RUN_META = {run_meta_json};

    let selectedOrgnr = null;
    let compareList = [];
    let isCompareMode = false;
    let isAboutMode = false;

    const $ = s => document.querySelector(s);
    const $$ = s => document.querySelectorAll(s);

    function escHtml(str) {{
      if (str === null || str === undefined) return '';
      return String(str).replace(/[&<>"']/g, c => ({{
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      }})[c]);
    }}

    function money(val) {{
      if (val === null || val === undefined || val === '') return '—';
      const n = Number(val);
      if (isNaN(n)) return escHtml(val);
      return new Intl.NumberFormat('en-US', {{ maximumFractionDigits: 0 }}).format(n).replace(/,/g, ' ') + ' NOK';
    }}

    // Populate legal forms filter
    const forms = [...new Set(COMPACT_DATA.map(x => x.form).filter(Boolean))].sort();
    forms.forEach(f => {{
      const opt = document.createElement('option');
      opt.value = f;
      opt.textContent = f;
      $('#filter-form').appendChild(opt);
    }});

    function getFilteredList() {{
      const q = ($('#q-input').value || '').trim().toLowerCase();
      const status = $('#filter-status').value;
      const form = $('#filter-form').value;
      const hasWeb = $('#filter-web').value;
      const hasJobs = $('#filter-jobs').value;
      const sort = $('#sort-select').value;

      let list = COMPACT_DATA.filter(item => {{
        if (q) {{
          const target = [item.name, item.org, item.muni, item.nace, item.headline].join(' ').toLowerCase();
          if (!target.includes(q)) return false;
        }}
        if (status && item.status !== status) return false;
        if (form && item.form !== form) return false;
        if (hasWeb === 'yes' && !item.web) return false;
        if (hasWeb === 'no' && item.web) return false;
        if (hasJobs === 'yes' && !item.has_jobs) return false;
        return true;
      }});

      list.sort((a, b) => {{
        if (sort === 'rev') return (b.rev || 0) - (a.rev || 0);
        if (sort === 'emp') return (b.emp || 0) - (a.emp || 0);
        if (sort === 'claims') return (b.claims_cnt || 0) - (a.claims_cnt || 0);
        return a.name.localeCompare(b.name, 'nb');
      }});

      return list;
    }}

    function renderList() {{
      const items = getFilteredList();
      $('#results-count').textContent = `${{items.length}} of ${{COMPACT_DATA.length}} companies`;
      const container = $('#company-list');
      container.innerHTML = '';

      if (items.length === 0) {{
        container.innerHTML = '<p style="padding:16px; color:var(--text-muted); font-size:14px;">No matching companies found.</p>';
        return;
      }}

      items.forEach(item => {{
        const btn = document.createElement('button');
        btn.className = 'company-card-btn' + (item.org === selectedOrgnr ? ' active' : '');
        btn.setAttribute('role', 'option');
        btn.setAttribute('aria-selected', item.org === selectedOrgnr);
        btn.innerHTML = `
          <div class="card-title-row">
            <span class="card-name">${{escHtml(item.name)}}</span>
            <span class="badge badge-${{item.status}}">${{item.status}}</span>
          </div>
          <div class="card-sub-row">
            <span>${{escHtml(item.org)}} · ${{escHtml(item.form)}}</span>
            <span>${{item.muni ? escHtml(item.muni) : (item.emp !== null ? item.emp + ' emp' : '0 emp')}}</span>
          </div>
        `;
        btn.onclick = () => {{
          selectCompany(item.org);
        }};
        container.appendChild(btn);
      }});

      if (!selectedOrgnr && items.length > 0) {{
        selectCompany(items[0].org);
      }}
    }}

    function selectCompany(orgnr, shouldScroll) {{
      selectedOrgnr = orgnr;
      isCompareMode = false;
      isAboutMode = false;
      window.location.hash = orgnr;
      renderList();
      renderProfile();
      if (shouldScroll && window.innerWidth < 960) {{
        const main = $('#main');
        if (main) {{
          main.scrollIntoView({{ behavior: 'smooth' }});
        }}
      }}
    }}

    function renderProfile() {{
      const main = $('#main');
      if (isAboutMode) {{
        renderAboutView();
        return;
      }}
      if (isCompareMode) {{
        renderCompareView();
        return;
      }}
      if (!selectedOrgnr || !DETAILS_DATA[selectedOrgnr]) {{
        main.innerHTML = '<p style="padding:20px; color:var(--text-muted);">Select a company from the directory.</p>';
        return;
      }}

      const data = DETAILS_DATA[selectedOrgnr];
      const env = data.raw;
      const synth = data.synthesis;
      const claims = data.claims || [];
      const evs = data.evidence || [];
      const evMap = {{}};
      evs.forEach(e => {{ evMap[e.id] = e; }});
      const claimsMap = {{}};
      claims.forEach(c => {{ claimsMap[c.claim_id] = c; }});

      const isCompared = compareList.includes(selectedOrgnr);

      // Synthesis narrative with clickable citations
      let narrativeHtml = '';
      if (synth && synth.sentences) {{
        narrativeHtml = synth.sentences.map(sent => {{
          let chips = (sent.claim_ids || []).map((cid, idx) => {{
            const claim = claimsMap[cid];
            const numLabel = cid.substring(0, 4);
            return `<button class="citation-chip" data-claim-id="${{escHtml(cid)}}" aria-label="View evidence for claim ${{escHtml(cid)}}">[${{numLabel}}]</button>`;
          }}).join('');
          return `<span>${{escHtml(sent.text)}} ${{chips}}</span> `;
        }}).join('');
      }}

      // Key facts
      const c_name = claims.find(c => c.field === 'legal_name');
      const c_form = claims.find(c => c.field === 'legal_form');
      const c_emp = claims.find(c => c.field === 'employees');
      const c_ind = claims.find(c => c.field === 'industry_code');
      const c_web = claims.find(c => c.field === 'official_website');
      const c_addr = claims.find(c => c.field === 'business_address');
      const rev_claim = claims.find(c => c.field === 'revenue');
      const res_claim = claims.find(c => c.field === 'operating_result' || c.field === 'annual_result');
      const eq_claim = claims.find(c => c.field === 'equity');

      const addrVal = c_addr ? c_addr.value : {{}};
      const muniStr = addrVal.municipality || addrVal.poststed || 'Not reported';
      const streetStr = (addrVal.street || []).join(', ') || 'No street registered';

      // Leadership items
      const roleClaims = claims.filter(c => c.family === 'leadership');
      // Subunits
      const subClaims = claims.filter(c => c.family === 'locations');
      // Jobs
      const jobClaims = claims.filter(c => c.family === 'hiring');
      // Changes
      const changes = data.changes || [];
      // Unknowns
      const unknowns = synth.unknowns || [];

      main.innerHTML = `
        <div class="profile-header">
          <div class="company-title-area">
            <h1>${{escHtml(c_name ? c_name.value : 'Entity ' + selectedOrgnr)}}</h1>
            <div class="company-meta-line">
              <span><b>Org.nr:</b> ${{escHtml(selectedOrgnr)}}</span>
              <button class="copy-btn" id="copy-org-btn" type="button" aria-label="Copy organisation number">📋 Copy</button>
              <span class="badge badge-${{data.status}}">${{data.status}}</span>
              <span>${{escHtml(c_form ? c_form.value : 'Entity')}}</span>
              ${{c_web ? `<a href="${{escHtml(c_web.value)}}" target="_blank" rel="noopener noreferrer" style="color:var(--accent); font-weight:600; text-decoration:none;">🌐 Verified Website ↗</a>` : ''}}
            </div>
          </div>
          <div style="display:flex; gap:8px;">
            <button class="btn" id="toggle-compare-btn" type="button">
              ${{isCompared ? '✓ Added to Compare' : '+ Add to Compare'}}
            </button>
            <button class="btn" id="copy-json-btn" type="button">📋 Copy JSON</button>
          </div>
        </div>

        <!-- Synthesis Box -->
        <section class="synthesis-card" aria-labelledby="synth-heading">
          <h2 id="synth-heading">
            <span>Verified Narrative Synthesis</span>
            <span style="font-size:12px; font-weight:600; color:var(--text-muted);">${{synth.generator || 'template-v1'}} · 100% cited</span>
          </h2>
          <div class="synthesis-narrative">${{narrativeHtml || '<p>No narrative available.</p>'}}</div>
        </section>

        <!-- Facts Grid -->
        <section class="facts-grid" aria-label="Key Facts">
          <div class="fact-item">
            <div class="fact-label">Employees</div>
            <div class="fact-value">${{c_emp && c_emp.value !== null ? escHtml(c_emp.value) : '0'}}</div>
            <div class="fact-sub">Registered employees</div>
          </div>
          <div class="fact-item">
            <div class="fact-label">Revenue (Latest)</div>
            <div class="fact-value">${{money(rev_claim ? rev_claim.value : null)}}</div>
            <div class="fact-sub">${{rev_claim && rev_claim.reporting_period ? escHtml(rev_claim.reporting_period.to.substring(0,4)) : '—'}}</div>
          </div>
          <div class="fact-item">
            <div class="fact-label">Operating Result</div>
            <div class="fact-value">${{money(res_claim ? res_claim.value : null)}}</div>
            <div class="fact-sub">${{res_claim && res_claim.reporting_period ? escHtml(res_claim.reporting_period.to.substring(0,4)) : '—'}}</div>
          </div>
          <div class="fact-item">
            <div class="fact-label">Equity</div>
            <div class="fact-value">${{money(eq_claim ? eq_claim.value : null)}}</div>
            <div class="fact-sub">Latest fiscal balance</div>
          </div>
          <div class="fact-item">
            <div class="fact-label">Municipality</div>
            <div class="fact-value">${{escHtml(muniStr)}}</div>
            <div class="fact-sub">${{escHtml(streetStr)}}</div>
          </div>
          <div class="fact-item">
            <div class="fact-label">Industry (NACE)</div>
            <div class="fact-value" style="font-size:15px;">${{escHtml(c_ind ? c_ind.value : '—')}}</div>
            <div class="fact-sub">Classification code</div>
          </div>
        </section>

        <!-- Leadership Section -->
        <section class="section-block" aria-labelledby="lead-heading">
          <h3 id="lead-heading">
            <span>Leadership & Key Roles</span>
            <span class="badge badge-${{data.field_states.leadership ? data.field_states.leadership.availability : 'available'}}">
              ${{roleClaims.length}} registered
            </span>
          </h3>
          ${{roleClaims.length > 0 ? `
            <div class="data-table-wrap">
              <table class="data-table responsive-cards-table">
                <thead>
                  <tr><th>Role</th><th>Name / Holder</th><th>Citation</th></tr>
                </thead>
                <tbody>
                  ${{roleClaims.map(c => `
                    <tr>
                      <td data-label="Role"><b>${{escHtml(typeof c.value === 'object' && c.value.role ? c.value.role : c.field)}}</b></td>
                      <td data-label="Holder">${{escHtml(typeof c.value === 'object' ? (c.value.name || JSON.stringify(c.value)) : c.value)}}</td>
                      <td data-label="Citation">
                        <button class="citation-chip" data-claim-id="${{escHtml(c.claim_id)}}">[${{escHtml(c.claim_id.substring(0,4))}}]</button>
                      </td>
                    </tr>
                  `).join('')}}
                </tbody>
              </table>
            </div>
          ` : '<p style="color:var(--text-muted); font-size:14px;">No individual role holders returned in registry snapshot.</p>'}}
        </section>

        <!-- Operating Locations -->
        <section class="section-block" aria-labelledby="loc-heading">
          <h3 id="loc-heading">
            <span>Operating Locations & Subunits</span>
            <span class="badge badge-${{data.field_states.locations ? data.field_states.locations.availability : 'available'}}">
              ${{subClaims.length}} subunit(s)
            </span>
          </h3>
          ${{subClaims.length > 0 ? `
            <div class="data-table-wrap">
              <table class="data-table responsive-cards-table">
                <thead><tr><th>Subunit Orgnr</th><th>Name / Details</th><th>Citation</th></tr></thead>
                <tbody>
                  ${{subClaims.map(c => `
                    <tr>
                      <td data-label="Orgnr"><code>${{escHtml(c.discriminator || (typeof c.value === 'object' && c.value.organisation_number ? c.value.organisation_number : 'Subunit'))}}</code></td>
                      <td data-label="Details">${{escHtml(typeof c.value === 'object' ? (c.value.name ? c.value.name + (c.value.municipality ? ' (' + c.value.municipality + ')' : '') : JSON.stringify(c.value)) : c.value)}}</td>
                      <td data-label="Citation">
                        <button class="citation-chip" data-claim-id="${{escHtml(c.claim_id)}}">[${{escHtml(c.claim_id.substring(0,4))}}]</button>
                      </td>
                    </tr>
                  `).join('')}}
                </tbody>
              </table>
            </div>
          ` : '<p style="color:var(--text-muted); font-size:14px;">No secondary subunits registered in open registries.</p>'}}
        </section>

        <!-- Hiring Signals -->
        <section class="section-block" aria-labelledby="jobs-heading">
          <h3 id="jobs-heading">
            <span>Hiring & Job Postings</span>
            <span class="badge badge-${{data.field_states.hiring ? data.field_states.hiring.availability : 'not_available'}}">
              ${{jobClaims.length}} posting(s)
            </span>
          </h3>
          ${{jobClaims.length > 0 ? `
            <div class="data-table-wrap">
              <table class="data-table responsive-cards-table">
                <thead><tr><th>Posting Title</th><th>Details / Link</th><th>Citation</th></tr></thead>
                <tbody>
                  ${{jobClaims.map(c => `
                    <tr>
                      <td data-label="Title"><b>${{escHtml(typeof c.value === 'object' ? c.value.title || 'Vacancy' : c.value)}}</b></td>
                      <td data-label="Link">${{c.value && c.value.url ? `<a href="${{escHtml(c.value.url)}}" target="_blank" rel="noopener noreferrer">View Posting ↗</a>` : 'NAV Feed'}}</td>
                      <td data-label="Citation">
                        <button class="citation-chip" data-claim-id="${{escHtml(c.claim_id)}}">[${{escHtml(c.claim_id.substring(0,4))}}]</button>
                      </td>
                    </tr>
                  `).join('')}}
                </tbody>
              </table>
            </div>
          ` : '<p style="color:var(--text-muted); font-size:14px;">No active postings detected in official NAV pam-stilling feed or on verified site.</p>'}}
        </section>

        <!-- What is Unknown / Missing Inspector -->
        <section class="section-block" style="border-left:4px solid var(--status-ambiguous-text);" aria-labelledby="unknown-heading">
          <h3 id="unknown-heading">
            <span>Missing / Unverified Data Points</span>
            <span class="badge badge-ambiguous">${{unknowns.length}} unknown(s)</span>
          </h3>
          <p style="font-size:13px; color:var(--text-muted); margin-bottom:10px;">
            Standardized reason codes for data points that could not be established with exact proof:
          </p>
          <div class="unknowns-list">
            ${{unknowns.map(u => `
              <div class="unknown-item">
                <b>${{escHtml(u.topic)}}:</b> <code>${{escHtml(u.why)}}</code><br>
                <small style="color:var(--text-muted);">Checked sources: ${{escHtml((u.checked || []).join(', '))}}</small>
              </div>
            `).join('')}}
          </div>
        </section>

        <!-- Refresh Changes -->
        <section class="section-block" aria-labelledby="changes-heading">
          <h3 id="changes-heading">
            <span>What Changed (Refresh Audit)</span>
            <span class="badge badge-available">${{changes.length}} change(s)</span>
          </h3>
          ${{changes.length > 0 ? `
            <div class="data-table-wrap">
              <table class="data-table responsive-cards-table">
                <thead><tr><th>Type</th><th>Field</th><th>Detected At</th></tr></thead>
                <tbody>
                  ${{changes.map(ch => `
                    <tr>
                      <td data-label="Type"><span class="badge badge-available">${{escHtml(ch.type)}}</span></td>
                      <td data-label="Field"><code>${{escHtml(ch.field)}}</code></td>
                      <td data-label="Date">${{escHtml(ch.detected_at)}}</td>
                    </tr>
                  `).join('')}}
                </tbody>
              </table>
            </div>
          ` : '<p style="color:var(--text-muted); font-size:14px;">First observation run; no earlier snapshot recorded or no changes detected.</p>'}}
        </section>

        <!-- Raw JSON Inspector -->
        <details class="json-drawer" aria-label="Raw Contract Envelope">
          <summary>View Complete Raw Contract Envelope (JSON)</summary>
          <pre class="json-code" tabindex="0"><code>${{escHtml(JSON.stringify(env, null, 2))}}</code></pre>
        </details>
      `;

      // Wire events on newly rendered profile
      $('#copy-org-btn').onclick = () => {{
        navigator.clipboard.writeText(selectedOrgnr).then(() => {{
          $('#copy-org-btn').textContent = '✓ Copied!';
          setTimeout(() => {{ $('#copy-org-btn').textContent = '📋 Copy'; }}, 2000);
        }});
      }};

      $('#copy-json-btn').onclick = () => {{
        navigator.clipboard.writeText(JSON.stringify(env, null, 2)).then(() => {{
          $('#copy-json-btn').textContent = '✓ JSON Copied!';
          setTimeout(() => {{ $('#copy-json-btn').textContent = '📋 Copy JSON'; }}, 2000);
        }});
      }};

      $('#toggle-compare-btn').onclick = () => {{
        if (compareList.includes(selectedOrgnr)) {{
          compareList = compareList.filter(o => o !== selectedOrgnr);
        }} else {{
          if (compareList.length >= 3) {{
            alert('You can compare up to 3 companies at once.');
            return;
          }}
          compareList.push(selectedOrgnr);
        }}
        $('#compare-count').textContent = compareList.length;
        renderProfile();
      }};

      // Wire citation buttons
      $$('.citation-chip').forEach(btn => {{
        btn.onclick = () => {{
          const cid = btn.dataset.claimId;
          openEvidenceModal(cid, claimsMap[cid], evMap);
        }};
      }});
    }}

    function openEvidenceModal(cid, claim, evMap) {{
      const modal = $('#evidence-modal');
      const body = $('#modal-body');
      if (!claim) {{
        body.innerHTML = `<p>Claim ID <code>${{escHtml(cid)}}</code> not found in index.</p>`;
        modal.classList.add('active');
        return;
      }}

      const evIds = claim.evidence_ids || [];
      const evRows = evIds.map(eid => evMap[eid]).filter(Boolean);

      body.innerHTML = `
        <div style="margin-bottom:12px;">
          <div style="font-size:12px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">Claim Field</div>
          <div style="font-size:16px; font-weight:800; color:var(--accent);">${{escHtml(claim.family)}} / ${{escHtml(claim.field)}}</div>
          <div style="font-size:14px; margin-top:4px;"><b>Asserted Value:</b> <code>${{escHtml(typeof claim.value === 'object' ? JSON.stringify(claim.value) : claim.value)}}</code></div>
          <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">Claim ID: <code>${{escHtml(claim.claim_id)}}</code></div>
        </div>

        <h4 style="font-size:14px; font-weight:700; margin:16px 0 8px; border-top:1px solid var(--border); padding-top:12px;">
          Backing Evidence (${{evRows.length}} record${{evRows.length === 1 ? '' : 's'}})
        </h4>
        ${{evRows.map(ev => `
          <div class="evidence-card">
            <div><b>Source URL:</b> <a href="${{escHtml(ev.source_url)}}" target="_blank" rel="noopener noreferrer">${{escHtml(ev.source_url)}} ↗</a></div>
            <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">
              <span>Retrieved: ${{escHtml(ev.retrieved_at)}}</span> ·
              <span>Source: ${{escHtml(ev.source_class || 'official')}}</span>
            </div>
            <div style="font-size:12px; color:var(--text-muted); margin-top:2px;">
              <span>Content SHA-256: <code>${{escHtml(ev.content_sha256 ? ev.content_sha256.substring(0, 16) + '...' : 'none')}}</code></span>
            </div>
            <div style="margin-top:8px; font-size:12px; font-weight:600;">Verbatim Claim Span in Snapshot:</div>
            <div class="evidence-quote">${{escHtml(ev.claim_span || 'No verbatim span quote')}}</div>
          </div>
        `).join('')}}
      `;

      modal.classList.add('active');
    }}

    function closeEvidenceModal() {{
      $('#evidence-modal').classList.remove('active');
    }}

    $('#modal-close-btn').onclick = closeEvidenceModal;
    $('#evidence-modal').onclick = e => {{
      if (e.target === $('#evidence-modal')) closeEvidenceModal();
    }};

    function renderCompareView() {{
      const main = $('#main');
      if (compareList.length === 0) {{
        main.innerHTML = `
          <div style="padding:24px; text-align:center;">
            <h2>Compare Companies</h2>
            <p style="color:var(--text-muted); margin-top:8px;">No companies currently selected for comparison. Click "+ Add to Compare" on any company profile.</p>
            <button class="btn btn-primary" style="margin-top:16px;" onclick="selectCompany(COMPACT_DATA[0].org)">Return to Directory</button>
          </div>
        `;
        return;
      }}

      const comps = compareList.map(org => DETAILS_DATA[org]).filter(Boolean);

      main.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border); padding-bottom:14px;">
          <div>
            <h1 style="font-size:24px; font-weight:800;">Company Comparison</h1>
            <p style="color:var(--text-muted); font-size:14px;">Side-by-side verified facts across ${{comps.length}} companies</p>
          </div>
          <button class="btn" onclick="compareList=[]; $('#compare-count').textContent=0; renderCompareView();">Clear Comparison</button>
        </div>

        <div class="compare-matrix">
          ${{comps.map(c => {{
            const env = c.raw;
            const synth = c.synthesis;
            const claims = c.claims || [];
            const c_name = claims.find(x => x.field === 'legal_name');
            const c_form = claims.find(x => x.field === 'legal_form');
            const c_emp = claims.find(x => x.field === 'employees');
            const c_ind = claims.find(x => x.field === 'industry_code');
            const c_web = claims.find(x => x.field === 'official_website');
            const c_rev = claims.find(x => x.field === 'revenue');
            const c_res = claims.find(x => x.field === 'operating_result' || x.field === 'annual_result');

            return `
              <div class="compare-col">
                <h3 style="font-size:18px; font-weight:800; margin-bottom:6px;">${{escHtml(c_name ? c_name.value : c.org)}}</h3>
                <div style="font-size:13px; color:var(--text-muted); margin-bottom:12px;">
                  <code>${{escHtml(c.org)}}</code> · <span class="badge badge-${{c.status}}">${{c.status}}</span>
                </div>

                <div style="display:flex; flex-direction:column; gap:8px; font-size:14px;">
                  <div><b>Legal Form:</b> ${{escHtml(c_form ? c_form.value : '—')}}</div>
                  <div><b>Employees:</b> ${{c_emp && c_emp.value !== null ? escHtml(c_emp.value) : '0'}}</div>
                  <div><b>Revenue:</b> ${{money(c_rev ? c_rev.value : null)}}</div>
                  <div><b>Operating Result:</b> ${{money(c_res ? c_res.value : null)}}</div>
                  <div><b>NACE Industry:</b> ${{escHtml(c_ind ? c_ind.value : '—')}}</div>
                  <div><b>Website:</b> ${{c_web ? `<a href="${{escHtml(c_web.value)}}" target="_blank" rel="noopener noreferrer">Verified ↗</a>` : 'Not Available'}}</div>
                  <div><b>Total Claims:</b> ${{claims.length}}</div>
                  <div><b>Unknowns:</b> ${{synth.unknowns ? synth.unknowns.length : 0}} missing</div>
                </div>

                <button class="btn btn-primary" style="width:100%; margin-top:14px;" onclick="selectCompany('${{escHtml(c.org)}}')">
                  Open Full Profile
                </button>
              </div>
            `;
          }}).join('')}}
        </div>
      `;
    }}

    function renderAboutView() {{
      const main = $('#main');
      main.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border); padding-bottom:14px;">
          <div>
            <h1 style="font-size:24px; font-weight:800;">About Signalpost & Verification Guide</h1>
            <p style="color:var(--text-muted); font-size:14px;">Built for the Builderr Norwegian Company Research Challenge</p>
          </div>
          <button class="btn btn-primary" onclick="selectCompany(COMPACT_DATA[0].org)">Return to Directory</button>
        </div>

        <div style="display:flex; flex-direction:column; gap:16px; margin-top:16px; font-size:15px; line-height:1.7;">
          <div class="section-block">
            <h3 style="margin-bottom:8px;">1. Strict Exact-Entity Proof (Rule N2)</h3>
            <p>
              In Signalpost, 9-digit organisation numbers are the sole primary key. Websites, job vacancies, and company profiles are published ONLY when backed by exact-entity proof (presence of the 9-digit orgnr or official subunit registration). Name similarity and search rankings are candidates, never evidence.
            </p>
          </div>

          <div class="section-block">
            <h3 style="margin-bottom:8px;">2. Zero Fabrication & Verbatim Claim Spans (Rule N3)</h3>
            <p>
              Missing data is never converted to 0 or empty strings. Every published claim contains a canonical source URL, retrieval timestamp, immutable content-addressed SHA-256 snapshot reference, and an exact verbatim <code>claim_span</code> excerpt found within the stored snapshot.
            </p>
          </div>

          <div class="section-block">
            <h3 style="margin-bottom:8px;">3. The Six Information States</h3>
            <p>
              Signalpost envelopes categorize every field and terminal outcome into standardized, color-and-text paired badges:
            </p>
            <ul style="margin:8px 0 0 20px;">
              <li><b>● Available</b> — exact evidence verified and published.</li>
              <li><b>▲ Ambiguous</b> — conflicting or inconclusive identity candidates found; publication withheld.</li>
              <li><b>○ Not Available</b> — source checked, entity confirmed not present or unfiled.</li>
              <li><b>⊘ Not Applicable</b> — filing obligation does not apply to this legal form.</li>
              <li><b>✕ Failed</b> — upstream API error or timeout; graceful degradation.</li>
            </ul>
          </div>

          <div class="section-block">
            <h3 style="margin-bottom:8px;">4. Allowed Sources & Prohibited Scrapers (Rule N5)</h3>
            <p>
              All claims originate deterministically from permitted open data sources: Brønnøysund Enhetsregisteret bulk, open APIs, Regnskapsregisteret, official NAV pam-stilling feed, and company-owned websites after exact-entity proof. Forbidden scrapers (LinkedIn, Finn.no, Google result scraping, paywalled directories) are quarantined.
            </p>
          </div>

          <div class="section-block">
            <h3 style="margin-bottom:8px;">5. Run Metadata</h3>
            <p>
              <b>Run ID:</b> <code>${{escHtml(RUN_META.run_id || 'dev-batch')}}</code><br>
              <b>Date:</b> ${{escHtml(RUN_META.started_at || '2026-10-04')}}<br>
              <b>Strategy Version:</b> <code>0.6.0</code> (frozen in config/strategies.toml)<br>
              <b>Notice:</b> Research demo for the Builderr Signalpost challenge.
            </p>
          </div>
        </div>
      `;
    }}

    // Header buttons
    $('#compare-btn').onclick = () => {{
      isCompareMode = true;
      isAboutMode = false;
      renderProfile();
    }};

    $('#about-btn').onclick = () => {{
      isAboutMode = true;
      isCompareMode = false;
      renderProfile();
    }};

    // Filter event listeners
    ['q-input', 'filter-status', 'filter-form', 'filter-web', 'filter-jobs', 'sort-select'].forEach(id => {{
      $('#' + id).addEventListener('input', () => {{
        renderList();
      }});
    }});

    $('#reset-filters').onclick = () => {{
      $('#q-input').value = '';
      $('#filter-status').value = '';
      $('#filter-form').value = '';
      $('#filter-web').value = '';
      $('#filter-jobs').value = '';
      $('#sort-select').value = 'name';
      renderList();
    }};

    // Keyboard navigation
    window.addEventListener('keydown', e => {{
      if (e.key === 'Escape') {{
        closeEvidenceModal();
      }}
    }});

    // Handle URL hash navigation & immediate init
    function initFromHash() {{
      const hash = window.location.hash.replace('#', '');
      if (hash && DETAILS_DATA[hash]) {{
        selectedOrgnr = hash;
      }} else if (!selectedOrgnr && COMPACT_DATA.length > 0) {{
        selectedOrgnr = COMPACT_DATA[0].org;
      }}
      renderList();
      renderProfile();
      if (hash && window.innerWidth < 960) {{
        const main = $('#main');
        if (main) {{
          main.scrollIntoView();
        }}
      }}
    }}

    window.addEventListener('hashchange', initFromHash);
    window.addEventListener('DOMContentLoaded', initFromHash);
    initFromHash();
  </script>
</body>
</html>
"""


def render_static_company_page(env: dict[str, Any], run_meta: dict[str, Any] | None = None) -> str:
    """Pre-render a static company page for site/c/<orgnr>.html that works server-less without JavaScript."""
    org = str(env.get("organisation_number", ""))
    status = env.get("status", "available")
    claims = env.get("claims", [])
    evidences = env.get("evidence", [])
    synthesis = env.get("synthesis", {}) or {}

    c_map = {c.get("field"): c for c in claims if c.get("field")}
    ev_map = {e.get("id"): e for e in evidences if e.get("id")}

    name = c_map.get("legal_name", {}).get("value") or f"Entity {org}"
    form = c_map.get("legal_form", {}).get("value") or "—"
    emp = c_map.get("employees", {}).get("value")
    web = c_map.get("official_website", {}).get("value") or ""
    ind_code = c_map.get("industry_code", {}).get("value") or "—"
    addr = c_map.get("business_address", {}).get("value") or {}
    muni = addr.get("municipality") or addr.get("poststed") or "Not reported"

    rev = c_map.get("revenue", {}).get("value")
    res = c_map.get("operating_result", {}).get("value") or c_map.get("annual_result", {}).get("value")
    equity = c_map.get("equity", {}).get("value")

    css = get_viewer_css()

    # Pre-render narrative sentences
    narrative_parts = []
    for s in synthesis.get("sentences", []):
        cids = s.get("claim_ids", [])
        chips = " ".join(f'<span class="citation-chip">[{esc(cid[:4])}]</span>' for cid in cids)
        narrative_parts.append(f'<span>{esc(s.get("text"))} {chips}</span>')
    narrative_html = " ".join(narrative_parts)

    # Unknowns
    unknowns = synthesis.get("unknowns", [])
    unknowns_html = "".join(
        f'<div class="unknown-item"><b>{esc(u.get("topic"))}:</b> <code>{esc(u.get("why"))}</code><br><small style="color:var(--text-muted);">Checked sources: {esc(", ".join(u.get("checked", [])))}</small></div>'
        for u in unknowns
    )

    claims_rows = []
    for c in claims:
        eids = c.get("evidence_ids", [])
        ev = ev_map.get(eids[0], {}) if eids else {}
        s_url = ev.get("source_url", "#")
        span = ev.get("claim_span", "")
        val = c.get("value")
        if isinstance(val, dict):
            if val.get("name"):
                display_val = f"{val.get('name')} ({val.get('role', '')})"
            elif val.get("title"):
                display_val = val.get("title")
            else:
                display_val = json.dumps(val, ensure_ascii=False)
        else:
            display_val = str(val) if val is not None else "—"
        f_val = display_val[:60]
        claims_rows.append(
            f'<tr>'
            f'<td data-label="Field"><code>{esc(c.get("field"))}</code></td>'
            f'<td data-label="Value"><b>{esc(f_val)}</b></td>'
            f'<td data-label="Source"><a href="{esc(s_url)}" target="_blank" rel="noopener noreferrer">Source ↗</a></td>'
            f'<td data-label="Span quote"><small>{esc(span)}</small></td>'
            f'</tr>'
        )
    claims_rows_html = "".join(claims_rows)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="default-src 'self' 'unsafe-inline' data:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:;">
  <title>{esc(name)} ({esc(org)}) — Signalpost Static Profile</title>
  <meta name="description" content="Verified facts for {esc(name)} (org.nr {esc(org)}).">
  <style>{css}</style>
</head>
<body>
  <a href="#main" class="skip-link">Skip to main content</a>
  <header class="app-header" role="banner">
    <div class="brand-wrap">
      <a href="../index.html#{esc(org)}" class="brand-logo">
        <span style="color:var(--accent);">◆</span> Signalpost
      </a>
      <span class="brand-badge">Static Page</span>
    </div>
    <div class="header-actions">
      <a href="../index.html#{esc(org)}" class="btn btn-primary">← Interactive Viewer</a>
      <a href="../data/{esc(org)}.json" class="btn" download>Download JSON</a>
    </div>
  </header>

  <div class="layout-container" style="grid-template-columns: 1fr; max-width: 1100px;">
    <main id="main" class="profile-view" role="main">
      <div class="profile-header">
        <div class="company-title-area">
          <h1>{esc(name)}</h1>
          <div class="company-meta-line">
            <span><b>Org.nr:</b> {esc(org)}</span>
            <span class="badge badge-{esc(status)}">{esc(status)}</span>
            <span>{esc(form)}</span>
            {f'<a href="{esc(web)}" target="_blank" rel="noopener noreferrer" style="color:var(--accent); font-weight:600;">🌐 Verified Website ↗</a>' if web else ''}
          </div>
        </div>
      </div>

      <section class="synthesis-card" aria-labelledby="synth-title">
        <h2 id="synth-title">Verified Narrative Synthesis</h2>
        <div class="synthesis-narrative">{narrative_html}</div>
      </section>

      <section class="facts-grid" aria-label="Key Facts">
        <div class="fact-item">
          <div class="fact-label">Employees</div>
          <div class="fact-value">{esc(emp) if emp is not None else '0'}</div>
          <div class="fact-sub">Registered employees</div>
        </div>
        <div class="fact-item">
          <div class="fact-label">Revenue (Latest)</div>
          <div class="fact-value">{format_currency(rev)}</div>
        </div>
        <div class="fact-item">
          <div class="fact-label">Operating Result</div>
          <div class="fact-value">{format_currency(res)}</div>
        </div>
        <div class="fact-item">
          <div class="fact-label">Equity</div>
          <div class="fact-value">{format_currency(equity)}</div>
        </div>
        <div class="fact-item">
          <div class="fact-label">Municipality</div>
          <div class="fact-value">{esc(muni)}</div>
        </div>
        <div class="fact-item">
          <div class="fact-label">Industry (NACE)</div>
          <div class="fact-value" style="font-size:15px;">{esc(ind_code)}</div>
        </div>
      </section>

      <section class="section-block" aria-labelledby="unverified-title">
        <h3 id="unverified-title">Missing / Unverified Data Points ({len(unknowns)})</h3>
        <div class="unknowns-list">{unknowns_html}</div>
      </section>

      <section class="section-block" aria-labelledby="claims-title">
        <h3 id="claims-title">All Backed Claims ({len(claims)})</h3>
        <div class="data-table-wrap">
          <table class="data-table responsive-cards-table">
            <thead>
              <tr><th>Field</th><th>Value</th><th>Source Link</th><th>Verbatim Span Quote</th></tr>
            </thead>
            <tbody>
              {claims_rows_html}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  </div>
</body>
</html>
"""


def build_viewer_site(
    envelopes_path: str | Path,
    out_dir: str | Path = "site",
    standalone_path: str | Path | None = None,
    run_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile result envelopes into a complete static site and standalone viewer."""
    env_path = Path(envelopes_path)
    site_dir = Path(out_dir)
    site_dir.mkdir(parents=True, exist_ok=True)

    data_dir = site_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    company_pages_dir = site_dir / "c"
    company_pages_dir.mkdir(parents=True, exist_ok=True)

    assets_dir = site_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    envelopes = []
    with env_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                envelopes.append(json.loads(line))

    run_meta = run_meta or {
        "run_id": "phase-06-build",
        "started_at": "2026-10-04T00:00:00Z",
        "total_envelopes": len(envelopes),
    }

    # 1. Build compact index (< 400 KB for 1,100 companies)
    compact_rows = [extract_compact_index_entry(e) for e in envelopes]
    index_json_path = data_dir / "index.json"
    index_json_content = json.dumps(compact_rows, ensure_ascii=False, indent=None)
    index_json_path.write_text(index_json_content, encoding="utf-8")
    index_size_kb = len(index_json_content.encode("utf-8")) / 1024.0

    # 2. Write individual company JSON files and static HTML pages
    for env in envelopes:
        org = str(env.get("organisation_number", ""))
        # site/data/<orgnr>.json
        (data_dir / f"{org}.json").write_text(json.dumps(env, ensure_ascii=False, indent=2), encoding="utf-8")
        # site/c/<orgnr>.html
        static_html = render_static_company_page(env, run_meta)
        (company_pages_dir / f"{org}.html").write_text(static_html, encoding="utf-8")

    # 3. Write assets
    (assets_dir / "style.css").write_text(get_viewer_css(), encoding="utf-8")

    # 4. Generate standalone index.html
    full_html = render_standalone_html(envelopes, run_meta)
    (site_dir / "index.html").write_text(full_html, encoding="utf-8")

    if standalone_path:
        st_p = Path(standalone_path)
        st_p.parent.mkdir(parents=True, exist_ok=True)
        st_p.write_text(full_html, encoding="utf-8")

    return {
        "envelopes_count": len(envelopes),
        "index_json_kb": round(index_size_kb, 2),
        "site_dir": str(site_dir),
        "standalone_path": str(standalone_path) if standalone_path else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Signalpost Static Company Viewer Compiler")
    parser.add_argument("--envelopes", "-i", required=True, help="Input envelopes JSONL file")
    parser.add_argument("--out", "-o", default="site", help="Output site directory")
    parser.add_argument("--standalone", help="Optional path to emit standalone index.html (e.g. out/viewer/index.html)")
    args = parser.parse_args()

    summary = build_viewer_site(args.envelopes, args.out, args.standalone)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
