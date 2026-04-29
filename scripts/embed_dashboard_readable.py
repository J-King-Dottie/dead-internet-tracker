from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX_PATH = ROOT / "index.html"
DEFAULT_DATA_PATH = ROOT / "data" / "dashboard_readable.json"

HEAD_START = "  <!-- DASHBOARD_READABLE_DATA_START -->"
HEAD_END = "  <!-- DASHBOARD_READABLE_DATA_END -->"
BODY_START = "  <!-- DASHBOARD_READABLE_SUMMARY_START -->"
BODY_END = "  <!-- DASHBOARD_READABLE_SUMMARY_END -->"


def latest_values_text(chart: dict[str, Any]) -> str:
    latest = chart.get("latestValues") or {}
    if latest:
        parts = []
        for name, point in latest.items():
            if not isinstance(point, dict):
                continue
            period = point.get("period")
            value = point.get("value")
            if period is not None and value is not None:
                parts.append(f"{name}: {value} in {period}")
        if parts:
            return "; ".join(parts)

    series = chart.get("series") or []
    parts = []
    for item in series:
        values = item.get("values") or []
        for point in reversed(values):
            if isinstance(point, dict) and point.get("value") not in {None, ""}:
                period = point.get("period") or point.get("year")
                parts.append(f"{item.get('name', 'Series')}: {point.get('value')} in {period}")
                break
    return "; ".join(parts)


def build_head_block(data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</script>", "<\\/script>")
    return "\n".join(
        [
            HEAD_START,
            '  <script type="application/json" id="dashboard-readable-data">',
            payload,
            "  </script>",
            HEAD_END,
        ]
    )


def build_body_block(data: dict[str, Any]) -> str:
    lines = [
        BODY_START,
        '  <noscript id="dashboard-readable-summary">',
        '    <section aria-labelledby="dashboard-readable-summary-title">',
        '      <h2 id="dashboard-readable-summary-title">Dead Internet Tracker data summary</h2>',
        "      <p>This page is a static research dashboard about AI-generated content, AI bot traffic, bot automation, and human activity on the public web. The normalized chart data is also available as JSON at /data/dashboard_readable.json.</p>",
        "      <ul>",
    ]

    for chart in data.get("charts") or []:
        title = html.escape(str(chart.get("title", "Untitled chart")))
        description = html.escape(str(chart.get("description", "")))
        source = html.escape(str(chart.get("source", "")))
        latest = html.escape(latest_values_text(chart))
        detail = f"{description} Latest values: {latest}. Source: {source}."
        lines.append(f"        <li><strong>{title}</strong>: {detail}</li>")

    lines.extend(
        [
            "      </ul>",
            "    </section>",
            "  </noscript>",
            BODY_END,
        ]
    )
    return "\n".join(lines)


def replace_or_insert(html_text: str, start: str, end: str, block: str, marker: str) -> str:
    if start in html_text and end in html_text:
        before, rest = html_text.split(start, 1)
        _, after = rest.split(end, 1)
        return before + block + after
    if marker not in html_text:
        raise SystemExit(f"Cannot insert generated dashboard block because {marker} was not found.")
    return html_text.replace(marker, block + "\n" + marker, 1)


def embed(index_path: Path, data_path: Path) -> None:
    data = json.loads(data_path.read_text(encoding="utf-8"))
    html_text = index_path.read_text(encoding="utf-8")
    html_text = replace_or_insert(html_text, HEAD_START, HEAD_END, build_head_block(data), "</head>")
    html_text = replace_or_insert(html_text, BODY_START, BODY_END, build_body_block(data), "<body>")
    index_path.write_text(html_text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed machine-readable dashboard data in index.html.")
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_PATH)
    args = parser.parse_args()
    embed(args.index, args.data)
    print(f"Embedded dashboard readable data in {args.index}")


if __name__ == "__main__":
    main()
