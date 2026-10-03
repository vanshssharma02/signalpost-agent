"""Main batch runner and entry point for Signalpost."""
from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import logging
import os
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from norway_company_agent.http import FetchResult
from norway_company_agent.identity import apply_website_identity_gate
from norway_company_agent.official import (
    accounting_obligation_assessment,
    fetch_official_modules,
    normalize_entity,
)
from norway_company_agent.sampling import iter_bulk
from norway_company_agent.website import fetch_website
from signalpost.envelope_adapter import profile_to_envelope
from signalpost.ref.envelope import FAMILIES, STATES, failure_envelope, finalize, utc_now
from signalpost.ref.guard import Deadline, EnvelopeWriter, InputRow, parse_inputs
from signalpost.ref.validate import validate_envelopes

logger = logging.getLogger("signalpost")


def load_bulk_subset(path: str | Path, target_orgs: set[str]) -> tuple[dict[str, dict], dict[str, Any]]:
    """Scan bulk CSV or CSV.GZ and extract matching profiles without raising if some are missing."""
    p = Path(path)
    if not p.exists():
        return {}, {"error": f"bulk file {path} not found"}
    snapshot_sha256 = hashlib.sha256(p.read_bytes()).hexdigest()
    found: dict[str, dict[str, Any]] = {}
    scanned = 0
    now = utc_now()
    for profile in iter_bulk(path):
        scanned += 1
        org = profile.get("organisation_number")
        if org in target_orgs:
            raw = profile.pop("raw", {})
            profile["evidence"] = {
                "registry": {
                    "field": "registry",
                    "status": "available",
                    "source_type": "official_registry_bulk",
                    "source_class": "official_registry_bulk",
                    "source_url": "https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv",
                    "value": raw,
                    "retrieved_at": now,
                    "content_sha256": snapshot_sha256,
                    "source_row_key": org,
                },
                "accounting_obligation": accounting_obligation_assessment(profile),
            }
            found[org] = profile
            if len(found) == len(target_orgs):
                break
    return found, {
        "registry_snapshot_sha256": snapshot_sha256,
        "registry_rows_scanned": scanned,
        "requested": len(target_orgs),
        "found": len(found),
    }


def make_run_metadata(run_id: str, started_at: str, strategy_set: str = "default") -> dict[str, Any]:
    return {
        "run_id": run_id,
        "started_at": started_at,
        "terminal_status": "completed",
        "agent": {
            "name": "signalpost",
            "version": "0.2.0",
            "git_commit": "phase-02",
        },
        "strategy_set": strategy_set,
    }


