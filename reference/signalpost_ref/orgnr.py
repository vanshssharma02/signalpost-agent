"""Norwegian organisation-number handling: normalise, validate (mod-11), find on a page.

The organisation number is the ONLY identity key. A page that shows the target number
is exact-entity proof; name similarity never is.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

WEIGHTS = (3, 2, 7, 6, 5, 4, 3, 2)

# 9 digits, optional single separators (space, dot, NBSP) between the 3-digit groups.
# Lookarounds make sure we never cut a longer digit run (phones, bank accounts, IDs).
_ORG_RE = re.compile(r"(?<![\d.])(\d{3})[ .\u00a0]?(\d{3})[ .\u00a0]?(\d{3})(?![\d])")
_LABEL_RE = re.compile(
    r"(org\.?\s*-?\s*(?:nr|no|nummer)\.?|organi[sz]asjonsnummer|organi[sz]ation\s+(?:number|no)\.?"
    r"|foretaksregisteret|enhetsregisteret|vat|mva|orgnr)[\s:#-]*(?:NO\s*)?$",
    re.IGNORECASE,
)


def normalize(value: object) -> str | None:
    """Return the 9-digit string, or None if the value is not exactly nine digits."""
    digits = re.sub(r"\D", "", str(value or ""))
    return digits if len(digits) == 9 else None


def is_valid(orgnr: str | None) -> bool:
    """Mod-11 check digit (weights 3,2,7,6,5,4,3,2)."""
    org = normalize(orgnr)
    if not org:
        return False
    total = sum(int(d) * w for d, w in zip(org[:8], WEIGHTS))
    check = 11 - (total % 11)
    if check == 11:
        check = 0
    return check != 10 and check == int(org[8])


@dataclass(frozen=True)
class OrgnrHit:
    orgnr: str
    start: int
    end: int
    valid: bool
    labelled: bool  # preceded by "org.nr", "organisasjonsnummer", "NO ... MVA", ...
    context: str


def find_orgnrs(text: str, *, window: int = 60) -> list[OrgnrHit]:
    """All 9-digit candidates in text, with mod-11 validity and label detection."""
    hits: list[OrgnrHit] = []
    for match in _ORG_RE.finditer(text or ""):
        org = "".join(match.groups())
        before = text[max(0, match.start() - 24): match.start()]
        labelled = bool(_LABEL_RE.search(before))
        hits.append(
            OrgnrHit(
                orgnr=org,
                start=match.start(),
                end=match.end(),
                valid=is_valid(org),
                labelled=labelled,
                context=text[max(0, match.start() - window): match.end() + window].replace("\n", " "),
            )
        )
    return hits


def assess_page(text: str, target: str, family: set[str] | None = None) -> dict:
    """Decide what a page proves about `target`.

    family = target + its subunits + (optionally) parent/group members from the registry,
    used to tell "same legal entity" from "sister company" pages.
    Returns {"verdict": "exact" | "conflict" | "none", "span": str|None, "foreign": [...]}.
    """
    target_n = normalize(target)
    family = {normalize(x) for x in (family or set())} - {None}
    hits = find_orgnrs(text)
    mine = [h for h in hits if h.orgnr == target_n]
    foreign = [h for h in hits if h.valid and h.orgnr != target_n and h.orgnr not in family]
    foreign_labelled = [h for h in foreign if h.labelled]
    if mine:
        best = sorted(mine, key=lambda h: (not h.labelled, h.start))[0]
        # A different, labelled organisation number on the page and ours only unlabelled
        # => group/agency/portfolio page. Do not publish as exact.
        if foreign_labelled and not best.labelled:
            return {"verdict": "conflict", "span": best.context, "foreign": [h.orgnr for h in foreign_labelled]}
        return {"verdict": "exact", "span": best.context, "foreign": [h.orgnr for h in foreign_labelled]}
    if foreign_labelled:
        return {"verdict": "conflict", "span": None, "foreign": [h.orgnr for h in foreign_labelled]}
    return {"verdict": "none", "span": None, "foreign": []}
