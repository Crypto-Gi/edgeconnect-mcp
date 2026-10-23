"""Local archive of appliance alarms, so reports keep them past the Orchestrator's own 7 days of alarm history.

`edgeconnect-mcp report store` re-reads the 7 days the Orchestrator still has and keeps them here, one JSON object per line:

    <root>/<nickname>/alarms/YYYY-MM.jsonl   appliance alarms by occurrence time, the latest version of each id
    <root>/<nickname>/coverage.json          the time spans (epoch ms) the archive covers

Only alarms are kept: stats are read live, and the audit log is not stored (the owner's decision, 2026-10-23: a busy
Orchestrator logs thousands of entries an hour; a full audit trail belongs in a remote log receiver). Nothing here is
scheduled; run the command from cron or launchd.
"""
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

DEFAULT_ROOT = Path.home() / ".edgeconnect-mcp" / "history"
CAP = 10000  # alarms asked for per read (maxAlarms); a page that full is split, never trusted
DAY_MS = 86400000
MIN_WINDOW_MS = 60000  # a one-minute page that is still full is reported and left uncovered, not split further
ALARM_LOOKBACK_MS = 7 * DAY_MS  # the Orchestrator keeps 7 days of alarm history: every pull re-reads it, so clear times catch up

Call = Callable[[str, Dict[str, Any], Any], Optional[Any]]  # (path, query, body) -> rows, or None when the read failed


def paged(call: Call, path: str, start_ms: int, end_ms: int, query: Callable[[int, int], Dict[str, Any]], body: Any = None,
          cap: int = CAP) -> Tuple[List[Any], List[Tuple[int, int]], List[str]]:
    """Rows for [start_ms, end_ms], read a day at a time; a page that comes back with `cap` rows is split in two until it fits.

    Returns the rows, the windows not read completely (a failed read, an unexpected reply, or a one-minute page still full;
    never counted as covered) and notes."""
    rows: List[Any] = []
    failed: List[Tuple[int, int]] = []
    notes: List[str] = []
    stack = []
    t = start_ms
    while t < end_ms:
        stack.append((t, min(t + DAY_MS, end_ms)))
        t += DAY_MS
    stack.reverse()
    while stack:
        a, b = stack.pop()
        got = call(path, query(a, b), body)
        if not isinstance(got, list):
            failed.append((a, b))
            continue
        if len(got) >= cap:
            if b - a > MIN_WINDOW_MS:
                mid = (a + b) // 2
                stack += [(mid, b), (a, mid)]
                continue
            failed.append((a, b))
            notes.append("{}: {} rows within one minute at {}; some may be missing".format(path, len(got), _iso(a)))
        rows += got
    return rows, failed, notes


def read_alarms(call: Call, nepks: List[str], read_posts: bool, start_ms: int, end_ms: int) -> Tuple[List[Dict[str, Any]], List[Tuple[int, int]], List[str], str]:
    """Alarms raised in [start_ms, end_ms] plus every alarm open now, for these appliances.

    With the read POSTs: POST /alarm/appliance (view=all by time, and view=active so alarms raised long before are not missed).
    If the key refuses that POST, or the Orchestrator is GET-only: the correlated alarm list, GET /alarm/correlatedAlarms
    (view=closed by time, which carries no clear time, and view=active). It is empty when alarm correlation is off."""
    if not nepks:
        return [], [], [], "none"
    if read_posts:
        rows, failed, notes = paged(call, "/alarm/appliance", start_ms, end_ms, lambda a, b: {"view": "all", "from": a, "to": b, "maxAlarms": CAP}, {"nePks": nepks})
        active = call("/alarm/appliance", {"view": "active", "maxAlarms": CAP}, {"nePks": nepks})
        if isinstance(active, list) or not failed:
            if not isinstance(active, list):
                notes.append("the alarms open now (view=active) could not be read, so alarms raised before the period and still open may be missing")
            return _for(nepks, rows + (active if isinstance(active, list) else [])), failed, notes, "POST /alarm/appliance"
        notes.append("POST /alarm/appliance was refused, so the correlated alarm list (GET) was used")
    rows, failed, more = paged(call, "/alarm/correlatedAlarms", start_ms, end_ms, lambda a, b: {"view": "closed", "from": a, "to": b, "maxAlarms": CAP})
    active = call("/alarm/correlatedAlarms", {"view": "active", "maxAlarms": CAP}, None)
    closed = [dict(r, closed=True) for r in rows if isinstance(r, dict)]
    still_open = [dict(r, closed=False) for r in active if isinstance(r, dict)] if isinstance(active, list) else []
    if not isinstance(active, list):
        failed.append((start_ms, end_ms))
    out = []
    rows = closed + still_open
    for row in rows:
        if isinstance(row.get("clearedTime"), (int, float)) and not row.get("clearedTimeInMills"):
            row = dict(row, clearedTimeInMills=row["clearedTime"])
        out.append(row)
    return _for(nepks, out), failed, (notes if read_posts else []) + more, "GET /alarm/correlatedAlarms"


