from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "web-sample"
OUTPUT_PATH = DATA_DIR / "web_sample_classifications_so_far.svg"


@dataclass(frozen=True)
class Row:
    period: str
    ai_share: float
    mixed_share: float
    human_share: float
    sample_size: int
    sample_source: str


def load_rows(path: Path) -> list[Row]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows: list[Row] = []
    for item in payload.get("periods", []):
        ai_share = float(item["ai_share"])
        mixed_share = float(item["mixed_count"]) / float(item["sample_size"]) * 100.0
        human_share = float(item["human_count"]) / float(item["sample_size"]) * 100.0
        rows.append(
            Row(
                period=item["period"],
                ai_share=ai_share,
                mixed_share=mixed_share,
                human_share=human_share,
                sample_size=int(item["sample_size"]),
                sample_source=item["sample_source"],
            )
        )
    return rows


def ordered_rows() -> list[Row]:
    paths = [
        DATA_DIR / "web_sample_summary.json",
        DATA_DIR / "web_sample_summary_pubjan2026.json",
        DATA_DIR / "web_sample_summary_pubfeb2026.json",
    ]
    deduped: dict[str, Row] = {}
    for path in paths:
        for row in load_rows(path):
            deduped[row.period] = row
    return [deduped[key] for key in sorted(deduped)]


def fmt_pct(value: float) -> str:
    return f"{value:.1f}%"


