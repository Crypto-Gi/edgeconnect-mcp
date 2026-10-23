import json
import tempfile
import unittest
from pathlib import Path

from edgeconnect_mcp import history
from edgeconnect_mcp.history import CAP, DAY_MS, History, merge, missing, paged, pull, read_alarms

NOW = 1790000000000  # ms


class FakeOrchestrator:
    """POST /alarm/appliance and GET /alarm/correlatedAlarms over fixed data, capped like the Orchestrator."""

    def __init__(self, alarms=(), cap=CAP, fail=(), refuse_post=False):
        self.alarms, self.cap, self.fail, self.refuse_post, self.calls = list(alarms), cap, list(fail), refuse_post, []

    def __call__(self, path, query, body):
        self.calls.append((path, dict(query), body))
        if path in ("/alarm/appliance", "/alarm/correlatedAlarms"):
            if path == "/alarm/appliance" and self.refuse_post:
                return None  # e.g. HTTP 403 for a key that may not POST
            if query.get("view") == "active":
                return [r for r in self.alarms if not r.get("clearedTimeInMills")][:self.cap]
            if any(query["from"] <= f < query["to"] for f in self.fail):
                return None
            rows = [r for r in self.alarms if query["from"] <= r["timeOccurredInMills"] <= query["to"]]
            if path == "/alarm/correlatedAlarms":  # the closed view, without clear times
                rows = [dict(r, clearedTimeInMills=None, clearedTime=None) for r in rows if r.get("clearedTimeInMills")]
            return rows[:self.cap]
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
        self.assertEqual(len(failed), 1)  # and that minute is not counted as read
        _, failed, _ = paged(lambda p, q, b: {"unexpected": True}, "/x", NOW - DAY_MS, NOW, lambda a, b: {})
        self.assertEqual(failed, [(NOW - DAY_MS, NOW)])  # a reply that is not a list is not a read
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
        fake = FakeOrchestrator(alarms=[{"id": 1, "applianceId": "1.NE", "timeOccurredInMills": NOW - 3600000}])
        self.assertEqual(pull(fake, self.history, ["1.NE"], True, NOW)["alarms"]["new"], 1)
        fake.alarms = [{"id": 1, "applianceId": "1.NE", "timeOccurredInMills": NOW - 3600000, "clearedTimeInMills": NOW}]
        later = NOW + DAY_MS
        fake.calls.clear()
        self.assertEqual(pull(fake, self.history, ["1.NE"], True, later)["alarms"]["new"], 0)
        self.assertEqual(min(q["from"] for _, q, _ in fake.calls if "from" in q), later - history.ALARM_LOOKBACK_MS)
        self.assertEqual(self.history.load("alarms", 0, later)[0]["clearedTimeInMills"], NOW)  # the clear time caught up
        self.assertEqual(missing(self.history.coverage()["alarms"], NOW - history.ALARM_LOOKBACK_MS, later), [])

    def test_failed_windows_stay_uncovered(self):
        summary = pull(FakeOrchestrator(fail=[NOW - DAY_MS]), self.history, ["1.NE"], True, NOW)
        self.assertEqual(len(summary["alarms"]["failed"]), 1)
        self.assertEqual(missing(self.history.coverage()["alarms"], NOW - history.ALARM_LOOKBACK_MS, NOW), [[NOW - DAY_MS, NOW]])

    def test_get_only_and_a_refused_post_store_the_correlated_alarm_list(self):
        data = [{"id": 1, "applianceId": "1.NE", "timeOccurredInMills": NOW - DAY_MS, "clearedTimeInMills": NOW - 1000},
                {"id": 2, "applianceId": "1.NE", "timeOccurredInMills": NOW - 3600000},
                {"id": 3, "applianceId": "9.NE", "timeOccurredInMills": NOW - 3600000}]  # not in scope
        fake = FakeOrchestrator(alarms=data)
        summary = pull(fake, self.history, ["1.NE"], False, NOW)
        self.assertEqual(summary["alarms"]["source"], "GET /alarm/correlatedAlarms")
        self.assertFalse([c for c in fake.calls if c[0] == "/alarm/appliance"])
        stored = {a["id"]: a for a in self.history.load("alarms", 0, NOW)}
        self.assertEqual((set(stored), stored[1]["closed"], stored[2]["closed"]), ({1, 2}, True, False))
        rows, failed, notes, source = read_alarms(FakeOrchestrator(alarms=data, refuse_post=True), ["1.NE"], True, NOW - DAY_MS - 1, NOW)
        self.assertEqual((source, len(rows), failed), ("GET /alarm/correlatedAlarms", 2, []))
        self.assertIn("refused", notes[0])

    def test_open_alarms_raised_before_the_window_are_read_too(self):
        old = {"id": 5, "applianceId": "1.NE", "timeOccurredInMills": NOW - 40 * DAY_MS}
        rows, _, _, _ = read_alarms(FakeOrchestrator(alarms=[old]), ["1.NE"], True, NOW - DAY_MS, NOW)
        self.assertEqual([r["id"] for r in rows], [5])

    def test_no_appliances_is_an_error_and_covers_nothing(self):
        with self.assertRaises(ValueError):
            pull(FakeOrchestrator(), self.history, [], True, NOW)
        self.assertEqual(self.history.coverage(), {})

    def test_writes_replace_the_file_whole(self):
        from unittest import mock
        self.history.write("alarms", [{"id": 1, "timeOccurredInMills": NOW}])
        with mock.patch("os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.history.write("alarms", [{"id": 2, "timeOccurredInMills": NOW}])
        self.assertEqual([a["id"] for a in self.history.load("alarms", 0, NOW)], [1])  # the old file is intact
        self.assertEqual([p.name for p in (Path(self.tmp.name) / "lab" / "alarms").iterdir()], ["{}.jsonl".format(history._month(NOW))])  # no temp left


if __name__ == "__main__":
    unittest.main()
