"""Bounded retries for read-only public-data requests."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from http.client import IncompleteRead, RemoteDisconnected
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


def retry_delay(error: Exception, attempt: int) -> float:
    delay = (5, 15, 45)[min(attempt, 2)]
    header = error.headers.get("Retry-After") if isinstance(error, HTTPError) and error.headers else None
    if header:
        try:
            delay = max(delay, float(header))
        except ValueError:
            try:
                delay = max(delay, (parsedate_to_datetime(header) - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError):
                pass
    return delay


def request_json(request: Request, *, timeout: int = 60, attempts: int = 4) -> dict:
    for attempt in range(attempts):
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
            # Stack Exchange can request a pause even with a successful response.
            if payload.get("backoff"):
                time.sleep(float(payload["backoff"]))
            return payload
        except HTTPError as error:
            if error.code not in RETRYABLE_STATUS or attempt == attempts - 1:
                raise
            delay = retry_delay(error, attempt)
        except (URLError, TimeoutError, ConnectionError, IncompleteRead, RemoteDisconnected, json.JSONDecodeError):
            if attempt == attempts - 1:
                raise
            delay = (5, 15, 45)[min(attempt, 2)]
        print(f"Temporary data request failure; retry {attempt + 2}/{attempts} in {delay:g}s.", flush=True)
        time.sleep(delay)
    raise RuntimeError("Data request exhausted its retries")