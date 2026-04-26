from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


API_BASE = "https://wikimedia.org/api/rest_v1/metrics/editors/aggregate/en.wikipedia.org/user/content"
USER_AGENT = "DeadInternetTracker/1.0 (local dashboard research)"
DISPLAY_START = "2020-01"
ACTIVITY_LEVELS = {
    "all_editors": "all-activity-levels",
    "mid_editors": "5..24-edits",
    "core_editors": "25..99-edits",
    "very_active_editors": "100..-edits",
}


def fetch_monthly_series(activity_level: str) -> list[dict]:
    url = f"{API_BASE}/{activity_level}/monthly/20010101/20261231"
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req) as response:
        payload = json.load(response)
    return payload["items"][0]["results"]


def rows_to_map(rows: list[dict]) -> dict[str, int]:
    return {row["timestamp"][:7]: int(row["editors"]) for row in rows}


def build_snapshot() -> dict:
    now = datetime.now(timezone.utc)
    all_rows = fetch_monthly_series(ACTIVITY_LEVELS["all_editors"])
    mid_rows = fetch_monthly_series(ACTIVITY_LEVELS["mid_editors"])
    core_rows = fetch_monthly_series(ACTIVITY_LEVELS["core_editors"])
    very_active_rows = fetch_monthly_series(ACTIVITY_LEVELS["very_active_editors"])

    all_map = rows_to_map(all_rows)
    mid_map = rows_to_map(mid_rows)
    core_map = rows_to_map(core_rows)
    very_active_map = rows_to_map(very_active_rows)

    months = [month for month in sorted(all_map.keys()) if month >= DISPLAY_START]
    active_values = [
        mid_map.get(month, 0) + core_map.get(month, 0) + very_active_map.get(month, 0)
        for month in months
    ]

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
        "axisValueFormat": "compact",
        "tooltipValueFormat": "integer",
        "series": [
            {
                "name": "All editors",
                "color": "#58e6ff",
                "values": [all_map[month] for month in months],
            },
            {
                "name": "Active editors (5+)",
                "color": "#ff9a62",
                "values": active_values,
            },
        ],
        "latestObservedMonth": months[-1] if months else None,
    }
    return snapshot


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    snapshot = build_snapshot()
    data_dir = root / "data" / "wikipedia"
    data_dir.mkdir(parents=True, exist_ok=True)

    json_path = data_dir / "wikipedia.json"
    js_path = data_dir / "wikipedia.js"

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
