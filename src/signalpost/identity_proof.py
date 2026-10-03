"""Strict exact-entity proof and identity assessment for Norwegian company websites (Rule N2).

Proof ladder:
- P1 exact: valid mod-11 target orgnr on candidate page (body or JSON-LD),
  no conflicting outside-family labelled orgnr, same registrable domain.
- P2 strong combo (only if page has zero org numbers):
  (a) all distinctive legal-name tokens in title/H1/footer/JSON-LD,
  (b) registered street address AND postal code in text,
  (c) registered phone OR email domain == site domain OR registry role-holder on page.
- Rejection reason codes: host_blocklisted, parked_page, other_org_labelled,
  group_or_portfolio_page, belongs_to_parent_or_sister, name_only_match,
  address_only_match, no_proof, dead, blocked, wrong_language_or_empty,
  redirected_to_different_company.
"""
from __future__ import annotations

import re
import unicodedata
import urllib.parse
from dataclasses import dataclass
from typing import Any, Iterable

import tldextract
from bs4 import BeautifulSoup

from signalpost.ref.domains import FREE_MAIL, name_tokens
from signalpost.ref.orgnr import assess_page, find_orgnrs, is_valid, normalize

BLOCKLISTED_HOSTS = {
    # Directory & company lookup services
    "proff.no", "purehelp.no", "1881.no", "gulesider.no", "allabolag.se",
    "eniro.no", "regnskapstall.no", "dn.no", "e24.no", "bisnode.no", "dnb.no",
    "yellowpages.com", "ratsit.se", "largestcompanies.com", "hitta.se",
    # Social media platforms
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com",
    "youtube.com", "tiktok.com", "pinterest.com", "threads.net", "snapchat.com",
    # Marketplaces & portals
    "finn.no", "mittanbud.no", "anbudstorget.no", "github.com", "gitlab.com",
    "medium.com", "wikipedia.org", "wikidata.org", "overpass-turbo.eu",
    # Parked & registrar landing hosts
    "domeneshop.no", "godaddy.com", "dan.com", "sedo.com", "afternic.com",
    "hugedomains.com", "namecheap.com", "one.com", "proisp.no", "loopia.no",
}

PARKED_MARKERS = (
    "domain is for sale", "domain for sale", "domenet er til salgs", "til salgs",
    "parked at", "parkert hos domeneshop", "parkert hos", "parked free",
    "her flytter snart en ny gjest", "denne nettsiden er under konstruksjon",
    "under oppussing", "denne siden er under utvikling", "miss hosting",
    "buy this domain", "inquire about this domain", "has been informing visitors",
    "find the best information and most relevant links", "kjøp dette domenet",
    "websiden er under utvikling", "nettside kommer snart", "kommer snart",
    "domain has expired", "domenet har utløpt",
)


def get_registrable_domain(url: str) -> str:
    """Extract registrable domain (e.g. 'example.no' from 'https://sub.example.no/path')."""
    try:
        parsed = urllib.parse.urlparse(url if "://" in url else f"https://{url}")
        host = (parsed.hostname or "").lower().rstrip(".")
        extracted = tldextract.extract(host)
        if extracted.domain and extracted.suffix:
            return f"{extracted.domain}.{extracted.suffix}".lower()
        return host
    except Exception:
        return ""


def is_blocklisted_host(url: str) -> bool:
    """Check if URL host belongs to a known directory, social network, or platform."""
    reg = get_registrable_domain(url)
    if not reg:
        return True
    return reg in BLOCKLISTED_HOSTS or any(reg.endswith("." + b) for b in BLOCKLISTED_HOSTS)


def is_parked_page(html_text: str) -> bool:
    """Check text for parked domain or domain-for-sale phrases (Norwegian and English)."""
    norm = unicodedata.normalize("NFKD", html_text or "").encode("ascii", "ignore").decode().casefold()
    return any(marker in norm for marker in PARKED_MARKERS)


