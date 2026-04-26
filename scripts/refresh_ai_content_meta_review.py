from __future__ import annotations

import argparse
import csv
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


QUESTION = "How much of the content on the internet is AI generated?"
DATA_DIR = Path("data") / "ai-content-meta-review"
JSON_PATH = DATA_DIR / "ai_content_meta_review.json"
JS_PATH = DATA_DIR / "ai_content_meta_review.js"
CSV_PATH = DATA_DIR / "ai_content_meta_review.csv"
PROTOCOL_PATH = DATA_DIR / "ai_content_meta_review_research_protocol.md"
LOG_PATH = DATA_DIR / "ai_content_meta_review_refresh_log.md"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-5"
DEFAULT_LOOKBACK_DAYS = 35
MIN_QUERY_ITERATIONS = 40


def canonical_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    parts = urlsplit(url)
    scheme = parts.scheme.lower() or "https"
    netloc = parts.netloc.lower()
    path = re.sub(r"/+$", "", parts.path)
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid"}
    ]
    query = urlencode(query_pairs, doseq=True)
    return urlunsplit((scheme, netloc, path, query, ""))


def load_snapshot() -> dict:
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def write_snapshot(snapshot: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(snapshot, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
    JS_PATH.write_text(
        "window.__AI_CONTENT_META_REVIEW_SNAPSHOT__ = "
        + json.dumps(snapshot, indent=4, ensure_ascii=False)
        + ";\n",
        encoding="utf-8",
    )
    with CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["series", "year", "publication_date", "value", "source", "notes"],
        )
        writer.writeheader()
        for row in snapshot["rows"]:
            writer.writerow(
                {
                    "series": row["series"],
                    "year": row["year"],
                    "publication_date": row["publication_date"],
                    "value": row["value"],
                    "source": row["source"],
                    "notes": row["notes"],
                }
            )


def parse_percent(value: str) -> float | None:
    match = re.search(r"-?\d+(?:\.\d+)?", value or "")
    if not match:
        return None
    parsed = float(match.group(0))
    if parsed < 0 or parsed > 100:
        return None
    return parsed


def parse_iso_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def normalize_notes(notes: str) -> str:
    return " ".join((notes or "").split())


def notes_sentence_count(notes: str) -> int:
    return len([part for part in re.split(r"(?<=[.!?])\s+", notes.strip()) if part])


def existing_identity(row: dict) -> tuple[str, int, str]:
    series_key = re.sub(r"\s+", " ", row.get("series", "").strip().lower())
    return (series_key, int(row.get("year", 0)), canonical_url(row.get("source", "")))


def is_duplicate(candidate: dict, existing_rows: list[dict]) -> bool:
    candidate_identity = existing_identity(candidate)
    candidate_url = candidate_identity[2]
    candidate_series = candidate_identity[0]
    candidate_year = candidate_identity[1]
    candidate_value = parse_percent(candidate.get("value", ""))
    for row in existing_rows:
        row_identity = existing_identity(row)
        if candidate_url and candidate_url == row_identity[2]:
            return True
        if candidate_series == row_identity[0] and candidate_year == row_identity[1]:
            row_value = parse_percent(row.get("value", ""))
            if row_value is None or candidate_value is None:
                return True
            if abs(row_value - candidate_value) <= 0.05:
                return True
    return False


def validate_candidate(candidate: dict, today: date, earliest_publication_date: date) -> str | None:
    required = ["series", "year", "publication_date", "value", "source", "notes"]
    for field in required:
        if not str(candidate.get(field, "")).strip():
            return f"missing {field}"
    try:
        year = int(candidate["year"])
    except (TypeError, ValueError):
        return "invalid year"
    if year < 2020 or year > today.year:
        return "year outside chart range"
    publication_date = parse_iso_date(str(candidate["publication_date"]))
    if not publication_date:
        return "publication_date is not YYYY-MM-DD"
    if publication_date < earliest_publication_date:
        return "publication is outside recent-refresh window"
    if publication_date > today + timedelta(days=1):
        return "publication_date is in the future"
    if parse_percent(str(candidate["value"])) is None:
        return "value is not a valid percentage"
    if not canonical_url(str(candidate["source"])):
        return "source URL is invalid"
    notes = normalize_notes(str(candidate["notes"]))
    if notes_sentence_count(notes) != 3:
        return "notes must be exactly three sentences"
    return None


def extract_response_text(payload: dict) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]

    chunks: list[str] = []
    for item in payload.get("output", []):
        if item.get("type") == "message":
            for content in item.get("content", []):
                text = content.get("text")
                if isinstance(text, str):
                    chunks.append(text)
    return "\n".join(chunks).strip()


