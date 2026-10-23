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
         "/stats/aggregate/availability/tunnel", "/health/alarmPeriodSummary", "/alarm/summary", "/gmsLicense", "/license/portal/summary",
         "/alarm/count/appliance", "/gms/stats/nonStatsTable/retention", "/maintenanceMode", "/tunnels2/physical", "/tunnels2/bonded",
         "/stats/timeseries/interfaceOverlay", "/stats/timeseries/interface", "/license/portal/appliance", "/appliance/backup",
         "/health/healthThresholdConfig", "/stats/aggregate/tunnel"]
POSTS = ["/alarm/appliance", "/health", "/stats/aggregate/interface"]
SPEC = {"swagger": "2.0", "basePath": "/gms/rest", "paths": dict({p: {"get": {"summary": p}} for p in PATHS}, **{p: {"post": {"summary": p}} for p in POSTS})}
APPLIANCES = [{"nePk": "1.NE", "hostName": "branch-a", "state": 1, "model": "EC-V", "softwareVersion": "9.6.2.1_1", "serial": "SN-0001"},
              {"nePk": "2.NE", "hostName": "branch-b<script>", "state": 2, "model": "EC-XS", "softwareVersion": "9.7.1.0_1", "serial": "SN-0002"}]


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

    def test_executive_statuses(self):
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
        b = report.collect(self.server(client, get_only=False), "lab", "availability", "2026-09")
        posts = [c for c in client.calls if c[0] == "POST"]
        self.assertEqual(posts, [("POST", "/alarm/appliance", {"view": "all", "from": 1788220800000, "to": 1790812799000, "maxAlarms": 10000, "orderBySeverity": True}, {"nePks": ["1.NE", "2.NE"]})])
        reach = [c for c in client.calls if c[1] == "/stats/aggregate/availability/appliance"]
        self.assertEqual(reach[0][2], {"nePk": "1.NE", "date": "2026-09-01", "granularity": "month"})
        self.assertEqual({c["id"]: c["outcome"] for c in b["calls"] if c["id"].startswith("reach:")}, {"reach:1.NE": "ok", "reach:2.NE": "empty"})
        b = report.collect(self.server(client, get_only=False), "lab", "lifecycle", "2026-09")
        self.assertNotIn("AAAA", json.dumps(b))  # licence keys and serials never reach a bundle
        self.assertNotIn("00-11", json.dumps(b))
        self.assertNotIn("SN-000", json.dumps(b))  # GET /appliance names it plain `serial`
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


NOW = 1790000000  # 2026-09-21


def phase2_bundle(report_name, **data):
    b = bundle(**data)
    b["report"] = report_name
    b["period"]["now_s"] = NOW
    return b


class NocTests(unittest.TestCase):
    def test_state_alarms_health_tunnels_and_worst_sites(self):
        health = {"1.NE": [{"status": "HEALTHY", "time": NOW - 3600}, {"status": "CRITICAL", "time": NOW - 7200}, {"blank": True, "status": None, "time": NOW - 60},
                           {"status": "WARNING", "time": NOW - 3 * 86400}],
                  "2.NE": [{"status": "HEALTHY", "time": NOW - 3600}, {"status": "HEALTHY", "time": NOW - 5 * 86400}]}
        tunnels = {"1.NE": {"t1": {"operStatus": "Up - Active", "alias": "a"}, "t2": {"operStatus": "Down", "alias": "b"}}, "2.NE": {"t3": {"operStatus": "Up - Idle", "alias": "c"}}}
        alarms = [{"applianceId": "2.NE", "severity": "CRITICAL", "description": "Tunnel down", "timeOccurredInMills": (NOW - 60) * 1000}, {"applianceId": "1.NE", "severity": "MINOR"}]
        m = report.compute(phase2_bundle("noc", health=health, tunnels_physical=tunnels, tunnels_bonded={}, active_alarms=alarms,
                                         alarm_retention={"historical_appliance_alarm": {"retention": 604800}}))
        v = {k: m["metrics"][k]["value"] for k in ("state_normal", "state_unreachable", "active_critical", "active_minor", "health_good_24h_pct", "health_good_7d_pct", "tunnels_physical_down", "tunnels_physical_total")}
        self.assertEqual(v, {"state_normal": 1, "state_unreachable": 1, "active_critical": 1, "active_minor": 1, "health_good_24h_pct": 66.667, "health_good_7d_pct": 60.0,
                             "tunnels_physical_down": 1, "tunnels_physical_total": 3})
        s = {sid: sec["status"] for sid, sec in m["sections"].items()}
        self.assertEqual((s["noc-appliances"], s["noc-alarms"], s["noc-health"], s["noc-tunnels"], s["noc-summary"]), ("red", "red", "red", "red", "red"))
        self.assertIn("keeps 7 days of alarm history", " ".join(m["sections"]["noc-alarms"]["notes"]))
        worst = m["sections"]["noc-worst"]["table"]
        self.assertEqual([(r["appliance"], r["score"]) for r in worst], [("branch-b<script>", 110), ("branch-a", 3)])  # not normal + critical; tunnel down + unhealthy hour

    def test_get_only_alarm_counts_and_no_health(self):
        m = report.compute(phase2_bundle("noc", alarm_summary={"numOfCriticalAlarms": 0, "numOfMajorAlarms": 2, "numOfMinorAlarms": 1, "numOfWarningAlarms": 0},
                                         alarm_counts=[{"applianceId": "1.NE", "numOfMajorAlarms": 2}]))
        self.assertEqual((m["sections"]["noc-alarms"]["status"], m["metrics"]["active_major"]["value"]), ("amber", 2))
        self.assertEqual(m["sections"]["noc-alarms"]["table"][0]["major"], 2)
        self.assertEqual((m["sections"]["noc-health"]["status"], m["metrics"]["health_good_24h_pct"]["value"]), ("grey", None))
        self.assertIn("POST /health did not run", " ".join(m["sections"]["data-gaps"]["notes"]))


