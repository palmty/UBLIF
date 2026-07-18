"""
UBLIF runner  —  Phase 3 ledger report + Phase 4 experiment harness.

    venv/Scripts/python -X utf8 scripts/ubif_fix/run_ublif.py

Produces (to outputs/ublif/):
  * ledger_report.json      accounting identity + dropped_at + flag rates (Scenario A)
  * ablation.json           A/B/C/D marginal contributions (Phase 4.1)
  * threshold_sweep.json    duplicate_window_seconds sweep (Phase 4.2)
  * fault_injection.json    per-layer recall/precision on labelled faults (Phase 4.3)
"""
from __future__ import annotations

import copy
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))
from utils.ubif_pipeline import UblifPipeline, load_experiment_set  # noqa: E402
from utils.ubif_ledger import dropped_at, flags, all_drop_rules, survived  # noqa: E402
from fixtures import assert_fixture_count, build_injection_set          # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG = os.path.join(ROOT, "config.yaml")
RAW = os.path.join(ROOT, "output_raw.ndjson")
OUT = os.path.join(ROOT, "outputs", "ublif")
os.makedirs(OUT, exist_ok=True)


def _save(name, obj):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def fresh(X):
    return copy.deepcopy(X)


def scenario_A(X):
    print("\n" + "=" * 72)
    print("SCENARIO A (provenance + dedup)  —  Phase 3 ledger")
    print("=" * 72)
    p = UblifPipeline(CONFIG, provenance=True, dedup=True, duplicate_window_seconds=1.0)
    res = p.run(fresh(X))
    s = res["stats"]
    print(f"X = {s['X']:,}")
    print(f"  R1a (provenance) = {s['R1a']:,}")
    print(f"  R1b (dedup)      = {s['R1b']:,}")
    print(f"  R2  (standards)  = {s['R2']:,}")
    print(f"  R3  (compliance) = {s['R3']:,}")
    print(f"  VR  (valid)      = {s['VR']:,}")
    print(f"  identity X == R1a+R1b+R2+R3+VR : {s['identity_holds']}")

    allrec = res["R1a"] + res["R1b"] + res["R2"] + res["R3"] + res["VR"]
    drop_stage = Counter(dropped_at(r)[0] or "VR" for r in allrec)
    drop_rule = Counter(f"{dropped_at(r)[0]}:{dropped_at(r)[1]}" for r in allrec if dropped_at(r)[0])
    flag_rate = Counter(f for r in res["VR"] for f in flags(r))
    # non-short-circuit overlap: records matching >1 drop rule
    overlap = Counter()
    for r in allrec:
        rules = sorted({rule for _, rule in all_drop_rules(r)})
        if len(rules) > 1:
            overlap["+".join(rules)] += 1
    dup_identical = sum(1 for r in res["R1b"] if r.get("_dup_identical"))

    print(f"\n  dropped_at(stage): {dict(drop_stage)}")
    print(f"  drop rules: {dict(drop_rule.most_common())}")
    print(f"  flag rates on VR: {dict(flag_rate.most_common())}")
    print(f"  duplicate-identity (payload==anchor) among R1b: {dup_identical:,}/{s['R1b']:,}")
    print(f"  multi-rule overlap (order-independent): {dict(overlap.most_common(10))}")

    _save("ledger_report.json", {
        "stats": s,
        "dropped_at_stage": dict(drop_stage),
        "drop_rules": dict(drop_rule),
        "flag_rates_on_VR": dict(flag_rate),
        "duplicate_identical_in_R1b": dup_identical,
        "multi_rule_overlap": dict(overlap),
    })
    return s


