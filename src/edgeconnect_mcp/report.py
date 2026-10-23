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
import math
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from string import Template
from typing import Any, Dict, List, Mapping, Optional, Tuple

from . import __version__
from .advisories import ADVISORIES, AS_OF as ADVISORIES_AS_OF
from .errors import EdgeConnectError
from .server import HOME_DOTENV, Server, ToolError

STATUSES = ("green", "amber", "red", "grey")
REPORTS = ("availability", "noc", "capacity", "lifecycle", "executive")
SECTIONS = {
    "availability": (("avail-summary", "Availability summary"), ("avail-appliances", "Appliance reachability"),
                     ("avail-tunnels", "Tunnel availability"), ("avail-alarms", "Alarms in the period"), ("data-gaps", "Data gaps")),
    "noc": (("noc-summary", "NOC summary"), ("noc-appliances", "Appliance state"), ("noc-alarms", "Active alarms"), ("noc-health", "Health"),
            ("noc-tunnels", "Tunnels down"), ("noc-worst", "Sites needing attention"), ("data-gaps", "Data gaps")),
    "capacity": (("cap-summary", "WAN capacity summary"), ("cap-links", "WAN links by P95 utilisation"), ("data-gaps", "Data gaps")),
    "lifecycle": (("life-summary", "Lifecycle summary"), ("life-inventory", "Inventory and software"), ("life-licences", "Licences"),
                  ("life-backups", "Backups"), ("life-advisories", "Security advisories"), ("life-eol", "Hardware end of life"), ("data-gaps", "Data gaps")),
    "executive": (("exec-fleet", "Fleet"), ("exec-availability", "Availability"), ("exec-alarms", "Active alarms"),
                  ("exec-licensing", "Licensing"), ("exec-software", "Software versions"), ("exec-capacity", "WAN capacity"),
                  ("exec-noc", "NOC digest"), ("exec-lifecycle", "Lifecycle and vulnerabilities"), ("data-gaps", "Data gaps")),
}
TITLES = {"availability": "Availability report", "noc": "NOC digest", "capacity": "WAN capacity report",
          "lifecycle": "Lifecycle, licence and vulnerability report", "executive": "Executive summary"}
PARTS = {"executive": ("availability", "noc", "capacity", "lifecycle")}  # reports that combine others; the rest are themselves
STATE_NAMES = {1: "normal", 2: "unreachable", 3: "unsupported", 4: "out of sync", 5: "syncing"}  # GET /appliance `state`
GOOD_HEALTH = ("HEALTHY",)  # POST /health hourly `status` that counts as good; the spec enum is HEALTHY, WARNING, MINOR, MAJOR, CRITICAL
WAN_INTERFACE = re.compile(r"^b?wan\d", re.I)  # WAN ports and their VLANs (wan0, wan1.20, bwan0) in POST /stats/aggregate/interface
HEALTH_VERTICALS = ["ALARM", "LOSS", "LATENCY", "JITTER", "MOS", "BW_UTILIZATION"]
HOURLY_RETENTION = 14 * 86400  # hourly stats are kept 14 days by default (GET /gms/stats/retention), so P95 looks back at most this far
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
            record.update(outcome="skipped", error="read-only POSTs are off for this Orchestrator (get_only); GET alternatives used where one exists")
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


