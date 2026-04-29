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
KEY_START = "  <!-- DASHBOARD_KEY_METRICS_START -->"
KEY_END = "  <!-- DASHBOARD_KEY_METRICS_END -->"
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


def latest_point(chart: dict[str, Any], series_name: str) -> dict[str, Any] | None:
    latest = chart.get("latestValues") or {}
    point = latest.get(series_name)
    return point if isinstance(point, dict) else None


def format_number(value: Any) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(numeric) >= 1000 and numeric.is_integer():
        return f"{int(numeric):,}"
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.2f}".rstrip("0").rstrip(".")


def value_with_period(point: dict[str, Any] | None, suffix: str = "") -> str:
    if not point:
        return "not available"
    value = point.get("value")
    period = point.get("period") or point.get("year")
    return f"{format_number(value)}{suffix} in {period}"


def key_metrics_sentence(chart: dict[str, Any]) -> str:
    key = chart.get("chartKey")
    if key == "ai-content-meta-review":
        average_series = next((series for series in chart.get("series") or [] if series.get("name") == "Annual average"), {})
        latest_average = None
        for point in reversed(average_series.get("values") or []):
            if isinstance(point, dict) and point.get("value") not in {None, ""}:
                latest_average = point
                break
        return f"Published AI-content estimates: latest included estimates average about {value_with_period(latest_average, '%')}, but sources vary across content types."

    if key == "web-sample-classifications":
        strong = value_with_period(latest_point(chart, "Strong AI signal"), "%")
        partial = value_with_period(latest_point(chart, "Partial AI signal"), "%")
        return f"Web sample: strong AI signal is {strong}; partial AI signal is {partial} across sampled article-style Common Crawl pages."

    if key == "traffic-bot-human":
        point = latest_point(chart, "AI bots")
        if point:
            return f"AI bot traffic: Cloudflare's latest monthly snapshot puts AI bots at {format_number(point.get('value'))}% of total observed traffic in {point.get('period')}."
        return "AI bot traffic: latest Cloudflare AI bot traffic value is not available."

    if key == "imperva-traffic":
        automated = value_with_period(latest_point(chart, "Automated traffic"), "%")
        return f"High-value site traffic: automated traffic reached {automated} on security-focused sites such as banking."

    if key == "wikipedia":
        all_point = latest_point(chart, "All editors (1+)")
        active_point = latest_point(chart, "Active editors (5+)")
        if all_point and active_point:
            return f"Wikipedia activity: English Wikipedia had {format_number(all_point.get('value'))} editors in {all_point.get('period')}, including {format_number(active_point.get('value'))} active editors."
        return "Wikipedia activity: latest editor values are not available."

    if key == "stack-overflow":
        point = latest_point(chart, "Total new questions asked")
        if point:
            return f"Stack Overflow activity: Stack Overflow had {format_number(point.get('value'))} new questions in {point.get('period')}, down sharply from 2020 levels."
        return "Stack Overflow activity: latest question count is not available."

    return f"{chart.get('title', 'Chart')}: {latest_values_text(chart)}."


def build_key_metrics_block(data: dict[str, Any]) -> str:
    lines = [
        KEY_START,
        '  <section class="ai-key-metrics" id="ai-key-metrics" aria-labelledby="ai-key-metrics-title">',
        '    <h2 id="ai-key-metrics-title">Key metrics</h2>',
        "    <p>Current snapshot of the Dead Internet Tracker. These values are generated from the same local snapshots as the charts and are placed near the top of the HTML for search engines and AI readers.</p>",
        "    <ul>",
    ]
    for chart in data.get("charts") or []:
        lines.append(f"      <li>{esc(key_metrics_sentence(chart))}</li>")
    lines.extend(["    </ul>", "  </section>", KEY_END])
    return "\n".join(lines)


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


def insert_key_metrics_block(html_text: str, block: str) -> str:
    html_text = remove_generated_block(html_text, KEY_START, KEY_END)
    marker = "<body>"
    if marker not in html_text:
        raise SystemExit(f"Cannot insert key metrics because {marker} was not found.")
    return html_text.replace(marker, marker + "\n" + block, 1)


def embed(index_path: Path, data_path: Path) -> None:
    data = json.loads(data_path.read_text(encoding="utf-8"))
    html_text = index_path.read_text(encoding="utf-8")
    html_text = remove_generated_block(html_text, HEAD_START, HEAD_END)
    html_text = insert_key_metrics_block(html_text, build_key_metrics_block(data))
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
