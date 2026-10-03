"""Candidate-domain generation from a legal name. Candidates are NEVER evidence:
every candidate must still pass the organisation-number proof before publication."""
from __future__ import annotations

import re
import unicodedata

LEGAL_TOKENS = {
    "as", "asa", "ans", "da", "enk", "iks", "sa", "sam", "sti", "stiftelsen", "nuf", "ks", "brl",
    "bbl", "esek", "fli", "norge", "norway", "holding", "invest",
}
FREE_MAIL = {
    "gmail.com", "googlemail.com", "hotmail.com", "hotmail.no", "outlook.com", "outlook.no", "live.com",
    "live.no", "yahoo.com", "yahoo.no", "icloud.com", "me.com", "online.no", "broadpark.no", "getmail.no",
    "msn.com", "proton.me", "protonmail.com", "start.no", "c2i.net", "frisurf.no", "tele2.no", "lyse.net",
}


def _ascii(value: str, *, oe: bool = False) -> str:
    table = {"ø": "oe" if oe else "o", "å": "aa" if oe else "a", "æ": "ae", "é": "e", "ü": "u", "ö": "o", "ä": "a"}
    text = "".join(table.get(ch, ch) for ch in value.casefold())
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def name_tokens(name: str, *, oe: bool = False) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", _ascii(name, oe=oe))
    return [t for t in tokens if t not in LEGAL_TOKENS and len(t) > 0]


def candidate_hosts(name: str, *, tlds: tuple[str, ...] = ("no", "com"), limit: int = 12) -> list[str]:
    """Ordered, de-duplicated candidate registrable domains (no scheme, no www)."""
    slugs: list[str] = []
    for oe in (False, True):
        t = name_tokens(name, oe=oe)
        if not t:
            continue
        slugs.append("".join(t))
        slugs.append("-".join(t))
        if len(t) >= 2:
            slugs.append("".join(t[:2]))
        if len(t) == 1 or len(t[0]) >= 6:
            slugs.append(t[0])
    seen: set[str] = set()
    hosts: list[str] = []
    for tld in tlds:
        for slug in slugs:
            if 2 <= len(slug) <= 63 and not slug.startswith("-") and not slug.endswith("-"):
                host = f"{slug}.{tld}"
                if host not in seen:
                    seen.add(host)
                    hosts.append(host)
    return hosts[:limit]


def email_domain_candidate(email: str | None) -> str | None:
    """Business email domain (not free mail / ISP mail) as a website CANDIDATE."""
    if not email or "@" not in email:
        return None
    domain = email.rsplit("@", 1)[1].strip().casefold().strip(".")
    return None if not domain or domain in FREE_MAIL else domain