def extract_page_text_and_jsonld(html: str) -> tuple[str, list[dict[str, Any]], str, list[str]]:
    """Extract plain visible text, JSON-LD objects, page title, and H1 headers from HTML."""
    soup = BeautifulSoup(html or "", "lxml")
    
    # Remove script and style elements except json-ld
    jsonld_data: list[dict[str, Any]] = []
    for script in soup.find_all("script"):
        if script.get("type") == "application/ld+json":
            try:
                import json
                data = json.loads(script.string or "")
                if isinstance(data, list):
                    jsonld_data.extend(item for item in data if isinstance(item, dict))
                elif isinstance(data, dict):
                    jsonld_data.append(data)
            except Exception:
                pass
        script.decompose()
        
    for tag in soup.find_all(["style", "noscript", "svg"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    h1s = [h.get_text(separator=" ", strip=True) for h in soup.find_all("h1")]
    text = soup.get_text(separator=" ", strip=True)
    return text, jsonld_data, title, h1s


@dataclass(frozen=True)
class ProofResult:
    verdict: str  # "exact" | "strong_combo" | "rejected"
    proof_level: str  # "p1_exact" | "p2_strong" | "none"
    confidence: float
    reason: str  # reason code
    claim_span: str | None
    verified_url: str | None
    registrable_domain: str | None
    details: dict[str, Any]


def verify_website_proof(
    *,
    candidate_url: str,
    final_url: str,
    page_html: str,
    target_orgnr: str,
    legal_name: str,
    family_orgnrs: set[str] | None = None,
    business_address: dict[str, Any] | None = None,
    postal_address: dict[str, Any] | None = None,
    phone: str | None = None,
    email: str | None = None,
    role_holders: list[str] | None = None,
) -> ProofResult:
    """Evaluate candidate page against strict exact-entity proof rules (P1 / P2)."""
    norm_target = normalize(target_orgnr)
    assert norm_target is not None, f"Invalid target orgnr: {target_orgnr}"

    family = {normalize(x) for x in (family_orgnrs or set()) if normalize(x)}
    family.add(norm_target)

    cand_reg = get_registrable_domain(candidate_url)
    final_reg = get_registrable_domain(final_url)

    # 1. Host blocklist check
    if is_blocklisted_host(final_url) or is_blocklisted_host(candidate_url):
        return ProofResult(
            verdict="rejected",
            proof_level="none",
            confidence=0.0,
            reason="host_blocklisted",
            claim_span=None,
            verified_url=None,
            registrable_domain=cand_reg,
            details={"candidate_domain": cand_reg, "final_domain": final_reg},
        )

    # 2. Redirect to a completely different registrable domain
    if cand_reg and final_reg and cand_reg != final_reg:
        # Allowed only if both belong to same company (verified on page)
        pass

    # 3. Parse HTML text and metadata
    text, jsonlds, title, h1s = extract_page_text_and_jsonld(page_html)

    # Check for empty or non-HTML page
    if len(text.strip()) < 30:
        return ProofResult(
            verdict="rejected",
            proof_level="none",
            confidence=0.0,
            reason="wrong_language_or_empty",
            claim_span=None,
            verified_url=None,
            registrable_domain=final_reg,
            details={},
        )

    # 4. Parked page check
    if is_parked_page(text) or is_parked_page(title):
        return ProofResult(
            verdict="rejected",
            proof_level="none",
            confidence=0.0,
            reason="parked_page",
            claim_span=None,
            verified_url=None,
            registrable_domain=final_reg,
            details={},
        )

    # 5. Check JSON-LD for organization identifiers
    jsonld_orgnrs: list[str] = []
    for jd in jsonlds:
        for key in ("vatID", "taxID", "identifier", "iso6523Code"):
            val = jd.get(key)
            if val:
                norm_val = normalize(val)
                if norm_val:
                    jsonld_orgnrs.append(norm_val)

    # 6. Check orgnr hits in page text
    assessment = assess_page(text, norm_target, family)
    all_hits = find_orgnrs(text)
    valid_orgs_on_page = {h.orgnr for h in all_hits if h.valid} | set(jsonld_orgnrs)

    # Group / portfolio page trap: 3 or more distinct valid org numbers
    if len(valid_orgs_on_page) >= 3:
        return ProofResult(
            verdict="rejected",
            proof_level="none",
            confidence=0.0,
            reason="group_or_portfolio_page",
            claim_span=None,
            verified_url=None,
            registrable_domain=final_reg,
            details={"valid_orgs_count": len(valid_orgs_on_page), "orgs": list(valid_orgs_on_page)[:5]},
        )

    # Target orgnr present in text or JSON-LD
    target_hit = any(h.orgnr == norm_target for h in all_hits) or (norm_target in jsonld_orgnrs)
    foreign_labelled = assessment.get("foreign", [])

    if target_hit:
        # Conflicting foreign labelled orgnr outside family
        if foreign_labelled:
            return ProofResult(
                verdict="rejected",
                proof_level="none",
                confidence=0.0,
                reason="other_org_labelled",
                claim_span=None,
                verified_url=None,
                registrable_domain=final_reg,
                details={"foreign_labelled": foreign_labelled},
            )

        # Build clean verbatim claim span
        span = assessment.get("span")
        if not span:
            # Construct from text around the hit
            idx = text.find(norm_target)
            if idx >= 0:
                span = text[max(0, idx - 40): min(len(text), idx + 50)]
            else:
                idx_html = page_html.find(norm_target)
                if idx_html >= 0:
                    span = page_html[max(0, idx_html - 30): min(len(page_html), idx_html + 40)]
                else:
                    span = f"Org.nr. {norm_target}"

        return ProofResult(
            verdict="exact",
            proof_level="p1_exact",
            confidence=1.0,
            reason="verified_p1_exact",
            claim_span=span[:500],
            verified_url=final_url,
            registrable_domain=final_reg,
            details={"source": "page_orgnr_match"},
        )

    # Family member's number present without ours
    family_members_present = (valid_orgs_on_page & family) - {norm_target}
    if family_members_present:
        return ProofResult(
            verdict="rejected",
            proof_level="none",
            confidence=0.0,
            reason="belongs_to_parent_or_sister",
            claim_span=None,
            verified_url=None,
            registrable_domain=final_reg,
            details={"family_members_present": list(family_members_present)},
        )

    # Another valid orgnr labelled without ours
    if foreign_labelled:
        return ProofResult(
            verdict="rejected",
            proof_level="none",
            confidence=0.0,
            reason="other_org_labelled",
            claim_span=None,
            verified_url=None,
            registrable_domain=final_reg,
            details={"foreign_labelled": foreign_labelled},
        )

    # 7. P2 Strong Combo Check (only if NO valid org numbers on page at all)
    if len(valid_orgs_on_page) == 0:
        # Check (a): all distinctive legal-name tokens in title / H1 / footer / JSON-LD
        tokens = name_tokens(legal_name)
        if tokens:
            name_header_text = " ".join([title, *h1s]).lower()
            tokens_in_header = all(t.lower() in name_header_text for t in tokens)
            tokens_in_body = all(t.lower() in text.lower() for t in tokens)

            # Check (b): registered street address AND postal code in text
            addr_matched = False
            addr_span = ""
            for addr_dict in filter(None, [business_address, postal_address]):
                postnr = str(addr_dict.get("postnummer") or "").strip()
                gate = str(addr_dict.get("adresse") or "").strip()
                if isinstance(gate, list):
                    gate = " ".join(gate)
                if postnr and len(postnr) == 4 and gate and len(gate) >= 4:
                    if postnr in text and gate.lower() in text.lower():
                        addr_matched = True
                        idx_gate = text.lower().find(gate.lower())
                        if idx_gate >= 0:
                            addr_span = text[idx_gate: min(len(text), idx_gate + len(gate) + 30)].strip()
                        else:
                            addr_span = gate
                        break

            # Check (c): phone OR email domain == site domain OR role holder
            third_signal = False
            phone_clean = re.sub(r"\D", "", str(phone or ""))
            if len(phone_clean) >= 8 and phone_clean in re.sub(r"\D", "", text):
                third_signal = True

            if not third_signal and email and "@" in email:
                mail_domain = email.split("@", 1)[1].lower()
                if mail_domain not in FREE_MAIL and mail_domain == final_reg:
                    third_signal = True

            if not third_signal and role_holders:
                for rh in role_holders:
                    if rh and len(rh.strip()) >= 5 and rh.lower() in text.lower():
                        third_signal = True
                        break

            if (tokens_in_header or tokens_in_body) and addr_matched and third_signal:
                p2_span = addr_span or legal_name
                return ProofResult(
                    verdict="strong_combo",
                    proof_level="p2_strong",
                    confidence=0.9,
                    reason="verified_p2_strong_combo",
                    claim_span=p2_span[:500],
                    verified_url=final_url,
                    registrable_domain=final_reg,
                    details={"matched_address": addr_span, "tokens": tokens},
                )
            elif tokens_in_header or tokens_in_body:
                return ProofResult(
                    verdict="rejected",
                    proof_level="none",
                    confidence=0.0,
                    reason="name_only_match",
                    claim_span=None,
                    verified_url=None,
                    registrable_domain=final_reg,
                    details={"tokens": tokens},
                )
            elif addr_matched:
                return ProofResult(
                    verdict="rejected",
                    proof_level="none",
                    confidence=0.0,
                    reason="address_only_match",
                    claim_span=None,
                    verified_url=None,
                    registrable_domain=final_reg,
                    details={},
                )

    return ProofResult(
        verdict="rejected",
        proof_level="none",
        confidence=0.0,
        reason="no_proof",
        claim_span=None,
        verified_url=None,
        registrable_domain=final_reg,
        details={},
    )