def render_svg(rows: list[Row]) -> str:
    width = 1500
    height = 860
    margin_left = 120
    margin_right = 80
    margin_top = 130
    margin_bottom = 150
    chart_width = width - margin_left - margin_right
    chart_height = height - margin_top - margin_bottom
    chart_x0 = margin_left
    chart_y0 = margin_top
    chart_y1 = margin_top + chart_height
    step = chart_width / len(rows)
    bar_width = min(48.0, step * 0.64)
    bar_gap = step - bar_width

    colors = {
        "bg": "#faf7f2",
        "grid": "#d9d0c3",
        "axis": "#3f3a34",
        "human": "#8fa3ad",
        "mixed": "#d99042",
        "ai": "#c94f43",
        "label": "#1f1d1a",
        "muted": "#6e665d",
        "card": "#fffdf8",
    }

    def y_scale(pct: float) -> float:
        return chart_y1 - (pct / 100.0) * chart_height

    grid_lines: list[str] = []
    for tick in range(0, 101, 20):
        y = y_scale(float(tick))
        grid_lines.append(
            f'<line x1="{chart_x0}" y1="{y:.1f}" x2="{chart_x0 + chart_width}" y2="{y:.1f}" '
            f'stroke="{colors["grid"]}" stroke-width="1" />'
        )
        grid_lines.append(
            f'<text x="{chart_x0 - 18}" y="{y + 5:.1f}" font-size="18" text-anchor="end" '
            f'fill="{colors["muted"]}">{tick}%</text>'
        )

    bars: list[str] = []
    x_labels: list[str] = []
    ai_points: list[str] = []
    influenced_points: list[str] = []
    for idx, row in enumerate(rows):
        x_left = chart_x0 + idx * step + bar_gap / 2.0
        x_mid = x_left + bar_width / 2.0
        human_h = chart_height * (row.human_share / 100.0)
        mixed_h = chart_height * (row.mixed_share / 100.0)
        ai_h = chart_height * (row.ai_share / 100.0)

        y_human = chart_y1 - human_h
        y_mixed = y_human - mixed_h
        y_ai = y_mixed - ai_h

        title = (
            f"{row.period} | Human {fmt_pct(row.human_share)} | "
            f"Mixed {fmt_pct(row.mixed_share)} | AI {fmt_pct(row.ai_share)} | "
            f"Sample {row.sample_size:,} | {row.sample_source}"
        )
        bars.append(
            f'<g><title>{escape(title)}</title>'
            f'<rect x="{x_left:.1f}" y="{y_human:.1f}" width="{bar_width:.1f}" height="{human_h:.1f}" '
            f'rx="4" fill="{colors["human"]}" />'
            f'<rect x="{x_left:.1f}" y="{y_mixed:.1f}" width="{bar_width:.1f}" height="{mixed_h:.1f}" '
            f'fill="{colors["mixed"]}" />'
            f'<rect x="{x_left:.1f}" y="{y_ai:.1f}" width="{bar_width:.1f}" height="{ai_h:.1f}" '
            f'rx="4" fill="{colors["ai"]}" /></g>'
        )
        ai_points.append(f"{x_mid:.1f},{y_scale(row.ai_share):.1f}")
        influenced_points.append(f"{x_mid:.1f},{y_scale(row.ai_share + row.mixed_share):.1f}")

        label = row.period[2:]
        x_labels.append(
            f'<text x="{x_mid:.1f}" y="{chart_y1 + 30:.1f}" font-size="15" text-anchor="end" '
            f'fill="{colors["muted"]}" transform="rotate(-45 {x_mid:.1f} {chart_y1 + 30:.1f})">{label}</text>'
        )

    latest = rows[-1]
    note_box_x = width - 350
    note_box_y = 44
    latest_mixed_plus_ai = latest.ai_share + latest.mixed_share

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="{colors["bg"]}" />
  <text x="{margin_left}" y="56" font-size="34" font-weight="700" fill="{colors["label"]}">Web Sample Classifications So Far</text>
  <text x="{margin_left}" y="88" font-size="20" fill="{colors["muted"]}">Classified months only: 2025-01 to 2026-02. Each column is a 5,000-page month-level sample.</text>

  <rect x="{note_box_x}" y="{note_box_y}" width="280" height="92" rx="14" fill="{colors["card"]}" stroke="{colors["grid"]}" />
  <text x="{note_box_x + 18}" y="{note_box_y + 30}" font-size="18" font-weight="700" fill="{colors["label"]}">Latest month: {latest.period}</text>
  <text x="{note_box_x + 18}" y="{note_box_y + 56}" font-size="17" fill="{colors["ai"]}">AI share: {fmt_pct(latest.ai_share)}</text>
  <text x="{note_box_x + 18}" y="{note_box_y + 80}" font-size="17" fill="{colors["mixed"]}">AI-influenced share: {fmt_pct(latest_mixed_plus_ai)}</text>

  <rect x="{chart_x0}" y="{chart_y0}" width="{chart_width}" height="{chart_height}" rx="18" fill="{colors["card"]}" stroke="{colors["grid"]}" />
  {''.join(grid_lines)}
  <line x1="{chart_x0}" y1="{chart_y1}" x2="{chart_x0 + chart_width}" y2="{chart_y1}" stroke="{colors["axis"]}" stroke-width="1.5" />
  {''.join(bars)}
  <polyline points="{' '.join(influenced_points)}" fill="none" stroke="{colors["mixed"]}" stroke-width="3" stroke-dasharray="8 6" />
  <polyline points="{' '.join(ai_points)}" fill="none" stroke="{colors["ai"]}" stroke-width="3.5" />
  {''.join(x_labels)}

  <text x="{margin_left}" y="{height - 72}" font-size="18" fill="{colors["muted"]}">Stacked bars show Human, Mixed, and AI shares. Dashed line marks AI + Mixed.</text>
  <g transform="translate({margin_left},{height - 46})">
    <rect x="0" y="-12" width="18" height="18" rx="4" fill="{colors["human"]}" />
    <text x="28" y="2" font-size="18" fill="{colors["label"]}">Human</text>
    <rect x="118" y="-12" width="18" height="18" rx="4" fill="{colors["mixed"]}" />
    <text x="146" y="2" font-size="18" fill="{colors["label"]}">Mixed</text>
    <rect x="228" y="-12" width="18" height="18" rx="4" fill="{colors["ai"]}" />
    <text x="256" y="2" font-size="18" fill="{colors["label"]}">AI</text>
    <line x1="328" y1="-3" x2="366" y2="-3" stroke="{colors["mixed"]}" stroke-width="3" stroke-dasharray="8 6" />
    <text x="378" y="2" font-size="18" fill="{colors["label"]}">AI-influenced</text>
  </g>
</svg>
"""


def main() -> None:
    rows = ordered_rows()
    svg = render_svg(rows)
    OUTPUT_PATH.write_text(svg, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    print(f"Periods: {rows[0].period} .. {rows[-1].period} ({len(rows)} months)")


if __name__ == "__main__":
    main()