class CapacityTests(unittest.TestCase):
    TOTALS = [{"nePk": "1.NE", "INTERFACE": "wan0", "TRAFFIC_TYPE": 4, "SUM_TX_BYTES": 1080000000000, "SUM_RX_BYTES": 0, "AVG_MAX_BW_TX": 100000, "AVG_MAX_BW_RX": 100000,
               "MIN_TIMESTAMP": 0, "MAX_TIMESTAMP": 0},
              {"nePk": "1.NE", "INTERFACE": "blan0", "TRAFFIC_TYPE": 4, "SUM_TX_BYTES": 9e12, "AVG_MAX_BW_TX": 1000},
              {"nePk": "2.NE", "INTERFACE": "wan1.20", "TRAFFIC_TYPE": 4, "SUM_TX_BYTES": 0, "SUM_RX_BYTES": 0, "AVG_MAX_BW_TX": 50000, "AVG_MAX_BW_RX": 50000, "MIN_TIMESTAMP": 0, "MAX_TIMESTAMP": 0}]

    def test_wan_links_average_utilisation_and_ranking(self):
        links = report.wan_links({"interface_totals": self.TOTALS}, {"1.NE": "a", "2.NE": "b"})
        self.assertEqual([(l["nePk"], l["interface"], l["avg_tx_pct"]) for l in links], [("1.NE", "wan0", 100.0), ("2.NE", "wan1.20", 0.0)])  # LAN ignored
        overlay = [{"INTERFACE": "wan0", "ISWANSIDE": True, "TX_BYTES": 540000000, "RX_BYTES": 0, "MAX_BW_TX": 1000, "MAX_BW_RX": 1000, "LABELNAME": "INET"},
                   {"INTERFACE": "wan0", "ISWANSIDE": True, "TX_BYTES": 540000000, "RX_BYTES": 0, "MAX_BW_TX": 1000, "MAX_BW_RX": 1000, "LABELNAME": "INET"},
                   {"INTERFACE": "lan0", "ISWANSIDE": False, "TX_BYTES": 1e12}]
        links = report.wan_links({"wan_side:1.NE": overlay}, ["1.NE"])
        self.assertEqual([(l["interface"], l["label"], l["avg_tx_pct"]) for l in links], [("wan0", "INET", 10.0)])  # 1.08 GB over a day on 1 Mbps

    def test_p95_of_hourly_utilisation_flags_links_at_80_percent(self):
        hourly = [{"tx_bytes": 45000000000 * pct / 100, "rx_bytes": 0, "max_bw_tx": 100000, "max_bw_rx": 100000} for pct in range(1, 101)]  # 100 hours, 1..100%
        m = report.compute(phase2_bundle("capacity", interface_totals=self.TOTALS, **{"hourly:1.NE:wan0": hourly}))
        rows = {(r["appliance"], r["interface"]): r for r in m["sections"]["cap-links"]["table"]}
        self.assertEqual((rows[("branch-a", "wan0")]["p95_out_pct"], rows[("branch-a", "wan0")]["status"]), (95.0, "red"))
        self.assertEqual(rows[("branch-b<script>", "wan1.20")]["status"], "grey")  # no hourly data: not in the top N
        self.assertEqual({k: m["metrics"][k]["value"] for k in ("links_flagged", "worst_p95_pct", "links_measured", "wan_links")},
                         {"links_flagged": 1, "worst_p95_pct": 95.0, "links_measured": 1, "wan_links": 2})
        self.assertEqual(report._p95([5.0]), 5.0)
        self.assertIsNone(report._p95([]))


