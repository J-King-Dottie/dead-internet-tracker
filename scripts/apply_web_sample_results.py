from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def extract_output_text(response_body: dict) -> str | None:
    for item in response_body.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                return content["text"]
    return None


def load_prepared(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_labels(path: Path) -> dict[str, str]:
    labels: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        response_body = ((row.get("response") or {}).get("body")) or {}
        text = extract_output_text(response_body)
        if not text:
            continue
        parsed = json.loads(text)
        labels_by_id = parsed.get("labels_by_id")
        if isinstance(labels_by_id, dict):
            for item_id, label in labels_by_id.items():
                if item_id and label in {"Human", "Mixed", "AI"}:
                    labels[item_id] = label
            continue
        for item in parsed.get("results", []):
            item_id = item.get("id")
            label = item.get("label")
            if item_id and label in {"Human", "Mixed", "AI"}:
                labels[item_id] = label
    return labels


def build_snapshot(period_rows: list[dict], summary_rows: list[dict], model_name: str) -> dict:
    periods = [row["period"] for row in summary_rows]
    ai_shares = [row["ai_share"] for row in summary_rows]
    mixed_shares = [
        row.get("mixed_share", round(row["ai_influenced_share"] - row["ai_share"], 2))
        for row in summary_rows
    ]
    now = datetime.now(timezone.utc).date().isoformat()
    return {
        "chartKey": "web-sample-ai-human",
        "title": "Estimated AI-written share of sampled open-web writing",
        "description": (
            "This estimates how much of a stable monthly sample of open-web article-like pages appears AI-written. "
            "It matters because it is a direct repeated measurement attempt, not just a proxy."
        ),
        "source": f"Common Crawl sampled article-like pages, classified with {model_name}",
        "lastRefreshed": now,
        "method": (
            "Each period samples 10,000 article-like URLs from Common Crawl with one URL per registered domain, "
            "tops up within the same crawl if needed, keeps pages with 400 to 1,000 tokens of readable text, "
            "and classifies 5,000 usable pages as Human, Mixed, or AI."
        ),
        "caveats": (
            "This is a stable sample of article-like open-web pages, not the whole internet. "
            "The classifier is imperfect, but the method is kept stable so the trend is the main signal."
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
                "name": "Mixed share",
                "color": "#8be9fd",
                "values": mixed_shares,
            },
        ],
        "periods": summary_rows,
        "latestObservedMonth": periods[-1] if periods else None,
        "pages": period_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepared", required=True)
    parser.add_argument("--output", required=True, help="Direct-run or batch output JSONL")
    parser.add_argument("--suffix", help="Optional output filename suffix, e.g. pubjan2026")
    parser.add_argument("--model", help="Optional model name override for summary metadata")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    prepared_path = Path(args.prepared)
    output_path = Path(args.output)
    if not prepared_path.is_absolute():
        prepared_path = (root / prepared_path).resolve()
    if not output_path.is_absolute():
        output_path = (root / output_path).resolve()

    prepared = load_prepared(prepared_path)
    labels = load_labels(output_path)
    period = prepared["period"]

    page_rows: list[dict] = []
    for row in prepared["pages"]:
        label = labels.get(row["id"])
        if label:
            row = dict(row)
            row["classification"] = label
            page_rows.append(row)

    if not page_rows:
        raise SystemExit("No classified rows found in output file.")

    ai_count = sum(1 for row in page_rows if row["classification"] == "AI")
    mixed_count = sum(1 for row in page_rows if row["classification"] == "Mixed")
    human_count = sum(1 for row in page_rows if row["classification"] == "Human")
    sample_size = ai_count + mixed_count + human_count
    ai_share = round(ai_count / sample_size * 100.0, 2)
    mixed_share = round(mixed_count / sample_size * 100.0, 2)
    ai_influenced_share = round((ai_count + mixed_count) / sample_size * 100.0, 2)

    summary_row = {
        "period": period,
        "sample_size": sample_size,
        "ai_count": ai_count,
        "mixed_count": mixed_count,
        "human_count": human_count,
        "ai_share": ai_share,
        "mixed_share": mixed_share,
        "ai_influenced_share": ai_influenced_share,
        "sample_source": page_rows[0]["sample_source"],
        "dropped_count": prepared.get("droppedCount", 0),
    }

    data_dir = root / "data" / "web-sample"
    data_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_{args.suffix}" if args.suffix else ""

    page_level_path = data_dir / f"web_sample_page_level_{period}{suffix}.json"
    page_level_path.write_text(json.dumps(page_rows, indent=2), encoding="utf-8")

    summary_json_path = data_dir / f"web_sample_summary{suffix}.json"
    summary_js_path = data_dir / f"web_sample_summary{suffix}.js"

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
    summary_json_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    summary_js_path.write_text(
        "window.__WEB_SAMPLE_SUMMARY_SNAPSHOT__ = "
        + json.dumps(snapshot, indent=2)
        + ";\n",
        encoding="utf-8",
    )

    print(f"Wrote {page_level_path}")
    print(f"Wrote {summary_json_path}")
    print(f"Wrote {summary_js_path}")


if __name__ == "__main__":
    main()
