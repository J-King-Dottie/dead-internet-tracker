from __future__ import annotations

import argparse
import json
from pathlib import Path

from setup_web_sample_lite_year import build_lite_payload, load_prepared, sample_pages
from build_web_sample_requests import build_request_line, chunked


def parse_periods(values: list[str]) -> list[str]:
    periods: list[str] = []
    for value in values:
        value = value.strip()
        if not value:
            continue
        if ":" in value:
            start, end = value.split(":", 1)
            start_year, start_month = map(int, start.split("-"))
            end_year, end_month = map(int, end.split("-"))
            cursor_year, cursor_month = start_year, start_month
            while (cursor_year, cursor_month) <= (end_year, end_month):
                periods.append(f"{cursor_year:04d}-{cursor_month:02d}")
                cursor_month += 1
                if cursor_month > 12:
                    cursor_month = 1
                    cursor_year += 1
        else:
            periods.append(value)
    return sorted(dict.fromkeys(periods))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", required=True, nargs="+", help="Periods like 2026-01 or ranges like 2026-01:2026-02")
    parser.add_argument("--sample-size", type=int, default=1000)
    parser.add_argument("--group-size", type=int, default=20)
    parser.add_argument("--model", default="gpt-5-mini")
    parser.add_argument("--input-dir", default="data/web-sample")
    parser.add_argument("--output-dir", default="data/web-sample-lite")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    input_dir = Path(args.input_dir)
    if not input_dir.is_absolute():
        input_dir = (root / input_dir).resolve()
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = (root / output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    periods = parse_periods(args.period)
    manifest_rows: list[dict] = []
    for period in periods:
        parent_path = input_dir / f"web_sample_prepared_{period}.json"
        if not parent_path.exists():
            raise SystemExit(f"Missing prepared parent sample for {period}: {parent_path}")

        parent = load_prepared(parent_path)
        parent["_prepared_path"] = str(parent_path)
        sampled_pages, seed = sample_pages(parent["pages"], period, args.sample_size)
        lite_payload = build_lite_payload(
            parent=parent,
            pages=sampled_pages,
            seed=seed,
            sample_size=args.sample_size,
            model=args.model,
            group_size=args.group_size,
        )
        requests = [
            build_request_line(period, batch_index, items, args.model)
            for batch_index, items in enumerate(chunked(sampled_pages, args.group_size), start=1)
        ]

        prepared_path = output_dir / f"web_sample_lite_prepared_{period}.json"
        requests_path = output_dir / f"web_sample_lite_requests_{period}.jsonl"
        if (prepared_path.exists() or requests_path.exists()) and not args.overwrite:
            raise SystemExit(
                f"Output already exists for {period}. Use --overwrite to replace {prepared_path.name} and {requests_path.name}."
            )
        prepared_path.write_text(json.dumps(lite_payload, indent=2) + "\n", encoding="utf-8")
        with requests_path.open("w", encoding="utf-8") as handle:
            for request in requests:
                handle.write(json.dumps(request) + "\n")
        manifest_rows.append(
            {
                "period": period,
                "parentPrepared": str(parent_path),
                "preparedPath": str(prepared_path),
                "requestsPath": str(requests_path),
                "sampleSeed": str(seed),
                "sampleSizePrepared": len(sampled_pages),
                "requestCount": len(requests),
                "model": args.model,
            }
        )
        print(f"Wrote {prepared_path.name}")
        print(f"Wrote {requests_path.name}")

    manifest = {
        "series": "web-sample-lite-v1",
        "sampleSize": args.sample_size,
        "groupSize": args.group_size,
        "model": args.model,
        "periods": manifest_rows,
    }
    manifest_path = output_dir / "web_sample_lite_setup_range.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {manifest_path.name}")


if __name__ == "__main__":
    main()
