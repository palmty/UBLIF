"""
UBLIF staged pipeline  —  Phases 1 (bug fixes) + 2 (architecture) + 3 (ledger).

Pipeline over the experiment set X (raw minus the 149 fixtures):

    X
     -> Alg0   Field mapping / normalize            [no drop]
     -> Alg1a  Provenance: test/admin, bot/crawler   -> R1a   (drop)   [gated: provenance]
     -> Alg1b  Deduplication (windowed, tz-aware)     -> R1b   (drop)   [gated: dedup]
     -> Alg2   Standards + Completeness               -> R2    (drop)
     -> Alg2b  Repair (format date ...)               [no drop, counts repairs]
     -> Alg3a  Compliance verify (enforce / flag)     -> R3    (drop)
     -> Alg3b  Privacy transform (hash/mask/truncate) [no drop]
     -> VR

Accounting identity (checked):  X == R1a + R1b + R2 + R3 + VR
where R_s = records whose FIRST drop is at stage s, VR = survivors.

Architecture moves realised here (Phase 2):
  * `Format Date`        : Alg1 -> Alg2/Alg2b   (was self-validating -> R2=0)
  * `Map Fields`         : Alg1 -> Alg0         (structural, not a filter)
  * `No Service ID`      : Alg1 -> Alg2         (a completeness check)
  * missing `customValue`: (unowned) -> Alg2    (counted as R2, not eaten by dedup)
  * Device 802.1AR / DOI : deleted              (dead code — no data)
  * `Hashing & Masking`  : Alg3 middle -> Alg3b (last), so verify precedes transform
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

import yaml

from utils.ubif_ledger import (
    acct, cv, dedup_key, dropped_at, flags, is_fixture, mark, parse_dt,
    payload, sid, survived,
)
from utils.legal_compliance import ComputerCrimeActChecker, PDPACompliance

_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,9})?(Z|[+-]\d{2}:\d{2})?$")
_IPV4_RE = re.compile(r"^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$")
_IPV6_RE = re.compile(r"^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$|^::1$")
_DEVICE_RE = re.compile(r"^(iphone|android|web|ipad|desktop|computer|nexus|windows|ios|macos)$", re.IGNORECASE)


class UblifPipeline:
    """Staged, ledgered UBLIF pipeline. One instance == one scenario run."""

    def __init__(
        self,
        config_path: str,
        provenance: bool = True,
        dedup: bool = True,
        duplicate_window_seconds: float = 1.0,
        include_item_in_key: bool = True,
    ):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        dq = cfg.get("ubif_filters", {}).get("data_quality", [])
        self.test_patterns = ["test", "admin", "demo", "debug"]
        self.bot_patterns = ["bot", "crawler", "spider", "scraper"]
        for rule in dq:
            if rule.get("name") == "remove_test_accounts":
                self.test_patterns = [p.lower() for p in rule.get("patterns", self.test_patterns)]
            if rule.get("name") == "remove_bot_traffic":
                self.bot_patterns = [p.lower() for p in rule.get("bot_patterns", self.bot_patterns)]

        self.provenance = provenance
        self.dedup = dedup
        self.window = float(duplicate_window_seconds)
        self.include_item = include_item_in_key

        self._crime = ComputerCrimeActChecker(config={"action": "reject"})
        self._pdpa = PDPACompliance()

        self.stats: Dict[str, Any] = {}

    # ------------------------------------------------------------------ Alg0
    def alg0(self, records: List[Dict[str, Any]]) -> None:
        for r in records:
            dt, status = parse_dt(r)
            r["_ts"], r["_ts_status"] = dt, status  # pipeline may write; parse_dt itself does not
            mark(r, "alg0", "pass", "field_mapping", status)

    # ----------------------------------------------------------------- Alg1a
    def alg1a(self, records: List[Dict[str, Any]]) -> None:
        if not self.provenance:
            for r in records:
                mark(r, "alg1a", "pass", "disabled")
            return
        for r in records:
            a = acct(r).lower()
            device = str(cv(r, "device") or "").lower()
            operation = str(cv(r, "operation") or "").lower()
            is_test = bool(a) and any(a.startswith(p) for p in self.test_patterns)
            is_bot = any(p in device or p in operation for p in self.bot_patterns)
            # non-short-circuit: record every matched provenance rule
            if is_test:
                mark(r, "alg1a", "drop", "test_admin_account", a)
            if is_bot:
                mark(r, "alg1a", "drop", "bot_traffic", f"{device}/{operation}")
            if not is_test and not is_bot:
                mark(r, "alg1a", "pass", "human")

    # ----------------------------------------------------------------- Alg1b
    def alg1b(self, records: List[Dict[str, Any]]) -> None:
        if not self.dedup:
            for r in records:
                mark(r, "alg1b", "pass", "disabled")
            return

        alive = [r for r in records if survived(r)]
        dated = [r for r in alive if r.get("_ts") is not None]
        undated = [r for r in alive if r.get("_ts") is None]

        # tz-uniform after Fix 1 -> sort can never raise; no try/except crutch.
        dated.sort(key=lambda r: r["_ts"])

        seen: Dict[Any, Dict[str, Any]] = {}
        for r in dated:
            k = dedup_key(r, include_item=self.include_item)
            if k is None:  # no actor identity (guest w/o distinguisher) -> never dedup
                mark(r, "alg1b", "pass", "not_applicable")
                continue
            if k in seen:
                anchor = seen[k]
                diff = (r["_ts"] - anchor["_ts"]).total_seconds()
                assert diff >= 0, "records not sorted ascending by _ts"
                if 0 <= diff <= self.window:  # fixed-anchor window (Fix 4)
                    r["_dup_of"] = anchor.get("_id")
                    r["_dup_identical"] = (payload(r) == payload(anchor))
                    mark(r, "alg1b", "drop", "duplicate_window", f"diff={diff:.3f}s")
                    continue
                # outside window -> becomes the new anchor
            seen[k] = r
            mark(r, "alg1b", "pass", "unique_in_window")

        for r in undated:
            mark(r, "alg1b", "pass", f"skipped:{r.get('_ts_status')}")

    # ------------------------------------------------------------------ Alg2
    def alg2(self, records: List[Dict[str, Any]]) -> None:
        for r in records:
            if not survived(r):
                continue
            # --- completeness (DROP) ---
            missing_required = [f for f in ("category", "name") if not str(r.get(f) or "").strip()]
            has_payload = any(cv(r, f) not in (None, "") for f in ("serviceId", "account", "datetime"))
            if missing_required:
                mark(r, "alg2", "drop", "missing_required_field", ",".join(missing_required))
                continue
            if not has_payload:
                mark(r, "alg2", "drop", "missing_customvalue", "no serviceId/account/datetime")
                continue

            # --- standards (FLAG, non-required per config) ---
            dt_raw = cv(r, "datetime")
            if dt_raw and not _ISO_RE.match(str(dt_raw)):
                mark(r, "alg2", "flag", "iso8601_bad", str(dt_raw))
            lat, lon = cv(r, "location.lat"), cv(r, "location.lon")
            if lat is not None and lon is not None:
                try:
                    if not (-90 <= float(lat) <= 90) or not (-180 <= float(lon) <= 180):
                        mark(r, "alg2", "flag", "geo_out_of_range", f"{lat},{lon}")
                except (ValueError, TypeError):
                    mark(r, "alg2", "flag", "geo_unparseable", f"{lat},{lon}")
            ip = cv(r, "serviceIP")
            if ip and not (_IPV4_RE.match(str(ip)) or _IPV6_RE.match(str(ip))):
                mark(r, "alg2", "flag", "ip_malformed", str(ip))
            dev = cv(r, "device")
            if dev and not _DEVICE_RE.match(str(dev)):
                mark(r, "alg2", "flag", "device_bad", str(dev))
            if sid(r) == "":
                mark(r, "alg2", "flag", "no_service_id", "")  # soft completeness

    # ----------------------------------------------------------------- Alg2b
    def alg2b(self, records: List[Dict[str, Any]]) -> None:
        """Repair pass — counts repairable violations, drops nothing."""
        for r in records:
            if not survived(r):
                continue
            repaired = [f["rule"] for f in r.get("_trace", [])
                        if f["decision"] == "flag" and f["rule"] in ("iso8601_bad",)]
            if repaired:
                mark(r, "alg2b", "pass", "repaired", ",".join(repaired))
            else:
                mark(r, "alg2b", "pass", "nothing_to_repair")

    # ----------------------------------------------------------------- Alg3a
    def alg3a(self, records: List[Dict[str, Any]]) -> None:
        for r in records:
            if not survived(r):
                continue
            is_clean, threats = self._crime.check_record(r)
            if not is_clean:  # COMPUTER_CRIME_ACT action=reject -> enforce (drop)
                mark(r, "alg3a", "drop", "computer_crime_act", ";".join(threats)[:120])
                continue
            # other laws: flag only
            if not acct(r):
                mark(r, "alg3a", "flag", "pdpa_no_account", "")
            if not cv(r, "device") or not cv(r, "serviceIP"):
                mark(r, "alg3a", "flag", "cybersecurity_logging", "")

    # ----------------------------------------------------------------- Alg3b
    def alg3b(self, records: List[Dict[str, Any]]) -> None:
        """Privacy transform on survivors — last, so verify precedes transform."""
        for r in records:
            if not survived(r):
                continue
            a = cv(r, "account")
            if a:
                h = self._pdpa.anonymize_account(str(a))
                r["customValue.account"] = h
                if isinstance(r.get("customValue"), dict):
                    r["customValue"]["account"] = h
            ip = cv(r, "serviceIP")
            if ip:
                m = self._pdpa.mask_ip_address(str(ip))
                r["customValue.serviceIP"] = m
                if isinstance(r.get("customValue"), dict):
                    r["customValue"]["serviceIP"] = m
            for coord in ("location.lat", "location.lon"):
                val = cv(r, coord)
                if val is not None:
                    try:
                        rv = round(float(val), 4)
                        r[f"customValue.{coord}"] = rv
                    except (ValueError, TypeError):
                        pass
            mark(r, "alg3b", "pass", "privacy_transform")

    # ------------------------------------------------------------------- run
    def run(self, X: List[Dict[str, Any]]) -> Dict[str, Any]:
        self.alg0(X)
        self.alg1a(X)
        self.alg1b(X)
        self.alg2(X)
        self.alg2b(X)
        self.alg3a(X)
        self.alg3b(X)

        buckets = {"alg1a": [], "alg1b": [], "alg2": [], "alg3a": []}
        vr = []
        for r in X:
            stage, _ = dropped_at(r)
            if stage is None:
                vr.append(r)
            else:
                buckets.setdefault(stage, []).append(r)

        R1a, R1b, R2, R3 = (buckets["alg1a"], buckets["alg1b"],
                            buckets["alg2"], buckets["alg3a"])

        # Phase 3.2 accounting identity — the whole point of the rebuild.
        assert all("_trace" in r for r in X), "every record must carry a trace"
        total = len(R1a) + len(R1b) + len(R2) + len(R3) + len(vr)
        assert total == len(X), f"identity broken: {total} != {len(X)}"

        self.stats = {
            "X": len(X),
            "R1a": len(R1a), "R1b": len(R1b), "R2": len(R2), "R3": len(R3),
            "VR": len(vr),
            "identity_holds": total == len(X),
            "provenance": self.provenance, "dedup": self.dedup, "window": self.window,
        }
        return {"R1a": R1a, "R1b": R1b, "R2": R2, "R3": R3, "VR": vr, "stats": self.stats}


def load_experiment_set(config_path: str, raw_path: str):
    """Return (X, F) — X = raw minus the 149 fixtures, F = the fixtures."""
    import json
    records = []
    with open(raw_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    F = [r for r in records if is_fixture(r)]
    X = [r for r in records if not is_fixture(r)]
    return X, F