class LifecycleTests(unittest.TestCase):
    def test_advisory_versions(self):
        advisory = {"fixed_in": {"9.6": "9.6.1", "9.5": "9.5.6", "9.4": "9.4.8"}}
        cases = {"9.6.0.40000": "below 9.6.1", "9.6.1.1": None, "9.5.5_1": "below 9.5.6", "9.4.8.0": None, "9.3.7.0_96892": "no fix in the 9.3 train; upgrade",
                 "9.7.1.42046": None, "10.0.0.40625": None, "": None}
        self.assertEqual({v: report.advisory_hit(v, advisory) for v in cases}, cases)

    def test_licences_backups_advisories_and_eol(self):
        portal = {"data": [{"applianceId": "1.NE", "expirationDate": (NOW + 20 * 86400) * 1000}, {"applianceId": "2.NE", "expirationDate": (NOW + 60 * 86400) * 1000}]}
        m = report.compute(phase2_bundle("lifecycle", versions={"current": "9.6.0.1"}, gms_license={"daysToExpiration": 400, "usedAppliances": 2}, portal_appliances=portal,
                                         **{"backup:1.NE": [{"backupTime": NOW - 40 * 86400}, {"backupTime": NOW - 2 * 86400}], "backup:2.NE": []}))
        v = {k: m["metrics"][k]["value"] for k in ("licences_expiring_30", "licences_expiring_90", "backups_stale", "advisory_hits", "ecos_trains")}
        self.assertEqual(v, {"licences_expiring_30": 1, "licences_expiring_90": 2, "backups_stale": 1, "advisory_hits": 1, "ecos_trains": 2})
        s = {sid: sec["status"] for sid, sec in m["sections"].items()}
        self.assertEqual((s["life-licences"], s["life-backups"], s["life-advisories"], s["life-eol"], s["life-summary"]), ("red", "amber", "red", "grey", "red"))
        self.assertEqual(m["sections"]["life-advisories"]["table"][0]["target"], "Orchestrator")
        page = report.render(m)
        self.assertIn("<title>Lifecycle, licence and vulnerability report, as of 2026-09-21", page)
        self.assertIn("2 of 2 appliances returned data", page)
        self.assertIn("as of", " ".join(m["sections"]["life-advisories"]["notes"]))