def collect(server: Any, orchestrator: str, report: str, month: str, appliances: Optional[List[str]] = None, top: int = 20,
            now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    first, start_ms, end_ms = month_window(month, now)
    c = Collector(server, orchestrator)
    c.call("versions", "/gms/versions")
    inventory = c.call("appliances", "/appliance") or []
    if appliances:
        inventory = [a for a in inventory if a.get("nePk") in appliances or a.get("hostName") in appliances]
        c.data["appliances"] = inventory
    nepks = [a["nePk"] for a in inventory if a.get("nePk")]
    parts = PARTS.get(report, (report,))
    if "availability" in parts:
        _collect_availability(c, nepks, first, start_ms, end_ms)
    if "noc" in parts:
        _collect_noc(c, nepks, int(now.timestamp()))
    if "capacity" in parts:
        _collect_capacity(c, nepks, start_ms // 1000, end_ms // 1000, top)
    if "lifecycle" in parts:
        _collect_lifecycle(c, nepks)
    return {"kind": "edgeconnect-report-bundle", "generator": __version__, "report": report, "orchestrator": orchestrator,
            "period": {"month": month, "from_ms": start_ms, "to_ms": end_ms, "now_s": int(now.timestamp())},
            "collected_at": now.isoformat(timespec="seconds"), "read_posts_enabled": c.read_posts, "calls": c.calls, "data": c.data,
            "units": {"stats_time": "epoch seconds", "alarm_and_audit_time": "epoch milliseconds", "availability": "date YYYY-MM-DD; values are minute sample counts",
                      "bandwidth": "kbps", "interface_bytes": "bytes per bucket"}}


def _collect_availability(c: Collector, nepks: List[str], first: date, start_ms: int, end_ms: int) -> None:
    c.call("availability_threshold", "/stats/config/availabilityThreshold")
    c.call("retention", "/gms/stats/retention")
    for ne in nepks:
        # Availability takes a date, alarms take epoch milliseconds (stats aggregates would take seconds).
        c.call("reach:" + ne, "/stats/aggregate/availability/appliance", {"nePk": ne, "date": first.isoformat(), "granularity": "month"})
        c.call("overlay:" + ne, "/stats/aggregate/availability/tunnel", {"nePk": ne, "date": first.isoformat(), "granularity": "month", "overlayId": "all"})
        c.call("underlay:" + ne, "/stats/aggregate/availability/tunnel", {"nePk": ne, "date": first.isoformat(), "granularity": "month", "overlayId": "0"})
        c.call("alarm_period:" + ne, "/health/alarmPeriodSummary", {"applianceId": ne, "from": start_ms, "to": end_ms})
    if nepks:
        c.call("appliance_alarms", "/alarm/appliance", {"view": "all", "from": start_ms, "to": end_ms, "maxAlarms": 10000, "orderBySeverity": True}, {"nePks": nepks})


def _collect_noc(c: Collector, nepks: List[str], now_s: int) -> None:
    c.call("alarm_summary", "/alarm/summary")
    c.call("alarm_counts", "/alarm/count/appliance")
    c.call("alarm_retention", "/gms/stats/nonStatsTable/retention")
    c.call("maintenance", "/maintenanceMode")
    # Network-wide in one call each; the boolean selectors keep only the fields named.
    c.call("tunnels_physical", "/tunnels2/physical", {"operStatus": "true", "srcNePk": "true", "alias": "true"})
    c.call("tunnels_bonded", "/tunnels2/bonded", {"operStatus": "true", "srcNePk": "true", "alias": "true", "tag": "true"})
    if nepks:
        c.call("active_alarms", "/alarm/appliance", {"view": "active", "maxAlarms": 10000, "orderBySeverity": True}, {"nePks": nepks})
        c.call("health", "/health", {}, {"from": now_s - 7 * 86400, "to": now_s, "nePks": nepks, "overlayId": -1, "verticals": HEALTH_VERTICALS})


def _collect_capacity(c: Collector, nepks: List[str], start_s: int, end_s: int, top: int) -> None:
    if not nepks:
        return
    totals = c.call("interface_totals", "/stats/aggregate/interface", {"startTime": start_s, "endTime": end_s, "granularity": "day", "trafficType": "all_traffic"}, {"nePks": nepks})
    if totals is None:  # GET-only, or the POST was refused: the overlay transport stats mark WAN-side interfaces (last day only)
        for ne in nepks:
            c.call("wan_side:" + ne, "/stats/timeseries/interfaceOverlay", {"nePk": ne, "startTime": end_s - 86400, "endTime": end_s, "granularity": "day"})
    hourly_from = max(start_s, end_s - HOURLY_RETENTION)
    for link in wan_links(c.data, nepks)[:top]:  # busiest first, so the P95 reads go to the links most likely to be full
        c.call("hourly:{}:{}".format(link["nePk"], link["interface"]), "/stats/timeseries/interface",
               {"nePk": link["nePk"], "startTime": hourly_from, "endTime": end_s, "granularity": "hour", "trafficType": "all_traffic", "interfaceName": link["interface"]})


def _collect_lifecycle(c: Collector, nepks: List[str]) -> None:
    c.call("gms_license", "/gmsLicense")
    c.call("portal_appliances", "/license/portal/appliance")
    for ne in nepks:
        c.call("backup:" + ne, "/appliance/backup", {"nePk": ne, "runningConfig": "false"})  # without it each backup carries its whole config


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


def _p95(values: List[float]) -> Optional[float]:
    """Nearest-rank 95th percentile."""
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)], 2)


def _version(text: Any) -> Tuple[int, ...]:
    """9.6.2.1_107093 -> (9, 6, 2, 1); 9.7.1.42046 -> (9, 7, 1, 42046)."""
    match = re.match(r"\d+(?:\.\d+)*", str(text or ""))
    return tuple(int(part) for part in match.group(0).split(".")) if match else ()


def advisory_hit(version: Any, advisory: Mapping[str, Any]) -> Optional[str]:
    """Why `version` is affected by `advisory`, or None. Trains newer than every listed one are not affected."""
    v = _version(version)
    if len(v) < 2:
        return None
    fixed = {_version(train): _version(build) for train, build in advisory["fixed_in"].items()}
    train = v[:2]
    if train in fixed:
        return "below {}".format(".".join(map(str, fixed[train]))) if v < fixed[train] else None
    return "no fix in the {} train; upgrade".format(".".join(map(str, train))) if train < min(fixed) else None


