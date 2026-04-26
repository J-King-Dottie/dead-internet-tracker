from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import re
import sys
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from html.parser import HTMLParser
from functools import lru_cache
from pathlib import Path
from typing import Iterable
import time

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _aws_common import s3_client
RUBRIC_VERSION = "research-guided-rubric-v3"
SYSTEM_PROMPT = (
    "This is one step in a fixed repeated methodology for the Dead Internet Tracker. "
    "Your job is to label sampled open-web writing consistently so the results are comparable over time. "
    "You classify webpage excerpts as Human, Mixed, or AI. "
    "Human means the writing appears to be all human. "
    "Mixed means some level of AI writing appears evident. "
    "AI means there is a strong signal of AI writing. "
    "Base the label on the writing itself, not the topic. "
    "Think carefully enough to make a best label judgment from the excerpt. "
    "Use a research-guided rubric that weighs lexical variety and repetition, sentence and syntactic variation, discourse cohesion and progression, readability and register, and personal reference or concrete specificity. "
    "Each excerpt may also include supporting metrics for lexical diversity, repeated 3-gram rate, and sentence-length standard deviation. "
    "Use those metrics as supporting evidence only, not as an automatic override. "
    "Useful signals toward AI can include unusually standardized or impersonal register, repetitive phrasing, flatter sentence rhythm, smooth but generic progression, or repeated templated discourse-marker openings. "
    "Personal reference or concrete specificity can support Human, but their absence alone is not enough for AI. "
    "Use Human when the writing appears all human under the rubric. "
    "Use Mixed only when some real AI-writing signal appears present but not strong enough for AI. "
    "Use AI when the excerpt shows a large enough concentration of AI-writing signals under the rubric. "
    "No single cue is decisive. "
    "Judge patterns across the excerpt, not one phrase in isolation. "
    "Do not rely on first-person pronouns, contractions, family references, or minor grammatical roughness as stand-alone evidence for Human. "
    "Do not treat polished, factual, or generic writing by itself as enough for AI. "
    "Do not use Mixed as a fallback for uncertainty. "
    "Do not use uncertainty by itself as a reason to choose Human. "
    "Return one label for every provided id exactly once, with no omissions and no duplicates. "
    "Return JSON only."
)
USER_PROMPT_GUIDANCE = [
    "Label each webpage excerpt as Human, Mixed, or AI.",
    "Use the system rubric and definitions exactly.",
    "Return one label for each id exactly once.",
    "Do not repeat ids.",
    "Do not omit ids.",
]
PROMPT_HASH = hashlib.sha1((SYSTEM_PROMPT + "\n" + "\n".join(USER_PROMPT_GUIDANCE)).encode("utf-8")).hexdigest()


