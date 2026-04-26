from __future__ import annotations

import sys
from pathlib import Path


def add_local_deps() -> None:
    root = Path(__file__).resolve().parent.parent
    deps = root / ".deps"
    if deps.exists():
        sys.path.insert(0, str(deps))


add_local_deps()

import boto3  # type: ignore


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def aws_env(root: Path) -> dict[str, str]:
    env = load_env(root / ".env")
    required = [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "ATHENA_REGION",
        "ATHENA_RESULTS_S3",
    ]
    missing = [key for key in required if key not in env]
    if missing:
        raise SystemExit(f"Missing AWS config in .env: {', '.join(missing)}")
    return env


def athena_client(root: Path):
    env = aws_env(root)
    return boto3.client(
        "athena",
        aws_access_key_id=env["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=env["AWS_SECRET_ACCESS_KEY"],
        region_name=env["ATHENA_REGION"],
    )


def s3_client(root: Path):
    env = aws_env(root)
    return boto3.client(
        "s3",
        aws_access_key_id=env["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=env["AWS_SECRET_ACCESS_KEY"],
        region_name=env["ATHENA_REGION"],
    )
