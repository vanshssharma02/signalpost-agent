"""Website discovery ladder and candidate generation (Workflow /03).

Rungs:
1. S-A registry_homepage: hjemmeside from registry record (normalized, social/directory rejected).
2. S-B registry_email_domain: domain of registry epostadresse (via email_domain_candidate).
3. S-C subunit_homepage: hjemmeside and email domain of underenheter subunits.
4. S-D nav_employer_homepage: employer.homepage from NAV job ads.
5. S-E domain_guess: candidate_hosts(legal_name) (.no, .com, max 12).
6. S-F search_orgnr: transient candidate queries if SEARCH_API_KEY is present.

Every candidate is independently fetched and must pass exact-entity proof (identity_proof.py).
"""
from __future__ import annotations

import json
import logging
import os
import re
import socket
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from bs4 import BeautifulSoup
import tldextract

from norway_company_agent.http import FetchResult
from norway_company_agent.website import (
    PRIORITY_TERMS,
    SAFE_OPENER,
    USER_AGENT,
    _priority_links,
    _robots_allowed,
    assert_public_url,
    normalize_homepage,
)
from signalpost.identity_proof import (
    ProofResult,
    get_registrable_domain,
    is_blocklisted_host,
    verify_website_proof,
)
from signalpost.ref.domains import candidate_hosts, email_domain_candidate
from signalpost.ref.orgnr import normalize

logger = logging.getLogger("signalpost.discovery")

MAX_PAGE_BYTES = 1_500_000
CONNECT_TIMEOUT = 5.0
READ_TIMEOUT = 10.0


@dataclass
class DiscoveredWebsite:
    homepage_url: str
    verified_url: str
    registrable_domain: str
    strategy: str
    proof_level: str  # "p1_exact" | "p2_strong"
    claim_span: str
    page_html: str
    page_text: str
    content_sha256: str
    retrieved_at: str
    brand_name: str | None = None
    social_links: list[dict[str, str]] | None = None


def generate_candidates(
    profile: dict[str, Any],
    *,
    subunits: list[dict[str, Any]] | None = None,
    nav_homepage: str | None = None,
    max_domain_guesses: int = 12,
) -> list[tuple[str, str]]:
    """Generate ordered (strategy, candidate_url) tuples for a company."""
    candidates: list[tuple[str, str]] = []
    seen_domains: set[str] = set()

    def add_cand(strat: str, url: str | None) -> None:
        if not url:
            return
        clean = normalize_homepage(url)
        if not clean:
            return
        reg = get_registrable_domain(clean)
        if not reg or is_blocklisted_host(clean) or reg in seen_domains:
            return
        seen_domains.add(reg)
        candidates.append((strat, clean))

    # Rung 1: Registry homepage
    reg_site = profile.get("website") or (profile.get("evidence", {}).get("registry", {}).get("value") or {}).get("hjemmeside")
    add_cand("registry_homepage", reg_site)

    # Rung 2: Registry email domain
    raw_val = (profile.get("evidence", {}).get("registry", {}).get("value") or {})
    reg_email = profile.get("email") or raw_val.get("epostadresse")
    email_domain = email_domain_candidate(reg_email)
    if email_domain:
        add_cand("registry_email_domain", f"https://{email_domain}")

    # Rung 3: Subunit websites & emails
    subs = subunits or (profile.get("evidence", {}).get("locations", {}).get("value") or {}).get("locations", [])
    for sub in subs:
        if isinstance(sub, dict):
            sub_web = sub.get("hjemmeside") or sub.get("website")
            add_cand("subunit_homepage", sub_web)
            sub_mail = sub.get("epostadresse") or sub.get("email")
            sub_mail_domain = email_domain_candidate(sub_mail)
            if sub_mail_domain:
                add_cand("subunit_homepage", f"https://{sub_mail_domain}")

    # Rung 4: NAV job ad employer homepage
    add_cand("nav_employer_homepage", nav_homepage)

    # Rung 5: Domain name guessing
    legal_name = profile.get("name") or raw_val.get("navn") or ""
    if legal_name:
        for host in candidate_hosts(legal_name, limit=max_domain_guesses):
            add_cand("domain_guess", f"https://{host}")

    # Rung 6: Search API (transient candidates, only if SEARCH_API_KEY is present)
    orgnr = str(profile.get("organisation_number") or "")
    if os.environ.get("SEARCH_API_KEY") and orgnr:
        b_addr = profile.get("business_address") or raw_val.get("forretningsadresse") or {}
        postnr = str(b_addr.get("postnummer") or "")
        poststed = str(b_addr.get("poststed") or "")
        for u in fetch_search_candidates(orgnr, legal_name, postnr, poststed):
            add_cand("search_orgnr", u)

    return candidates