def recent_research_schema() -> dict:
    candidate_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "series": {"type": "string"},
            "year": {"type": "integer"},
            "publication_date": {"type": "string"},
            "value": {"type": "string"},
            "source": {"type": "string"},
            "notes": {"type": "string"},
            "source_type": {"type": "string"},
            "platform_or_corpus": {"type": "string"},
            "modality": {"type": "string"},
            "method_type": {"type": "string"},
            "dedupe_rationale": {"type": "string"},
            "supporting_evidence": {"type": "string"},
        },
        "required": [
            "series",
            "year",
            "publication_date",
            "value",
            "source",
            "notes",
            "source_type",
            "platform_or_corpus",
            "modality",
            "method_type",
            "dedupe_rationale",
            "supporting_evidence",
        ],
    }
    rejected_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "source": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["source", "reason"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "search_scope": {"type": "string"},
            "query_iterations": {"type": "integer"},
            "lanes_searched": {"type": "array", "items": {"type": "string"}},
            "candidates": {"type": "array", "items": candidate_schema},
            "rejected": {"type": "array", "items": rejected_schema},
            "remaining_gaps": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "search_scope",
            "query_iterations",
            "lanes_searched",
            "candidates",
            "rejected",
            "remaining_gaps",
        ],
    }


def build_prompt(snapshot: dict, protocol: str, earliest_publication_date: date, today: date) -> str:
    existing_rows = snapshot.get("rows", [])
    existing_sources = sorted({canonical_url(row.get("source", "")) for row in existing_rows if row.get("source")})
    existing_series = sorted({f"{row.get('series')} ({row.get('year')})" for row in existing_rows})
    return f"""
You are refreshing the Dead Internet Tracker AI content meta-review chart.

This is a weekly recent-source sweep, not a historical rebuild.
Today is {today.isoformat()}.
Only include sources with publication dates on or after {earliest_publication_date.isoformat()}.
The goal is to find newly published public estimates we are missing for the share of online content that is AI-generated or materially LLM-assisted.

Follow this protocol exactly:
{protocol}

Existing source URLs to dedupe against:
{json.dumps(existing_sources, indent=2)}

Existing study/year rows to dedupe against:
{json.dumps(existing_series, indent=2)}

Search requirements for this weekly run:
- Use web search thoroughly.
- Run at least {MIN_QUERY_ITERATIONS} distinct search iterations.
- Search recent academic, preprint, institutional, industry, platform, news, and analyst lanes.
- Search for recent estimates across web pages, social posts, reviews, academic writing, news, images, video, music, and platform-specific corpora.
- Include arXiv, journal/conference pages, Google-Scholar-style broad queries, institutional reports, industry studies, and high-quality secondary summaries when the primary source is unavailable.
- Do not include traffic, bot traffic, AI adoption, SEO/referral displacement, recommendation share, or vague commentary unless it contains a content-share denominator.
- Do not duplicate sources already listed above or the same underlying estimate through a weaker secondary source.
- Prefer primary sources, but accept strong secondary summaries when they preserve the denominator, method, and scope.

Return JSON only. For every kept candidate, notes must be exactly three short sentences:
1. claim with estimate and scope
2. method
3. caveat
""".strip()


def call_openai_research(prompt: str, model: str, api_key: str) -> dict:
    request_body = {
        "model": model,
        "tools": [{"type": "web_search"}],
        "input": [
            {
                "role": "system",
                "content": (
                    "You are a careful research assistant maintaining a static public dashboard. "
                    "Prioritize source quality, dedupe aggressively, and output only schema-valid JSON."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "recent_ai_content_research",
                "strict": True,
                "schema": recent_research_schema(),
            }
        },
    }
    request = Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=900) as response:
        payload = json.load(response)
    text = extract_response_text(payload)
    if not text:
        raise RuntimeError("OpenAI response did not include output text")
    return json.loads(text)