def wan_links(data: Mapping[str, Any], nepks: Any) -> List[Dict[str, Any]]:
    """WAN interfaces with their average utilisation over the window, busiest first.

    From POST /stats/aggregate/interface when it ran (one row per interface; BW in kbps; daily buckets), else from the
    WAN-side rows of GET /stats/timeseries/interfaceOverlay for the last day (summed over overlays)."""
    links: Dict[Tuple[str, str], Dict[str, Any]] = {}
    rows = data.get("interface_totals")
    if isinstance(rows, list):
        for row in rows:
            name = str(row.get("INTERFACE") or "")
            if row.get("nePk") in nepks and WAN_INTERFACE.match(name) and row.get("TRAFFIC_TYPE") in (4, None):
                seconds = float(row.get("MAX_TIMESTAMP") or 0) - float(row.get("MIN_TIMESTAMP") or 0) + 86400
                links[(row["nePk"], name)] = {"nePk": row["nePk"], "interface": name, "label": "", "tx_bytes": float(row.get("SUM_TX_BYTES") or 0),
                                              "rx_bytes": float(row.get("SUM_RX_BYTES") or 0), "bw_tx": float(row.get("AVG_MAX_BW_TX") or 0),
                                              "bw_rx": float(row.get("AVG_MAX_BW_RX") or 0), "seconds": seconds, "source": "POST /stats/aggregate/interface"}
    else:
        for ne in nepks:
            for row in data.get("wan_side:" + str(ne)) or []:
                if not isinstance(row, dict) or not row.get("ISWANSIDE"):
                    continue
                link = links.setdefault((ne, str(row.get("INTERFACE"))), {"nePk": ne, "interface": str(row.get("INTERFACE")), "label": str(row.get("LABELNAME") or ""),
                                                                         "tx_bytes": 0.0, "rx_bytes": 0.0, "bw_tx": 0.0, "bw_rx": 0.0, "seconds": 86400.0,
                                                                         "source": "GET /stats/timeseries/interfaceOverlay (last day)"})
                link["tx_bytes"] += float(row.get("TX_BYTES") or 0)
                link["rx_bytes"] += float(row.get("RX_BYTES") or 0)
                link["bw_tx"] = max(link["bw_tx"], float(row.get("MAX_BW_TX") or 0))
                link["bw_rx"] = max(link["bw_rx"], float(row.get("MAX_BW_RX") or 0))
    for link in links.values():
        link["avg_tx_pct"] = _util(link["tx_bytes"], link["seconds"], link["bw_tx"])
        link["avg_rx_pct"] = _util(link["rx_bytes"], link["seconds"], link["bw_rx"])
    return sorted(links.values(), key=lambda link: -max(link["avg_tx_pct"] or 0, link["avg_rx_pct"] or 0))


def _load_status(pct: Optional[float]) -> str:
    """Link load: P95 at or above 80% is amber, at or above 95% red."""
    return "grey" if pct is None else "red" if pct >= 95 else "amber" if pct >= 80 else "green"


def _util(byte_count: float, seconds: float, kbps: float) -> Optional[float]:
    """Percent of the configured bandwidth: bytes x 8 / (seconds x kbps x 1000)."""
    return round(100.0 * byte_count * 8 / (seconds * kbps * 1000), 2) if seconds > 0 and kbps > 0 else None


