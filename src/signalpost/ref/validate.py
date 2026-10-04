"""Contract validator: run it on every output before you believe a score.
    python -m signalpost_ref.validate --input batch.jsonl --output out/envelopes.jsonl [--snapshots out/snapshots]
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from .envelope import FAMILIES, STATES, stringify_keys
from .guard import parse_inputs

HEX64 = re.compile(r"^[0-9a-f]{64}$")
STANDALONE_ZERO = re.compile(r"(?<![\d.,])0(?:[.,]0+)?(?![\d])")
NEEDS_PERIOD = {"accounts", "accounts_history"}
NEEDS_DATE = {"hiring", "activity"}
TOP_KEYS = ("organisation_number", "status", "run", "claims", "evidence", "changes", "errors", "operations", "field_states")


def _iso(value) -> bool:
    try:
        datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _snapshot_text(snapshots: Path | None, ev: dict) -> str | None:
    if not snapshots or not ev.get("snapshot_ref"):
        return None
    for candidate in (snapshots / ev["snapshot_ref"], snapshots.parent / ev["snapshot_ref"]):
        if candidate.exists():
            raw = gzip.open(candidate, "rb").read() if candidate.suffix == ".gz" else candidate.read_bytes()
            return raw.decode("utf-8", "replace")
    return None


def validate_envelopes(envs: list[dict], expected: list[str], snapshots: Path | None = None) -> dict:
    errors: list[str] = []
    orgs = [e.get("organisation_number") for e in envs]
    if len(envs) != len(expected):
        errors.append(f"count mismatch: {len(envs)} envelopes for {len(expected)} inputs")
    if len(set(orgs)) != len(orgs):
        errors.append("duplicate organisation_number in output")
    missing = [o for o in expected if o not in set(orgs)]
    if missing:
        errors.append(f"missing envelopes for {len(missing)} inputs, e.g. {missing[:3]}")
    if orgs != [o for o in expected if o in set(orgs)]:
        errors.append("output order differs from input order (not fatal, but keep it stable)")
    checked_spans = bad_spans = 0
    for env in envs:
        org = env.get("organisation_number")
        for key in TOP_KEYS:
            if key not in env:
                errors.append(f"{org}: missing top-level key {key}")
        if env.get("status") not in STATES or env.get("availability") not in STATES:
            errors.append(f"{org}: invalid terminal status {env.get('status')!r}")
        evs = {e["id"]: e for e in env.get("evidence", [])}
        ids = [c.get("claim_id") for c in env.get("claims", [])]
        if len(ids) != len(set(ids)):
            errors.append(f"{org}: duplicate claim_id")
        for fam, st in (env.get("field_states") or {}).items():
            if fam not in FAMILIES or st.get("availability") not in STATES:
                errors.append(f"{org}: bad field_state {fam}")
        for c in env.get("claims", []):
            if c.get("availability") not in STATES:
                errors.append(f"{org}/{c.get('field')}: bad availability")
                continue
            if c["availability"] != "available":
                continue
            if c.get("value") is None:
                errors.append(f"{org}/{c['field']}: available claim without value")
            if not c.get("evidence_ids"):
                errors.append(f"{org}/{c['field']}: no evidence")
            if c["family"] in NEEDS_PERIOD and not c.get("reporting_period"):
                errors.append(f"{org}/{c['field']}: missing reporting_period")
            if c["family"] in NEEDS_DATE and not (c.get("published_at") or c.get("reporting_period")):
                errors.append(f"{org}/{c['field']}: missing published_at/reporting_period")
            for ev_id in c.get("evidence_ids", []):
                ev = evs.get(ev_id)
                if not ev:
                    errors.append(f"{org}/{c['field']}: dangling evidence id {ev_id}")
                    continue
                if not str(ev.get("source_url", "")).startswith(("http://", "https://")):
                    errors.append(f"{org}/{ev_id}: bad source_url")
                if not _iso(ev.get("retrieved_at")):
                    errors.append(f"{org}/{ev_id}: bad retrieved_at")
                if not HEX64.match(str(ev.get("content_sha256", ""))):
                    errors.append(f"{org}/{ev_id}: bad content_sha256")
                if not _norm(ev.get("claim_span", "")):
                    errors.append(f"{org}/{ev_id}: empty claim_span")
                text = _snapshot_text(snapshots, ev)
                if text is not None:
                    checked_spans += 1
                    if _norm(ev["claim_span"]) not in _norm(text):
                        bad_spans += 1
                        errors.append(f"{org}/{ev_id}: claim_span not found in snapshot")
            if isinstance(c.get("value"), (int, float)) and c["value"] == 0 and c["family"] in NEEDS_PERIOD:
                span = " ".join(evs.get(i, {}).get("claim_span", "") for i in c["evidence_ids"])
                if not STANDALONE_ZERO.search(span):
                    errors.append(f"{org}/{c['field']}: zero value not backed by a source span (missing != 0)")
    return {"passed": not [e for e in errors if "not fatal" not in e], "envelopes": len(envs), "expected": len(expected),
            "spans_checked": checked_spans, "spans_bad": bad_spans, "errors": errors[:200], "error_count": len(errors)}


def compare_runs(first: list[dict], second: list[dict]) -> dict:
    """Idempotency: identical sources => same claim ids and values, no change events, first_observed_at kept."""
    problems: list[str] = []
    a = {e["organisation_number"]: e for e in first}
    b = {e["organisation_number"]: e for e in second}
    if set(a) != set(b):
        problems.append("different organisation sets")
    for org in sorted(set(a) & set(b)):
        ca = {c["claim_id"]: c for c in a[org]["claims"]}
        cb = {c["claim_id"]: c for c in b[org]["claims"]}
        if set(ca) != set(cb):
            problems.append(f"{org}: claim id sets differ")
        for cid in set(ca) & set(cb):
            if ca[cid]["value"] != cb[cid]["value"]:
                problems.append(f"{org}/{cid}: value changed without source change")
            if ca[cid]["first_observed_at"] != cb[cid]["first_observed_at"]:
                problems.append(f"{org}/{cid}: first_observed_at moved")
        if b[org].get("changes"):
            problems.append(f"{org}: false change events {len(b[org]['changes'])}")
    return {"idempotent": not problems, "problems": problems[:100]}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--snapshots")
    args = p.parse_args()
    expected = [r.orgnr for r in parse_inputs(Path(args.input).read_text(encoding="utf-8")) if r.orgnr and not r.problem]
    envs = [json.loads(line) for line in Path(args.output).read_text(encoding="utf-8").splitlines() if line.strip()]
    report = validate_envelopes(envs, expected, Path(args.snapshots) if args.snapshots else None)
    print(json.dumps(stringify_keys(report), indent=2, ensure_ascii=False, sort_keys=True))
    sys.exit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
