from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from apply_web_sample_results import load_labels


def load_prepared(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_snapshot(period_rows: list[dict], summary_rows: list[dict], model_name: str) -> dict:
    periods = [row["period"] for row in summary_rows]
    ai_shares = [row["ai_share"] for row in summary_rows]
    ai_influenced_shares = [row["ai_influenced_share"] for row in summary_rows]
    now = datetime.now(timezone.utc).date().isoformat()
    return {
        "chartKey": "web-sample-lite-ai-human",
        "title": "Monthly AI share in the web sample",
        "description": (
            "This tracks the monthly share of sampled article-style web pages classified as AI."
        ),
        "source": "Common Crawl monthly samples classified under a research-guided rubric",
        "lastRefreshed": now,
        "method": (
            "For each month, this series draws a deterministic random 1,000-page subset from the full prepared "
            "5,000-page article-style Common Crawl sample and classifies those pages as Human, Mixed, or AI."
        ),
        "caveats": (
            "This is a stable sample of article-style open-web pages, not the whole internet. "
            "The lite series is cheaper and faster than the full 5,000-page run, but noisier month to month."
        ),
        "xValues": periods,
        "axisValueFormat": "percent1",
        "tooltipValueFormat": "percent2",
        "series": [
            {
                "name": "AI share",
                "color": "#ff79c6",
                "values": ai_shares,
            },
            {
                "name": "AI-influenced share",
                "color": "#8be9fd",
                "values": ai_influenced_shares,
            },
        ],
        "periods": summary_rows,
        "latestObservedMonth": periods[-1] if periods else None,
        "pages": period_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepared", required=True)
    parser.add_argument("--output", required=True, help="Live output JSONL")
    parser.add_argument("--data-dir", default="data/web-sample-lite")
    parser.add_argument("--prefix", default="web_sample_lite")
    parser.add_argument("--model", help="Optional model name override for summary metadata")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    prepared_path = Path(args.prepared)
    if not prepared_path.is_absolute():
        prepared_path = (root / prepared_path).resolve()
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = (root / output_path).resolve()
    data_dir = Path(args.data_dir)
    if not data_dir.is_absolute():
        data_dir = (root / data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    prepared = load_prepared(prepared_path)
    labels = load_labels(output_path)
    period = prepared["period"]

    page_rows: list[dict] = []
    for row in prepared["pages"]:
        label = labels.get(row["id"])
        if label:
            item = dict(row)
            item["classification"] = label
            page_rows.append(item)

    if not page_rows:
        raise SystemExit("No classified rows found in output file.")

    ai_count = sum(1 for row in page_rows if row["classification"] == "AI")
    mixed_count = sum(1 for row in page_rows if row["classification"] == "Mixed")
    human_count = sum(1 for row in page_rows if row["classification"] == "Human")
    sample_size = ai_count + mixed_count + human_count
    ai_share = round(ai_count / sample_size * 100.0, 2)
    ai_influenced_share = round((ai_count + mixed_count) / sample_size * 100.0, 2)

    summary_row = {
        "period": period,
        "sample_size": sample_size,
        "ai_count": ai_count,
        "mixed_count": mixed_count,
        "human_count": human_count,
        "ai_share": ai_share,
        "ai_influenced_share": ai_influenced_share,
        "sample_source": page_rows[0]["sample_source"],
        "sample_seed": prepared.get("sampleSeed"),
        "parent_sample_size_prepared": prepared.get("parentSampleSizePrepared"),
        "rubric_version": prepared.get("rubricVersion"),
        "prompt_hash": prepared.get("promptHash"),
    }

    prefix = args.prefix
    page_level_path = data_dir / f"{prefix}_page_level_{period}.json"
    summary_json_path = data_dir / f"{prefix}_summary.json"
    summary_js_path = data_dir / f"{prefix}_summary.js"

    page_level_path.write_text(json.dumps(page_rows, indent=2) + "\n", encoding="utf-8")

    if summary_json_path.exists():
        existing = json.loads(summary_json_path.read_text(encoding="utf-8"))
        existing_rows = existing.get("periods", [])
    else:
        existing_rows = []

    merged_rows = [row for row in existing_rows if row.get("period") != period]
    merged_rows.append(summary_row)
    merged_rows.sort(key=lambda row: row["period"])

    model_name = args.model or prepared.get("model", "gpt-5-mini")
    snapshot = build_snapshot(page_rows, merged_rows, model_name)
    summary_json_path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    summary_js_path.write_text(
        f"window.__{prefix.upper()}_SUMMARY_SNAPSHOT__ = " + json.dumps(snapshot, indent=2) + ";\n",
        encoding="utf-8",
    )

    print(f"Wrote {page_level_path}")
    print(f"Wrote {summary_json_path}")
    print(f"Wrote {summary_js_path}")


if __name__ == "__main__":
    main()
