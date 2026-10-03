"""Fault-injection tests for the Signalpost runner and envelope pipeline (all offline fixtures)."""
from __future__ import annotations

import asyncio
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from signalpost.ref.envelope import (
    FAMILIES,
    STATES,
    failure_envelope,
    finalize,
    make_claim,
    make_evidence,
    new_envelope,
    sha256_hex,
    utc_now,
)
from signalpost.ref.guard import Deadline, EnvelopeWriter, parse_inputs, run_batch
from signalpost.ref.validate import compare_runs, validate_envelopes
from signalpost.run import run_batch_process
from norway_company_agent.website import assert_public_url


A, B, C = "985821585", "988077917", "923609016"
RUN = {"run_id": "test-run", "started_at": utc_now()}


def make_dummy_envelope(org: str) -> dict:
    env = new_envelope(org, RUN)
    html = f"<footer>Org.nr. {org}</footer>"
    ev = make_evidence(
        f"ev-{org}",
        source_url="https://example.no/",
        retrieved_at=utc_now(),
        content_sha256=sha256_hex(html),
        claim_span=f"Org.nr. {org}",
        source_class="company_owned",
    )
    make_c = make_claim(
        f"c-{org}",
        "official_website",
        "website",
        "https://example.no/",
        [ev["id"]],
        source_class="company_owned",
        method="orgnr_exact",
        identity_proof="orgnr_exact",
    )
    from signalpost.ref.envelope import add_claim, set_field_state
    add_claim(env, make_c, [ev])
    for f in FAMILIES:
        if env["field_states"][f]["availability"] != "available":
            set_field_state(env, f, "not_available", "checked_nothing_found")
    return finalize(env)


def test_chaos_input_parsing():
    raw_chaos = "\ufeff\n  \n985821585\n985821585\n\"12345678\"\nsome-junk-text\n988077917\n"
    rows = parse_inputs(raw_chaos)
    assert len(rows) == 5
    assert rows[0].orgnr == "985821585" and rows[0].problem is None
    assert rows[1].orgnr == "985821585" and rows[1].problem == "duplicate"
    assert rows[2].problem == "malformed"
    assert rows[3].problem == "malformed"
    assert rows[4].orgnr == "988077917" and rows[4].problem is None


def test_chaos_input_runner_never_raises(tmp_path):
    input_file = tmp_path / "chaos.txt"
    input_file.write_text("\ufeff\n985821585\n985821585\n12345678\nsome-junk\n988077917\n", encoding="utf-8")
    out_file = tmp_path / "out.jsonl"
    report_file = tmp_path / "report.json"

    report = asyncio.run(
        run_batch_process(
            input_file.read_text(encoding="utf-8"),
            bulk_path=None,
            output_path=out_file,
            report_path=report_file,
            offline=True,
            time_budget_s=10.0,
        )
    )
    lines = [json.loads(line) for line in out_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    # Should have 1 envelope for first 985821585, 2 for malformed, 1 for 988077917 = 4 total (duplicate deduplicated)
    assert len(lines) == 4
    for env in lines:
        assert env["status"] in STATES
        assert env["availability"] in STATES


def test_worker_faults_isolated(tmp_path):
    orgs = [f"9{str(i).zfill(8)}" for i in range(1, 11)]

    async def faulty_worker(org: str, deadline: Deadline) -> dict:
        idx = int(org[1:])
        if idx == 2:
            raise RuntimeError("unexpected explosion")
        if idx == 4:
            await asyncio.sleep(20)  # hang
        if idx == 6:
            return {"not": "an envelope"}
        return make_dummy_envelope(org)

    writer = EnvelopeWriter(tmp_path / "faulty_out.jsonl")
    rep = asyncio.run(
        run_batch(
            orgs,
            faulty_worker,
            writer,
            run=RUN,
            deadline=Deadline(5.0),
            concurrency=4,
            per_company_timeout=0.2,
        )
    )
    writer.finalize(orgs, lambda o: failure_envelope(o, RUN, "missing", "x"))
    lines = [json.loads(line) for line in (tmp_path / "faulty_out.jsonl").read_text().splitlines()]
    assert len(lines) == 10
    statuses = {l["organisation_number"]: l["status"] for l in lines}
    assert statuses[orgs[1]] == "failed"
    assert statuses[orgs[3]] == "failed"
    assert statuses[orgs[5]] == "failed"
    assert statuses[orgs[0]] == "available"


def test_tiny_budget_watchdog(tmp_path):
    orgs = [f"9{str(i).zfill(8)}" for i in range(1, 51)]

    async def slow_worker(org: str, deadline: Deadline) -> dict:
        await asyncio.sleep(0.1)
        return make_dummy_envelope(org)

    writer = EnvelopeWriter(tmp_path / "budget_out.jsonl")
    t0 = time.monotonic()
    rep = asyncio.run(
        run_batch(
            orgs,
            slow_worker,
            writer,
            run=RUN,
            deadline=Deadline(0.3, hard=0.5),
            concurrency=2,
            per_company_timeout=1.0,
        )
    )
    elapsed = time.monotonic() - t0
    writer.finalize(orgs, lambda o: failure_envelope(o, RUN, "time_budget", "time budget exhausted"))
    lines = [json.loads(line) for line in (tmp_path / "budget_out.jsonl").read_text().splitlines()]
    assert len(lines) == 50
    assert elapsed < 1.0


def test_resume_does_not_repeat_finished(tmp_path):
    out_file = tmp_path / "resume_out.jsonl"
    writer = EnvelopeWriter(out_file)
    writer.write(make_dummy_envelope(A))
    writer._handle.close()

    executed = []

    async def tracking_worker(org: str, deadline: Deadline) -> dict:
        executed.append(org)
        return make_dummy_envelope(org)

    w2 = EnvelopeWriter(out_file)
    asyncio.run(run_batch([A, B], tracking_worker, w2, run=RUN, deadline=Deadline(5.0)))
    assert executed == [B]
    assert w2.done() == {A, B}


def test_ssrf_private_network_refused():
    for target in ("http://127.0.0.1", "http://localhost", "http://10.0.0.1", "http://192.168.1.1"):
        with pytest.raises(ValueError):
            assert_public_url(target)


def test_runs_idempotent():
    first = [make_dummy_envelope(A), make_dummy_envelope(B)]
    second = [make_dummy_envelope(A), make_dummy_envelope(B)]
    for i in range(2):
        second[i]["claims"][0]["first_observed_at"] = first[i]["claims"][0]["first_observed_at"]
    cmp = compare_runs(first, second)
    assert cmp["idempotent"]
