from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request

from http_json import request_json


API_BASE = "https://wikimedia.org/api/rest_v1/metrics/editors/aggregate/en.wikipedia.org/user/content"
USER_AGENT = "DeadInternetTracker/1.0 (local dashboard research)"
REQUEST_TIMEOUT_SECONDS = 60
DISPLAY_START = "2020-01"
ACTIVITY_LEVELS = {
    "all_editors": "all-activity-levels",
    "mid_editors": "5..24-edits",
    "core_editors": "25..99-edits",
    "very_active_editors": "100..-edits",
}


def fetch_monthly_series(activity_level: str, start_month: str, last_day: datetime) -> list[dict]:
    # Usually just two or three months. Split a first-time bootstrap or a long
    # catch-up into annual requests rather than one expensive full-history query.
    rows = []
    end_exclusive = (last_day.replace(day=28) + timedelta(days=4)).replace(day=1)
    for year in range(int(start_month[:4]), last_day.year + 1):
        start = max(f"{year}0101", start_month.replace("-", "") + "01")
        # Monthly buckets require the following month's boundary. December 31
        # would omit December, just as August 31 omits August.
        end = min(f"{year + 1}0101", end_exclusive.strftime("%Y%m%d"))
        url = f"{API_BASE}/{activity_level}/monthly/{start}/{end}"
        req = Request(url, headers={"User-Agent": USER_AGENT})
        payload = request_json(req, timeout=REQUEST_TIMEOUT_SECONDS)
        rows.extend(payload["items"][0]["results"])
    if not rows:
        raise RuntimeError(f"No Wikimedia data for {activity_level}")
    return rows


def rows_to_map(rows: list[dict]) -> dict[str, int]:
    return {row["timestamp"][:7]: int(row["editors"]) for row in rows}


def build_snapshot(previous: dict | None = None, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    previous = previous or {}
    last_day = now.replace(day=1) - timedelta(days=1)
    start_month = DISPLAY_START
    if latest := previous.get("latestObservedMonth"):
        # Recheck the last two saved months for revisions, plus any missing ones.
        overlap = datetime.strptime(latest, "%Y-%m") - timedelta(days=1)
        start_month = max(DISPLAY_START, overlap.strftime("%Y-%m"))
    print(f"Wikimedia: fetching {start_month} through {last_day:%Y-%m}; keeping earlier history", flush=True)
    all_rows = fetch_monthly_series(ACTIVITY_LEVELS["all_editors"], start_month, last_day)
    mid_rows = fetch_monthly_series(ACTIVITY_LEVELS["mid_editors"], start_month, last_day)
    core_rows = fetch_monthly_series(ACTIVITY_LEVELS["core_editors"], start_month, last_day)
    very_active_rows = fetch_monthly_series(ACTIVITY_LEVELS["very_active_editors"], start_month, last_day)

    all_map = rows_to_map(all_rows)
    mid_map = rows_to_map(mid_rows)
    core_map = rows_to_map(core_rows)
    very_active_map = rows_to_map(very_active_rows)

    months = [month for month in sorted(all_map.keys()) if month >= start_month]
    current_month = now.strftime("%Y-%m")
    months = [month for month in months if month < current_month]
    if not months or any(month not in cohort for month in months for cohort in (mid_map, core_map, very_active_map)):
        raise RuntimeError("Incomplete Wikimedia editor cohorts; retaining the previous snapshot")
    saved_series = {item["name"]: dict(zip(previous.get("xValues", []), item["values"])) for item in previous.get("series", [])}
    all_values = saved_series.get("All editors", {})
    active_values = saved_series.get("Active editors (5+)", {})
    for month in months:
        all_values[month] = all_map[month]
        active_values[month] = mid_map[month] + core_map[month] + very_active_map[month]
    months = sorted(all_values)
    # Missing API months must not become a silent gap in the chart.
    cursor = datetime.strptime(DISPLAY_START, "%Y-%m")
    expected_months = []
    while cursor.strftime("%Y-%m") <= months[-1]:
        expected_months.append(cursor.strftime("%Y-%m"))
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
    if months != expected_months or any(month not in active_values for month in months):
        raise ValueError("Incomplete Wikimedia monthly history")

    snapshot = {
        "chartKey": "wikipedia",
        "title": "Wikipedia activity",
        "description": (
            "This tracks monthly human editors on English Wikipedia content pages. "
            "It matters because it shows whether people are still doing sustained public knowledge work."
        ),
        "source": "Wikimedia editor analytics for en.wikipedia.org content pages",
        "lastRefreshed": now.date().isoformat(),
        "method": (
            "Active editors are users making 5 or more edits in a month. "
            "The chart shows observed monthly counts only."
        ),
        "caveats": (
            "This is English Wikipedia only, not all Wikipedias. "
            "It measures editor participation, not article quality or total knowledge output."
        ),
        "xValues": months,
        "axisValueFormat": "integer",
        "tooltipValueFormat": "integer",
        "series": [
            {
                "name": "All editors",
                "color": "#58e6ff",
                "values": [all_values[month] for month in months],
            },
            {
                "name": "Active editors (5+)",
                "color": "#ff9a62",
                "values": [active_values[month] for month in months],
            },
        ],
        "latestObservedMonth": months[-1] if months else None,
    }
    return snapshot


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    data_dir = root / "data" / "wikipedia"
    data_dir.mkdir(parents=True, exist_ok=True)

    json_path = data_dir / "wikipedia.json"
    js_path = data_dir / "wikipedia.js"
    previous = json.loads(json_path.read_text(encoding="utf-8")) if json_path.exists() else {}
    snapshot = build_snapshot(previous)

    json_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    js_path.write_text(
        "window.__WIKIPEDIA_SNAPSHOT__ = "
        + json.dumps(snapshot, indent=2)
        + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote {json_path}")
    print(f"Wrote {js_path}")


if __name__ == "__main__":
    main()
