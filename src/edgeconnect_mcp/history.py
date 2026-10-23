"""Local archive of appliance alarms, so reports keep them past the Orchestrator's own 7 days of alarm history.

`edgeconnect-mcp report store` re-reads the 7 days the Orchestrator still has and keeps them here, one JSON object per line:

    <root>/<nickname>/alarms/YYYY-MM.jsonl        appliance alarms by occurrence time, the latest version of each id
    <root>/<nickname>/alarm_counts/YYYY-MM.jsonl  daily alarm counts per appliance, when the alarm list cannot be read (get_only)
    <root>/<nickname>/coverage.json               the time spans (epoch ms) each kind covers

Only alarms are kept: stats are read live, and the audit log is not stored (the owner's decision, 2026-10-23: a busy
Orchestrator logs thousands of entries an hour; a full audit trail belongs in a remote log receiver). Nothing here is
scheduled; run the command from cron or launchd.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

DEFAULT_ROOT = Path.home() / ".edgeconnect-mcp" / "history"
CAP = 10000  # alarms POST /alarm/appliance returns at most (maxAlarms); a page that full is split, never trusted
DAY_MS = 86400000
MIN_WINDOW_MS = 60000  # a one-minute page that is still full is reported, not split further
ALARM_LOOKBACK_MS = 7 * DAY_MS  # the Orchestrator keeps 7 days of alarm history: every pull re-reads it, so clear times catch up
TIME_FIELD = {"alarms": "timeOccurredInMills", "alarm_counts": "day_ms"}

Call = Callable[[str, Dict[str, Any], Any], Optional[Any]]  # (path, query, body) -> rows, or None when the read failed


def paged(call: Call, path: str, start_ms: int, end_ms: int, query: Callable[[int, int], Dict[str, Any]], body: Any = None,
          cap: int = CAP) -> Tuple[List[Any], List[Tuple[int, int]], List[str]]:
    """Rows for [start_ms, end_ms], read a day at a time; a page that comes back with `cap` rows is split in two until it fits.

    Returns the rows, the windows that could not be read (not covered) and notes about pages still full at one minute."""
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
            if got is None:
                failed.append((a, b))
            continue
        if len(got) >= cap:
            if b - a > MIN_WINDOW_MS:
                mid = (a + b) // 2
                stack += [(mid, b), (a, mid)]
                continue
            notes.append("{}: {} rows within one minute at {}; some may be missing".format(path, len(got), _iso(a)))
        rows += got
    return rows, failed, notes


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
        """Store records by month, one line each; a record with an id already stored replaces it (alarms gain a clear time)."""
        field, new = TIME_FIELD[kind], 0
        by_month: Dict[str, List[Dict[str, Any]]] = {}
        for record in records:
            if isinstance(record, dict) and isinstance(record.get(field), (int, float)) and record.get("id") is not None:
                by_month.setdefault(_month(record[field]), []).append(record)
        for month, items in by_month.items():
            path = self.dir / kind / (month + ".jsonl")
            stored = {str(r["id"]): r for r in self._read(path)}
            new += len({str(r["id"]) for r in items} - set(stored))
            stored.update({str(r["id"]): r for r in items})
            _private_write(path, "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in sorted(stored.values(), key=lambda r: r[field])))
        return new

    def load(self, kind: str, start_ms: int, end_ms: int) -> List[Dict[str, Any]]:
        field, out = TIME_FIELD[kind], []
        for path in sorted((self.dir / kind).glob("*.jsonl")) if (self.dir / kind).is_dir() else []:
            if _month(start_ms) <= path.stem <= _month(end_ms):
                out += [r for r in self._read(path) if start_ms <= r.get(field, -1) <= end_ms]
        return out

    @staticmethod
    def _read(path: Path) -> List[Dict[str, Any]]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []


def _private_write(path: Path, text: str) -> None:
    """Only the owner can read the archive (it names appliances and sites), like the MCP audit log: folders 0700, files 0600."""
    for folder in reversed([path.parent] + [p for p in path.parent.parents if not p.exists()]):
        folder.mkdir(mode=0o700, exist_ok=True)
    path.touch(mode=0o600, exist_ok=True)
    os.chmod(path, 0o600)
    path.write_text(text, encoding="utf-8")


def pull(call: Call, history: History, nepks: List[str], read_posts: bool, now_ms: int) -> Dict[str, Any]:
    """Store the alarms the Orchestrator still has (7 days); under get_only, daily counts for the days not stored yet."""
    cov = history.coverage()
    if read_posts:
        # The whole 7 days is re-read on every run, so alarms stored while open gain their clear time.
        kind, span = "alarms", [now_ms - ALARM_LOOKBACK_MS, now_ms]
        records, failed, notes = paged(call, "/alarm/appliance", span[0], span[1], lambda x, y: {"view": "all", "from": x, "to": y, "maxAlarms": CAP},
                                       {"nePks": nepks}) if nepks else ([], [], [])
    else:
        # GET-only: one count read per appliance and day, so only the days not stored yet, plus the last stored (still open) day.
        kind = "alarm_counts"
        last = max((b for _, b in cov.get(kind, [])), default=None)
        span = [max(now_ms - ALARM_LOOKBACK_MS, (last - DAY_MS) if last is not None else 0), now_ms]
        records, failed, notes = _daily_counts(call, nepks, span[0], span[1]), [], []
    new = history.write(kind, records)
    history.add_coverage(kind, missing([list(f) for f in failed], span[0], span[1]))  # the span minus the windows that failed
    return {kind: {"read": len(records), "new": new, "from": span[0], "to": now_ms, "failed": [[a, b] for a, b in failed], "notes": notes}}


def _daily_counts(call: Call, nepks: List[str], start_ms: int, end_ms: int) -> List[Dict[str, Any]]:
    """GET-only fallback: per appliance and UTC day, the alarm counts GET /health/alarmPeriodSummary gives (no alarm list)."""
    out = []
    day = start_ms - start_ms % DAY_MS
    while day < end_ms:
        for ne in nepks:
            got = call("/health/alarmPeriodSummary", {"applianceId": ne, "from": day, "to": min(day + DAY_MS, end_ms)}, None)
            if isinstance(got, dict) and isinstance(got.get("alarmCountsInPeriod"), dict):
                out.append({"id": "{}:{}".format(_iso(day)[:10], ne), "nePk": ne, "day_ms": day, "counts": got["alarmCountsInPeriod"]})
        day += DAY_MS
    return out
