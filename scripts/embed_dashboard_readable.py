from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX_PATH = ROOT / "index.html"
DEFAULT_DATA_PATH = ROOT / "data" / "dashboard_readable.json"

BODY_START = "  <!-- DASHBOARD_READABLE_SUMMARY_START -->"
BODY_END = "  <!-- DASHBOARD_READABLE_SUMMARY_END -->"
HEAD_START = "  <!-- DASHBOARD_READABLE_DATA_START -->"
HEAD_END = "  <!-- DASHBOARD_READABLE_DATA_END -->"


def esc(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def point_period(point: dict[str, Any]) -> str:
    return esc(point.get("period") or point.get("year") or "")


def latest_values_text(chart: dict[str, Any]) -> str:
    latest = chart.get("latestValues") or {}
    parts = []
    for name, point in latest.items():
        if isinstance(point, dict) and point.get("value") not in {None, ""}:
            parts.append(f"{name}: {point.get('value')} in {point.get('period')}")
    if parts:
        return "; ".join(parts)

    for series in chart.get("series") or []:
        for point in reversed(series.get("values") or []):
            if isinstance(point, dict) and point.get("value") not in {None, ""}:
                parts.append(f"{series.get('name', 'Series')}: {point.get('value')} in {point.get('period') or point.get('year')}")
                break
    return "; ".join(parts)


def point_notes(point: dict[str, Any]) -> str:
    notes = []
    for key in ("rawValue", "source", "notes", "publicationDate", "estimateCount"):
        value = point.get(key)
        if value not in {None, ""}:
            notes.append(f"{key}: {value}")
    return "; ".join(notes)


def chart_table(chart: dict[str, Any]) -> str:
    rows = []
    for series in chart.get("series") or []:
        series_name = esc(series.get("name", "Series"))
        unit = esc(series.get("unit") or chart.get("unit") or "")
        for point in series.get("values") or []:
            if not isinstance(point, dict):
                continue
            value = point.get("value")
            if value in {None, ""}:
                continue
            rows.append(
                "          <tr>"
                f"<td>{series_name}</td>"
                f"<td>{point_period(point)}</td>"
                f"<td>{esc(value)}</td>"
                f"<td>{unit}</td>"
                f"<td>{esc(point_notes(point))}</td>"
                "</tr>"
            )

    if not rows:
        return "      <p>No plotted values available.</p>"

    return "\n".join(
        [
            '      <div class="agent-data-table-wrap">',
            "        <table>",
            "          <thead>",
            "            <tr><th>Series</th><th>Period</th><th>Value</th><th>Unit</th><th>Notes</th></tr>",
            "          </thead>",
            "          <tbody>",
            *rows,
            "          </tbody>",
            "        </table>",
            "      </div>",
        ]
    )


def build_body_block(data: dict[str, Any]) -> str:
    lines = [
        BODY_START,
        '  <section class="agent-readable-data" id="underlying-data" aria-labelledby="underlying-data-title">',
        '    <h2 id="underlying-data-title">Underlying chart data</h2>',
        "    <p>This section is generated from the same local snapshots as the dashboard above. It is ordinary HTML so search engines and AI readers can read the chart values from this page without running JavaScript.</p>",
        "    <ul>",
    ]

    for chart in data.get("charts") or []:
        title = esc(chart.get("title", "Untitled chart"))
        description = esc(chart.get("description", ""))
        source = esc(chart.get("source", ""))
        latest = esc(latest_values_text(chart))
        lines.append(f"      <li><strong>{title}</strong>: {description} Latest values: {latest}. Source: {source}.</li>")

    lines.extend(["    </ul>", '    <div class="agent-data-charts">'])

    for chart in data.get("charts") or []:
        title = esc(chart.get("title", "Untitled chart"))
        lines.extend(
            [
                '      <section class="agent-data-chart">',
                f"        <h3>{title}</h3>",
                f"        <p>{esc(chart.get('description', ''))}</p>",
                f"        <p><strong>Source:</strong> {esc(chart.get('source', ''))}</p>",
                f"        <p><strong>Source snapshot:</strong> {esc(chart.get('sourceSnapshot', ''))}</p>",
                f"        <p><strong>Last refreshed:</strong> {esc(chart.get('lastRefreshed', ''))}</p>",
                f"        <p><strong>Method:</strong> {esc(chart.get('method', ''))}</p>",
                f"        <p><strong>Caveats:</strong> {esc(chart.get('caveats', ''))}</p>",
                chart_table(chart),
                "      </section>",
            ]
        )

    lines.extend(["    </div>", "  </section>", BODY_END])
    return "\n".join(lines)


def remove_generated_block(html_text: str, start: str, end: str) -> str:
    if start not in html_text or end not in html_text:
        return html_text
    before, rest = html_text.split(start, 1)
    _, after = rest.split(end, 1)
    return before + after


def insert_body_block(html_text: str, block: str) -> str:
    html_text = remove_generated_block(html_text, BODY_START, BODY_END)
    marker = '  <footer class="page-footer-note">'
    if marker not in html_text:
        raise SystemExit(f"Cannot insert generated dashboard data because {marker} was not found.")
    return html_text.replace(marker, block + "\n" + marker, 1)


def embed(index_path: Path, data_path: Path) -> None:
    data = json.loads(data_path.read_text(encoding="utf-8"))
    html_text = index_path.read_text(encoding="utf-8")
    html_text = remove_generated_block(html_text, HEAD_START, HEAD_END)
    html_text = insert_body_block(html_text, build_body_block(data))
    index_path.write_text(html_text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed plain-HTML dashboard data in index.html.")
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_PATH)
    args = parser.parse_args()
    embed(args.index, args.data)
    print(f"Embedded plain HTML dashboard data in {args.index}")


if __name__ == "__main__":
    main()
