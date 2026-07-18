"""
UBLIF Phase 0 — Freeze & Provenance diagnostics (READ-ONLY).

Confirms the facts that the Phase 1 code fixes depend on:
  0.2  fixture detection candidates (target = 149)
  0.3  fixtures must not overlap the unparseable/missing set
  0.4  unique dedup keys vs duplicates_removed
  0.5  timezone of the tz-naive records (do NOT assume UTC)
  0.6  name/category cardinality -> does itemId belong in the dedup key?

Run:
    venv/Scripts/python.exe scripts/ubif_fix/phase0_diagnostics.py
"""
from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
RAW = os.path.join(ROOT, "output_raw.ndjson")


# ----------------------------------------------------------------------------
# field helpers (data is dot-flattened: 'customValue.datetime', not nested)
# ----------------------------------------------------------------------------
def _cv(r, field):
    """Read customValue.<field> from either flattened or nested records."""
    v = r.get(f"customValue.{field}")
    if v is not None:
        return v
    cv = r.get("customValue")
    if isinstance(cv, dict):
        return cv.get(field)
    return None


def _acct(r):
    return _cv(r, "account") or ""


def _sid(r):
    return _cv(r, "serviceId") or ""


def _dt_raw(r):
    return _cv(r, "datetime")


def _parse(r):
    """Return (datetime|None, status) WITHOUT localizing (diagnostic only)."""
    s = _dt_raw(r)
    if not s:
        return None, "missing"
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")), "ok"
    except (ValueError, TypeError):
        return None, "unparseable"


def load():
    records = []
    empty = 0
    parse_err = 0
    with open(RAW, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                empty += 1
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                parse_err += 1
    return records, empty, parse_err


def main():
    print("=" * 72)
    print("UBLIF PHASE 0 DIAGNOSTICS")
    print("=" * 72)

    # 0.1 hash
    h = hashlib.sha256()
    with open(RAW, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    print(f"\n[0.1] sha256(output_raw.ndjson) = {h.hexdigest()}")

    records, empty, parse_err = load()
    print(f"[0.1] lines parsed = {len(records):,}  empty = {empty}  parse_err = {parse_err}")
    print(f"      (doc expects 104,309 / 0 / 0)")

    # datetime / tz split
    dts = {}  # id -> (dt, status)
    for r in records:
        dts[id(r)] = _parse(r)

    parsed = [d for d, s in dts.values() if d is not None]
    aware = [d for d in parsed if d.tzinfo is not None]
    naive = [d for d in parsed if d.tzinfo is None]
    missing = sum(1 for _, s in dts.values() if s == "missing")
    unparse = sum(1 for _, s in dts.values() if s == "unparseable")
    print(f"\n[tz] parseable = {len(parsed):,}  aware = {len(aware):,}  naive = {len(naive):,}")
    print(f"     missing = {missing:,}  unparseable = {unparse:,}")
    print(f"     (doc: aware 95,423 / naive 5,338 / unparseable 3,548)")

    # 0.5 timezone of naive records — hour-of-day distribution
    def plat(r):
        return r.get("platform") or r.get("source") or r.get("category", "?")

    print("\n[0.5] naive platform breakdown:")
    naive_plat = Counter()
    naive_hours = Counter()
    aware_hours = Counter()
    for r in records:
        d, s = dts[id(r)]
        if d is None:
            continue
        if d.tzinfo is None:
            naive_plat[str(plat(r))[:40]] += 1
            naive_hours[d.hour] += 1
        else:
            aware_hours[d.hour] += 1
    for k, v in naive_plat.most_common(10):
        print(f"        {v:6,}  {k}")
    print("\n[0.5] naive hour-of-day histogram (local wall-clock as stored):")
    for hh in range(24):
        bar = "#" * (naive_hours[hh] * 60 // max(max(naive_hours.values(), default=1), 1))
        print(f"        {hh:02d}h {naive_hours[hh]:6,} {bar}")
    naive_peak = naive_hours.most_common(3)
    print(f"      naive peak hours = {naive_peak}")
    print("\n[0.5] aware hour-of-day histogram (as stored, mostly UTC 'Z'):")
    for hh in range(24):
        bar = "#" * (aware_hours[hh] * 60 // max(max(aware_hours.values(), default=1), 1))
        print(f"        {hh:02d}h {aware_hours[hh]:6,} {bar}")
    print(f"      aware peak hours = {aware_hours.most_common(3)}")
    print("      -> naive peak ~02-03h => stored as UTC (true 09-10 ICT)")
    print("      -> naive peak ~09-10h => stored as Asia/Bangkok (UTC+7)")

    # 0.4 unique dedup keys vs total
    keys = set()
    for r in records:
        keys.add((_acct(r), _sid(r), r.get("name", ""), r.get("category", "")))
    print(f"\n[0.4] unique 4-tuple keys = {len(keys):,}  (doc Cset = 43,736)")
    print(f"      total records          = {len(records):,}")
    print(f"      implied collisions     = {len(records) - len(keys):,}")

    # 0.3 unparseable/missing account-empty overlap ("3,548")
    no_dt_ids = {id(r) for r in records if dts[id(r)][0] is None}
    print(f"\n[0.3] records with no usable datetime = {len(no_dt_ids):,}")
    no_cv = sum(
        1
        for r in records
        if not isinstance(r.get("customValue"), dict)
        and not any(k.startswith("customValue.") for k in r.keys())
    )
    print(f"      records with NO customValue.* keys at all = {no_cv:,}")

    # 0.6 name / category cardinality
    print("\n[0.6] top name:")
    for k, v in Counter(r.get("name", "") for r in records).most_common(15):
        print(f"        {v:6,}  {k}")
    print("[0.6] top category:")
    for k, v in Counter(r.get("category", "") for r in records).most_common(15):
        print(f"        {v:6,}  {k}")
    has_itemid = sum(1 for r in records if _cv(r, "itemId") not in (None, ""))
    print(f"[0.6] records with a non-empty customValue.itemId = {has_itemid:,}")

    # 0.2 fixture marker hunting — look for anomalous constant markers
    print("\n[0.2] account value distribution (top 20):")
    for k, v in Counter(_acct(r) for r in records).most_common(20):
        print(f"        {v:6,}  {k!r}")
    print("[0.2] serviceIP prefix (top 15):")
    for k, v in Counter(str(_cv(r, "serviceIP") or "")[:12] for r in records).most_common(15):
        print(f"        {v:6,}  {k!r}")
    print("[0.2] _index distribution:")
    for k, v in Counter(r.get("_index", "") for r in records).most_common(10):
        print(f"        {v:6,}  {k!r}")

    # any record carrying an explicit fixture/synthetic marker?
    marker_keys = Counter()
    for r in records:
        for k in r.keys():
            lk = k.lower()
            if any(t in lk for t in ("fixture", "synthetic", "inject", "label", "ground", "_fx", "test_")):
                marker_keys[k] += 1
    print(f"\n[0.2] explicit fixture-ish keys found: {dict(marker_keys) or 'NONE'}")


if __name__ == "__main__":
    main()
