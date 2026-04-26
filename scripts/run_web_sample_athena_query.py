from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from _aws_common import athena_client, aws_env, s3_client


def run_query(client, sql: str, output: str) -> dict:
    response = client.start_query_execution(
        QueryString=sql,
        ResultConfiguration={"OutputLocation": output},
        QueryExecutionContext={"Catalog": "AwsDataCatalog", "Database": "ccindex"},
    )
    qid = response["QueryExecutionId"]
    print(f"[athena] started query_execution_id={qid}")
    sys.stdout.flush()
    last_status: str | None = None
    last_log_at = 0.0
    while True:
        meta = client.get_query_execution(QueryExecutionId=qid)["QueryExecution"]
        status = meta["Status"]["State"]
        now = time.time()
        if status != last_status or now - last_log_at >= 10:
            print(f"[athena] query_execution_id={qid} status={status}")
            sys.stdout.flush()
            last_status = status
            last_log_at = now
        if status in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return {
                "queryExecutionId": qid,
                "status": status,
                "reason": meta["Status"].get("StateChangeReason"),
                "outputLocation": meta["ResultConfiguration"]["OutputLocation"],
            }
        time.sleep(2)


def download_output_bytes(root: Path, s3_url: str) -> bytes:
    parsed = urlparse(s3_url)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    client = s3_client(root)
    obj = client.get_object(Bucket=bucket, Key=key)
    return obj["Body"].read()


def count_csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        return max(sum(1 for _ in reader) - 1, 0)


def write_or_append_csv(target_path: Path, payload: bytes, append: bool) -> int:
    if not append or not target_path.exists():
        target_path.write_bytes(payload)
        return count_csv_rows(target_path)

    text = payload.decode("utf-8")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return count_csv_rows(target_path)

    data_rows = rows[1:]
    if not data_rows:
        return count_csv_rows(target_path)

    with target_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerows(data_rows)
    return count_csv_rows(target_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", required=True, help="YYYY-MM")
    parser.add_argument("--suffix", help="Optional filename suffix, e.g. clean")
    parser.add_argument("--append", action="store_true", help="Append into an existing candidate CSV instead of creating a new file")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    env = aws_env(root)
    client = athena_client(root)
    data_dir = root / "data" / "web-sample"
    data_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_{args.suffix}" if args.suffix else ""

    sql_path = data_dir / "web_sample_queries" / f"web_sample_athena_query_{args.period}{suffix}.sql"
    if not sql_path.exists():
        raise SystemExit(f"Missing SQL file: {sql_path}")

    sql = sql_path.read_text(encoding="utf-8")
    result = run_query(client, sql, env["ATHENA_RESULTS_S3"])
    if result["status"] != "SUCCEEDED":
        raise SystemExit(json.dumps(result, indent=2))

    csv_path = data_dir / f"web_sample_candidates_{args.period}{suffix}.csv"
    meta_path = data_dir / f"web_sample_candidates_{args.period}{suffix}_meta.json"
    payload = download_output_bytes(root, result["outputLocation"])
    row_count = write_or_append_csv(csv_path, payload, args.append)

    meta_payload = {
        "period": args.period,
        "suffix": args.suffix or None,
        "appendMode": args.append,
        "totalRows": row_count,
        "runs": [],
    }
    if meta_path.exists():
        try:
            existing = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                meta_payload.update(existing)
                meta_payload["period"] = args.period
                meta_payload["suffix"] = args.suffix or None
                meta_payload["appendMode"] = args.append
                meta_payload["totalRows"] = row_count
                meta_payload["runs"] = list(existing.get("runs", []))
        except Exception:
            pass
    meta_payload["runs"].append(result)
    meta_payload["totalRows"] = row_count
    meta_path.write_text(json.dumps(meta_payload, indent=2), encoding="utf-8")
    print(f"Wrote {csv_path}")
    print(f"Wrote {meta_path}")
    print(f"Rows: {row_count}")


if __name__ == "__main__":
    main()
