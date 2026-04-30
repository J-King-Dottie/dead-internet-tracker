from __future__ import annotations

import argparse
import html
import json
import re
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


def percent0(value: Any) -> str:
    return f"{round(float(value))}%"


def percent1(value: Any) -> str:
    return f"{float(value):.1f}%"


def latest_series_point(chart: dict[str, Any], series_name: str) -> dict[str, Any] | None:
    point = latest_point(chart, series_name)
    if point:
        return point
    series = next((item for item in chart.get("series") or [] if item.get("name") == series_name), {})
    for row in reversed(series.get("values") or []):
        if isinstance(row, dict) and row.get("value") not in {None, ""}:
            return row
    return None


def chart_by_key(data: dict[str, Any], key: str) -> dict[str, Any]:
    return next((chart for chart in data.get("charts") or [] if chart.get("chartKey") == key), {})


def dynamic_values(data: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}

    ai_content = chart_by_key(data, "ai-content-meta-review")
    annual_average = next((series for series in ai_content.get("series") or [] if series.get("name") == "Annual average"), {})
    latest_2026_average = next(
        (
            point.get("value")
            for point in annual_average.get("values") or []
            if isinstance(point, dict) and str(point.get("year")) == "2026" and point.get("value") not in {None, ""}
        ),
        None,
    )
    if latest_2026_average is not None:
        values["ai-content-2026-average"] = percent0(latest_2026_average)

    web_sample = chart_by_key(data, "web-sample-classifications")
    strong = latest_series_point(web_sample, "Strong AI signal")
    partial = latest_series_point(web_sample, "Partial AI signal")
    if strong:
        values["web-sample-latest-strong-share"] = percent1(strong.get("value"))
    if partial:
        values["web-sample-latest-partial-share"] = percent1(partial.get("value"))

    cloudflare = chart_by_key(data, "traffic-bot-human")
    ai_bots = latest_series_point(cloudflare, "AI bots")
    if ai_bots:
        values["cloudflare-latest-ai-bot-share"] = percent0(ai_bots.get("value"))

    imperva = chart_by_key(data, "imperva-traffic")
    automated = latest_series_point(imperva, "Automated traffic")
    if automated:
        values["imperva-latest-automated-share"] = percent0(automated.get("value"))

    wikipedia = chart_by_key(data, "wikipedia")
    all_editors = next((series for series in wikipedia.get("series") or [] if series.get("name") == "All editors (1+)"), {})
    editor_values = [
        point for point in all_editors.get("values") or []
        if isinstance(point, dict) and point.get("value") not in {None, ""}
    ]
    peak_2020 = max((float(point["value"]) for point in editor_values if str(point.get("period")).startswith("2020-")), default=None)
    latest_editor_value = float(editor_values[-1]["value"]) if editor_values else None
    if peak_2020 and latest_editor_value is not None:
        values["wikipedia-editor-decline"] = percent0(((peak_2020 - latest_editor_value) / peak_2020) * 100)

    stack_overflow = chart_by_key(data, "stack-overflow")
    questions = latest_series_point(stack_overflow, "Total new questions asked")
    if questions:
        values["stackoverflow-latest-questions"] = format_number(questions.get("value"))

    return values


def fill_dynamic_spans(html_text: str, data: dict[str, Any]) -> str:
    values = dynamic_values(data)
    for key, value in values.items():
        pattern = re.compile(rf'(<span data-dynamic="{re.escape(key)}">)(.*?)(</span>)', re.DOTALL)
        html_text = pattern.sub(rf"\g<1>{esc(value)}\g<3>", html_text)
    return html_text


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
    html_text = remove_generated_block(html_text, "  <!-- DASHBOARD_KEY_METRICS_START -->", "  <!-- DASHBOARD_KEY_METRICS_END -->")
    html_text = fill_dynamic_spans(html_text, data)
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
