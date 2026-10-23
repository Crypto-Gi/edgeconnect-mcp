"""Orchestrator reports: collect -> compute -> (the agent writes narrative.json) -> validate -> render. Standard library only.

collect  runs a fixed recipe of reads through the MCP server in-process (same .env, spec allowlist, redaction, audit log
         and get_only rule) and writes bundle.json with every call's provenance.
compute  turns the bundle into metrics.json: every number and every green/amber/red/grey status the report shows.
template prints the narrative skeleton: section ids, computed status and the metric ids the prose may cite.
validate checks narrative.json: numbers only as {{m:<metric id>}} tokens, known sections, no status that contradicts compute.
render   writes one self-contained HTML5 file (inline CSS and SVG, no JavaScript).
"""
import argparse
import calendar
import hashlib
import html
import json
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from string import Template
from typing import Any, Dict, List, Mapping, Optional, Tuple

from . import __version__
from .errors import EdgeConnectError
from .server import HOME_DOTENV, Server, ToolError

STATUSES = ("green", "amber", "red", "grey")
REPORTS = ("availability", "executive")
SECTIONS = {
    "availability": (("avail-summary", "Availability summary"), ("avail-appliances", "Appliance reachability"),
                     ("avail-tunnels", "Tunnel availability"), ("avail-alarms", "Alarms in the period"), ("data-gaps", "Data gaps")),
    "executive": (("exec-fleet", "Fleet"), ("exec-availability", "Availability"), ("exec-alarms", "Active alarms"),
                  ("exec-licensing", "Licensing"), ("exec-software", "Software versions"), ("exec-capacity", "WAN capacity"),
                  ("exec-noc", "NOC digest"), ("exec-lifecycle", "Lifecycle and vulnerabilities"), ("data-gaps", "Data gaps")),
}
NOT_BUILT = ("exec-capacity", "exec-noc", "exec-lifecycle")  # sections whose reports come in a later phase: always grey
DEFAULT_AVAILABILITY = (99.0, 99.5)  # used, and flagged, when GET /stats/config/availabilityThreshold returns nothing
# Keys never copied into a bundle, whatever the server's redaction does.
_DROP_KEYS = re.compile(r"licen[cs]e[-_]?key|serial[-_]?number|account[-_]?key|password|secret|token", re.I)
_TOKEN = re.compile(r"\{\{m:([A-Za-z0-9_.\-]+)\}\}")
_STATUS_WORDS = {"green": ("healthy", "on target", "meets target", "met target", "no issues"),
                 "amber": ("degraded", "at risk", "warning", "needs attention"),
                 "red": ("critical", "failing", "below target", "missed target", "outage"),
                 "grey": ("no data", "not available", "unknown")}
MAX_TEXT = 1200


# --- collect -----------------------------------------------------------------

class Collector:
    def __init__(self, server: Any, orchestrator: str) -> None:
        self.server, self.orchestrator = server, orchestrator
        self.calls: List[Dict[str, Any]] = []
        self.data: Dict[str, Any] = {}
        self.read_posts = next((o["read_posts_enabled"] for o in self._tool("list_orchestrators", {})[1] if o["name"] == orchestrator), False)

    def _tool(self, name: str, arguments: Mapping[str, Any]) -> Tuple[bool, Any]:
        response = self.server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": dict(arguments, max_chars=10 ** 9)}})
        text = response["result"]["content"][0]["text"]
        if response["result"]["isError"]:
            return False, text.split("\n", 1)[0][len("Error: "):] if text.startswith("Error: ") else text
        value = json.loads(text)
        return True, value.get("result") if isinstance(value, dict) and "result" in value else value

    def call(self, cid: str, path: str, query: Optional[Dict[str, Any]] = None, body: Any = None) -> Any:
        method = "GET" if body is None else "POST"
        record: Dict[str, Any] = {"id": cid, "method": method, "path": path, "query": query or {}, "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        if body is not None:
            record["body"] = body
        if method == "POST" and not self.read_posts:
            record.update(outcome="skipped", error="read-only POSTs are off for this Orchestrator (get_only); GET alternatives used")
            self.calls.append(record)
            return None
        started = time.monotonic()
        arguments: Dict[str, Any] = {"orchestrator": self.orchestrator, "path": path, "query": query or {}}
        ok, value = self._tool("api_get" if body is None else "api_read_post", dict(arguments, **({"body": body} if body is not None else {})))
        record["seconds"] = round(time.monotonic() - started, 2)
        if not ok:
            status = re.search(r"HTTP (\d{3})", str(value))
            record.update(outcome="error", error=str(value)[:300], http_status=int(status.group(1)) if status else None)
            self.calls.append(record)
            return None
        value = _scrub(value)
        record["outcome"] = "empty" if value in (None, [], {}, "") or value == {"data": []} else "ok"
        self.calls.append(record)
        self.data[cid] = value
        return value


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _scrub(v) for k, v in value.items() if not _DROP_KEYS.search(str(k))}
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value


