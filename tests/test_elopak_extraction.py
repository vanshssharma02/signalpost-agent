"""Test extraction for test company 811413682 (Elopak ASA)."""
import pytest
from norway_company_agent.batch import profiles_from_bulk
from norway_company_agent.website import fetch_website
from norway_company_agent.identity import apply_website_identity_gate


def test_elopak_bulk_and_website_extraction():
    # 1. Bulk extraction from Brreg snapshot
    profiles, meta = profiles_from_bulk("data/brreg-enheter.csv", ["811413682"])
    assert len(profiles) == 1
    profile = profiles[0]
    assert profile["organisation_number"] == "811413682"
    assert "ELOPAK" in profile["name"]
    assert profile["website"] == "www.elopak.com"

    # Verify no None keys in profile or raw
    assert None not in profile
    raw = profile.get("evidence", {}).get("registry", {}).get("value", {})
    assert None not in raw
    assert raw.get("hjemmeside") == "www.elopak.com"

    # 2. Website extraction & identity gate
    web_rec, _ = fetch_website(profile["website"])
    assert web_rec["status"] == "available"
    assert web_rec["source_url"] == "https://www.elopak.com/"
    assert web_rec["retrieved_at"] is not None

    val = web_rec.get("value") or {}
    assert "elopak.com" in val.get("registered_domain", "")
    assert val.get("final_url") == "https://www.elopak.com/"

    gated = apply_website_identity_gate(profile, web_rec)
    assert gated["website"]["status"] == "available"
    assert gated["assessment"]["publishable"] is True
    assert "elopak" in gated["assessment"]["matched_tokens"]
