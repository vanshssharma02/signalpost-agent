"""Never lose a row: tolerant input parsing, deadline watchdog, append-only writer, bounded batch runner."""
from __future__ import annotations

import asyncio
import json
import os
import re
import statistics
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from .envelope import dumps, failure_envelope, stringify_keys
from .orgnr import normalize

KEYS = ("organisation_number", "organisasjonsnummer", "organization_number", "orgnr", "org_nr", "orgNumber", "id")


@dataclass
class InputRow:
    index: int
    raw: Any
    orgnr: str | None
    problem: str | None = None  # None | "malformed" | "duplicate"


def _extract(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in KEYS:
            if key in value and value[key] is not None:
                return _extract(value[key])
        for v in value.values():
            hit = _extract(v) if isinstance(v, (str, int)) else None
            if hit:
                return hit
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return normalize(str(value).zfill(9))
    if isinstance(value, str):
        direct = normalize(value)
        if direct:
            return direct
        match = re.search(r"(?<!\d)(\d{3})[ .]?(\d{3})[ .]?(\d{3})(?!\d)", value)
        return "".join(match.groups()) if match else None
    return None


def parse_inputs(text: str) -> list[InputRow]:
    """JSON array, {"organisation_numbers": [...]}, JSONL of strings/objects, or plain text lines."""
    text = text.lstrip("\ufeff").strip()
    items: list[Any] = []
    parsed = None
    if text[:1] in "[{":
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
    if isinstance(parsed, list):
        items = parsed
    elif isinstance(parsed, dict):
        listed = next((parsed[k] for k in ("organisation_numbers", "organisations", "companies", "items") if isinstance(parsed.get(k), list)), None)
        items = listed if listed is not None else [parsed]
    else:
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                items.append(line)
    rows: list[InputRow] = []
    seen: set[str] = set()
    for index, raw in enumerate(items):
        org = _extract(raw)
        if org is None:
            rows.append(InputRow(index, raw, None, "malformed"))
        elif org in seen:
            rows.append(InputRow(index, raw, org, "duplicate"))
        else:
            seen.add(org)
            rows.append(InputRow(index, raw, org, None))
    return rows


class Deadline:
    def __init__(self, budget_s: float, soft: float = 0.80, hard: float = 0.92, clock: Callable[[], float] = time.monotonic):
        self.clock, self.start = clock, clock()
        self.budget, self.soft_at, self.hard_at = budget_s, budget_s * soft, budget_s * hard

    def elapsed(self) -> float:
        return self.clock() - self.start

    def soft_passed(self) -> bool:
        return self.elapsed() >= self.soft_at

    def hard_passed(self) -> bool:
        return self.elapsed() >= self.hard_at

    def remaining_to_hard(self) -> float:
        return max(0.0, self.hard_at - self.elapsed())


class EnvelopeWriter:
    """Append-only partial file (crash-safe) -> atomic rewrite in input order at the end."""

    def __init__(self, path: str | Path, fsync_every: int = 25):
        self.path = Path(path)
        self.partial = self.path.with_name(self.path.name + ".partial")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fsync_every, self._n = fsync_every, 0
        self._handle = self.partial.open("a", encoding="utf-8")
        self.envelopes: dict[str, dict] = {}
        for line in self.partial.read_text(encoding="utf-8").splitlines():  # resume support
            if line.strip():
                try:
                    env = json.loads(line)
                    self.envelopes[env["organisation_number"]] = env
                except (json.JSONDecodeError, KeyError):
                    continue

    def done(self) -> set[str]:
        return set(self.envelopes)

    def write(self, env: dict) -> None:
        clean_env = stringify_keys(env)
        self.envelopes[clean_env["organisation_number"]] = clean_env
        self._handle.write(dumps(clean_env) + "\n")
        self._handle.flush()
        self._n += 1
        if self._n % self.fsync_every == 0:
            os.fsync(self._handle.fileno())

    def finalize(self, order: list[str], fallback: Callable[[str], dict]) -> int:
        for org in order:
            if org not in self.envelopes:
                self.envelopes[org] = stringify_keys(fallback(org))
            else:
                self.envelopes[org] = stringify_keys(self.envelopes[org])
        self._handle.flush()
        os.fsync(self._handle.fileno())
        self._handle.close()
        tmp = self.path.with_name(self.path.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as out:
            for org in order:
                out.write(dumps(self.envelopes[org]) + "\n")
            out.flush()
            os.fsync(out.fileno())
        tmp.replace(self.path)
        return len(order)


Worker = Callable[[str, Deadline], Awaitable[dict]]


async def run_batch(orgs: list[str], worker: Worker, writer: EnvelopeWriter, *, run: dict, deadline: Deadline,
                    concurrency: int = 16, per_company_timeout: float = 90.0) -> dict:
    """Every org ends with exactly one envelope. Exceptions, hangs and the global deadline are all absorbed."""
    sem = asyncio.Semaphore(concurrency)
    todo = [o for o in orgs if o not in writer.done()]
    timings: list[float] = []

    async def one(org: str) -> None:
        async with sem:
            started = time.monotonic()
            if deadline.hard_passed():
                writer.write(failure_envelope(org, run, "time_budget", "global deadline reached before start", stage="scheduler"))
                return
            limit = max(0.05, min(per_company_timeout, deadline.remaining_to_hard()))
            try:
                env = await asyncio.wait_for(worker(org, deadline), timeout=limit)
            except asyncio.TimeoutError:
                code = "time_budget" if deadline.hard_passed() else "company_timeout"
                env = failure_envelope(org, run, code, f"no result within {limit:.1f}s", stage="scheduler")
            except Exception as exc:  # noqa: BLE001 - nothing may escape the batch loop
                env = failure_envelope(org, run, "worker_exception", f"{type(exc).__name__}: {exc}", stage="worker")
            if not isinstance(env, dict) or env.get("organisation_number") != org:
                env = failure_envelope(org, run, "bad_worker_output", "worker returned a malformed envelope", stage="worker")
            writer.write(env)
            timings.append(time.monotonic() - started)

    await asyncio.gather(*(one(o) for o in todo))
    codes = Counter(e["errors"][0]["code"] for e in writer.envelopes.values() if e.get("errors"))
    return stringify_keys({
        "processed_this_run": len(todo), "resumed": len(orgs) - len(todo),
        "status_counts": dict(Counter(e["status"] for e in writer.envelopes.values())),
        "error_codes": dict(codes),
        "p50_s": round(statistics.median(timings), 3) if timings else None,
        "p95_s": round(sorted(timings)[int(0.95 * (len(timings) - 1))], 3) if timings else None,
    })
