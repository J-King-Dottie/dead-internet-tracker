from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
from datetime import date, datetime, timedelta, timezone
from http.client import RemoteDisconnected
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


DATA_DIR = Path("data") / "ai-content-meta-review"
JSON_PATH = DATA_DIR / "ai_content_meta_review.json"
JS_PATH = DATA_DIR / "ai_content_meta_review.js"
CSV_PATH = DATA_DIR / "ai_content_meta_review.csv"
PROTOCOL_PATH = DATA_DIR / "ai_content_meta_review_research_protocol.md"
LOG_PATH = DATA_DIR / "ai_content_meta_review_refresh_log.md"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-5.4"
DEFAULT_REASONING_EFFORT = "low"
DEFAULT_LOOKBACK_DAYS = 7
MIN_QUERY_ITERATIONS = 10
OPENAI_REQUEST_ATTEMPTS = 3
RETRYABLE_HTTP_STATUS = {408, 409, 429, 500, 502, 503, 504}
OPENAI_POLL_SECONDS = 5


def should_log_poll_lines() -> bool:
    configured = os.environ.get("OPENAI_POLL_LOG", "").strip().lower()
    if configured:
        return configured in {"1", "true", "yes", "on"}
    return not os.environ.get("GITHUB_ACTIONS")


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


def is_clean_percent(value: str) -> bool:
    return bool(re.fullmatch(r"\d+(?:\.\d+)?%", (value or "").strip()))


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
        if candidate_url and candidate_url == row_identity[2] and candidate_year == row_identity[1]:
            return True
        if candidate_series == row_identity[0] and candidate_year == row_identity[1]:
            row_value = parse_percent(row.get("value", ""))
            if row_value is None or candidate_value is None:
                return True
            if abs(row_value - candidate_value) <= 0.05:
                return True
    return False


def validate_candidate(candidate: dict, today: date) -> str | None:
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
    if publication_date > today + timedelta(days=1):
        return "publication_date is in the future"
    if not is_clean_percent(str(candidate["value"])) or parse_percent(str(candidate["value"])) is None:
        return "value must be an exact percentage string like 12.3%"
    if not canonical_url(str(candidate["source"])):
        return "source URL is invalid"
    notes = normalize_notes(str(candidate["notes"]))
    if notes_sentence_count(notes) != 3:
        return "notes must be exactly three sentences"
    return None


def normalize_candidate(candidate: dict) -> dict:
    try:
        year = int(candidate.get("year", 0) or 0)
    except (TypeError, ValueError):
        year = 0
    return {
        "series": str(candidate.get("series", "")).strip(),
        "year": year,
        "value": str(candidate.get("value", "")).strip(),
        "source": str(candidate.get("source", "")).strip(),
        "notes": normalize_notes(str(candidate.get("notes", ""))),
        "publication_date": str(candidate.get("publication_date", "")).strip(),
    }


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


def openai_json_request(method: str, url: str, api_key: str, timeout: int, request_body: dict | None = None) -> dict:
    data = json.dumps(request_body).encode("utf-8") if request_body is not None else None
    headers = {"Authorization": f"Bearer {api_key}"}
    if request_body is not None:
        headers["Content-Type"] = "application/json"
    for attempt in range(1, OPENAI_REQUEST_ATTEMPTS + 1):
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code not in RETRYABLE_HTTP_STATUS or attempt == OPENAI_REQUEST_ATTEMPTS:
                raise
        except (RemoteDisconnected, TimeoutError, URLError):
            if attempt == OPENAI_REQUEST_ATTEMPTS:
                raise

        sleep_seconds = min(2 ** attempt, 30)
        print(f"OpenAI request failed; retrying in {sleep_seconds}s ({attempt}/{OPENAI_REQUEST_ATTEMPTS})", flush=True)
        time.sleep(sleep_seconds)

    raise RuntimeError("OpenAI request failed without returning a response")


def create_openai_response(request_body: dict, api_key: str, timeout: int) -> dict:
    return openai_json_request("POST", OPENAI_RESPONSES_URL, api_key, timeout, {**request_body, "background": True})


def fetch_openai_response(response_id: str, api_key: str) -> dict:
    return openai_json_request("GET", f"{OPENAI_RESPONSES_URL}/{response_id}", api_key, timeout=120)


def wait_for_openai_response(response_id: str, api_key: str, timeout_seconds: int) -> dict:
    deadline = time.monotonic() + timeout_seconds
    log_poll_lines = should_log_poll_lines()
    while True:
        payload = fetch_openai_response(response_id, api_key)
        status = payload.get("status")
        if log_poll_lines:
            print(f"poll response_id={response_id} status={status}", flush=True)
        if status == "completed":
            return payload
        if status in {"failed", "cancelled", "incomplete"}:
            raise RuntimeError(f"OpenAI response ended with status {status}: {payload}")
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Timed out waiting for OpenAI response {response_id}")
        time.sleep(OPENAI_POLL_SECONDS)