def fetch_search_candidates(orgnr: str, legal_name: str, postal_code: str = "", town: str = "") -> list[str]:
    """Transient candidate generation using SEARCH_API_KEY (Rule N4/N5).
    Never stores titles, snippets, query text or raw responses.
    """
    api_key = os.environ.get("SEARCH_API_KEY")
    if not api_key:
        return []
    queries = [
        f'"{orgnr[:3]} {orgnr[3:6]} {orgnr[6:]}"',
        f'"{orgnr}"',
    ]
    if legal_name:
        queries.append(f'"{legal_name}" {postal_code} {town}'.strip())

    found_urls: list[str] = []
    seen_domains: set[str] = set()

    headers = {"Accept": "application/json", "X-Subscription-Token": api_key}
    for q in queries[:2]:
        try:
            params = urllib.parse.urlencode({"q": q, "count": 5})
            req = urllib.request.Request(f"https://api.search.brave.com/res/v1/web/search?{params}", headers=headers)
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for res in data.get("web", {}).get("results", []):
                    u = res.get("url")
                    if u:
                        reg = get_registrable_domain(u)
                        if reg and not is_blocklisted_host(u) and reg not in seen_domains:
                            seen_domains.add(reg)
                            found_urls.append(u)
        except Exception:
            continue
    return found_urls[:5]


_ROBOTS_CACHE: dict[str, Any] = {}


def is_robots_allowed(url: str, timeout: float = CONNECT_TIMEOUT) -> bool:
    """Respect robots.txt and cache per host."""
    try:
        parsed = urllib.parse.urlparse(url)
        host = (parsed.hostname or "").lower()
        if not host:
            return True
        if host in _ROBOTS_CACHE:
            parser = _ROBOTS_CACHE[host]
            return parser.can_fetch(USER_AGENT, url) if parser else True

        robots_url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "/robots.txt", "", "", ""))
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(robots_url)
        req = urllib.request.Request(robots_url, headers={"User-Agent": USER_AGENT})
        with SAFE_OPENER.open(req, timeout=timeout) as resp:
            parser.parse(resp.read().decode("utf-8", errors="replace").splitlines())
        _ROBOTS_CACHE[host] = parser
        return parser.can_fetch(USER_AGENT, url)
    except Exception:
        _ROBOTS_CACHE[host] = None
        return True


def _dns_precheck(host: str, timeout: float = 3.0) -> bool:
    """Fast DNS resolution check (3s timeout) to drop non-existent domains quickly."""
    try:
        socket.setdefaulttimeout(timeout)
        socket.gethostbyname(host)
        return True
    except Exception:
        return False
    finally:
        socket.setdefaulttimeout(None)


