"""Audit trail: one record per tool call, written to a JSON-lines file and optionally to syslog and SQLite.

Records never hold secrets: queries and write bodies are redacted before they get here, and a body holds the
<REDACTED:...> tokens the client sent back, not the values behind them.
"""
import json
import logging
import logging.handlers
import os
import select
import socket
import sqlite3
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlsplit

from .errors import ConfigurationError

SYSLOG_MAX = 8000  # many receivers cut longer messages, so a large body goes to the file and SQLite only
_COLUMNS = ("ts", "day", "session", "id", "client", "tool", "orchestrator", "method", "path", "action", "phase", "outcome", "error")


class AuditTrail:
    def __init__(self, path: Optional[str] = None, syslog: Optional[str] = None, sqlite: Optional[str] = None,
                 log: Callable[[str], None] = lambda line: print(line, file=sys.stderr)) -> None:
        self.log = log
        self._lock = threading.Lock()
        self._file = _open_private(path, "a") if path else None
        self._syslog_target = syslog
        self._syslog = _syslog_handler(syslog) if syslog else None
        self._db = _open_sqlite(sqlite) if sqlite else None

    def write(self, record: Dict[str, Any]) -> None:
        line = json.dumps(record, ensure_ascii=True, default=str)
        with self._lock:
            for name, sink in (("file", self._write_file), ("sqlite", self._write_sqlite), ("syslog", self._write_syslog)):
                try:
                    sink(record, line)
                except Exception as exc:  # a broken log sink must not break the tool call; say so on stderr instead
                    self.log("edgeconnect-mcp audit {} failed: {}".format(name, type(exc).__name__))

    def _write_file(self, record: Dict[str, Any], line: str) -> None:
        if self._file:
            self._file.write(line + "\n")
            self._file.flush()

    def _write_sqlite(self, record: Dict[str, Any], line: str) -> None:
        if self._db:
            self._db.execute("INSERT INTO audit ({}, record) VALUES ({})".format(", ".join(_COLUMNS), ", ".join("?" * (len(_COLUMNS) + 1))),
                             [None if record.get(c) is None else str(record.get(c)) for c in _COLUMNS] + [line])
            self._db.commit()

    def _write_syslog(self, record: Dict[str, Any], line: str) -> None:
        if self._syslog:
            if len(line) > SYSLOG_MAX:
                line = json.dumps(dict({k: v for k, v in record.items() if k != "body"}, body_omitted=True), ensure_ascii=True, default=str)
            record_ = logging.LogRecord("edgeconnect-mcp", logging.INFO, "", 0, "edgeconnect-mcp: " + line, None, None)
            try:
                if self._syslog.socktype == socket.SOCK_STREAM and _peer_closed(self._syslog.socket):
                    raise OSError("syslog server closed the connection")  # a send would succeed and the record be lost
                self._syslog.emit(record_)
            except OSError:
                # SysLogHandler never reconnects a dropped TCP connection, so build a new handler and retry once. If the
                # server is still down this raises, the old handler stays, and the next record tries again.
                try:
                    fresh = _syslog_handler(self._syslog_target)  # type: ignore[arg-type]
                except ConfigurationError as exc:
                    raise OSError(str(exc))
                self._syslog.close()
                self._syslog = fresh
                self._syslog.emit(record_)

    def flush(self) -> None:
        if self._file:
            self._file.flush()

    def close(self) -> None:
        with self._lock:
            for sink in (self._file, self._db, self._syslog):
                if sink:
                    sink.close()


def _open_private(path: str, mode: str) -> Any:
    target = Path(path).expanduser()
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(str(target), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    os.chmod(str(target), 0o600)  # tighten a file created earlier with looser permissions
    return os.fdopen(descriptor, mode, encoding="utf-8")


def _open_sqlite(path: str) -> sqlite3.Connection:
    _open_private(path, "a").close()  # create it 0600 before SQLite opens it
    db = sqlite3.connect(str(Path(path).expanduser()), check_same_thread=False)  # every use is under AuditTrail._lock
    db.execute("CREATE TABLE IF NOT EXISTS audit ({}, record TEXT NOT NULL)".format(", ".join(c + " TEXT" for c in _COLUMNS)))
    db.execute("CREATE INDEX IF NOT EXISTS audit_ts ON audit (ts)")
    db.commit()
    return db


def _peer_closed(sock: socket.socket) -> bool:
    """A syslog server never sends, so a readable TCP socket means it closed or reset the connection."""
    try:
        readable, _, _ = select.select([sock], [], [], 0)
        return bool(readable) and sock.recv(1, socket.MSG_PEEK) == b""
    except (OSError, ValueError):
        return True


class _SysLogHandler(logging.handlers.SysLogHandler):
    def close(self) -> None:
        # A handler whose connect failed has no socket, yet logging still closes it at exit and printed a traceback.
        if getattr(self, "socket", None) is None:
            return logging.Handler.close(self)
        super().close()


def _raise(record: logging.LogRecord) -> None:
    raise OSError("syslog send failed")


def _syslog_handler(target: str) -> logging.handlers.SysLogHandler:
    """udp://host:514, tcp://host:514, or a local socket such as /dev/log (Linux) or /var/run/syslog (macOS)."""
    if target.startswith("/"):
        address: Any = target
        socktype = None
    else:
        parts = urlsplit(target)
        if parts.scheme not in ("udp", "tcp") or not parts.hostname:
            raise ConfigurationError("mcp_audit_syslog must be udp://host:port, tcp://host:port or a local socket path, not {!r}".format(target))
        address = (parts.hostname, parts.port or 514)
        socktype = socket.SOCK_STREAM if parts.scheme == "tcp" else socket.SOCK_DGRAM
    try:
        handler = _SysLogHandler(address=address, facility=logging.handlers.SysLogHandler.LOG_AUTHPRIV, socktype=socktype)
    except OSError as exc:
        raise ConfigurationError("mcp_audit_syslog {}: cannot connect ({})".format(target, exc))
    handler.handleError = _raise  # type: ignore[assignment]  # so AuditTrail.write sees and reports the failure
    if socktype == socket.SOCK_STREAM:
        handler.append_nul = False
        handler.setFormatter(logging.Formatter("%(message)s\n"))  # TCP syslog needs a record separator
    return handler
