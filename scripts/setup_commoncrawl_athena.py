from __future__ import annotations

import json
import time
from pathlib import Path

from _aws_common import athena_client, aws_env


DATABASE_SQL = "CREATE DATABASE IF NOT EXISTS ccindex"
TABLE_SQL = """
CREATE EXTERNAL TABLE IF NOT EXISTS ccindex.ccindex (
  url_surtkey STRING,
  url STRING,
  url_host_name STRING,
  url_host_tld STRING,
  url_host_2nd_last_part STRING,
  url_host_3rd_last_part STRING,
  url_host_4th_last_part STRING,
  url_host_5th_last_part STRING,
  url_host_registry_suffix STRING,
  url_host_registered_domain STRING,
  url_host_private_suffix STRING,
  url_host_private_domain STRING,
  url_host_name_reversed STRING,
  url_protocol STRING,
  url_port INT,
  url_path STRING,
  url_query STRING,
  fetch_time TIMESTAMP,
  fetch_status SMALLINT,
  fetch_redirect STRING,
  content_digest STRING,
  content_mime_type STRING,
  content_mime_detected STRING,
  content_charset STRING,
  content_languages STRING,
  content_truncated STRING,
  warc_filename STRING,
  warc_record_offset INT,
  warc_record_length INT,
  warc_segment STRING
)
PARTITIONED BY (
  crawl STRING,
  subset STRING
)
STORED AS PARQUET
LOCATION 's3://commoncrawl/cc-index/table/cc-main/warc/'
"""
REPAIR_SQL = "MSCK REPAIR TABLE ccindex.ccindex"


def run_query(client, sql: str, output: str, database: str | None = None) -> dict:
    kwargs = {
        "QueryString": sql,
        "ResultConfiguration": {"OutputLocation": output},
        "QueryExecutionContext": {"Catalog": "AwsDataCatalog"},
    }
    if database:
        kwargs["QueryExecutionContext"]["Database"] = database
    response = client.start_query_execution(**kwargs)
    qid = response["QueryExecutionId"]
    while True:
        meta = client.get_query_execution(QueryExecutionId=qid)["QueryExecution"]
        status = meta["Status"]["State"]
        if status in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return {
                "queryExecutionId": qid,
                "status": status,
                "reason": meta["Status"].get("StateChangeReason"),
            }
        time.sleep(2)


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    env = aws_env(root)
    client = athena_client(root)
    output = env["ATHENA_RESULTS_S3"]

    results = {
        "create_database": run_query(client, DATABASE_SQL, output),
        "create_table": run_query(client, TABLE_SQL, output, database="ccindex"),
        "repair_table": run_query(client, REPAIR_SQL, output, database="ccindex"),
    }

    data_dir = root / "data" / "web-sample"
    data_dir.mkdir(parents=True, exist_ok=True)
    output_path = data_dir / "athena_commoncrawl_setup.json"
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