def fetch_candidate_html(url: str, *, timeout: float = 10.0, max_bytes: int = MAX_PAGE_BYTES) -> tuple[str | None, str | None, int, str | None]:
    """Fetch URL safely following redirects through assert_public_url.
    Returns (html_str, final_url, status_code, error_msg).
    """
    try:
        assert_public_url(url)
    except Exception as exc:
        return None, None, 0, f"blocked_url: {exc}"

    if not is_robots_allowed(url, timeout=CONNECT_TIMEOUT):
        return None, None, 403, "robots_disallowed"

    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or ""
    if not _dns_precheck(host):
        return None, None, 0, "dns_resolution_failed"

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )

    try:
        with SAFE_OPENER.open(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "").lower()
            if "html" not in content_type and "text" not in content_type and "xml" not in content_type and "json" not in content_type:
                return None, resp.geturl(), resp.status, "unsupported_content_type"

            raw = resp.read(max_bytes + 1)
            if len(raw) > max_bytes:
                return None, resp.geturl(), resp.status, "payload_too_large"

            final_url = resp.geturl()
            html = raw.decode("utf-8", errors="replace")
            return html, final_url, resp.status, None
    except Exception as exc:
        return None, None, 0, f"fetch_error: {type(exc).__name__}: {str(exc)[:100]}"


def extract_brand_name(soup: BeautifulSoup, legal_name: str) -> str | None:
    """Extract public brand name from verified page (og:site_name, JSON-LD, title)."""
    # 1. og:site_name
    og_site = soup.find("meta", property="og:site_name") or soup.find("meta", attrs={"name": "og:site_name"})
    if og_site and og_site.get("content"):
        cand = str(og_site["content"]).strip()
        if 2 <= len(cand) <= 60:
            return cand

    # 2. JSON-LD Organization name
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            items = data if isinstance(data, list) else [data]
            for it in items:
                if isinstance(it, dict) and it.get("name") and it.get("@type") in ("Organization", "Corporation", "LocalBusiness"):
                    cand = str(it["name"]).strip()
                    if 2 <= len(cand) <= 60:
                        return cand
        except Exception:
            pass

    # 3. Title before separator
    if soup.title and soup.title.string:
        t = soup.title.string.strip()
        for sep in (" - ", " | ", " – ", " — ", " : "):
            if sep in t:
                part = t.split(sep, 1)[0].strip()
                if 2 <= len(part) <= 60 and not any(k in part.lower() for k in ("hjem", "forside", "home", "velkommen")):
                    return part

    return legal_name


