from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE = "https://api.stackexchange.com/2.3/questions"
DISPLAY_START = "2020-01"


def month_iter(start_month: str, end_month: str) -> list[str]:
    sy, sm = map(int, start_month.split("-"))
    ey, em = map(int, end_month.split("-"))
    months: list[str] = []
    year, month = sy, sm
    while (year, month) <= (ey, em):
        months.append(f"{year}-{month:02d}")
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
    return months


def month_bounds(month: str) -> tuple[int, int]:
    year, month_num = map(int, month.split("-"))
    start = datetime(year, month_num, 1, tzinfo=timezone.utc)
    if month_num == 12:
        next_month = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        next_month = datetime(year, month_num + 1, 1, tzinfo=timezone.utc)
    end = int(next_month.timestamp()) - 1
    return int(start.timestamp()), end


def fetch_monthly_questions(start_month: str, end_month: str) -> list[dict]:
    rows = []
    for month in month_iter(start_month, end_month):
        fromdate, todate = month_bounds(month)
        params = urlencode(
            {
                "site": "stackoverflow",
                "fromdate": fromdate,
                "todate": todate,
                "pagesize": 0,
                "filter": "total",
                "sort": "creation",
            }
        )
        request = Request(f"{API_BASE}?{params}", headers={"User-Agent": "DeadInternetTracker/1.0"})
        with urlopen(request) as response:
            payload = json.load(response)
        rows.append(
            {
                "month": month,
                "questions": int(payload["total"]),
            }
        )
    return rows


def build_snapshot() -> dict:
    now = datetime.now(timezone.utc)
    latest_full_year = now.year if now.month > 1 else now.year - 1
    latest_full_month_num = now.month - 1 if now.month > 1 else 12
    latest_full_month = f"{latest_full_year}-{latest_full_month_num:02d}"
    month_rows = fetch_monthly_questions(DISPLAY_START, latest_full_month)

    snapshot = {
        "chartKey": "stack-overflow",
        "title": "Stack Overflow activity",
        "description": (
            "This tracks monthly new questions on Stack Overflow. "
            "It matters because it shows whether people are still asking other people for help in public."
        ),
        "source": "Stack Exchange API monthly question counts for Stack Overflow",
        "lastRefreshed": now.date().isoformat(),
        "method": (
            "Monthly question counts are pulled from the official Stack Exchange API using each month's creation-date window. "
            "The chart shows observed monthly counts only."
        ),
        "caveats": (
            "This is a public web proxy, not a measure of all problem-solving. "
            "This monthly feed currently covers questions asked, not answered-question counts."
        ),
        "xValues": [row["month"] for row in month_rows],
        "axisValueFormat": "compact",
        "tooltipValueFormat": "integer",
        "series": [
            {
                "name": "Questions asked",
                "color": "#7af59d",
                "values": [row["questions"] for row in month_rows],
            }
        ],
        "latestObservedMonth": month_rows[-1]["month"] if month_rows else None,
        "monthly": month_rows,
    }
    return snapshot


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    snapshot = build_snapshot()
    data_dir = root / "data" / "stackoverflow"
    data_dir.mkdir(parents=True, exist_ok=True)

    json_path = data_dir / "stackoverflow.json"
    js_path = data_dir / "stackoverflow.js"

    json_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    js_path.write_text(
        "window.__STACKOVERFLOW_SNAPSHOT__ = "
        + json.dumps(snapshot, indent=2)
        + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote {json_path}")
    print(f"Wrote {js_path}")


if __name__ == "__main__":
    main()
