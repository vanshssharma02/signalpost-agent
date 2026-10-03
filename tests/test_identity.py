"""Anti-contamination and exact-entity proof test suite (Workflow /03).

Verifies strict proof semantics across edge cases:
- sister company on a shared group site
- franchise sites with the same brand and different org numbers
- agency portfolio listing 20 customer org numbers
- two companies with near-identical legal names
- directory page that prints the org number
- Facebook page as registry homepage
- domain-for-sale page
- org number only inside an image
- org number in a valid format (NO ... MVA)
- NUF branch pointing at the foreign parent's site
- sole proprietorship with a personal name
- page mentioning our org number in a customer list among many others
- look-alike TLD belonging to another firm
"""
from __future__ import annotations

from pathlib import Path
import pytest

from signalpost.identity_proof import (
    verify_website_proof,
    is_blocklisted_host,
    is_parked_page,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "identity"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def test_valid_mva_format_passes_p1():
    html = _read_fixture("valid_mva_format.html")
    res = verify_website_proof(
        candidate_url="https://sandneselektriske.no",
        final_url="https://sandneselektriske.no/",
        page_html=html,
        target_orgnr="985821585",
        legal_name="SANDNES ELEKTRISKE AS",
    )
    assert res.verdict == "exact"
    assert res.proof_level == "p1_exact"
    assert res.reason == "verified_p1_exact"
    assert "985821585" in (res.claim_span or "").replace(".", "").replace(" ", "")


def test_sister_company_rejected():
    html = _read_fixture("sister_company.html")
    # Target is sister 988077917; page only has parent 985821585
    res = verify_website_proof(
        candidate_url="https://nordicgroup.no",
        final_url="https://nordicgroup.no/",
        page_html=html,
        target_orgnr="988077917",
        legal_name="SUBSIDIARY BETA AS",
        family_orgnrs={"985821585"},
    )
    assert res.verdict == "rejected"
    assert res.reason == "belongs_to_parent_or_sister"


def test_franchise_site_rejected():
    html = _read_fixture("franchise_site.html")
    # Target is Burger King Norway 985821585; page is franchisee 923609016
    res = verify_website_proof(
        candidate_url="https://burgerkingoslo.no",
        final_url="https://burgerkingoslo.no/",
        page_html=html,
        target_orgnr="985821585",
        legal_name="BURGER KING NORGE AS",
    )
    assert res.verdict == "rejected"
    assert res.reason == "other_org_labelled"


def test_agency_portfolio_rejected():
    html = _read_fixture("agency_portfolio.html")
    # Page lists multiple clients
    res = verify_website_proof(
        candidate_url="https://webdesign.no/portfolio",
        final_url="https://webdesign.no/portfolio",
        page_html=html,
        target_orgnr="985821585",
        legal_name="KUNDE EN AS",
    )
    assert res.verdict == "rejected"
    assert res.reason == "group_or_portfolio_page"


def test_customer_list_mention_rejected():
    html = _read_fixture("customer_list_mention.html")
    res = verify_website_proof(
        candidate_url="https://saasnordic.no/kunder",
        final_url="https://saasnordic.no/kunder",
        page_html=html,
        target_orgnr="985821585",
        legal_name="KUNDE A AS",
    )
    assert res.verdict == "rejected"
    assert res.reason == "group_or_portfolio_page"


def test_near_identical_name_rejected_without_proof():
    html = _read_fixture("near_identical_name.html")
    res = verify_website_proof(
        candidate_url="https://bergenelektro.no",
        final_url="https://bergenelektro.no/",
        page_html=html,
        target_orgnr="985821585",
        legal_name="BERGEN ELEKTRO INSTALLASJON AS",
    )
    assert res.verdict == "rejected"
    assert res.reason in {"name_only_match", "no_proof"}


def test_directory_page_rejected():
    html = _read_fixture("directory_page.html")
    res = verify_website_proof(
        candidate_url="https://proff.no/selskap/sandnes/985821585",
        final_url="https://proff.no/selskap/sandnes/985821585",
        page_html=html,
        target_orgnr="985821585",
        legal_name="SANDNES ELEKTRISKE AS",
    )
    assert res.verdict == "rejected"
    assert res.reason == "host_blocklisted"


def test_facebook_page_rejected():
    html = _read_fixture("facebook_page.html")
    res = verify_website_proof(
        candidate_url="https://facebook.com/sandneselektriske",
        final_url="https://facebook.com/sandneselektriske",
        page_html=html,
        target_orgnr="985821585",
        legal_name="SANDNES ELEKTRISKE AS",
    )
    assert res.verdict == "rejected"
    assert res.reason == "host_blocklisted"


def test_parked_page_rejected():
    html = _read_fixture("parked_domain.html")
    res = verify_website_proof(
        candidate_url="https://sandneselektriske.no",
        final_url="https://sandneselektriske.no/",
        page_html=html,
        target_orgnr="985821585",
        legal_name="SANDNES ELEKTRISKE AS",
    )
    assert res.verdict == "rejected"
    assert res.reason == "parked_page"


def test_orgnr_in_image_not_p1():
    html = _read_fixture("orgnr_in_image.html")
    res = verify_website_proof(
        candidate_url="https://sandneselektriske.no",
        final_url="https://sandneselektriske.no/",
        page_html=html,
        target_orgnr="985821585",
        legal_name="SANDNES ELEKTRISKE AS",
    )
    # Must NOT pass P1 because text does not contain the orgnr
    assert res.proof_level != "p1_exact"
    assert res.verdict == "rejected"


def test_nuf_parent_site_rejected():
    html = _read_fixture("nuf_parent_site.html")
    res = verify_website_proof(
        candidate_url="https://acmeglobal.com",
        final_url="https://acmeglobal.com/",
        page_html=html,
        target_orgnr="985821585",
        legal_name="ACME GLOBAL NORGE NUF",
    )
    assert res.verdict == "rejected"


def test_sole_proprietorship_rejected_without_strong_combo():
    html = _read_fixture("sole_proprietorship.html")
    res = verify_website_proof(
        candidate_url="https://nordmann.no",
        final_url="https://nordmann.no/",
        page_html=html,
        target_orgnr="985821585",
        legal_name="OLA NORDMANN ENK",
    )
    assert res.verdict == "rejected"


def test_lookalike_domain_with_other_orgnr_rejected():
    html = _read_fixture("lookalike_domain.html")
    res = verify_website_proof(
        candidate_url="https://tidetec.com",
        final_url="https://tidetec.com/",
        page_html=html,
        target_orgnr="980502155",  # Target is Norwegian Tidetec AS
        legal_name="TIDETEC AS",
    )
    assert res.verdict == "rejected"
    assert res.reason == "other_org_labelled"
