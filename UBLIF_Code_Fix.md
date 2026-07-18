# UBLIF — คู่มือแก้ไขโค้ด (Code Fix Guide)

> **สถานะตั้งต้น:** `sorted()` ล้มเงียบเพราะ tz ปนกัน (aware 95,423 / naive 5,338)
> → dedup window ไม่เคยทำงาน → ตัวเลขใน Table 4 เดิม **เป็นโมฆะทั้งตาราง**
> เอกสารนี้ครอบคลุมเฉพาะ **ส่วนโค้ด** เท่านั้น

---

## หลักการเดียวที่คุมทั้งแผน

> **ห้ามลบ record ทิ้ง — ให้ mark แล้วพาไปจนจบ**

ตัวเลขทุกตัวต้อง derive จาก **ledger** ได้ ไม่ใช่จาก `len()` ของ list ที่เหลือรอด
นี่คือสิ่งที่ทำให้ `assert X == ΣR + VR` เป็นจริงในโค้ด → survivorship ไม่มีที่ซ่อน

---

## ข้อเท็จจริงที่ยืนยันแล้ว (ใช้เป็น assertion ได้)

| ตัวเลข                     | ค่า           | ความหมาย                                            |
| -------------------------- | ------------- | --------------------------------------------------- |
| บรรทัดในไฟล์ดิบ            | 104,309       | ว่าง 0 · parse ไม่ได้ 0                             |
| **X**                      | **104,309**   | = 104,309 − 149                                     |
| tz-aware                   | 95,423        |                                                     |
| tz-naive                   | 5,338         | **→ ทำให้ `sorted()` โยน TypeError**                |
| unparseable = account ว่าง | 3,548         | **ชุดเดียวกันทั้งหมด** — ขาด `customValue` ทั้งก้อน |
| Cset เดิม                  | 43,736 (42%)  | ตัวเลขจาก pipeline ที่ sort ล้ม                     |
| R₂ / R₃ (Scenario B)       | 4,271 / 3,764 | รวม 8,035 = IR ✓                                    |

---

# Phase 0 — Freeze & Provenance (ทำก่อนแตะโค้ด)

## 0.1 ตรึงไฟล์ดิบ

```bash
sha256sum output_raw.ndjson > raw.sha256   # 104,309 บรรทัด
git init && git add -A && git commit -m "freeze: pre-rebuild state"
```

## 0.2 ⚠️ กฎระบุ fixture — งานสำคัญที่สุดใน Phase 0

ต้องได้ **กฎ deterministic ที่เขียนลงเปเปอร์ได้** ไม่ใช่ "จำได้ว่าตัวไหน"

```python
def is_fixture(r) -> bool:
    """ต้อง return True ครบ 149 ตัวพอดี ไม่ขาดไม่เกิน"""
    ...

fx = [r for r in records if is_fixture(r)]
assert len(fx) == 149, f"ได้ {len(fx)} ตัว — กฎยังไม่แม่น"
```

**ถ้าได้ 152 หรือ 147 → หยุดทุกอย่าง** แปลว่ายังมี fixture ที่หาไม่เจอ หรือกฎกิน record จริง

แนวทางหา marker:

```python
from collections import Counter
print(Counter(_acct(r) for r in fx))
print(Counter(str(r.get('serviceIP',''))[:8] for r in fx))
print(Counter(r.get('category','') for r in fx))
print(Counter((r.get('customValue') or {}).get('datetime','')[:10] for r in fx))
```

ถ้าไม่มี marker เลย → สร้างย้อนหลังไม่ได้ ต้องใช้ explicit record-ID list และเขียนในเปเปอร์ตรงๆ

> **⚠️ ถ้ากฎคือ `account` ขึ้นต้นด้วย `test`/`admin`** → Alg1a กินอยู่แล้วโดยอัตโนมัติ
> **ต้องจำไว้ตอนออกแบบ fault injection (Phase 4.3)** — record ที่ inject ห้ามใช้ account แบบนี้

เขียนกฎที่ได้ลง `fixtures.py` + commit

## 0.3 ตรวจว่า fixture ไม่ทับกับ 3,548

```python
assert not ({id(r) for r in fx} & {id(r) for r in records if _dt(r) is None})
```

## 0.4 ปิดตัวเลขที่ยังค้าง 2 ตัว

```python
keys = {(_acct(r), _sid(r), r.get('name',''), r.get('category','')) for r in records}
print(f"unique keys = {len(keys)}   vs   Cset เดิม = 43,736")
print(f"duplicates_removed = {self.stats['duplicates_removed']}   vs   R1 เดิม = 60,424")
```

