import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import http_json
import refresh_sources as refresh
import embed_dashboard_readable as embed

NOW = datetime(2026, 9, 23, 11, tzinfo=timezone.utc)


def snapshot(month="2026-07"):
    return {"latestObservedMonth": month, "lastRefreshed": "2026-08-02", "xValues": ["2026-06", month], "series": [{"name": "Observed", "values": [100, 90]}]}


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for key, config in refresh.SOURCES.items():
            path = self.root / config["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            content = {"rows": [{"year": 2026}], "lastRefreshed": "2026-09-21"} if "weekday" in config else snapshot()
            path.write_text(json.dumps(content))
            path.with_suffix(".js").write_text("previous browser snapshot")

    def write_august(self, root, key):
        path = root / refresh.SOURCES[key]["path"]
        data = snapshot()
        data["xValues"].append("2026-08")
        data["series"][0]["values"].append(80)
        data["latestObservedMonth"] = "2026-08"
        path.write_text(json.dumps(data))
        path.with_suffix(".js").write_text("new browser snapshot")

    def test_failed_source_does_not_lose_successful_sources(self):
        wiki = self.root / refresh.SOURCES["wikipedia"]["path"]
        original = wiki.read_bytes()
        calls = []
        def run(root, key):
            calls.append(key)
            if key == "wikipedia":
                wiki.write_text("broken partial write")
                raise TimeoutError()
            self.write_august(root, key)
        result = refresh.refresh_due_sources(self.root, NOW, "monthly-api", executor=run)
        self.assertEqual(set(calls), {"stack-overflow", "traffic-bot-human", "wikipedia"})
        self.assertEqual(result["failed"], ["wikipedia"])
        self.assertEqual(wiki.read_bytes(), original)
        self.assertEqual(refresh.load_json(self.root / refresh.SOURCES["stack-overflow"]["path"])["latestObservedMonth"], "2026-08")
        state = refresh.load_json(self.root / refresh.STATE_PATH)
        self.assertEqual(state["wikipedia"]["nextAttemptAt"], "2026-09-25T10:15:00Z")
        self.assertEqual(state["stack-overflow"]["nextAttemptAt"], "2026-10-02T10:15:00Z")
        # A daily check must not retry early or touch healthy sources.
        result = refresh.refresh_due_sources(self.root, NOW.replace(day=24), executor=lambda *_: self.fail("Early retry"))
        self.assertFalse(result["attempted"])
        result = refresh.refresh_due_sources(self.root, NOW.replace(day=25), executor=self.write_august)
        self.assertEqual(result["attempted"], ["wikipedia"])
        self.assertEqual(refresh.load_json(self.root / refresh.STATE_PATH)["wikipedia"]["nextAttemptAt"], "2026-10-10T10:15:00Z")

    def test_successful_but_stale_response_keeps_retrying(self):
        result = refresh.refresh_due_sources(self.root, NOW, "wikipedia", executor=lambda *_: None)
        self.assertEqual(result["waiting"], ["wikipedia"])
        result = refresh.refresh_due_sources(self.root, NOW.replace(day=25), "wikipedia", executor=lambda *_: None)
        self.assertEqual(result["waiting"], ["wikipedia"])
        self.assertEqual(refresh.load_json(self.root / refresh.STATE_PATH)["wikipedia"]["nextAttemptAt"], "2026-09-27T10:15:00Z")

    def test_missing_observations_are_rejected(self):
        old = snapshot()
        new = snapshot("2026-08")
        with self.assertRaisesRegex(ValueError, "lost an existing observation"):
            refresh.validate_snapshot("stack-overflow", new, old)
        new = snapshot()
        new["series"][0]["values"][-1] = None
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            refresh.validate_snapshot("stack-overflow", new, old)

    def test_permanent_error_is_scheduled_again_in_two_days(self):
        def fail(*_):
            raise ValueError("secret content must not enter public status")
        refresh.refresh_due_sources(self.root, NOW, "traffic-bot-human", executor=fail)
        state = refresh.load_json(self.root / refresh.STATE_PATH)["traffic-bot-human"]
        self.assertEqual(state["lastError"], "ValueError")
        self.assertEqual(state["attemptKind"], "catch-up")
        self.assertNotIn("secret", json.dumps(state))

    def test_calendar_schedule_and_month_rollover(self):
        jan = datetime(2027, 1, 1, tzinfo=timezone.utc)
        self.assertEqual(refresh.expected_month("wikipedia", jan), "2026-11")
        self.assertEqual(refresh.iso(refresh.regular_window("wikipedia", jan)[1]), "2027-01-10T10:15:00Z")
        self.assertEqual(refresh.expected_month("wikipedia", jan.replace(day=10, hour=11)), "2026-12")
        self.assertEqual(refresh.iso(refresh.regular_window("ai-content-meta-review", NOW)[1]), "2026-09-28T09:30:00Z")

    def test_monthly_job_does_not_run_paid_research(self):
        calls = []
        refresh.refresh_due_sources(self.root, NOW, "monthly-api", True, executor=lambda root, key: (calls.append(key), self.write_august(root, key)))
        self.assertNotIn("ai-content-meta-review", calls)

    def test_research_no_new_rows_still_counts_as_success(self):
        monday = datetime(2026, 9, 28, 10, tzinfo=timezone.utc)
        result = refresh.refresh_due_sources(self.root, monday, "ai-content-meta-review", executor=lambda *_: None)
        self.assertFalse(result["failed"])
        state = refresh.load_json(self.root / refresh.STATE_PATH)["ai-content-meta-review"]
        self.assertEqual(state["nextAttemptAt"], "2026-10-05T09:30:00Z")
        self.assertEqual(state["status"], "current")


class RetryTests(unittest.TestCase):
    def test_504_is_retried_then_succeeds(self):
        error = HTTPError("https://example.test", 504, "timeout", {}, None)
        with patch.object(http_json, "urlopen", side_effect=[error, io.BytesIO(b'{"ok":true}')]) as request, patch.object(http_json.time, "sleep") as sleep:
            self.assertEqual(http_json.request_json(Request("https://example.test")), {"ok": True})
            self.assertEqual(request.call_count, 2)
            sleep.assert_called_once_with(5)

    def test_timeouts_stop_after_bounded_retries(self):
        with patch.object(http_json, "urlopen", side_effect=TimeoutError()) as request, patch.object(http_json.time, "sleep"):
            with self.assertRaises(TimeoutError):
                http_json.request_json(Request("https://example.test"))
            self.assertEqual(request.call_count, 4)

    def test_403_is_not_hammered(self):
        error = HTTPError("https://example.test", 403, "forbidden", {}, None)
        with patch.object(http_json, "urlopen", side_effect=error), patch.object(http_json.time, "sleep") as sleep:
            with self.assertRaises(HTTPError):
                http_json.request_json(Request("https://example.test"))
            sleep.assert_not_called()

    def test_retry_after_is_respected(self):
        error = HTTPError("https://example.test", 429, "slow down", {"Retry-After": "30"}, None)
        self.assertEqual(http_json.retry_delay(error, 0), 30)


class EmbedTests(unittest.TestCase):
    def test_rebuild_preserves_header_without_old_footer(self):
        source = "<main>new header</main>\n" + embed.BODY_START + "old data" + embed.BODY_END + "<script>ui</script>"
        block = embed.BODY_START + "new data" + embed.BODY_END
        result = embed.insert_body_block(source, block)
        self.assertIn("new header", result)
        self.assertIn("new data", result)
        self.assertEqual(result.count(embed.BODY_START), 1)
        self.assertEqual(embed.insert_body_block(result, block), result)


if __name__ == "__main__":
    unittest.main()