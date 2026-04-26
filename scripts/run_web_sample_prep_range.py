from __future__ import annotations

import argparse
import calendar
import json
import subprocess
from dataclasses import dataclass, asdict
from datetime import date, datetime
from pathlib import Path
from urllib.request import Request, urlopen


COLLINFO_URL = "https://index.commoncrawl.org/collinfo.json"


@dataclass
class CrawlWindow:
    crawl: str
    start: date
    end: date


def fetch_crawl_windows() -> list[CrawlWindow]:
    request = Request(COLLINFO_URL, headers={"User-Agent": "DeadInternetTracker/1.0"})
    with urlopen(request) as response:
        payload = json.load(response)
    rows = [
        CrawlWindow(
            crawl=item["id"],
            start=datetime.fromisoformat(item["from"]).date(),
            end=datetime.fromisoformat(item["to"]).date(),
        )
        for item in payload
    ]
    rows.sort(key=lambda row: (row.start, row.end, row.crawl))
    return rows


def iter_periods(start_period: str, end_period: str) -> list[str]:
    start_year, start_month = map(int, start_period.split("-"))
    end_year, end_month = map(int, end_period.split("-"))
    periods: list[str] = []
    year = start_year
    month = start_month
    while (year, month) <= (end_year, end_month):
        periods.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            month = 1
            year += 1
    return periods


def first_crawl_after_month(crawls: list[CrawlWindow], period: str) -> str:
    year, month = map(int, period.split("-"))
    month_end = date(year, month, calendar.monthrange(year, month)[1])
    for row in crawls:
        if row.start > month_end:
            return row.crawl
    raise RuntimeError(f"No Common Crawl snapshot found after {period}")


def later_crawls(crawls: list[CrawlWindow], crawl: str) -> list[str]:
    crawl_ids = [row.crawl for row in crawls]
    if crawl not in crawl_ids:
        return []
    idx = crawl_ids.index(crawl)
    return crawl_ids[idx + 1 :]


def run_command(root: Path, args: list[str]) -> None:
    subprocess.run(args, cwd=root, check=True)


def render_query(root: Path, period: str, crawl: str, limit: int) -> None:
    run_command(
        root,
        [
            "python",
            str(root / "scripts" / "render_web_sample_athena_query.py"),
            "--period",
            period,
            "--crawl",
            crawl,
            "--limit",
            str(limit),
        ],
    )


def run_query(root: Path, period: str, append: bool) -> None:
    args = [
        "python",
        str(root / "scripts" / "run_web_sample_athena_query.py"),
        "--period",
        period,
    ]
    if append:
        args.append("--append")
    run_command(root, args)