def month_window(month: str, now: Optional[datetime] = None) -> Tuple[date, int, int]:
    """First day, start and end (epoch ms) of YYYY-MM; the current month ends now."""
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        raise ValueError("--month must be YYYY-MM")
    year, number = int(month[:4]), int(month[5:])
    first = date(year, number, 1)
    start = datetime(year, number, 1, tzinfo=timezone.utc)
    end = datetime(year, number, calendar.monthrange(year, number)[1], 23, 59, 59, tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    if start > now:
        raise ValueError("--month {} is in the future".format(month))
    return first, int(start.timestamp() * 1000), int(min(end, now).timestamp() * 1000)


def collect(server: Any, orchestrator: str, report: str, month: str, appliances: Optional[List[str]] = None) -> Dict[str, Any]:
    first, start_ms, end_ms = month_window(month)
    c = Collector(server, orchestrator)
    c.call("versions", "/gms/versions")
    inventory = c.call("appliances", "/appliance") or []
    if appliances:
        inventory = [a for a in inventory if a.get("nePk") in appliances or a.get("hostName") in appliances]
    c.call("availability_threshold", "/stats/config/availabilityThreshold")
    c.call("retention", "/gms/stats/retention")
    nepks = [a["nePk"] for a in inventory if a.get("nePk")]
    for ne in nepks:
        # Availability takes a date, alarms take epoch milliseconds (stats aggregates would take seconds).
        c.call("reach:" + ne, "/stats/aggregate/availability/appliance", {"nePk": ne, "date": first.isoformat(), "granularity": "month"})
        c.call("overlay:" + ne, "/stats/aggregate/availability/tunnel", {"nePk": ne, "date": first.isoformat(), "granularity": "month", "overlayId": "all"})
        c.call("underlay:" + ne, "/stats/aggregate/availability/tunnel", {"nePk": ne, "date": first.isoformat(), "granularity": "month", "overlayId": "0"})
        c.call("alarm_period:" + ne, "/health/alarmPeriodSummary", {"applianceId": ne, "from": start_ms, "to": end_ms})
    if nepks:
        c.call("appliance_alarms", "/alarm/appliance", {"view": "all", "from": start_ms, "to": end_ms, "maxAlarms": 10000, "orderBySeverity": True}, {"nePks": nepks})
    if report == "executive":
        c.call("alarm_summary", "/alarm/summary")
        c.call("gms_license", "/gmsLicense")
        c.call("portal_license", "/license/portal/summary")
    bundle = {"kind": "edgeconnect-report-bundle", "generator": __version__, "report": report, "orchestrator": orchestrator,
              "period": {"month": month, "from_ms": start_ms, "to_ms": end_ms},
              "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "read_posts_enabled": c.read_posts, "calls": c.calls, "data": c.data,
              "units": {"stats_aggregate_time": "epoch seconds", "alarm_and_audit_time": "epoch milliseconds", "availability": "date YYYY-MM-DD; values are minute sample counts"}}
    return bundle


# --- compute -----------------------------------------------------------------

def band(value: Optional[float], limits: Tuple[float, float], higher_is_better: bool = True) -> str:
    """green / amber / red against two limits; grey when there is no value. Limit order does not matter."""
    if value is None:
        return "grey"
    low, high = sorted(limits)
    if higher_is_better:
        return "green" if value >= high else "amber" if value >= low else "red"
    return "green" if value <= low else "amber" if value <= high else "red"


def worst(statuses: List[str]) -> str:
    known = [s for s in statuses if s != "grey"]
    return max(known, key=("green", "amber", "red").index) if known else "grey"


def _limits(threshold: Any, key: str) -> Tuple[Tuple[float, float], bool]:
    item = threshold.get(key) if isinstance(threshold, dict) else None
    if isinstance(item, dict) and isinstance(item.get("goodLimit"), (int, float)) and isinstance(item.get("okLimit"), (int, float)):
        return (float(item["goodLimit"]), float(item["okLimit"])), False
    return DEFAULT_AVAILABILITY, True


def _pct(part: float, whole: float) -> Optional[float]:
    return round(100.0 * part / whole, 3) if whole else None


def _tunnel_totals(value: Any) -> Dict[str, float]:
    """Seconds sampled, down and degraded. `count` is minute samples while tunnel_state, blackout and brownout are seconds
    (seen on 9.7.1 and 10.0: count 1441 for a day, downtime up to count x 60); tunnel_state and blackout overlap, so take the larger."""
    totals = {"seconds": 0.0, "down": 0.0, "brownout": 0.0}
    groups = value.values() if isinstance(value, dict) else [value] if isinstance(value, list) else []
    for group in groups:
        for row in group if isinstance(group, list) else []:
            if isinstance(row, dict):
                seconds = 60.0 * float(row.get("count") or 0)
                totals["seconds"] += seconds
                totals["down"] += min(seconds, max(float(row.get("tunnel_state") or 0), float(row.get("blackout") or 0)))
                totals["brownout"] += min(seconds, float(row.get("brownout") or 0))
    return totals


def compute(bundle: Mapping[str, Any]) -> Dict[str, Any]:
    data, calls = bundle["data"], bundle["calls"]
    metrics: Dict[str, Dict[str, Any]] = {}
    sections: Dict[str, Dict[str, Any]] = {}
    gaps: List[str] = []

    def metric(mid: str, value: Any, unit: str, label: str, status: Optional[str] = None) -> str:
        metrics[mid] = {"value": value, "unit": unit, "label": label, "status": status}
        return mid

    stats_calls = [c for c in calls if c["path"].startswith("/stats/")]
    stats_down = bool(stats_calls) and all(c.get("outcome") == "error" and c.get("http_status") == 500 for c in stats_calls)
    for c in calls:
        if c.get("outcome") in ("error", "skipped") and not (stats_down and c["path"].startswith("/stats/")):
            gaps.append("{} {}: {}".format(c["method"], c["path"], c.get("error") or c["outcome"]))
    if stats_down:
        gaps.insert(0, "Every statistics call returned HTTP 500: the Orchestrator's statistics store is down, so availability is not shown.")

    inventory = data.get("appliances") or []
    names = {a.get("nePk"): a.get("hostName") or a.get("nePk") for a in inventory}
    reachable_now = [a for a in inventory if a.get("state") == 1]
    threshold = data.get("availability_threshold") or {}

    # Appliance reachability: minute samples, so % = reachable minutes / sample count.
    limits, default_used = _limits(threshold, "reachability")
    if default_used:
        gaps.append("No availability thresholds configured; default {} / {} % used.".format(*DEFAULT_AVAILABILITY))
    rows, total_reach, total_samples = [], 0.0, 0.0
    for ne, name in names.items():
        sample = (data.get("reach:" + str(ne)) or [{}])[0] if isinstance(data.get("reach:" + str(ne)), list) else {}
        samples, reach = float(sample.get("samplecount") or 0), float(sample.get("appliancereachability") or 0)
        pct = _pct(reach, samples)
        if pct is None and not stats_down:
            state = next((a.get("state") for a in inventory if a.get("nePk") == ne), None)
            gaps.append("{}: no reachability samples for the month{}.".format(name, " although it is reachable now (check ECOS 9.3.4/9.4.2/9.5.0 or later, and retention)" if state == 1 else ""))
        total_reach, total_samples = total_reach + reach, total_samples + samples
        rows.append({"appliance": name, "nePk": ne, "value": pct, "status": band(pct, limits)})
    fleet = _pct(total_reach, total_samples)
    m_fleet = metric("fleet_reach_pct", fleet, "%", "Fleet appliance reachability", band(fleet, limits))
    below = [r for r in rows if r["status"] in ("amber", "red")]
    m_below = metric("appliances_below_target", len(below) if fleet is not None else None, "appliances", "Appliances below the reachability target")
    m_measured = metric("appliances_measured", sum(1 for r in rows if r["value"] is not None), "appliances", "Appliances with reachability data")
    m_total = metric("appliances_total", len(inventory), "appliances", "Appliances in scope")
    metric("reach_target_pct", max(limits), "%", "Reachability target")
    rows.sort(key=lambda r: (r["value"] is None, r["value"] if r["value"] is not None else 0))
    sections["avail-appliances"] = {"status": metrics[m_fleet]["status"], "metrics": [m_fleet, m_below, m_measured, "reach_target_pct"],
                                    "table": rows, "chart": [(r["appliance"], r["value"]) for r in rows if r["value"] is not None][:25]}

    # Tunnel availability, derived: 1 - down seconds / sampled seconds; brownout is shown as a degraded share.
    tunnel_metrics, tunnel_rows, tunnel_status = [], [], []
    for kind, key, label in (("overlay", "overlayAvailability", "Overlay"), ("underlay", "underlayAvailability", "Underlay")):
        lim, _ = _limits(threshold, key)
        totals = {"seconds": 0.0, "down": 0.0, "brownout": 0.0}
        for ne, name in names.items():
            t = _tunnel_totals(data.get("{}:{}".format(kind, ne)))
            for k in totals:
                totals[k] += t[k]
            if t["seconds"]:
                pct = _pct(t["seconds"] - t["down"], t["seconds"])
                tunnel_rows.append({"appliance": name, "kind": label, "value": pct, "degraded_pct": _pct(t["brownout"], t["seconds"]), "status": band(pct, lim)})
        pct = _pct(totals["seconds"] - totals["down"], totals["seconds"])
        tunnel_status.append(band(pct, lim))
        tunnel_metrics += [metric(kind + "_avail_pct", pct, "%", label + " tunnel availability (derived)", band(pct, lim)),
                           metric(kind + "_degraded_pct", _pct(totals["brownout"], totals["seconds"]), "%", label + " brownout share")]
    tunnel_rows.sort(key=lambda r: (r["value"] is None, r["value"] or 0))
    sections["avail-tunnels"] = {"status": worst(tunnel_status), "metrics": tunnel_metrics, "table": tunnel_rows,
                                 "notes": ["Derived from the Orchestrator's tunnel availability data as 1 - downtime / time sampled (samples are minutes, downtime is seconds); brownout is reported separately."]}

    # Alarms raised in the period: the full list if the read POST ran, otherwise per-appliance counts (GET).
    counts = {"CRITICAL": 0, "MAJOR": 0, "MINOR": 0, "WARNING": 0}
    alarm_rows: List[Dict[str, Any]] = []
    listed = data.get("appliance_alarms")
    if isinstance(listed, list):
        for alarm in listed:
            sev = str(alarm.get("severity") or "").upper()
            if sev in counts:
                counts[sev] += 1
            if sev in ("CRITICAL", "MAJOR") and len(alarm_rows) < 15:
                alarm_rows.append({"appliance": names.get(alarm.get("applianceId"), alarm.get("applianceId")), "severity": sev.lower(), "description": str(alarm.get("description") or "")[:160]})
        source = "POST /alarm/appliance"
    else:
        for ne in names:
            period = data.get("alarm_period:" + str(ne)) or {}
            for sev, n in ((period.get("alarmCountsInPeriod") or {}) if isinstance(period, dict) else {}).items():
                if str(sev).upper() in counts and isinstance(n, int):
                    counts[str(sev).upper()] += n
        source = "GET /health/alarmPeriodSummary per appliance"
    have_alarms = isinstance(listed, list) or any(("alarm_period:" + str(ne)) in data for ne in names)
    alarm_status = "grey" if not have_alarms else "red" if counts["CRITICAL"] else "amber" if counts["MAJOR"] else "green"
    alarm_ids = [metric("alarms_" + sev.lower(), counts[sev] if have_alarms else None, "alarms", sev.title() + " alarms in the period") for sev in counts]
    sections["avail-alarms"] = {"status": alarm_status, "metrics": alarm_ids, "table": alarm_rows, "notes": ["Source: " + source + "."]}

    availability_status = worst([sections["avail-appliances"]["status"], sections["avail-tunnels"]["status"]])
    summary_status = worst([availability_status, sections["avail-alarms"]["status"]])
    sections["avail-summary"] = {"status": summary_status, "metrics": [m_fleet, "overlay_avail_pct", "underlay_avail_pct", "alarms_critical", m_total]}

    if bundle["report"] == "executive":
        share = _pct(len(reachable_now), len(inventory))
        m_now = metric("reachable_now_pct", share, "%", "Appliances reachable at collection time", band(share, limits))
        metric("reachable_now", len(reachable_now), "appliances", "Appliances reachable at collection time")
        sections["exec-fleet"] = {"status": metrics[m_now]["status"], "metrics": [m_total, "reachable_now", m_now],
                                  "table": [{"appliance": a.get("hostName"), "model": a.get("model"), "ecos": a.get("softwareVersion"), "reachable": "yes" if a.get("state") == 1 else "no"}
                                            for a in sorted(inventory, key=lambda a: (a.get("state") == 1, str(a.get("hostName"))))][:40]}
        sections["exec-availability"] = {"status": availability_status, "metrics": [m_fleet, "overlay_avail_pct", "underlay_avail_pct", "appliances_below_target"]}
        active = data.get("alarm_summary") if isinstance(data.get("alarm_summary"), dict) else None
        ids = [metric("active_" + sev, active.get("numOf{}Alarms".format(sev.title())) if active else None, "alarms", "Active {} alarms".format(sev)) for sev in ("critical", "major", "minor", "warning")]
        sections["exec-alarms"] = {"status": "grey" if not active else "red" if metrics[ids[0]]["value"] else "amber" if metrics[ids[1]]["value"] else "green", "metrics": ids}
        lic = data.get("gms_license") if isinstance(data.get("gms_license"), dict) else None
        days = lic.get("daysToExpiration") if lic else None
        lic_status = "grey" if not isinstance(days, int) else "red" if days < 30 else "amber" if days < 90 else "green"
        sections["exec-licensing"] = {"status": lic_status, "metrics": [
            metric("license_days_left", days, "days", "Days until the Orchestrator licence expires", lic_status),
            metric("license_used", lic.get("usedAppliances") if lic else None, "appliances", "Licensed appliances in use"),
            metric("license_max", lic.get("maxAppliances") if lic else None, "appliances", "Appliance licence limit")],
            "notes": ["Rule: under 30 days red, under 90 days amber."]}
        versions: Dict[str, int] = {}
        for a in inventory:
            versions[str(a.get("softwareVersion") or "unknown")] = versions.get(str(a.get("softwareVersion") or "unknown"), 0) + 1
        trains = {re.sub(r"^(\d+\.\d+).*", r"\1", v) for v in versions}
        sw_status = "grey" if not inventory else "green" if len(trains) <= 1 else "amber"
        sections["exec-software"] = {"status": sw_status, "metrics": [metric("ecos_versions", len(versions), "versions", "Distinct ECOS builds"),
                                                                     metric("ecos_trains", len(trains), "trains", "Distinct ECOS trains (major.minor)", sw_status),
                                                                     metric("orchestrator_version", (data.get("versions") or {}).get("current"), "", "Orchestrator release")],
                                     "table": [{"ecos": v, "appliances": n} for v, n in sorted(versions.items(), key=lambda item: -item[1])],
                                     "notes": ["Rule: more than one ECOS train in use is amber."]}
        for sid in NOT_BUILT:
            sections[sid] = {"status": "grey", "metrics": [], "notes": ["This report is not built yet."]}
    sections["data-gaps"] = {"status": "grey" if gaps else "green", "metrics": [], "notes": gaps or ["None: every call returned data."]}

    answered = sum(1 for ne in names if ("reach:" + str(ne)) in data)
    return {"kind": "edgeconnect-report-metrics", "report": bundle["report"], "orchestrator": bundle["orchestrator"],
            "orchestrator_version": (data.get("versions") or {}).get("current") if isinstance(data.get("versions"), dict) else None,
            "period": bundle["period"], "collected_at": bundle["collected_at"], "bundle_sha256": bundle.get("sha256"),
            "coverage": {"appliances": len(names), "with_availability_data": answered}, "stats_store_down": stats_down,
            "metrics": metrics, "sections": {sid: sections[sid] for sid, _ in SECTIONS[bundle["report"]]}}


# --- narrative -----------------------------------------------------------------

def template(metrics: Mapping[str, Any]) -> Dict[str, Any]:
    order = [sid for sid, _ in SECTIONS[metrics["report"]] if sid in metrics["sections"]]  # metrics.json keys are sorted
    return {"report": metrics["report"], "sections": {sid: {"status": metrics["sections"][sid]["status"], "text": "", "cite": metrics["sections"][sid]["metrics"]} for sid in order}}


def validate(metrics: Mapping[str, Any], narrative: Any) -> List[str]:
    problems: List[str] = []
    if not isinstance(narrative, dict) or narrative.get("report") != metrics["report"] or not isinstance(narrative.get("sections"), dict):
        return ["narrative must be {\"report\": \"%s\", \"sections\": {...}}" % metrics["report"]]
    for sid, section in narrative["sections"].items():
        if sid not in metrics["sections"]:
            problems.append("{}: unknown section".format(sid))
            continue
        if not isinstance(section, dict) or set(section) - {"status", "text", "cite"}:
            problems.append("{}: a section has only status, text and cite".format(sid))
            continue
        computed = metrics["sections"][sid]["status"]
        if section.get("status") not in (None, computed):
            problems.append("{}: status {!r} contradicts the computed status {!r}".format(sid, section.get("status"), computed))
        text = section.get("text") or ""
        if not isinstance(text, str) or len(text) > MAX_TEXT:
            problems.append("{}: text must be a string of at most {} characters".format(sid, MAX_TEXT))
            continue
        for mid in _TOKEN.findall(text):
            if mid not in metrics["metrics"]:
                problems.append("{}: {{{{m:{}}}}} is not a metric".format(sid, mid))
        prose = _TOKEN.sub(" ", text)
        if re.search(r"\d", prose):
            problems.append("{}: bare number in the text; cite numbers only as {{{{m:<metric id>}}}}: {!r}".format(sid, re.search(r".{0,20}\d.{0,20}", prose).group(0)))
        if "{{" in prose or "}}" in prose:
            problems.append("{}: malformed token; use {{{{m:<metric id>}}}}".format(sid))
        lowered = prose.lower()
        for status, words in _STATUS_WORDS.items():
            if status != computed and any(re.search(r"\b" + re.escape(w) + r"\b", lowered) for w in words):
                problems.append("{}: wording implies {} but the computed status is {}".format(sid, status, computed))
    return problems


# --- render ------------------------------------------------------------------

PAGE = Template("""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>$title</title>
<style>
:root{--bg:#14171c;--fg:#e8eaed;--muted:#9aa0a6;--card:#1e2229;--line:#333a44;--green:#3fb950;--amber:#d29922;--red:#f85149;--grey:#8b949e;--bar:#58a6ff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px}h1{font-size:24px;margin:0 0 4px}h2{font-size:18px;margin:0 0 8px}
.meta,.note,footer{color:var(--muted);font-size:13px}section{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:16px;margin:16px 0;break-inside:avoid}
.status{display:inline-block;font-weight:600;font-size:13px;padding:2px 10px;border-radius:12px;border:1px solid currentColor;margin-bottom:8px}
.green{color:var(--green)}.amber{color:var(--amber)}.red{color:var(--red)}.grey{color:var(--grey)}
.banner{border:2px solid var(--red);color:var(--fg);padding:12px 16px;border-radius:8px;margin:16px 0}
.kpis{display:flex;flex-wrap:wrap;gap:12px;margin:8px 0}.kpi{border:1px solid var(--line);border-radius:6px;padding:8px 12px;min-width:150px}
.kpi b{display:block;font-size:20px}.kpi span{color:var(--muted);font-size:12px}
table{width:100%;border-collapse:collapse;font-size:13px;margin-top:8px}th,td{text-align:left;padding:4px 6px;border-bottom:1px solid var(--line)}
svg{width:100%;height:auto;margin-top:8px}svg text{fill:var(--fg);font-size:11px}svg rect.bar{fill:var(--bar)}
@media print{@page{size:A4;margin:14mm}:root{--bg:#fff;--fg:#111;--muted:#555;--card:#fff;--line:#ccc;--green:#1a7f37;--amber:#9a6700;--red:#cf222e;--grey:#57606a;--bar:#0969da}main{max-width:none;padding:0}}
</style></head><body><main>
<header><h1>$title</h1><div class="meta">$subtitle</div></header>
$banner
$sections
<footer><p>Orchestrator $orchestrator, release $version. Data collected $collected for $period. Coverage: $coverage. Bundle SHA-256 $bundle. Generated by edgeconnect-mcp $generator; numbers and statuses are computed by code, the prose only cites them.</p></footer>
</main></body></html>
""")


def _fmt(metric: Mapping[str, Any], unit_word: bool = True) -> str:
    """A metric for display; in prose (unit_word False) only % is kept, so "{{m:alarms_critical}} critical alarms" reads right."""
    value = metric.get("value")
    if value is None:
        return "no data"
    if isinstance(value, float):
        value = "{:.2f}".format(value)
    unit = metric.get("unit") or ""
    return "{}{}".format(value, unit if unit == "%" else (" " + unit if unit and unit_word else ""))


def _chart(points: List[Tuple[str, float]], title: str) -> str:
    if not points:
        return ""
    floor = min(90.0, min(v for _, v in points))  # zoom so 99.9 and 100 can be told apart
    width, row = 640, 18
    bars = []
    for i, (label, value) in enumerate(points):
        length = 0 if value <= floor else (value - floor) / (100.0 - floor) * (width - 260)
        y = i * row
        bars.append('<text x="0" y="{0}">{1}</text><rect class="bar" x="200" y="{2}" width="{3:.1f}" height="12"><title>{1}: {4:.2f}%</title></rect>'
                    '<text x="{5:.1f}" y="{0}">{4:.2f}%</text>'.format(y + 11, html.escape(str(label)[:28]), y + 1, length, value, 206 + length))
    return '<svg viewBox="0 0 {} {}" role="img" aria-label="{}"><title>{}</title>{}</svg>'.format(width, len(points) * row + 4, html.escape(title), html.escape(title), "".join(bars))


def _table(rows: List[Mapping[str, Any]]) -> str:
    if not rows:
        return ""
    columns = list(rows[0].keys())
    cell = lambda v: "no data" if v is None else "{:.2f}".format(v) if isinstance(v, float) else html.escape(str(v))
    head = "".join("<th>{}</th>".format(html.escape(c)) for c in columns)
    body = "".join("<tr>{}</tr>".format("".join('<td class="{}">{}</td>'.format(r[c] if c == "status" else "", cell(r[c])) for c in columns)) for r in rows)
    return "<table><thead><tr>{}</tr></thead><tbody>{}</tbody></table>".format(head, body)


def render(metrics: Mapping[str, Any], narrative: Optional[Mapping[str, Any]] = None) -> str:
    if narrative is not None:
        problems = validate(metrics, narrative)
        if problems:
            raise ValueError("narrative.json is not valid:\n" + "\n".join(problems))
    titles = dict(SECTIONS[metrics["report"]])
    texts = (narrative or {}).get("sections") or {}
    parts = []
    for sid in (sid for sid, _ in SECTIONS[metrics["report"]] if sid in metrics["sections"]):  # metrics.json keys are sorted
        sec = metrics["sections"][sid]
        text = html.escape((texts.get(sid) or {}).get("text") or "")
        text = _TOKEN.sub(lambda m: html.escape(_fmt(metrics["metrics"][m.group(1)], unit_word=False)), text)
        kpis = "".join('<div class="kpi"><b class="{}">{}</b><span>{}</span></div>'.format(metrics["metrics"][mid].get("status") or "", html.escape(_fmt(metrics["metrics"][mid])), html.escape(metrics["metrics"][mid]["label"]))
                       for mid in sec.get("metrics", []) if mid in metrics["metrics"])
        notes = "".join('<p class="note">{}</p>'.format(html.escape(n)) for n in sec.get("notes", []))
        chart = _chart(sec.get("chart") or [], "Lowest appliance reachability, % of the month")
        parts.append('<section data-section-id="{0}"><h2>{1}</h2><div class="status {2}">Status: {3}</div>{4}<div class="kpis">{5}</div>{6}{7}{8}</section>'.format(
            sid, html.escape(titles[sid]), sec["status"], sec["status"].title(), "<p>{}</p>".format(text) if text else "", kpis, chart, _table(sec.get("table") or []), notes))
    banner = '<div class="banner" data-section-id="stats-store-down">Statistics store down: every statistics call returned HTTP 500, so availability numbers are missing.</div>' if metrics.get("stats_store_down") else ""
    coverage = metrics.get("coverage") or {}
    return PAGE.substitute(
        title=html.escape("{} report, {}".format(metrics["report"].title(), metrics["period"]["month"])),
        subtitle=html.escape("Orchestrator {} · period {}".format(metrics["orchestrator"], metrics["period"]["month"])),
        banner=banner, sections="\n".join(parts), orchestrator=html.escape(str(metrics["orchestrator"])), version=html.escape(str(metrics.get("orchestrator_version"))),
        collected=html.escape(str(metrics["collected_at"])), period=html.escape(metrics["period"]["month"]),
        coverage=html.escape("{} of {} appliances returned availability data".format(coverage.get("with_availability_data"), coverage.get("appliances"))),
        bundle=html.escape(str(metrics.get("bundle_sha256"))), generator=html.escape(__version__))


# --- CLI ---------------------------------------------------------------------

def _load(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _dump(path: Path, value: Any) -> None:
    Path(path).write_text(json.dumps(value, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")  # order kept: sections and table columns


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="edgeconnect-mcp report", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("collect", help="read the Orchestrator and write bundle.json")
    p.add_argument("--orchestrator", required=True)
    p.add_argument("--report", choices=REPORTS, required=True)
    p.add_argument("--month", default=datetime.now(timezone.utc).strftime("%Y-%m"), help="YYYY-MM (default: this month to date)")
    p.add_argument("--appliances", help="comma-separated nePks or host names (default: all)")
    p.add_argument("--out", type=Path, default=Path("."), help="folder for bundle.json")
    p.add_argument("--dotenv")
    for name, help_text in (("compute", "bundle.json -> metrics.json"), ("template", "metrics.json -> narrative skeleton")):
        q = sub.add_parser(name, help=help_text)
        q.add_argument("input", type=Path)
    q = sub.add_parser("validate", help="check narrative.json against metrics.json")
    q.add_argument("metrics", type=Path)
    q.add_argument("narrative", type=Path)
    q = sub.add_parser("render", help="metrics.json [+ narrative.json] -> report.html")
    q.add_argument("metrics", type=Path)
    q.add_argument("narrative", type=Path, nargs="?")
    q.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "collect":
            dotenv = args.dotenv or next((str(path) for path in (HOME_DOTENV, Path(".env")) if path.is_file()), None)
            server = Server.from_dotenv(dotenv)
            server.log = lambda line: None
            bundle = collect(server, args.orchestrator, args.report, args.month, [a.strip() for a in args.appliances.split(",")] if args.appliances else None)
            bundle["sha256"] = hashlib.sha256(json.dumps(bundle, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
            args.out.mkdir(parents=True, exist_ok=True)
            _dump(args.out / "bundle.json", bundle)
            failed = sum(1 for c in bundle["calls"] if c["outcome"] in ("error", "skipped"))
            print("{}: {} calls, {} without data; wrote {}".format(args.orchestrator, len(bundle["calls"]), failed, args.out / "bundle.json"))
        elif args.command == "compute":
            out = args.input.with_name("metrics.json")
            _dump(out, compute(_load(args.input)))
            print("wrote {}".format(out))
        elif args.command == "template":
            print(json.dumps(template(_load(args.input)), indent=1))
        elif args.command == "validate":
            problems = validate(_load(args.metrics), _load(args.narrative))
            for problem in problems:
                print(problem)
            if problems:
                return 1
            print("narrative is valid")
        elif args.command == "render":
            args.out.write_text(render(_load(args.metrics), _load(args.narrative) if args.narrative else None), encoding="utf-8")
            print("wrote {}".format(args.out))
    except (ValueError, KeyError, OSError, EdgeConnectError, ToolError) as exc:
        print("edgeconnect-mcp report: {}".format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
