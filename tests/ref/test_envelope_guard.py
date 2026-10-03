import asyncio, json, time
from pathlib import Path

from signalpost.ref.envelope import (STATES, FAMILIES, new_envelope, make_claim, make_evidence, add_claim,
                                     set_field_state, finalize, failure_envelope, sha256_hex, utc_now)
from signalpost.ref.guard import parse_inputs, Deadline, EnvelopeWriter, run_batch
from signalpost.ref.validate import validate_envelopes, compare_runs
from signalpost.ref.claims import claim_key

A, B, C = "985821585", "988077917", "923609016"   # first two are mod-11 valid public examples
RUN = {"run_id": "t1", "started_at": utc_now()}


def good_env(org):
    env = new_envelope(org, RUN)
    html = f"<footer>Org.nr. {org}</footer>"
    ev = make_evidence("ev-1", source_url="https://example.no/", retrieved_at=utc_now(), content_sha256=sha256_hex(html),
                       claim_span=f"Org.nr. {org}", source_class="company_owned", extractor="t")
    add_claim(env, make_claim(claim_key(org, "official_website"), "official_website", "website", "https://example.no/", ["ev-1"],
                              source_class="company_owned", method="orgnr_on_page", identity_proof="orgnr_exact"), [ev])
    for fam in FAMILIES:
        if env["field_states"][fam]["availability"] != "available":
            set_field_state(env, fam, "not_available", "checked_nothing_found")
    return finalize(env)


def test_parse_inputs_shapes():
    txt = f"{A}\n985 821 585\nabc\n{B}\n"
    rows = parse_inputs(txt)
    assert [r.problem for r in rows] == [None, "duplicate", "malformed", None]
    assert [r.orgnr for r in parse_inputs(json.dumps([A, {"organisation_number": B}, int(C)]))] == [A, B, C]
    assert [r.orgnr for r in parse_inputs(json.dumps({"organisation_numbers": [A, B]}))] == [A, B]
    jl = f'"{A}"\n{{"orgnr":"{B}","name":"x"}}\n{{"foo":"bar"}}\n'
    assert [r.problem for r in parse_inputs(jl)] == [None, None, "malformed"]
    assert parse_inputs("\ufeff" + A)[0].orgnr == A
    assert parse_inputs("") == []


def test_envelope_states_and_status():
    env = good_env(A)
    assert env["status"] == "available" and env["availability"] == "available" and env["state"] == "complete"
    empty = new_envelope(A, RUN)
    for fam in FAMILIES:
        set_field_state(empty, fam, "not_available", "checked_nothing_found")
    assert finalize(empty)["status"] == "not_available"
    deleted = new_envelope(A, RUN)
    deleted["identity"]["flags"] = {"deleted": True}
    assert finalize(deleted)["status"] == "not_applicable"
    f = failure_envelope("notanumber", RUN, "malformed_input", "x")
    assert f["status"] == "failed" and f["errors"][0]["code"] == "malformed_input"
    assert all(s in STATES for s in (f["status"], *[v["availability"] for v in f["field_states"].values()]))


def test_validator_accepts_good_and_catches_bad():
    envs = [good_env(A), good_env(B)]
    rep = validate_envelopes(envs, [A, B])
    assert rep["passed"], rep["errors"]
    assert not validate_envelopes(envs[:1], [A, B])["passed"]                      # missing row
    bad = good_env(C); bad["claims"][0]["evidence_ids"] = ["ev-404"]
    assert not validate_envelopes([bad], [C])["passed"]                             # dangling evidence
    bad2 = good_env(C); bad2["evidence"][0]["content_sha256"] = "xyz"
    assert not validate_envelopes([bad2], [C])["passed"]                            # bad hash
    bad3 = good_env(C); bad3["status"] = "complete"
    assert not validate_envelopes([bad3], [C])["passed"]                            # not a six-state value


def test_period_and_zero_rules():
    env = new_envelope(A, RUN)
    ev = make_evidence("ev-1", source_url="https://data.brreg.no/x", retrieved_at=utc_now(), content_sha256=sha256_hex("a"),
                       claim_span='"sumDriftsinntekter": 1200', source_class="official_registry")
    add_claim(env, make_claim("c1", "revenue", "accounts", 1200, ["ev-1"], source_class="official_registry", method="regnskap_api"), [ev])
    for fam in FAMILIES:
        if env["field_states"][fam]["availability"] != "available":
            set_field_state(env, fam, "not_available", "x")
    finalize(env)
    assert any("reporting_period" in e for e in validate_envelopes([env], [A])["errors"])
    env["claims"][0]["reporting_period"] = {"from": "2025-01-01", "to": "2025-12-31"}
    assert validate_envelopes([env], [A])["passed"]
    env["claims"][0]["value"] = 0
    assert not validate_envelopes([env], [A])["passed"]                             # 0 not backed by a standalone-zero span
    env["evidence"][0]["claim_span"] = '"sumDriftsinntekter": 0'
    assert validate_envelopes([env], [A])["passed"]                                 # a reported zero is fine


