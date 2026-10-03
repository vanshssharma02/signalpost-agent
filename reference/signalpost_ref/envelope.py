"""Terminal result envelope: a SUPERSET of Builderr's OUTPUT_CONTRACT.md plus the legacy
starter keys (state / modules / profile), so either reader finds what it expects.

Six states only: available, not_available, blocked, not_applicable, ambiguous, failed.
Missing is never zero; a family that was never checked is `failed` (reason `not_checked`),
which is different from a family that was checked and found empty (`not_available`).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Iterable

SCHEMA_VERSION = "signalpost-envelope/1"
STATES = ("available", "not_available", "blocked", "not_applicable", "ambiguous", "failed")
FAMILIES = (
    "identity", "brand", "accounts", "accounts_history", "leadership", "locations",
    "group", "website", "company_profiles", "hiring", "activity",
)
LEGACY_STATE = {"available": "complete", "not_available": "not_found", "blocked": "blocked_policy",
                "not_applicable": "not_applicable", "ambiguous": "not_found", "failed": "source_error"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha256_hex(data: bytes | str) -> str:
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def dumps(env: dict) -> str:
    return json.dumps(env, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def make_evidence(ev_id: str, *, source_url: str, retrieved_at: str, content_sha256: str, claim_span: str,
                  source_class: str, http_status: int | None = 200, final_url: str | None = None,
                  snapshot_ref: str | None = None, span_locator: dict | None = None,
                  published_at: str | None = None, reporting_period: dict | None = None,
                  extractor: str = "", extractor_version: str = "1") -> dict:
    return {
        "id": ev_id, "source_url": source_url, "final_url": final_url or source_url, "http_status": http_status,
        "source_class": source_class, "retrieved_at": retrieved_at, "content_sha256": content_sha256,
        "snapshot_ref": snapshot_ref, "claim_span": (claim_span or "")[:500], "span_locator": span_locator,
        "published_at": published_at, "reporting_period": reporting_period,
        "extractor": extractor, "extractor_version": extractor_version,
    }


def make_claim(claim_id: str, field: str, family: str, value: Any, evidence_ids: Iterable[str], *,
               source_class: str, method: str, availability: str = "available", confidence: float = 1.0,
               reporting_period: dict | None = None, published_at: str | None = None,
               identity_proof: str | None = None, derived_from: Iterable[str] | None = None,
               now: str | None = None) -> dict:
    assert availability in STATES and family in FAMILIES
    now = now or utc_now()
    claim = {
        "claim_id": claim_id, "field": field, "family": family, "value": value, "availability": availability,
        "confidence": confidence, "evidence_ids": list(evidence_ids), "source_class": source_class,
        "method": method, "reporting_period": reporting_period, "published_at": published_at,
        "identity_proof": identity_proof, "first_observed_at": now, "last_verified_at": now,
    }
    if derived_from:
        claim["derived_from"] = list(derived_from)
    return claim


def new_envelope(orgnr: str, run: dict) -> dict:
    return {
        "schema_version": SCHEMA_VERSION, "organisation_number": orgnr,
        "status": "failed", "availability": "failed", "status_reason": "not_finalized",
        "run": {**run, "terminal_status": "completed"},
        "identity": {"claim_ids": []},
        "field_states": {f: {"availability": "failed", "reason": "not_checked", "checked_sources": [], "claim_ids": []}
                         for f in FAMILIES},
        "claims": [], "evidence": [], "synthesis": None, "changes": [], "errors": [],
        "operations": {"requests": 0, "runtime_ms": 0, "third_party_cost_usd": 0},
    }


def set_field_state(env: dict, family: str, availability: str, reason: str, *,
                    checked_sources: Iterable[str] = (), claim_ids: Iterable[str] = ()) -> None:
    assert availability in STATES and family in FAMILIES
    state = env["field_states"][family]
    state.update({"availability": availability, "reason": reason})
    state["checked_sources"] = sorted(set(state.get("checked_sources", [])) | set(checked_sources))
    state["claim_ids"] = sorted(set(state.get("claim_ids", [])) | set(claim_ids))


def add_claim(env: dict, claim: dict, evidences: Iterable[dict]) -> None:
    """Append a claim with its evidence; the family becomes `available`. Duplicate claim_ids are ignored."""
    if any(c["claim_id"] == claim["claim_id"] for c in env["claims"]):
        return
    have = {e["id"] for e in env["evidence"]}
    for ev in evidences:
        if ev["id"] not in have:
            env["evidence"].append(ev)
            have.add(ev["id"])
    env["claims"].append(claim)
    set_field_state(env, claim["family"], "available", "verified", claim_ids=[claim["claim_id"]])


def add_error(env: dict, code: str, message: str, *, stage: str, retryable: bool = False) -> None:
    env["errors"].append({"code": code, "message": str(message)[:300], "stage": stage, "retryable": retryable})


def derive_status(env: dict) -> tuple[str, str]:
    """Company-level terminal state (confirm exact semantics with Builderr)."""
    flags = (env.get("identity") or {}).get("flags") or {}
    if flags.get("deleted") or flags.get("bankrupt") or flags.get("liquidating"):
        return "not_applicable", "entity_deleted_or_in_insolvency_process"
    if env.get("run", {}).get("terminal_status") == "failed":
        return "failed", "run_failed_for_company"
    if any(c["availability"] == "available" for c in env["claims"]):
        return "available", "verified_claims_present"
    states = {s["availability"] for s in env["field_states"].values()}
    if "blocked" in states:
        return "blocked", "sources_refused"
    if states == {"failed"} or "failed" in states and "not_available" not in states:
        return "failed", "no_family_completed"
    return "not_available", "checked_nothing_found"


def finalize(env: dict, *, now: str | None = None) -> dict:
    env["run"]["completed_at"] = now or utc_now()
    status, reason = derive_status(env)
    env["status"], env["availability"], env["status_reason"] = status, status, reason
    env["claims"].sort(key=lambda c: (c["family"], c["field"], c["claim_id"]))
    env["evidence"].sort(key=lambda e: e["id"])
    # legacy starter keys (kept so older readers do not break)
    env["state"] = LEGACY_STATE[status]
    env.setdefault("modules", {})
    env.setdefault("profile", {})
    return env


def failure_envelope(orgnr: Any, run: dict, code: str, message: str, *, stage: str = "batch") -> dict:
    """Used for malformed input, worker crashes, per-company timeouts and global-deadline fallbacks."""
    env = new_envelope(str(orgnr), run)
    env["run"]["terminal_status"] = "failed"
    for fam in FAMILIES:
        set_field_state(env, fam, "failed", code)
    add_error(env, code, message, stage=stage, retryable=code in {"company_timeout", "time_budget", "worker_exception"})
    return finalize(env)
