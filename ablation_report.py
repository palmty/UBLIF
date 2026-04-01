"""Ablation / what-if metrics report.

This script compares record rejection/compliance rates under different
pipeline variants using the same raw NDJSON input.

Scenarios:
  A) stream_clean + UBIF + legal
  B) stream_clean + legal (skip UBIF)
  C) UBIF + legal (no stream_clean)
  D) legal only (raw)

Notes:
- "stream_clean" here uses DataCleaner.stream_process_record() (drops records
  early for missing serviceId / duplicates / etc.).
- "UBIF" uses UBIFValidator.validate_record() and rejects records with
  violations.
- "legal" uses ComputerCrimeActChecker.check_record() to count threats/flagging.

The purpose is to make it easy to quantify whether 0% rejection / 100%
compliance is driven by upstream cleaning, lenient validation rules, or
truly-clean data.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

from src.utils.data_cleaner import DataCleaner
from src.utils.legal_compliance import ComputerCrimeActChecker
from src.utils.ubif_validator import UBIFValidator


@dataclass
class ScenarioResult:
    name: str
    total_lines: int
    json_errors: int
    kept_after_stream_clean: int
    dropped_by_stream_clean: int
    ubif_validated: int
    ubif_valid: int
    ubif_rejected: int
    legal_checked: int
    legal_flagged: int
    legal_clean: int
    elapsed_seconds: float

    @property
    def ubif_rejection_rate_pct(self) -> float:
        if self.ubif_validated <= 0:
            return 0.0
        return (self.ubif_rejected / self.ubif_validated) * 100.0

    @property
    def compliance_rate_pct(self) -> float:
        if self.legal_checked <= 0:
            return 0.0
        return (self.legal_clean / self.legal_checked) * 100.0

    @property
    def overall_success_rate_pct(self) -> float:
        """Records that pass everything that is enabled in the scenario.

        If UBIF is enabled: denominator is ubif_validated.
        If UBIF is disabled: denominator is legal_checked.
        """

        if self.ubif_validated > 0:
            denom = self.ubif_validated
            numer = min(self.ubif_valid, self.legal_clean)
        else:
            denom = self.legal_checked
            numer = self.legal_clean
        if denom <= 0:
            return 0.0
        return (numer / denom) * 100.0


def iter_ndjson(path: Path) -> Iterator[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def run_scenario(
    *,
    name: str,
    config_path: Path,
    input_path: Path,
    stream_clean: bool,
    ubif: bool,
    legal: bool,
    limit: Optional[int] = None,
) -> ScenarioResult:
    start = time.perf_counter()

    data_cleaner = DataCleaner(str(config_path))
    ubif_validator = UBIFValidator(str(config_path)) if ubif else None
    crime_checker = ComputerCrimeActChecker() if legal else None

    total_lines = 0
    json_errors = 0
    kept_after_stream_clean = 0
    dropped_by_stream_clean = 0

    ubif_validated = 0
    ubif_valid = 0
    ubif_rejected = 0

    legal_checked = 0
    legal_flagged = 0
    legal_clean = 0

    with input_path.open("r", encoding="utf-8") as f:
        for line in f:
            if limit is not None and total_lines >= limit:
                break

            total_lines += 1
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                json_errors += 1
                continue

            if stream_clean:
                processed = data_cleaner.stream_process_record(record)
                if processed is None:
                    dropped_by_stream_clean += 1
                    continue
                record = processed

            kept_after_stream_clean += 1

            if ubif and ubif_validator is not None:
                ubif_validated += 1
                is_valid, _violations = ubif_validator.validate_record(record)
                if is_valid:
                    ubif_valid += 1
                else:
                    ubif_rejected += 1
                    # If rejected by UBIF, do not check legal compliance
                    continue

            if legal and crime_checker is not None:
                legal_checked += 1
                is_clean, threats = crime_checker.check_record(record)
                if is_clean:
                    legal_clean += 1
                else:
                    legal_flagged += 1

    elapsed = time.perf_counter() - start

    return ScenarioResult(
        name=name,
        total_lines=total_lines,
        json_errors=json_errors,
        kept_after_stream_clean=kept_after_stream_clean,
        dropped_by_stream_clean=dropped_by_stream_clean,
        ubif_validated=ubif_validated,
        ubif_valid=ubif_valid,
        ubif_rejected=ubif_rejected,
        legal_checked=legal_checked,
        legal_flagged=legal_flagged,
        legal_clean=legal_clean,
        elapsed_seconds=elapsed,
    )


def print_table(results: List[ScenarioResult]) -> None:
    headers = [
        "Scenario",
        "Lines",
        "JSONerr",
        "Kept",
        "Dropped",
        "UBIF_validated",
        "UBIF_rejected(%)",
        "Legal_checked",
        "Legal_flagged",
        "Compliance(%)",
        "OverallSuccess(%)",
        "Sec",
    ]

    rows: List[List[str]] = []
    for r in results:
        rows.append(
            [
                r.name,
                str(r.total_lines),
                str(r.json_errors),
                str(r.kept_after_stream_clean),
                str(r.dropped_by_stream_clean),
                str(r.ubif_validated),
                f"{r.ubif_rejection_rate_pct:.2f}%",
                str(r.legal_checked),
                str(r.legal_flagged),
                f"{r.compliance_rate_pct:.2f}%",
                f"{r.overall_success_rate_pct:.2f}%",
                f"{r.elapsed_seconds:.2f}",
            ]
        )

    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def fmt_row(cols: List[str]) -> str:
        return " | ".join(c.ljust(widths[i]) for i, c in enumerate(cols))

    print(fmt_row(headers))
    print("-+-".join("-" * w for w in widths))
    for row in rows:
        print(fmt_row(row))


def main() -> int:
    parser = argparse.ArgumentParser(description="Ablation / what-if metrics report")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--input", default="output_raw.ndjson", help="Path to raw NDJSON")
    parser.add_argument("--limit", type=int, default=None, help="Optional record limit")
    args = parser.parse_args()

    config_path = Path(args.config)
    input_path = Path(args.input)

    results: List[ScenarioResult] = []

    results.append(
        run_scenario(
            name="A stream_clean+UBIF+legal",
            config_path=config_path,
            input_path=input_path,
            stream_clean=True,
            ubif=True,
            legal=True,
            limit=args.limit,
        )
    )

    results.append(
        run_scenario(
            name="B stream_clean+legal (no UBIF)",
            config_path=config_path,
            input_path=input_path,
            stream_clean=True,
            ubif=False,
            legal=True,
            limit=args.limit,
        )
    )

    results.append(
        run_scenario(
            name="C UBIF+legal (raw)",
            config_path=config_path,
            input_path=input_path,
            stream_clean=False,
            ubif=True,
            legal=True,
            limit=args.limit,
        )
    )

    results.append(
        run_scenario(
            name="D legal only (raw)",
            config_path=config_path,
            input_path=input_path,
            stream_clean=False,
            ubif=False,
            legal=True,
            limit=args.limit,
        )
    )

    print_table(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
