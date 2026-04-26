from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "web-sample"

# The dashboard should only read the standard comparable classification series.
INPUTS = [
    DATA_DIR / "web_sample_summary.json",
]

OUTPUT_JSON = DATA_DIR / "web_sample_dashboard_snapshot.json"
OUTPUT_JS = DATA_DIR / "web_sample_dashboard_snapshot.js"


def load_period_rows() -> tuple[list[dict], dict]:
    deduped: dict[str, dict] = {}
    template: dict | None = None

    for path in INPUTS:
        payload = json.loads(path.read_text(encoding="utf-8"))
        template = payload
        for row in payload.get("periods", []):
            deduped[row["period"]] = row

    if template is None:
        raise FileNotFoundError("No web sample summaries found")

    rows = [deduped[key] for key in sorted(deduped)]
    return rows, template


def build_snapshot() -> dict:
    periods, template = load_period_rows()
    january_periods = [row for row in periods if str(row["period"]).endswith("-01")]

    return {
        "chartKey": "web-sample-classifications",
        "title": "January AI share in the web sample",
        "description": "This compares the AI-written share in the January Common Crawl web sample for each year classified so far. It matters because it gives a cleaner same-month comparison.",
        "source": template["source"],
        "lastRefreshed": max(payload_last_refreshed(path) for path in INPUTS),
        "method": template["method"],
        "caveats": "This chart shows January only. It is a stable sample of article-like open-web pages, not the whole internet.",
        "xValues": [row["period"] for row in january_periods],
        "axisValueFormat": "percent1",
        "tooltipValueFormat": "percent2",
        "series": [
            {
                "name": "AI",
                "color": "#ff79c6",
                "values": [float(row["ai_share"]) for row in january_periods],
            },
        ],
        "periods": january_periods,
        "latestObservedMonth": january_periods[-1]["period"] if january_periods else None,
    }


def payload_last_refreshed(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("lastRefreshed", "")


def main() -> None:
    snapshot = build_snapshot()
    OUTPUT_JSON.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    OUTPUT_JS.write_text(
        "window.__WEB_SAMPLE_DASHBOARD_SNAPSHOT__ = " + json.dumps(snapshot, indent=2) + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT_JSON}")
    print(f"Wrote {OUTPUT_JS}")


if __name__ == "__main__":
    main()
