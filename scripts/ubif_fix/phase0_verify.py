"""Phase 0.2/0.3 verification: fixture rule (=149), overlap, guest distinguishers."""
from __future__ import annotations
import json, os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
RAW = os.path.join(ROOT, "output_raw.ndjson")


def _cv(r, f):
    v = r.get(f"customValue.{f}")
    if v is not None:
        return v
    cv = r.get("customValue")
    return cv.get(f) if isinstance(cv, dict) else None


def is_fixture(r):
    return "_index" not in r


records = []
with open(RAW, encoding="utf-8") as fh:
    for line in fh:
        line = line.strip()
        if line:
            records.append(json.loads(line))

fx = [r for r in records if is_fixture(r)]
print(f"[0.2] is_fixture (_index==''): {len(fx)}  (target 149)")
assert len(fx) == 149, f"got {len(fx)}"

# 0.3 overlap with no-datetime (the '3,548')
no_dt = {id(r) for r in records if not _cv(r, "datetime")}
overlap = {id(r) for r in fx} & no_dt
print(f"[0.3] fixtures overlapping the no-datetime set: {len(overlap)} (must be 0)")

# fixture account values (must not be test/admin, else Alg1a eats them)
print("[0.2] fixture accounts:", dict(Counter(str(_cv(r, 'account')) for r in fx)))
print("[0.2] fixture categories:", dict(Counter(str(r.get('category', '')) for r in fx).most_common(8)))
print("[0.2] fixture names:", dict(Counter(str(r.get('name', '')) for r in fx).most_common(8)))
print("[0.2] fixture datetimes[:10]:", dict(Counter(str(_cv(r, 'datetime'))[:10] for r in fx).most_common(8)))
print("[0.2] sample fixture record:")
print("   ", json.dumps(fx[0], ensure_ascii=False)[:400])

# guest distinguishers available?
all_keys = Counter()
for r in records:
    for k in r.keys():
        all_keys[k] += 1
print("\n[guest] all top-level keys present (name -> count):")
for k, v in all_keys.most_common(40):
    print(f"        {v:7,}  {k}")

for cand in ("sessionId", "clientIP", "customValue.sessionId", "customValue.clientIP",
             "customValue.serviceIP", "customValue.accessId", "_id"):
    present = sum(1 for r in records if r.get(cand) not in (None, ""))
    print(f"[guest] distinguisher {cand!r}: {present:,} non-empty")