class TextExtractor(HTMLParser):
    SKIP_TAGS = {"script", "style", "noscript", "svg", "head"}
    BLOCK_TAGS = {
        "p",
        "div",
        "article",
        "section",
        "main",
        "br",
        "li",
        "ul",
        "ol",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "blockquote",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
        elif tag in self.BLOCK_TAGS and self.parts and self.parts[-1] != "\n":
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1
        elif tag in self.BLOCK_TAGS and self.parts and self.parts[-1] != "\n":
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        cleaned = data.strip()
        if cleaned:
            self.parts.append(cleaned)
            self.parts.append(" ")

    def get_text(self) -> str:
        text = "".join(self.parts)
        text = re.sub(r"\n{2,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()


@dataclass
class SampleRow:
    page_id: str
    period: str
    url: str
    domain: str
    sample_source: str
    warc_filename: str
    warc_record_offset: int
    warc_record_length: int
    content_charset: str | None


def read_csv_rows(path: Path) -> list[SampleRow]:
    rows: list[SampleRow] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for idx, row in enumerate(reader, start=1):
            rows.append(
                SampleRow(
                    page_id=f"page-{idx:05d}",
                    period=row["period"],
                    url=row["url"],
                    domain=row["domain"],
                    sample_source=row["sample_source"],
                    warc_filename=row["warc_filename"],
                    warc_record_offset=int(row["warc_record_offset"]),
                    warc_record_length=int(row["warc_record_length"]),
                    content_charset=(row.get("content_charset") or "").strip() or None,
                )
            )
    return rows


@lru_cache(maxsize=1)
def commoncrawl_client():
    root = Path(__file__).resolve().parent.parent
    return s3_client(root)


def fetch_warc_record(row: SampleRow) -> bytes:
    start = row.warc_record_offset
    end = row.warc_record_offset + row.warc_record_length - 1
    response = commoncrawl_client().get_object(
        Bucket="commoncrawl",
        Key=row.warc_filename,
        Range=f"bytes={start}-{end}",
    )
    return response["Body"].read()


def split_double_newline(data: bytes) -> tuple[bytes, bytes]:
    marker = b"\r\n\r\n"
    idx = data.find(marker)
    if idx != -1:
        return data[:idx], data[idx + len(marker) :]
    marker = b"\n\n"
    idx = data.find(marker)
    if idx != -1:
        return data[:idx], data[idx + len(marker) :]
    return data, b""


def extract_html_from_warc(gzipped_record: bytes) -> bytes:
    warc = gzip.decompress(gzipped_record)
    _, http_response = split_double_newline(warc)
    _, html = split_double_newline(http_response)
    return html


def decode_html(raw_html: bytes, content_charset: str | None) -> str:
    candidates = []
    if content_charset:
        candidates.append(content_charset)
    candidates.extend(["utf-8", "windows-1252", "latin-1"])
    for charset in candidates:
        try:
            return raw_html.decode(charset, errors="strict")
        except Exception:
            continue
    return raw_html.decode("utf-8", errors="ignore")


def extract_main_text(html: str) -> str:
    parser = TextExtractor()
    parser.feed(html)
    parser.close()
    text = parser.get_text()
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def first_n_tokens(text: str, token_limit: int) -> str:
    tokens = text.split()
    return " ".join(tokens[:token_limit])


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", text.lower())


def lexical_diversity(text: str) -> float:
    tokens = words(text)
    if not tokens:
        return 0.0
    return len(set(tokens)) / len(tokens)


def repeated_ngram_rate(text: str, n: int = 3) -> float:
    tokens = words(text)
    if len(tokens) < n:
        return 0.0
    ngrams = [tuple(tokens[idx : idx + n]) for idx in range(len(tokens) - n + 1)]
    if not ngrams:
        return 0.0
    counts: dict[tuple[str, ...], int] = {}
    for ngram in ngrams:
        counts[ngram] = counts.get(ngram, 0) + 1
    repeated = sum(count - 1 for count in counts.values() if count > 1)
    return repeated / len(ngrams)


def sentence_length_stddev(text: str) -> float:
    sentence_chunks = re.split(r"[.!?]+", text)
    lengths = [len(words(chunk)) for chunk in sentence_chunks if words(chunk)]
    if len(lengths) < 2:
        return 0.0
    mean = sum(lengths) / len(lengths)
    variance = sum((length - mean) ** 2 for length in lengths) / len(lengths)
    return math.sqrt(variance)


def compute_metrics(text: str) -> dict[str, float]:
    return {
        "lexical_diversity": round(lexical_diversity(text), 4),
        "repeated_3gram_rate": round(repeated_ngram_rate(text, n=3), 4),
        "sentence_length_stddev": round(sentence_length_stddev(text), 4),
    }


def chunked(items: list[dict], size: int) -> Iterable[list[dict]]:
    for idx in range(0, len(items), size):
        yield items[idx : idx + size]


def build_user_prompt(items: list[dict]) -> str:
    item_ids = [item["id"] for item in items]
    lines = [
        *USER_PROMPT_GUIDANCE,
        "Use only these ids in the output:",
        ", ".join(item_ids),
        "",
    ]
    for item in items:
        lines.extend(
            [
                f"ID: {item['id']}",
                f"URL: {item['url']}",
                "METRICS:",
                (
                    "lexical_diversity="
                    f"{item['metrics']['lexical_diversity']}, "
                    "repeated_3gram_rate="
                    f"{item['metrics']['repeated_3gram_rate']}, "
                    "sentence_length_stddev="
                    f"{item['metrics']['sentence_length_stddev']}"
                ),
                "EXCERPT:",
                item["excerpt"],
                "",
            ]
        )
    return "\n".join(lines).strip()


def build_json_schema(items: list[dict]) -> dict:
    item_ids = [item["id"] for item in items]
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "labels_by_id": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    item_id: {"type": "string", "enum": ["Human", "Mixed", "AI"]}
                    for item_id in item_ids
                },
                "required": item_ids,
            }
        },
        "required": ["labels_by_id"],
    }