class Phase2CollectTests(CollectTests):
    def answers(self):
        a = super().answers()
        a.update({"/stats/aggregate/interface": CapacityTests.TOTALS, "/stats/timeseries/interfaceOverlay": {"1.NE": [{"INTERFACE": "wan0", "ISWANSIDE": True, "TX_BYTES": 1, "MAX_BW_TX": 10}]}})
        return a

    def test_capacity_get_only_finds_wan_links_from_overlay_stats_then_reads_hourly(self):
        client = RoutedClient(self.answers())
        report.collect(self.server(client, get_only=True), "lab", "capacity", "2026-09", now=datetime(2026, 9, 21, tzinfo=timezone.utc))
        paths = [(c[0], c[1], (c[2] or {}).get("interfaceName"), (c[2] or {}).get("granularity")) for c in client.calls if c[1].startswith("/stats")]
        self.assertEqual(paths, [("GET", "/stats/timeseries/interfaceOverlay", None, "day"), ("GET", "/stats/timeseries/interfaceOverlay", None, "day"),
                                 ("GET", "/stats/timeseries/interface", "wan0", "hour")])
        hourly = [c for c in client.calls if c[1] == "/stats/timeseries/interface"][0][2]
        self.assertEqual(hourly["endTime"] - hourly["startTime"], 14 * 86400)  # hourly retention caps the P95 window

    def test_capacity_uses_the_totals_post_and_the_top_n(self):
        client = RoutedClient(self.answers())
        report.collect(self.server(client, get_only=False), "lab", "capacity", "2026-09", top=1, now=datetime(2026, 9, 21, tzinfo=timezone.utc))
        self.assertEqual([(c[0], c[1], (c[2] or {}).get("interfaceName")) for c in client.calls if c[1].startswith("/stats")],
                         [("POST", "/stats/aggregate/interface", None), ("GET", "/stats/timeseries/interface", "wan0")])

    def test_noc_and_lifecycle_requests(self):
        client = RoutedClient(self.answers())
        report.collect(self.server(client, get_only=False), "lab", "executive", "2026-09", now=datetime(2026, 9, 21, tzinfo=timezone.utc))
        health = [c for c in client.calls if c[1] == "/health"][0]
        self.assertEqual((health[3]["to"] - health[3]["from"], health[3]["nePks"]), (7 * 86400, ["1.NE", "2.NE"]))  # seconds
        self.assertEqual([c[2]["runningConfig"] for c in client.calls if c[1] == "/appliance/backup"], ["false", "false"])
        self.assertEqual([c[2] for c in client.calls if c[1] == "/tunnels2/bonded"], [{"operStatus": "true", "srcNePk": "true", "alias": "true", "tag": "true"}])


class PresentationTests(unittest.TestCase):
    def executive(self, down=1, total=12, **data):
        inventory = [{"nePk": "{}.NE".format(i), "hostName": "site-{}".format(i), "state": 2 if i < down else 1, "softwareVersion": "9.7.1.0_1"} for i in range(total)]
        b = phase2_bundle("executive", appliances=inventory, **data)
        return report.compute(b)

    def test_fleet_is_amber_with_any_appliance_down_and_red_above_ten_percent(self):
        self.assertEqual([self.executive(down=d)["sections"]["exec-fleet"]["status"] for d in (0, 1, 2)], ["green", "amber", "red"])  # 0, 8.3%, 16.7% down
        self.assertNotIn("table", self.executive()["sections"]["exec-fleet"])  # the appliance list lives in the availability and NOC reports

    def test_executive_verdict_and_kpi_strip(self):
        m = self.executive(down=1, alarm_summary={"numOfCriticalAlarms": 2, "numOfMajorAlarms": 0, "numOfMinorAlarms": 0, "numOfWarningAlarms": 0})
        self.assertEqual(m["headline"]["status"], "red")
        self.assertTrue(m["headline"]["text"].startswith("Overall: Red. Attention needed in Fleet"))
        self.assertIn("Active alarms", m["headline"]["text"])
        self.assertEqual(m["headline"]["kpis"], list(report.EXEC_KPIS))
        page = report.render(m)
        self.assertLess(page.index('data-section-id="verdict"'), page.index('data-section-id="exec-fleet"'))
        self.assertIn('data-section-id="kpi-strip"', page)
        self.assertIsNone(report.compute(bundle())["headline"])  # only the executive page has one

    def test_availability_summary_follows_availability_not_alarms(self):
        m = report.compute(bundle(appliance_alarms=[{"applianceId": "1.NE", "severity": "CRITICAL"}]))
        self.assertEqual((m["sections"]["avail-alarms"]["status"], m["sections"]["avail-summary"]["status"]), ("red", "amber"))

    def test_tunnels_down_all_period_are_listed_apart_and_left_out_and_the_table_keeps_the_worst_25(self):
        overlay = {"1": [{"count": 1000, "tunnel_state": 0, "blackout": 0, "brownout": 0},
                         {"count": 1000, "tunnel_state": 60000, "blackout": 60000, "brownout": 0, "label": "INET", "serviceName": "SSE", "tunnelcount": 2}]}
        m = report.compute(bundle(**{"overlay:1.NE": overlay}))  # default: include them
        self.assertEqual((m["metrics"]["overlay_avail_pct"]["value"], m["metrics"]["tunnel_groups_down_all_period"]["value"]), (50.0, 2))
        self.assertIn("counted in the figures above", " ".join(m["sections"]["avail-tunnels"]["notes"]))
        b = bundle(**{"overlay:1.NE": overlay})
        b["options"] = {"down_tunnels": "separate"}
        m = report.compute(b)
        self.assertEqual((m["metrics"]["overlay_avail_pct"]["value"], m["metrics"]["tunnel_groups_down_all_period"]["value"]), (100.0, 2))
        self.assertIn("branch-a overlay INET SSE (2 tunnels)", " ".join(m["sections"]["avail-tunnels"]["notes"]))
        self.assertIn("down tunnels: separate (2 down all period and 0 idle tunnels losing probes excluded)", report.render(m))
        many = [{"nePk": "{}.NE".format(i), "hostName": "s{}".format(i), "state": 1} for i in range(30)]
        data = {"appliances": many}
        data.update({"overlay:{}.NE".format(i): {"1": [{"count": 100, "tunnel_state": i, "blackout": 0}]} for i in range(30)})
        m = report.compute(bundle(**data))
        self.assertEqual(len(m["sections"]["avail-tunnels"]["table"]), 25)
        self.assertIn("Worst 25 shown; 6 more rows not shown.", m["sections"]["avail-tunnels"]["notes"])  # 30 overlay rows + the fixture's underlay row

    def test_singular_units_status_coloured_bars_and_labelled_axis(self):
        self.assertEqual(report._fmt({"value": 1, "unit": "alarms"}), "1 alarm")
        self.assertEqual(report._fmt({"value": 2, "unit": "alarms"}), "2 alarms")
        svg = report._chart({"title": "t", "zoom": True, "points": [("a", 95.0, "red"), ("b", 100.0, "green")]})
        self.assertIn('class="bar red"', svg)
        self.assertIn('class="bar green"', svg)
        self.assertIn("Scale 90% to 100% (zoomed)", svg)
        self.assertIn("Scale 0% to 100%", report._chart({"title": "t", "zoom": False, "points": [("a", 5.0, "green")]}))