def test_snapshot_span_check(tmp_path):
    import gzip
    body = "<p>Org.nr. 985821585</p>"
    sha = sha256_hex(body)
    snap = tmp_path / "snapshots" / sha[:2]; snap.mkdir(parents=True)
    (snap / f"{sha}.gz").write_bytes(gzip.compress(body.encode()))
    env = good_env(A)
    env["evidence"][0].update({"content_sha256": sha, "snapshot_ref": f"{sha[:2]}/{sha}.gz", "claim_span": "Org.nr. 985821585"})
    assert validate_envelopes([env], [A], tmp_path / "snapshots")["spans_checked"] == 1
    env["evidence"][0]["claim_span"] = "Org.nr. 111111111"
    assert not validate_envelopes([env], [A], tmp_path / "snapshots")["passed"]


def test_batch_never_loses_a_row(tmp_path):
    orgs = [f"9{str(i).zfill(8)}" for i in range(1, 11)]

    async def worker(org, deadline):
        i = int(org[1:])
        if i == 3:
            raise RuntimeError("boom")
        if i == 5:
            await asyncio.sleep(60)                     # hangs
        if i == 7:
            return {"not": "an envelope"}
        await asyncio.sleep(0.01)
        return good_env(org)

    writer = EnvelopeWriter(tmp_path / "out.jsonl")
    rep = asyncio.run(run_batch(orgs, worker, writer, run=RUN, deadline=Deadline(5), concurrency=4, per_company_timeout=0.3))
    n = writer.finalize(orgs, lambda o: failure_envelope(o, RUN, "missing", "x"))
    lines = [json.loads(l) for l in (tmp_path / "out.jsonl").read_text().splitlines()]
    assert n == 10 and [l["organisation_number"] for l in lines] == orgs                   # 1:1 and in input order
    codes = {l["organisation_number"]: (l["errors"][0]["code"] if l["errors"] else None) for l in lines}
    assert codes[orgs[2]] == "worker_exception" and codes[orgs[4]] == "company_timeout" and codes[orgs[6]] == "bad_worker_output"
    assert rep["status_counts"]["available"] == 7 and rep["status_counts"]["failed"] == 3
    assert validate_envelopes(lines, orgs)["passed"]


def test_global_deadline_finalises_everything(tmp_path):
    orgs = [f"9{str(i).zfill(8)}" for i in range(1, 41)]

    async def slow(org, deadline):
        await asyncio.sleep(0.25)
        return good_env(org)

    writer = EnvelopeWriter(tmp_path / "o.jsonl")
    t0 = time.monotonic()
    rep = asyncio.run(run_batch(orgs, slow, writer, run=RUN, deadline=Deadline(1.0, hard=0.6), concurrency=4, per_company_timeout=5))
    elapsed = time.monotonic() - t0
    writer.finalize(orgs, lambda o: failure_envelope(o, RUN, "missing", "x"))
    lines = [json.loads(l) for l in (tmp_path / "o.jsonl").read_text().splitlines()]
    assert len(lines) == 40 and elapsed < 1.4                                              # watchdog held the line
    assert rep["status_counts"].get("available", 0) >= 4 and rep["error_codes"].get("time_budget", 0) >= 1


def test_resume_skips_finished_rows(tmp_path):
    orgs = [A, B]
    w1 = EnvelopeWriter(tmp_path / "r.jsonl"); w1.write(good_env(A)); w1._handle.close()
    calls = []

    async def worker(org, deadline):
        calls.append(org); return good_env(org)

    w2 = EnvelopeWriter(tmp_path / "r.jsonl")
    asyncio.run(run_batch(orgs, worker, w2, run=RUN, deadline=Deadline(5)))
    assert calls == [B] and w2.done() == {A, B}


def test_idempotent_compare():
    one, two = [good_env(A)], [good_env(A)]
    two[0]["claims"][0]["first_observed_at"] = one[0]["claims"][0]["first_observed_at"]
    assert compare_runs(one, two)["idempotent"]
    two[0]["claims"][0]["value"] = "https://other.no/"
    assert not compare_runs(one, two)["idempotent"]