def openai_background_response(request_body: dict, api_key: str, timeout_seconds: int) -> dict:
    payload = create_openai_response(request_body, api_key, timeout=120)
    response_id = payload.get("id")
    print(f"submitted response_id={response_id or '(missing)'} status={payload.get('status')}", flush=True)
    if payload.get("status") == "completed":
        return payload
    if not response_id:
        raise RuntimeError(f"OpenAI background response did not include an id: {payload}")
    return wait_for_openai_response(response_id, api_key, timeout_seconds)


def recent_research_schema() -> dict:
    candidate_schema = research_candidate_schema()
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "search_scope": {"type": "string"},
            "query_iterations": {"type": "integer"},
            "lanes_searched": {"type": "array", "items": {"type": "string"}},
            "candidates": {"type": "array", "items": candidate_schema},
        },
        "required": ["search_scope", "query_iterations", "lanes_searched", "candidates"],
    }


def research_candidate_schema() -> dict:
    return {
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


def repair_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "candidates": {"type": "array", "items": research_candidate_schema()},
        },
        "required": ["candidates"],
    }


def protocol_for_weekly_prompt(protocol: str) -> str:
    omitted_sections = {"Search Standard", "Refresh Output Standard"}
    kept: list[str] = []
    skip = False
    for line in protocol.splitlines():
        section_match = re.match(r"^##\s+(.+?)\s*$", line)
        if section_match:
            skip = section_match.group(1) in omitted_sections
        if not skip and "reason included or reason rejected" not in line.lower():
            kept.append(line)
    return "\n".join(kept).strip()


def build_prompt(
    snapshot: dict,
    protocol: str,
    recent_publication_date: date,
    today: date,
) -> str:
    existing_rows = snapshot.get("rows", [])
    weekly_protocol = protocol_for_weekly_prompt(protocol)
    existing_sources = sorted({canonical_url(row.get("source", "")) for row in existing_rows if row.get("source")})
    existing_series = sorted({f"{row.get('series')} ({row.get('year')})" for row in existing_rows})
    return f"""
You are refreshing the Dead Internet Tracker AI content meta-review chart.

Today is {today.isoformat()}.
Goal: find missing published estimates for the share of online content that is AI-generated or materially LLM-assisted.

Use this protocol excerpt for inclusion standards, source quality, dedupe judgment, and note format.
It intentionally omits the full-refresh search-volume and refresh-log sections because this is a weekly incremental run.
{weekly_protocol}

Existing source URLs to dedupe against:
{json.dumps(existing_sources, indent=2)}

Existing study/year rows to dedupe against:
{json.dumps(existing_series, indent=2)}

Search scope:
- First search for sources published since {recent_publication_date.isoformat()}.
- Then search for missed {today.year} sources.
- If you discover an older strong source while searching, include it when it adds missing 2020+ annual points.
- If a source contains an annual time series, extract every qualifying annual point from 2020 onward as separate candidate rows.

Deep search standard:
- Run about {MIN_QUERY_ITERATIONS} broad search iterations across varied query phrasings and source types.
- Each search iteration should inspect multiple promising results before moving on.
- Cover academic/preprint, industry/platform, institutional/policy, and media/analyst discovery lanes.
- Search across text, web pages, social posts, reviews, academic writing, news, images, video, music, code, product listings, app reviews, and platform-specific corpora.
- Use targeted site queries for likely sources such as arxiv.org, pubmed.ncbi.nlm.nih.gov, aclanthology.org, ssrn.com, originality.ai, copyleaks.com, graphite.io, and major platform or report domains.
- For each promising source, verify the denominator, year, method, publication date, and whether it is primary or secondary before including it.

Hard exclusions:
- Exclude traffic, bot traffic, AI adoption, SEO/referral displacement, recommendation share, and vague commentary unless there is a clear content-share denominator.
- Do not duplicate the same source-year or the same underlying estimate through a weaker secondary source.

Return JSON only. For every kept candidate, notes must be exactly three short sentences:
1. claim with estimate and scope
2. method
3. caveat
Use an exact percentage string in value, such as "12.3%".
""".strip()