THRESHOLDS = {"packetLoss": {"goodLimit": 0.1, "okLimit": 1.0}, "latency": {"goodLimit": 20.0, "okLimit": 50.0},
              "jitter": {"goodLimit": 10.0, "okLimit": 20.0}, "mos": {"goodLimit": 1.0, "okLimit": 4.0}}


class ReviewFixTests(unittest.TestCase):
    def test_serials_never_reach_a_bundle(self):
        self.assertEqual(report._scrub({"serial": "X", "serialNumber": "Y", "hostName": "a"}), {"hostName": "a"})

    def test_get_only_alarm_severities_count_only_the_appliances_in_scope(self):
        m = report.compute(phase2_bundle("noc", alarm_summary={"numOfCriticalAlarms": 9, "numOfMajorAlarms": 9, "numOfMinorAlarms": 9, "numOfWarningAlarms": 9},
                                         alarm_counts=[{"applianceId": "1.NE", "numOfCriticalAlarms": 1}, {"applianceId": "99.NE", "numOfCriticalAlarms": 5}]))
        self.assertEqual((m["metrics"]["active_critical"]["value"], m["metrics"]["active_major"]["value"]), (1, 0))

    def test_stats_store_down_ignores_skipped_and_refused_posts(self):
        b = bundle(**{"reach:1.NE": None, "reach:2.NE": None})
        b["calls"] = [{"id": "r", "method": "GET", "path": "/stats/aggregate/availability/appliance", "outcome": "error", "http_status": 500, "error": "HTTP 500"},
                      {"id": "i", "method": "POST", "path": "/stats/aggregate/interface", "outcome": "skipped", "error": "get_only"},
                      {"id": "j", "method": "POST", "path": "/stats/aggregate/interface", "outcome": "error", "http_status": 403, "error": "HTTP 403"}]
        self.assertTrue(report.compute(b)["stats_store_down"])

    def test_licence_tile_and_section_use_one_rule(self):
        for days, expected in ((30, "red"), (90, "amber"), (91, "green")):
            m = report.compute(phase2_bundle("lifecycle", gms_license={"daysToExpiration": days}))
            self.assertEqual((m["metrics"]["license_days_left"]["status"], m["sections"]["life-licences"]["status"]), (expected, expected), days)

    def test_alarm_list_at_the_cap_is_a_gap(self):
        m = report.compute(phase2_bundle("noc", active_alarms=[{"applianceId": "1.NE", "severity": "MINOR"}] * report.MAX_ALARMS))
        self.assertIn("10000-alarm cap", " ".join(m["sections"]["data-gaps"]["notes"]))
        m = report.compute(bundle(appliance_alarms=[{"applianceId": "1.NE", "severity": "MINOR"}] * report.MAX_ALARMS))
        self.assertIn("10000-alarm cap", " ".join(m["sections"]["data-gaps"]["notes"]))

    def test_validator_allows_severity_names_and_fixed_terms(self):
        metrics = report.compute(bundle())  # avail-summary is amber
        ok = {"report": "availability", "sections": {"avail-summary": {"text": "One critical alarm and a warning alarm were raised; P95 over the last 24 hours stayed low on ECOS 9.6.2 and the last 7 days."}}}
        self.assertEqual(report.validate(metrics, ok), [])
        bad = {"report": "availability", "sections": {"avail-summary": {"text": "Reachability was 99 percent; there was an outage."}}}
        problems = " ".join(report.validate(metrics, bad))
        self.assertIn("bare number", problems)
        self.assertIn("implies red", problems)

    def test_path_quality_grades_each_tunnel_against_the_health_thresholds(self):
        paths = {"bondedTunnel_1": {"1.NE": {"alias": "to_hub_DEFAULT", "overlayid": "1", "SUM_POST_LOSS": 200, "SUM_WRX_PKTS": 99800, "AVG_LATENCY_AVG": 30, "AVG_JITTER": 2, "mos": 430}},
                 "tunnel_2": {"1.NE": {"alias": "to_hub_INET", "overlayid": "0", "SUM_POST_LOSS": 0, "SUM_WRX_PKTS": 100000, "AVG_LATENCY_AVG": 5, "AVG_JITTER": 1, "mos": 440}},
                 "tunnel_3": {"1.NE": {"alias": "to_hub_LTE", "overlayid": "0", "SUM_POST_LOSS": 5000, "SUM_WRX_PKTS": 95000, "AVG_LATENCY_AVG": 90, "AVG_JITTER": 30, "mos": 50}},
                 "bondedTunnel_4": {"1.NE": {"alias": "to_hub_GUEST", "overlayid": "2", "SUM_POST_LOSS": 3433, "SUM_WRX_PKTS": 0, "AVG_LATENCY_AVG": 5, "AVG_JITTER": 1, "mos": 440}}}
        m = report.compute(bundle(health_threshold=THRESHOLDS, **{"paths:1.NE": paths}))
        rows = {r["tunnel"]: (r["loss_pct"], r["latency_ms"], r["mos"], r["status"]) for r in m["sections"]["avail-paths"]["table"]}
        self.assertEqual(rows, {"to_hub_DEFAULT": (0.2, 30.0, 4.3, "amber"), "to_hub_INET": (0.0, 5.0, 4.4, "green"), "to_hub_LTE": (5.0, 90.0, 0.5, "red"),
                                "to_hub_GUEST": (None, 5.0, 4.4, "red")})  # no traffic but probes lost: a broken path, red, not "no data"
        self.assertEqual([r["tunnel"] for r in m["sections"]["avail-paths"]["table"]][0], "to_hub_LTE")  # worst first
        self.assertEqual({k: m["metrics"][k]["value"] for k in ("paths_measured", "paths_red", "paths_amber")}, {"paths_measured": 4, "paths_red": 2, "paths_amber": 1})
        self.assertEqual(m["sections"]["avail-paths"]["status"], "red")
        self.assertEqual(m["metrics"]["paths_idle_probe_loss"]["value"], 1)
        b = bundle(health_threshold=THRESHOLDS, **{"paths:1.NE": paths})
        b["options"] = {"down_tunnels": "separate"}
        m = report.compute(b)  # separate: listed apart and left out of the status
        self.assertNotIn("to_hub_GUEST", [r["tunnel"] for r in m["sections"]["avail-paths"]["table"]])
        self.assertIn("listed apart", " ".join(m["sections"]["avail-paths"]["notes"]))
        self.assertIn("1 idle tunnels losing probes excluded", report.render(m))
        silent = {"tunnel_9": {"1.NE": {"alias": "to_hub_SPARE", "overlayid": "0", "SUM_POST_LOSS": 0, "SUM_WRX_PKTS": 0, "AVG_LATENCY_AVG": 5, "AVG_JITTER": 1, "mos": 440}}}
        row = report.compute(bundle(health_threshold=THRESHOLDS, **{"paths:1.NE": silent}))["sections"]["avail-paths"]["table"][0]
        self.assertEqual((row["loss_pct"], row["note"], row["status"]), (None, "", "green"))  # no packets and no probe loss: loss is no data
        m = report.compute(bundle(**{"paths:1.NE": paths}))  # no thresholds read: defaults, listed as a gap
        self.assertIn("healthThresholdConfig", " ".join(m["sections"]["data-gaps"]["notes"]))

    def test_banner_names_statistics_not_only_availability(self):
        m = report.compute(phase2_bundle("capacity"))
        m["stats_store_down"] = True
        self.assertIn("so statistics are missing", report.render(m))


