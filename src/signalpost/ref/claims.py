"""Stable claim keys and an idempotent merge that yields real changes only."""
from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any


def canonical(value: Any) -> str:
    """Deterministic JSON: sorted keys, no whitespace, NFC-normalised strings."""
    def norm(v: Any) -> Any:
        if isinstance(v, str):
            return unicodedata.normalize("NFC", v).strip()
        if isinstance(v, dict):
            return {str(k): norm(x) for k, x in sorted(v.items())}
        if isinstance(v, (list, tuple)):
            return [norm(x) for x in v]
        return v
    return json.dumps(norm(value), ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def value_hash(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()[:16]


def claim_key(orgnr: str, field: str, discriminator: str = "") -> str:
    """Identity of a claim slot. Discriminator = job uuid, role id, fiscal year, URL, ...
    The VALUE is deliberately not part of the key, so a changed value is a change, not a new claim."""
    raw = f"{orgnr}|{field}|{discriminator}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def merge_claims(previous: dict[str, dict], current: list[dict], now: str, *, rechecked_fields: set[str]) -> tuple[dict[str, dict], list[dict]]:
    """Merge a fresh crawl into the previous claim store.

    Each claim: {"key", "field", "value", "first_observed_at", "last_verified_at", "history": [...]}.
    - same key + same value  -> only last_verified_at moves (no change event)
    - same key + new value   -> change event "changed"; old value kept in history
    - new key                -> change event "added"
    - missing now            -> "removed" ONLY if its field family was successfully re-checked;
                                otherwise keep the last supported value (failed refresh must not erase).
    """
    merged = {k: dict(v) for k, v in previous.items()}
    changes: list[dict] = []
    seen: set[str] = set()
    for claim in current:
        key = claim["key"]
        seen.add(key)
        new_hash = value_hash(claim["value"])
        old = merged.get(key)
        if old is None:
            merged[key] = {**claim, "value_hash": new_hash, "first_observed_at": now, "last_verified_at": now, "history": []}
            changes.append({"type": "added", "key": key, "field": claim["field"], "new": claim["value"], "at": now})
        elif old.get("value_hash") == new_hash:
            old["last_verified_at"] = now
        else:
            old["history"] = [*old.get("history", []), {"value": old["value"], "until": now}]
            changes.append({"type": "changed", "key": key, "field": claim["field"], "old": old["value"], "new": claim["value"], "at": now})
            old.update({"value": claim["value"], "value_hash": new_hash, "last_verified_at": now})
    for key, old in list(merged.items()):
        if key not in seen and old["field"] in rechecked_fields and not old.get("removed_at"):
            old["removed_at"] = now
            changes.append({"type": "removed", "key": key, "field": old["field"], "old": old["value"], "at": now})
    return merged, changes
