from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_web_sample_requests import build_request_line, chunked, compute_metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepared", required=True, help="Prepared JSON file with exact pages/excerpts")
    parser.add_argument("--model", default="gpt-5-mini")
    parser.add_argument("--group-size", type=int, default=20)
    parser.add_argument("--suffix", help="Optional output filename suffix")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    prepared_path = Path(args.prepared)
    if not prepared_path.is_absolute():
        prepared_path = (root / prepared_path).resolve()

    prepared = json.loads(prepared_path.read_text(encoding="utf-8"))
    period = prepared["period"]
    pages = prepared["pages"]
    for page in pages:
        if "metrics" not in page:
            page["metrics"] = compute_metrics(page["excerpt"])

    requests = [
        build_request_line(period, batch_index, items, args.model)
        for batch_index, items in enumerate(chunked(pages, args.group_size), start=1)
    ]

    data_dir = root / "data" / "web-sample"
    data_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_{args.suffix}" if args.suffix else ""
    output_path = data_dir / f"web_sample_requests_{period}{suffix}.jsonl"

    with output_path.open("w", encoding="utf-8") as handle:
        for request in requests:
            handle.write(json.dumps(request) + "\n")

    print(f"Wrote {output_path}")
    print(f"Built {len(requests)} requests from exact prepared sample")


if __name__ == "__main__":
    main()
