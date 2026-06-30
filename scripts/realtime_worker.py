#!/usr/bin/env python3
"""
Near real-time API ingestion worker for ACGI.

This worker polls the configured API endpoint, normalizes events into the
pipeline input schema, deduplicates using event_id, stores checkpoint state,
and runs incremental Phase 1 processing on buffered batches.
"""

import argparse
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib import error, request

import sys

# Add src directory for importing pipeline module.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from phase1_data_processing import DataProcessingPipeline


ALLOWED_SERVICE_TYPES = {
    "restaurant",
    "hotel",
    "homestay",
    "tourist",
    "activity",
    "product",
    "knowledge",
    "business",
}

SERVICE_TYPE_MAP = {
    "route": "tourist",
    "travel": "tourist",
}

DEVICE_MAP = {
    "mobile": "Android",
    "android": "Android",
    "iphone": "IPhone",
    "ipad": "iPad",
    "web": "Web",
    "desktop": "Desktop",
}

OPERATION_MAP_FROM_DEVICE = {
    "Android": "Android",
    "IPhone": "IOS",
    "iPad": "IOS",
    "Web": "Windows",
    "Desktop": "Windows",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Near real-time ACGI ingestion worker")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--api-url", default="https://sdkapi.rcbt-sip.com/api/events", help="Events API URL")
    parser.add_argument("--api-key", default="", help="API key value (optional; prefer env in production)")
    parser.add_argument("--api-key-env", default="RCBT_API_KEY", help="Environment variable containing API key")
    parser.add_argument("--accept", default="application/json", help="Accept header value")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Polling interval in seconds")
    parser.add_argument("--request-timeout", type=float, default=5.0, help="HTTP timeout in seconds")
    parser.add_argument("--retry-max", type=int, default=3, help="Max retries per poll")
    parser.add_argument("--retry-backoff", type=float, default=1.0, help="Initial backoff seconds")
    parser.add_argument("--raw-output", default="output_raw.ndjson", help="Append-only raw NDJSON file")
    parser.add_argument("--state-path", default="outputs/realtime_state.json", help="Checkpoint/dedup state file")
    parser.add_argument("--batch-dir", default="outputs/realtime_batches", help="Temp batch NDJSON directory")
    parser.add_argument("--pipeline-output", default="outputs/realtime", help="Incremental pipeline output directory")
    parser.add_argument("--combined-output", default="outputs/realtime_UBLDF.ndjson", help="Combined incremental UBLDF NDJSON")
    parser.add_argument("--pipeline-min-interval", type=float, default=10.0, help="Minimum seconds between pipeline runs")
    parser.add_argument("--pipeline-batch-size", type=int, default=200, help="Run pipeline when buffer reaches this size")
    parser.add_argument("--max-seen-ids", type=int, default=50000, help="Maximum remembered event_ids for dedup")
    parser.add_argument("--once", action="store_true", help="Run one poll cycle and exit")
    return parser.parse_args()


def ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def parse_event_datetime(raw_value: Any) -> Optional[datetime]:
    if raw_value is None:
        return None

    text = str(raw_value).strip()
    if not text:
        return None

    # API sample: "2026-06-30 02:53:37.176"
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    # Fallback for ISO-like strings.
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def to_iso8601_z(dt: Optional[datetime]) -> str:
    if dt is None:
        return ""
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_service_type(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = SERVICE_TYPE_MAP.get(text, text)
    if text in ALLOWED_SERVICE_TYPES:
        return text
    return "product"


def normalize_device(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "Web"
    return DEVICE_MAP.get(text, "Web")


def normalize_operation(raw_operation: Any, normalized_device: str) -> str:
    op = str(raw_operation or "").strip()
    if op in {"IOS", "Android", "Windows", "MacOS", "Linux"}:
        return op
    return OPERATION_MAP_FROM_DEVICE.get(normalized_device, "Windows")


def build_pipeline_record(event: Dict[str, Any]) -> Optional[Tuple[datetime, Dict[str, Any]]]:
    event_id = str(event.get("event_id", "")).strip()
    dt = parse_event_datetime(event.get("event_datetime"))
    if not event_id or dt is None:
        return None

    category = str(event.get("category", "")).strip() or "Activity"
    event_name = str(event.get("event_name", "")).strip() or "unknown_event"
    service_name = str(event.get("service_name", "")).strip()

    normalized_device = normalize_device(event.get("device"))
    normalized_operation = normalize_operation(event.get("operation"), normalized_device)
    normalized_service_type = normalize_service_type(event.get("service_type"))

    lat = event.get("loc_lat")
    lon = event.get("loc_lon")
    location = None
    try:
        if lat is not None and lon is not None:
            lat_f = float(lat)
            lon_f = float(lon)
            if not (lat_f == 0.0 and lon_f == 0.0):
                location = {"lat": lat_f, "lon": lon_f}
    except (TypeError, ValueError):
        location = None

    record = {
        "_id": event_id,
        "category": category,
        "name": event_name,
        "customValue": {
            "datetime": to_iso8601_z(dt),
            "account": str(event.get("account", "Guest") or "Guest"),
            "serviceId": event.get("service_id", 0),
            "serviceName": service_name,
            "serviceType": normalized_service_type,
            "keyword": str(event.get("keyword", "") or ""),
            "location": location,
            "serviceIP": str(event.get("service_ip", "") or ""),
            "device": normalized_device,
            "operation": normalized_operation,
            "accessId": 1,
        },
        # Keep source fields for traceability.
        "source_event_id": event_id,
        "source_event_index": str(event.get("event_index", "")),
        "source_event_date": str(event.get("event_date", "")),
    }
    return dt, record


def load_state(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {
            "last_event_datetime": "",
            "seen_event_ids": [],
            "stats": {
                "poll_count": 0,
                "fetched_events": 0,
                "new_events": 0,
                "pipeline_runs": 0,
            },
        }

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "seen_event_ids" not in data:
                data["seen_event_ids"] = []
            if "stats" not in data:
                data["stats"] = {}
            return data
    except (OSError, json.JSONDecodeError):
        return {
            "last_event_datetime": "",
            "seen_event_ids": [],
            "stats": {},
        }


def save_state(path: str, state: Dict[str, Any]) -> None:
    ensure_parent_dir(path)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def append_ndjson(path: str, records: List[Dict[str, Any]]) -> None:
    if not records:
        return
    ensure_parent_dir(path)
    with open(path, "a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def fetch_events(api_url: str, api_key: str, accept: str, timeout_sec: float, retry_max: int, retry_backoff: float) -> List[Dict[str, Any]]:
    headers = {
        "accept": accept,
        "x-api-key": api_key,
    }

    last_error: Optional[Exception] = None
    backoff = retry_backoff

    for attempt in range(1, retry_max + 1):
        try:
            req = request.Request(api_url, method="GET", headers=headers)
            with request.urlopen(req, timeout=timeout_sec) as resp:
                body = resp.read().decode("utf-8")
                payload = json.loads(body)
                if isinstance(payload, list):
                    return [item for item in payload if isinstance(item, dict)]
                if isinstance(payload, dict):
                    # Common wrapper keys.
                    for key in ("events", "data", "results", "items"):
                        value = payload.get(key)
                        if isinstance(value, list):
                            return [item for item in value if isinstance(item, dict)]
                    # Single event fallback.
                    if payload.get("event_id"):
                        return [payload]
                return []
        except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < retry_max:
                time.sleep(backoff)
                backoff *= 2

    raise RuntimeError(f"Failed to fetch events after {retry_max} attempts: {last_error}")


def parse_checkpoint_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def filter_new_records(events: List[Dict[str, Any]], state: Dict[str, Any], max_seen_ids: int) -> List[Dict[str, Any]]:
    checkpoint = parse_checkpoint_datetime(str(state.get("last_event_datetime", "")))
    seen_ids = list(state.get("seen_event_ids", []))
    seen_lookup = set(seen_ids)

    accepted: List[Tuple[datetime, str, Dict[str, Any]]] = []

    for event in events:
        event_id = str(event.get("event_id", "")).strip()
        if not event_id or event_id in seen_lookup:
            continue

        normalized = build_pipeline_record(event)
        if normalized is None:
            continue
        dt, record = normalized

        # Incremental gating by datetime checkpoint.
        if checkpoint is not None and dt < checkpoint:
            continue

        accepted.append((dt, event_id, record))

    accepted.sort(key=lambda item: (item[0], item[1]))
    new_records = [item[2] for item in accepted]

    # Update state checkpoint and dedup cache.
    if accepted:
        last_dt = accepted[-1][0]
        state["last_event_datetime"] = to_iso8601_z(last_dt)
        for _, event_id, _ in accepted:
            seen_ids.append(event_id)
        if len(seen_ids) > max_seen_ids:
            seen_ids = seen_ids[-max_seen_ids:]
        state["seen_event_ids"] = seen_ids

    return new_records


def run_pipeline_for_batch(batch_records: List[Dict[str, Any]], config_path: str, batch_dir: str, pipeline_output: str, combined_output: str) -> int:
    if not batch_records:
        return 0

    os.makedirs(batch_dir, exist_ok=True)
    os.makedirs(pipeline_output, exist_ok=True)

    batch_ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    batch_path = os.path.join(batch_dir, f"batch_{batch_ts}.ndjson")
    append_ndjson(batch_path, batch_records)

    pipeline = DataProcessingPipeline(config_path, batch_path, pipeline_output)
    pipeline.run_full_pipeline()

    # Append latest incremental UBLDF result to cumulative realtime file.
    ubldf_path = os.path.join(pipeline_output, "UBLDF.json")
    appended = 0
    if os.path.exists(ubldf_path):
        try:
            with open(ubldf_path, "r", encoding="utf-8") as f:
                ubldf_rows = json.load(f)
            if isinstance(ubldf_rows, list) and ubldf_rows:
                append_ndjson(combined_output, ubldf_rows)
                appended = len(ubldf_rows)
        except (OSError, json.JSONDecodeError):
            appended = 0

    return appended


def process_cycle(args: argparse.Namespace, state: Dict[str, Any], pending_buffer: List[Dict[str, Any]], last_pipeline_run_ts: float) -> float:
    api_key = str(args.api_key or "").strip() or os.getenv(args.api_key_env, "").strip()
    if not api_key:
        raise RuntimeError(
            f"Missing API key. Provide --api-key or set environment variable: {args.api_key_env}"
        )

    events = fetch_events(
        api_url=args.api_url,
        api_key=api_key,
        accept=args.accept,
        timeout_sec=args.request_timeout,
        retry_max=args.retry_max,
        retry_backoff=args.retry_backoff,
    )

    state.setdefault("stats", {})
    state["stats"]["poll_count"] = int(state["stats"].get("poll_count", 0)) + 1
    state["stats"]["fetched_events"] = int(state["stats"].get("fetched_events", 0)) + len(events)

    new_records = filter_new_records(events, state, args.max_seen_ids)
    state["stats"]["new_events"] = int(state["stats"].get("new_events", 0)) + len(new_records)

    if new_records:
        append_ndjson(args.raw_output, new_records)
        pending_buffer.extend(new_records)

    now_ts = time.time()
    enough_time_elapsed = (now_ts - last_pipeline_run_ts) >= args.pipeline_min_interval
    enough_records_buffered = len(pending_buffer) >= args.pipeline_batch_size

    if pending_buffer and (enough_time_elapsed or enough_records_buffered or args.once):
        buffered = list(pending_buffer)
        pending_buffer.clear()
        appended = run_pipeline_for_batch(
            batch_records=buffered,
            config_path=args.config,
            batch_dir=args.batch_dir,
            pipeline_output=args.pipeline_output,
            combined_output=args.combined_output,
        )
        state["stats"]["pipeline_runs"] = int(state["stats"].get("pipeline_runs", 0)) + 1
        state["stats"]["last_pipeline_appended_rows"] = int(appended)
        last_pipeline_run_ts = now_ts

    save_state(args.state_path, state)
    return last_pipeline_run_ts


def print_startup(args: argparse.Namespace) -> None:
    print("=" * 72)
    print("ACGI Near Real-time Worker")
    print("=" * 72)
    print(f"API URL:               {args.api_url}")
    print(f"API key source:        {'--api-key' if str(args.api_key or '').strip() else args.api_key_env}")
    print(f"Poll interval:         {args.poll_interval}s")
    print(f"Pipeline min interval: {args.pipeline_min_interval}s")
    print(f"Pipeline batch size:   {args.pipeline_batch_size}")
    print(f"State path:            {args.state_path}")
    print(f"Raw output:            {args.raw_output}")
    print(f"Pipeline output:       {args.pipeline_output}")
    print(f"Combined output:       {args.combined_output}")
    print("=" * 72)


def main() -> None:
    args = parse_args()
    state = load_state(args.state_path)
    pending_buffer: List[Dict[str, Any]] = []
    last_pipeline_run_ts = 0.0

    print_startup(args)

    while True:
        try:
            last_pipeline_run_ts = process_cycle(args, state, pending_buffer, last_pipeline_run_ts)
            if args.once:
                break
            time.sleep(args.poll_interval)
        except KeyboardInterrupt:
            print("\nWorker stopped by user.")
            break
        except Exception as exc:
            print(f"[ERROR] {exc}")
            save_state(args.state_path, state)
            if args.once:
                raise
            time.sleep(max(args.poll_interval, 1.0))


if __name__ == "__main__":
    main()
