from __future__ import annotations

import argparse
import calendar
import json
import os
import subprocess
from datetime import date, datetime
from pathlib import Path
from urllib.request import Request, urlopen

from apply_web_sample_results import load_labels


COLLINFO_URL = "https://index.commoncrawl.org/collinfo.json"


def run_command(root: Path, args: list[str]) -> None:
    print("[run]", " ".join(args))
    subprocess.run(args, cwd=root, check=True)


def month_after(period: str) -> str:
    year, month = map(int, period.split("-"))
    month += 1
    if month == 13:
        year += 1
        month = 1
    return f"{year:04d}-{month:02d}"


def load_next_period(root: Path) -> str:
    summary_path = root / "data" / "web-sample-lite" / "web_sample_lite_summary.json"
    if not summary_path.exists():
        raise SystemExit(f"Missing lite summary: {summary_path}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    periods = sorted(row["period"] for row in summary.get("periods", []) if row.get("period"))
    if not periods:
        raise SystemExit("Cannot infer next period because lite summary has no periods.")
    return month_after(periods[-1])


def first_available_crawl_after_month(period: str) -> str | None:
    request = Request(COLLINFO_URL, headers={"User-Agent": "DeadInternetTracker/1.0"})
    with urlopen(request) as response:
        payload = json.load(response)

    year, month = map(int, period.split("-"))
    month_end = date(year, month, calendar.monthrange(year, month)[1])
    crawls = [
        (
            datetime.fromisoformat(item["from"]).date(),
            item["id"],
        )
        for item in payload
    ]
    crawls.sort()
    for crawl_start, crawl_id in crawls:
        if crawl_start > month_end:
            return crawl_id
    return None


def ensure_all_labels(prepared_path: Path, output_path: Path) -> None:
    prepared = json.loads(prepared_path.read_text(encoding="utf-8"))
    expected_ids = {row["id"] for row in prepared.get("pages", [])}
    labels = load_labels(output_path)
    missing = sorted(expected_ids - set(labels))
    if missing:
        preview = ", ".join(missing[:8])
        raise SystemExit(f"Classification output missing {len(missing)} page label(s): {preview}")


def write_github_output(values: dict[str, str]) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def refresh_period(
    root: Path,
    period: str,
    sample_size: int,
    model: str,
    group_size: int,
    concurrency: int,
    max_retries: int,
) -> None:
    crawl = first_available_crawl_after_month(period)
    if not crawl:
        print(f"No Common Crawl snapshot starts after {period} ends yet. Skipping without changes.")
        return

    data_dir = root / "data"
    lite_dir = data_dir / "web-sample-lite"
    prepared_path = lite_dir / f"web_sample_lite_prepared_{period}.json"
    requests_path = lite_dir / f"web_sample_lite_requests_{period}.jsonl"
    output_path = lite_dir / f"web_sample_lite_live_output_{period}.jsonl"
    error_path = lite_dir / f"web_sample_lite_live_errors_{period}.jsonl"

    run_command(
        root,
        [
            "python",
            "scripts/run_web_sample_prep_range.py",
            "--start-period",
            period,
            "--end-period",
            period,
            "--model",
            model,
        ],
    )
    run_command(
        root,
        [
            "python",
            "scripts/setup_web_sample_lite_range.py",
            "--period",
            period,
            "--sample-size",
            str(sample_size),
            "--group-size",
            str(group_size),
            "--model",
            model,
            "--overwrite",
        ],
    )
    run_command(
        root,
        [
            "python",
            "scripts/run_web_sample_live.py",
            "--input",
            str(requests_path),
            "--data-dir",
            str(lite_dir),
            "--output-prefix",
            "web_sample_lite_live_output",
            "--error-prefix",
            "web_sample_lite_live_errors",
            "--suffix",
            period,
            "--concurrency",
            str(concurrency),
            "--max-retries",
            str(max_retries),
        ],
    )

    if error_path.exists() and error_path.read_text(encoding="utf-8").strip():
        raise SystemExit(f"Live classification had errors: {error_path}")

    ensure_all_labels(prepared_path, output_path)
    run_command(
        root,
        [
            "python",
            "scripts/apply_web_sample_lite_results.py",
            "--prepared",
            str(prepared_path),
            "--output",
            str(output_path),
            "--model",
            model,
        ],
    )
    run_command(root, ["python", "scripts/build_dashboard_readable.py"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh the next monthly 1,000-page web sample lite period.")
    parser.add_argument("--period", help="Optional explicit YYYY-MM period. Defaults to next missing lite month.")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check whether the target period has an eligible Common Crawl collection.",
    )
    parser.add_argument("--sample-size", type=int, default=1000)
    parser.add_argument("--model", default="gpt-5-mini")
    parser.add_argument("--group-size", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--max-retries", type=int, default=3)
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    period = args.period or load_next_period(root)
    print(f"Target web sample lite period: {period}")

    if args.check_only:
        crawl = first_available_crawl_after_month(period)
        available = "true" if crawl else "false"
        if crawl:
            print(f"Eligible Common Crawl collection found for {period}: {crawl}")
        else:
            print(f"No eligible Common Crawl collection found for {period}.")
        write_github_output(
            {
                "available": available,
                "period": period,
                "crawl": crawl or "",
            }
        )
        return

    refresh_period(
        root=root,
        period=period,
        sample_size=args.sample_size,
        model=args.model,
        group_size=args.group_size,
        concurrency=args.concurrency,
        max_retries=args.max_retries,
    )


if __name__ == "__main__":
    main()
