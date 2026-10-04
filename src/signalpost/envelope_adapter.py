"""Module for building compliant terminal envelopes matching OUTPUT_CONTRACT.md and signalpost_ref schema."""
from __future__ import annotations

import gzip
import hashlib
import json
import re
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Iterable

from signalpost.ref.claims import canonical, claim_key
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
    stringify_keys,
    utc_now,
)
from signalpost.synthesis import compose_synthesis


def _determine_change_type(field: str, action: str) -> str:
    """Map field and action to standardized change type enum (Workflow /05)."""
    if action == "removed":
        if field == "role_holder":
            return "role_ended"
        if field == "subunit":
            return "location_closed"
        if field == "job_posting":
            return "closed_job"
        return "status_changed"
    if action == "added":
        if field in ("revenue", "operating_result", "annual_result", "profit_before_tax", "assets", "equity", "debt"):
            return "new_filing"
        if field == "role_holder":
            return "new_role"
        if field == "subunit":
            return "new_location"
        if field == "job_posting":
            return "new_job"
        if field == "official_website":
            return "new_website"
        if field == "company_news_item":
            return "news_item_added"
        if field == "company_profile":
            return "profile_added"
        return "description_changed"
    # action == "changed"
    if field == "official_website":
        return "website_changed"
    if field == "role_holder":
        return "new_role"
    if field in ("revenue", "operating_result", "annual_result"):
        return "new_filing"
    return "description_changed"



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
    previous_env: dict | None = None,
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

    # 8. Hiring (NAV jobs & Site Careers)
    nav_jobs = evidences.get("nav_jobs") or []
    site_careers = evidences.get("site_careers") or []
    hiring_claims_added = False

    for job in nav_jobs:
        if isinstance(job, dict):
            j_uuid = job["uuid"]
            j_title = job["title"]
            j_emp_name = job["employer_name"]
            j_orgnr = job["employer_orgnr"]
            j_pub = job["published"]
            j_exp = job.get("expires")
            j_loc = job.get("location")
            j_extent = job.get("extent")
            j_eng = job.get("engagement_type")
            j_url = job.get("source_ad_url")
            j_snap = job.get("snapshot_json")
            j_span = job.get("claim_span")
        else:
            j_uuid = job.uuid
            j_title = job.title
            j_emp_name = job.employer_name
            j_orgnr = job.employer_orgnr
            j_pub = job.published
            j_exp = job.expires
            j_loc = job.location
            j_extent = job.extent
            j_eng = job.engagement_type
            j_url = job.source_ad_url
            j_snap = job.snapshot_json
            j_span = job.claim_span

        sha, snap_ref = store_snapshot(snapshots_dir, j_snap)
        ev_id = f"ev-nav-{orgnr}-{j_uuid[:8]}"
        ev = make_evidence(
            ev_id,
            source_url=j_url,
            retrieved_at=now,
            content_sha256=sha,
            snapshot_ref=snap_ref,
            claim_span=j_span,
            source_class="public_platform_api",
        )
        rep_period = {"from": j_pub[:10], "to": j_exp[:10]} if j_exp else {"from": j_pub[:10], "to": j_pub[:10]}
        c = make_claim(
            claim_key(orgnr, "job_posting", j_uuid),
            field="job_posting",
            family="hiring",
            value={
                "title": j_title,
                "employer_name": j_emp_name,
                "location": j_loc,
                "extent": j_extent,
                "engagement_type": j_eng,
                "published": j_pub,
                "expires": j_exp,
                "source_ad_url": j_url,
            },
            evidence_ids=[ev["id"]],
            source_class="public_platform_api",
            method="nav_pam_feed",
            identity_proof="orgnr_exact",
            published_at=j_pub,
            reporting_period=rep_period,
        )
        add_claim(env, c, [ev])
        hiring_claims_added = True

    for car in site_careers:
        c_title = car["title"] if isinstance(car, dict) else car.title
        c_url = car["url"] if isinstance(car, dict) else car.url
        c_is_job = car["is_job_posting"] if isinstance(car, dict) else car.is_job_posting
        c_pub = car["published_at"] if isinstance(car, dict) else car.published_at
        c_exp = car["expires_at"] if isinstance(car, dict) else car.expires_at
        c_span = car["claim_span"] if isinstance(car, dict) else car.claim_span

        web_snap = evidences.get("website", {}).get("value", {}).get("page_html") or c_span
        norm_span = re.sub(r"\s+", " ", c_span or "").strip()
        norm_snap = re.sub(r"\s+", " ", web_snap or "").strip()
        if not norm_span or norm_span not in norm_snap:
            c_span = c_title if (c_title and c_title in web_snap) else (norm_snap[:50] if len(norm_snap) >= 5 else "karriere")
        sha, snap_ref = store_snapshot(snapshots_dir, web_snap)
        car_id = hashlib.sha256(c_url.encode("utf-8")).hexdigest()[:8]
        ev_id = f"ev-career-{orgnr}-{car_id}"
        ev = make_evidence(
            ev_id,
            source_url=c_url,
            retrieved_at=now,
            content_sha256=sha,
            snapshot_ref=snap_ref,
            claim_span=c_span,
            source_class="company_owned",
        )
        field_name = "job_posting" if c_is_job else "careers_page"
        iso_pub = c_pub or now
        c = make_claim(
            claim_key(orgnr, field_name, car_id),
            field=field_name,
            family="hiring",
            value={"title": c_title, "url": c_url, "published_at": iso_pub},
            evidence_ids=[ev["id"]],
            source_class="company_owned",
            method="html_site_careers",
            identity_proof="site_verified",
            published_at=iso_pub,
        )
        add_claim(env, c, [ev])
        hiring_claims_added = True

    if not hiring_claims_added:
        set_field_state(env, "hiring", "not_available", "none_in_nav_feed_or_site")

    # 9. Activity (Company News Items)
    site_news = evidences.get("site_news") or []
    activity_claims_added = False

    for news in site_news:
        n_title = news["title"] if isinstance(news, dict) else news.title
        n_url = news["url"] if isinstance(news, dict) else news.url
        n_pub = news["published_at"] if isinstance(news, dict) else news.published_at
        n_span = news["claim_span"] if isinstance(news, dict) else news.claim_span
        n_src = news.get("source_type", "html") if isinstance(news, dict) else news.source_type

        web_snap = evidences.get("website", {}).get("value", {}).get("page_html") or n_span
        norm_span = re.sub(r"\s+", " ", n_span or "").strip()
        norm_snap = re.sub(r"\s+", " ", web_snap or "").strip()
        if not norm_span or norm_span not in norm_snap:
            n_span = n_title if (n_title and n_title in web_snap) else (norm_snap[:50] if len(norm_snap) >= 5 else "nyheter")
        sha, snap_ref = store_snapshot(snapshots_dir, web_snap)
        news_id = hashlib.sha256(n_url.encode("utf-8")).hexdigest()[:8]
        ev_id = f"ev-news-{orgnr}-{news_id}"
        ev = make_evidence(
            ev_id,
            source_url=n_url,
            retrieved_at=now,
            content_sha256=sha,
            snapshot_ref=snap_ref,
            claim_span=n_span,
            source_class="company_owned",
        )
        c = make_claim(
            claim_key(orgnr, "company_news_item", news_id),
            field="company_news_item",
            family="activity",
            value={"title": n_title, "url": n_url, "published_at": n_pub},
            evidence_ids=[ev["id"]],
            source_class="company_owned",
            method=n_src,
            identity_proof="site_verified",
            published_at=n_pub,
        )
        add_claim(env, c, [ev])
        activity_claims_added = True

    if not activity_claims_added:
        set_field_state(env, "activity", "not_available", "no_news_items_detected")

    # 10. Company Profiles (Outbound Social Profiles)
    site_profs = evidences.get("site_profiles") or []
    profiles_claims_added = False

    for prof in site_profs:
        p_plat = prof["platform"] if isinstance(prof, dict) else prof.platform
        p_url = prof["url"] if isinstance(prof, dict) else prof.url
        p_span = prof["claim_span"] if isinstance(prof, dict) else prof.claim_span

        web_snap = evidences.get("website", {}).get("value", {}).get("page_html") or p_span
        norm_span = re.sub(r"\s+", " ", p_span or "").strip()
        norm_snap = re.sub(r"\s+", " ", web_snap or "").strip()
        if not norm_span or norm_span not in norm_snap:
            p_span = p_plat if (p_plat and p_plat in web_snap) else (norm_snap[:50] if len(norm_snap) >= 5 else p_plat)
        sha, snap_ref = store_snapshot(snapshots_dir, web_snap)
        prof_id = f"{p_plat}-{hashlib.sha256(p_url.encode('utf-8')).hexdigest()[:6]}"
        ev_id = f"ev-prof-{orgnr}-{prof_id}"
        ev = make_evidence(
            ev_id,
            source_url=p_url,
            retrieved_at=now,
            content_sha256=sha,
            snapshot_ref=snap_ref,
            claim_span=p_span,
            source_class="company_owned",
        )
        c = make_claim(
            claim_key(orgnr, "company_profile", p_plat),
            field="company_profile",
            family="company_profiles",
            value={"platform": p_plat, "url": p_url},
            evidence_ids=[ev["id"]],
            source_class="company_owned",
            method="verified_site_outbound",
            identity_proof="site_verified",
        )
        add_claim(env, c, [ev])
        profiles_claims_added = True

    if not profiles_claims_added:
        set_field_state(env, "company_profiles", "not_available", "no_profiles_detected")

    # 11. Set remaining families to not_available or not_checked
    for fam in FAMILIES:
        if env["field_states"][fam]["availability"] == "failed" and env["field_states"][fam]["reason"] == "not_checked":
            set_field_state(env, fam, "not_available", "checked_nothing_found")

    # Operations metrics
    metrics = profile.get("run_metrics") or {}
    env["operations"] = {
        "requests": metrics.get("requests", 0),
        "runtime_ms": int(sum(metrics.get("latencies_ms", []))),
        "third_party_cost_usd": 0.0,
    }

    # 11. Differential claim merge with previous observation (Workflow /05)
    if previous_env:
        prev_claims = {c["claim_id"]: c for c in previous_env.get("claims", []) if "claim_id" in c}
        current_claim_ids = set()

        for c in env["claims"]:
            cid = c["claim_id"]
            current_claim_ids.add(cid)
            if cid in prev_claims:
                old_c = prev_claims[cid]
                # Preserve stable first_observed_at
                c["first_observed_at"] = old_c.get("first_observed_at") or old_c.get("last_verified_at") or now
                c["last_verified_at"] = now
                if canonical(old_c.get("value")) != canonical(c.get("value")):
                    # Material change detected
                    ch_type = _determine_change_type(c["field"], "changed")
                    old_ev = (old_c.get("evidence_ids") or [None])[0]
                    new_ev = (c.get("evidence_ids") or [None])[0]
                    env["changes"].append({
                        "type": ch_type,
                        "orgnr": orgnr,
                        "field": c["field"],
                        "claim_id": cid,
                        "old": old_c.get("value"),
                        "new": c.get("value"),
                        "old_evidence_id": old_ev,
                        "new_evidence_id": new_ev,
                        "detected_at": now,
                        "material": True,
                    })
            else:
                # New claim observed
                c["first_observed_at"] = now
                c["last_verified_at"] = now
                ch_type = _determine_change_type(c["field"], "added")
                new_ev = (c.get("evidence_ids") or [None])[0]
                env["changes"].append({
                    "type": ch_type,
                    "orgnr": orgnr,
                    "field": c["field"],
                    "claim_id": cid,
                    "old": None,
                    "new": c.get("value"),
                    "old_evidence_id": None,
                    "new_evidence_id": new_ev,
                    "detected_at": now,
                    "material": True,
                })

        # Check for claims present in previous but missing in current
        for old_cid, old_c in prev_claims.items():
            if old_cid not in current_claim_ids:
                fam = old_c.get("family", "")
                st = env["field_states"].get(fam, {})
                if st.get("availability") in ("available", "not_available"):
                    # Family was successfully checked, so this claim ended
                    ch_type = _determine_change_type(old_c["field"], "removed")
                    old_ev = (old_c.get("evidence_ids") or [None])[0]
                    env["changes"].append({
                        "type": ch_type,
                        "orgnr": orgnr,
                        "field": old_c["field"],
                        "claim_id": old_cid,
                        "old": old_c.get("value"),
                        "new": None,
                        "old_evidence_id": old_ev,
                        "new_evidence_id": None,
                        "detected_at": now,
                        "material": True,
                    })
                else:
                    # Family check failed or was not completed: KEEP last supported claim!
                    env["claims"].append(old_c)

    # 12. Structured source-grounded synthesis (Workflow /05)
    env["synthesis"] = compose_synthesis(env, profile=profile, previous=previous_env)

    def _to_json_safe(obj: Any) -> Any:
        if is_dataclass(obj) and not isinstance(obj, type):
            return asdict(obj)
        if isinstance(obj, dict):
            return {str(k): _to_json_safe(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple, set)):
            return [_to_json_safe(v) for v in obj]
        return obj

    # Keep legacy profile dict for backwards compatibility
    env["profile"] = _to_json_safe(profile)
    return finalize(stringify_keys(env))
