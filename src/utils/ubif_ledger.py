"""
UBLIF record-level ledger & Phase-1 primitives.

Single source of truth for:
  * SOURCE_TZ / parse_dt        (Phase 1, Fix 1)
  * dedup_key                   (Phase 1, Fix 3)
  * is_fixture                  (Phase 0.2)  -> exactly 149 on output_raw.ndjson
  * mark / dropped_at / flags   (Phase 3 ledger)
  * payload                     (duplicate-identity ground truth)

Guiding rule (the one that governs the whole plan):
  *Never delete a record — mark it and carry it to the end.*
  Every headline number must be derivable from the ledger, not from the
  len() of some surviving list.  That is what makes `X == sum(R) + VR`
  a genuine assertion instead of survivorship.

Data note: production records are dot-flattened ("customValue.datetime"),
but the 149 fixtures use a nested {"customValue": {...}} dict.  All helpers
here read both shapes.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

# Confirmed in Phase 0.5: tz-naive timestamps (5,338) are Asia/Bangkok local.
# naive wall-clock peaks 14-16h; tz-aware (UTC 'Z') peaks 07-09h; 07-09 UTC +7
# == 14-16 ICT -> the two populations align only under UTC+7.  Do NOT assume UTC.
SOURCE_TZ = ZoneInfo("Asia/Bangkok")

# Content fields used to decide "same event retried" vs "different event".
# Everything except the timestamp and per-record identifiers/bookkeeping.
_PAYLOAD_EXCLUDE = {
    "_id", "_index", "_ts", "_ts_status", "_trace", "_dup_of", "_dup_identical",
    "_stage", "customValue.datetime", "source_event_id", "source_event_index",
    "source_event_date",
}


# ---------------------------------------------------------------------------
# field access (flattened OR nested customValue)
# ---------------------------------------------------------------------------
def cv(record: Dict[str, Any], field: str) -> Optional[Any]:
    """Read customValue.<field> from a flattened or nested record."""
    v = record.get(f"customValue.{field}")
    if v is not None:
        return v
    nested = record.get("customValue")
    if isinstance(nested, dict):
        return nested.get(field)
    return None


def acct(record: Dict[str, Any]) -> str:
    return str(cv(record, "account") or "")


def sid(record: Dict[str, Any]) -> str:
    v = cv(record, "serviceId")
    return "" if v is None else str(v)


# ---------------------------------------------------------------------------
# Phase 0.2 — fixture detection (deterministic; asserts to 149)
# ---------------------------------------------------------------------------
def is_fixture(record: Dict[str, Any]) -> bool:
    """
    The 149 pre-existing synthetic records are exactly those with no `_index`
    key (they instead carry `source_event_id`/`source_event_index` and a nested
    `customValue` dict).  Verified: len == 149 and disjoint from the 3,548
    no-datetime records.
    """
    return "_index" not in record


# ---------------------------------------------------------------------------
# Phase 1 / Fix 1 — parse_dt: read-only, never hide, never collapse
# ---------------------------------------------------------------------------
def parse_dt(record: Dict[str, Any]) -> Tuple[Optional[datetime], str]:
    """
    Return (datetime|None, status).  Statuses:
        'missing'         -> no datetime field
        'unparseable'     -> present but not ISO-8601
        'naive_localized' -> parsed, had no tz, localized to SOURCE_TZ
        'aware'           -> parsed with an explicit offset

    MUST NOT write anything back onto `record` and MUST NOT return
    datetime.min (that is what silently glued the 3,548 into one dedup bucket).
    """
    s = cv(record, "datetime")
    if not s:
        return None, "missing"
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None, "unparseable"
    if dt.tzinfo is None:
        return dt.replace(tzinfo=SOURCE_TZ), "naive_localized"
    return dt, "aware"


# ---------------------------------------------------------------------------
# Phase 1 / Fix 3 — dedup_key: guests must not collapse across identities
# ---------------------------------------------------------------------------
def dedup_key(record: Dict[str, Any], include_item: bool = True):
    """
    Return the identity tuple used for windowed dedup, or None when the record
    has no way to be attributed to a single actor (then it is never deduped).

    Guests (account empty / 'Guest') carry no sessionId/clientIP in this
    dataset, so they fall through to None — conservative, per Phase 0.4 which
    showed the 4-tuple collapses 104k rows into 4,292 buckets.
    """
    account = acct(record)
    if not account or account == "Guest":
        sess = record.get("sessionId") or record.get("clientIP")
        if not sess:
            return None
        account = f"__anon__{sess}"

    key = [account, sid(record), record.get("name", ""), record.get("category", "")]
    if include_item:
        key.append(str(cv(record, "itemId") or ""))  # absent in this data -> ""
    return tuple(key)


def payload(record: Dict[str, Any]) -> Dict[str, Any]:
    """Content fingerprint: everything except timestamp/id/bookkeeping."""
    out = {}
    for k, v in record.items():
        if k in _PAYLOAD_EXCLUDE:
            continue
        if isinstance(v, dict):  # nested customValue (fixtures)
            v = {ik: iv for ik, iv in v.items() if ik != "datetime"}
        out[k] = v
    return out


# ---------------------------------------------------------------------------
# Phase 3 — the ledger
# ---------------------------------------------------------------------------
def mark(record: Dict[str, Any], stage: str, decision: str, rule: str, detail: str = "") -> None:
    """Append one immutable decision to the record's trace. Never removes rows."""
    record.setdefault("_trace", []).append(
        {"stage": stage, "decision": decision, "rule": rule, "detail": detail}
    )


def dropped_at(record: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """(stage, rule) of the FIRST drop in canonical order, or (None, None)."""
    for t in record.get("_trace", []):
        if t["decision"] == "drop":
            return t["stage"], t["rule"]
    return None, None


def flags(record: Dict[str, Any]) -> List[str]:
    return [t["rule"] for t in record.get("_trace", []) if t["decision"] == "flag"]


def all_drop_rules(record: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Every drop the record matched (non-short-circuit rule attribution)."""
    return [(t["stage"], t["rule"]) for t in record.get("_trace", []) if t["decision"] == "drop"]


def survived(record: Dict[str, Any]) -> bool:
    return dropped_at(record)[0] is None
