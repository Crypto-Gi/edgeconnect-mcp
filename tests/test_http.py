import ipaddress
import json
import os
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from edgeconnect_mcp.config import Config
from edgeconnect_mcp.http_server import http_settings, make_http_server
from edgeconnect_mcp.errors import ConfigurationError
from edgeconnect_mcp.server import Orchestrator, Server
from test_server import SPEC, FakeClient

TOKEN, READ_TOKEN = "w" * 40, "r" * 40


class HttpTransportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        spec = Path(self.tmp.name) / "spec.json"
        spec.write_text(json.dumps(SPEC))
        self.client = FakeClient()
        audit = os.path.join(self.tmp.name, "audit.jsonl")
        self.server = Server({"lab": Orchestrator("lab", Config(base_url="https://orch.example/gms/rest", api_key="KEY"), True, str(spec), self.client, confirm_writes=False)},
                             default="lab", log=lambda line: None, audit_log=audit)
        networks = [ipaddress.ip_network("127.0.0.1"), ipaddress.ip_network("10.1.2.0/24")]
        self.httpd = make_http_server(self.server, 0, TOKEN, READ_TOKEN, networks, {"https://ok.example"}, log=lambda line: None)
        Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.server.audit.close()
        self.tmp.cleanup()

    def post(self, message, token=TOKEN, method="POST", path="/mcp", **headers):
        connection = HTTPConnection("127.0.0.1", self.httpd.server_port, timeout=5)
        body = message if isinstance(message, bytes) else json.dumps(message).encode()
        base = {"Content-Type": "application/json"}
        if token:
            base["Authorization"] = "Bearer " + token
        base.update(headers)
        connection.request(method, path, body=body, headers=base)
        response = connection.getresponse()
        data = response.read()
        connection.close()
        return response.status, json.loads(data) if data else None

    def tool(self, name, token=TOKEN, **arguments):
        return self.post({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}}, token=token)

    def test_listens_on_loopback_only(self):
        self.assertEqual(self.httpd.server_address[0], "127.0.0.1")

    def test_calls_work_with_the_token(self):
        status, body = self.post({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}})
        self.assertEqual((status, body["result"]["protocolVersion"]), (200, "2025-06-18"))
        self.assertEqual(self.post({"jsonrpc": "2.0", "method": "notifications/initialized"}), (202, None))
        status, body = self.tool("api_get", path="/appliance")
        self.assertEqual(status, 200)
        self.assertFalse(body["result"]["isError"])

    def test_modern_requests_mirror_body_fields_in_headers(self):
        meta = {"io.modelcontextprotocol/protocolVersion": "2026-07-28", "io.modelcontextprotocol/clientCapabilities": {}}
        call = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "api_get", "arguments": {"path": "/appliance"}, "_meta": meta}}
        headers = {"MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "tools/call", "Mcp-Name": "api_get"}
        status, body = self.post(call, **headers)
        self.assertEqual((status, body["result"]["resultType"]), (200, "complete"))
        self.assertEqual(self.post(call, **dict(headers, **{"Mcp-Name": "=?base64?YXBpX2dldA==?="}))[0], 200)
        for bad in ({"Mcp-Name": "api_write"}, {"Mcp-Method": "tools/list"}, {"MCP-Protocol-Version": "2025-06-18"}, {"Mcp-Name": "=?base64?!!?="}):
            status, body = self.post(call, **dict(headers, **bad))
            self.assertEqual((status, body["error"]["code"]), (400, -32020), bad)
        self.assertEqual(self.post(call, **{"Mcp-Method": "tools/call", "Mcp-Name": "api_get"})[1]["error"]["code"], -32020)  # no version header
        self.assertEqual(len(self.client.calls), 2)
        bare = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        self.assertEqual(self.post(bare, **{"MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "tools/list"})[0], 400)  # modern header, body without _meta
        old = dict(meta, **{"io.modelcontextprotocol/protocolVersion": "1900-01-01"})
        status, body = self.post({"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {"_meta": old}}, **{"MCP-Protocol-Version": "1900-01-01", "Mcp-Method": "tools/list"})
        self.assertEqual((status, body["error"]["code"]), (400, -32022))
        status, body = self.post({"jsonrpc": "2.0", "id": 4, "method": "nope", "params": {"_meta": meta}}, **{"MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "nope"})
        self.assertEqual((status, body["error"]["code"]), (404, -32601))
        self.assertEqual(self.post(bare, **{"MCP-Protocol-Version": "2025-06-18"})[0], 200)  # legacy clients are unchanged

    def test_refusals(self):
        message = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        self.assertEqual(self.post(message, token=None)[0], 401)
        self.assertEqual(self.post(message, token="x" * 40)[0], 401)
        self.assertEqual(self.post(message, Origin="https://evil.example")[0], 403)
        self.assertEqual(self.post(message, Origin="https://ok.example")[0], 200)
        self.assertEqual(self.post(message, **{"X-Forwarded-For": "203.0.113.9"})[0], 403)
        self.assertEqual(self.post(message, **{"X-Forwarded-For": "203.0.113.9, 10.1.2.7"})[0], 200)  # the proxy's own entry is last
        self.assertEqual(self.post(message, **{"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.post(b"{}", **{"Content-Length": str(2 * 1024 * 1024 + 1)})[0], 413)
        self.assertEqual(self.post(b"x" * (3 * 1024 * 1024))[0], 413)  # a real oversized body is read off the socket, so a proxy sees the 413
        self.assertEqual(self.post([message])[0], 400)
        self.assertEqual(self.post(message, method="GET")[0], 405)
        self.assertEqual(self.post(message, path="/other")[0], 404)
        self.assertEqual(self.client.calls, [])

    def test_refused_requests_are_audited_without_the_token(self):
        message = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        wrong = "wrongtoken" + "x" * 30
        self.post(message, token=wrong)
        self.post(message, Origin="https://evil.example")
        self.post(message, **{"X-Forwarded-For": "203.0.113.9"})
        self.server.audit.flush()
        text = Path(self.tmp.name, "audit.jsonl").read_text()
        records = [json.loads(line) for line in text.splitlines()]
        self.assertEqual([(r["tool"], r["outcome"], r["status"]) for r in records], [("http_refused", "refused", 401), ("http_refused", "refused", 403), ("http_refused", "refused", 403)])
        self.assertIn("evil.example", records[1]["error"])
        self.assertEqual(records[2]["client"], "203.0.113.9")
        self.assertNotIn(wrong, text)

    def test_read_token_cannot_write_and_audit_names_the_client(self):
        status, body = self.tool("api_write", token=READ_TOKEN, method="POST", path="/ipObjects/addressGroup", body={"name": "g"})
        self.assertTrue(body["result"]["isError"])
        self.assertIn("read-only", body["result"]["content"][0]["text"])
        self.assertFalse(self.tool("api_get", token=READ_TOKEN, path="/appliance")[1]["result"]["isError"])
        self.assertFalse(self.tool("api_write", method="POST", path="/ipObjects/addressGroup", body={"name": "g"})[1]["result"]["isError"])
        self.server.audit.flush()
        records = [json.loads(line) for line in Path(self.tmp.name, "audit.jsonl").read_text().splitlines()]
        self.assertEqual([(r["tool"], r["outcome"], r["client"]) for r in records],
                         [("api_write", "error", "127.0.0.1"), ("api_get", "ok", "127.0.0.1"), ("api_write", "ok", "127.0.0.1")])

    def test_requests_run_in_parallel_and_overload_gets_503(self):
        import threading
        from edgeconnect_mcp import http_server
        release, entered = threading.Event(), threading.Semaphore(0)
        slow = self.client.request

        def blocking(method, path, **kwargs):
            entered.release()
            release.wait(5)
            return slow(method, path, **kwargs)

        self.client.request = blocking
        self.server.orchestrators["lab"].limits["read"].rate = 0
        results = []
        workers = [Thread(target=lambda: results.append(self.tool("api_get", path="/appliance")[0])) for _ in range(http_server.MAX_CONCURRENT)]
        for worker in workers:
            worker.start()
        for _ in workers:
            self.assertTrue(entered.acquire(timeout=5))  # all of them are inside the Orchestrator call at once
        self.assertEqual(self.post({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})[0], 503)
        release.set()
        for worker in workers:
            worker.join(5)
        self.assertEqual(results, [200] * http_server.MAX_CONCURRENT)
        self.assertEqual(self.post({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})[0], 200)

    def test_forwarded_for_only_counts_from_trusted_proxies(self):
        httpd = make_http_server(self.server, 0, TOKEN, None, [ipaddress.ip_network("10.1.2.0/24")], set(), log=lambda line: None,
                                 proxies=[ipaddress.ip_network("192.0.2.0/24")])  # loopback peer is not a trusted proxy here
        Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            connection = HTTPConnection("127.0.0.1", httpd.server_port, timeout=5)
            connection.request("POST", "/mcp", body=b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}',
                               headers={"Content-Type": "application/json", "Authorization": "Bearer " + TOKEN, "X-Forwarded-For": "10.1.2.7"})
            self.assertEqual(connection.getresponse().status, 403)
            connection.close()
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_settings_validation(self):
        dotenv = Path(self.tmp.name) / ".env"
        dotenv.write_text("x=1\n")
        os.chmod(str(dotenv), 0o600)
        settings = http_settings({"mcp_http_token": TOKEN, "mcp_http_allowed_clients": "127.0.0.1, 10.0.0.0/8"}, str(dotenv))
        self.assertEqual([str(n) for n in settings["networks"]], ["127.0.0.1/32", "10.0.0.0/8"])
        self.assertEqual([str(n) for n in http_settings({"mcp_http_token": TOKEN}, None)["networks"]], ["127.0.0.1/32", "::1/128"])
        defaults = http_settings({"mcp_http_token": TOKEN}, None)
        self.assertEqual((defaults["host"], [str(n) for n in defaults["proxies"]]), ("127.0.0.1", ["127.0.0.1/32", "::1/128"]))
        self.assertEqual(http_settings({"mcp_http_token": TOKEN, "mcp_http_listen": "0.0.0.0"}, None)["host"], "0.0.0.0")
        for bad in ({}, {"mcp_http_token": "short"}, {"mcp_http_token": TOKEN, "mcp_http_read_token": TOKEN}, {"mcp_http_token": TOKEN, "mcp_http_allowed_clients": "nope"},
                    {"mcp_http_token": TOKEN, "mcp_http_trusted_proxies": "nope"}, {"mcp_http_token": TOKEN, "mcp_http_listen": "localhost"}):
            with self.assertRaises(ConfigurationError):
                http_settings(bad, str(dotenv))
        os.chmod(str(dotenv), 0o644)
        with self.assertRaisesRegex(ConfigurationError, "chmod 600"):
            http_settings({"mcp_http_token": TOKEN}, str(dotenv))

    def test_ssh_caller_is_recorded_in_stdio_mode(self):
        os.environ["SSH_CLIENT"] = "192.0.2.5 50000 22"
        try:
            self.assertEqual(Server({}, log=lambda line: None).client, "192.0.2.5")
        finally:
            del os.environ["SSH_CLIENT"]


if __name__ == "__main__":
    unittest.main()
