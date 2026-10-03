"""NAV Arbeidsplassen job feed connector (Workflow /04).

Ingests active ads from pam-stilling-feed, indexed and matched by employer.orgnr.
Adheres to official terms:
- Inactive ads are dropped.
- Contact list and personal applicant info (contactList) are strictly never stored or exposed.
- Evidence snapshot stores the verbatim ad payload with employer.orgnr and title.
- Identity proof is 'orgnr_exact'.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("signalpost.connectors.nav_jobs")

NAV_FEED_BASE = "https://pam-stilling-feed.nav.no"
NAV_PUBLIC_TOKEN_URL = f"{NAV_FEED_BASE}/api/publicToken"
NAV_FEED_URL = f"{NAV_FEED_BASE}/api/v1/feed"
NAV_ENTRY_URL_TEMPLATE = f"{NAV_FEED_BASE}/api/v1/feedentry/{{uuid}}"

USER_AGENT = "Signalpost-Research-Agent/1.0 (+https://builderr.no/signalpost)"
CONNECT_TIMEOUT = 5.0
READ_TIMEOUT = 12.0

_TOKEN_CACHE: str | None = None
_FEED_ITEMS_CACHE: list[dict[str, Any]] | None = None
_FEED_CACHE_TIMESTAMP: float = 0.0


@dataclass
class NavJobPosting:
    uuid: str
    title: str
    employer_name: str
    employer_orgnr: str
    employer_homepage: str | None
    location: str | None
    extent: str | None
    engagement_type: str | None
    published: str
    expires: str | None
    application_due: str | None
    source_ad_url: str
    claim_span: str
    snapshot_json: str
    content_sha256: str


def get_nav_token(*, force_refresh: bool = False) -> str | None:
    """Retrieve NAV feed JWT token from env (NAV_FEED_TOKEN) or rotating public endpoint."""
    global _TOKEN_CACHE
    if not force_refresh and _TOKEN_CACHE:
        return _TOKEN_CACHE

    env_token = os.environ.get("NAV_FEED_TOKEN")
    if env_token:
        _TOKEN_CACHE = env_token.strip()
        return _TOKEN_CACHE

    try:
        req = urllib.request.Request(NAV_PUBLIC_TOKEN_URL, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=CONNECT_TIMEOUT) as resp:
            content = resp.read().decode("utf-8", errors="replace").strip()
            # The response format is typically:
            # "Current public token for Nav Job Vacancy Feed:\n<jwt_token>"
            lines = [l.strip() for l in content.splitlines() if l.strip()]
            token = lines[-1]
            if token and len(token) > 20:
                _TOKEN_CACHE = token
                return token
    except Exception as exc:
        logger.warning("Could not retrieve public NAV feed token: %s", exc)

    return None


def fetch_ad_detail(
    uuid: str,
    token: str,
    *,
    opener: Any = None,
) -> dict[str, Any] | None:
    """Fetch live ad detail for a specific ad UUID. Drops contactList per terms."""
    url = NAV_ENTRY_URL_TEMPLATE.format(uuid=uuid)
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        open_fn = opener.open if opener else urllib.request.urlopen
        with open_fn(req, timeout=READ_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            status = data.get("status")
            if status != "ACTIVE":
                return None
            ad_content = data.get("ad_content") or data.get("json")
            if not ad_content:
                return None

            # Strictly strip personal contactList per terms
            ad_content.pop("contactList", None)
            return ad_content
    except Exception as exc:
        logger.debug("Error fetching NAV ad %s: %s", uuid, exc)
        return None


def _normalize_name_tokens(name: str) -> set[str]:
    """Extract significant lowercase tokens from company name."""
    cleaned = re.sub(r"\b(AS|ASA|ENK|ANS|DA|BA|BRL|KF|FKF|NUF)\b", "", name, flags=re.IGNORECASE)
    cleaned = re.sub(r"[^\w\s]", " ", cleaned).lower()
    tokens = {t for t in cleaned.split() if len(t) >= 3 and not t.isdigit()}
    return tokens


def ingest_recent_nav_feed(
    token: str,
    *,
    max_pages: int = 5,
    days_back: int = 30,
    opener: Any = None,
) -> list[dict[str, Any]]:
    """Ingest active ads from the feed within days_back window, cached in-memory."""
    global _FEED_ITEMS_CACHE, _FEED_CACHE_TIMESTAMP

    # Cache for up to 30 minutes in memory
    now_ts = datetime.now(timezone.utc).timestamp()
    if _FEED_ITEMS_CACHE is not None and (now_ts - _FEED_CACHE_TIMESTAMP) < 1800:
        return _FEED_ITEMS_CACHE

    d_start = datetime.now(timezone.utc) - timedelta(days=days_back)
    http_date = format_datetime(d_start, usegmt=True)

    active_items: list[dict[str, Any]] = []
    next_path: str | None = None
    open_fn = opener.open if opener else urllib.request.urlopen

    for page_num in range(max_pages):
        url = f"{NAV_FEED_BASE}{next_path}" if next_path else NAV_FEED_URL
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            },
        )
        if not next_path:
            req.add_header("If-Modified-Since", http_date)

        try:
            with open_fn(req, timeout=READ_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for item in data.get("items", []):
                    entry = item.get("_feed_entry", {})
                    if entry.get("status") == "ACTIVE":
                        active_items.append({
                            "uuid": entry.get("uuid") or item.get("id"),
                            "title": entry.get("title") or item.get("title"),
                            "businessName": entry.get("businessName") or "",
                            "url": item.get("url"),
                        })
                next_path = data.get("next_url")
                if not next_path:
                    break
        except Exception as exc:
            logger.warning("Error fetching NAV feed page %d: %s", page_num + 1, exc)
            break

    _FEED_ITEMS_CACHE = active_items
    _FEED_CACHE_TIMESTAMP = now_ts
    return active_items


def find_company_nav_job_postings(
    orgnr: str,
    legal_name: str,
    *,
    brand: str | None = None,
    feed_items: list[dict[str, Any]] | None = None,
    token: str | None = None,
    detail_fetcher: Callable[[str, str], dict[str, Any] | None] | None = None,
) -> list[NavJobPosting]:
    """Find and verify active job postings for a company using nav_name_match."""
    token = token or get_nav_token()
    if not token:
        return []

    if feed_items is None:
        feed_items = ingest_recent_nav_feed(token)

    if not feed_items:
        return []

    target_tokens = _normalize_name_tokens(legal_name)
    if brand:
        target_tokens |= _normalize_name_tokens(brand)

    norm_target_clean = re.sub(r"[^\w]", "", legal_name.lower())

    candidate_entries: list[dict[str, Any]] = []
    seen_uuids: set[str] = set()

    for item in feed_items:
        uuid = item.get("uuid")
        if not uuid or uuid in seen_uuids:
            continue

        b_name = item.get("businessName", "").strip()
        if not b_name:
            continue

        b_clean = re.sub(r"[^\w]", "", b_name.lower())
        b_tokens = _normalize_name_tokens(b_name)

        is_candidate = False
        if b_clean and (b_clean == norm_target_clean or (len(b_clean) >= 6 and (b_clean in norm_target_clean or norm_target_clean in b_clean))):
            is_candidate = True
        elif target_tokens and (b_tokens & target_tokens):
            # If tokens overlap significantly
            overlap = len(b_tokens & target_tokens)
            if overlap >= min(len(target_tokens), len(b_tokens)):
                is_candidate = True

        if is_candidate:
            seen_uuids.add(uuid)
            candidate_entries.append(item)

    fetch_fn = detail_fetcher or (lambda u, tok: fetch_ad_detail(u, tok))
    verified_postings: list[NavJobPosting] = []

    for cand in candidate_entries:
        uuid = cand["uuid"]
        ad_content = fetch_fn(uuid, token)
        if not ad_content:
            continue

        employer = ad_content.get("employer") or {}
        emp_orgnr = str(employer.get("orgnr") or "").strip().replace(" ", "")

        # Strict exact-entity proof: employer.orgnr == target orgnr
        if emp_orgnr != orgnr:
            continue

        title = str(ad_content.get("title") or cand.get("title") or "Stilling")
        published = str(ad_content.get("published") or datetime.now(timezone.utc).isoformat())
        expires = ad_content.get("expires")
        app_due = ad_content.get("applicationDue")
        extent = ad_content.get("extent")
        engagement = ad_content.get("engagementtype")
        homepage = employer.get("homepage")

        loc_str = None
        work_locs = ad_content.get("workLocations") or []
        if work_locs and isinstance(work_locs, list) and isinstance(work_locs[0], dict):
            w = work_locs[0]
            loc_str = w.get("city") or w.get("municipal") or w.get("county")

        link = str(ad_content.get("link") or f"https://arbeidsplassen.nav.no/stillinger/stilling/{uuid}")

        # Construct clean sanitized snapshot text
        clean_snapshot_dict = {
            "uuid": uuid,
            "title": title,
            "employer": {
                "name": employer.get("name"),
                "orgnr": emp_orgnr,
                "homepage": homepage,
            },
            "published": published,
            "expires": expires,
            "extent": extent,
            "engagementtype": engagement,
            "workLocations": work_locs,
            "link": link,
        }
        snap_json = json.dumps(clean_snapshot_dict, ensure_ascii=False, indent=2)
        sha = hashlib.sha256(snap_json.encode("utf-8")).hexdigest()

        # Verbatim claim span containing orgnr and title
        claim_span = f'{{"uuid": "{uuid}", "title": "{title}", "orgnr": "{emp_orgnr}"}}'
        if claim_span not in snap_json:
            claim_span = f'"orgnr": "{emp_orgnr}"'

        verified_postings.append(
            NavJobPosting(
                uuid=uuid,
                title=title,
                employer_name=str(employer.get("name") or legal_name),
                employer_orgnr=emp_orgnr,
                employer_homepage=homepage,
                location=loc_str,
                extent=extent,
                engagement_type=engagement,
                published=published,
                expires=expires,
                application_due=app_due,
                source_ad_url=link,
                claim_span=claim_span,
                snapshot_json=snap_json,
                content_sha256=sha,
            )
        )

    return verified_postings
