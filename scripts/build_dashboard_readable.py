from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_PATH = DATA_DIR / "dashboard_readable.json"


def load_json(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def month_sequence(start_label: str, end_label: str) -> list[str]:
    start_year, start_month = map(int, start_label.split("-"))
    end_year, end_month = map(int, end_label.split("-"))
    labels: list[str] = []
    year = start_year
    month = start_month
    while year < end_year or (year == end_year and month <= end_month):
        labels.append(f"{year}-{month:02d}")
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
    return labels


def is_monthly_label(label: str) -> bool:
    return bool(re.fullmatch(r"\d{4}-\d{2}", str(label)))


def normalize_snapshot_range(snapshot: dict[str, Any]) -> dict[str, Any]:
    labels = snapshot.get("xValues") or []
    if not labels:
        return snapshot

    if is_monthly_label(labels[0]):
        first_populated_index = None
        for series in snapshot.get("series") or []:
            for index, value in enumerate(series.get("values") or []):
                if value is not None and value != "":
                    first_populated_index = index if first_populated_index is None else min(first_populated_index, index)
                    break
        first_data_label = labels[first_populated_index] if first_populated_index is not None else labels[0]
        start_label = first_data_label if first_data_label > "2020-01" else "2020-01"
        end_label = labels[-1]
        full_labels = month_sequence(start_label, end_label)
        label_index = {label: index for index, label in enumerate(labels)}
        normalized = {**snapshot, "xValues": full_labels}
        normalized["series"] = [
            {
                **series,
                "values": [
                    (series.get("values") or [])[label_index[label]]
                    if label in label_index and label_index[label] < len(series.get("values") or [])
                    else None
                    for label in full_labels
                ],
            }
            for series in snapshot.get("series") or []
        ]
        return normalized

    start_index = next((index for index, label in enumerate(labels) if int(label) >= 2020), 0)
    if start_index <= 0:
        return snapshot
    return {
        **snapshot,
        "xValues": labels[start_index:],
        "series": [
            {**series, "values": (series.get("values") or [])[start_index:]}
            for series in snapshot.get("series") or []
        ],
    }


def trailing_moving_average(values: list[Any], window_size: int) -> list[float | None]:
    averaged: list[float | None] = []
    for index in range(len(values)):
        start = max(0, index - window_size + 1)
        window_values = [
            float(value)
            for value in values[start : index + 1]
            if isinstance(value, (int, float)) or (isinstance(value, str) and value.strip())
        ]
        if not window_values:
            averaged.append(None)
        else:
            averaged.append(round(sum(window_values) / len(window_values), 2))
    return averaged


def parse_estimate_midpoint(value: Any) -> float | None:
    if value is None:
        return None
    text = (
        str(value)
        .replace("â€“", "-")
        .replace("â€”", "-")
        .replace("âˆ’", "-")
        .replace("–", "-")
        .replace("—", "-")
        .replace("−", "-")
        .replace(",", "")
        .replace("%", "")
        .strip()
    )
    if not text:
        return None
    if "-" in text:
        parts = [float(part.strip()) for part in text.split("-") if re.search(r"\d", part)]
        if len(parts) == 2:
            return (parts[0] + parts[1]) / 2
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None


def latest_value(series: dict[str, Any], labels: list[str]) -> dict[str, Any] | None:
    values = series.get("values") or []
    for index in range(min(len(values), len(labels)) - 1, -1, -1):
        value = values[index]
        if value is not None and value != "":
            return {"period": labels[index], "value": value}
    return None


def series_payload(name: str, labels: list[str], values: list[Any], unit: str, color: str | None = None) -> dict[str, Any]:
    payload = {
        "name": name,
        "unit": unit,
        "values": [{"period": label, "value": value} for label, value in zip(labels, values)],
    }
    if color:
        payload["color"] = color
    return payload


def line_chart(snapshot_path: str, chart_key: str, displayed_series_names: dict[str, str] | None = None) -> dict[str, Any]:
    snapshot = normalize_snapshot_range(load_json(snapshot_path))
    labels = snapshot.get("xValues") or []
    displayed_series_names = displayed_series_names or {}
    series = []
    latest_values = {}
    for item in snapshot.get("series") or []:
        name = displayed_series_names.get(item.get("name"), item.get("name"))
        values = item.get("values") or []
        series.append(series_payload(name, labels, values, snapshot.get("axisValueFormat", ""), item.get("color")))
        latest_values[name] = latest_value({"values": values}, labels)
    return {
        "chartKey": chart_key,
        "title": snapshot.get("title", ""),
        "description": snapshot.get("description", ""),
        "source": snapshot.get("source", ""),
        "sourceSnapshot": snapshot_path,
        "lastRefreshed": snapshot.get("lastRefreshed", ""),
        "method": snapshot.get("method", ""),
        "caveats": snapshot.get("caveats", ""),
        "xValues": labels,
        "series": series,
        "latestValues": latest_values,
    }


def ai_content_meta_review() -> dict[str, Any]:
    snapshot_path = "data/ai-content-meta-review/ai_content_meta_review.json"
    snapshot = load_json(snapshot_path)
    rows = []
    for row in snapshot.get("rows") or []:
        year = int(row.get("year"))
        midpoint = parse_estimate_midpoint(row.get("value"))
        if year >= 2020 and midpoint is not None:
            rows.append({**row, "year": year, "valuePercentMidpoint": midpoint})

    years = sorted({row["year"] for row in rows})
    annual_average = []
    for year in years:
        values = [row["valuePercentMidpoint"] for row in rows if row["year"] == year]
        annual_average.append(
            {
                "year": year,
                "value": round(sum(values) / len(values), 4) if values else None,
                "estimateCount": len(values),
            }
        )

    return {
        "chartKey": "ai-content-meta-review",
        "title": "AI content share meta review",
        "description": "Published estimates of AI-generated or materially AI-assisted content, shown as a scatter plot with an annual average line.",
        "source": "Curated AI deep research using a guided source-review process.",
        "sourceSnapshot": snapshot_path,
        "lastRefreshed": snapshot.get("lastRefreshed", ""),
        "unit": "percent",
        "xValues": [str(year) for year in years],
        "series": [
            {
                "name": "Published estimates",
                "values": [
                    {
                        "year": row["year"],
                        "value": row["valuePercentMidpoint"],
                        "rawValue": row.get("value", ""),
                        "series": row.get("series", ""),
                        "source": row.get("source", ""),
                        "notes": row.get("notes", ""),
                        "publicationDate": row.get("publication_date", ""),
                    }
                    for row in rows
                ],
            },
            {"name": "Annual average", "values": annual_average},
        ],
    }


def web_sample_classifications() -> dict[str, Any]:
    snapshot_path = "data/web-sample-lite/web_sample_lite_summary.json"
    snapshot = load_json(snapshot_path)
    labels = snapshot.get("xValues") or []
    source_series = snapshot.get("series") or []
    ai_series = next((series for series in source_series if series.get("name") in {"AI share", "AI"}), source_series[0])
    mixed_series = next((series for series in source_series if series.get("name") in {"Mixed share", "Mixed"}), None)
    influenced_series = next((series for series in source_series if series.get("name") == "AI-influenced share"), None)
    ai_values = ai_series.get("values") or []
    if mixed_series:
        mixed_values = mixed_series.get("values") or []
    else:
        mixed_values = []
        for index, influenced in enumerate((influenced_series or {}).get("values") or []):
            ai = ai_values[index] if index < len(ai_values) else None
            mixed_values.append(round(max(0, float(influenced) - float(ai)), 2) if influenced is not None and ai is not None else None)

    strong_values = trailing_moving_average(ai_values, 6)
    partial_values = trailing_moving_average(mixed_values, 6)
    periods = []
    for period in snapshot.get("periods") or []:
        ai_share = period.get("ai_share")
        influenced_share = period.get("ai_influenced_share")
        mixed_share = period.get("mixed_share")
        if mixed_share is None and ai_share is not None and influenced_share is not None:
            mixed_share = round(max(0, float(influenced_share) - float(ai_share)), 2)
        periods.append({**period, "mixed_share": mixed_share})

    return {
        "chartKey": "web-sample-classifications",
        "title": "Monthly AI share in the web sample",
        "description": "Trailing 6-month moving averages of sampled article-style web pages classified as strong AI signal or partial AI signal. The two lines are exclusive.",
        "source": snapshot.get("source", ""),
        "sourceSnapshot": snapshot_path,
        "lastRefreshed": snapshot.get("lastRefreshed", ""),
        "method": "Each month samples 1,000 article-style Common Crawl pages and classifies excerpts with an LLM rubric. The plotted values are trailing 6-month moving averages.",
        "caveats": snapshot.get("caveats", ""),
        "xValues": labels,
        "series": [
            series_payload("Strong AI signal", labels, strong_values, "percent"),
            series_payload("Partial AI signal", labels, partial_values, "percent"),
        ],
        "underlyingMonthlyCounts": periods,
        "latestValues": {
            "Strong AI signal": latest_value({"values": strong_values}, labels),
            "Partial AI signal": latest_value({"values": partial_values}, labels),
        },
    }


def imperva_traffic() -> dict[str, Any]:
    snapshot_path = "data/imperva/imperva.json"
    snapshot = normalize_snapshot_range(load_json(snapshot_path))
    labels = snapshot.get("xValues") or []
    series_by_name = {series.get("name"): series for series in snapshot.get("series") or []}
    bad = series_by_name.get("Bad bot", {}).get("values") or []
    good = series_by_name.get("Good bot", {}).get("values") or []
    human = series_by_name.get("Human", {}).get("values") or []
    automated = [round(float((bad[index] if index < len(bad) else 0) or 0) + float((good[index] if index < len(good) else 0) or 0), 2) for index in range(len(labels))]
    return {
        "chartKey": "imperva-traffic",
        "title": snapshot.get("title", ""),
        "description": snapshot.get("description", ""),
        "source": snapshot.get("source", ""),
        "sourceSnapshot": snapshot_path,
        "lastRefreshed": snapshot.get("lastRefreshed", ""),
        "method": snapshot.get("method", ""),
        "caveats": snapshot.get("caveats", ""),
        "xValues": labels,
        "series": [
            series_payload("Automated traffic", labels, automated, "percent"),
            series_payload("Human", labels, human, "percent"),
        ],
        "latestValues": {
            "Automated traffic": latest_value({"values": automated}, labels),
            "Human": latest_value({"values": human}, labels),
        },
    }


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    charts = [
        ai_content_meta_review(),
        web_sample_classifications(),
        line_chart("data/cloudflare/cloudflare.json", "traffic-bot-human", {"AI bot share": "AI bots"}),
        imperva_traffic(),
        line_chart(
            "data/wikipedia/wikipedia.json",
            "wikipedia",
            {"All editors": "All editors (1+)", "Active editors": "Active editors (5+)"},
        ),
        line_chart("data/stackoverflow/stackoverflow.json", "stack-overflow", {"Questions asked": "Total new questions asked"}),
    ]
    payload = {
        "title": "Dead Internet Tracker machine-readable chart data",
        "canonicalUrl": "https://dead-internet-tracker.onrender.com/",
        "description": "Normalized chart data for AI and search crawlers. This file contains the data actually plotted on the public page, plus source snapshot links and short method/caveat fields.",
        "generatedAt": datetime.now(timezone.utc).date().isoformat(),
        "charts": charts,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
