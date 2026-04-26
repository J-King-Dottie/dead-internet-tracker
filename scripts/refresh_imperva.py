from __future__ import annotations

import json
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "imperva"


# Compiled from the annual traffic profile charts published in:
# - Imperva 2024 Bad Bot Report (values through 2023)
# - Imperva 2025 Bad Bot Report (2024 update)
YEARS = [str(year) for year in range(2013, 2025)]
BAD_BOT = [23.6, 22.8, 18.6, 19.9, 21.8, 20.4, 24.1, 25.6, 27.7, 30.2, 32.0, 37.0]
GOOD_BOT = [19.4, 36.3, 27.0, 18.8, 20.4, 17.5, 13.1, 15.2, 14.6, 17.3, 17.6, 14.0]
HUMAN = [57.0, 40.9, 54.4, 61.3, 57.8, 62.1, 62.8, 59.2, 57.7, 52.6, 50.4, 49.0]


def build_snapshot() -> dict:
    return {
        "chartKey": "imperva-traffic",
        "title": "Imperva traffic profile",
        "description": "This tracks Imperva's published traffic split over time. For this chart, automated traffic means good bot plus bad bot. It matters because it shows automation overtaking humans in a large observed slice of the web.",
        "source": "Imperva Bad Bot Report 2024 and 2025",
        "lastRefreshed": str(date.today()),
        "method": "We compile the annual traffic profile Imperva publishes in its Bad Bot Report, then combine good bot and bad bot into one automated line. The 2024 point comes from the 2025 report update.",
        "caveats": "This is broader than the Cloudflare chart. Cloudflare above tracks AI bot traffic only; this chart tracks all automation. The levels differ because the metric is broader and the two companies see different slices of the web.",
        "xValues": YEARS,
        "axisValueFormat": "percent1",
        "tooltipValueFormat": "percent1",
        "series": [
            {"name": "Bad bot", "color": "#ff6f7c", "values": BAD_BOT},
            {"name": "Good bot", "color": "#ffd36a", "values": GOOD_BOT},
            {"name": "Human", "color": "#58e6ff", "values": HUMAN},
        ],
    }

def main() -> None:
    snapshot = build_snapshot()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    json_path = DATA_DIR / "imperva.json"
    js_path = DATA_DIR / "imperva.js"

    json_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    js_path.write_text(
        "window.__IMPERVA_SNAPSHOT__ = " + json.dumps(snapshot, indent=2) + ";\n",
        encoding="utf-8",
    )

    print(f"Wrote {json_path}")
    print(f"Wrote {js_path}")


if __name__ == "__main__":
    main()
