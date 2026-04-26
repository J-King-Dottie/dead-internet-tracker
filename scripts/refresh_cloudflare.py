from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE = "https://api.cloudflare.com/client/v4"
DISPLAY_START_MONTH = "2020-01"
FIRST_USABLE_MONTH = "2024-09"


@dataclass
class MonthValue:
    month: str
    bot_share_total_traffic: float
    ai_crawler_share_of_bot_traffic: float
    ai_search_share_of_bot_traffic: float | None


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def api_get(token: str, endpoint: str, params: dict[str, str]) -> dict:
    url = f"{API_BASE}{endpoint}?{urlencode(params)}"
    req = Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "DeadInternetTracker/1.0 (local dashboard research)",
        },
    )
    with urlopen(req) as response:
        payload = json.load(response)
    if not payload.get("success"):
        raise RuntimeError(f"Cloudflare API error for {endpoint}: {payload.get('errors')}")
    return payload["result"]


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


def monthly_window_params(month: str) -> dict[str, str]:
    return {
        "dateStart": f"{month}-01T00:00:00Z",
        "dateEnd": f"{month}-28T00:00:00Z",
        "aggInterval": "1d",
        "format": "JSON",
    }


def average(values: list[float]) -> float:
    return sum(values) / len(values)


def load_cached_monthly(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}

    monthly_rows = payload.get("monthly")
    if not isinstance(monthly_rows, list):
        return {}

    cached: dict[str, dict] = {}
    for row in monthly_rows:
        month = row.get("month")
        if isinstance(month, str):
            cached[month] = row
    return cached


def fetch_month(token: str, month: str) -> MonthValue:
    bot_result = api_get(
        token,
        "/radar/http/timeseries_groups/BOT_CLASS",
        monthly_window_params(month),
    )
    bot_series = bot_result.get("serie_0") or bot_result.get("WORLD")
    if not bot_series or "bot" not in bot_series:
        raise RuntimeError(f"Missing overall bot share values for {month}")
    bot_share_total_traffic = average([float(value) for value in bot_series["bot"]])

    cat_result = api_get(
        token,
        "/radar/bots/timeseries_groups/BOT_CATEGORY",
        {
            **monthly_window_params(month),
            "dataSource": "ALL",
        },
    )
    cat_series = cat_result.get("serie_0", {})
    ai_values = [float(value) for value in cat_series.get("AI_CRAWLER", [])]
    if not ai_values:
        raise RuntimeError(f"Missing AI crawler category values for {month}")
    ai_crawler_share_of_bot_traffic = average(ai_values)

    ai_search_values = [float(value) for value in cat_series.get("AI_SEARCH", [])]
    ai_search_share_of_bot_traffic = average(ai_search_values) if ai_search_values else None

    return MonthValue(
        month=month,
        bot_share_total_traffic=bot_share_total_traffic,
        ai_crawler_share_of_bot_traffic=ai_crawler_share_of_bot_traffic,
        ai_search_share_of_bot_traffic=ai_search_share_of_bot_traffic,
    )


def build_snapshot() -> dict:
    root = Path(__file__).resolve().parent.parent
    env = load_env(root / ".env")
    token = env["CLOUDFLARE_API_TOKEN"]
    existing_snapshot_path = root / "data" / "cloudflare" / "cloudflare.json"
    now = datetime.now(timezone.utc)

    latest_full_year = now.year if now.month > 1 else now.year - 1
    latest_full_month_num = now.month - 1 if now.month > 1 else 12
    latest_full_month = f"{latest_full_year}-{latest_full_month_num:02d}"

    cached_rows = load_cached_monthly(existing_snapshot_path)
    observed_months = month_iter(FIRST_USABLE_MONTH, latest_full_month)
    missing_months = [month for month in observed_months if month not in cached_rows]

    fetched: list[MonthValue] = []
    if missing_months:
        with ThreadPoolExecutor(max_workers=8) as executor:
            fetched = list(executor.map(lambda month: fetch_month(token, month), missing_months))

    for row in fetched:
        ai_crawler_share_total_traffic = row.bot_share_total_traffic * row.ai_crawler_share_of_bot_traffic / 100.0
        ai_search_share_total_traffic = (
            row.bot_share_total_traffic * row.ai_search_share_of_bot_traffic / 100.0
            if row.ai_search_share_of_bot_traffic is not None
            else None
        )
        ai_bot_share_total_traffic = ai_crawler_share_total_traffic + (ai_search_share_total_traffic or 0.0)
        cached_rows[row.month] = {
            "month": row.month,
            "bot_share_total_traffic": row.bot_share_total_traffic,
            "ai_crawler_share_of_bot_traffic": row.ai_crawler_share_of_bot_traffic,
            "ai_crawler_share_total_traffic": ai_crawler_share_total_traffic,
            "ai_search_share_of_bot_traffic": row.ai_search_share_of_bot_traffic,
            "ai_search_share_total_traffic": ai_search_share_total_traffic,
            "ai_bot_share_total_traffic": ai_bot_share_total_traffic,
        }

    monthly_rows = []
    for month in observed_months:
        row = cached_rows.get(month)
        if row:
            monthly_rows.append(row)

    display_months = month_iter(DISPLAY_START_MONTH, latest_full_month)
    display_values = [
        round(cached_rows[month]["ai_bot_share_total_traffic"], 2) if month in cached_rows else None
        for month in display_months
    ]

    snapshot = {
        "chartKey": "traffic-bot-human",
        "title": "Estimated AI bot share of total traffic",
        "description": (
            "This estimates how much of total web traffic is AI bots. "
            "It matters because it gets closer to the machine share of web traversal than general bot traffic does."
        ),
        "source": "Cloudflare Radar bot share and bot category time series",
        "lastRefreshed": now.date().isoformat(),
        "method": (
            "We estimate AI bot share by combining Cloudflare's bot share of total traffic with its AI bot categories. "
            "The chart shows observed monthly values only."
        ),
        "caveats": (
            "Crawlers learn from the internet. Search bots use it. "
            "Cloudflare sees a large but incomplete slice of the web, with weaker coverage in places like China. "
            "This tracks AI bot traffic, not all AI activity. "
            "AI search only appears separately from June 2025, so the measure gets better over time."
        ),
        "xValues": display_months,
        "axisValueFormat": "percent1",
        "tooltipValueFormat": "percent2",
        "series": [
            {
                "name": "AI bot share",
                "color": "#ff79c6",
                "values": display_values,
            }
        ],
        "latestObservedMonth": latest_full_month,
        "monthly": monthly_rows,
    }
    return snapshot


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    snapshot = build_snapshot()
    data_dir = root / "data" / "cloudflare"
    data_dir.mkdir(parents=True, exist_ok=True)

    json_path = data_dir / "cloudflare.json"
    js_path = data_dir / "cloudflare.js"

    json_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    js_path.write_text(
        "window.__CLOUDFLARE_SNAPSHOT__ = "
        + json.dumps(snapshot, indent=2)
        + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote {json_path}")
    print(f"Wrote {js_path}")


if __name__ == "__main__":
    main()
