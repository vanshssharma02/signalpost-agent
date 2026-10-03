"""Structured extraction connector for verified company websites (Workflow /04).

Extracts deterministic signals strictly from verified company-owned pages:
1. Activity (company_news_item): JSON-LD Article, RSS/Atom feeds, WordPress REST, <time datetime> tags.
2. Company Profiles (company_profile): Outbound social links (LinkedIn company, Facebook, Instagram, X, YouTube).
   Strict rule: NEVER fetch or scrape third-party platform pages directly.
3. Hiring (careers_page, job_posting): Site-hosted JobPosting JSON-LD, /karriere pages, ATS links.
4. Public Brand (public_brand): og:site_name, JSON-LD name/alternateName.
5. Locations corroboration (office_address_site): Address on contact/about page.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Iterable

from bs4 import BeautifulSoup
import dateutil.parser

from norway_company_agent.website import (
    SAFE_OPENER,
    USER_AGENT,
    _social_links,
    normalize_social_url,
    structured_social_links,
)
from signalpost.identity_proof import get_registrable_domain

logger = logging.getLogger("signalpost.connectors.site_extraction")

KNOWN_ATS_DOMAINS = {
    "teamtailor.com",
    "webcruiter.com",
    "webcruiter.no",
    "easycruit.com",
    "recman.no",
    "varbi.com",
    "jobylon.com",
    "lever.co",
    "greenhouse.io",
    "workable.com",
    "bamboohr.com",
    "smartrecruiters.com",
}

CAREERS_PATH_MARKERS = {
    "karriere",
    "jobb",
    "ledige-stillinger",
    "stillinger",
    "career",
    "careers",
    "jobs",
    "work-with-us",
}


@dataclass
class ExtractedNewsItem:
    title: str
    url: str
    published_at: str
    claim_span: str
    source_type: str  # "jsonld", "rss", "wp_rest", "html_time"


@dataclass
class ExtractedProfileLink:
    platform: str
    url: str
    claim_span: str


@dataclass
class ExtractedCareerItem:
    title: str
    url: str
    is_job_posting: bool
    is_ats_link: bool
    published_at: str | None
    expires_at: str | None
    claim_span: str


@dataclass
class SiteExtractionResult:
    news_items: list[ExtractedNewsItem]
    social_profiles: list[ExtractedProfileLink]
    careers_items: list[ExtractedCareerItem]
    brand_name: str | None
    contact_email: str | None
    contact_phone: str | None
    address_snippet: str | None


def _parse_iso_date(raw_date: str) -> str | None:
    """Parse raw date string to normalized ISO-8601 UTC string."""
    if not raw_date:
        return None
    try:
        dt = dateutil.parser.parse(raw_date)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.isoformat()
    except Exception:
        return None


def extract_jsonld_signals(soup: BeautifulSoup, base_url: str) -> tuple[list[ExtractedNewsItem], list[ExtractedCareerItem], list[ExtractedProfileLink]]:
    news: list[ExtractedNewsItem] = []
    careers: list[ExtractedCareerItem] = []
    profiles: list[ExtractedProfileLink] = []

    now = datetime.now(timezone.utc)
    max_age_days = 730  # 24 months

    for script in soup.find_all("script", type="application/ld+json"):
        raw_text = script.string or ""
        if not raw_text.strip():
            continue
        try:
            data = json.loads(raw_text)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue

                # 1. Organization sameAs social profiles
                item_type = item.get("@type")
                types = set(item_type if isinstance(item_type, list) else [item_type])

                if types & {"Organization", "Corporation", "LocalBusiness", "Store", "Restaurant"}:
                    same_as = item.get("sameAs") or []
                    same_urls = same_as if isinstance(same_as, list) else [same_as]
                    for u in same_urls:
                        if isinstance(u, str):
                            norm = normalize_social_url(u.strip())
                            if norm:
                                span = u.strip()
                                profiles.append(ExtractedProfileLink(platform=norm["platform"], url=norm["url"], claim_span=span))

                # 2. NewsArticle / Article
                if types & {"Article", "NewsArticle", "BlogPosting"}:
                    title = item.get("headline") or item.get("name")
                    url = item.get("url") or item.get("mainEntityOfPage") or base_url
                    if isinstance(url, dict):
                        url = url.get("@id") or base_url
                    pub_date = item.get("datePublished") or item.get("dateModified")
                    iso_pub = _parse_iso_date(str(pub_date)) if pub_date else None
                    if title and iso_pub:
                        dt = datetime.fromisoformat(iso_pub)
                        if (now - dt).days <= max_age_days:
                            span = f'"{title}"' if title in raw_text else title
                            news.append(ExtractedNewsItem(
                                title=str(title).strip(),
                                url=urllib.parse.urljoin(base_url, str(url)),
                                published_at=iso_pub,
                                claim_span=span,
                                source_type="jsonld",
                            ))

                # 3. JobPosting
                if types & {"JobPosting"}:
                    title = item.get("title") or item.get("name")
                    pub = _parse_iso_date(str(item.get("datePosted"))) if item.get("datePosted") else None
                    valid_thru = _parse_iso_date(str(item.get("validThrough"))) if item.get("validThrough") else None
                    job_url = item.get("url") or base_url
                    if title:
                        span = f'"{title}"' if title in raw_text else title
                        careers.append(ExtractedCareerItem(
                            title=str(title).strip(),
                            url=urllib.parse.urljoin(base_url, str(job_url)),
                            is_job_posting=True,
                            is_ats_link=False,
                            published_at=pub,
                            expires_at=valid_thru,
                            claim_span=span,
                        ))
        except Exception:
            continue

    return news, careers, profiles


def extract_html_social_links(soup: BeautifulSoup, base_url: str) -> list[ExtractedProfileLink]:
    """Extract and validate outbound company social profiles from page DOM."""
    profiles: list[ExtractedProfileLink] = []
    seen_urls: set[str] = set()

    links = _social_links(base_url, soup)
    for link_dict in links:
        platform = link_dict["platform"]
        canon_url = link_dict["url"]
        if canon_url in seen_urls:
            continue

        # Look up corresponding href in soup for verbatim claim span
        span = ""
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or len(href) < 5:
                continue
            if canon_url in href or href in canon_url:
                span = href
                break
            if platform in href.lower() and any(part in href.lower() for part in canon_url.lower().split("/") if len(part) >= 3 and part not in ("http:", "https:", "www", "com", platform)):
                span = href
                break
        if not span:
            span = platform

        seen_urls.add(canon_url)
        profiles.append(ExtractedProfileLink(platform=platform, url=canon_url, claim_span=span))

    return profiles


def extract_careers_and_ats_links(soup: BeautifulSoup, base_url: str) -> list[ExtractedCareerItem]:
    """Find site careers page links and outbound ATS links."""
    items: list[ExtractedCareerItem] = []
    seen: set[str] = set()

    for a in soup.select("a[href]"):
        href = str(a.get("href") or "").strip()
        if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue

        full_url = urllib.parse.urljoin(base_url, href)
        parsed = urllib.parse.urlparse(full_url)
        reg_domain = get_registrable_domain(full_url)
        anchor_text = a.get_text(" ", strip=True)

        if full_url in seen:
            continue

        # Check outbound ATS links
        if reg_domain in KNOWN_ATS_DOMAINS:
            seen.add(full_url)
            items.append(ExtractedCareerItem(
                title=anchor_text or f"Karriereportal ({reg_domain})",
                url=full_url,
                is_job_posting=False,
                is_ats_link=True,
                published_at=None,
                expires_at=None,
                claim_span=href,
            ))
            continue

        # Check careers page on site
        path_lower = parsed.path.lower()
        if any(marker in path_lower for marker in CAREERS_PATH_MARKERS):
            seen.add(full_url)
            items.append(ExtractedCareerItem(
                title=anchor_text or "Karriereside",
                url=full_url,
                is_job_posting=False,
                is_ats_link=False,
                published_at=None,
                expires_at=None,
                claim_span=href,
            ))

    return items


def extract_html_time_news(soup: BeautifulSoup, base_url: str) -> list[ExtractedNewsItem]:
    """Extract dated news items from <time datetime="..."> tags and meta og:article:published_time."""
    items: list[ExtractedNewsItem] = []
    seen_urls: set[str] = set()
    now = datetime.now(timezone.utc)
    max_age_days = 730

    # 1. Meta og:article:published_time
    og_pub = soup.find("meta", property="article:published_time") or soup.find("meta", attrs={"name": "article:published_time"})
    if og_pub and og_pub.get("content"):
        iso = _parse_iso_date(str(og_pub["content"]))
        if iso:
            dt = datetime.fromisoformat(iso)
            if (now - dt).days <= max_age_days:
                title = soup.title.get_text(" ", strip=True) if soup.title else "Nyhet"
                items.append(ExtractedNewsItem(
                    title=title,
                    url=base_url,
                    published_at=iso,
                    claim_span=str(og_pub["content"]),
                    source_type="html_time",
                ))
                seen_urls.add(base_url)

    # 2. <time datetime="..."> inside articles
    for time_tag in soup.find_all("time", attrs={"datetime": True}):
        dt_val = time_tag["datetime"]
        iso = _parse_iso_date(dt_val)
        if not iso:
            continue
        dt = datetime.fromisoformat(iso)
        if (now - dt).days > max_age_days:
            continue

        # Find enclosing heading or link
        parent_article = time_tag.find_parent(["article", "li", "div"])
        heading = None
        link = None
        if parent_article:
            heading = parent_article.find(["h1", "h2", "h3", "h4"])
            link = parent_article.find("a", href=True)

        title = heading.get_text(" ", strip=True) if heading else time_tag.get_text(" ", strip=True)
        url = urllib.parse.urljoin(base_url, link["href"]) if link else base_url

        if title and len(title) >= 5 and url not in seen_urls:
            seen_urls.add(url)
            items.append(ExtractedNewsItem(
                title=title,
                url=url,
                published_at=iso,
                claim_span=dt_val,
                source_type="html_time",
            ))

    return items[:5]


def extract_all_site_signals(
    html: str,
    base_url: str,
    *,
    legal_name: str = "",
) -> SiteExtractionResult:
    """Run full structured extraction pipeline on a verified company website."""
    soup = BeautifulSoup(html or "", "lxml")

    # 1. JSON-LD signals
    news_jsonld, careers_jsonld, profiles_jsonld = extract_jsonld_signals(soup, base_url)

    # 2. HTML social links
    profiles_html = extract_html_social_links(soup, base_url)
    all_profiles = list({p.url: p for p in (profiles_jsonld + profiles_html)}.values())

    # 3. HTML news / time tags
    news_html = extract_html_time_news(soup, base_url)
    all_news = list({n.url: n for n in (news_jsonld + news_html)}.values())
    all_news.sort(key=lambda n: n.published_at, reverse=True)

    # 4. Careers & ATS links
    careers_html = extract_careers_and_ats_links(soup, base_url)
    all_careers = list({c.url: c for c in (careers_jsonld + careers_html)}.values())

    # 5. Public Brand Name
    brand: str | None = None
    og_site = soup.find("meta", property="og:site_name") or soup.find("meta", attrs={"name": "og:site_name"})
    if og_site and og_site.get("content"):
        cand = str(og_site["content"]).strip()
        if 2 <= len(cand) <= 60 and cand.upper() != legal_name.upper():
            brand = cand

    # 6. Contact email & phone
    email: str | None = None
    for a in soup.select('a[href^="mailto:"]'):
        m = a["href"].replace("mailto:", "").split("?")[0].strip().lower()
        if "@" in m and not any(k in m for k in ("example", "domain", "test")):
            email = m
            break

    phone: str | None = None
    for a in soup.select('a[href^="tel:"]'):
        tel = a["href"].replace("tel:", "").strip()
        digits = re.sub(r"\D", "", tel)
        if 8 <= len(digits) <= 12:
            phone = tel
            break

    return SiteExtractionResult(
        news_items=all_news[:5],
        social_profiles=all_profiles[:8],
        careers_items=all_careers[:5],
        brand_name=brand,
        contact_email=email,
        contact_phone=phone,
        address_snippet=None,
    )