def compute(bundle: Mapping[str, Any]) -> Dict[str, Any]:
    data, calls, report = bundle["data"], bundle["calls"], bundle["report"]
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
        gaps.insert(0, "Every statistics call returned HTTP 500: the Orchestrator's statistics store is down, so statistics are not shown.")

    inventory = data.get("appliances") or []
    names = {a.get("nePk"): a.get("hostName") or a.get("nePk") for a in inventory}
    now_s = int(bundle["period"].get("now_s") or bundle["period"]["to_ms"] // 1000)
    parts = PARTS.get(report, (report,))
    ctx = {"data": data, "inventory": inventory, "names": names, "metric": metric, "metrics": metrics, "gaps": gaps, "stats_down": stats_down, "now_s": now_s}
    m_total = metric("appliances_total", len(inventory), "appliances", "Appliances in scope")
    if "availability" in parts:
        sections.update(_availability(ctx))
    if "noc" in parts:
        sections.update(_noc(ctx))
    if "capacity" in parts:
        sections.update(_capacity(ctx))
    if "lifecycle" in parts:
        sections.update(_lifecycle(ctx))

    if report == "executive":
        reachable_now = [a for a in inventory if a.get("state") == 1]
        share = _pct(len(reachable_now), len(inventory))
        limits, _ = _limits(data.get("availability_threshold") or {}, "reachability")
        m_now = metric("reachable_now_pct", share, "%", "Appliances reachable at collection time", band(share, limits))
        metric("reachable_now", len(reachable_now), "appliances", "Appliances reachable at collection time")
        sections["exec-fleet"] = {"status": metrics[m_now]["status"], "metrics": [m_total, "reachable_now", m_now],
                                  "table": [{"appliance": a.get("hostName"), "model": a.get("model"), "ecos": a.get("softwareVersion"), "reachable": "yes" if a.get("state") == 1 else "no"}
                                            for a in sorted(inventory, key=lambda a: (a.get("state") == 1, str(a.get("hostName"))))][:40]}
        sections["exec-availability"] = {"status": worst([sections["avail-appliances"]["status"], sections["avail-tunnels"]["status"]]),
                                         "metrics": ["fleet_reach_pct", "overlay_avail_pct", "underlay_avail_pct", "appliances_below_target"]}
        sections["exec-alarms"] = dict(sections["noc-alarms"], table=[])
        sections["exec-licensing"] = dict(sections["life-licences"], table=[])
        sections["exec-software"] = {"status": metrics["ecos_trains"]["status"], "metrics": ["ecos_versions", "ecos_trains", "orchestrator_version"],
                                     "notes": ["Rule: more than one ECOS train in use is amber."]}
        sections["exec-capacity"] = {"status": sections["cap-summary"]["status"], "metrics": sections["cap-summary"]["metrics"]}
        sections["exec-noc"] = {"status": sections["noc-summary"]["status"], "metrics": sections["noc-summary"]["metrics"]}
        sections["exec-lifecycle"] = {"status": sections["life-summary"]["status"], "metrics": sections["life-summary"]["metrics"]}
    sections["data-gaps"] = {"status": "grey" if gaps else "green", "metrics": [], "notes": gaps or ["None: every call returned data."]}

    # An appliance counts as covered when any per-appliance read returned something for it (keyed "<what>:<nePk>", or named inside a result).
    other = json.dumps({k: v for k, v in data.items() if k not in ("appliances", "versions") and ":" not in k})
    answered = sum(1 for ne in names if any(k.endswith(":" + str(ne)) and v for k, v in data.items()) or '"{}"'.format(ne) in other)
    return {"kind": "edgeconnect-report-metrics", "report": report, "orchestrator": bundle["orchestrator"],
            "orchestrator_version": (data.get("versions") or {}).get("current") if isinstance(data.get("versions"), dict) else None,
            "period": bundle["period"], "collected_at": bundle["collected_at"], "bundle_sha256": bundle.get("sha256"),
            "coverage": {"appliances": len(names), "with_data": answered}, "stats_store_down": stats_down,
            "metrics": metrics, "sections": {sid: sections[sid] for sid, _ in SECTIONS[report]}}


def _availability(ctx: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    data, inventory, names, metric, metrics, gaps = ctx["data"], ctx["inventory"], ctx["names"], ctx["metric"], ctx["metrics"], ctx["gaps"]
    sections: Dict[str, Dict[str, Any]] = {}
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
        if pct is None and not ctx["stats_down"]:
            state = next((a.get("state") for a in inventory if a.get("nePk") == ne), None)
            gaps.append("{}: no reachability samples for the month{}.".format(name, " although it is reachable now (check ECOS 9.3.4/9.4.2/9.5.0 or later, and retention)" if state == 1 else ""))
        total_reach, total_samples = total_reach + reach, total_samples + samples
        rows.append({"appliance": name, "nePk": ne, "value": pct, "status": band(pct, limits)})
    fleet = _pct(total_reach, total_samples)
    m_fleet = metric("fleet_reach_pct", fleet, "%", "Fleet appliance reachability", band(fleet, limits))
    below = [r for r in rows if r["status"] in ("amber", "red")]
    m_below = metric("appliances_below_target", len(below) if fleet is not None else None, "appliances", "Appliances below the reachability target")
    m_measured = metric("appliances_measured", sum(1 for r in rows if r["value"] is not None), "appliances", "Appliances with reachability data")
    metric("reach_target_pct", max(limits), "%", "Reachability target")
    rows.sort(key=lambda r: (r["value"] is None, r["value"] if r["value"] is not None else 0))
    sections["avail-appliances"] = {"status": metrics[m_fleet]["status"], "metrics": [m_fleet, m_below, m_measured, "reach_target_pct"],
                                    "table": rows, "chart": {"title": "Lowest appliance reachability, % of the month", "zoom": True,
                                                             "points": [(r["appliance"], r["value"], r["status"]) for r in rows if r["value"] is not None][:25]}}

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
    sections["avail-summary"] = {"status": worst([availability_status, alarm_status]), "metrics": [m_fleet, "overlay_avail_pct", "underlay_avail_pct", "alarms_critical", "appliances_total"]}
    return sections


def _noc(ctx: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    data, inventory, names, metric, gaps, now_s = ctx["data"], ctx["inventory"], ctx["names"], ctx["metric"], ctx["gaps"], ctx["now_s"]
    sections: Dict[str, Dict[str, Any]] = {}
    # Appliance state now.
    counts = {name: 0 for name in STATE_NAMES.values()}
    state_of: Dict[Any, str] = {}
    for a in inventory:
        state_of[a.get("nePk")] = STATE_NAMES.get(a.get("state"), "state {}".format(a.get("state")))
        counts[state_of[a.get("nePk")]] = counts.get(state_of[a.get("nePk")], 0) + 1
    not_normal = len(inventory) - counts["normal"]
    share = _pct(not_normal, len(inventory))
    state_status = "grey" if not inventory else "green" if not not_normal else "red" if share > 10 else "amber"
    paused = set(((data.get("maintenance") or {}).get("pauseOrchestration") or []) if isinstance(data.get("maintenance"), dict) else [])
    sections["noc-appliances"] = {"status": state_status, "metrics": [metric("state_" + name.replace(" ", "_"), counts[name], "appliances", "Appliances " + name)
                                                                      for name in STATE_NAMES.values()],
                                  "table": [{"appliance": names[ne], "state": st, "maintenance": "yes" if ne in paused else ""} for ne, st in sorted(state_of.items(), key=lambda i: str(names[i[0]])) if st != "normal"],
                                  "notes": ["Rule: any appliance not normal is amber; more than 10% is red."]}

    # Active alarms: the list through the read POST, else the GET totals and per-appliance counts.
    sev_counts: Dict[str, Optional[int]] = {"critical": 0, "major": 0, "minor": 0, "warning": 0}
    per_ne: Dict[Any, Dict[str, int]] = {}
    rows: List[Dict[str, Any]] = []
    active = data.get("active_alarms")
    if isinstance(active, list):
        for alarm in active:
            sev = str(alarm.get("severity") or "").lower()
            if sev in sev_counts:
                sev_counts[sev] += 1
                per_ne.setdefault(alarm.get("applianceId"), {}).setdefault(sev, 0)
                per_ne[alarm.get("applianceId")][sev] += 1
            if sev in ("critical", "major") and len(rows) < 15:
                since = alarm.get("timeOccurredInMills")
                rows.append({"appliance": names.get(alarm.get("applianceId"), alarm.get("applianceId")), "severity": sev, "description": str(alarm.get("description") or "")[:160],
                             "since": datetime.fromtimestamp(since / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M") if isinstance(since, (int, float)) else ""})
        source = "POST /alarm/appliance (active)"
    else:
        summary = data.get("alarm_summary") if isinstance(data.get("alarm_summary"), dict) else None
        sev_counts = {sev: summary.get("numOf{}Alarms".format(sev.title())) if summary else None for sev in sev_counts}
        for item in data.get("alarm_counts") or []:
            if isinstance(item, dict) and item.get("applianceId") in names:
                per_ne[item["applianceId"]] = {sev: int(item.get("numOf{}Alarms".format(sev.title())) or 0) for sev in ("critical", "major", "minor", "warning")}
        rows = [{"appliance": names[ne], "critical": c.get("critical", 0), "major": c.get("major", 0), "minor": c.get("minor", 0), "warning": c.get("warning", 0)}
                for ne, c in sorted(per_ne.items(), key=lambda i: (-i[1].get("critical", 0), -i[1].get("major", 0)))][:15]
        source = "GET /alarm/summary and GET /alarm/count/appliance (counts only; the alarm list needs the read POST)"
    alarm_status = "grey" if sev_counts["critical"] is None else "red" if sev_counts["critical"] else "amber" if sev_counts["major"] else "green"
    retention = (data.get("alarm_retention") or {}).get("historical_appliance_alarm", {}).get("retention") if isinstance(data.get("alarm_retention"), dict) else None
    notes = ["Source: " + source + "."]
    if isinstance(retention, (int, float)):
        notes.append("This Orchestrator keeps {:g} days of alarm history.".format(retention / 86400))
    sections["noc-alarms"] = {"status": alarm_status, "notes": notes, "table": rows,
                              "metrics": [metric("active_" + sev, n, "alarms", "Active {} alarms".format(sev)) for sev, n in sev_counts.items()]}

    # Health: share of appliance-hours in good health (POST /health hourly entries; blank hours are not counted).
    health = data.get("health")
    health_ids, health_status, seen = [], "grey", set()
    bad_hours: Dict[Any, int] = {}
    if isinstance(health, dict):
        for window, seconds in (("24h", 86400), ("7d", 7 * 86400)):
            total = good = 0
            for ne, entries in health.items():
                for entry in entries if isinstance(entries, list) and ne in names else []:
                    status = str(entry.get("status") or "").upper()
                    if entry.get("blank") or not status or float(entry.get("time") or 0) < now_s - seconds:
                        continue
                    seen.add(status)
                    total += 1
                    good += status in GOOD_HEALTH
                    if window == "24h" and status not in GOOD_HEALTH:
                        bad_hours[ne] = bad_hours.get(ne, 0) + 1
            pct = _pct(good, total)
            health_ids.append(metric("health_good_{}_pct".format(window), pct, "%", "Appliance-hours in good health, last {}".format(window), band(pct, (95.0, 99.0))))
        health_status = metrics_status(ctx, health_ids[0])
    else:
        gaps.append("Health: POST /health did not run, so hourly health is not shown.")
        health_ids = [metric("health_good_24h_pct", None, "%", "Appliance-hours in good health, last 24h"), metric("health_good_7d_pct", None, "%", "Appliance-hours in good health, last 7d")]
    sections["noc-health"] = {"status": health_status, "metrics": health_ids,
                              "notes": ["Rule: at least 99% of appliance-hours healthy is green, 95% amber, less red. Statuses seen: {}.".format(", ".join(sorted(seen)) or "none")]}

    # Tunnels down now, from the cached tunnel state (one network-wide read each).
    tunnel_ids, tunnel_rows, tunnel_status = [], [], []
    down_per_ne: Dict[Any, int] = {}
    for kind, key in (("physical", "tunnels_physical"), ("bonded", "tunnels_bonded")):
        value = data.get(key)
        if not isinstance(value, dict):
            tunnel_ids += [metric("tunnels_{}_down".format(kind), None, "tunnels", "{} tunnels down".format(kind.title()))]
            continue
        total = down = 0
        for ne, tunnels in value.items():
            for tunnel in (tunnels.values() if isinstance(tunnels, dict) and ne in names else []):
                total += 1
                if not str(tunnel.get("operStatus") or "").lower().startswith("up"):
                    down += 1
                    down_per_ne[ne] = down_per_ne.get(ne, 0) + 1
                    if len(tunnel_rows) < 30:
                        tunnel_rows.append({"appliance": names[ne], "kind": kind, "tunnel": tunnel.get("alias"), "state": tunnel.get("operStatus")})
        share = _pct(down, total)
        tunnel_status.append("grey" if not total else "green" if not down else "red" if share > 10 else "amber")
        tunnel_ids += [metric("tunnels_{}_down".format(kind), down, "tunnels", "{} tunnels down".format(kind.title()), tunnel_status[-1]),
                       metric("tunnels_{}_total".format(kind), total, "tunnels", "{} tunnels".format(kind.title()))]
    sections["noc-tunnels"] = {"status": worst(tunnel_status), "metrics": tunnel_ids, "table": tunnel_rows,
                               "notes": ["Rule: any tunnel not up is amber; more than 10% of tunnels is red. Bonded tunnels are the overlays."]}

    # Sites needing attention: a fixed score so the order is reproducible.
    scored = []
    for ne, name in names.items():
        alarms = per_ne.get(ne, {})
        score = (100 if state_of.get(ne) != "normal" else 0) + 10 * alarms.get("critical", 0) + 3 * alarms.get("major", 0) + 2 * down_per_ne.get(ne, 0) + bad_hours.get(ne, 0)
        if score:
            scored.append({"appliance": name, "state": state_of.get(ne), "critical": alarms.get("critical", 0), "major": alarms.get("major", 0),
                           "tunnels_down": down_per_ne.get(ne, 0), "unhealthy_hours_24h": bad_hours.get(ne, 0), "score": score})
    scored.sort(key=lambda r: -r["score"])
    sections["noc-worst"] = {"status": "green" if not scored else worst([state_status, alarm_status, worst(tunnel_status)]), "table": scored[:10],
                             "metrics": [metric("sites_needing_attention", len(scored), "appliances", "Appliances needing attention")],
                             "notes": ["Score: not normal 100, each critical alarm 10, each major 3, each tunnel down 2, each unhealthy hour 1."]}
    sections["noc-summary"] = {"status": worst([state_status, alarm_status, health_status, worst(tunnel_status)]),
                               "metrics": ["state_unreachable", "active_critical", "active_major", "tunnels_bonded_down", "health_good_24h_pct", "sites_needing_attention"]}
    return sections


def metrics_status(ctx: Dict[str, Any], mid: str) -> str:
    return ctx["metrics"][mid].get("status") or "grey"


def _capacity(ctx: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    data, names, metric, gaps = ctx["data"], ctx["names"], ctx["metric"], ctx["gaps"]
    links = wan_links(data, names)
    rows = []
    for link in links:
        hourly = data.get("hourly:{}:{}".format(link["nePk"], link["interface"]))
        tx, rx = [], []
        for row in hourly if isinstance(hourly, list) else []:
            # Each hourly row carries the configured bandwidth (kbps) at that time.
            for values, key, bw in ((tx, "tx_bytes", "max_bw_tx"), (rx, "rx_bytes", "max_bw_rx")):
                pct = _util(float(row.get(key) or 0), 3600, float(row.get(bw) or 0))
                if pct is not None:
                    values.append(pct)
        p95_tx, p95_rx = _p95(tx), _p95(rx)
        peak = max([v for v in (p95_tx, p95_rx) if v is not None], default=None)
        rows.append({"appliance": names.get(link["nePk"], link["nePk"]), "interface": link["interface"], "label": link["label"],
                     "outbound_mbps": round(link["bw_tx"] / 1000, 1), "inbound_mbps": round(link["bw_rx"] / 1000, 1),
                     "avg_out_pct": link["avg_tx_pct"], "avg_in_pct": link["avg_rx_pct"], "p95_out_pct": p95_tx, "p95_in_pct": p95_rx,
                     "hours": max(len(tx), len(rx)), "status": _load_status(peak)})
    measured = [r for r in rows if r["status"] != "grey"]
    flagged = [r for r in measured if r["status"] in ("amber", "red")]
    worst_p95 = max([max(v for v in (r["p95_out_pct"], r["p95_in_pct"]) if v is not None) for r in measured], default=None)
    status = "grey" if not measured else worst([r["status"] for r in measured])
    rows.sort(key=lambda r: (r["status"] == "grey", -max(r["p95_out_pct"] or 0, r["p95_in_pct"] or 0), -max(r["avg_out_pct"] or 0, r["avg_in_pct"] or 0)))
    if not links:
        gaps.append("Capacity: no WAN interfaces found (POST /stats/aggregate/interface, or GET /stats/timeseries/interfaceOverlay under GET-only).")
    notes = ["P95 of hourly averages over the last {:g} days of the period at most (hourly retention); hourly averages understate short bursts.".format(HOURLY_RETENTION / 86400),
             "Outbound = WAN Tx, inbound = WAN Rx, against the configured bandwidth. Rule: P95 at or above 80% is amber, 95% red.",
             "Links ranked by average utilisation from {}; only the top ones get a P95, the rest stay grey.".format(links[0]["source"] if links else "the interface totals")]
    if len(rows) > 30:
        notes.append("{} more links not shown.".format(len(rows) - 30))
    m_flag = metric("links_flagged", len(flagged) if measured else None, "links", "WAN links at or above 80% P95", status)
    sections = {"cap-links": {"status": status, "metrics": [m_flag], "table": rows[:30], "notes": notes,
                              "chart": {"title": "Highest WAN P95 utilisation, % of configured bandwidth", "zoom": False,
                                        "points": [("{} {}".format(r["appliance"], r["interface"]), max(r["p95_out_pct"] or 0, r["p95_in_pct"] or 0), r["status"]) for r in rows if r["status"] != "grey"][:20]}}}
    sections["cap-summary"] = {"status": status, "metrics": [m_flag, metric("worst_p95_pct", worst_p95, "%", "Highest WAN P95 utilisation", _load_status(worst_p95)),
                                                             metric("links_measured", len(measured), "links", "WAN links with a P95"),
                                                             metric("wan_links", len(links), "links", "WAN links found")]}
    return sections


def _lifecycle(ctx: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    data, inventory, names, metric, gaps, now_s = ctx["data"], ctx["inventory"], ctx["names"], ctx["metric"], ctx["gaps"], ctx["now_s"]
    sections: Dict[str, Dict[str, Any]] = {}
    groups: Dict[Tuple[str, str], int] = {}
    for a in inventory:
        key = (str(a.get("model") or "unknown"), str(a.get("softwareVersion") or "unknown"))
        groups[key] = groups.get(key, 0) + 1
    versions = {v for _, v in groups}
    trains = {".".join(map(str, _version(v)[:2])) or v for v in versions}
    sw_status = "grey" if not inventory else "green" if len(trains) <= 1 else "amber"
    orch_version = (data.get("versions") or {}).get("current") if isinstance(data.get("versions"), dict) else None
    sections["life-inventory"] = {"status": sw_status, "table": [{"model": m, "ecos": v, "appliances": n} for (m, v), n in sorted(groups.items(), key=lambda i: (-i[1], i[0]))],
                                  "metrics": [metric("ecos_versions", len(versions), "versions", "Distinct ECOS builds"),
                                              metric("ecos_trains", len(trains), "trains", "Distinct ECOS trains (major.minor)", sw_status),
                                              metric("orchestrator_version", orch_version, "", "Orchestrator release")],
                                  "notes": ["Rule: more than one ECOS train in use is amber."]}

    # Licences: the Orchestrator's, and each portal-licensed appliance's expiry (epoch ms) where the portal gives one.
    lic = data.get("gms_license") if isinstance(data.get("gms_license"), dict) else None
    days = lic.get("daysToExpiration") if lic else None
    portal = data.get("portal_appliances")
    expiring, lic_rows = {30: 0, 90: 0}, []
    for item in (portal.get("data") or []) if isinstance(portal, dict) else []:
        expiry = item.get("expirationDate") if isinstance(item, dict) else None
        if isinstance(expiry, (int, float)) and item.get("applianceId") in names:
            left = int((expiry / 1000 - now_s) // 86400)
            for limit in expiring:
                expiring[limit] += left <= limit
            if left <= 90:
                lic_rows.append({"appliance": names[item["applianceId"]], "days_left": left})
    have = isinstance(days, int) or isinstance(portal, dict)
    worst_days = min([d for d in [days] + [r["days_left"] for r in lic_rows] if isinstance(d, int)], default=None)
    lic_status = "grey" if not have else "red" if worst_days is not None and worst_days <= 30 else "amber" if worst_days is not None and worst_days <= 90 else "green"
    sections["life-licences"] = {"status": lic_status, "table": sorted(lic_rows, key=lambda r: r["days_left"]),
                                 "metrics": [metric("license_days_left", days, "days", "Days until the Orchestrator licence expires", band(days, (30, 90)) if isinstance(days, int) else None),
                                             metric("license_used", lic.get("usedAppliances") if lic else None, "appliances", "Licensed appliances in use"),
                                             metric("licences_expiring_90", expiring[90] if isinstance(portal, dict) else None, "appliances", "Appliance licences expiring within 90 days"),
                                             metric("licences_expiring_30", expiring[30] if isinstance(portal, dict) else None, "appliances", "Appliance licences expiring within 30 days")],
                                 "notes": ["Rule: 30 days or less red, 90 days or less amber."]}

    # Backups: the newest appliance backup each appliance has on the Orchestrator.
    backup_rows, stale, read = [], 0, 0
    for ne, name in names.items():
        history = data.get("backup:" + str(ne))
        if history is None:
            continue
        read += 1
        times = [float(b.get("backupTime")) for b in history if isinstance(b, dict) and isinstance(b.get("backupTime"), (int, float))] if isinstance(history, list) else []
        age = int((now_s - max(times)) // 86400) if times else None
        stale += age is None or age > 30
        backup_rows.append({"appliance": name, "last_backup": datetime.fromtimestamp(max(times), timezone.utc).strftime("%Y-%m-%d") if times else "none", "days_ago": age})
    backup_status = "grey" if not read else "amber" if stale else "green"
    sections["life-backups"] = {"status": backup_status, "table": sorted(backup_rows, key=lambda r: -(r["days_ago"] if r["days_ago"] is not None else 10 ** 6))[:30],
                                "metrics": [metric("backups_stale", stale if read else None, "appliances", "Appliances without a backup in 30 days", backup_status),
                                            metric("backups_read", read, "appliances", "Appliances whose backup history was read")],
                                "notes": ["Rule: an appliance with no backup in the last 30 days is amber."]}

    # Advisories: a dated, hand-kept list (there is no API); Orchestrator entries are checked against its release.
    hits = []
    for advisory in ADVISORIES:
        targets = [("Orchestrator", orch_version)] if advisory["product"] == "orchestrator" else [(names.get(a.get("nePk")), a.get("softwareVersion")) for a in inventory]
        for target, version in targets:
            why = advisory_hit(version, advisory)
            if why:
                hits.append({"target": target, "version": version, "advisory": advisory["id"], "why": why, "cves": ", ".join(advisory["cves"])})
    checked = bool(orch_version) or bool(inventory)
    adv_status = "grey" if not checked else "red" if hits else "green"
    sections["life-advisories"] = {"status": adv_status, "table": hits[:30],
                                   "metrics": [metric("advisory_hits", len(hits) if checked else None, "findings", "Advisory findings", adv_status),
                                               metric("advisories_checked", len(ADVISORIES), "advisories", "Advisories in the list")],
                                   "notes": ["Advisory list as of {}; there is no API for advisories, so check the HPE security portal for newer ones.".format(ADVISORIES_AS_OF)]
                                   + ["{}: {}. {}".format(a["id"], a["title"], a["url"]) for a in ADVISORIES]}
    sections["life-eol"] = {"status": "grey", "metrics": [], "notes": ["No API gives hardware end-of-life dates; not supplied."]}
    sections["life-summary"] = {"status": worst([sw_status, lic_status, backup_status, adv_status]),
                                "metrics": ["advisory_hits", "licences_expiring_90", "license_days_left", "backups_stale", "ecos_trains"]}
    return sections


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


def _chart(chart: Mapping[str, Any]) -> str:
    points, title = chart.get("points") or [], str(chart.get("title") or "")
    if not points:
        return ""
    values = [p[1] for p in points]
    # Availability zooms so 99.9 and 100 can be told apart; utilisation starts at 0 and may pass 100.
    floor, ceiling = (min(90.0, min(values)), 100.0) if chart.get("zoom") else (0.0, max(100.0, max(values)))
    width, row = 640, 18
    bars = []
    for i, (label, value) in enumerate((p[0], p[1]) for p in points):
        length = 0 if value <= floor else (value - floor) / (ceiling - floor) * (width - 260)
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
        chart = _chart(sec.get("chart") or {})
        parts.append('<section data-section-id="{0}"><h2>{1}</h2><div class="status {2}">Status: {3}</div>{4}<div class="kpis">{5}</div>{6}{7}{8}</section>'.format(
            sid, html.escape(titles[sid]), sec["status"], sec["status"].title(), "<p>{}</p>".format(text) if text else "", kpis, chart, _table(sec.get("table") or []), notes))
    banner = '<div class="banner" data-section-id="stats-store-down">Statistics store down: every statistics call returned HTTP 500, so availability numbers are missing.</div>' if metrics.get("stats_store_down") else ""
    coverage = metrics.get("coverage") or {}
    now = metrics["period"].get("now_s")
    as_of = datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if now else metrics["collected_at"]
    period = {"noc": "last 24 hours and 7 days to " + as_of, "lifecycle": "as of " + as_of}.get(metrics["report"], metrics["period"]["month"])
    return PAGE.substitute(
        title=html.escape("{}, {}".format(TITLES[metrics["report"]], period)),
        subtitle=html.escape("Orchestrator {} · {}".format(metrics["orchestrator"], period)),
        banner=banner, sections="\n".join(parts), orchestrator=html.escape(str(metrics["orchestrator"])), version=html.escape(str(metrics.get("orchestrator_version"))),
        collected=html.escape(str(metrics["collected_at"])), period=html.escape(period),
        coverage=html.escape("{} of {} appliances returned data in a per-appliance read".format(coverage.get("with_data"), coverage.get("appliances"))),
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
    p.add_argument("--top", type=int, default=20, help="capacity: WAN links that get an hourly P95 read, busiest first (default 20)")
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
            bundle = collect(server, args.orchestrator, args.report, args.month, [a.strip() for a in args.appliances.split(",")] if args.appliances else None, top=args.top)
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
