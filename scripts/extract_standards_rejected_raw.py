import argparse
import json
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE_ROOT))

from src.utils.ubif_validator import UBIFValidator


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract UBIF (data standards) rejected records from raw NDJSON"
    )
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--input", default="output_raw.ndjson", help="Path to raw NDJSON")
    parser.add_argument(
        "--output",
        default="outputs/standards_rejected_raw.json",
        help="Path to output JSON file",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit of records to scan",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    input_path = Path(args.input)
    output_path = Path(args.output)

    validator = UBIFValidator(str(config_path))

    rejected_records = []
    total_lines = 0

    with input_path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if args.limit is not None and total_lines >= args.limit:
                break
            total_lines += 1

            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            is_valid, violations = validator.validate_record(record)
            if not is_valid:
                rejected_records.append(
                    {
                        "line_number": line_number,
                        "record": record,
                        "violations": violations,
                    }
                )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(rejected_records, f, indent=2, ensure_ascii=False)

    print(f"Total lines scanned: {total_lines}")
    print(f"Rejected records: {len(rejected_records)}")
    print(f"Output file: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
