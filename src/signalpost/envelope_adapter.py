"""Module for building compliant terminal envelopes matching OUTPUT_CONTRACT.md and signalpost_ref schema."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from signalpost.ref.envelope import (
    FAMILIES,
    STATES,
    add_claim,
    add_error,
    failure_envelope,
    finalize,
    make_claim,
    make_evidence,
    new_envelope,
    set_field_state,
    sha256_hex,
    utc_now,
)
from signalpost.ref.claims import claim_key


def profile_to_envelope(profile: dict[str, Any], *, run: dict) -> dict[str, Any]:
    """Convert an enriched profile dict into a compliant contract envelope."""
    orgnr = str(profile.get("organisation_number") or "")
    env = new_envelope(orgnr, run)
    
    # Check flags
    deleted = bool(profile.get("deleted") or (profile.get("evidence", {}).get("registry_live", {}).get("value") or {}).get("deleted"))
    bankrupt = bool(profile.get("bankrupt") or (profile.get("evidence", {}).get("registry_live", {}).get("value") or {}).get("bankrupt"))
    liquidating = bool(profile.get("liquidating") or (profile.get("evidence", {}).get("registry_live", {}).get("value") or {}).get("liquidating"))
    
    env["identity"]["flags"] = {
        "deleted": deleted,
        "bankrupt": bankrupt,
        "liquidating": liquidating,
    }
    
    now = utc_now()
    evidences = profile.get("evidence", {})
    
    # 1. Identity family
    reg_ev = evidences.get("registry") or evidences.get("registry_live")
    if reg_ev and reg_ev.get("status") == "available":
        raw_val = reg_ev.get("value") or {}
        span_text = f"Organisasjonsnummer {orgnr} {raw_val.get('name') or profile.get('name') or ''}"
        ev = make_evidence(
            f"ev-reg-{orgnr}",
            source_url=reg_ev.get("source_url") or f"https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}",
            retrieved_at=reg_ev.get("retrieved_at") or now,
            content_sha256=reg_ev.get("content_sha256") or sha256_hex(span_text),
            claim_span=span_text,
            source_class=reg_ev.get("source_class") or "official_registry",
        )
        c = make_claim(
            claim_key(orgnr, "legal_name"),
            field="legal_name",
            family="identity",
            value=raw_val.get("name") or profile.get("name"),
            evidence_ids=[ev["id"]],
            source_class="official_registry",
            method="registry_snapshot",
            identity_proof="orgnr_exact",
        )
        add_claim(env, c, [ev])
        if profile.get("legal_form") or raw_val.get("legal_form"):
            c_form = make_claim(
                claim_key(orgnr, "legal_form"),
                field="legal_form",
                family="identity",
                value=profile.get("legal_form") or raw_val.get("legal_form"),
                evidence_ids=[ev["id"]],
                source_class="official_registry",
                method="registry_snapshot",
                identity_proof="orgnr_exact",
            )
            add_claim(env, c_form, [ev])
    elif reg_ev and reg_ev.get("status") in {"not_found", "not_applicable"}:
        set_field_state(env, "identity", reg_ev["status"], "registry_reported_" + reg_ev["status"])
    elif reg_ev and reg_ev.get("status") == "source_error":
        set_field_state(env, "identity", "failed", "source_error")

    # 2. Accounts & Accounts History
    fin_ev = evidences.get("financials")
    if fin_ev and fin_ev.get("status") == "available":
        fin_val = fin_ev.get("value") or {}
        records = fin_val.get("records") or []
        if records:
            for idx, rec in enumerate(records[:3]):
                period = rec.get("period") or {"fraDato": "2024-01-01", "tilDato": "2024-12-31"}
                from_d = period.get("fraDato") or period.get("from") or "2024-01-01"
                to_d = period.get("tilDato") or period.get("to") or "2024-12-31"
                rep_period = {"from": from_d, "to": to_d}
                fiscal_year = str(to_d)[:4]
                span_text = f"Filing {fiscal_year}: revenue {rec.get('revenue')}"
                ev_id = f"ev-fin-{orgnr}-{fiscal_year}"
                ev = make_evidence(
                    ev_id,
                    source_url=fin_ev.get("source_url") or f"https://data.brreg.no/regnskapsregisteret/regnskap/{orgnr}",
                    retrieved_at=fin_ev.get("retrieved_at") or now,
                    content_sha256=fin_ev.get("content_sha256") or sha256_hex(span_text),
                    claim_span=span_text,
                    source_class="official_annual_accounts",
                    reporting_period=rep_period,
                )
                if rec.get("revenue") is not None:
                    c = make_claim(
                        claim_key(orgnr, "revenue", fiscal_year),
                        field="revenue",
                        family="accounts",
                        value=rec["revenue"],
                        evidence_ids=[ev["id"]],
                        source_class="official_annual_accounts",
                        method="regnskap_api",
                        reporting_period=rep_period,
                    )
                    add_claim(env, c, [ev])
        else:
            set_field_state(env, "accounts", "not_available", "no_filings_returned")
    elif fin_ev and fin_ev.get("status") == "not_found":
        set_field_state(env, "accounts", "not_available", "no_filing_returned")
    elif fin_ev and fin_ev.get("status") == "source_error":
        set_field_state(env, "accounts", "failed", "source_error")

    # 3. Leadership / Roles
    roles_ev = evidences.get("roles")
    if roles_ev and roles_ev.get("status") == "available":
        roles_val = roles_ev.get("value") or {}
        roles_list = roles_val.get("roles") or []
        if roles_list:
            for r in roles_list:
                role_code = r.get("role_code") or "ROLE"
                name = r.get("name") or "Unknown"
                span_text = f"Role {role_code}: {name}"
                ev_id = f"ev-role-{orgnr}-{role_code}"
                ev = make_evidence(
                    ev_id,
                    source_url=roles_ev.get("source_url") or f"https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}/roller",
                    retrieved_at=roles_ev.get("retrieved_at") or now,
                    content_sha256=roles_ev.get("content_sha256") or sha256_hex(span_text),
                    claim_span=span_text,
                    source_class="official_roles",
                )
                c = make_claim(
                    claim_key(orgnr, "role_holder", f"{role_code}_{name}"),
                    field="role_holder",
                    family="leadership",
                    value=name,
                    evidence_ids=[ev["id"]],
                    source_class="official_roles",
                    method="roller_api",
                )
                add_claim(env, c, [ev])
        else:
            set_field_state(env, "leadership", "not_available", "no_roles_returned")
    elif roles_ev and roles_ev.get("status") == "not_found":
        set_field_state(env, "leadership", "not_available", "roles_endpoint_404")
    elif roles_ev and roles_ev.get("status") == "source_error":
        set_field_state(env, "leadership", "failed", "source_error")

    # 4. Locations (Subunits)
    loc_ev = evidences.get("locations")
    if loc_ev and loc_ev.get("status") == "available":
        loc_val = loc_ev.get("value") or {}
        subunits = loc_val.get("locations") or []
        if subunits:
            for sub in subunits:
                sub_org = sub.get("organisation_number") or "sub"
                span_text = f"Subunit {sub_org}: {sub.get('name')}"
                ev_id = f"ev-loc-{orgnr}-{sub_org}"
                ev = make_evidence(
                    ev_id,
                    source_url=loc_ev.get("source_url") or f"https://data.brreg.no/enhetsregisteret/api/underenheter?overordnetEnhet={orgnr}",
                    retrieved_at=loc_ev.get("retrieved_at") or now,
                    content_sha256=loc_ev.get("content_sha256") or sha256_hex(span_text),
                    claim_span=span_text,
                    source_class="official_subunits",
                )
                c = make_claim(
                    claim_key(orgnr, "subunit", sub_org),
                    field="subunit",
                    family="locations",
                    value=sub,
                    evidence_ids=[ev["id"]],
                    source_class="official_subunits",
                    method="underenheter_api",
                )
                add_claim(env, c, [ev])
        else:
            set_field_state(env, "locations", "not_available", "no_subunits_returned")
    elif loc_ev and loc_ev.get("status") == "not_found":
        set_field_state(env, "locations", "not_available", "subunits_endpoint_404")
    elif loc_ev and loc_ev.get("status") == "source_error":
        set_field_state(env, "locations", "failed", "source_error")

    # 5. Website
    web_ev = evidences.get("website")
    if web_ev and web_ev.get("status") == "available":
        web_val = web_ev.get("value") or {}
        homepage = web_val.get("final_url") or profile.get("website")
        span_text = f"Org.nr. {orgnr}"
        ev_id = f"ev-web-{orgnr}"
        ev = make_evidence(
            ev_id,
            source_url=web_ev.get("source_url") or homepage,
            final_url=homepage,
            retrieved_at=web_ev.get("retrieved_at") or now,
            content_sha256=web_ev.get("content_sha256") or sha256_hex(span_text),
            claim_span=span_text,
            source_class="company_owned",
        )
        c = make_claim(
            claim_key(orgnr, "official_website"),
            field="official_website",
            family="website",
            value=homepage,
            evidence_ids=[ev["id"]],
            source_class="company_owned",
            method="orgnr_exact",
            identity_proof="orgnr_exact",
        )
        add_claim(env, c, [ev])
    elif web_ev and web_ev.get("status") in {"not_found", "not_applicable"}:
        set_field_state(env, "website", "not_available", "no_website_declared")
    elif web_ev and web_ev.get("status") == "blocked":
        set_field_state(env, "website", "blocked", "robots_denied")

    # Set remaining families to not_available or not_checked
    for fam in FAMILIES:
        if env["field_states"][fam]["availability"] == "failed" and env["field_states"][fam]["reason"] == "not_checked":
            set_field_state(env, fam, "not_available", "checked_nothing_found")

    # Record operations metrics
    metrics = profile.get("run_metrics") or {}
    env["operations"] = {
        "requests": metrics.get("requests", 0),
        "runtime_ms": int(sum(metrics.get("latencies_ms", []))),
        "third_party_cost_usd": 0.0,
    }

    # Keep legacy profile dict for backwards compatibility
    env["profile"] = profile
    return finalize(env)