def call_openai_research(prompt: str, model: str, api_key: str) -> dict:
    request_body = {
        "model": model,
        "reasoning": {"effort": DEFAULT_REASONING_EFFORT},
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

    payload = openai_background_response(request_body, api_key, timeout_seconds=900)
    text = extract_response_text(payload)
    if not text:
        raise RuntimeError("OpenAI response did not include output text")
    return json.loads(text)


def call_openai_repair(
    candidates: list[dict],
    validation_errors: list[str],
    today: date,
    model: str,
    api_key: str,
) -> list[dict]:
    if not candidates:
        return []
    repair_items = [
        {"candidate": candidate, "error": error}
        for candidate, error in zip(candidates, validation_errors)
    ]
    prompt = f"""
Repair candidate rows for the Dead Internet Tracker AI content meta-review table.

Today is {today.isoformat()}.
Return only candidates that can be corrected into valid rows.
Drop candidates when the source does not actually contain a content-share estimate.

Validation rules:
- year must be an integer from 2020 through {today.year}
- publication_date must be YYYY-MM-DD and not in the future
- value must be an exact percentage string from 0% to 100%, such as 12.3%
- source must be a valid URL
- notes must be exactly three short sentences: claim with estimate and scope; method; caveat

Candidates and validation errors:
{json.dumps(repair_items, indent=2)}
""".strip()
    request_body = {
        "model": model,
        "reasoning": {"effort": DEFAULT_REASONING_EFFORT},
        "tools": [{"type": "web_search"}],
        "input": [
            {
                "role": "system",
                "content": (
                    "You repair structured research rows. Verify source context when needed, "
                    "return only valid corrected rows, and output schema-valid JSON."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "repaired_ai_content_candidates",
                "strict": True,
                "schema": repair_schema(),
            }
        },
    }
    payload = openai_background_response(request_body, api_key, timeout_seconds=600)
    text = extract_response_text(payload)
    if not text:
        return []
    return [normalize_candidate(candidate) for candidate in json.loads(text).get("candidates", [])]


def append_log(
    today: date,
    research: dict,
    added_rows: list[dict],
) -> None:
    added = [f"  - {row['series']} ({row['year']})" for row in added_rows] or ["  - none"]
    lanes = [f"  - {lane}" for lane in research.get("lanes_searched", [])] or ["  - not reported"]
    entry = f"""

## {today.isoformat()} - Automated Weekly Recent-Source Sweep

- scope: recent priority plus `{today.year}` missed-source search; older publication dates allowed when discovered
- query iterations reported: {research.get("query_iterations", 0)}
- lanes searched:
{chr(10).join(lanes)}
- added:
{chr(10).join(added)}
""".rstrip()
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(entry + "\n")


def refresh(model: str, lookback_days: int, dry_run: bool) -> int:
    started_at = time.monotonic()
    today = datetime.now(timezone.utc).date()
    earliest_publication_date = date(today.year, 1, 1)
    recent_publication_date = today - timedelta(days=lookback_days)
    snapshot = load_snapshot()
    protocol = PROTOCOL_PATH.read_text(encoding="utf-8")

    if dry_run:
        print("Dry run OK.", flush=True)
        print(f"Existing rows: {len(snapshot.get('rows', []))}", flush=True)
        print(f"Current-year search focus starts: {earliest_publication_date.isoformat()}", flush=True)
        print(f"Recent priority window starts: {recent_publication_date.isoformat()}", flush=True)
        print("Older publication dates are allowed when discovered during the search.", flush=True)
        return 0

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required")

    print(f"Starting AI content research refresh with model={model}, reasoning_effort={DEFAULT_REASONING_EFFORT}", flush=True)
    research = call_openai_research(
        build_prompt(snapshot, protocol, recent_publication_date, today),
        model=model,
        api_key=api_key,
    )
    print(f"parsing completed API response: {len(research.get('candidates', []))} candidate(s)", flush=True)
    existing_rows = list(snapshot.get("rows", []))
    added_rows: list[dict] = []

    reported_iterations = int(research.get("query_iterations", 0) or 0)
    if reported_iterations < MIN_QUERY_ITERATIONS:
        print(f"Search depth warning: reported {reported_iterations} query iterations; requested {MIN_QUERY_ITERATIONS}.", flush=True)

    repair_candidates: list[dict] = []
    repair_errors: list[str] = []
    for candidate in research.get("candidates", []):
        candidate = normalize_candidate(candidate)
        reason = validate_candidate(candidate, today)
        if reason:
            repair_candidates.append(candidate)
            repair_errors.append(reason)
            continue
        if is_duplicate(candidate, existing_rows + added_rows):
            continue
        added_rows.append(candidate)

    if repair_candidates:
        print(f"validating candidates: repairing {len(repair_candidates)} invalid candidate(s)", flush=True)
    for candidate in call_openai_repair(repair_candidates, repair_errors, today, model, api_key):
        reason = validate_candidate(candidate, today)
        if reason:
            continue
        if is_duplicate(candidate, existing_rows + added_rows):
            continue
        added_rows.append(candidate)

    if not added_rows:
        append_log(today, research, added_rows)
        elapsed = time.monotonic() - started_at
        print(f"No new rows added. Finished in {elapsed:.1f}s.", flush=True)
        return 0

    snapshot["lastRefreshed"] = today.isoformat()
    snapshot["rows"] = sorted(
        existing_rows + added_rows,
        key=lambda row: (int(row["year"]), row["series"].lower(), row["publication_date"], row["source"]),
    )
    write_snapshot(snapshot)
    append_log(today, research, added_rows)
    elapsed = time.monotonic() - started_at
    unique_sources = len({row["source"] for row in added_rows})
    print(f"writing files complete: added {len(added_rows)} new row(s) from {unique_sources} unique source(s). Finished in {elapsed:.1f}s.", flush=True)
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