| ผล                   | แปลว่า                                                                         |
| -------------------- | ------------------------------------------------------------------------------ |
| `len(keys) ≈ 43,736` | ✅ ยืนยัน 58% = **global dedup artifact** → หลังแก้ bug ข้อมูลจะกลับมาเกือบหมด |
| `len(keys) ≫ 43,736` | มีกฎอื่นร่วมลบ → ต้องแยกด้วย rule attribution (Phase 3)                        |

## 0.5 🔴 ตรวจ timezone จริงของ naive 5,338 — ห้ามเดา

```python
from collections import Counter
def plat(r): return r.get('platform') or r.get('source') or r.get('category','?')
print("naive:", Counter(plat(r) for r in records if (d:=_dt(r)) and d.tzinfo is None))
print("aware:", Counter(plat(r) for r in records if (d:=_dt(r)) and d.tzinfo is not None))
```

**ห้าม `replace(tzinfo=utc)` มั่ว** — แพลตฟอร์มท่องเที่ยวไทยที่ไม่ส่ง tz แทบแน่นอนว่าเป็น **Asia/Bangkok (UTC+7)**
ถ้ายัด UTC เข้าไป → **timestamp เลื่อน 7 ชั่วโมง** → dedup window ผิด → temporal analysis ผิดทั้งหมด (bug ตัวใหม่ที่เนียนกว่าเดิม)

**วิธีตรวจ:** ดู distribution รายชั่วโมง — ถ้า peak อยู่ตี 2–3 (ตีความเป็น UTC) = จริงๆ คือ 9–10 โมงเช้าเวลาไทย → ยืนยัน UTC+7

## 0.6 ตรวจว่า `name` / `category` เก็บอะไร

```python
print(Counter(r.get('name','') for r in records).most_common(20))
print(Counter(r.get('category','') for r in records).most_common(20))
```

- ถ้า `name="view_hotel"`, `category="hotel"` → **item ID ไม่อยู่ใน key** → คนเทียบโรงแรม A vs B ใน 1 วินาที โดนลบ 1 ตัว = **false rejection** → ต้องเพิ่ม `itemId` เข้า key
- ถ้ามี item ID อยู่แล้ว → ไม่ต้องเพิ่ม

---

# Phase 1 — แก้ Bug

## 🔧 Fix 1: `get_timestamp` → อ่านอย่างเดียว ห้ามซ่อน ห้ามยุบ

```python
from datetime import datetime
from zoneinfo import ZoneInfo

SOURCE_TZ = ZoneInfo("Asia/Bangkok")   # ← ยืนยันจาก Phase 0.5 ก่อนเท่านั้น

def parse_dt(record):
    """return (datetime|None, status). ห้ามเขียนค่ากลับลง record."""
    cv = record.get('customValue') or {}
    s = (record.get('customValue.datetime')
         or (cv.get('datetime') if isinstance(cv, dict) else '')
         or '')
    if not s:
        return None, 'missing'
    try:
        dt = datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return None, 'unparseable'          # ❌ ห้าม return datetime.min
    if dt.tzinfo is None:
        return dt.replace(tzinfo=SOURCE_TZ), 'naive_localized'
    return dt, 'aware'
```

**3 อย่างที่แก้:**

| เดิม                   | ใหม่            | ผล                                              |
| ---------------------- | --------------- | ----------------------------------------------- |
| `return datetime.min`  | `return None`   | 3,548 เลิกกระจุกที่จุดเดียว → เลิกถูก dedup กิน |
| `except: pass` (เงียบ) | นับ + tag       | unparseable กลายเป็นตัวเลขที่รายงานได้          |
| tz ปนกัน               | localize ทุกตัว | **`sorted()` ไม่มีทางล้ม**                      |

> **❗ กฎเหล็ก: `parse_dt` ห้ามเขียนค่าที่ normalize แล้วกลับลง record**
> ไม่งั้น Alg2 จะตรวจ ISO 8601 บนค่าที่ถูกซ่อมแล้ว = tautology เดิมกลับมา

## 🔧 Fix 2: `remove_duplicates` → เขียนใหม่ทั้งฟังก์ชัน