def append_log(
    today: date,
    research: dict,
    added_rows: list[dict],
    rejected_reasons: list[str],
    earliest_publication_date: date,
) -> None:
    added = [f"  - {row['series']} ({row['year']})" for row in added_rows] or ["  - none"]
    rejected = [f"  - {reason}" for reason in rejected_reasons[:8]] or ["  - none"]
    lanes = [f"  - {lane}" for lane in research.get("lanes_searched", [])] or ["  - not reported"]
    gaps = [f"  - {gap}" for gap in research.get("remaining_gaps", [])] or ["  - not reported"]
    entry = f"""

## {today.isoformat()} - Automated Weekly Recent-Source Sweep

- scope: recent public estimates published from `{earliest_publication_date.isoformat()}` through `{today.isoformat()}`
- query iterations reported: {research.get("query_iterations", 0)}
- lanes searched:
{chr(10).join(lanes)}
- added:
{chr(10).join(added)}
- rejected or skipped:
{chr(10).join(rejected)}
- gaps still thin:
{chr(10).join(gaps)}
""".rstrip()
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(entry + "\n")


def refresh(model: str, lookback_days: int, dry_run: bool) -> int:
    today = datetime.now(timezone.utc).date()
    earliest_publication_date = today - timedelta(days=lookback_days)
    snapshot = load_snapshot()
    protocol = PROTOCOL_PATH.read_text(encoding="utf-8")

    if dry_run:
        print("Dry run OK.")
        print(f"Existing rows: {len(snapshot.get('rows', []))}")
        print(f"Recent publication window starts: {earliest_publication_date.isoformat()}")
        return 0

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required")

    research = call_openai_research(
        build_prompt(snapshot, protocol, earliest_publication_date, today),
        model=model,
        api_key=api_key,
    )
    existing_rows = list(snapshot.get("rows", []))
    added_rows: list[dict] = []
    rejected_reasons: list[str] = []

    reported_iterations = int(research.get("query_iterations", 0) or 0)
    if reported_iterations < MIN_QUERY_ITERATIONS:
        rejected_reasons.append(
            f"Run reported only {reported_iterations} query iterations; required {MIN_QUERY_ITERATIONS}."
        )

    for candidate in research.get("candidates", []):
        candidate = {
            "series": str(candidate.get("series", "")).strip(),
            "year": int(candidate.get("year", 0) or 0),
            "value": str(candidate.get("value", "")).strip(),
            "source": str(candidate.get("source", "")).strip(),
            "notes": normalize_notes(str(candidate.get("notes", ""))),
            "publication_date": str(candidate.get("publication_date", "")).strip(),
        }
        reason = validate_candidate(candidate, today, earliest_publication_date)
        if reason:
            rejected_reasons.append(f"{candidate.get('series') or candidate.get('source')}: {reason}")
            continue
        if is_duplicate(candidate, existing_rows + added_rows):
            rejected_reasons.append(f"{candidate['series']} ({candidate['year']}): duplicate source or estimate")
            continue
        added_rows.append(candidate)

    if not added_rows:
        append_log(today, research, added_rows, rejected_reasons, earliest_publication_date)
        print("No new rows added.")
        return 0

    snapshot["lastRefreshed"] = today.isoformat()
    snapshot["rows"] = sorted(
        existing_rows + added_rows,
        key=lambda row: (int(row["year"]), row["series"].lower(), row["publication_date"], row["source"]),
    )
    write_snapshot(snapshot)
    append_log(today, research, added_rows, rejected_reasons, earliest_publication_date)
    print(f"Added {len(added_rows)} new row(s).")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh the AI content meta-review with recent public sources.")
    parser.add_argument("--model", default=os.environ.get("OPENAI_RESEARCH_MODEL", DEFAULT_MODEL))
    parser.add_argument("--lookback-days", type=int, default=int(os.environ.get("RESEARCH_LOOKBACK_DAYS", DEFAULT_LOOKBACK_DAYS)))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    raise SystemExit(refresh(args.model, args.lookback_days, args.dry_run))


if __name__ == "__main__":
    main()