def prepare_requests(
    root: Path,
    period: str,
    candidate_csv: Path,
    target_usable: int,
    min_tokens: int,
    token_limit: int,
    model: str,
    group_size: int,
    workers: int,
) -> dict:
    args = [
        "python",
        str(root / "scripts" / "build_web_sample_requests.py"),
        "--input",
        str(candidate_csv),
        "--target-usable",
        str(target_usable),
        "--min-tokens",
        str(min_tokens),
        "--token-limit",
        str(token_limit),
        "--model",
        model,
        "--group-size",
        str(group_size),
        "--workers",
        str(workers),
        "--resume-existing",
    ]
    run_command(root, args)
    prepared_path = root / "data" / "web-sample" / f"web_sample_prepared_{period}.json"
    return json.loads(prepared_path.read_text(encoding="utf-8"))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-period", default="2020-01")
    parser.add_argument("--end-period", default="2025-12")
    parser.add_argument("--initial-limit", type=int, default=10000)
    parser.add_argument("--topup-limit", type=int, default=2000)
    parser.add_argument("--max-crawl-attempts", type=int, default=6)
    parser.add_argument("--target-usable", type=int, default=5000)
    parser.add_argument("--min-tokens", type=int, default=400)
    parser.add_argument("--token-limit", type=int, default=1000)
    parser.add_argument("--group-size", type=int, default=20)
    parser.add_argument("--model", default="gpt-5-mini")
    parser.add_argument("--workers", type=int, default=64)
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    data_dir = root / "data" / "web-sample"
    data_dir.mkdir(parents=True, exist_ok=True)
    status_path = data_dir / f"web_sample_prep_status_{args.start_period}_{args.end_period}.json"

    crawls = fetch_crawl_windows()
    periods = iter_periods(args.start_period, args.end_period)
    status_rows: list[dict] = []

    for period in periods:
        candidate_csv = data_dir / f"web_sample_candidates_{period}.csv"
        prepared_path = data_dir / f"web_sample_prepared_{period}.json"
        requests_path = data_dir / f"web_sample_requests_{period}.jsonl"

        if prepared_path.exists() and requests_path.exists():
            prepared = load_json(prepared_path)
            if prepared.get("sampleSizePrepared", 0) >= args.target_usable:
                status_rows.append(
                    {
                        "period": period,
                        "status": "ready",
                        "sampleSizePrepared": prepared.get("sampleSizePrepared", 0),
                        "candidateCsv": str(candidate_csv),
                        "preparedPath": str(prepared_path),
                        "requestsPath": str(requests_path),
                        "note": "existing prepared sample reused",
                    }
                )
                status_path.write_text(json.dumps({"rows": status_rows}, indent=2), encoding="utf-8")
                print(f"[skip] {period}: existing prepared sample already has {prepared.get('sampleSizePrepared', 0)} usable pages")
                continue

        first_crawl = first_crawl_after_month(crawls, period)
        crawl_sequence = [first_crawl] + later_crawls(crawls, first_crawl)

        used_crawls: list[str] = []
        prepared_payload: dict | None = None
        meta_payload: dict | None = None

        if candidate_csv.exists():
            candidate_csv.unlink()
        meta_path = data_dir / f"web_sample_candidates_{period}_meta.json"
        if meta_path.exists():
            meta_path.unlink()

        append_mode = False

        for crawl in crawl_sequence:
            used_crawls.append(crawl)
            per_crawl_attempt = 0
            while per_crawl_attempt < args.max_crawl_attempts:
                limit = args.initial_limit if (not append_mode and per_crawl_attempt == 0 and len(used_crawls) == 1) else args.topup_limit
                render_query(root, period, crawl, limit)
                run_query(root, period, append=append_mode)
                append_mode = True
                per_crawl_attempt += 1

                prepared_payload = prepare_requests(
                    root=root,
                    period=period,
                    candidate_csv=candidate_csv,
                    target_usable=args.target_usable,
                    min_tokens=args.min_tokens,
                    token_limit=args.token_limit,
                    model=args.model,
                    group_size=args.group_size,
                    workers=args.workers,
                )
                meta_payload = load_json(meta_path)
                prepared_count = prepared_payload.get("sampleSizePrepared", 0)
                print(
                    f"[prep] {period}: crawl={crawl} attempt={per_crawl_attempt} "
                    f"rows={meta_payload.get('totalRows', 0)} usable={prepared_count}"
                )
                if prepared_count >= args.target_usable:
                    break
            if prepared_payload and prepared_payload.get("sampleSizePrepared", 0) >= args.target_usable:
                break

        prepared_count = prepared_payload.get("sampleSizePrepared", 0) if prepared_payload else 0
        total_rows = meta_payload.get("totalRows", 0) if meta_payload else 0
        status = "ready" if prepared_count >= args.target_usable else "short"
        status_row = {
            "period": period,
            "status": status,
            "sampleSizePrepared": prepared_count,
            "candidateRows": total_rows,
            "crawlsUsed": used_crawls,
            "candidateCsv": str(candidate_csv),
            "candidateMeta": str(meta_path),
            "preparedPath": str(prepared_path),
            "requestsPath": str(requests_path),
        }
        status_rows.append(status_row)
        status_path.write_text(json.dumps({"rows": status_rows}, indent=2), encoding="utf-8")
        print(f"[done] {period}: {status} usable={prepared_count} candidate_rows={total_rows}")

    print(f"Wrote {status_path}")


if __name__ == "__main__":
    main()