```python
def dedup(self, records):
    if not self.remove_duplicates_enabled:
        return records

    dated, undated = [], []
    for r in records:
        dt, status = parse_dt(r)
        r['_ts'], r['_ts_status'] = dt, status
        (dated if dt else undated).append(r)

    # ❌ ห้ามมี try/except — ถ้า sort ล้ม ต้องล้มดัง ไม่ใช่ข้ามเงียบ
    dated.sort(key=lambda r: r['_ts'])

    seen = {}
    for r in dated:
        k = self.dedup_key(r)
        if k is None:                       # dedup ใช้ไม่ได้กับ record นี้
            mark(r, 'alg1b', 'pass', 'not_applicable')
            continue
        if k in seen:
            diff = (r['_ts'] - seen[k]['_ts']).total_seconds()
            assert diff >= 0, "sorted แล้วต้องไม่ติดลบ"
            if 0 <= diff <= self.duplicate_window_seconds:      # ✅ มีขอบล่าง
                mark(r, 'alg1b', 'drop', 'duplicate_window', f'diff={diff:.3f}s')
                r['_dup_of'] = seen[k]
                r['_dup_identical'] = (payload(r) == payload(seen[k]))   # ← ground truth
                self.stats['duplicates_removed'] += 1
                continue
        seen[k] = r
        mark(r, 'alg1b', 'pass', 'unique_in_window')

    # ✅ undated ไม่เข้า dedup แต่ส่งต่อให้ Alg2 ตรวจ → R2 > 0 ทันที
    for r in undated:
        mark(r, 'alg1b', 'pass', f'skipped:{r["_ts_status"]}')

    return dated + undated
```

**`payload()`** = ทุกฟิลด์เนื้อหายกเว้น timestamp/`_id` → ใช้ตัดสินว่าเป็น retry artifact หรือคนละ event จริง

## 🔧 Fix 3: `dedup_key` → guest ห้ามยุบข้ามคน

```python
def dedup_key(self, r):
    cv = r.get('customValue') or {}
    g = lambda f: r.get(f'customValue.{f}') or (cv.get(f) if isinstance(cv, dict) else '') or ''

    account = g('account')
    if not account:
        sess = r.get('sessionId') or r.get('clientIP')
        if not sess:
            return None                      # ✅ ไม่มีตัวแยกคน → ไม่ dedup เลย (conservative)
        account = f'__anon__{sess}'

    return (account, g('serviceId'), r.get('name', ''), r.get('category', ''), g('itemId'))
```

> `itemId` ใส่หรือไม่ ขึ้นกับผล Phase 0.6

## 🔧 Fix 4: semantics ของ window ต้องประกาศ

โค้ดเดิมอัปเดต anchor **เฉพาะตอน keep** → เป็น **fixed-anchor window** ไม่ใช่ sliding
(A@0 keep → B@0.9 drop → C@1.5 keep เพราะเทียบกับ 0 ไม่ใช่ 0.9)

ไม่ผิด แต่ต้องเขียนในเปเปอร์ให้ตรงกับโค้ด และ threshold sweep ต้องระบุ semantics ที่ใช้

---

# Phase 2 — จัดโครงสถาปัตยกรรมใหม่

**รากของปัญหาคือกฎอยู่ผิด layer**

```
raw file (104,309)
  ├─ is_fixture() ──→ F (149)  ─────────→ Fault Injection Experiment (แยกออกไป)
  └─ X (104,160)
       ↓ Alg0   Field Mapping เท่านั้น (ห้ามซ่อมค่า!)          [no drop]
       ↓ Alg1a  Provenance Filter: test/admin, bot/crawler      → R1a
       ↓ Alg1b  Deduplication (windowed, tz-aware)              → R1b
       ↓ Alg2   Standards + Completeness                        → R2
       ↓ Alg2b  Repair (format date ฯลฯ) [รายงาน repair count]  [no drop]
       ↓ Alg3a  Compliance Verify (enforce 2 / flag 3)          → R3
       ↓ Alg3b  Privacy Transform (hash/mask/truncate)          [no drop]
       └─ VR
```

$$X = R_{1a} + R_{1b} + R_2 + R_3 + VR$$

## ตารางการย้ายกฎ

