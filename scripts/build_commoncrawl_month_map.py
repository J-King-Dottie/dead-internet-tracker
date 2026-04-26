from __future__ import annotations

import calendar
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen


COLLINFO_URL = "https://index.commoncrawl.org/collinfo.json"


@dataclass
class CrawlWindow:
    crawl: str
    start: date
    end: date


def fetch_crawls() -> list[CrawlWindow]:
    request = Request(COLLINFO_URL, headers={"User-Agent": "DeadInternetTracker/1.0"})
    with urlopen(request) as response:
        payload = json.load(response)

    crawls = [
        CrawlWindow(
            crawl=item["id"],
            start=datetime.fromisoformat(item["from"]).date(),
            end=datetime.fromisoformat(item["to"]).date(),
        )
        for item in payload
    ]
    crawls.sort(key=lambda row: row.start)
    return crawls


def month_iter(start_period: str, end_period: str) -> list[str]:
    year, month = map(int, start_period.split("-"))
    end_year, end_month = map(int, end_period.split("-"))
    periods: list[str] = []
    while (year, month) <= (end_year, end_month):
        periods.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            month = 1
            year += 1
    return periods


def month_bounds(period: str) -> tuple[date, date]:
    year, month = map(int, period.split("-"))
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    return first, last


def midpoint(start: date, end: date) -> date:
    return start + timedelta(days=(end - start).days // 2)


def choose_best_crawl(period: str, crawls: list[CrawlWindow]) -> dict:
    month_start, month_end = month_bounds(period)
    after = [crawl for crawl in crawls if crawl.start > month_end]
    before_or_during = [crawl for crawl in crawls if crawl.start <= month_end]

    search_order = [crawl.crawl for crawl in after] + [crawl.crawl for crawl in reversed(before_or_during)]

    if after:
        best = after[0]
        match_type = "first_after_month"
    elif before_or_during:
        best = before_or_during[-1]
        match_type = "latest_available_before_month_end"
    else:
        raise ValueError(f"No Common Crawl snapshots available for period {period}")

    midpoint_distance = abs((midpoint(best.start, best.end) - midpoint(month_start, month_end)).days)

    return {
        "period": period,
        "crawl": best.crawl,
        "crawl_from": best.start.isoformat(),
        "crawl_to": best.end.isoformat(),
        "midpoint_distance_days": midpoint_distance,
        "match_type": match_type,
        "search_order": search_order,
    }


def build_markdown(rows: list[dict], generated_on: str) -> str:
    lines = [
        "# Common Crawl Month Map",
        "",
        f"Generated: `{generated_on}`",
        "",
        "This maps each target month to the best matching Common Crawl snapshot using the actual crawl date windows, not the crawl ID.",
        "",
        "Matching rule:",
        "- prefer the first crawl whose window starts after the target month ends",
        "- if more data is needed later, continue through later crawls in order",
        "- only fall back backward when no later crawl exists yet",
        "",
        "| Target month | Selected crawl | Crawl window | Match | Midpoint distance | Next crawls if needed |",
        "|---|---|---|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['period']} | {row['crawl']} | {row['crawl_from']} to {row['crawl_to']} | {row['match_type']} | {row['midpoint_distance_days']} | {', '.join(row['search_order'][:3])} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    data_dir = root / "data" / "web-sample"
    data_dir.mkdir(parents=True, exist_ok=True)

    crawls = [crawl for crawl in fetch_crawls() if crawl.start >= date(2020, 1, 1)]
    today = datetime.now(UTC).date()
    periods = month_iter("2020-01", today.strftime("%Y-%m"))
    rows = [choose_best_crawl(period, crawls) for period in periods]

    json_path = data_dir / "commoncrawl_month_map.json"
    md_path = data_dir / "commoncrawl_month_map.md"
    generated_on = datetime.now(UTC).date().isoformat()

    payload = {
        "generated_on": generated_on,
        "rule": {
            "primary": "first_crawl_after_target_month",
            "secondary": "later_crawls_after_target_month_in_order",
            "fallback": "latest_available_before_target_month_end",
        },
        "rows": rows,
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(rows, generated_on), encoding="utf-8")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Rows: {len(rows)}")


if __name__ == "__main__":
    main()
