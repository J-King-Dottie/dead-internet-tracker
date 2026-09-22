import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import refresh_wikipedia as wiki
import refresh_sources as refresh

NOW = datetime(2026, 9, 23, tzinfo=timezone.utc)


def history():
    months = [f"{year}-{month:02d}" for year in range(2020, 2027)
              for month in range(1, 13) if (year, month) <= (2026, 6)]
    return {"xValues": months, "latestObservedMonth": months[-1], "series": [
        {"name": "All editors", "values": [100] * len(months)},
        {"name": "Active editors (5+)", "values": [30] * len(months)},
    ]}


def recent_rows(level, start, end):
    count = 110 if level == "all-activity-levels" else 12
    return [{"timestamp": f"2026-{month:02d}-01T00:00:00.000Z", "editors": count}
            for month in range(5, 9)]


class WikipediaTests(unittest.TestCase):
    def test_only_recent_slice_fetched_and_older_history_preserved(self):
        previous = history()
        with patch.object(wiki, "fetch_monthly_series", side_effect=recent_rows) as fetch:
            result = wiki.build_snapshot(previous, NOW)
        self.assertEqual(fetch.call_count, 4)
        for call in fetch.call_args_list:
            self.assertEqual(call.args[1], "2026-05")
            self.assertEqual(call.args[2].strftime("%Y-%m"), "2026-08")
        self.assertEqual(result["latestObservedMonth"], "2026-08")
        self.assertEqual(result["series"][0]["values"][:-4], previous["series"][0]["values"][:-2])
        self.assertEqual(result["series"][0]["values"][-4:], [110] * 4)
        self.assertEqual(result["series"][1]["values"][-4:], [36] * 4)
        refresh.validate_snapshot("wikipedia", result, previous)

    def test_missing_new_month_is_rejected(self):
        def rows(*args):
            return [r for r in recent_rows(*args) if not r["timestamp"].startswith("2026-07")]
        with patch.object(wiki, "fetch_monthly_series", side_effect=rows):
            with self.assertRaisesRegex(ValueError, "monthly history"):
                wiki.build_snapshot(history(), NOW)

    def test_partial_cohort_is_not_replaced_with_zero(self):
        def rows(level, *args):
            data = recent_rows(level, *args)
            return data[:-1] if level == "25..99-edits" else data
        with patch.object(wiki, "fetch_monthly_series", side_effect=rows):
            with self.assertRaisesRegex(RuntimeError, "Incomplete Wikimedia editor cohorts"):
                wiki.build_snapshot(history(), NOW)

    def test_end_boundary_includes_last_completed_month_and_december(self):
        payload = {"items": [{"results": [{"timestamp": "2026-08-01", "editors": 1}]}]}
        with patch.object(wiki, "request_json", return_value=payload) as request:
            wiki.fetch_monthly_series("all-activity-levels", "2025-11", NOW.replace(month=8, day=31))
        urls = [call.args[0].full_url for call in request.call_args_list]
        self.assertTrue(urls[0].endswith("/20251101/20260101"))
        self.assertTrue(urls[1].endswith("/20260101/20260901"))


if __name__ == "__main__":
    unittest.main()
