from __future__ import annotations

import argparse
import calendar
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen


COLLINFO_URL = "https://index.commoncrawl.org/collinfo.json"

SQL_TEMPLATE = """-- Common Crawl monthly sample for the Dead Internet Tracker
-- Run this in AWS Athena after registering the Common Crawl columnar index table:
-- https://commoncrawl.org/columnar-index
--
-- Expected table name below: ccindex.ccindex
-- Crawl selected: {crawl}
-- Tracker period: {period}
-- Method: target URLs whose path suggests publication in {period} and sample them from the first crawl after that month

WITH frame AS (
  SELECT
    '{period}' AS period,
    url,
    url_host_registered_domain AS domain,
    crawl AS sample_source,
    warc_filename,
    warc_record_offset,
    warc_record_length,
    content_charset
  FROM ccindex.ccindex
  WHERE crawl = '{crawl}'
    AND subset = 'warc'
    AND fetch_status = 200
    AND content_mime_detected = 'text/html'
    AND url_host_registered_domain IS NOT NULL
    AND content_languages LIKE '%eng%'
    AND NOT regexp_like(
      lower(url_path),
      '/(tag|tags|category|categories|author|authors|search|archive|archives|feed|feeds|video|videos|gallery|galleries|login|signin|account|checkout|cart|product|products|shop|docs|documentation|wiki|forum|forums|profile|profiles|events|calendar)/'
    )
    AND (
      regexp_like(lower(url_path), '/(blog|blogs|article|articles|news|post|posts|story|stories)/')
      OR regexp_like(lower(url_path), '/(?:19|20)[0-9][0-9]/(?:0?[1-9]|1[0-2])(?:/|$)')
      OR regexp_like(lower(url_path), '(?:^|[\\\\/_-])(?:19|20)[0-9][0-9][\\\\/_-](?:0?[1-9]|1[0-2])(?:[\\\\/_-]|$)')
      OR regexp_like(lower(url_path), '(?:^|[^0-9])(?:19|20)[0-9][0-9](?:0[1-9]|1[0-2])(?:[0-3][0-9])?(?:[^0-9]|$)')
    )
    AND (
      regexp_like(lower(url_path), '{target_sep_regex}')
      OR regexp_like(lower(url_path), '{target_compact_regex}')
    )
),
dedup AS (
  SELECT
    *,
    row_number() OVER (PARTITION BY domain ORDER BY rand()) AS domain_rank
  FROM frame
)
SELECT
  period,
  url,
  domain,
  sample_source,
  warc_filename,
  warc_record_offset,
  warc_record_length,
  content_charset
FROM dedup
WHERE domain_rank = 1
ORDER BY rand()
LIMIT 5000;
"""


def fetch_latest_crawl() -> tuple[str, str]:
    request = Request(COLLINFO_URL, headers={"User-Agent": "DeadInternetTracker/1.0"})
    with urlopen(request) as response:
        payload = json.load(response)

    latest = payload[0]
    crawl = latest["id"]
    from_date = datetime.fromisoformat(latest["from"])
    period = from_date.strftime("%Y-%m")
    return crawl, period


def fetch_monthly_crawls(start_period: str) -> list[tuple[str, str]]:
    request = Request(COLLINFO_URL, headers={"User-Agent": "DeadInternetTracker/1.0"})
    with urlopen(request) as response:
        payload = json.load(response)

    selected: dict[str, str] = {}
    for item in payload:
        crawl = item["id"]
        period = datetime.fromisoformat(item["from"]).strftime("%Y-%m")
        if period < start_period:
            continue
        current = selected.get(period)
        if current is None or crawl > current:
            selected[period] = crawl
    return [(crawl, period) for period, crawl in sorted(selected.items())]


def load_month_map(root: Path) -> dict[str, dict]:
    path = root / "data" / "web-sample" / "commoncrawl_month_map.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {row["period"]: row for row in payload.get("rows", [])}