def build_request_line(period: str, batch_index: int, items: list[dict], model: str) -> dict:
    body = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": SYSTEM_PROMPT}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": build_user_prompt(items)}],
            },
        ],
        "max_output_tokens": 3000,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "web_sample_labels",
                "strict": True,
                "schema": build_json_schema(items),
            }
        },
    }
    if model.startswith("gpt-5"):
        body["reasoning"] = {"effort": "low"}
    else:
        body["temperature"] = 0

    return {
        "custom_id": f"web-sample-{period}-part-{batch_index:04d}",
        "method": "POST",
        "url": "/v1/responses",
        "body": body,
    }


def prepare_page(row: SampleRow, token_limit: int, min_tokens: int) -> dict | None:
    warc_record = fetch_warc_record(row)
    html_bytes = extract_html_from_warc(warc_record)
    html = decode_html(html_bytes, row.content_charset)
    main_text = extract_main_text(html)
    excerpt = first_n_tokens(main_text, token_limit)
    token_count = len(excerpt.split())
    if token_count < min_tokens:
        return None
    metrics = compute_metrics(excerpt)
    return {
        "id": row.page_id,
        "period": row.period,
        "url": row.url,
        "domain": row.domain,
        "sample_source": row.sample_source,
        "warc_filename": row.warc_filename,
        "warc_record_offset": row.warc_record_offset,
        "warc_record_length": row.warc_record_length,
        "excerpt": excerpt,
        "excerpt_token_count": token_count,
        "metrics": metrics,
    }