class ReviewCollectTests(CollectTests):
    def answers(self):
        a = super().answers()
        a.update({"/stats/aggregate/interface": CapacityTests.TOTALS,
                  "/gms/stats/retention": {"interface": [{"granularity": "HOUR", "retention": 7 * 86400}, {"granularity": "HOUR", "retention": 3 * 86400}, {"granularity": "DAY", "retention": 93 * 86400}]}})
        return a

    def test_capacity_past_month_uses_daily_data_and_current_month_uses_hourly_retention(self):
        client = RoutedClient(self.answers())
        b = report.collect(self.server(client, get_only=False), "lab", "capacity", "2026-09", now=datetime(2026, 10, 23, tzinfo=timezone.utc))
        series = [c[2] for c in client.calls if c[1] == "/stats/timeseries/interface"]
        self.assertEqual({(q["granularity"], q["startTime"], q["endTime"]) for q in series}, {("day", 1788220800, 1790812799)})
        self.assertEqual(b["data"]["capacity_basis"]["granularity"], "day")
        client = RoutedClient(self.answers())
        report.collect(self.server(client, get_only=False), "lab", "capacity", "2026-10", now=datetime(2026, 10, 23, tzinfo=timezone.utc))
        q = [c[2] for c in client.calls if c[1] == "/stats/timeseries/interface"][0]
        self.assertEqual((q["granularity"], q["endTime"] - q["startTime"]), ("hour", 7 * 86400))  # the longer HOUR retention read from the Orchestrator

    def test_daily_basis_is_computed_per_day_and_labelled(self):
        daily = [{"tx_bytes": 1080000000000 * 0.5, "rx_bytes": 0, "max_bw_tx": 100000, "max_bw_rx": 100000}]  # half of 100 Mbps for a day
        m = report.compute(phase2_bundle("capacity", interface_totals=CapacityTests.TOTALS, capacity_basis={"granularity": "day", "retention_known": True},
                                         **{"hourly:1.NE:wan0": daily}))
        row = [r for r in m["sections"]["cap-links"]["table"] if r["interface"] == "wan0"][0]
        self.assertEqual(row["p95_out_pct"], 50.0)
        self.assertIn("daily averages", " ".join(m["sections"]["cap-links"]["notes"]))

    def test_nickname_case_and_dotenv_environment(self):
        client = RoutedClient(self.answers())
        report.collect(self.server(client, get_only=False), "Lab", "availability", "2026-09", now=datetime(2026, 10, 23, tzinfo=timezone.utc))
        self.assertTrue([c for c in client.calls if c[0] == "POST"])  # not skipped as get_only
        from unittest import mock
        with mock.patch.dict("os.environ", {"EDGECONNECT_DOTENV": "/x/ec.env"}), mock.patch.object(report.Server, "from_dotenv", side_effect=OSError("stop")) as loader, \
                mock.patch("sys.stderr"):
            self.assertEqual(report.main(["collect", "--orchestrator", "lab", "--report", "noc"]), 1)
        loader.assert_called_once_with("/x/ec.env")


