from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def load_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def get_openai_api_key(root: Path) -> str:
    env_values = load_env(root / ".env")
    api_key = os.environ.get("OPENAI_API_KEY") or env_values.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Missing OPENAI_API_KEY in environment or .env")
    return api_key


def timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def load_requests(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def load_completed_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    completed: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        custom_id = row.get("custom_id")
        if custom_id:
            completed.add(custom_id)
    return completed


def post_json(api_key: str, url: str, payload: dict) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request) as response:
        return json.load(response)


def run_request(api_key: str, row: dict, max_retries: int) -> tuple[str, dict]:
    custom_id = row["custom_id"]
    url = f"https://api.openai.com{row['url']}"
    payload = row["body"]

    attempt = 0
    last_error: dict | None = None
    while attempt <= max_retries:
        attempt += 1
        try:
            body = post_json(api_key, url, payload)
            return custom_id, {"custom_id": custom_id, "response": {"body": body}}
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="ignore")
            last_error = {
                "custom_id": custom_id,
                "error": {
                    "type": "http_error",
                    "status": exc.code,
                    "message": details or str(exc),
                    "attempt": attempt,
                },
            }
            if exc.code in {408, 409, 429, 500, 502, 503, 504} and attempt <= max_retries:
                time.sleep(min(2**attempt, 20))
                continue
            return custom_id, last_error
        except URLError as exc:
            last_error = {
                "custom_id": custom_id,
                "error": {
                    "type": "url_error",
                    "message": str(exc),
                    "attempt": attempt,
                },
            }
            if attempt <= max_retries:
                time.sleep(min(2**attempt, 20))
                continue
            return custom_id, last_error
        except Exception as exc:  # noqa: BLE001
            last_error = {
                "custom_id": custom_id,
                "error": {
                    "type": "exception",
                    "message": str(exc),
                    "attempt": attempt,
                },
            }
            if attempt <= max_retries:
                time.sleep(min(2**attempt, 20))
                continue
            return custom_id, last_error

    if last_error is None:
        last_error = {
            "custom_id": custom_id,
            "error": {"type": "unknown", "message": "Request failed without error details."},
        }
    return custom_id, last_error


def append_jsonl(path: Path, row: dict, lock: threading.Lock) -> None:
    with lock:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Request JSONL file")
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--suffix", help="Optional output suffix")
    parser.add_argument("--data-dir", default="data/web-sample", help="Directory for output JSONL files")
    parser.add_argument("--output-prefix", default="web_sample_live_output", help="Prefix for successful output JSONL")
    parser.add_argument("--error-prefix", default="web_sample_live_errors", help="Prefix for error output JSONL")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = (root / input_path).resolve()

    api_key = get_openai_api_key(root)
    requests = load_requests(input_path)
    if not requests:
        raise SystemExit("No requests found in input JSONL.")

    data_dir = Path(args.data_dir)
    if not data_dir.is_absolute():
        data_dir = (root / data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    suffix = f"_{args.suffix}" if args.suffix else ""
    output_path = data_dir / f"{args.output_prefix}{suffix}.jsonl"
    error_path = data_dir / f"{args.error_prefix}{suffix}.jsonl"

    completed_ids = load_completed_ids(output_path) | load_completed_ids(error_path)
    pending = [row for row in requests if row["custom_id"] not in completed_ids]
    total = len(requests)
    completed = len(load_completed_ids(output_path))
    failed = len(load_completed_ids(error_path))

    print(
        f"[{timestamp()}] starting live run total={total} "
        f"already_completed={completed} already_failed={failed} pending={len(pending)} "
        f"concurrency={args.concurrency}"
    )

    output_lock = threading.Lock()
    error_lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        iterator = iter(pending)
        in_flight = set()

        while len(in_flight) < args.concurrency:
            try:
                row = next(iterator)
            except StopIteration:
                break
            in_flight.add(executor.submit(run_request, api_key, row, args.max_retries))

        while in_flight:
            done, in_flight = wait(in_flight, return_when=FIRST_COMPLETED)
            for future in done:
                custom_id, result = future.result()
                if "response" in result:
                    append_jsonl(output_path, result, output_lock)
                    completed += 1
                else:
                    append_jsonl(error_path, result, error_lock)
                    failed += 1

                finished = completed + failed
                print(
                    f"[{timestamp()}] finished={finished}/{total} "
                    f"completed={completed} failed={failed} last={custom_id}"
                )
                sys.stdout.flush()

            while len(in_flight) < args.concurrency:
                try:
                    row = next(iterator)
                except StopIteration:
                    break
                in_flight.add(executor.submit(run_request, api_key, row, args.max_retries))

    print(
        f"[{timestamp()}] done total={total} completed={completed} failed={failed} "
        f"output={output_path.name} errors={error_path.name}"
    )


if __name__ == "__main__":
    main()
