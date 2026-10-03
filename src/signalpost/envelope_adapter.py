"""Module for building compliant terminal envelopes matching OUTPUT_CONTRACT.md and signalpost_ref schema."""
from __future__ import annotations

import gzip
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

from signalpost.ref.claims import claim_key
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


def store_snapshot(snapshots_dir: Path | str | None, text_or_bytes: str | bytes) -> tuple[str, str | None]:
    """Store raw snapshot text or bytes to snapshots_dir/ab/<sha>.gz and return (sha256, rel_path)."""
    if isinstance(text_or_bytes, str):
        content = text_or_bytes.encode("utf-8")
    else:
        content = text_or_bytes
    sha = hashlib.sha256(content).hexdigest()
    if not snapshots_dir:
        return sha, None
    s_dir = Path(snapshots_dir)
    rel_path = f"{sha[:2]}/{sha}.gz"
    full_path = s_dir / rel_path
    if not full_path.exists():
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(full_path, "wb") as gz:
            gz.write(content)
    return sha, rel_path


def profile_to_envelope(
    profile: dict[str, Any],
    *,
    run: dict,
    snapshots_dir: Path | str | None = None,
) -> dict[str, Any]:
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
        name_val = raw_val.get("name") or profile.get("name") or f"Entity {orgnr}"
        if isinstance(name_val, list):
            name = " ".join(str(x) for x in name_val).strip() or f"Entity {orgnr}"
        else:
            name = str(name_val).strip()
        form = profile.get("legal_form") or raw_val.get("legal_form")
        employees = raw_val.get("employees") if raw_val.get("employees") is not None else profile.get("employees")
        industry = raw_val.get("industry") or profile.get("industry_code")
        reg_date = raw_val.get("registration_date") or profile.get("registration_date")
        b_addr = raw_val.get("business_address") or profile.get("business_address")
        p_addr = raw_val.get("postal_address") or profile.get("postal_address")

        snapshot_lines = [
            f"Organisasjonsnummer {orgnr} {name}",
            f"Foretaksform: {form or ''}",
            f"Ansatte: {employees if employees is not None else ''}",
            f"Naering: {industry or ''}",
            f"Stiftelsesdato: {reg_date or ''}",
            f"Forretningsadresse: {b_addr if b_addr else ''}",
            f"Postadresse: {p_addr if p_addr else ''}",
            json.dumps(raw_val, ensure_ascii=False),
        ]
        snapshot_content = "\n".join(snapshot_lines)
        sha, snap_ref = store_snapshot(snapshots_dir, snapshot_content)

        span_text = f"Organisasjonsnummer {orgnr} {name}"
        ev = make_evidence(
            f"ev-reg-{orgnr}",
            source_url=reg_ev.get("source_url") or f"https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}",
            retrieved_at=reg_ev.get("retrieved_at") or now,
            content_sha256=sha,
            snapshot_ref=snap_ref,
            claim_span=span_text,
            source_class=reg_ev.get("source_class") or "official_registry",
        )

        c_name = make_claim(
            claim_key(orgnr, "legal_name"),
            field="legal_name",
            family="identity",
            value=name,
            evidence_ids=[ev["id"]],
            source_class="official_registry",
            method="registry_snapshot",
            identity_proof="orgnr_exact",
        )
        add_claim(env, c_name, [ev])
        env["identity"]["legal_name"] = name
        env["identity"]["claim_ids"].append(c_name["claim_id"])

        if form:
            c_form = make_claim(
                claim_key(orgnr, "legal_form"),
                field="legal_form",
                family="identity",
                value=form,
                evidence_ids=[ev["id"]],
                source_class="official_registry",
                method="registry_snapshot",
                identity_proof="orgnr_exact",
            )
            add_claim(env, c_form, [ev])
            env["identity"]["claim_ids"].append(c_form["claim_id"])

        if employees is not None:
            c_emp = make_claim(
                claim_key(orgnr, "registered_employees"),
                field="registered_employees",
                family="identity",
                value=employees,
                evidence_ids=[ev["id"]],
                source_class="official_registry",
                method="registry_snapshot",
                identity_proof="orgnr_exact",
            )
            add_claim(env, c_emp, [ev])
            env["identity"]["claim_ids"].append(c_emp["claim_id"])

        if industry:
            c_ind = make_claim(
                claim_key(orgnr, "industry_code"),
                field="industry_code",
                family="identity",
                value=industry,
                evidence_ids=[ev["id"]],
                source_class="official_registry",
                method="registry_snapshot",
                identity_proof="orgnr_exact",
            )
            add_claim(env, c_ind, [ev])
            env["identity"]["claim_ids"].append(c_ind["claim_id"])

        if b_addr:
            c_baddr = make_claim(
                claim_key(orgnr, "business_address"),
                field="business_address",
                family="identity",
                value=b_addr,
                evidence_ids=[ev["id"]],
                source_class="official_registry",
                method="registry_snapshot",
                identity_proof="orgnr_exact",
            )
            add_claim(env, c_baddr, [ev])
            env["identity"]["claim_ids"].append(c_baddr["claim_id"])
    elif reg_ev and reg_ev.get("status") in {"not_found", "not_applicable"}:
        set_field_state(env, "identity", reg_ev["status"], "registry_reported_" + reg_ev["status"])
    elif reg_ev and reg_ev.get("status") == "source_error":
        set_field_state(env, "identity", "failed", "source_error")

    # 2. Accounts (Financials)
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

                metric_pairs = []
                for m in ("revenue", "operating_result", "profit_before_tax", "annual_result", "assets", "equity", "debt"):
                    if rec.get(m) is not None:
                        metric_pairs.append(f"{m}: {rec[m]}")

                span_text = f"Filing {fiscal_year}: " + ", ".join(metric_pairs)
                snap_content = f"{span_text}\n{json.dumps(rec, ensure_ascii=False)}"
                sha, snap_ref = store_snapshot(snapshots_dir, snap_content)

                ev_id = f"ev-fin-{orgnr}-{fiscal_year}"
                ev = make_evidence(
                    ev_id,
                    source_url=fin_ev.get("source_url") or f"https://data.brreg.no/regnskapsregisteret/regnskap/{orgnr}",
                    retrieved_at=fin_ev.get("retrieved_at") or now,
                    content_sha256=sha,
                    snapshot_ref=snap_ref,
                    claim_span=span_text,
                    source_class="official_annual_accounts",
                    reporting_period=rep_period,
                )

                for m in ("revenue", "operating_result", "profit_before_tax", "annual_result", "assets", "equity", "debt"):
                    val = rec.get(m)
                    if val is not None:
                        c = make_claim(
                            claim_key(orgnr, m, fiscal_year),
                            field=m,
                            family="accounts",
                            value=val,
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
            def _clean_role_name(val: Any) -> str:
                if isinstance(val, list):
                    return " ".join(str(x) for x in val).strip() or "Unknown"
                if isinstance(val, dict):
                    return str(val.get("navn") or val).strip() or "Unknown"
                return str(val).strip() if val else "Unknown"

            roles_text_lines = [f"Roller for {orgnr}:"]
            for r in roles_list:
                rc = str(r.get("role_code") or "ROLE")
                rn = _clean_role_name(r.get("name") or r.get("organisation_number"))
                roles_text_lines.append(f"Role {rc}: {rn}")
            roles_text_lines.append(json.dumps(roles_val, ensure_ascii=False))
            roles_snap = "\n".join(roles_text_lines)
            sha, snap_ref = store_snapshot(snapshots_dir, roles_snap)

            for r in roles_list:
                role_code = str(r.get("role_code") or "ROLE")
                name = _clean_role_name(r.get("name") or r.get("organisation_number"))
                span_text = f"Role {role_code}: {name}"
                role_hash = sha256_hex(f"{role_code}:{name}")[:12]
                ev_id = f"ev-role-{orgnr}-{role_hash}"
                ev = make_evidence(
                    ev_id,
                    source_url=roles_ev.get("source_url") or f"https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}/roller",
                    retrieved_at=roles_ev.get("retrieved_at") or now,
                    content_sha256=sha,
                    snapshot_ref=snap_ref,
                    claim_span=span_text,
                    source_class="official_roles",
                )
                c = make_claim(
                    claim_key(orgnr, "role_holder", f"{role_code}_{name}"),
                    field="role_holder",
                    family="leadership",
                    value={"name": name, "role_code": role_code, "role": r.get("role")},
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
            def _clean_sub_name(val: Any) -> str:
                if isinstance(val, list):
                    return " ".join(str(x) for x in val).strip() or "Unknown"
                return str(val).strip() if val else "Unknown"

            loc_lines = [f"Underenheter for {orgnr}:"]
            for sub in subunits:
                sub_org = str(sub.get("organisation_number") or "sub")
                sub_name = _clean_sub_name(sub.get("name"))
                loc_lines.append(f"Subunit {sub_org}: {sub_name}")
            loc_lines.append(json.dumps(loc_val, ensure_ascii=False))
            loc_snap = "\n".join(loc_lines)
            sha, snap_ref = store_snapshot(snapshots_dir, loc_snap)

            for sub in subunits:
                sub_org = str(sub.get("organisation_number") or "sub")
                sub_name = _clean_sub_name(sub.get("name"))
                span_text = f"Subunit {sub_org}: {sub_name}"
                ev_id = f"ev-loc-{orgnr}-{sub_org}"
                ev = make_evidence(
                    ev_id,
                    source_url=loc_ev.get("source_url") or f"https://data.brreg.no/enhetsregisteret/api/underenheter?overordnetEnhet={orgnr}",
                    retrieved_at=loc_ev.get("retrieved_at") or now,
                    content_sha256=sha,
                    snapshot_ref=snap_ref,
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

    # 5. Group structure
    grp_ev = evidences.get("group")
    if grp_ev and grp_ev.get("status") == "available":
        grp_val = grp_ev.get("value") or {}
        parent = grp_val.get("morselskap") or grp_val.get("overordnetEnhet")
        sub_list = grp_val.get("datterselskaper") or []
        if parent or sub_list:
            grp_snap = f"Konsernstruktur for {orgnr}:\n{json.dumps(grp_val, ensure_ascii=False)}"
            sha, snap_ref = store_snapshot(snapshots_dir, grp_snap)
            span_text = f"Konsernstruktur for {orgnr}"
            ev_id = f"ev-grp-{orgnr}"
            ev = make_evidence(
                ev_id,
                source_url=grp_ev.get("source_url") or f"https://data.brreg.no/enhetsregisteret/api/konsernstruktur/{orgnr}",
                retrieved_at=grp_ev.get("retrieved_at") or now,
                content_sha256=sha,
                snapshot_ref=snap_ref,
                claim_span=span_text,
                source_class="official_group_structure",
            )
            if parent:
                c_parent = make_claim(
                    claim_key(orgnr, "parent_entity", str(parent)),
                    field="parent_entity",
                    family="group",
                    value=parent,
                    evidence_ids=[ev["id"]],
                    source_class="official_group_structure",
                    method="konsern_api",
                )
                add_claim(env, c_parent, [ev])
            for sub in sub_list:
                sub_id = str(sub.get("organisasjonsnummer") if isinstance(sub, dict) else sub)
                c_sub = make_claim(
                    claim_key(orgnr, "subsidiary", sub_id),
                    field="subsidiary",
                    family="group",
                    value=sub,
                    evidence_ids=[ev["id"]],
                    source_class="official_group_structure",
                    method="konsern_api",
                )
                add_claim(env, c_sub, [ev])
        else:
            set_field_state(env, "group", "not_available", "no_group_structure_returned")
    elif grp_ev and grp_ev.get("status") in {"not_found", "not_applicable"}:
        set_field_state(env, "group", "not_available", "not_in_group")
    elif grp_ev and grp_ev.get("status") == "source_error":
        set_field_state(env, "group", "failed", "source_error")

    # 6. Accounts History
    hist_ev = evidences.get("financial_history")
    if hist_ev and hist_ev.get("status") == "available":
        hist_val = hist_ev.get("value") or {}
        years = hist_val.get("years") or []
        if years:
            hist_snap = f"Regnskapshistorikk for {orgnr}: {', '.join(years)}\n{json.dumps(hist_val, ensure_ascii=False)}"
            sha, snap_ref = store_snapshot(snapshots_dir, hist_snap)
            span_text = f"Regnskapshistorikk for {orgnr}: {', '.join(years)}"
            ev_id = f"ev-hist-{orgnr}"
            ev = make_evidence(
                ev_id,
                source_url=hist_ev.get("source_url") or f"https://data.brreg.no/regnskapsregisteret/regnskap/{orgnr}/aar",
                retrieved_at=hist_ev.get("retrieved_at") or now,
                content_sha256=sha,
                snapshot_ref=snap_ref,
                claim_span=span_text,
                source_class="official_annual_account_copies",
            )
            c_hist = make_claim(
                claim_key(orgnr, "available_filing_years"),
                field="available_filing_years",
                family="accounts_history",
                value=years,
                evidence_ids=[ev["id"]],
                source_class="official_annual_account_copies",
                method="regnskap_aar_api",
                reporting_period={"from": f"{years[0]}-01-01", "to": f"{years[-1]}-12-31"},
            )
            add_claim(env, c_hist, [ev])
        else:
            set_field_state(env, "accounts_history", "not_available", "no_history_years_returned")
    elif hist_ev and hist_ev.get("status") in {"not_found", "not_applicable"}:
        set_field_state(env, "accounts_history", "not_available", "no_history_returned")
    elif hist_ev and hist_ev.get("status") == "source_error":
        set_field_state(env, "accounts_history", "failed", "source_error")

    # 7. Website & Brand
    web_ev = evidences.get("website")
    if web_ev and web_ev.get("status") == "available":
        web_val = web_ev.get("value") or {}
        homepage = web_val.get("final_url") or profile.get("website")
        span_text = web_val.get("claim_span") or f"Org.nr. {orgnr}"
        proof_lvl = web_val.get("proof_level") or "orgnr_exact"
        method_str = web_val.get("strategy") or "exact_proof"
        page_html = web_val.get("page_html")
        page_text = web_val.get("page_text") or ""

        if page_html:
            snap_content = f"{page_html}\n\n<!-- SIGNALPOST_EXTRACTED_TEXT -->\n{page_text}" if page_text else page_html
            norm_span = re.sub(r"\s+", " ", span_text).strip()
            norm_snap = re.sub(r"\s+", " ", snap_content).strip()
            if norm_span not in norm_snap:
                if orgnr in snap_content:
                    idx = snap_content.find(orgnr)
                    span_text = snap_content[max(0, idx - 30): min(len(snap_content), idx + 40)]
                elif profile.get("name") and profile["name"] in snap_content:
                    idx = snap_content.find(profile["name"])
                    span_text = snap_content[idx: min(len(snap_content), idx + len(profile["name"]))]
            sha, snap_ref = store_snapshot(snapshots_dir, snap_content)
        else:
            web_snap = f"Official website: {homepage}\n{span_text}\n{web_val.get('text_sample') or ''}"
            sha, snap_ref = store_snapshot(snapshots_dir, web_snap)

        ev_id = f"ev-web-{orgnr}"
        ev = make_evidence(
            ev_id,
            source_url=web_ev.get("source_url") or homepage,
            final_url=homepage,
            retrieved_at=web_ev.get("retrieved_at") or now,
            content_sha256=sha,
            snapshot_ref=snap_ref,
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
            method=method_str,
            identity_proof=proof_lvl,
        )
        add_claim(env, c, [ev])

        brand_name = web_val.get("brand_name")
        if brand_name:
            c_brand = make_claim(
                claim_key(orgnr, "public_brand"),
                field="public_brand",
                family="brand",
                value=brand_name,
                evidence_ids=[ev["id"]],
                source_class="company_owned",
                method="html_meta",
            )
            add_claim(env, c_brand, [ev])
    elif web_ev and web_ev.get("status") in {"not_found", "not_applicable", "not_available"}:
        set_field_state(env, "website", "not_available", web_ev.get("note") or "no_verified_website")
    elif web_ev and web_ev.get("status") == "ambiguous":
        set_field_state(env, "website", "ambiguous", web_ev.get("note") or "conflicting_proof_candidates")
    elif web_ev and web_ev.get("status") == "blocked":
        set_field_state(env, "website", "blocked", "robots_denied")

    # 8. Set remaining families to not_available or not_checked
    for fam in FAMILIES:
        if env["field_states"][fam]["availability"] == "failed" and env["field_states"][fam]["reason"] == "not_checked":
            set_field_state(env, fam, "not_available", "checked_nothing_found")

    # 9. Record operations metrics
    metrics = profile.get("run_metrics") or {}
    env["operations"] = {
        "requests": metrics.get("requests", 0),
        "runtime_ms": int(sum(metrics.get("latencies_ms", []))),
        "third_party_cost_usd": 0.0,
    }

    # Keep legacy profile dict for backwards compatibility
    env["profile"] = profile
    return finalize(env)