class OptionTests(CollectTests):
    def test_choices_outside_the_list_are_rejected(self):
        from unittest import mock
        for bad in (["--target", "98"], ["--down-tunnels", "drop"], ["--period", "last-week"]):
            with mock.patch("sys.stderr"), self.assertRaises(SystemExit):
                report.main(["collect", "--orchestrator", "lab", "--report", "availability"] + bad)
        with self.assertRaises(ValueError):
            report.collect(self.server(RoutedClient(self.answers()), get_only=True), "lab", "availability", target="95")
        with self.assertRaisesRegex(ValueError, "does not have: nowhere"):
            report.collect(self.server(RoutedClient(self.answers()), get_only=True), "lab", "availability", appliances=["branch-a", "nowhere"])

    def test_period_defaults_to_last_month_and_options_are_stored_and_printed(self):
        now = datetime(2026, 1, 10, tzinfo=timezone.utc)
        self.assertEqual((report.resolve_month("last-month", now), report.resolve_month("month-to-date", now)), ("2025-12", "2026-01"))
        b = report.collect(self.server(RoutedClient(self.answers()), get_only=True), "lab", "availability", appliances=["branch-a"], now=now, target="99.9")
        self.assertEqual(b["options"], {"period": "last-month", "month": "2025-12", "scope": ["branch-a"], "target": "99.9", "down_tunnels": "include"})
        page = report.render(report.compute(b))
        self.assertIn("Report options: period: last-month (2025-12); scope: branch-a; availability target: 99.9%; down tunnels: include", page)
        self.assertEqual(page.count("Report options:"), 2)  # under the title and in the footer

    def test_a_fixed_target_is_met_or_missed(self):
        b = bundle()  # fleet 99.75%
        b["options"] = {"target": "99.5"}
        self.assertEqual(report.compute(b)["metrics"]["fleet_reach_pct"]["status"], "green")
        b["options"] = {"target": "99.9"}
        self.assertEqual(report.compute(b)["metrics"]["fleet_reach_pct"]["status"], "red")


