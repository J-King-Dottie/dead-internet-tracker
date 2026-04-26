from __future__ import annotations

import json
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "imperva"

MONTH_LABELS = [f"{year}-{month:02d}" for year in (2022, 2023, 2024) for month in range(1, 13)]

# Reconstructed from published Imperva charts:
# - 2024 Bad Bot Report: 2022 vs 2023 monthly ATO chart
# - 2025 Bad Bot Report: 2023 vs 2024 monthly ATO chart
# Values are approximate and digitized from the figures.
ATO_2022 = [121000, 119000, 242000, 167000, 172000, 206000, 213000, 291000, 182000, 167000, 218000, 251000]
ATO_2023 = [216000, 226000, 233000, 163000, 265000, 231000, 239000, 215000, 183000, 206000, 201000, 192000]
ATO_2024 = [188000, 185000, 242000, 233000, 282000, 355000, 375000, 330000, 321000, 364000, 355000, 327000]


def build_snapshot() -> dict:
    return {
        "chartKey": "imperva-ato",
        "title": "Imperva monthly account takeover attacks",
        "description": "This tracks monthly account takeover attacks in Imperva's reports. It matters because it shows cheap automation making account abuse more industrial.",
        "source": "Imperva 2024 and 2025 Bad Bot Reports",
        "lastRefreshed": str(date.today()),
        "method": "We read the values off Imperva's published monthly ATO charts and stitched them into one series. It is not perfect, but it is reasonably accurate.",
        "caveats": "This is chart-read from published figures, not raw source data. It is a bot-abuse metric, not a direct measure of AI content or human displacement.",
        "xValues": MONTH_LABELS,
        "axisValueFormat": "compact",
        "tooltipValueFormat": "integer",
        "series": [
            {"name": "ATO attacks", "color": "#ff79c6", "values": ATO_2022 + ATO_2023 + ATO_2024},
        ],
    }


def main() -> None:
    snapshot = build_snapshot()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    json_path = DATA_DIR / "imperva_ato.json"
    js_path = DATA_DIR / "imperva_ato.js"

    json_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    js_path.write_text(
        "window.__IMPERVA_ATO_SNAPSHOT__ = " + json.dumps(snapshot, indent=2) + ";\n",
        encoding="utf-8",
    )

    print(f"Wrote {json_path}")
    print(f"Wrote {js_path}")


if __name__ == "__main__":
    main()
