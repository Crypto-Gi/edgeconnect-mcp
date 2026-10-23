import json
import re
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from edgeconnect_mcp import report
from edgeconnect_mcp.config import Config
from edgeconnect_mcp.server import Orchestrator, Server

PATHS = ["/gms/versions", "/appliance", "/stats/config/availabilityThreshold", "/gms/stats/retention", "/stats/aggregate/availability/appliance",
         "/stats/aggregate/availability/tunnel", "/health/alarmPeriodSummary", "/alarm/summary", "/gmsLicense", "/license/portal/summary"]
SPEC = {"swagger": "2.0", "basePath": "/gms/rest", "paths": dict({p: {"get": {"summary": p}} for p in PATHS}, **{"/alarm/appliance": {"post": {"summary": "alarms"}}})}
APPLIANCES = [{"nePk": "1.NE", "hostName": "branch-a", "state": 1, "model": "EC-V", "softwareVersion": "9.6.2.1_1"},
              {"nePk": "2.NE", "hostName": "branch-b<script>", "state": 2, "model": "EC-XS", "softwareVersion": "9.7.1.0_1"}]


class RoutedClient:
    """Answers each path from a table, like an Orchestrator would."""

    def __init__(self, answers):
        self.answers, self.calls = answers, []

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs.get("query"), kwargs.get("json_body")))
        answer = self.answers.get(path, [])
        if isinstance(answer, Exception):
            raise answer
        key = (kwargs.get("query") or {}).get("nePk") or (kwargs.get("query") or {}).get("applianceId")
        if isinstance(answer, dict) and key in answer and path != "/gmsLicense":
            answer = answer[key]
        return json.dumps(answer).encode()

    def _url(self, path, query):
        return "https://orch.example/gms/rest" + path


def bundle(**data):
    base = {"versions": {"current": "9.7.1.1"}, "appliances": APPLIANCES, "availability_threshold": {"reachability": {"goodLimit": 99.0, "okLimit": 99.9},
            "overlayAvailability": {"goodLimit": 99.0, "okLimit": 99.9}, "underlayAvailability": {"goodLimit": 99.0, "okLimit": 99.9}},
            "reach:1.NE": [{"samplecount": 1000, "appliancereachability": 995}], "reach:2.NE": [{"samplecount": 1000, "appliancereachability": 1000}],
            "overlay:1.NE": {"1": [{"count": 1000, "tunnel_state": 600, "blackout": 600, "brownout": 1200}]}, "underlay:1.NE": {"0": [{"count": 1000, "tunnel_state": 0, "blackout": 0, "brownout": 0}]},
            "alarm_period:1.NE": {"alarmCountsInPeriod": {"MAJOR": 2, "WARNING": 5}}}
    base.update(data)
    calls = [{"id": k, "method": "GET", "path": "/stats/aggregate/availability/appliance" if k.startswith("reach") else "/appliance", "outcome": "ok"} for k in base]
    return {"report": "availability", "orchestrator": "lab", "period": {"month": "2026-10", "from_ms": 0, "to_ms": 1}, "collected_at": "2026-10-23T00:00:00+00:00",
            "calls": calls, "data": base, "sha256": "abc"}


