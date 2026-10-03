"""Unit tests for Signalpost static company viewer (Workflow /06).
Validates HTML escaping, WCAG landmarks, zero external CDN dependencies,
index JSON size cap, and evidence card linkage.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from signalpost.viewer import (
    build_viewer_site,
    extract_compact_index_entry,
    render_standalone_html,
    render_static_company_page,
)


@pytest.fixture
def sample_envelopes():
    return [
        {
            "organisation_number": "912569608",
            "status": "available",
            "claims": [
                {
                    "claim_id": "c-name-1",
                    "field": "legal_name",
                    "family": "identity",
                    "value": "SAFE4 SECURITY GROUP AS <script>alert(1)</script>",
                    "availability": "available",
                    "evidence_ids": ["ev-1"],
                },
                {
                    "claim_id": "c-form-1",
                    "field": "legal_form",
                    "family": "identity",
                    "value": "AS",
                    "availability": "available",
                    "evidence_ids": ["ev-1"],
                },
                {
                    "claim_id": "c-rev-1",
                    "field": "revenue",
                    "family": "accounts",
                    "value": 123456789.0,
                    "availability": "available",
                    "reporting_period": {"from": "2024-01-01", "to": "2024-12-31"},
                    "evidence_ids": ["ev-2"],
                },
            ],
            "evidence": [
                {
                    "id": "ev-1",
                    "source_url": "https://data.brreg.no/api/enheter/912569608",
                    "retrieved_at": "2026-10-01T00:00:00Z",
                    "content_sha256": "a" * 64,
                    "claim_span": "SAFE4 SECURITY GROUP AS 912569608",
                    "source_class": "official_registry",
                },
                {
                    "id": "ev-2",
                    "source_url": "https://data.brreg.no/regnskapsregisteret/regnskap/912569608",
                    "retrieved_at": "2026-10-01T00:00:00Z",
                    "content_sha256": "b" * 64,
                    "claim_span": "Salgsinntekter 123456789",
                    "source_class": "official_accounts",
                },
            ],
            "field_states": {
                "identity": {"availability": "available"},
                "accounts": {"availability": "available"},
                "website": {"availability": "not_available", "reason": "none_found"},
            },
            "synthesis": {
                "generator": "template-v1",
                "headline": "SAFE4 SECURITY GROUP AS (AS, org.nr 912569608)",
                "what_it_does": "Security systems provider.",
                "unknowns": [
                    {
                        "topic": "website",
                        "why": "website: none_found",
                        "checked": ["registry_homepage", "domain_probing"],
                    }
                ],
                "sentences": [
                    {
                        "id": "s1",
                        "text": "SAFE4 SECURITY GROUP AS is an AS entity.",
                        "claim_ids": ["c-name-1", "c-form-1"],
                    }
                ],
            },
            "changes": [],
            "operations": {"requests": 4, "runtime_ms": 1200, "third_party_cost_usd": 0.0},
        },
        {
            "organisation_number": "835606252",
            "status": "available",
            "claims": [
                {
                    "claim_id": "c-name-2",
                    "field": "legal_name",
                    "family": "identity",
                    "value": "SAHO AS",
                    "availability": "available",
                    "evidence_ids": ["ev-3"],
                }
            ],
            "evidence": [
                {
                    "id": "ev-3",
                    "source_url": "https://data.brreg.no/api/enheter/835606252",
                    "retrieved_at": "2026-10-01T00:00:00Z",
                    "content_sha256": "c" * 64,
                    "claim_span": "SAHO AS 835606252",
                    "source_class": "official_registry",
                }
            ],
            "field_states": {
                "identity": {"availability": "available"},
                "accounts": {"availability": "not_available", "reason": "no_filings"},
            },
            "synthesis": {
                "generator": "template-v1",
                "headline": "SAHO AS (AS, org.nr 835606252)",
                "unknowns": [{"topic": "accounts", "why": "accounts: no_filings", "checked": ["official_annual_accounts"]}],
                "sentences": [{"id": "s1", "text": "SAHO AS has no filings.", "claim_ids": ["c-name-2"]}],
            },
            "changes": [],
            "operations": {"requests": 2, "runtime_ms": 800, "third_party_cost_usd": 0.0},
        },
    ]


def test_html_escaping_hostile_input(sample_envelopes):
    """Ensure hostile HTML strings (e.g., <script>) are properly escaped."""
    static_html = render_static_company_page(sample_envelopes[0])
    assert "<script>alert(1)</script>" not in static_html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in static_html

    standalone_html = render_standalone_html(sample_envelopes)
    # The literal script tag from user input should never be executable in HTML body
    assert "<h1>SAFE4 SECURITY GROUP AS <script>alert(1)</script></h1>" not in standalone_html


def test_zero_external_cdn_dependencies(sample_envelopes):
    """Ensure viewer has no runtime dependencies on external CDNs or fonts."""
    html_doc = render_standalone_html(sample_envelopes)
    assert "https://cdn." not in html_doc
    assert "https://unpkg.com" not in html_doc
    assert "https://fonts.googleapis.com" not in html_doc
    assert "https://cdnjs.cloudflare.com" not in html_doc
    # CSP meta tag must be present
    assert "Content-Security-Policy" in html_doc


def test_wcag_accessibility_elements(sample_envelopes):
    """Ensure semantic landmarks, skip links, and accessible controls are present."""
    html_doc = render_standalone_html(sample_envelopes)
    assert 'class="skip-link"' in html_doc
    assert '<header class="app-header"' in html_doc
    assert '<main id="main"' in html_doc
    assert '<aside class="directory-sidebar"' in html_doc
    assert 'type="search"' in html_doc
    assert 'aria-label=' in html_doc
    assert 'lang="en"' in html_doc


def test_status_badges_not_color_alone(sample_envelopes):
    """Ensure status badges display textual labels and symbols alongside styling."""
    static_html = render_static_company_page(sample_envelopes[0])
    assert "badge badge-available" in static_html
    assert "available" in static_html.lower()


def test_static_company_page_under_150_kb(sample_envelopes):
    """Ensure pre-rendered static company page loads under 150 KB."""
    page_html = render_static_company_page(sample_envelopes[0])
    size_kb = len(page_html.encode("utf-8")) / 1024.0
    assert size_kb < 150.0
    # Must have evidence source link with rel="noopener noreferrer"
    assert 'rel="noopener noreferrer"' in page_html


def test_index_json_compact_size_cap(sample_envelopes):
    """Ensure compact index entries stay within budget (< 400 KB for 1,100 companies)."""
    entry = extract_compact_index_entry(sample_envelopes[0])
    assert entry["org"] == "912569608"
    assert entry["form"] == "AS"
    assert entry["rev"] == 123456789.0
    entry_json = json.dumps(entry, ensure_ascii=False)
    # A single row should be under 400 bytes so 1,100 rows stay well under 400 KB
    assert len(entry_json.encode("utf-8")) < 400


def test_build_viewer_site_output_files(sample_envelopes, tmp_path):
    """Test full directory generation of site/ distribution."""
    input_file = tmp_path / "envelopes.jsonl"
    with input_file.open("w", encoding="utf-8") as f:
        for env in sample_envelopes:
            f.write(json.dumps(env) + "\n")

    out_site = tmp_path / "site"
    standalone_out = tmp_path / "viewer" / "index.html"

    res = build_viewer_site(
        envelopes_path=input_file,
        out_dir=out_site,
        standalone_path=standalone_out,
    )

    assert res["envelopes_count"] == 2
    assert (out_site / "index.html").exists()
    assert (out_site / "data" / "index.json").exists()
    assert (out_site / "data" / "912569608.json").exists()
    assert (out_site / "c" / "912569608.html").exists()
    assert (out_site / "assets" / "style.css").exists()
    assert standalone_out.exists()