class ReviewRound2Tests(unittest.TestCase):
    def test_severity_words_without_alarm_after_them_are_not_status_words(self):
        metrics = report.compute(bundle())  # avail-alarms is amber (2 major)
        for text in ("{{m:alarms_major}} major and {{m:alarms_critical}} critical ones.",
                     "{{m:alarms_critical}} critical, {{m:alarms_major}} major and {{m:alarms_minor}} minor alarms, plus a warning."):
            self.assertEqual(report.validate(metrics, {"report": "availability", "sections": {"avail-alarms": {"text": text}}}), [], text)
        self.assertTrue(report.validate(metrics, {"report": "availability", "sections": {"avail-alarms": {"text": "There was an outage."}}}))

    def test_scoped_get_only_alarms_never_fall_back_to_network_wide_totals(self):
        summary = {"numOfCriticalAlarms": 9, "numOfMajorAlarms": 9, "numOfMinorAlarms": 9, "numOfWarningAlarms": 9}
        b = phase2_bundle("noc", alarm_summary=summary)
        b["options"] = {"scope": ["branch-a"]}
        m = report.compute(b)
        self.assertEqual((m["metrics"]["active_critical"]["value"], m["sections"]["noc-alarms"]["status"]), (None, "grey"))
        self.assertIn("network-wide", " ".join(m["sections"]["data-gaps"]["notes"]))
        self.assertEqual(report.compute(phase2_bundle("noc", alarm_summary=summary))["metrics"]["active_critical"]["value"], 9)  # scope all: the summary is right

    def test_noc_health_band_is_printed_as_the_reports_own_rule(self):
        m = report.compute(phase2_bundle("noc", health={"1.NE": [{"status": "HEALTHY", "time": NOW - 60}]}))
        self.assertIn("the report's own rule", " ".join(m["sections"]["noc-health"]["notes"]))

    def test_fixed_terms_are_only_the_report_windows(self):
        metrics = report.compute(bundle())
        bad = {"report": "availability", "sections": {"avail-summary": {"text": "The licence expires in 7 days."}}}
        self.assertIn("bare number", " ".join(report.validate(metrics, bad)))
        ok = {"report": "availability", "sections": {"avail-summary": {"text": "Over the last 7 days and the last 24 hours, P95 held."}}}
        self.assertEqual(report.validate(metrics, ok), [])

    def test_a_period_older_than_daily_retention_is_a_gap(self):
        b = bundle(retention={"tunnel": [{"granularity": "DAY", "retention": 31 * 86400}], "interface": [{"granularity": "DAY", "retention": 31 * 86400}]})
        b["period"].update(from_ms=(NOW - 60 * 86400) * 1000, now_s=NOW)
        self.assertIn("older than the 31 days of daily statistics", " ".join(report.compute(b)["sections"]["data-gaps"]["notes"]))
        b["period"].update(from_ms=(NOW - 10 * 86400) * 1000)
        self.assertNotIn("daily statistics", " ".join(report.compute(b)["sections"]["data-gaps"]["notes"]))


if __name__ == "__main__":
    unittest.main()
