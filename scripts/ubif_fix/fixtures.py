"""
UBLIF fixtures — Phase 0.2 detection + Phase 4.3 fault-injection spec.

Detection rule (Phase 0.2, verified deterministic):
    is_fixture(r)  <=>  "_index" not in r        -> exactly 149 records
    (these carry source_event_id / nested customValue; disjoint from the
     3,548 no-datetime records — checked in assert_fixture_count).

Injection spec (Phase 4.3): labelled synthetic records with a KNOWN
ground-truth so recall/precision of each layer can be measured.  Note the
critical constraints the plan calls out:
  * injected `account` must NOT start with test/admin (else Alg1a eats it
    before Alg2 ever sees it),
  * a `clean_control` group that must pass 100%.
"""
from __future__ import annotations

import copy
import json
import os
import sys
from typing import Any, Callable, Dict, List, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))
from utils.ubif_ledger import is_fixture, parse_dt  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RAW = os.path.join(ROOT, "output_raw.ndjson")


def load_raw(path: str = RAW) -> List[Dict[str, Any]]:
    records = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def split_fixtures(records: List[Dict[str, Any]]) -> Tuple[List[Dict], List[Dict]]:
    """Return (fixtures F, experiment set X) — F removed before Alg0."""
    fx = [r for r in records if is_fixture(r)]
    x = [r for r in records if not is_fixture(r)]
    return fx, x


def assert_fixture_count(records: List[Dict[str, Any]]) -> int:
    fx = [r for r in records if is_fixture(r)]
    assert len(fx) == 149, f"is_fixture matched {len(fx)}, expected 149"
    no_dt = {id(r) for r in records if parse_dt(r)[0] is None}
    overlap = {id(r) for r in fx} & no_dt
    assert not overlap, f"fixtures overlap the no-datetime set: {len(overlap)}"
    return len(fx)


# ---------------------------------------------------------------------------
# Phase 4.3 — fault injection
# ---------------------------------------------------------------------------
def _set_cv(r: Dict[str, Any], field: str, value: Any) -> Dict[str, Any]:
    r[f"customValue.{field}"] = value
    if isinstance(r.get("customValue"), dict):
        r["customValue"][field] = value
    return r


def _del_cv(r: Dict[str, Any], field: str) -> Dict[str, Any]:
    r.pop(f"customValue.{field}", None)
    if isinstance(r.get("customValue"), dict):
        r["customValue"].pop(field, None)
    return r


def _set_geo(r: Dict[str, Any], lat: float, lon: float) -> Dict[str, Any]:
    _set_cv(r, "location.lat", lat)
    _set_cv(r, "location.lon", lon)
    r["customValue.location.lat"] = lat
    r["customValue.location.lon"] = lon
    return r


# (label, expected_layer, count, mutator).  expected_layer is the ground-truth
# stage that SHOULD catch/flag the fault.
FIXTURE_SPEC: List[Tuple[str, str, int, Callable[[Dict], Dict]]] = [
    ("date_not_iso8601",  "alg2", 30, lambda r: _set_cv(r, "datetime", "15/01/2024 10:30")),
    ("geo_out_of_range",  "alg2", 30, lambda r: _set_geo(r, 95.7, 200.4)),
    ("ipv4_malformed",    "alg2", 30, lambda r: _set_cv(r, "serviceIP", "999.1.1.1")),
    ("ipv6_malformed",    "alg2", 30, lambda r: _set_cv(r, "serviceIP", "2001:zzzz::1")),
    ("missing_serviceid", "alg2", 30, lambda r: _del_cv(r, "serviceId")),
    ("clean_control",     "none", 30, lambda r: r),
]


def _base_clean_record(i: int) -> Dict[str, Any]:
    """A valid, non-test/admin account record used as the injection base."""
    return {
        "name": "product/detail/show",
        "category": "product",
        "customValue.account": f"injacct{i:04d}",  # NOT test/admin
        "customValue.serviceId": 100 + (i % 50),
        "customValue.serviceName": "InjectionService",
        "customValue.serviceType": "product",
        "customValue.serviceIP": "203.158.195.10",
        "customValue.location.lat": 13.75,
        "customValue.location.lon": 100.5,
        "customValue.keyword": "inject",
        "customValue.datetime": "2024-06-01T10:00:00Z",
        "customValue.device": "Web",
        "customValue.operation": "Windows",
        "_index": "peechang-log.inject",
        "_id": f"inj-{i}",
    }


def build_injection_set() -> List[Dict[str, Any]]:
    """Return labelled synthetic records with `_fault_label` / `_expected_layer`."""
    out: List[Dict[str, Any]] = []
    i = 0
    for label, layer, count, mutate in FIXTURE_SPEC:
        for _ in range(count):
            r = mutate(copy.deepcopy(_base_clean_record(i)))
            r["_fault_label"] = label
            r["_expected_layer"] = layer
            out.append(r)
            i += 1
    return out


if __name__ == "__main__":
    recs = load_raw()
    n = assert_fixture_count(recs)
    inj = build_injection_set()
    print(f"[0.2] is_fixture -> {n} (== 149)  OK")
    print(f"[0.3] fixtures disjoint from no-datetime  OK")
    print(f"[4.3] injection set built: {len(inj)} records across {len(FIXTURE_SPEC)} groups")