def discover_company_website(
    profile: dict[str, Any],
    *,
    subunits: list[dict[str, Any]] | None = None,
    nav_homepage: str | None = None,
    family_orgnrs: set[str] | None = None,
    trace_log_path: Path | str | None = "out/discovery_trace.jsonl",
    metrics_out: list[FetchResult] | None = None,
) -> DiscoveredWebsite | None:
    """Run discovery ladder for a single company until verified or exhausted."""
    orgnr = str(profile.get("organisation_number") or "")
    legal_name = str(profile.get("name") or "")
    raw_val = (profile.get("evidence", {}).get("registry", {}).get("value") or {})

    # Extract supporting identity signals for P2
    business_addr = profile.get("business_address") or raw_val.get("forretningsadresse")
    postal_addr = profile.get("postal_address") or raw_val.get("postadresse")
    phone = profile.get("phone") or raw_val.get("telefon")
    email = profile.get("email") or raw_val.get("epostadresse")

    roles_val = (profile.get("evidence", {}).get("roles", {}).get("value") or {}).get("roles", [])
    role_holders = [str(r.get("name") or "") for r in roles_val if r.get("name")]

    candidates = generate_candidates(profile, subunits=subunits, nav_homepage=nav_homepage)
    if not candidates:
        return None

    trace_records: list[dict[str, Any]] = []

    for strategy, cand_url in candidates:
        t0 = time.monotonic()
        html, final_url, status_code, err = fetch_candidate_html(cand_url)
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        if metrics_out is not None:
            metrics_out.append(FetchResult(
                url=cand_url,
                status=status_code or 200,
                elapsed_ms=elapsed_ms,
                bytes_received=len(html.encode("utf-8")) if html else 0,
            ))

        if not html or not final_url:
            trace_records.append({
                "orgnr": orgnr,
                "strategy": strategy,
                "candidate_url": cand_url,
                "verdict": "rejected",
                "reason": err or "empty_response",
                "elapsed_ms": elapsed_ms,
            })
            continue

        proof = verify_website_proof(
            candidate_url=cand_url,
            final_url=final_url,
            page_html=html,
            target_orgnr=orgnr,
            legal_name=legal_name,
            family_orgnrs=family_orgnrs,
            business_address=business_addr,
            postal_address=postal_addr,
            phone=phone,
            email=email,
            role_holders=role_holders,
        )

        trace_records.append({
            "orgnr": orgnr,
            "strategy": strategy,
            "candidate_url": cand_url,
            "final_url": final_url,
            "verdict": proof.verdict,
            "proof_level": proof.proof_level,
            "reason": proof.reason,
            "elapsed_ms": elapsed_ms,
        })

        # If verified exact or strong combo on homepage
        if proof.verdict in ("exact", "strong_combo") and proof.claim_span:
            soup = BeautifulSoup(html, "lxml")
            brand = extract_brand_name(soup, legal_name)
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            sha = __import__("hashlib").sha256(html.encode("utf-8")).hexdigest()

            _write_trace(trace_log_path, trace_records)
            return DiscoveredWebsite(
                homepage_url=cand_url,
                verified_url=final_url,
                registrable_domain=proof.registrable_domain or get_registrable_domain(final_url),
                strategy=strategy,
                proof_level=proof.proof_level,
                claim_span=proof.claim_span,
                page_html=html,
                page_text=soup.get_text(separator=" ", strip=True),
                content_sha256=sha,
                retrieved_at=now,
                brand_name=brand,
            )

        # If homepage didn't have orgnr, check subpages (/kontakt, /om-oss, etc.)
        soup = BeautifulSoup(html, "lxml")
        sub_links = _priority_links(final_url, soup, limit=3)
        for sub_url in sub_links:
            t_sub = time.monotonic()
            sub_html, sub_final, sub_status, sub_err = fetch_candidate_html(sub_url)
            sub_ms = int((time.monotonic() - t_sub) * 1000)
            if metrics_out is not None:
                metrics_out.append(FetchResult(
                    url=sub_url,
                    status=sub_status or 200,
                    elapsed_ms=sub_ms,
                    bytes_received=len(sub_html.encode("utf-8")) if sub_html else 0,
                ))
            if not sub_html or not sub_final:
                continue

            sub_proof = verify_website_proof(
                candidate_url=cand_url,
                final_url=sub_final,
                page_html=sub_html,
                target_orgnr=orgnr,
                legal_name=legal_name,
                family_orgnrs=family_orgnrs,
                business_address=business_addr,
                postal_address=postal_addr,
                phone=phone,
                email=email,
                role_holders=role_holders,
            )

            trace_records.append({
                "orgnr": orgnr,
                "strategy": f"{strategy}_subpage",
                "candidate_url": sub_url,
                "final_url": sub_final,
                "verdict": sub_proof.verdict,
                "proof_level": sub_proof.proof_level,
                "reason": sub_proof.reason,
                "elapsed_ms": sub_ms,
            })

            if sub_proof.verdict in ("exact", "strong_combo") and sub_proof.claim_span:
                brand = extract_brand_name(soup, legal_name)
                now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                sub_sha = __import__("hashlib").sha256(sub_html.encode("utf-8")).hexdigest()

                _write_trace(trace_log_path, trace_records)
                return DiscoveredWebsite(
                    homepage_url=cand_url,
                    verified_url=sub_final,
                    registrable_domain=sub_proof.registrable_domain or get_registrable_domain(final_url),
                    strategy=strategy,
                    proof_level=sub_proof.proof_level,
                    claim_span=sub_proof.claim_span,
                    page_html=sub_html,
                    page_text=BeautifulSoup(sub_html, "lxml").get_text(separator=" ", strip=True),
                    content_sha256=sub_sha,
                    retrieved_at=now,
                    brand_name=brand,
                )

    _write_trace(trace_log_path, trace_records)
    return None


def _write_trace(path: Path | str | None, records: list[dict[str, Any]]) -> None:
    if not path or not records:
        return
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass
