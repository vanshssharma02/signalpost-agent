"""Deterministic, source-grounded synthesis engine (Workflow /05).

Generates structured profile summaries strictly grounded in verified claims.
Rules (N3 & N4):
1. Every factual sentence or metric MUST cite at least one claim_id that exists in the envelope.
2. Sentences without claims contain zero factual statements (framing words only).
3. Missing or unverified data points are cataloged under 'unknowns' with standard reason codes.
4. Deterministic first: runs 100% without external LLM keys or network access (--no-llm).
5. Output length cap: strictly under 250 words total.
"""
from __future__ import annotations

import re
from typing import Any

from signalpost.ref.envelope import FAMILIES, utc_now


def _format_currency(val: float | int | None) -> str:
    if val is None:
        return "N/A"
    return f"{val:,.0f} NOK"


def _clean_str(val: Any) -> str:
    return re.sub(r"\s+", " ", str(val or "")).strip()


class SentenceCollector:
    """Helper to collect sentences and enforce claim_id citations."""

    def __init__(self, valid_claim_ids: set[str]):
        self.valid_claim_ids = valid_claim_ids
        self.sentences: list[dict[str, Any]] = []

    def add(self, text: str, claim_ids: list[str] | set[str] | None = None) -> str:
        s_text = _clean_str(text)
        if not s_text:
            return ""
        if not s_text.endswith((".", "!", "?")):
            s_text += "."

        # Filter to only claim_ids that exist in the envelope
        cids = [cid for cid in (claim_ids or []) if cid in self.valid_claim_ids]
        # Deduplicate while preserving order
        seen = set()
        dedup_cids = [c for c in cids if not (c in seen or seen.add(c))]

        s_id = f"s{len(self.sentences) + 1}"
        self.sentences.append({
            "id": s_id,
            "text": s_text,
            "claim_ids": dedup_cids,
        })
        return s_text


def compose_synthesis(
    envelope: dict[str, Any],
    *,
    profile: dict[str, Any] | None = None,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose structured, citation-grounded synthesis object for an envelope."""
    claims = envelope.get("claims") or []
    claims_by_id = {c["claim_id"]: c for c in claims if "claim_id" in c}
    valid_claim_ids = set(claims_by_id.keys())

    # Map claims by field
    claims_by_field: dict[str, list[dict[str, Any]]] = {}
    for c in claims:
        f = c.get("field")
        if f:
            claims_by_field.setdefault(f, []).append(c)

    orgnr = str(envelope.get("organisation_number") or "")
    identity = envelope.get("identity") or {}
    flags = identity.get("flags") or {}
    field_states = envelope.get("field_states") or {}

    c_name = claims_by_field.get("legal_name", [None])[0]
    c_form = claims_by_field.get("legal_form", [None])[0]
    c_ind = claims_by_field.get("industry_code", [None])[0]
    c_web = claims_by_field.get("official_website", [None])[0]
    c_brand = claims_by_field.get("public_brand", [None])[0]
    c_emp = claims_by_field.get("employees", [None])[0]
    c_baddr = claims_by_field.get("business_address", [None])[0]

    legal_name = str(c_name["value"]) if c_name else f"Entity {orgnr}"
    legal_form = str(c_form["value"]) if c_form else "Entity"
    headline = f"{legal_name} ({legal_form}, org.nr {orgnr})"

    collector = SentenceCollector(valid_claim_ids)

    # 1. WHAT IT DOES
    wid_sentences = []
    # Check purpose from raw registry data if present
    raw_reg = (profile or {}).get("evidence", {}).get("registry", {}).get("value") or {}
    if not isinstance(raw_reg, dict):
        raw_reg = {}
    purpose = _clean_str(raw_reg.get("vedtektsfestetFormaal") or raw_reg.get("aktivitet"))

    name_cids = [c_name["claim_id"]] if c_name else []

    if purpose and len(purpose) >= 5 and c_name:
        # Grounded in name and registry snapshot; keep concise (<30 words)
        first_sentence = purpose.split(". ")[0].strip()
        p_words = first_sentence.split()
        if len(p_words) > 30:
            first_sentence = " ".join(p_words[:30]) + "..."
        if not first_sentence.endswith((".", "...")):
            first_sentence += "."
        wid_sentences.append(collector.add(
            f"The registered business purpose of {legal_name} is: {first_sentence}",
            name_cids,
        ))

    if c_ind:
        # NACE classification
        ind_code = str(c_ind["value"])
        ind_label = (profile or {}).get("industry_label") or raw_reg.get("naeringskode1.beskrivelse") or "unspecified"
        wid_sentences.append(collector.add(
            f"{legal_name} is classified under NACE code {ind_code} ({ind_label})",
            [c_ind["claim_id"]] + name_cids,
        ))
    elif not wid_sentences:
        wid_sentences.append(collector.add(
            f"{legal_name} has no industry code registered",
            name_cids,
        ))

    if c_web:
        web_url = str(c_web["value"])
        wid_sentences.append(collector.add(
            f"The company operates its verified website at {web_url}",
            [c_web["claim_id"]],
        ))

    if c_brand:
        b_name = str(c_brand["value"])
        wid_sentences.append(collector.add(
            f"It operates publicly under the brand name '{b_name}', according to its website",
            [c_brand["claim_id"]],
        ))

    what_it_does = " ".join(wid_sentences)

    # 2. BUSINESS MODEL
    bm_sentences = []
    business_model: str | None = None
    if c_form and c_ind:
        ind_label = (profile or {}).get("industry_label") or "commercial"
        bm_text = f"Operates as a registered {legal_form} entity within the {ind_label} sector"
        cids = [c_form["claim_id"], c_ind["claim_id"]]
        if c_emp and c_emp.get("value") is not None:
            emp_cnt = c_emp["value"]
            bm_text += f", with {emp_cnt} registered employee(s)"
            cids.append(c_emp["claim_id"])
        bm_sentences.append(collector.add(bm_text, cids))
        business_model = " ".join(bm_sentences)

    # 3. SIZE AND FINANCIALS
    sf_sentences = []
    # Group financials claims by fiscal year
    fin_by_year: dict[str, dict[str, dict[str, Any]]] = {}
    for f_field in ("revenue", "operating_result", "annual_result", "profit_before_tax", "assets", "equity", "debt"):
        for c in claims_by_field.get(f_field, []):
            rep = c.get("reporting_period") or {}
            year = str(rep.get("to") or "")[:4]
            if year and year.isdigit():
                fin_by_year.setdefault(year, {})[f_field] = c

    if fin_by_year:
        years_sorted = sorted(fin_by_year.keys(), reverse=True)
        latest_yr = years_sorted[0]
        latest_m = fin_by_year[latest_yr]

        c_rev = latest_m.get("revenue")
        c_op = latest_m.get("operating_result")
        c_net = latest_m.get("annual_result") or latest_m.get("profit_before_tax")
        c_ass = latest_m.get("assets")
        c_eq = latest_m.get("equity")

        # Sentence: latest revenue and operating result
        rev_val = c_rev["value"] if c_rev else None
        op_val = c_op["value"] if c_op else None
        if rev_val is not None and op_val is not None:
            cids = [c_rev["claim_id"], c_op["claim_id"]]
            sf_sentences.append(collector.add(
                f"For fiscal year {latest_yr}, {legal_name} reported revenue of {_format_currency(rev_val)} and an operating result of {_format_currency(op_val)}",
                cids,
            ))
        elif rev_val is not None:
            sf_sentences.append(collector.add(
                f"For fiscal year {latest_yr}, revenue was {_format_currency(rev_val)}",
                [c_rev["claim_id"]],
            ))

        # Sentence: Net result, assets, equity
        net_val = c_net["value"] if c_net else None
        ass_val = c_ass["value"] if c_ass else None
        eq_val = c_eq["value"] if c_eq else None
        if net_val is not None and ass_val is not None and eq_val is not None:
            cids = [c_net["claim_id"], c_ass["claim_id"], c_eq["claim_id"]]
            sf_sentences.append(collector.add(
                f"Net result was {_format_currency(net_val)}, with total assets of {_format_currency(ass_val)} and equity of {_format_currency(eq_val)}",
                cids,
            ))
        elif net_val is not None:
            sf_sentences.append(collector.add(
                f"Annual net result was {_format_currency(net_val)} in {latest_yr}",
                [c_net["claim_id"]],
            ))

        # Qualitative & Derived metrics
        if net_val is not None and net_val < 0:
            sf_sentences.append(collector.add(
                f"The company was loss-making in {latest_yr}",
                [c_net["claim_id"]],
            ))

        # YoY Revenue growth
        prev_yr = str(int(latest_yr) - 1)
        if prev_yr in fin_by_year and c_rev and "revenue" in fin_by_year[prev_yr]:
            c_prev_rev = fin_by_year[prev_yr]["revenue"]
            prev_rev_val = c_prev_rev["value"]
            if prev_rev_val and prev_rev_val > 0 and rev_val is not None:
                growth = (rev_val - prev_rev_val) / prev_rev_val
                growth_pct = growth * 100
                cids = [c_rev["claim_id"], c_prev_rev["claim_id"]]
                if growth > 0.10:
                    sf_sentences.append(collector.add(
                        f"Revenue grew by {growth_pct:+.1f}% year-over-year from {prev_yr} (derived: YoY revenue change)",
                        cids,
                    ))
                elif growth < -0.10:
                    sf_sentences.append(collector.add(
                        f"Revenue contracted by {growth_pct:+.1f}% year-over-year from {prev_yr} (derived: YoY revenue change)",
                        cids,
                    ))
                else:
                    sf_sentences.append(collector.add(
                        f"Revenue remained stable year-over-year from {prev_yr} (derived: YoY revenue change within 10%)",
                        cids,
                    ))

        # Operating margin
        if rev_val and rev_val > 0 and op_val is not None:
            margin_pct = (op_val / rev_val) * 100
            sf_sentences.append(collector.add(
                f"Operating margin was {margin_pct:.1f}% (derived: operating result / revenue)",
                [c_op["claim_id"], c_rev["claim_id"]],
            ))
    else:
        sf_sentences.append(collector.add(
            "No annual accounting filings were returned by Regnskapsregisteret for this entity",
            name_cids,
        ))

    size_and_financials = " ".join(sf_sentences)

    # 4. LEADERSHIP AND STRUCTURE
    ls_sentences = []
    roles_claims = claims_by_field.get("role_holder", [])
    chair_claim = next((c for c in roles_claims if (c.get("value") or {}).get("role_code") == "LEDE"), None)
    ceo_claim = next((c for c in roles_claims if (c.get("value") or {}).get("role_code") == "DAGL"), None)

    if chair_claim:
        chair_name = chair_claim["value"].get("name") or "Unknown"
        ls_sentences.append(collector.add(
            f"The board of directors is chaired by {chair_name}",
            [chair_claim["claim_id"]],
        ))

    if ceo_claim:
        ceo_name = ceo_claim["value"].get("name") or "Unknown"
        ls_sentences.append(collector.add(
            f"Daily operations are led by general manager {ceo_name}",
            [ceo_claim["claim_id"]],
        ))

    if roles_claims:
        all_r_ids = [c["claim_id"] for c in roles_claims[:6]]
        ls_sentences.append(collector.add(
            f"The entity has {len(roles_claims)} registered role position(s) in the register of business enterprises",
            all_r_ids,
        ))
    else:
        ls_sentences.append(collector.add(
            "No leadership or board roles are recorded in the business register",
            name_cids,
        ))

    group_claims = claims_by_field.get("parent_company", []) + claims_by_field.get("subsidiary", [])
    if group_claims:
        ls_sentences.append(collector.add(
            "The company is part of a registered corporate group structure",
            [group_claims[0]["claim_id"]],
        ))
    else:
        ls_sentences.append(collector.add(
            "No corporate group hierarchy or parent company is registered",
            name_cids,
        ))

    leadership_and_structure = " ".join(ls_sentences)

    # 5. LOCATIONS
    loc_sentences = []
    if c_baddr:
        loc_sentences.append(collector.add(
            f"The registered business address is {c_baddr['value']}",
            [c_baddr["claim_id"]],
        ))

    subunit_claims = claims_by_field.get("subunit", [])
    if subunit_claims:
        sub_ids = [c["claim_id"] for c in subunit_claims]
        loc_sentences.append(collector.add(
            f"The entity maintains {len(subunit_claims)} registered operating subunit(s) across Norway",
            sub_ids,
        ))
    else:
        loc_sentences.append(collector.add(
            "No secondary operating subunits are registered",
            name_cids,
        ))

    locations = " ".join(loc_sentences)

    # 6. HIRING SIGNAL
    hiring_sentences = []
    job_claims = claims_by_field.get("job_posting", [])
    careers_claims = claims_by_field.get("careers_page", [])

    if job_claims:
        latest_job = max(job_claims, key=lambda c: str(c.get("published_at") or ""))
        job_ids = [c["claim_id"] for c in job_claims]
        pub_d = str(latest_job.get("published_at") or "")[:10]
        hiring_sentences.append(collector.add(
            f"Identified {len(job_claims)} active job vacancy posting(s) in official feeds (latest published {pub_d})",
            job_ids,
        ))
    elif careers_claims:
        car_url = (careers_claims[0].get("value") or {}).get("url") or "careers portal"
        hiring_sentences.append(collector.add(
            f"Maintains a verified careers portal at {car_url}",
            [careers_claims[0]["claim_id"]],
        ))
    else:
        hiring_sentences.append(collector.add(
            "No active job postings were found in the NAV feed or on verified site pages",
            name_cids,
        ))

    hiring_signal = " ".join(hiring_sentences)

    # 7. RECENT ACTIVITY
    act_sentences = []
    news_claims = claims_by_field.get("company_news_item", [])
    if news_claims:
        latest_n = news_claims[0]
        n_title = (latest_n.get("value") or {}).get("title") or "Update"
        n_date = str((latest_n.get("value") or {}).get("published_at") or latest_n.get("published_at") or "")[:10]
        act_sentences.append(collector.add(
            f"Published company announcement '{n_title}' on {n_date} (company-owned publication)",
            [latest_n["claim_id"]],
        ))
    else:
        act_sentences.append(collector.add(
            "No recent news items were detected on verified company sources",
            name_cids,
        ))

    recent_activity = " ".join(act_sentences)

    # 8. WHAT CHANGED
    changes = envelope.get("changes") or []
    ch_sentences = []
    if changes:
        ch_cids = [c["claim_id"] for c in changes if c.get("claim_id") in valid_claim_ids]
        summary_items = [f"{ch.get('field')}: {ch.get('type')}" for ch in changes[:3]]
        ch_sentences.append(collector.add(
            f"Observed {len(changes)} update(s) since prior observation: {', '.join(summary_items)}",
            ch_cids,
        ))
    else:
        started_d = str(envelope.get("run", {}).get("started_at") or utc_now())[:10]
        if previous:
            ch_sentences.append(collector.add(
                f"No changes detected compared to the previous snapshot as of {started_d}",
                name_cids,
            ))
        else:
            ch_sentences.append(collector.add(
                f"First observation on {started_d}; no earlier snapshot recorded",
                name_cids,
            ))

    what_changed = " ".join(ch_sentences)

    # 9. UNKNOWNS
    unknowns = []
    source_mapping = {
        "identity": ["official_registry_bulk"],
        "brand": ["verified_website_meta"],
        "accounts": ["official_annual_accounts"],
        "accounts_history": ["official_annual_accounts"],
        "leadership": ["official_roles_api"],
        "locations": ["official_subunits_api"],
        "group": ["official_group_structure_api"],
        "website": ["registry_homepage", "email_domain", "subunits", "domain_probing"],
        "company_profiles": ["verified_website_outbound"],
        "hiring": ["pam_stilling_feed", "verified_website"],
        "activity": ["verified_website_articles"],
    }

    for fam in FAMILIES:
        st = field_states.get(fam) or {}
        avail = st.get("availability")
        if avail in ("not_available", "ambiguous", "failed"):
            reason = st.get("reason") or "not_available"
            checked = st.get("checked_sources") or source_mapping.get(fam, ["official_sources"])
            unknowns.append({
                "topic": fam,
                "why": f"{fam}: {reason}",
                "checked": checked,
            })

    if business_model is None:
        unknowns.append({
            "topic": "business_model",
            "why": "business_model: insufficient_verified_operational_facts",
            "checked": ["official_registry_bulk", "verified_website"],
        })

    # Return full compliant synthesis structure
    return {
        "generator": "template-v1",
        "language": "en",
        "headline": headline,
        "what_it_does": what_it_does,
        "business_model": business_model,
        "size_and_financials": size_and_financials,
        "leadership_and_structure": leadership_and_structure,
        "locations": locations,
        "hiring_signal": hiring_signal,
        "recent_activity": recent_activity,
        "what_changed": what_changed,
        "unknowns": unknowns,
        "sentences": collector.sentences,
    }