def resolve_crawl_for_period(root: Path, period: str) -> str:
    month_map = load_month_map(root)
    if period in month_map:
        return month_map[period]["crawl"]

    request = Request(COLLINFO_URL, headers={"User-Agent": "DeadInternetTracker/1.0"})
    with urlopen(request) as response:
        payload = json.load(response)

    target_year, target_month = map(int, period.split("-"))
    month_end = date(target_year, target_month, calendar.monthrange(target_year, target_month)[1])
    crawls = [
        (
            datetime.fromisoformat(item["from"]).date(),
            datetime.fromisoformat(item["to"]).date(),
            item["id"],
        )
        for item in payload
    ]
    crawls.sort()
    after = [crawl_id for crawl_start, _, crawl_id in crawls if crawl_start > month_end]
    if after:
        return after[0]
    before_or_during = [crawl_id for crawl_start, _, crawl_id in crawls if crawl_start <= month_end]
    best = before_or_during[-1] if before_or_during else None
    if not best:
        raise SystemExit(f"Could not resolve Common Crawl snapshot for period {period}")
    return best


def build_target_period_regexes(period: str) -> tuple[str, str]:
    year, month = period.split("-")
    month_no_pad = str(int(month))
    sep_regex = rf"(^|[\\/_-]){year}[\\/_-](?:0?{month_no_pad})([\\/_-]|$)"
    compact_regex = rf"(^|[^0-9]){year}{month}(?:[0-3][0-9])?([^0-9]|$)"
    return sep_regex, compact_regex


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--crawl", help="Common Crawl id, e.g. CC-MAIN-2026-12")
    parser.add_argument("--period", help="Tracker period, e.g. 2026-03")
    parser.add_argument("--from-period", help="Write one query per monthly period from YYYY-MM onward")
    parser.add_argument("--limit", type=int, default=10000, help="Candidate URL limit")
    parser.add_argument("--suffix", help="Optional filename suffix, e.g. clean")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    data_dir = root / "data" / "web-sample"
    data_dir.mkdir(parents=True, exist_ok=True)
    queries_dir = data_dir / "web_sample_queries"
    queries_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_{args.suffix}" if args.suffix else ""

    if args.from_period:
        manifest: list[dict[str, str]] = []
        for crawl, period in fetch_monthly_crawls(args.from_period):
            target_sep_regex, target_compact_regex = build_target_period_regexes(period)
            sql = SQL_TEMPLATE.replace("LIMIT 5000;", f"LIMIT {args.limit};").format(
                crawl=crawl,
                period=period,
                target_sep_regex=target_sep_regex,
                target_compact_regex=target_compact_regex,
            )
            output_path = queries_dir / f"web_sample_athena_query_{period}{suffix}.sql"
            output_path.write_text(sql, encoding="utf-8")
            manifest.append({"period": period, "crawl": crawl, "sql": str(output_path), "limit": args.limit})
            print(f"Wrote {output_path}")
        manifest_path = data_dir / f"web_sample_query_manifest{suffix}.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"Wrote {manifest_path}")
        return

    if args.crawl and args.period:
        crawl = args.crawl
        period = args.period
    elif args.period and not args.crawl:
        period = args.period
        crawl = resolve_crawl_for_period(root, period)
    else:
        latest_crawl, latest_period = fetch_latest_crawl()
        crawl = args.crawl or latest_crawl
        period = args.period or latest_period

    target_sep_regex, target_compact_regex = build_target_period_regexes(period)
    sql = SQL_TEMPLATE.replace("LIMIT 5000;", f"LIMIT {args.limit};").format(
        crawl=crawl,
        period=period,
        target_sep_regex=target_sep_regex,
        target_compact_regex=target_compact_regex,
    )
    output_path = queries_dir / f"web_sample_athena_query_{period}{suffix}.sql"
    output_path.write_text(sql, encoding="utf-8")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