class ComputeTests(unittest.TestCase):
    def test_reachability_is_reachable_minutes_over_samples_weighted_across_the_fleet(self):
        m = report.compute(bundle())
        self.assertEqual(m["metrics"]["fleet_reach_pct"]["value"], 99.75)
        self.assertEqual(m["metrics"]["fleet_reach_pct"]["status"], "amber")  # between 99.0 and 99.9
        rows = {r["nePk"]: (r["value"], r["status"]) for r in m["sections"]["avail-appliances"]["table"]}
        self.assertEqual(rows, {"1.NE": (99.5, "amber"), "2.NE": (100.0, "green")})

    def test_tunnel_availability_is_downtime_seconds_over_sample_minutes(self):
        # count is minute samples, tunnel_state / blackout / brownout are seconds (seen on 9.7.1 and 10.0); state and blackout overlap.
        m = report.compute(bundle())["metrics"]
        self.assertEqual((m["overlay_avail_pct"]["value"], m["overlay_degraded_pct"]["value"], m["underlay_avail_pct"]["value"]), (99.0, 2.0, 100.0))

    def test_alarms_use_the_full_list_when_the_read_post_ran_else_period_counts(self):
        m = report.compute(bundle())
        self.assertEqual((m["metrics"]["alarms_major"]["value"], m["metrics"]["alarms_warning"]["value"], m["sections"]["avail-alarms"]["status"]), (2, 5, "amber"))
        listed = [{"applianceId": "1.NE", "severity": "CRITICAL", "description": "Tunnel down"}, {"applianceId": "2.NE", "severity": "MINOR"}]
        m = report.compute(bundle(appliance_alarms=listed))
        self.assertEqual((m["metrics"]["alarms_critical"]["value"], m["metrics"]["alarms_major"]["value"], m["sections"]["avail-alarms"]["status"]), (1, 0, "red"))
        self.assertEqual(m["sections"]["avail-alarms"]["table"], [{"appliance": "branch-a", "severity": "critical", "description": "Tunnel down"}])

    def test_missing_data_is_grey_never_zero_and_listed_as_a_gap(self):
        m = report.compute(bundle(**{"reach:1.NE": [], "reach:2.NE": [], "availability_threshold": {}}))
        self.assertEqual((m["metrics"]["fleet_reach_pct"]["value"], m["metrics"]["fleet_reach_pct"]["status"]), (None, "grey"))
        gaps = " ".join(m["sections"]["data-gaps"]["notes"])
        self.assertIn("default 99.0 / 99.5", gaps)
        self.assertIn("branch-a: no reachability samples for the month although it is reachable now", gaps)

    def test_all_stats_500_is_one_stats_store_banner(self):
        b = bundle(**{"reach:1.NE": None, "reach:2.NE": None})
        b["calls"] = [{"id": "x", "method": "GET", "path": "/stats/aggregate/availability/appliance", "outcome": "error", "http_status": 500, "error": "HTTP 500"}] * 2
        m = report.compute(b)
        self.assertTrue(m["stats_store_down"])
        self.assertEqual(len([n for n in m["sections"]["data-gaps"]["notes"] if "HTTP 500" in n]), 1)

    def test_executive_statuses_and_unbuilt_sections(self):
        b = bundle(alarm_summary={"numOfCriticalAlarms": 0, "numOfMajorAlarms": 1, "numOfMinorAlarms": 0, "numOfWarningAlarms": 3}, gms_license={"daysToExpiration": 45, "usedAppliances": 2, "maxAppliances": 10})
        b["report"] = "executive"
        m = report.compute(b)
        self.assertEqual([sid for sid in m["sections"]], [sid for sid, _ in report.SECTIONS["executive"]])
        self.assertEqual({sid: m["sections"][sid]["status"] for sid in ("exec-alarms", "exec-licensing", "exec-software", "exec-fleet", "exec-capacity")},
                         {"exec-alarms": "amber", "exec-licensing": "amber", "exec-software": "amber", "exec-fleet": "red", "exec-capacity": "grey"})

    def test_band_and_month_window(self):
        self.assertEqual([report.band(v, (99.0, 99.5)) for v in (99.5, 99.2, 98.0, None)], ["green", "amber", "red", "grey"])
        self.assertEqual([report.band(v, (1.0, 5.0), higher_is_better=False) for v in (0.5, 3, 9)], ["green", "amber", "red"])
        first, start, end = report.month_window("2026-02", now=datetime(2026, 10, 1, tzinfo=timezone.utc))
        self.assertEqual((first.isoformat(), start, end), ("2026-02-01", 1769904000000, 1772323199000))
        now = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
        self.assertEqual(report.month_window("2026-10", now=now)[2], int(now.timestamp() * 1000))
        for bad in ("2026-13x", "26-10"):
            with self.assertRaises(ValueError):
                report.month_window(bad)
        with self.assertRaises(ValueError):
            report.month_window("2026-11", now=now)