async def run_batch_process(
    input_text: str,
    *,
    bulk_path: str | Path | None,
    output_path: str | Path,
    report_path: str | Path,
    snapshots_dir: str | Path = "out/snapshots",
    run_id: str | None = None,
    time_budget_s: float = 1500.0,
    expected_count: int | None = None,
    concurrency: int = 16,
    offline: bool = False,
    resume: bool = False,
) -> dict[str, Any]:
    started_at = utc_now()
    run_id = run_id or f"run-{started_at.replace(':', '').replace('-', '')}"
    run_meta = make_run_metadata(run_id, started_at)
    deadline = Deadline(time_budget_s)

    input_rows = parse_inputs(input_text)
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    partial_path = out_path.with_name(out_path.name + ".partial")
    if not resume and partial_path.exists():
        partial_path.unlink()

    writer = EnvelopeWriter(out_path)

    # Identify unique valid orgnrs, duplicates, and malformed entries
    valid_orgs_ordered: list[str] = []
    order_all: list[str] = []
    duplicates: list[str] = []
    malformed: list[Any] = []
    annotations: dict[str, dict] = {}

    for row in input_rows:
        if row.problem == "malformed":
            raw_str = str(row.raw)
            order_all.append(raw_str)
            malformed.append(row.raw)
            # Write immediate failure envelope for malformed input using raw value
            writer.write(failure_envelope(raw_str, run_meta, "malformed_input", f"Invalid input row: {row.raw!r}", stage="input"))
        elif row.problem == "duplicate":
            duplicates.append(row.orgnr or str(row.raw))
            # Duplicates produce no second envelope
        else:
            org = row.orgnr
            assert org is not None
            order_all.append(org)
            valid_orgs_ordered.append(org)
            if isinstance(row.raw, dict):
                annotations[org] = {k: v for k, v in row.raw.items() if k in ("evaluation_split", "sample_slice")}

    # Pre-load bulk profiles if available
    bulk_profiles: dict[str, dict] = {}
    bulk_meta: dict[str, Any] = {}
    if bulk_path and Path(bulk_path).exists():
        bulk_profiles, bulk_meta = load_bulk_subset(bulk_path, set(valid_orgs_ordered))

    # Async worker for a single organisation
    async def worker(org: str, d: Deadline) -> dict[str, Any]:
        loop = asyncio.get_running_loop()

        # Check bulk first
        profile = copy.deepcopy(bulk_profiles.get(org))
        if profile is None:
            # Look up live if not offline
            if offline:
                env = failure_envelope(org, run_meta, "absent_from_registry", "Org absent from bulk snapshot in offline mode", stage="registry")
                env["status"] = "not_available"
                env["availability"] = "not_available"
                env["status_reason"] = "absent_from_registry"
                return env
            # Fetch live
            def fetch_live():
                return fetch_official_modules(org, {"registry_live"})
            records, _ = await loop.run_in_executor(None, fetch_live)
            reg_live = records.get("registry_live", {})
            if reg_live.get("status") in {"not_found", "not_applicable"}:
                env = failure_envelope(org, run_meta, "absent_from_registry", f"Registry API returned {reg_live.get('status')}", stage="registry")
                env["status"] = reg_live["status"]
                env["availability"] = reg_live["status"]
                env["status_reason"] = "absent_from_registry"
                return env
            val = reg_live.get("value") or {}
            profile = {
                "organisation_number": org,
                "name": val.get("name"),
                "legal_form": val.get("legal_form"),
                "employees": val.get("employees"),
                "website": val.get("website"),
                "evidence": {"registry": reg_live},
            }

        # Apply annotations
        if org in annotations:
            profile.update(annotations[org])

        # If online and time permits, enrich with accounts, roles, subunits, group, website
        if not offline and not d.soft_passed():
            modules_to_fetch = {"financials", "roles", "locations", "group"}
            def fetch_more():
                records, metrics = fetch_official_modules(org, modules_to_fetch)
                if profile.get("website"):
                    try:
                        web_record, web_metrics = fetch_website(profile.get("website"))
                        gated = apply_website_identity_gate(profile, web_record)
                        records["website"] = gated["website"]
                        metrics.append(FetchResult(
                            url=profile["website"],
                            status=web_record.get("status", 200),
                            elapsed_ms=sum(web_metrics.get("latencies_ms", [])),
                            bytes_received=web_metrics.get("bytes", 0),
                        ))
                    except Exception as e:
                        logger.warning("Error fetching website for %s: %s", org, e)
                return records, metrics
            records, metrics = await loop.run_in_executor(None, fetch_more)
            profile.setdefault("evidence", {}).update(records)
            profile["run_metrics"] = {
                "requests": len(metrics),
                "latencies_ms": [m.elapsed_ms for m in metrics],
            }

        return profile_to_envelope(profile, run=run_meta, snapshots_dir=snapshots_dir)

    # Filter tasks to those not already completed (resume support)
    pending_orgs = [o for o in valid_orgs_ordered if o not in writer.done()]
    sem = asyncio.Semaphore(concurrency)
    timings: list[float] = []

    async def run_one(org: str):
        async with sem:
            t0 = time.monotonic()
            if deadline.hard_passed():
                writer.write(failure_envelope(org, run_meta, "time_budget", "Global deadline exceeded", stage="scheduler"))
                return
            limit = max(0.05, min(90.0, deadline.remaining_to_hard()))
            try:
                env = await asyncio.wait_for(worker(org, deadline), timeout=limit)
            except asyncio.TimeoutError:
                code = "time_budget" if deadline.hard_passed() else "company_timeout"
                env = failure_envelope(org, run_meta, code, f"Timeout after {limit:.1f}s", stage="scheduler")
            except Exception as exc:
                env = failure_envelope(org, run_meta, "worker_exception", f"{type(exc).__name__}: {exc}", stage="worker")
            if not isinstance(env, dict) or env.get("organisation_number") != org:
                env = failure_envelope(org, run_meta, "bad_worker_output", "Worker returned invalid output", stage="worker")
            writer.write(env)
            timings.append(time.monotonic() - t0)

    await asyncio.gather(*(run_one(o) for o in pending_orgs))

    # Finalize writer in original order
    writer.finalize(order_all, lambda o: failure_envelope(o, run_meta, "missing", "Not finalized", stage="scheduler"))

    # Read finalized envelopes
    final_envelopes = [writer.envelopes[k] for k in order_all if k in writer.envelopes]

    # Validate against expected inputs
    expected_org_list = [o for o in valid_orgs_ordered]
    validation = validate_envelopes(final_envelopes, expected_org_list, Path(snapshots_dir) if snapshots_dir else None)

    warnings = []
    if expected_count is not None and len(order_all) != expected_count:
        warnings.append(f"Expected count {expected_count} differed from input count {len(order_all)}")

    status_counts = dict(Counter(e.get("status") for e in final_envelopes))
    report = {
        "run_id": run_id,
        "started_at": started_at,
        "completed_at": utc_now(),
        "expected_count": expected_count,
        "total_inputs": len(input_rows),
        "emitted_envelopes": len(final_envelopes),
        "duplicates": duplicates,
        "malformed": malformed,
        "warnings": warnings,
        "status_counts": status_counts,
        "p50_s": round(statistics.median(timings), 3) if timings else None,
        "p95_s": round(sorted(timings)[int(0.95 * (len(timings) - 1))], 3) if timings else None,
        "validation": validation,
    }

    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Signalpost autonomous Norwegian company research runner")
    parser.add_argument("--organisations", "--input", "-i", dest="input", required=True, help="Input file path")
    parser.add_argument("--bulk", default=os.environ.get("SIGNALPOST_BULK"), help="Path to Brreg bulk file")
    parser.add_argument("--output", "-o", default="out/envelopes.jsonl", help="Output envelopes JSONL file")
    parser.add_argument("--profiles-output", default="out/profiles.jsonl", help="Output profiles JSONL file")
    parser.add_argument("--report", default="out/run-report.json", help="Output run report JSON file")
    parser.add_argument("--run-id", default=None, help="Unique run ID")
    parser.add_argument("--expected-count", type=int, default=None, help="Expected count (warning only)")
    parser.add_argument("--previous", help="Earlier envelopes directory or file for refresh")
    parser.add_argument("--snapshots-dir", default="out/snapshots", help="Directory for stored snapshots")
    parser.add_argument(
        "--time-budget",
        type=float,
        default=float(os.environ.get("SIGNALPOST_TIME_BUDGET_S", 1500.0)),
        help="Total time budget in seconds",
    )
    parser.add_argument("--workers", type=int, default=16, help="Worker concurrency")
    parser.add_argument("--resume", action="store_true", help="Resume from partial progress")
    parser.add_argument("--no-llm", action="store_true", help="Disable LLM calls")
    parser.add_argument("--strategies", default="config/strategies.toml", help="Path to strategies.toml")
    parser.add_argument("--offline", action="store_true", help="Offline mode (no network)")
    return parser


def main() -> None:
    parser = build_cli_parser()
    args, unknown = parser.parse_known_args()
    if unknown:
        print(f"Warning: ignoring unknown arguments: {unknown}", file=sys.stderr)

    input_text = Path(args.input).read_text(encoding="utf-8")
    report = asyncio.run(
        run_batch_process(
            input_text,
            bulk_path=args.bulk,
            output_path=args.output,
            report_path=args.report,
            snapshots_dir=args.snapshots_dir,
            run_id=args.run_id,
            time_budget_s=args.time_budget,
            expected_count=args.expected_count,
            concurrency=args.workers,
            offline=args.offline,
            resume=args.resume,
        )
    )
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["validation"]["passed"] else 1)


if __name__ == "__main__":
    main()
