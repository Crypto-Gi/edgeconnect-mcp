"""Local HTTP transport (MCP streamable HTTP, single JSON responses) for use behind an HTTPS reverse proxy.

It listens on 127.0.0.1 unless mcp_http_listen says otherwise (a container sets 0.0.0.0, with Docker publishing the
port to the host's 127.0.0.1 or a private network). Remote clients come through a proxy (Caddy, nginx) that
terminates HTTPS and appends X-Forwarded-For; that header is believed only from mcp_http_trusted_proxies, and the
client it names must be in mcp_http_allowed_clients. Every request needs the bearer token from .env, and every request
is checked on its own: there is no session state to hijack. Requests run in parallel threads, at most MAX_CONCURRENT
at once; a write confirmation code only works for the client address it was issued to.
Modern (2026-07-28) requests must also mirror their version, method and tool name in the MCP-Protocol-Version,
Mcp-Method and Mcp-Name headers; legacy (initialize-based) requests are served as before.
"""
import base64
import binascii
import hmac
import ipaddress
import json
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Mapping, Optional

from .errors import ConfigurationError
from .server import HEADER_MISMATCH, INVALID_PARAMS, META, METHOD_NOT_FOUND, MODERN_VERSIONS, UNSUPPORTED_VERSION

MAX_BODY = 2 * 1024 * 1024
MAX_CONCURRENT = 8  # requests served at once; more get 503 so a flood can't exhaust threads or the Orchestrator
MIN_TOKEN = 32
DEFAULT_ALLOWED_CLIENTS = DEFAULT_TRUSTED_PROXIES = "127.0.0.1,::1"
DEFAULT_LISTEN = "127.0.0.1"
TOKEN_HINT = "generate one with: python3 -c 'import secrets; print(secrets.token_urlsafe(32))'"


def http_settings(settings: Mapping[str, str], dotenv: Optional[str]) -> Dict[str, Any]:
    token = (settings.get("mcp_http_token") or "").strip()
    read_token = (settings.get("mcp_http_read_token") or "").strip()
    if len(token) < MIN_TOKEN or (read_token and len(read_token) < MIN_TOKEN):
        raise ConfigurationError("HTTP mode needs mcp_http_token (and mcp_http_read_token, if set) of at least {} characters in .env; {}".format(MIN_TOKEN, TOKEN_HINT))
    if read_token == token:
        raise ConfigurationError("mcp_http_read_token must differ from mcp_http_token")
    networks = _networks(settings, "mcp_http_allowed_clients", DEFAULT_ALLOWED_CLIENTS)
    proxies = _networks(settings, "mcp_http_trusted_proxies", DEFAULT_TRUSTED_PROXIES)
    host = (settings.get("mcp_http_listen") or DEFAULT_LISTEN).strip()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        raise ConfigurationError("mcp_http_listen must be an IP address such as 127.0.0.1 or 0.0.0.0, not {!r}".format(host))
    if dotenv and os.stat(dotenv).st_mode & 0o077:
        raise ConfigurationError("{0} is readable by other users; run chmod 600 {0} before using HTTP mode".format(dotenv))
    origins = {part.strip().rstrip("/").lower() for part in (settings.get("mcp_http_allowed_origins") or "").split(",") if part.strip()}
    return {"token": token, "read_token": read_token or None, "networks": networks, "origins": origins, "host": host, "proxies": proxies}


def _networks(settings: Mapping[str, str], key: str, default: str) -> list:
    try:
        return [ipaddress.ip_network(part.strip(), strict=False) for part in (settings.get(key) or default).split(",") if part.strip()]
    except ValueError as exc:
        raise ConfigurationError("{}: {}".format(key, exc))


def _meta_version(message: Mapping[str, Any]) -> Any:
    params = message.get("params") if isinstance(message.get("params"), dict) else {}
    return (params.get("_meta") if isinstance(params.get("_meta"), dict) else {}).get(META + "protocolVersion")


def _is_modern(headers: Any, message: Mapping[str, Any]) -> bool:
    return _meta_version(message) is not None or headers.get("MCP-Protocol-Version") in MODERN_VERSIONS


def _header_mismatch(headers: Any, message: Mapping[str, Any]) -> Optional[str]:
    # The body is what runs, so headers a proxy might route or filter on must agree with it.
    if "id" not in message or not _is_modern(headers, message):
        return None  # notifications and legacy requests have no mirrored headers to check
    params = message.get("params") if isinstance(message.get("params"), dict) else {}
    expected = [("MCP-Protocol-Version", _meta_version(message)), ("Mcp-Method", message.get("method"))]
    if message.get("method") in ("tools/call", "resources/read", "prompts/get"):
        expected.append(("Mcp-Name", params.get("name", params.get("uri"))))
    for name, value in expected:
        given = headers.get(name)
        if name == "Mcp-Name" and given and given.startswith("=?base64?") and given.endswith("?="):
            try:
                given = base64.b64decode(given[9:-2], validate=True).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError):
                return "Mcp-Name header is not valid base64"
        if given is None or given != value:
            return "Header mismatch: {} header {!r} does not match body value {!r}".format(name, given, value)
    return None


