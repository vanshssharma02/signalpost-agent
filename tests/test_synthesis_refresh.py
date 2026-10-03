"""Unit tests for synthesis and refresh engine (Workflow /05)."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from signalpost.ref.claims import canonical, claim_key, merge_claims, value_hash
from signalpost.ref.envelope import (
    FAMILIES,
    make_claim,
    make_evidence,
    new_envelope,
    set_field_state,
    utc_now,
)
from signalpost.ref.validate import compare_runs
from signalpost.synthesis import compose_synthesis


def test_claim_key_determinism():
    k1 = claim_key("123456789", "revenue", "2024")
    k2 = claim_key("123456789", "revenue", "2024")
    assert k1 == k2
    assert len(k1) == 20
    # Different discriminator gives different key
    k3 = claim_key("123456789", "revenue", "2023")
    assert k1 != k3


def test_merge_claims_idempotent():
    now1 = "2026-08-01T00:00:00Z"
    claims = [
        {"key": "k1", "field": "legal_name", "value": "Test AS"},
        {"key": "k2", "field": "revenue", "value": 1000.0},
    ]
    store1, changes1 = merge_claims({}, claims, now1, rechecked_fields={"legal_name", "revenue"})
    assert len(changes1) == 2
    assert all(c["type"] == "added" for c in changes1)
    assert store1["k1"]["first_observed_at"] == now1
    assert store1["k1"]["last_verified_at"] == now1

    # Rerun with identical claims at now2
    now2 = "2026-08-02T00:00:00Z"
    store2, changes2 = merge_claims(store1, claims, now2, rechecked_fields={"legal_name", "revenue"})
    assert changes2 == []  # Zero false changes!
    assert store2["k1"]["first_observed_at"] == now1  # Preserved!
    assert store2["k1"]["last_verified_at"] == now2   # Updated!


def test_merge_claims_change_and_removal():
    now1 = "2026-08-01T00:00:00Z"
    claims1 = [
        {"key": "k1", "field": "employees", "value": 5},
        {"key": "k2", "field": "role_holder", "value": "Ola Nordmann"},
    ]
    store1, _ = merge_claims({}, claims1, now1, rechecked_fields={"employees", "role_holder"})

    now2 = "2026-08-02T00:00:00Z"
    # Injected change: employees changed to 10; role_holder removed
    claims2 = [
        {"key": "k1", "field": "employees", "value": 10},
    ]
    store2, changes2 = merge_claims(store1, claims2, now2, rechecked_fields={"employees", "role_holder"})
    assert len(changes2) == 2
    ch_types = {c["type"] for c in changes2}
    assert ch_types == {"changed", "removed"}
    assert store2["k1"]["value"] == 10
    assert len(store2["k1"]["history"]) == 1
    assert store2["k2"]["removed_at"] == now2


def test_merge_claims_failed_source_preserves_last_supported():
    now1 = "2026-08-01T00:00:00Z"
    claims1 = [{"key": "k1", "field": "financials", "value": 500}]
    store1, _ = merge_claims({}, claims1, now1, rechecked_fields={"financials"})

    now2 = "2026-08-02T00:00:00Z"
    # Source failed: financials was NOT in rechecked_fields
    store2, changes2 = merge_claims(store1, [], now2, rechecked_fields=set())
    assert changes2 == []
    assert "k1" in store2
    assert store2["k1"].get("removed_at") is None


def test_compose_synthesis_schema_and_citations():
    org = "123456789"
    run_meta = {"run_id": "test-run", "started_at": "2026-10-04T00:00:00Z"}
    env = new_envelope(org, run_meta)

    # Add claims
    now = utc_now()
    c_name = make_claim("cid-name-1", "legal_name", "identity", "NORDIC TECH AS", ["ev-1"], source_class="registry", method="bulk", now=now)
    c_form = make_claim("cid-form-1", "legal_form", "identity", "AS", ["ev-1"], source_class="registry", method="bulk", now=now)
    c_ind = make_claim("cid-ind-1", "industry_code", "identity", "62.010", ["ev-1"], source_class="registry", method="bulk", now=now)
    c_rev = make_claim("cid-rev-1", "revenue", "accounts", 15000000.0, ["ev-2"], source_class="accounts", method="api", reporting_period={"from": "2024-01-01", "to": "2024-12-31"}, now=now)
    c_op = make_claim("cid-op-1", "operating_result", "accounts", 2500000.0, ["ev-2"], source_class="accounts", method="api", reporting_period={"from": "2024-01-01", "to": "2024-12-31"}, now=now)
    c_net = make_claim("cid-net-1", "annual_result", "accounts", 2000000.0, ["ev-2"], source_class="accounts", method="api", reporting_period={"from": "2024-01-01", "to": "2024-12-31"}, now=now)
    c_ass = make_claim("cid-ass-1", "assets", "accounts", 10000000.0, ["ev-2"], source_class="accounts", method="api", reporting_period={"from": "2024-01-01", "to": "2024-12-31"}, now=now)
    c_eq = make_claim("cid-eq-1", "equity", "accounts", 6000000.0, ["ev-2"], source_class="accounts", method="api", reporting_period={"from": "2024-01-01", "to": "2024-12-31"}, now=now)
    c_chair = make_claim("cid-chair-1", "role_holder", "leadership", {"name": "Astrid Lind", "role_code": "LEDE"}, ["ev-3"], source_class="roles", method="api", now=now)
    c_ceo = make_claim("cid-ceo-1", "role_holder", "leadership", {"name": "Lars Holm", "role_code": "DAGL"}, ["ev-3"], source_class="roles", method="api", now=now)
    c_web = make_claim("cid-web-1", "official_website", "website", "https://nordictech.no", ["ev-4"], source_class="company_owned", method="verified", now=now)
    c_brand = make_claim("cid-brand-1", "public_brand", "brand", "NordicTech", ["ev-4"], source_class="company_owned", method="verified", now=now)

    for c in (c_name, c_form, c_ind, c_rev, c_op, c_net, c_ass, c_eq, c_chair, c_ceo, c_web, c_brand):
        env["claims"].append(c)
        set_field_state(env, c["family"], "available", "verified")

    # Set other families to not_available
    for fam in ("locations", "group", "company_profiles", "hiring", "activity", "accounts_history"):
        set_field_state(env, fam, "not_available", f"no_{fam}_found")

    synth = compose_synthesis(env)

    # 1. Fixed schema keys
    expected_keys = {
        "generator", "language", "headline", "what_it_does", "business_model",
        "size_and_financials", "leadership_and_structure", "locations", "hiring_signal",
        "recent_activity", "what_changed", "unknowns", "sentences",
    }
    assert set(synth.keys()) == expected_keys
    assert synth["generator"] == "template-v1"
    assert synth["language"] == "en"

    # 2. Headline
    assert "NORDIC TECH AS (AS, org.nr 123456789)" in synth["headline"]

    # 3. Sentence citations
    all_env_cids = {c["claim_id"] for c in env["claims"]}
    assert len(synth["sentences"]) > 5
    for s in synth["sentences"]:
        assert isinstance(s["id"], str)
        assert isinstance(s["text"], str)
        assert isinstance(s["claim_ids"], list)
        # Every cited claim_id MUST exist in envelope claims
        for cid in s["claim_ids"]:
            assert cid in all_env_cids

    # 4. Unknowns list
    assert len(synth["unknowns"]) >= 6
    for u in synth["unknowns"]:
        assert "topic" in u and "why" in u and "checked" in u
        assert isinstance(u["checked"], list)

    # 5. Length constraint (< 250 words)
    total_words = sum(len(s["text"].split()) for s in synth["sentences"])
    assert total_words < 250


def test_compose_synthesis_sparse_entity():
    org = "999888777"
    env = new_envelope(org, {"run_id": "sparse-run", "started_at": "2026-10-04T00:00:00Z"})
    now = utc_now()
    c_name = make_claim("cid-sparse-name", "legal_name", "identity", "SPARSE ENK", ["ev-1"], source_class="registry", method="bulk", now=now)
    env["claims"].append(c_name)
    set_field_state(env, "identity", "available", "verified")
    for fam in FAMILIES:
        if fam != "identity":
            set_field_state(env, fam, "not_available", "not_found")

    synth = compose_synthesis(env)
    assert synth["headline"] == "SPARSE ENK (Entity, org.nr 999888777)"
    assert synth["business_model"] is None
    # Unknowns list cataloged
    assert len(synth["unknowns"]) >= 10
    # Sentences valid
    for s in synth["sentences"]:
        for cid in s["claim_ids"]:
            assert cid in {"cid-sparse-name"}