def load_resume_payload(
    prepared_path: Path,
    input_paths: list[Path],
    period: str,
    args: argparse.Namespace,
) -> tuple[list[dict], int, set[str]]:
    if not prepared_path.exists():
        return [], 0, set()

    try:
        payload = json.loads(prepared_path.read_text(encoding="utf-8"))
    except Exception:
        return [], 0, set()

    expected_inputs = [str(path) for path in input_paths]
    if payload.get("period") != period:
        return [], 0, set()
    if payload.get("inputCsvs") != expected_inputs:
        return [], 0, set()
    if payload.get("model") != args.model:
        return [], 0, set()
    if payload.get("tokenLimit") != args.token_limit:
        return [], 0, set()
    if payload.get("minTokens") != args.min_tokens:
        return [], 0, set()
    if payload.get("targetUsable") != args.target_usable:
        return [], 0, set()

    page_rows = list(payload.get("pages", []))
    dropped = int(payload.get("droppedCount", 0))
    processed_page_ids = set(payload.get("processedPageIds", []))
    return page_rows, dropped, processed_page_ids


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, nargs="+", help="One or more CSV files exported from Athena")
    parser.add_argument("--group-size", type=int, default=20)
    parser.add_argument("--model", default="gpt-5-mini")
    parser.add_argument("--token-limit", type=int, default=1000)
    parser.add_argument("--min-tokens", type=int, default=400)
    parser.add_argument("--target-usable", type=int, default=5000)
    parser.add_argument("--workers", type=int, default=64)
    parser.add_argument("--resume-existing", action="store_true")
    parser.add_argument("--suffix", help="Optional output filename suffix, e.g. clean")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    data_dir = root / "data" / "web-sample"
    data_dir.mkdir(parents=True, exist_ok=True)
    input_paths = []
    for input_arg in args.input:
        input_path = Path(input_arg)
        if not input_path.is_absolute():
            input_path = (root / input_path).resolve()
        input_paths.append(input_path)

    rows: list[SampleRow] = []
    for input_path in input_paths:
        rows.extend(read_csv_rows(input_path))
    if not rows:
        raise SystemExit("No rows found in input CSV.")

    deduped_rows: list[SampleRow] = []
    seen_domains: set[str] = set()
    for row in rows:
        if row.domain in seen_domains:
            continue
        seen_domains.add(row.domain)
        deduped_rows.append(row)
    rows = deduped_rows

    for idx, row in enumerate(rows, start=1):
        row.page_id = f"page-{idx:05d}"

    period = rows[0].period
    suffix = f"_{args.suffix}" if args.suffix else ""
    prepared_path = data_dir / f"web_sample_prepared_{period}{suffix}.json"
    batch_path = data_dir / f"web_sample_requests_{period}{suffix}.jsonl"

    page_rows: list[dict] = []
    dropped = 0
    processed_page_ids: set[str] = set()
    if args.resume_existing:
        page_rows, dropped, processed_page_ids = load_resume_payload(
            prepared_path=prepared_path,
            input_paths=input_paths,
            period=period,
            args=args,
        )

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        remaining_rows = [row for row in rows if row.page_id not in processed_page_ids]
        row_iter = iter(remaining_rows)
        max_in_flight = max(args.workers * 8, 128)
        in_flight: dict = {}
        last_progress_at = time.time()

        while len(in_flight) < max_in_flight and len(page_rows) < args.target_usable:
            try:
                row = next(row_iter)
            except StopIteration:
                break
            future = executor.submit(prepare_page, row, args.token_limit, args.min_tokens)
            in_flight[future] = row.page_id

        while in_flight and len(page_rows) < args.target_usable:
            done, pending = wait(set(in_flight), return_when=FIRST_COMPLETED)
            completed_ids = {future: in_flight[future] for future in done}
            in_flight = {future: in_flight[future] for future in pending}
            for future in done:
                page_id = completed_ids[future]
                processed_page_ids.add(page_id)
                try:
                    prepared = future.result()
                    if prepared is None:
                        dropped += 1
                    else:
                        page_rows.append(prepared)
                        if len(page_rows) >= args.target_usable:
                            break
                except Exception:
                    dropped += 1

            processed_count = len(processed_page_ids)
            now = time.time()
            if processed_count and (processed_count % 250 == 0 or now - last_progress_at >= 15):
                print(
                    f"[prep] period={period} processed={processed_count}/{len(rows)} "
                    f"usable={len(page_rows)} dropped={dropped} in_flight={len(in_flight)}"
                )
                sys.stdout.flush()
                last_progress_at = now

            while len(in_flight) < max_in_flight and len(page_rows) < args.target_usable:
                try:
                    row = next(row_iter)
                except StopIteration:
                    break
                future = executor.submit(prepare_page, row, args.token_limit, args.min_tokens)
                in_flight[future] = row.page_id

        for future in in_flight:
            future.cancel()

    if not page_rows:
        raise SystemExit("No usable pages were extracted.")

    page_rows = page_rows[: args.target_usable]

    requests = [
        build_request_line(period, batch_index, items, args.model)
        for batch_index, items in enumerate(chunked(page_rows, args.group_size), start=1)
    ]

    prepared_payload = {
        "period": period,
        "inputCsvs": [str(path) for path in input_paths],
        "rubricVersion": RUBRIC_VERSION,
        "promptHash": PROMPT_HASH,
        "systemPrompt": SYSTEM_PROMPT,
        "groupSize": args.group_size,
        "model": args.model,
        "tokenLimit": args.token_limit,
        "minTokens": args.min_tokens,
        "targetUsable": args.target_usable,
        "workers": args.workers,
        "sampleSizeRequested": len(rows),
        "sampleSizeProcessed": len(processed_page_ids),
        "sampleSizePrepared": len(page_rows),
        "droppedCount": dropped,
        "processedPageIds": sorted(processed_page_ids),
        "pages": page_rows,
    }
    prepared_path.write_text(json.dumps(prepared_payload, indent=2), encoding="utf-8")

    with batch_path.open("w", encoding="utf-8") as handle:
        for request in requests:
            handle.write(json.dumps(request) + "\n")

    print(f"Wrote {prepared_path}")
    print(f"Wrote {batch_path}")
    print(f"Prepared {len(page_rows)} pages across {len(requests)} batch requests")


if __name__ == "__main__":
    main()