def _for(nepks: List[str], rows: List[Any]) -> List[Dict[str, Any]]:
    wanted = set(nepks)
    return [r for r in rows if isinstance(r, dict) and r.get("applianceId") in wanted]


def merge(spans: List[List[int]]) -> List[List[int]]:
    out: List[List[int]] = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1] + 1:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def missing(spans: List[List[int]], start_ms: int, end_ms: int) -> List[List[int]]:
    """Parts of [start_ms, end_ms] the spans do not cover."""
    gaps, t = [], start_ms
    for a, b in merge(spans):
        if b < t or a > end_ms:
            continue
        if a > t:
            gaps.append([t, min(a, end_ms)])
        t = max(t, b)
    if t < end_ms:
        gaps.append([t, end_ms])
    return gaps


def _iso(ms: float) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _month(ms: float) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m")


class History:
    def __init__(self, root: Path, nickname: str) -> None:
        self.dir = Path(root).expanduser() / nickname

    def coverage(self) -> Dict[str, List[List[int]]]:
        path = self.dir / "coverage.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}

    def add_coverage(self, kind: str, spans: List[List[int]]) -> None:
        cov = self.coverage()
        cov[kind] = merge(cov.get(kind, []) + [list(s) for s in spans])
        _private_write(self.dir / "coverage.json", json.dumps(cov, indent=1) + "\n")

    def write(self, kind: str, records: List[Dict[str, Any]]) -> int:
        """Store alarms by month, one line each; one already stored with that id is replaced (it gains its clear time)."""
        new = 0
        by_month: Dict[str, List[Dict[str, Any]]] = {}
        for record in records:
            if isinstance(record, dict) and isinstance(record.get("timeOccurredInMills"), (int, float)) and record.get("id") is not None:
                by_month.setdefault(_month(record["timeOccurredInMills"]), []).append(record)
        for month, items in by_month.items():
            path = self.dir / kind / (month + ".jsonl")
            stored = {str(r["id"]): r for r in self._read(path)}
            new += len({str(r["id"]) for r in items} - set(stored))
            stored.update({str(r["id"]): r for r in items})
            _private_write(path, "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in sorted(stored.values(), key=lambda r: r["timeOccurredInMills"])))
        return new

    def load(self, kind: str, start_ms: int, end_ms: int) -> List[Dict[str, Any]]:
        out = []
        for path in sorted((self.dir / kind).glob("*.jsonl")) if (self.dir / kind).is_dir() else []:
            if _month(start_ms) <= path.stem <= _month(end_ms):
                out += [r for r in self._read(path) if start_ms <= r.get("timeOccurredInMills", -1) <= end_ms]
        return out

    @staticmethod
    def _read(path: Path) -> List[Dict[str, Any]]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []


def _private_write(path: Path, text: str) -> None:
    """Owner-only (folders 0700, files 0600, like the MCP audit log), and atomic: a temporary file in the same folder replaces
    the old one, so an interrupted run never leaves a month file cut short."""
    for folder in reversed([path.parent] + [p for p in path.parent.parents if not p.exists()]):
        folder.mkdir(mode=0o700, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix="." + path.name, suffix=".tmp")  # mkstemp creates it 0600
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())  # on disk before it replaces the old file, so a power cut cannot leave it empty
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def pull(call: Call, history: History, nepks: List[str], read_posts: bool, now_ms: int) -> Dict[str, Any]:
    """Store the alarms the Orchestrator still has: the whole 7 days, re-read every run, so alarms stored while open gain their clear time."""
    if not nepks:
        raise ValueError("no appliances read from the Orchestrator, so nothing was stored")
    span = [now_ms - ALARM_LOOKBACK_MS, now_ms]
    records, failed, notes, source = read_alarms(call, nepks, read_posts, span[0], span[1])
    new = history.write("alarms", records)
    history.add_coverage("alarms", missing([list(f) for f in failed], span[0], span[1]))  # the span minus what was not read
    return {"alarms": {"read": len(records), "new": new, "from": span[0], "to": now_ms, "failed": [[a, b] for a, b in failed], "notes": notes, "source": source}}
