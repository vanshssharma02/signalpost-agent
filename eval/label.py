#!/usr/bin/env python3
"""
label.py — Generate manual labelling template, interactive sheet, and gold truth.
"""
from __future__ import annotations

import csv
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEV_JSONL = ROOT / "eval" / "sets" / "dev.jsonl"
EVAL_DIR = ROOT / "eval"
LABELS_DIR = EVAL_DIR / "labels"
GOLD_DIR = EVAL_DIR / "gold"


def generate_labels():
    LABELS_DIR.mkdir(parents=True, exist_ok=True)
    GOLD_DIR.mkdir(parents=True, exist_ok=True)

    companies = []
    with DEV_JSONL.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                companies.append(json.loads(line))

    # 1. Generate dev-labels-template.csv
    csv_path = EVAL_DIR / "dev-labels-template.csv"
    csv_fields = [
        "organisation_number",
        "name",
        "legal_form",
        "municipality",
        "industry_code",
        "industry_label",
        "employees",
        "registry_website",
        "candidate_website",
        "official_website",  # URL or 'none'
        "has_open_jobs",     # 'y', 'n', 'unknown'
        "has_recent_news",    # 'y', 'n', 'unknown'
        "same_entity_verification",  # 'same_company', 'different_company', 'cannot_tell'
        "notes"
    ]

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        for c in companies:
            web = c.get("website") or ""
            cand_url = f"https://{web}" if web and not web.startswith("http") else web
            writer.writerow({
                "organisation_number": c["organisation_number"],
                "name": c["name"],
                "legal_form": c.get("legal_form", ""),
                "municipality": c.get("municipality", ""),
                "industry_code": c.get("industry_code", ""),
                "industry_label": c.get("industry_label", ""),
                "employees": c.get("employees") if c.get("employees") is not None else "",
                "registry_website": web,
                "candidate_website": cand_url,
                "official_website": cand_url if web else "none",
                "has_open_jobs": "unknown",
                "has_recent_news": "unknown",
                "same_entity_verification": "same_company" if web else "cannot_tell",
                "notes": "Registry-declared website" if web else ""
            })

    # 2. Generate dev-labels-template.jsonl
    jsonl_template_path = EVAL_DIR / "dev-labels-template.jsonl"
    with jsonl_template_path.open("w", encoding="utf-8") as f:
        for c in companies:
            web = c.get("website") or ""
            cand_url = f"https://{web}" if web and not web.startswith("http") else web
            row = {
                "organisation_number": c["organisation_number"],
                "name": c["name"],
                "legal_form": c.get("legal_form"),
                "municipality": c.get("municipality"),
                "industry_code": c.get("industry_code"),
                "industry_label": c.get("industry_label"),
                "employees": c.get("employees"),
                "registry_website": web,
                "candidate_website": cand_url,
                "official_website": cand_url if web else "none",
                "has_open_jobs": "unknown",
                "has_recent_news": "unknown",
                "same_entity_verification": "same_company" if web else "cannot_tell",
                "notes": "Registry-declared website" if web else ""
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # 3. Generate initial eval/gold/dev_labels.jsonl
    gold_path = GOLD_DIR / "dev_labels.jsonl"
    with gold_path.open("w", encoding="utf-8") as f:
        for c in companies:
            web = c.get("website") or ""
            cand_url = f"https://{web}" if web and not web.startswith("http") else web
            row = {
                "organisation_number": c["organisation_number"],
                "name": c["name"],
                "official_website": cand_url if web else "none",
                "has_open_jobs": "unknown",
                "has_recent_news": "unknown",
                "same_company_verified": bool(web),
                "notes": "Initial baseline seed from registry snapshot"
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # 4. Generate static HTML labelling sheet (eval/labels/sheet.html)
    sheet_path = LABELS_DIR / "sheet.html"
    companies_json = json.dumps(companies, ensure_ascii=False).replace("</", "<\\/")

    html_content = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Signalpost Dev Set Label Sheet (150 Companies)</title>
<style>
  :root {{
    --bg: #f8f9fa; --surface: #ffffff; --ink: #1e293b; --muted: #64748b;
    --border: #e2e8f0; --primary: #2563eb; --good: #16a34a; --warn: #d97706; --bad: #dc2626;
  }}
  body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--ink); line-height: 1.5; }}
  header {{ background: var(--surface); border-bottom: 1px solid var(--border); padding: 16px 24px; position: sticky; top: 0; z-index: 10; display: flex; justify-content: space-between; align-items: center; }}
  h1 {{ font-size: 1.25rem; margin: 0; }}
  .progress {{ font-weight: 600; color: var(--primary); }}
  .container {{ max-width: 1200px; margin: 24px auto; padding: 0 16px; }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
  .card-head {{ display: flex; justify-content: space-between; align-items: baseline; border-bottom: 1px solid var(--border); padding-bottom: 10px; margin-bottom: 12px; }}
  .comp-name {{ font-size: 1.15rem; font-weight: 700; color: var(--ink); }}
  .orgnr {{ font-family: monospace; font-size: 0.95rem; background: #e2e8f0; padding: 2px 6px; border-radius: 4px; }}
  .meta-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; margin-bottom: 16px; font-size: 0.875rem; }}
  .meta-item span {{ display: block; color: var(--muted); font-size: 0.75rem; text-transform: uppercase; }}
  .label-controls {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; background: #f1f5f9; padding: 14px; border-radius: 6px; }}
  .btn-group {{ display: flex; gap: 8px; margin-top: 6px; }}
  button {{ padding: 6px 12px; border: 1px solid var(--border); background: var(--surface); border-radius: 4px; cursor: pointer; font-size: 0.875rem; }}
  button:hover {{ background: #f8fafc; }}
  button.active {{ background: var(--primary); color: white; border-color: var(--primary); }}
  button.active.good {{ background: var(--good); border-color: var(--good); }}
  button.active.bad {{ background: var(--bad); border-color: var(--bad); }}
  button.active.warn {{ background: var(--warn); border-color: var(--warn); }}
  input[type="text"] {{ width: 100%; padding: 6px 10px; border: 1px solid var(--border); border-radius: 4px; font-size: 0.875rem; box-sizing: border-box; }}
  .actions {{ display: flex; gap: 12px; align-items: center; }}
</style>
</head>
<body>
<header>
  <div>
    <h1>Signalpost Dev Set Label Sheet</h1>
    <small style="color:var(--muted)">150 Norwegian Companies · Estimated ~1.5 min per company</small>
  </div>
  <div class="actions">
    <span class="progress" id="progress-text">0 / 150 completed</span>
    <button id="export-json" style="background:var(--primary);color:white;font-weight:600">Export dev_labels.jsonl</button>
  </div>
</header>
<main class="container" id="list"></main>

<script>
const COMPANIES = {companies_json};
let labels = JSON.parse(localStorage.getItem('signalpost_dev_labels') || '{{}}');

function save() {{
  localStorage.setItem('signalpost_dev_labels', JSON.stringify(labels));
  updateProgress();
}}

function updateProgress() {{
  const count = Object.keys(labels).length;
  document.getElementById('progress-text').textContent = `${{count}} / ${{COMPANIES.length}} completed`;
}}

function render() {{
  const list = document.getElementById('list');
  list.innerHTML = COMPANIES.map((c, idx) => {{
    const org = c.organisation_number;
    const l = labels[org] || {{
      official_website: c.website ? (c.website.startsWith('http') ? c.website : 'https://' + c.website) : 'none',
      status: c.website ? 'same_company' : 'cannot_tell',
      jobs: 'unknown',
      news: 'unknown'
    }};
    return `
    <div class="card" id="card-${{org}}">
      <div class="card-head">
        <div>
          <span style="color:var(--muted);margin-right:8px">#${{idx + 1}}</span>
          <span class="comp-name">${{c.name}}</span>
        </div>
        <span class="orgnr">${{org}}</span>
      </div>
      <div class="meta-grid">
        <div class="meta-item"><span>Legal Form</span><strong>${{c.legal_form || '—'}}</strong></div>
        <div class="meta-item"><span>Location</span><strong>${{c.municipality || '—'}}</strong></div>
        <div class="meta-item"><span>Industry</span><strong>${{c.industry_code || '—'}} ${{c.industry_label || ''}}</strong></div>
        <div class="meta-item"><span>Employees</span><strong>${{c.employees !== null ? c.employees : 'Not reported'}}</strong></div>
        <div class="meta-item"><span>Registry Website</span><strong>${{c.website ? `<a href="${{c.website.startsWith('http')?c.website:'https://'+c.website}}" target="_blank">${{c.website}}</a>` : 'None'}}</strong></div>
      </div>
      <div class="label-controls">
        <div>
          <label style="font-size:0.75rem;text-transform:uppercase;color:var(--muted);font-weight:700">Official Website URL (or 'none')</label>
          <input type="text" id="url-${{org}}" value="${{l.official_website || 'none'}}" onchange="onUrlChange('${{org}}', this.value)">
          <div class="btn-group" style="margin-top:8px">
            <button class="${{l.status === 'same_company' ? 'active good' : ''}}" onclick="setStatus('${{org}}', 'same_company')">Same Company</button>
            <button class="${{l.status === 'different_company' ? 'active bad' : ''}}" onclick="setStatus('${{org}}', 'different_company')">Different Company</button>
            <button class="${{l.status === 'cannot_tell' ? 'active warn' : ''}}" onclick="setStatus('${{org}}', 'cannot_tell')">Cannot Tell</button>
          </div>
        </div>
        <div>
          <div style="margin-bottom:8px">
            <span style="font-size:0.75rem;text-transform:uppercase;color:var(--muted);font-weight:700">Has Open Jobs</span>
            <div class="btn-group">
              <button class="${{l.jobs === 'y' ? 'active good' : ''}}" onclick="setJobs('${{org}}', 'y')">Yes</button>
              <button class="${{l.jobs === 'n' ? 'active' : ''}}" onclick="setJobs('${{org}}', 'n')">No</button>
              <button class="${{l.jobs === 'unknown' ? 'active warn' : ''}}" onclick="setJobs('${{org}}', 'unknown')">Unknown</button>
            </div>
          </div>
          <div>
            <span style="font-size:0.75rem;text-transform:uppercase;color:var(--muted);font-weight:700">Has Recent News</span>
            <div class="btn-group">
              <button class="${{l.news === 'y' ? 'active good' : ''}}" onclick="setNews('${{org}}', 'y')">Yes</button>
              <button class="${{l.news === 'n' ? 'active' : ''}}" onclick="setNews('${{org}}', 'n')">No</button>
              <button class="${{l.news === 'unknown' ? 'active warn' : ''}}" onclick="setNews('${{org}}', 'unknown')">Unknown</button>
            </div>
          </div>
        </div>
      </div>
    </div>
    `;
  }}).join('');
  updateProgress();
}}

function getEntry(org) {{
  if (!labels[org]) {{
    const c = COMPANIES.find(x => x.organisation_number === org);
    labels[org] = {{
      official_website: c.website ? (c.website.startsWith('http') ? c.website : 'https://' + c.website) : 'none',
      status: c.website ? 'same_company' : 'cannot_tell',
      jobs: 'unknown',
      news: 'unknown'
    }};
  }}
  return labels[org];
}}

window.onUrlChange = (org, val) => {{ getEntry(org).official_website = val.trim(); save(); }};
window.setStatus = (org, val) => {{ getEntry(org).status = val; save(); render(); }};
window.setJobs = (org, val) => {{ getEntry(org).jobs = val; save(); render(); }};
window.setNews = (org, val) => {{ getEntry(org).news = val; save(); render(); }};

document.getElementById('export-json').onclick = () => {{
  const rows = COMPANIES.map(c => {{
    const org = c.organisation_number;
    const l = labels[org] || {{
      official_website: c.website ? (c.website.startsWith('http') ? c.website : 'https://' + c.website) : 'none',
      status: c.website ? 'same_company' : 'cannot_tell',
      jobs: 'unknown',
      news: 'unknown'
    }};
    return JSON.stringify({{
      organisation_number: org,
      name: c.name,
      official_website: l.official_website,
      same_company_verified: l.status === 'same_company',
      has_open_jobs: l.jobs,
      has_recent_news: l.news
    }});
  }});
  const blob = new Blob([rows.join('\\n') + '\\n'], {{ type: 'application/x-jsonlines' }});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'dev_labels.jsonl';
  a.click();
  URL.revokeObjectURL(url);
}};

render();
</script>
</body>
</html>
"""
    sheet_path.write_text(html_content, encoding="utf-8")
    print(f"Generated {csv_path.name}")
    print(f"Generated {jsonl_template_path.name}")
    print(f"Generated {gold_path.name}")
    print(f"Generated {sheet_path.name}")


if __name__ == "__main__":
    generate_labels()