def make_http_server(server: Any, port: int, token: str, read_token: Optional[str], networks: Any, origins: Any, log: Callable[[str], None],
                     host: str = DEFAULT_LISTEN, proxies: Any = None) -> ThreadingHTTPServer:
    if proxies is None:
        proxies = _networks({}, "", DEFAULT_TRUSTED_PROXIES)
    slots = threading.BoundedSemaphore(MAX_CONCURRENT)

    class Handler(BaseHTTPRequestHandler):
        server_version = "edgeconnect-mcp"
        sys_version = ""
        timeout = 30  # a stalled client can't hold its thread for longer

        def do_POST(self) -> None:
            if not slots.acquire(blocking=False):
                return self._reply(503, {"error": "server busy, retry shortly"}, {"Retry-After": "2"})
            try:
                self._post()
            finally:
                slots.release()

        def _post(self) -> None:
            if self.path.split("?", 1)[0] != "/mcp":
                return self._reply(404, {"error": "not found"})
            origin = self.headers.get("Origin")
            if origin and origin.rstrip("/").lower() not in origins:
                return self._refuse_audited(403, "origin not allowed", "origin {!r} not allowed".format(origin[:100]))  # a web page in a browser
            client = self._client()
            if client is None or not any(client in network for network in networks):
                return self._refuse_audited(403, "client address {} not allowed; see mcp_http_allowed_clients".format(client))
            auth = self.headers.get("Authorization") or ""
            given = (auth[7:].strip() if auth[:7].lower() == "bearer " else "").encode()
            full = hmac.compare_digest(given, token.encode())
            read = read_token is not None and hmac.compare_digest(given, read_token.encode())
            if not (full or read):
                return self._refuse_audited(401, "missing or wrong access token", headers={"WWW-Authenticate": "Bearer"})
            if self.headers.get("Transfer-Encoding"):
                return self._reply(411, {"error": "send a Content-Length body, not chunked"})
            if (self.headers.get("Content-Type") or "").split(";")[0].strip().lower() != "application/json":
                return self._reply(415, {"error": "Content-Type must be application/json"})
            try:
                length = int(self.headers.get("Content-Length") or "")
            except ValueError:
                return self._reply(411, {"error": "Content-Length required"})
            if not 0 <= length <= MAX_BODY:
                self._reply(413, {"error": "body larger than {} bytes".format(MAX_BODY)})
                return self._discard(length)
            try:
                message = json.loads(self.rfile.read(length))
            except ValueError:
                return self._reply(400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
            if not isinstance(message, dict):
                return self._reply(400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "invalid request (batches are not supported)"}})
            mismatch = _header_mismatch(self.headers, message)
            if mismatch:
                return self._reply(400, {"jsonrpc": "2.0", "id": message.get("id"), "error": {"code": HEADER_MISMATCH, "message": mismatch}})
            response = server.handle(message, read_only=not full, client=str(client))
            if response is None:
                return self._reply(202, None)
            code = (response.get("error") or {}).get("code") if _is_modern(self.headers, message) else None
            self._reply(404 if code == METHOD_NOT_FOUND else 400 if code in (INVALID_PARAMS, UNSUPPORTED_VERSION) else 200, response)

        def _refuse_audited(self, status: int, message: str, detail: Optional[str] = None, headers: Optional[Mapping[str, str]] = None) -> None:
            client = self._client()
            server.audit_refused(str(client) if client else self.client_address[0], detail or message, status)
            self._reply(status, {"error": message}, headers)

        def _discard(self, length: int) -> None:
            # Closing with the body unread resets the connection, and a proxy such as Caddy then shows its own 502 instead of our 413.
            self.connection.settimeout(5)
            left = min(length, 4 * MAX_BODY)
            try:
                while left > 0:
                    chunk = self.rfile.read(min(65536, left))
                    if not chunk:
                        break
                    left -= len(chunk)
            except OSError:
                pass

        def _refuse(self) -> None:
            self._reply(405, {"error": "only POST /mcp is supported"}, {"Allow": "POST"})

        do_GET = do_DELETE = do_PUT = do_PATCH = do_HEAD = _refuse

        def _client(self) -> Any:
            # Only a trusted proxy's X-Forwarded-For counts; it appends the real client last.
            try:
                peer = ipaddress.ip_address(self.client_address[0])
                forwarded = self.headers.get("X-Forwarded-For")
                if forwarded and any(peer in network for network in proxies):
                    return ipaddress.ip_address(forwarded.split(",")[-1].strip())
                return peer
            except ValueError:
                return None

        def _reply(self, status: int, body: Any, headers: Optional[Mapping[str, str]] = None) -> None:
            data = b"" if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            if body is not None:
                self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        def log_message(self, format: str, *args: Any) -> None:
            log("edgeconnect-mcp http {} {}".format(self.client_address[0], format % args))

    httpd_class = type("Server6", (ThreadingHTTPServer,), {"address_family": socket.AF_INET6}) if ":" in host else ThreadingHTTPServer
    httpd = httpd_class((host, port), Handler)
    httpd.daemon_threads = True
    return httpd