| กฎ                                  | เดิมอยู่     | ย้ายไป                | เหตุผล                                             |
| ----------------------------------- | ------------ | --------------------- | -------------------------------------------------- |
| `Format Date` (Alg1 บรรทัด 13)      | Alg1         | **Alg2b (หลัง Alg2)** | 🔴 ซ่อมก่อนตรวจ = tautology → **นี่คือต้นตอ R₂=0** |
| `Map Fields` (Alg1 บรรทัด 12)       | Alg1         | Alg0                  | เป็น structural ไม่ใช่ filter                      |
| `No Service ID` (Alg1 บรรทัด 9–10)  | Alg1         | **Alg2**              | เป็น completeness check = งานของ Alg2              |
| **missing `customValue`** (3,548)   | ไม่มีใครตรวจ | **Alg2**              | ควรถูกนับเป็น R₂ ไม่ใช่ถูก dedup กิน               |
| `Device IEEE 802.1AR` (Alg2 12–14)  | Alg2         | **ลบทิ้ง**            | dead code — Table 2 บอกเองว่าข้อมูลไม่มี           |
| `Identifier ISO 26324` (Alg2 15–17) | Alg2         | **ลบทิ้ง**            | dead code — fixtures ก็ไม่มี                       |
| `Hashing & Masking` (Alg3 บรรทัด 6) | Alg3 กลาง    | **Alg3b (ท้ายสุด)**   | 🔴 ทำแล้วตรวจตัวเอง (บรรทัด 14) = self-validation  |

> **การย้าย 4 อย่างแรก → $R_2 > 0$ ทันที → VE กลายเป็นตัวเลขที่มีความหมายเป็นครั้งแรก**

---

# Phase 3 — Record-level Ledger (การเปลี่ยนแปลงที่คุ้มที่สุด)

```python
def mark(r, stage, decision, rule, detail=''):
    r.setdefault('_trace', []).append({
        'stage': stage,            # alg0|alg1a|alg1b|alg2|alg3a
        'decision': decision,      # pass|drop|flag
        'rule': rule,
        'detail': detail,
    })

def dropped_at(r):
    for t in r['_trace']:
        if t['decision'] == 'drop':
            return t['stage'], t['rule']
    return None, None

def flags(r):
    return [t['rule'] for t in r['_trace'] if t['decision'] == 'flag']
```

## ของฟรีที่ได้จาก ledger ทันที (ไม่ต้องรันเพิ่ม)

| ต้องการ                                     | ได้จาก                                                                      |
| ------------------------------------------- | --------------------------------------------------------------------------- |
| **Accounting identity**                     | `Counter(dropped_at(r)[0] for r in X)` → พิสูจน์ $X = \sum R_s + VR$ ในโค้ด |
| **Rule attribution** (แก้ order-dependency) | รันทุกกฎแบบ **ไม่ short-circuit** → รู้ว่ากฎไหนตัดเท่าไร + overlap          |
| **Flag rate (Eq.8)**                        | `Counter(f for r in VR for f in flags(r))`                                  |
| Test A (tag ของ 4,271)                      | `Counter(dropped_at(r)[1] for r in R2)`                                     |
| Test B (membership 3,764)                   | set intersection ระหว่าง scenario                                           |
| **Duplicate identity test**                 | `r['_dup_identical']` จาก Fix 2                                             |

> **⚠️ order-dependency ที่ต้องแก้:** โค้ดเดิมตรวจ `duplicate` **ก่อน** `bot`
> → bot ที่ยิง 500 event/วินาที ถูกนับเป็น **"duplicate"** ไม่ใช่ "bot"
> → สถิติ bot ต่ำเกินจริง, duplicate สูงเกินจริง
> **แก้:** รันทุกกฎแบบอิสระ บันทึกทุกกฎที่ติด แล้วค่อยตัดสิน

## assertion บังคับ

```python
assert len(X) == sum(len(R) for R in [R1a, R1b, R2, R3]) + len(VR)
assert all('_trace' in r for r in X)
```

---

# Phase 4 — Experiment Harness

## 4.1 Ablation 2×2 (แทน A vs B ที่ confounded)

```python
SCENARIOS = {
  'A': dict(provenance=True,  dedup=True ),   # เดิม
  'B': dict(provenance=False, dedup=False),   # เดิม
  'C': dict(provenance=False, dedup=True ),   # ⭐ ใหม่ — dedup อย่างเดียว
  'D': dict(provenance=True,  dedup=False),   # ⭐ ใหม่ — provenance อย่างเดียว
}
```

รายงาน **marginal contribution**: $PY_A - PY_C$ (ผลของ provenance) และ $PY_A - PY_D$ (ผลของ dedup)
❌ ไม่ใช่ $PY_A - PY_B$ ซึ่งคือสิ่งที่บรรณาธิการเรียกว่า tautological

## 4.2 Threshold Sweep (มี `duplicate_window_seconds` อยู่แล้ว)

```python
for w in [0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 30.0]:
    run(duplicate_window_seconds=w)   # → PY, retention, %identical, ข้อสรุปหลัก
```

