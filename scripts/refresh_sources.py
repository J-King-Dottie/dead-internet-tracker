"""Refresh sources independently and persist their actual next attempt times."""
from __future__ import annotations

import argparse
import calendar
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = Path("data/refresh_status.json")
SOURCES = {
    "stack-overflow": {"path": "data/stackoverflow/stackoverflow.json", "script": "refresh_stackoverflow.py", "day": 2},
    "traffic-bot-human": {"path": "data/cloudflare/cloudflare.json", "script": "refresh_cloudflare.py", "day": 2},
    "wikipedia": {"path": "data/wikipedia/wikipedia.json", "script": "refresh_wikipedia.py", "day": 10},
    "ai-content-meta-review": {"path": "data/ai-content-meta-review/ai_content_meta_review.json", "script": "refresh_ai_content_meta_review.py", "weekday": 0},
}


def iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_date(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def regular_window(key: str, now: datetime) -> tuple[datetime, datetime]:
    config = SOURCES[key]
    if "weekday" in config:
        previous = now.replace(hour=9, minute=30, second=0, microsecond=0) - timedelta(days=now.weekday())
        if previous > now:
            previous -= timedelta(days=7)
        return previous, previous + timedelta(days=7)
    previous = now.replace(day=config["day"], hour=10, minute=15, second=0, microsecond=0)
    if previous > now:
        prior_month = previous.replace(day=1) - timedelta(days=1)
        previous = previous.replace(year=prior_month.year, month=prior_month.month)
    next_month = previous.replace(day=1) + timedelta(days=calendar.monthrange(previous.year, previous.month)[1])
    return previous, previous.replace(year=next_month.year, month=next_month.month)


def expected_month(key: str, now: datetime) -> str:
    previous, _ = regular_window(key, now)
    return (previous.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def initial_state(root: Path, key: str, now: datetime) -> dict:
    snapshot = load_json(root / SOURCES[key]["path"])
    previous, following = regular_window(key, now)
    if "weekday" in SOURCES[key]:
        current = snapshot.get("lastRefreshed", "")[:10] >= previous.date().isoformat()
    else:
        current = snapshot.get("latestObservedMonth", "") >= expected_month(key, now)
    return {
        "status": "current" if current else "overdue",
        "latestObservedMonth": snapshot.get("latestObservedMonth"),
        "nextAttemptAt": iso(following if current else previous),
        "attemptKind": "scheduled" if current else "catch-up",
        "consecutiveFailures": 0,
    }


def validate_snapshot(key: str, snapshot: dict, previous: dict) -> None:
    if key == "ai-content-meta-review":
        if not snapshot.get("rows") or len(snapshot["rows"]) < len(previous.get("rows", [])):
            raise ValueError("Research snapshot is empty or lost existing rows")
        return
    labels, series = snapshot.get("xValues", []), snapshot.get("series", [])
    if not labels or not series or labels != sorted(set(labels)):
        raise ValueError("Missing or unordered chart data")
    latest = snapshot.get("latestObservedMonth", "")
    if not latest or latest < previous.get("latestObservedMonth", "") or latest != labels[-1]:
        raise ValueError("Snapshot would lose recent data")
    for item in series:
        values = item.get("values", [])
        if len(values) != len(labels) or values[-1] is None:
            raise ValueError("Incomplete chart series")
        if any(value is not None and (not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0) for value in values):
            raise ValueError("Invalid chart values")
    for index, old_series in enumerate(previous.get("series", [])):
        if index >= len(series):
            raise ValueError("Snapshot lost an existing series")
        new_values = dict(zip(labels, series[index]["values"]))
        for label, value in zip(previous.get("xValues", []), old_series.get("values", [])):
            if value is not None and new_values.get(label) is None:
                raise ValueError("Snapshot lost an existing observation")


def execute_refresh(root: Path, key: str) -> None:
    timeout = 4500 if key == "ai-content-meta-review" else 900
    subprocess.run([sys.executable, str(root / "scripts" / SOURCES[key]["script"])], cwd=root, check=True, timeout=timeout)


def retry_time(now: datetime) -> datetime:
    # The daily scheduler wakes at 10:15 UTC, two calendar days later.
    return (now + timedelta(days=2)).replace(hour=10, minute=15, second=0, microsecond=0)


def refresh_due_sources(root: Path, now: datetime, target: str = "due", force: bool = False, executor=execute_refresh) -> dict:
    original = load_json(root / STATE_PATH)
    state = dict(original)
    attempted, failed, waiting = [], [], []
    for key, config in SOURCES.items():
        record = dict(state.get(key) or initial_state(root, key, now))
        state[key] = record
        selected = target in ("due", "all") or (target == "monthly-api" and "day" in config) or target == key
        if not selected or (not force and parse_date(record["nextAttemptAt"]) > now):
            continue
        attempted.append(key)
        snapshot_path = root / config["path"]
        previous = load_json(snapshot_path)
        backup = {path: path.read_bytes() for path in snapshot_path.parent.glob("*") if path.is_file()}
        record["lastAttemptAt"] = iso(now)
        try:
            executor(root, key)
            snapshot = load_json(snapshot_path)
            validate_snapshot(key, snapshot, previous)
            record["lastSuccessfulFetchAt"] = iso(now)
            record["latestObservedMonth"] = snapshot.get("latestObservedMonth")
            record["consecutiveFailures"] = 0
            record.pop("lastError", None)
            if "day" in config and snapshot["latestObservedMonth"] < expected_month(key, now):
                record.update(status="waiting-for-source", nextAttemptAt=iso(retry_time(now)), attemptKind="catch-up")
                waiting.append(key)
            else:
                record.update(status="current", nextAttemptAt=iso(regular_window(key, now)[1]), attemptKind="scheduled")
        except Exception as error:
            # A partially written or invalid snapshot must never reach a commit.
            for path, content in backup.items():
                path.write_bytes(content)
            record.update(status="error", nextAttemptAt=iso(retry_time(now)), attemptKind="catch-up")
            record["consecutiveFailures"] = record.get("consecutiveFailures", 0) + 1
            # Do not publish raw exception messages, which may contain credentials.
            record["lastError"] = type(error).__name__
            failed.append(key)
            print(f"{key}: refresh failed ({type(error).__name__}); previous data retained.", flush=True)
        print(f"{key}: {record['status']}; next attempt {record['nextAttemptAt']}", flush=True)
    changed = state != original
    if changed:
        path = root / STATE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    return {"changed": changed, "attempted": attempted, "failed": failed, "waiting": waiting}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=["due", "all", "monthly-api", *SOURCES], default="due")
    parser.add_argument("--force", action="store_true", help="Attempt selected sources even before their next due date")
    args = parser.parse_args()
    result = refresh_due_sources(ROOT, datetime.now(timezone.utc), args.target, args.force)
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"changed={str(result['changed']).lower()}\nfailed={str(bool(result['failed'])).lower()}\n")
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        state = load_json(ROOT / STATE_PATH)
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("| Source | Result | Next attempt (UTC) |\n|---|---|---|\n")
            for key, record in state.items():
                handle.write(f"| {key} | {record['status']} | {record['nextAttemptAt']} |\n")
    print(json.dumps(result))
    # The workflow saves successful sources and retry state before reporting failure.
    if not os.environ.get("GITHUB_ACTIONS") and result["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()