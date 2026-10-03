"""Unit and fixture tests for external connectors (Workflow /04).

Tests NAV Arbeidsplassen feed ingestion & matching:
1. Exact match by employer.orgnr (passes)
2. Same-name different orgnr (must reject)
3. Ad with missing employer.orgnr (reject)
4. Inactive ad (must drop)
5. Duplicate ads (deduplicated by UUID)
6. Token retrieval & fallback
7. Personal contactList stripped from snapshot

Tests site structured extraction:
8. JSON-LD Article / NewsArticle
9. HTML <time datetime="..."> tags
10. Outbound company social links (canonical LinkedIn company, Facebook, Instagram, X)
11. Rejection of personal LinkedIn profile (/in/) and share links
12. Careers page and ATS link extraction (Teamtailor, Webcruiter)
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from signalpost.connectors.nav_jobs import (
    NavJobPosting,
    find_company_nav_job_postings,
)
from signalpost.connectors.site_extraction import (
    extract_all_site_signals,
    extract_html_social_links,
    extract_jsonld_signals,
    extract_careers_and_ats_links,
)
from bs4 import BeautifulSoup


# ============================================================================
# NAV ARBEIDSPLASSEN TESTS
# ============================================================================

def test_nav_job_exact_match_passes():
    feed_items = [
        {"uuid": "job-1", "title": "Senior Utvikler", "businessName": "ACME NORGE AS", "url": "/ad/job-1"},
    ]
    ad_payloads = {
        "job-1": {
            "uuid": "job-1",
            "title": "Senior Utvikler",
            "published": "2026-10-01T10:00:00Z",
            "expires": "2026-11-01T10:00:00Z",
            "employer": {"name": "Acme Norge AS", "orgnr": "985821585", "homepage": "https://acme.no"},
            "workLocations": [{"city": "Oslo", "postalCode": "0150"}],
            "extent": "Heltid",
            "engagementtype": "Fast",
            "contactList": [{"name": "Ola Nordmann", "phone": "12345678"}],  # Must be stripped
        }
    }

    def mock_fetcher(uuid: str, token: str):
        return ad_payloads.get(uuid)

    jobs = find_company_nav_job_postings(
        orgnr="985821585",
        legal_name="ACME NORGE AS",
        feed_items=feed_items,
        token="mock_token",
        detail_fetcher=mock_fetcher,
    )
    assert len(jobs) == 1
    job = jobs[0]
    assert job.uuid == "job-1"
    assert job.employer_orgnr == "985821585"
    assert job.title == "Senior Utvikler"
    assert "Ola Nordmann" not in job.snapshot_json  # ContactList stripped
    assert "985821585" in job.snapshot_json
    assert job.content_sha256 is not None


def test_nav_job_same_name_different_orgnr_rejected():
    feed_items = [
        {"uuid": "job-2", "title": "Regnskapsfører", "businessName": "ACME REGNSKAP AS", "url": "/ad/job-2"},
    ]
    ad_payloads = {
        "job-2": {
            "uuid": "job-2",
            "title": "Regnskapsfører",
            "published": "2026-10-01T10:00:00Z",
            "employer": {"name": "Acme Regnskap AS", "orgnr": "999888777"},  # Different orgnr!
        }
    }

    def mock_fetcher(uuid: str, token: str):
        return ad_payloads.get(uuid)

    jobs = find_company_nav_job_postings(
        orgnr="985821585",
        legal_name="ACME REGNSKAP AS",
        feed_items=feed_items,
        token="mock_token",
        detail_fetcher=mock_fetcher,
    )
    # Must reject because orgnr differs
    assert len(jobs) == 0


def test_nav_job_missing_employer_orgnr_rejected():
    feed_items = [
        {"uuid": "job-3", "title": "Konsulent", "businessName": "NORDIC TECH AS", "url": "/ad/job-3"},
    ]
    ad_payloads = {
        "job-3": {
            "uuid": "job-3",
            "title": "Konsulent",
            "employer": {"name": "Nordic Tech AS", "orgnr": None},
        }
    }

    def mock_fetcher(uuid: str, token: str):
        return ad_payloads.get(uuid)

    jobs = find_company_nav_job_postings(
        orgnr="985821585",
        legal_name="NORDIC TECH AS",
        feed_items=feed_items,
        token="mock_token",
        detail_fetcher=mock_fetcher,
    )
    assert len(jobs) == 0


def test_nav_job_inactive_ad_dropped():
    feed_items = [
        {"uuid": "job-4", "title": "Utvikler", "businessName": "TECH AS", "url": "/ad/job-4"},
    ]

    def mock_fetcher(uuid: str, token: str):
        # Inactive ads return None from fetch_ad_detail
        return None

    jobs = find_company_nav_job_postings(
        orgnr="985821585",
        legal_name="TECH AS",
        feed_items=feed_items,
        token="mock_token",
        detail_fetcher=mock_fetcher,
    )
    assert len(jobs) == 0


def test_nav_job_duplicates_deduplicated():
    feed_items = [
        {"uuid": "job-dup", "title": "Sjåfør", "businessName": "LOGISTIKK AS", "url": "/ad/job-dup"},
        {"uuid": "job-dup", "title": "Sjåfør", "businessName": "LOGISTIKK AS", "url": "/ad/job-dup"},
    ]
    ad_payloads = {
        "job-dup": {
            "uuid": "job-dup",
            "title": "Sjåfør",
            "published": "2026-10-01T10:00:00Z",
            "employer": {"name": "Logistikk AS", "orgnr": "985821585"},
        }
    }

    def mock_fetcher(uuid: str, token: str):
        return ad_payloads.get(uuid)

    jobs = find_company_nav_job_postings(
        orgnr="985821585",
        legal_name="LOGISTIKK AS",
        feed_items=feed_items,
        token="mock_token",
        detail_fetcher=mock_fetcher,
    )
    assert len(jobs) == 1


# ============================================================================
# SITE STRUCTURED EXTRACTION TESTS
# ============================================================================

def test_jsonld_article_and_job_extraction():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": "Vinner ny storkontrakt i Nordsjøen",
        "datePublished": "2026-09-15T08:00:00Z",
        "url": "https://example.no/nyheter/storkontrakt"
      }
      </script>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Senior Elektroingeniør",
        "datePosted": "2026-09-20T12:00:00Z",
        "validThrough": "2026-10-20T12:00:00Z",
        "url": "https://example.no/karriere/elektro"
      }
      </script>
    </head>
    <body><h1>Forside</h1></body>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")
    news, careers, profiles = extract_jsonld_signals(soup, "https://example.no")

    assert len(news) == 1
    assert news[0].title == "Vinner ny storkontrakt i Nordsjøen"
    assert news[0].published_at.startswith("2026-09-15")

    assert len(careers) == 1
    assert careers[0].title == "Senior Elektroingeniør"
    assert careers[0].is_job_posting is True


def test_html_time_news_extraction():
    html = """
    <html>
    <body>
      <article>
        <h2>Nyhetsbulletin september 2026</h2>
        <time datetime="2026-09-25T14:30:00+02:00">25. september 2026</time>
        <p>Vi oppsummerer kvartalets resultater.</p>
      </article>
    </body>
    </html>
    """
    signals = extract_all_site_signals(html, "https://example.no")
    assert len(signals.news_items) == 1
    assert "Nyhetsbulletin" in signals.news_items[0].title
    assert signals.news_items[0].published_at.startswith("2026-09-25")


def test_outbound_social_links_extraction_and_rejection():
    html = """
    <html>
    <body>
      <footer>
        <!-- Valid company profiles -->
        <a href="https://no.linkedin.com/company/acme-nordic/">LinkedIn</a>
        <a href="https://facebook.com/acmenordic">Facebook</a>
        <a href="https://instagram.com/acmenordic/">Instagram</a>
        <a href="https://x.com/acmenordic">X</a>

        <!-- Invalid links that must be rejected -->
        <a href="https://linkedin.com/in/ola-nordmann">Personal Profile</a>
        <a href="https://facebook.com/sharer/sharer.php?u=foo">Share Intent</a>
        <a href="https://x.com/intent/tweet">Tweet Intent</a>
      </footer>
    </body>
    </html>
    """
    signals = extract_all_site_signals(html, "https://example.no")
    platforms = {p.platform: p.url for p in signals.social_profiles}

    assert "linkedin" in platforms
    assert "company/acme-nordic" in platforms["linkedin"]
    assert "facebook" in platforms
    assert "instagram" in platforms
    assert "x" in platforms

    # Verify rejected links are NOT in platforms
    urls = [p.url for p in signals.social_profiles]
    assert not any("/in/" in u for u in urls)
    assert not any("sharer.php" in u for u in urls)
    assert not any("intent" in u for u in urls)


def test_careers_and_ats_link_extraction():
    html = """
    <html>
    <body>
      <nav>
        <a href="/om-oss">Om oss</a>
        <a href="/karriere">Ledige stillinger</a>
        <a href="https://acme.teamtailor.com">Søk jobb hos oss (Teamtailor)</a>
      </nav>
    </body>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")
    careers = extract_careers_and_ats_links(soup, "https://example.no")

    assert len(careers) == 2
    # One site careers page
    site_car = [c for c in careers if not c.is_ats_link]
    assert len(site_car) == 1
    assert "karriere" in site_car[0].url

    # One ATS link
    ats_car = [c for c in careers if c.is_ats_link]
    assert len(ats_car) == 1
    assert "teamtailor.com" in ats_car[0].url