เปลี่ยน "1 วินาที" จากตัวเลขลอยๆ → ตัวเลขที่มีเหตุผล (เลือกจากจุดที่ curve หักศอก)

## 4.3 Fault Injection (= external ground truth)

**เงื่อนไขบังคับ 4 ข้อ — พลาดข้อเดียวการทดลองเป็นโมฆะ:**

1. ❗ `account` **ห้าม**ขึ้นต้นด้วย `test`/`admin` → Alg1a จะกินก่อนถึง Alg2
2. ❗ ต้อง **ข้าม Alg2b (repair)** → ไม่งั้น `Format Date` ซ่อม violation ที่เพิ่ง inject
3. ❗ synthetic records **ห้ามอยู่ในตัวส่วนของ metric ใดๆ** ที่รายงานข้อมูลจริง
4. ❗ ต้องมี **clean control** เพื่อวัด false positive

```python
FIXTURE_SPEC = [
  ('date_not_iso8601',  30, lambda r: set_field(r, 'customValue.datetime', '15/01/2024 10:30')),
  ('geo_out_of_range',  30, lambda r: set_geo(r, 95.7, 200.4)),
  ('ipv4_malformed',    30, lambda r: set_field(r, 'serviceIP', '999.1.1.1')),
  ('ipv6_malformed',    30, lambda r: set_field(r, 'serviceIP', '2001:zzzz::1')),
  ('missing_serviceid', 30, lambda r: del_field(r, 'customValue.serviceId')),
  ('clean_control',     30, lambda r: r),      # ← ต้องผ่าน 100%
]
```

→ ได้ **recall / precision ต่อ check** โดยรู้ label แน่นอน 100% เพราะสร้างเอง

## 4.4 Baseline

| Layer            | Baseline ที่เทียบได้                                  | เทียบด้วยอะไร                                            |
| ---------------- | ----------------------------------------------------- | -------------------------------------------------------- |
| **Data quality** | rule-based (IQR / z-score), Great Expectations, Deequ | true-noise ที่จับได้ vs good records ที่เสียไป (จาก 4.3) |
| **Provenance**   | bot filter สำเร็จรูป / user-agent blocklist           | recall บน bot ที่ label ได้                              |
| **Legal layer**  | ⚠️ น่าจะไม่มีของเทียบ                                 | → feature comparison เชิงคุณภาพ + ประกาศเป็น novelty     |

---

# ✅ Checklist

## Phase 0 — Freeze

- [ ] 0.1 hash ไฟล์ดิบ + git commit
- [ ] 0.2 `is_fixture()` → **assert = 149**
- [ ] 0.3 fixture ไม่ทับ 3,548
- [ ] 0.4 `len(keys)` + `duplicates_removed`
- [ ] 0.5 **ยืนยัน timezone จริงของ naive 5,338** (อย่าเดา UTC)
- [ ] 0.6 ตรวจ `name` / `category` → ต้องมี itemId ใน key ไหม

## Phase 1 — Bug fixes

- [ ] 1.1 `parse_dt` → `None` + status · ห้ามเขียนกลับ · ห้าม `datetime.min`
- [ ] 1.2 `dedup` → sort ไม่มี try/except · ขอบล่าง `0 <= diff` · undated bypass
- [ ] 1.3 `dedup_key` → `__anon__` / `None`
- [ ] 1.4 ประกาศ fixed-anchor semantics

## Phase 2 — Architecture

- [ ] 2.1 ย้าย `Format Date` → Alg2b **(สำคัญที่สุด — ต้นตอ R₂=0)**
- [ ] 2.2 ย้าย `Map Fields` → Alg0
- [ ] 2.3 ย้าย `No Service ID` + missing `customValue` → Alg2
- [ ] 2.4 ลบ Alg2 บรรทัด 12–17 (Device, DOI)
- [ ] 2.5 ย้าย `Hashing & Masking` → Alg3b (ท้ายสุด)

## Phase 3 — Ledger

- [ ] 3.1 `mark()` + `_trace` ทุก stage
- [ ] 3.2 `assert X == ΣR + VR`
- [ ] 3.3 `_dup_of` + `_dup_identical`
- [ ] 3.4 รันกฎแบบไม่ short-circuit (แก้ order-dependency)

## Phase 4 — Experiments

- [ ] 4.1 scenarios A/B/C/D
- [ ] 4.2 threshold sweep
- [ ] 4.3 fault injection (ครบ 4 เงื่อนไข)
- [ ] 4.4 baseline
- [ ] **รันใหม่ทั้งหมด → ตัวเลขจริงชุดแรกของโปรเจกต์**

---