class NarrativeTests(unittest.TestCase):
    def setUp(self):
        self.metrics = report.compute(bundle())

    def narrative(self, text, status=None, sid="avail-summary"):
        section = {"text": text}
        if status:
            section["status"] = status
        return {"report": "availability", "sections": {sid: section}}

    def test_valid_narrative_passes_and_template_lists_every_section(self):
        self.assertEqual(report.validate(self.metrics, self.narrative("Fleet reachability was {{m:fleet_reach_pct}}, short of the target.", "amber")), [])
        self.assertEqual(list(report.template(self.metrics)["sections"]), [sid for sid, _ in report.SECTIONS["availability"]])

    def test_bare_numbers_unknown_metrics_and_sections_are_rejected(self):
        self.assertIn("bare number", report.validate(self.metrics, self.narrative("Reachability was 99.75 percent."))[0])
        self.assertIn("is not a metric", report.validate(self.metrics, self.narrative("{{m:made_up}}"))[0])
        self.assertIn("unknown section", report.validate(self.metrics, self.narrative("x", sid="nope"))[0])
        self.assertIn("malformed", report.validate(self.metrics, self.narrative("{{m:fleet_reach_pct}"))[0])

    def test_status_contradicting_compute_is_rejected(self):
        self.assertIn("contradicts", report.validate(self.metrics, self.narrative("Fine.", "green"))[0])
        self.assertIn("implies green", report.validate(self.metrics, self.narrative("The network was healthy all month."))[0])
        self.assertIn("implies red", report.validate(self.metrics, self.narrative("There was an outage."))[0])


class RenderTests(unittest.TestCase):
    def test_one_self_contained_page_with_sections_in_order_tokens_filled_and_text_escaped(self):
        metrics = report.compute(bundle())
        page = report.render(metrics, {"report": "availability", "sections": {"avail-summary": {"text": "Reachability {{m:fleet_reach_pct}} <b>x</b>"},
                                                                     "avail-alarms": {"text": "{{m:alarms_major}} major alarms."}}})
        self.assertIn("<p>2 major alarms.</p>", page)  # prose tokens carry no unit word
        self.assertIn(">2 alarms</b>", page)  # tiles do
        ids = [line.split('data-section-id="')[1].split('"')[0] for line in page.split("<section ")[1:]]
        self.assertEqual(ids, [sid for sid, _ in report.SECTIONS["availability"]])
        self.assertIn("Reachability 99.75% &lt;b&gt;x&lt;/b&gt;", page)
        self.assertNotIn("<script", page)  # the hostile host name is escaped
        self.assertIn("branch-b&lt;script&gt;", page)
        self.assertIn("<svg", page)
        self.assertIn("<title>branch-a: 99.50%</title>", page)
        self.assertIn("@media print", page)
        self.assertIn("Bundle SHA-256 abc", page)
        self.assertNotRegex(page, r"(?i)<(link|img|iframe)\b|src=|https?://")

    def test_render_refuses_an_invalid_narrative(self):
        with self.assertRaises(ValueError):
            report.render(report.compute(bundle()), {"report": "availability", "sections": {"avail-summary": {"text": "99 percent"}}})


class SkillTests(unittest.TestCase):
    def test_report_skill_names_only_tested_operations(self):
        root = Path(__file__).resolve().parent.parent
        tested = set((root / "skills" / "edgeconnect-guide" / "tested-operations.tsv").read_text(encoding="utf-8").splitlines())
        named = re.findall(r"`(GET|POST|PUT|PATCH|DELETE) (/[^`\s?]+)", (root / "skills" / "edgeconnect-report" / "SKILL.md").read_text(encoding="utf-8"))
        self.assertTrue(named)
        self.assertEqual([op for op in named if "\t".join(op) not in tested], [])


class CollectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.spec = Path(self.tmp.name) / "spec.json"
        self.spec.write_text(json.dumps(SPEC))

    def tearDown(self):
        self.tmp.cleanup()

    def server(self, client, get_only):
        orchestrator = Orchestrator("lab", Config(base_url="https://orch.example/gms/rest", api_key="KEY"), False, str(self.spec), client, get_only=get_only)
        return Server({"lab": orchestrator}, default="lab", log=lambda line: None)

    def answers(self):
        return {"/gms/versions": {"current": "9.7.1.1"}, "/appliance": APPLIANCES, "/stats/aggregate/availability/appliance": {"1.NE": [{"samplecount": 10, "appliancereachability": 10}], "2.NE": []},
                "/alarm/appliance": [{"applianceId": "1.NE", "severity": "MAJOR"}], "/gmsLicense": {"licenseKey": "AAAA-BBBB", "daysToExpiration": 400, "serialNumber": "00-11"}}

    def test_read_post_runs_with_writes_off_and_times_use_the_right_units(self):
        client = RoutedClient(self.answers())
        b = report.collect(self.server(client, get_only=False), "lab", "executive", "2026-09")
        posts = [c for c in client.calls if c[0] == "POST"]
        self.assertEqual(posts, [("POST", "/alarm/appliance", {"view": "all", "from": 1788220800000, "to": 1790812799000, "maxAlarms": 10000, "orderBySeverity": True}, {"nePks": ["1.NE", "2.NE"]})])
        reach = [c for c in client.calls if c[1] == "/stats/aggregate/availability/appliance"]
        self.assertEqual(reach[0][2], {"nePk": "1.NE", "date": "2026-09-01", "granularity": "month"})
        self.assertEqual({c["id"]: c["outcome"] for c in b["calls"] if c["id"].startswith("reach:")}, {"reach:1.NE": "ok", "reach:2.NE": "empty"})
        self.assertNotIn("AAAA", json.dumps(b))  # licence keys and serials never reach a bundle
        self.assertNotIn("00-11", json.dumps(b))
        self.assertEqual(b["data"]["gms_license"], {"daysToExpiration": 400})

    def test_get_only_skips_the_read_post_and_falls_back_to_gets(self):
        client = RoutedClient(self.answers())
        b = report.collect(self.server(client, get_only=True), "lab", "availability", "2026-09")
        self.assertFalse([c for c in client.calls if c[0] == "POST"])
        skipped = [c for c in b["calls"] if c["outcome"] == "skipped"]
        self.assertEqual([c["path"] for c in skipped], ["/alarm/appliance"])
        self.assertIn("GET alternatives", skipped[0]["error"])
        self.assertIn("GET /health/alarmPeriodSummary", " ".join(report.compute(b)["sections"]["avail-alarms"]["notes"]))

    def test_errors_are_recorded_with_their_http_status(self):
        from edgeconnect_mcp.errors import EdgeConnectError
        answers = self.answers()
        answers["/stats/aggregate/availability/appliance"] = EdgeConnectError("HTTP 500: There was an internal server error.")
        b = report.collect(self.server(RoutedClient(answers), get_only=True), "lab", "availability", "2026-09")
        errors = [c for c in b["calls"] if c["outcome"] == "error"]
        self.assertEqual({(c["path"], c["http_status"]) for c in errors}, {("/stats/aggregate/availability/appliance", 500)})

    def test_cli_pipeline_writes_metrics_and_html(self):
        folder = Path(self.tmp.name)
        (folder / "bundle.json").write_text(json.dumps(bundle()))
        self.assertEqual(report.main(["compute", str(folder / "bundle.json")]), 0)
        (folder / "narrative.json").write_text(json.dumps({"report": "availability", "sections": {"avail-summary": {"text": "{{m:fleet_reach_pct}}"}}}))
        self.assertEqual(report.main(["validate", str(folder / "metrics.json"), str(folder / "narrative.json")]), 0)
        self.assertEqual(report.main(["render", str(folder / "metrics.json"), str(folder / "narrative.json"), "--out", str(folder / "r.html")]), 0)
        self.assertIn("<!doctype html>", (folder / "r.html").read_text())
        (folder / "narrative.json").write_text(json.dumps({"report": "availability", "sections": {"avail-summary": {"text": "7 sites"}}}))
        self.assertEqual(report.main(["validate", str(folder / "metrics.json"), str(folder / "narrative.json")]), 1)


if __name__ == "__main__":
    unittest.main()
