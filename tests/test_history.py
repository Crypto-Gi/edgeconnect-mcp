import json
import tempfile
import unittest
from pathlib import Path

from edgeconnect_mcp import history
from edgeconnect_mcp.history import CAP, DAY_MS, History, merge, missing, paged, pull

NOW = 1790000000000  # ms


class FakeOrchestrator:
    """POST /alarm/appliance and GET /health/alarmPeriodSummary over fixed data, capped like the Orchestrator."""

    def __init__(self, alarms=(), cap=CAP, fail=()):
        self.alarms, self.cap, self.fail, self.calls = list(alarms), cap, list(fail), []

    def __call__(self, path, query, body):
        self.calls.append((path, dict(query), body))
        if path == "/alarm/appliance":
            if any(query["from"] <= f < query["to"] for f in self.fail):
                return None
            return [r for r in self.alarms if query["from"] <= r["timeOccurredInMills"] <= query["to"]][:self.cap]
        if path == "/health/alarmPeriodSummary":
            return {"alarmCountsInPeriod": {"MAJOR": 1}}
        raise AssertionError(path)  # nothing else, in particular no audit log, is read


def alarms(start, count, step):
    return [{"id": i, "timeOccurredInMills": start + i * step, "severity": "MAJOR"} for i in range(count)]


class PagingTests(unittest.TestCase):
    def test_full_pages_are_split_until_they_fit_so_nothing_is_dropped(self):
        rows = alarms(NOW - DAY_MS, 25, 60000)  # 25 alarms in 25 minutes
        fake = FakeOrchestrator(alarms=rows, cap=10)
        got, failed, notes = paged(fake, "/alarm/appliance", NOW - DAY_MS, NOW, lambda a, b: {"from": a, "to": b}, cap=10)
        self.assertEqual(({r["id"] for r in got}, failed, notes), ({r["id"] for r in rows}, [], []))
        self.assertGreater(len(fake.calls), 3)

    def test_a_one_minute_page_still_full_is_reported_and_failed_windows_are_returned(self):
        rows = [{"id": i, "timeOccurredInMills": NOW - 30000} for i in range(12)]  # 12 alarms in the same second
        got, failed, notes = paged(FakeOrchestrator(alarms=rows, cap=10), "/alarm/appliance", NOW - DAY_MS, NOW, lambda a, b: {"from": a, "to": b}, cap=10)
        self.assertEqual(len(got), 10)
        self.assertIn("rows within one minute", notes[0])
        _, failed, _ = paged(FakeOrchestrator(fail=[NOW - DAY_MS]), "/alarm/appliance", NOW - 2 * DAY_MS, NOW, lambda a, b: {"from": a, "to": b})
        self.assertEqual(failed, [(NOW - DAY_MS, NOW)])

    def test_spans_merge_and_report_what_is_missing(self):
        self.assertEqual(merge([[6, 9], [1, 3], [3, 4]]), [[1, 4], [6, 9]])
        self.assertEqual(missing([[1, 4], [6, 9]], 0, 10), [[0, 1], [4, 6], [9, 10]])
        self.assertEqual(missing([[0, 10]], 2, 8), [])


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.history = History(Path(self.tmp.name), "lab")

    def tearDown(self):
        self.tmp.cleanup()

    def test_alarms_are_deduplicated_by_id_a_later_version_replaces_the_stored_one_and_files_are_private(self):
        alarm = {"id": 7, "timeOccurredInMills": NOW - 1000, "severity": "MAJOR"}
        self.assertEqual(self.history.write("alarms", [alarm, alarm]), 1)
        self.assertEqual(self.history.write("alarms", [dict(alarm, clearedTimeInMills=NOW)]), 0)
        stored = self.history.load("alarms", NOW - DAY_MS, NOW)
        self.assertEqual([(a["id"], a.get("clearedTimeInMills")) for a in stored], [(7, NOW)])
        files = list((Path(self.tmp.name) / "lab").rglob("*.jsonl"))
        self.assertEqual({oct(f.stat().st_mode & 0o777) for f in files} | {oct(f.parent.stat().st_mode & 0o777) for f in files}, {"0o600", "0o700"})

    def test_every_pull_rereads_the_seven_days_the_orchestrator_keeps(self):
        fake = FakeOrchestrator(alarms=[{"id": 1, "timeOccurredInMills": NOW - 3600000}])
        self.assertEqual(pull(fake, self.history, ["1.NE"], True, NOW)["alarms"]["new"], 1)
        fake.alarms = [{"id": 1, "timeOccurredInMills": NOW - 3600000, "clearedTimeInMills": NOW}]
        later = NOW + DAY_MS
        fake.calls.clear()
        self.assertEqual(pull(fake, self.history, ["1.NE"], True, later)["alarms"]["new"], 0)
        self.assertEqual(min(q["from"] for _, q, _ in fake.calls), later - history.ALARM_LOOKBACK_MS)
        self.assertEqual(self.history.load("alarms", 0, later)[0]["clearedTimeInMills"], NOW)  # the clear time caught up
        self.assertEqual(missing(self.history.coverage()["alarms"], NOW - history.ALARM_LOOKBACK_MS, later), [])

    def test_failed_windows_stay_uncovered(self):
        summary = pull(FakeOrchestrator(fail=[NOW - DAY_MS]), self.history, ["1.NE"], True, NOW)
        self.assertEqual(len(summary["alarms"]["failed"]), 1)
        self.assertEqual(missing(self.history.coverage()["alarms"], NOW - history.ALARM_LOOKBACK_MS, NOW), [[NOW - DAY_MS, NOW]])

    def test_get_only_stores_daily_alarm_counts_and_reads_only_new_days(self):
        fake = FakeOrchestrator()
        summary = pull(fake, self.history, ["1.NE", "2.NE"], False, NOW)
        self.assertIn("alarm_counts", summary)
        self.assertFalse([c for c in fake.calls if c[0] == "/alarm/appliance"])
        counts = self.history.load("alarm_counts", 0, NOW)
        self.assertEqual({c["nePk"] for c in counts}, {"1.NE", "2.NE"})
        self.assertEqual(counts[0]["counts"], {"MAJOR": 1})
        self.assertTrue(json.loads((Path(self.tmp.name) / "lab" / "coverage.json").read_text())["alarm_counts"])
        fake.calls.clear()
        pull(fake, self.history, ["1.NE", "2.NE"], False, NOW + 3600000)
        self.assertLessEqual(len(fake.calls), 2 * 2)  # the last stored day and today, not 7 days again


if __name__ == "__main__":
    unittest.main()