def ablation(X):
    print("\n" + "=" * 72)
    print("PHASE 4.1  ABLATION 2x2  (marginal contribution, not A vs B)")
    print("=" * 72)
    scen = {
        "A": dict(provenance=True, dedup=True),
        "B": dict(provenance=False, dedup=False),
        "C": dict(provenance=False, dedup=True),   # dedup only
        "D": dict(provenance=True, dedup=False),   # provenance only
    }
    out = {}
    for name, kw in scen.items():
        p = UblifPipeline(CONFIG, duplicate_window_seconds=1.0, **kw)
        s = p.run(fresh(X))["stats"]
        # PY (proxy yield) = valid retention fraction
        s["PY"] = round(100.0 * s["VR"] / s["X"], 4)
        out[name] = s
        print(f"  {name}: VR={s['VR']:,}  PY={s['PY']}%  (prov={kw['provenance']}, dedup={kw['dedup']})")
    py = {k: out[k]["PY"] for k in out}
    marg = {
        "provenance_effect_PY_A_minus_C": round(py["A"] - py["C"], 4),
        "dedup_effect_PY_A_minus_D": round(py["A"] - py["D"], 4),
        "confounded_PY_A_minus_B (avoid)": round(py["A"] - py["B"], 4),
    }
    print(f"  marginal: {marg}")
    _save("ablation.json", {"scenarios": out, "marginal": marg})
    return out


def threshold_sweep(X):
    print("\n" + "=" * 72)
    print("PHASE 4.2  THRESHOLD SWEEP (duplicate_window_seconds)")
    print("=" * 72)
    rows = []
    for w in [0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 30.0]:
        p = UblifPipeline(CONFIG, provenance=True, dedup=True, duplicate_window_seconds=w)
        res = p.run(fresh(X))
        s = res["stats"]
        ident = sum(1 for r in res["R1b"] if r.get("_dup_identical"))
        pct_identical = round(100.0 * ident / s["R1b"], 2) if s["R1b"] else 0.0
        retention = round(100.0 * s["VR"] / s["X"], 3)
        rows.append({"window_s": w, "R1b": s["R1b"], "VR": s["VR"],
                     "retention_pct": retention, "pct_identical": pct_identical})
        print(f"  w={w:>5}s  R1b={s['R1b']:>6,}  VR={s['VR']:>7,}  "
              f"retention={retention:6.3f}%  identical={pct_identical:5.1f}%")
    _save("threshold_sweep.json", rows)
    return rows


def fault_injection(X):
    print("\n" + "=" * 72)
    print("PHASE 4.3  FAULT INJECTION (external ground truth)")
    print("=" * 72)
    inj = build_injection_set()
    Xi = fresh(X) + copy.deepcopy(inj)
    p = UblifPipeline(CONFIG, provenance=True, dedup=True, duplicate_window_seconds=1.0)
    p.run(Xi)

    injected = [r for r in Xi if "_fault_label" in r]
    per_label = {}
    for r in injected:
        lab = r["_fault_label"]
        d = per_label.setdefault(lab, {"n": 0, "caught": 0, "flagged": 0, "passed": 0})
        d["n"] += 1
        stage, _ = dropped_at(r)
        fl = flags(r)
        if stage is not None:
            d["caught"] += 1
        elif fl:
            d["flagged"] += 1
        else:
            d["passed"] += 1

    # clean_control must pass 100%
    cc = per_label.get("clean_control", {})
    control_ok = cc.get("passed", 0) == cc.get("n", 0)
    print("  label                caught  flagged  passed  n")
    for lab, d in per_label.items():
        print(f"  {lab:<20} {d['caught']:>6} {d['flagged']:>8} {d['passed']:>7} {d['n']:>4}")
    print(f"  clean_control passes 100%: {control_ok}")
    # detection = caught OR flagged for the fault groups
    detected = {lab: (d["caught"] + d["flagged"]) for lab, d in per_label.items() if lab != "clean_control"}
    recall = {lab: round(100.0 * v / per_label[lab]["n"], 1) for lab, v in detected.items()}
    print(f"  detection recall per fault: {recall}")
    _save("fault_injection.json", {
        "per_label": per_label, "clean_control_ok": control_ok, "recall_pct": recall,
    })
    return per_label


def main():
    print("Loading experiment set (raw minus 149 fixtures)...")
    X, F = load_experiment_set(CONFIG, RAW)
    # Phase 0 gate
    assert_fixture_count(X + F)
    print(f"  fixtures F = {len(F)}  |  experiment X = {len(X):,}  (X == 104,309 - 149 = 104,160)")
    assert len(X) == 104160, f"X={len(X)}"

    scenario_A(X)
    ablation(X)
    threshold_sweep(X)
    fault_injection(X)
    print(f"\nAll artifacts written to {OUT}")


if __name__ == "__main__":
    main()
