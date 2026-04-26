from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

from build_web_sample_requests import (
    PROMPT_HASH,
    RUBRIC_VERSION,
    SYSTEM_PROMPT,
    build_request_line,
    chunked,
    compute_metrics,
)


SERIES_VERSION = "web-sample-lite-v1"


def deterministic_seed(period: str, sample_size: int) -> int:
    digest = hashlib.sha256(f"{SERIES_VERSION}|{period}|{sample_size}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def sample_pages(pages: list[dict], period: str, sample_size: int) -> tuple[list[dict], int]:
    if len(pages) < sample_size:
        raise ValueError(f"{period} only has {len(pages)} prepared pages; need {sample_size}.")

    ordered = sorted(pages, key=lambda row: row["id"])
    seed = deterministic_seed(period, sample_size)
    rng = random.Random(seed)
    sampled = rng.sample(ordered, sample_size)
    sampled.sort(key=lambda row: row["id"])

    normalized: list[dict] = []
    for row in sampled:
        item = dict(row)
        if "metrics" not in item:
            item["metrics"] = compute_metrics(item["excerpt"])
        normalized.append(item)
    return normalized, seed


def load_prepared(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_lite_payload(parent: dict, pages: list[dict], seed: int, sample_size: int, model: str, group_size: int) -> dict:
    return {
        "series": SERIES_VERSION,
        "period": parent["period"],
        "parentPrepared": str(parent.get("_prepared_path", "")),
        "parentSampleSizePrepared": len(parent.get("pages", [])),
        "sampleStrategy": "random_without_replacement",
        "sampleSeed": str(seed),
        "sampleSizePrepared": len(pages),
        "groupSize": group_size,
        "model": model,
        "rubricVersion": RUBRIC_VERSION,
        "promptHash": PROMPT_HASH,
        "tokenLimit": parent.get("tokenLimit", 1000),
        "minTokens": parent.get("minTokens", 400),
        "targetUsable": sample_size,
        "systemPrompt": SYSTEM_PROMPT,
        "sourcePreparedModel": parent.get("model"),
        "sourcePreparedTargetUsable": parent.get("targetUsable"),
        "sourcePreparedDroppedCount": parent.get("droppedCount", 0),
        "pages": pages,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
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

    manifest_rows: list[dict] = []
    for month in range(1, 13):
        period = f"{args.year:04d}-{month:02d}"
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
        "series": SERIES_VERSION,
        "year": args.year,
        "sampleSize": args.sample_size,
        "groupSize": args.group_size,
        "model": args.model,
        "periods": manifest_rows,
    }
    manifest_path = output_dir / f"web_sample_lite_setup_{args.year}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {manifest_path.name}")


if __name__ == "__main__":
    main()
