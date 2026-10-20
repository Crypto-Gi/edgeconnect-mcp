import io
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from edgeconnect_mcp.config import Config, load_config
from edgeconnect_mcp.errors import ConfigurationError
from edgeconnect_mcp.server import Orchestrator, RateLimiter, Server, ToolError, high_risk_category

SPEC = {
    "swagger": "2.0",
    "basePath": "/gms/rest",
    "paths": {
        "/appliance": {"get": {"summary": "List all appliances", "tags": ["appliance"]}},
        "/appliance/{nePk}": {
            "get": {"summary": "Get one appliance", "parameters": [{"name": "nePk", "in": "path"}]},
            "delete": {"summary": "Delete appliance"},
        },
        "/appliance/rest/{nePk}": {"post": {"summary": "Appliance REST passthrough"}},
        "/thirdPartyServices/zscaler/countries": {"post": {"summary": "Set countries", "requestBody": {"content": {"text/plain": {"schema": {"type": "string"}}}}}},
        "/thirdPartyServices/zscaler/legacy": {"post": {"summary": "Set legacy text", "consumes": ["text/plain"]}},
        "/ipObjects/addressGroup/{name}": {"put": {"summary": "Update address group"}},
        "/logging/remoteReceiver": {"post": {"summary": "Set remote log receiver"}},
        "/ipObjects/addressGroup": {"get": {"summary": "List address groups"}, "post": {"summary": "Create address group", "parameters": [{"in": "body", "name": "body", "schema": {"$ref": "#/definitions/Group"}}]}},
    },
    "definitions": {
        "Group": {"type": "object", "properties": {"name": {"type": "string"}, "rules": {"type": "array", "items": {"$ref": "#/definitions/Rule"}}}},
        "Rule": {"type": "object", "properties": {"includedIPs": {"type": "array"}, "parent": {"$ref": "#/definitions/Rule"}}},
    },
}


class FakeClient:
    def __init__(self, body=b'{"ok": true, "apiKey": "s3cret"}'):
        self.body = body
        self.calls = []

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs.get("query"), kwargs.get("json_body")))
        return self.body

    def _url(self, path, query):
        return "https://orch.example/gms/rest" + path


class McpServerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        spec = Path(self.tmp.name) / "spec.json"
        spec.write_text(json.dumps(SPEC))
        config = Config(base_url="https://orch.example/gms/rest", api_key="KEY")
        self.lab_client, self.prod_client = FakeClient(), FakeClient()
        self.server = Server({  # two-step writes have their own test; the other write tests send in one step
            "lab": Orchestrator("lab", config, True, str(spec), self.lab_client, confirm_writes=False),
            "prod": Orchestrator("prod", config, False, str(spec), self.prod_client, confirm_writes=False),
        }, default="prod", log=lambda line: None)

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, name, **arguments):
        response = self.server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}})
        result = response["result"]
        return result["isError"], result["content"][0]["text"]

    def test_initialize_and_list_tools(self):
        init = self.server.handle({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}})
        self.assertEqual(init["result"]["protocolVersion"], "2025-06-18")
        self.assertIsNone(self.server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        names = [tool["name"] for tool in self.server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]]
        self.assertEqual(names, ["list_orchestrators", "find_operations", "describe_operation", "api_get", "api_write"])

    def test_modern_requests_are_stateless_and_carry_metadata(self):
        meta = {"io.modelcontextprotocol/protocolVersion": "2026-07-28", "io.modelcontextprotocol/clientCapabilities": {}}
        modern = lambda method, version="2026-07-28", **params: self.server.handle({"jsonrpc": "2.0", "id": 1, "method": method, "params": dict(params, _meta=dict(meta, **{"io.modelcontextprotocol/protocolVersion": version}))})
        discover = modern("server/discover")["result"]
        self.assertEqual(discover["supportedVersions"][:2], ["2026-07-28", "2025-11-25"])
        self.assertEqual((discover["resultType"], discover["capabilities"], discover["cacheScope"]), ("complete", {"tools": {}}, "private"))
        self.assertEqual(discover["_meta"]["io.modelcontextprotocol/serverInfo"]["name"], "edgeconnect-orchestrator")
        listed = modern("tools/list")["result"]  # no initialize first
        self.assertEqual((len(listed["tools"]), listed["ttlMs"], listed["resultType"]), (5, 0, "complete"))
        called = modern("tools/call", name="list_orchestrators", arguments={})["result"]
        self.assertEqual((called["isError"], called["resultType"]), (False, "complete"))
        self.assertNotIn("ttlMs", called)
        unsupported = modern("tools/list", version="1900-01-01")["error"]
        self.assertEqual((unsupported["code"], unsupported["data"]["requested"]), (-32022, "1900-01-01"))
        self.assertIn("2026-07-28", unsupported["data"]["supported"])
        self.assertEqual(modern("ping")["error"]["code"], -32601)  # removed in 2026-07-28
        no_caps = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {"_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28"}}}
        self.assertEqual(self.server.handle(no_caps)["error"]["code"], -32602)
        self.assertEqual(self.server.handle({"jsonrpc": "2.0", "id": 1, "method": "server/discover"})["error"]["code"], -32602)
        legacy = self.server.handle({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}})["result"]
        self.assertEqual(legacy["protocolVersion"], "2025-11-25")
        self.assertNotIn("resultType", self.server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"])

    def test_redaction_hides_psks_but_keeps_flags_and_numbers(self):
        self.prod_client.body = json.dumps({"presharedkey": "abc12", "authKey": "k", "passwordMinLen": 8, "csrfProtection": True, "md5Password": ""}).encode()
        _, text = self.call("api_get", path="/appliance")
        value = json.loads(text)["result"]
        self.assertRegex(value.pop("presharedkey"), r"^<REDACTED:[0-9a-f]{16}>$")
        self.assertRegex(value.pop("authKey"), r"^<REDACTED:[0-9a-f]{16}>$")
        self.assertEqual(value, {"passwordMinLen": 8, "csrfProtection": True, "md5Password": ""})
        self.prod_client.body = json.dumps({"cert": "-----BEGIN RSA PRIVATE KEY-----\nMIIE\n-----END RSA PRIVATE KEY-----"}).encode()
        _, text = self.call("api_get", path="/appliance")
        self.assertNotIn("MIIE", text)

    def test_every_secret_field_in_the_spec_is_redacted(self):
        # Every string property the 9.7.1 spec describes as a password, secret, key, community string or credential.
        secret = ["rocommunity", "trap_community", "accountKey", "oldAccountKey", "oldKey", "pre_shared_key", "presharedKey", "primaryKey",
                  "secondaryKey", "privacy_key", "storageAccountKey", "keyData", "key", "vpnCredential", "barcodeBase64Jpeg", "clientSecret",
                  "apiKey", "password", "authKey", "ike_psk"]
        readable = ["community", "set_community", "resourceKey", "keySize", "hash_type", "authType", "name", "monkey"]
        self.prod_client.body = json.dumps({key: "value-" + key for key in secret + readable}).encode()
        _, text = self.call("api_get", path="/appliance")
        value = json.loads(text)["result"]
        self.assertEqual([key for key in secret if not value[key].startswith("<REDACTED:")], [])
        self.assertEqual({key: value[key] for key in readable}, {key: "value-" + key for key in readable})

    def test_writes_need_confirmation_by_default(self):
        lab = self.server.orchestrators["lab"]
        lab.confirm_writes = True
        write = dict(orchestrator="lab", method="POST", path="/ipObjects/addressGroup", body={"name": "g"})
        error, text = self.call("api_write", **write)
        first = json.loads(text)
        self.assertFalse(error)
        self.assertEqual((first["status"], first["change"]["body"], first["change"]["operation"]), ("confirmation_required", {"name": "g"}, "Create address group"))
        self.assertEqual(self.lab_client.calls, [])  # nothing sent yet
        for changed in (dict(write, body={"name": "h"}), dict(write, method="PUT", path="/ipObjects/addressGroup/g"), dict(write, query={"x": "1"})):
            error, text = self.call("api_write", confirmation=first["confirmation"], **changed)
            self.assertTrue(error)
            self.assertIn("different request", text)
        self.assertEqual(self.lab_client.calls, [])
        code = json.loads(self.call("api_write", **write)[1])["confirmation"]
        other = self.server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "api_write", "arguments": dict(write, confirmation=code)}}, client="10.9.9.9")
        self.assertTrue(other["result"]["isError"])  # issued to another caller
        code = json.loads(self.call("api_write", **write)[1])["confirmation"]
        error, _ = self.call("api_write", confirmation=code, **write)
        self.assertFalse(error)
        self.assertEqual(self.lab_client.calls, [("POST", "/ipObjects/addressGroup", None, {"name": "g"})])
        self.assertTrue(self.call("api_write", confirmation=code, **write)[0])  # single use
        code = json.loads(self.call("api_write", **write)[1])["confirmation"]
        self.server._pending[code] = (self.server._pending[code][0], 0.0)  # expired
        self.assertTrue(self.call("api_write", confirmation=code, **write)[0])
        self.assertEqual(len(self.lab_client.calls), 1)
        # High-risk and disabled writes are refused at the first step, without a code.
        error, text = self.call("api_write", orchestrator="lab", method="DELETE", path="/appliance/2.NE")
        self.assertTrue(error)
        self.assertIn("high-risk", text)

    def test_write_confirmation_is_on_unless_turned_off(self):
        dotenv = Path(self.tmp.name) / "c.env"
        dotenv.write_text("orch_1=a\na_base_url=https://192.0.2.1\na_api_key=k\norch_2=b\nb_base_url=https://192.0.2.2\nb_api_key=k\nb_mcp_confirm_writes=false\nmcp_audit_log=off\n")
        server = Server.from_dotenv(str(dotenv))
        self.assertEqual({name: o.confirm_writes for name, o in server.orchestrators.items()}, {"a": True, "b": False})

    def test_main_prefers_home_settings_file_over_local_env(self):
        from unittest import mock
        import edgeconnect_mcp.server as server_module
        home = Path(self.tmp.name) / "home.env"
        home.write_text("x=1\n")
        (Path(self.tmp.name) / ".env").write_text("x=2\n")
        cwd = os.getcwd()
        os.chdir(self.tmp.name)
        try:
            with mock.patch.object(server_module, "HOME_DOTENV", home), mock.patch.object(Server, "from_dotenv", side_effect=OSError("stop")) as from_dotenv, mock.patch("sys.stderr", io.StringIO()):
                self.assertEqual(server_module.main([]), 2)
        finally:
            os.chdir(cwd)
        from_dotenv.assert_called_once_with(str(home))

    def test_secret_tokens_round_trip_on_write_back(self):
        self.lab_client.body = json.dumps({"name": "g", "presharedKey": "hunter2", "nested": [{"password": "p@ss"}]}).encode()
        _, text = self.call("api_get", orchestrator="lab", path="/ipObjects/addressGroup")
        self.assertNotIn("hunter2", text)
        self.assertNotIn("p@ss", text)
        read = json.loads(text)["result"]
        error, _ = self.call("api_write", orchestrator="lab", method="POST", path="/ipObjects/addressGroup", body=read)
        self.assertFalse(error)
        self.assertEqual(self.lab_client.calls[-1][3], {"name": "g", "presharedKey": "hunter2", "nested": [{"password": "p@ss"}]})
        error, _ = self.call("api_write", orchestrator="lab", method="PUT", path="/ipObjects/addressGroup/g", body=read)
        self.assertFalse(error)  # a child path of the one it was read from
        sent = len(self.lab_client.calls)
        # A token moved into a readable field, another secret field, another feature's path, or another Orchestrator is refused.
        for path, body in (("/ipObjects/addressGroup", {"name": read["presharedKey"]}),
                           ("/ipObjects/addressGroup", {"password": read["presharedKey"]}),
                           ("/logging/remoteReceiver", {"presharedKey": read["presharedKey"]})):
            error, text = self.call("api_write", orchestrator="lab", method="POST", path=path, body=body)
            self.assertTrue(error)
            self.assertIn("placeholders", text)
        self.server.orchestrators["prod"].writes = True
        error, _ = self.call("api_write", orchestrator="prod", method="POST", path="/ipObjects/addressGroup", body=read)
        self.assertTrue(error)
        self.assertEqual(len(self.lab_client.calls), sent)
        self.assertEqual(self.prod_client.calls, [])

    def test_list_orchestrators_never_shows_keys(self):
        error, text = self.call("list_orchestrators")
        self.assertFalse(error)
        self.assertNotIn("KEY", text)
        self.assertEqual({o["name"]: o["writes_enabled"] for o in json.loads(text)}, {"lab": True, "prod": False})

    def test_find_and_describe(self):
        _, text = self.call("find_operations", query="appliance")
        self.assertEqual(json.loads(text)["total_matches"], 4)
        _, text = self.call("describe_operation", method="POST", path="/ipObjects/addressGroup")
        self.assertIn('"name"', text)  # $ref resolved
        self.assertIn('"includedIPs"', text)  # nested $ref resolved
        self.assertIn('"#/definitions/Rule"', text)  # recursion stops at the cycle

    def test_get_is_redacted_and_matched_against_spec(self):
        error, text = self.call("api_get", path="/appliance/2.NE", query={"x": 1})
        self.assertFalse(error)
        self.assertNotIn("s3cret", text)
        self.assertEqual(self.prod_client.calls, [("GET", "/appliance/2.NE", {"x": 1}, None)])
        for bad in ("/appliance/../users", "/nope", "//evil.example/x", "/appliance/%2e%2e", "http://evil"):
            error, _ = self.call("api_get", path=bad)
            self.assertTrue(error, bad)

    def test_writes_are_gated_per_orchestrator(self):
        error, text = self.call("api_write", method="DELETE", path="/appliance/2.NE")
        self.assertTrue(error)
        self.assertIn("prod_mcp_writes", text)
        self.assertEqual(self.prod_client.calls, [])
        error, _ = self.call("api_write", orchestrator="lab", method="POST", path="/ipObjects/addressGroup", body={"name": "g"})
        self.assertFalse(error)
        self.assertEqual(self.lab_client.calls, [("POST", "/ipObjects/addressGroup", None, {"name": "g"})])
        error, text = self.call("api_write", orchestrator="lab", method="POST", path="/ipObjects/addressGroup", body={"name": "g", "password": "<REDACTED>"})
        self.assertTrue(error)
        self.assertIn("placeholders", text)
        error, text = self.call("api_write", orchestrator="lab", method="POST", path="/appliance/rest/2.NE", query={"url": "reboot"})
        self.assertTrue(error)
        self.assertIn("lab_mcp_passthrough", text)
        self.assertEqual(len(self.lab_client.calls), 1)
        self.server.orchestrators["lab"].passthrough = True
        error, _ = self.call("api_write", orchestrator="lab", method="POST", path="/appliance/rest/2.NE", query={"url": "x"})
        self.assertFalse(error)
        error, _ = self.call("api_write", orchestrator="lab", method="PUT", path="/appliance/2.NE")
        self.assertTrue(error)  # undocumented method
        error, _ = self.call("api_write", orchestrator="lab", method="GET", path="/appliance")
        self.assertTrue(error)

    def test_high_risk_writes_need_their_own_opt_in(self):
        lab = self.server.orchestrators["lab"]
        lab.passthrough = True
        error, text = self.call("api_write", orchestrator="lab", method="DELETE", path="/appliance/2.NE")
        self.assertTrue(error)
        self.assertIn("appliance_lifecycle", text)
        self.assertIn("lab_mcp_allow_high_risk", text)
        error, text = self.call("api_write", orchestrator="lab", method="POST", path="/appliance/rest/2.NE", query={"url": "system/reboot"})
        self.assertTrue(error)
        self.assertIn("(reboot)", text)
        self.assertEqual(self.lab_client.calls, [])
        lab.allow_high_risk = ("appliance_lifecycle",)
        error, _ = self.call("api_write", orchestrator="lab", method="DELETE", path="/appliance/2.NE")
        self.assertFalse(error)
        self.assertEqual(high_risk_category("POST", "/ipObjects/addressGroup"), None)
        for template in ("/certificates/parse", "/license/validate", "/cipher/checkCompatibility", "/sslCertificate/verify", "/users/lookup", "/brandImage/upload", "/appliance/rest/{nePk}/x/validate"):
            self.assertEqual(high_risk_category("POST", template), None, template)
        self.assertEqual(high_risk_category("POST", "/appliance/rest/{nePk}", "ntp/validate"), None)
        for template in ("/gms/backup/testConnection", "/authentication/userAuthType", "/authentication/userAuthTypeToken", "/gms/wizard", "/thirdPartyServices/sse/connectorPool", "/alarm/clear", "/overlays/{id}",
                         "/customCert/applianceConnectivity", "/customCert/orchestratorConnectivity", "/rmaWizard/checkInterfaceMapping"):
            self.assertEqual(high_risk_category("POST", template), None, template)
        self.assertEqual(high_risk_category("POST", "/ssl/x", None, "Verify the certificate chain"), None)
        for method, template, category in (("POST", "/security/estServer", "certificates"), ("PUT", "/spPortal/config", "provisioning"), ("POST", "/account/key/generate", "provisioning"),
                                           ("DELETE", "/account/oldKey", "provisioning"), ("POST", "/createCaseWithPortal", "provisioning"), ("POST", "/gms/gmsRegistration2", "provisioning"),
                                           ("POST", "/gmsSMTP/testEmail", "orchestrator_admin"), ("POST", "/sendVerificationEmail", "orchestrator_admin"), ("POST", "/delUnverifiedEmails", "orchestrator_admin"),
                                           ("POST", "/thirdPartyServices/clearpass/event/login", "identity_events"), ("POST", "/dhcpConfig/reset", "traffic_disruptive"),
                                           ("POST", "/gmsOperatingSystem/root/passwordChanged", "orchestrator_admin"), ("POST", "/haGroups", "appliance_lifecycle")):
            self.assertEqual(high_risk_category(method, template, None, "Change the settings"), category, template)
        self.assertEqual(high_risk_category("POST", "/ssl/x", None, "Validate a certificate chain"), None)
        self.assertEqual(high_risk_category("POST", "/appliance/denied/delete"), "appliance_lifecycle")
        self.assertEqual(high_risk_category("PUT", "/gmsSMTP/config"), "orchestrator_admin")
        self.assertEqual(high_risk_category("POST", "/sse/connector"), "appliance_lifecycle")
        self.assertEqual(high_risk_category("POST", "/brandCustomization/image"), None)
        self.assertEqual(high_risk_category("POST", "/appliance/rest/{nePk}", "deployment"), None)
        for method, template, category in (("DELETE", "/appliance", "appliance_lifecycle"), ("POST", "/appliance", "appliance_lifecycle"),
                                           ("POST", "/appliance/deleteForDiscovery", "appliance_lifecycle"), ("POST", "/appliance/changePassword", "appliance_lifecycle"),
                                           ("POST", "/cloudDeployment/aws/instances", "cloud_deployment"), ("POST", "/edge-ha/groups", "appliance_lifecycle"),
                                           ("POST", "/orch-ha/failover", "orchestrator_ha"), ("POST", "/gmsRemoteAuth/TACACS+", "auth"), ("PUT", "/gmsRemoteAuth/JWT", "auth"),
                                           ("DELETE", "/vxoaImages/{id}", "upgrade"), ("POST", "/preconfiguration/{id}/apply", "provisioning"),
                                           ("POST", "/applianceWizard/apply", "provisioning"), ("POST", "/rmaWizard", "provisioning"), ("POST", "/portal/registration", "provisioning"),
                                           ("POST", "/ztp/settings", "provisioning"), ("POST", "/accountKey/generate", "provisioning"),
                                           ("PUT", "/gmsConfig/sessionTimeout", "orchestrator_admin"), ("PUT", "/restApiConfig", "orchestrator_admin"),
                                           ("POST", "/advancedProperties", "orchestrator_admin"), ("PUT", "/security/advancedSettings", "orchestrator_admin"),
                                           ("POST", "/smtp", "orchestrator_admin"), ("DELETE", "/debugFiles/{name}", "orchestrator_admin"),
                                           ("DELETE", "/dbPartition/{id}", "orchestrator_admin"), ("POST", "/est/profile", "certificates"), ("POST", "/endEntityProfile", "certificates"),
                                           ("POST", "/users/{username}", "auth"), ("PUT", "/gms/backup/config", "backup_restore"),
                                           ("POST", "/broadcastCli", "cli"), ("POST", "/license/portal", "licensing"), ("POST", "/networkMemory", "traffic_disruptive")):
            self.assertEqual(high_risk_category(method, template), category, template)

    def test_flag_settings_named_like_secrets_stay_readable(self):
        self.lab_client.body = json.dumps({"applyPassword": "true", "enablePassword": "false", "password": "true", "authKey": "yes"}).encode()
        _, text = self.call("api_get", orchestrator="lab", path="/appliance")
        value = json.loads(text)["result"]
        self.assertEqual((value["applyPassword"], value["enablePassword"]), ("true", "false"))
        self.assertTrue(value["password"].startswith("<REDACTED:"))  # not flag-named, so still a secret
        self.assertTrue(value["authKey"].startswith("<REDACTED:"))

    def test_rate_limiter_waits_instead_of_failing(self):
        now, slept = [0.0], []
        limiter = RateLimiter(2, clock=lambda: now[0], sleep=lambda seconds: (slept.append(seconds), now.__setitem__(0, now[0] + seconds)))
        for _ in range(4):
            limiter.take()  # burst of twice the rate
        self.assertEqual(slept, [])
        limiter.take()
        self.assertAlmostEqual(slept[0], 0.5)
        RateLimiter(0, sleep=lambda seconds: self.fail("0 means no limit")).take()

    def test_audit_log_records_calls_without_secrets(self):
        path = os.path.join(self.tmp.name, "audit", "audit.jsonl")
        server = Server(self.server.orchestrators, default="prod", log=lambda line: None, audit_log=path)
        self.lab_client.body = json.dumps({"presharedKey": "hunter2"}).encode()
        for name, arguments in (("api_get", {"orchestrator": "lab", "path": "/appliance", "query": {"password": "q-secret"}}),
                                ("api_write", {"orchestrator": "lab", "method": "POST", "path": "/ipObjects/addressGroup", "body": {"name": "g"}}),
                                ("api_write", {"method": "DELETE", "path": "/appliance/2.NE"})):
            server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}})
        server.audit.close()
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        content = Path(path).read_text()
        self.assertNotIn("hunter2", content)
        self.assertNotIn("q-secret", content)
        records = [json.loads(line) for line in content.splitlines()]
        self.assertEqual([(r["tool"], r["orchestrator"], r["method"], r["outcome"]) for r in records],
                         [("api_get", "lab", "GET", "ok"), ("api_write", "lab", "POST", "ok"), ("api_write", "prod", "DELETE", "error")])
        self.assertTrue(records[1]["body_sha256"].startswith("sha256:"))
        self.assertIn("prod_mcp_writes", records[2]["error"])
        self.assertEqual((records[1]["body"], records[1]["phase"], records[1]["action"]), ('{"name": "g"}', "executed", "Create address group"))
        self.assertIn(records[0]["day"], ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"))

    def test_tcp_syslog_reconnects_after_the_server_comes_back(self):
        import socket
        import threading

        def listen(port=0):
            sock = socket.socket()
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", port))
            sock.listen(1)
            got = []

            def accept():
                conn, _ = sock.accept()
                conn.settimeout(5)
                got.append(conn.recv(65536).decode())
                conn.close()
            thread = threading.Thread(target=accept, daemon=True)
            thread.start()
            return sock, got, thread

        first, got_first, thread_first = listen()
        port = first.getsockname()[1]
        reports = []
        server = Server(self.server.orchestrators, default="prod", log=reports.append, audit_syslog="tcp://127.0.0.1:{}".format(port))
        call = lambda: server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "api_get", "arguments": {"path": "/appliance"}}})
        call()
        thread_first.join(5)
        self.assertEqual(len(got_first[0].splitlines()), 1)
        first.close()
        for _ in range(3):
            self.assertFalse(call()["result"]["isError"])  # server gone: calls still work
        self.assertTrue(any("audit syslog failed" in line for line in reports))
        second, got_second, thread_second = listen(port)
        call()
        thread_second.join(5)
        second.close()
        self.assertEqual(len(got_second[0].splitlines()), 1)  # a new connection was made

    def test_tcp_syslog_loses_nothing_when_the_server_restarts_between_records(self):
        import socket
        import threading

        def listen(port=0):
            sock = socket.socket()
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", port))
            sock.listen(1)
            sock.settimeout(5)
            got = []

            def accept():
                try:
                    conn, _ = sock.accept()
                except OSError:
                    return
                conn.settimeout(5)
                got.append(conn.recv(65536).decode())
                conn.close()
            thread = threading.Thread(target=accept, daemon=True)
            thread.start()
            return sock, got, thread

        first, got_first, thread_first = listen()
        port = first.getsockname()[1]
        server = Server(self.server.orchestrators, default="prod", log=lambda line: None, audit_syslog="tcp://127.0.0.1:{}".format(port))
        call = lambda: server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "api_get", "arguments": {"path": "/appliance"}}})
        call()
        thread_first.join(5)
        first.close()  # the syslog server restarts: its side of the connection is closed before the next record
        second, got_second, thread_second = listen(port)
        call()
        thread_second.join(5)
        second.close()
        self.assertEqual([len(text.splitlines()) for text in got_second], [1])  # the very next record arrives, none is lost

    def test_audit_goes_to_sqlite_and_syslog_too(self):
        import socket
        import sqlite3
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(5)
        db = os.path.join(self.tmp.name, "audit.db")
        self.server.orchestrators["lab"].confirm_writes = True
        server = Server(self.server.orchestrators, default="lab", log=lambda line: None, audit_sqlite=db,
                        audit_syslog="udp://127.0.0.1:{}".format(receiver.getsockname()[1]))
        server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "api_write", "arguments": {"method": "POST", "path": "/ipObjects/addressGroup", "body": {"name": "g", "password": "typed-in-clear"}}}})
        message = receiver.recv(65536).decode()
        receiver.close()
        server.audit.close()
        self.assertIn('"phase": "awaiting_confirmation"', message)
        self.assertNotIn("typed-in-clear", message)
        self.assertEqual(stat.S_IMODE(os.stat(db).st_mode), 0o600)
        connection = sqlite3.connect(db)
        rows = connection.execute("SELECT tool, method, path, action, phase, outcome, record FROM audit").fetchall()
        connection.close()
        self.assertEqual(rows[0][:6], ("api_write", "POST", "/ipObjects/addressGroup", "Create address group", "awaiting_confirmation", "ok"))
        self.assertNotIn("typed-in-clear", rows[0][6])
        with self.assertRaises(ConfigurationError):
            Server({}, audit_syslog="http://example")

    def test_results_are_marked_untrusted_and_hidden_characters_escaped(self):
        self.prod_client.body = json.dumps({"comment": "ok\u202egnp.exe\U000e0041"}).encode()
        _, text = self.call("api_get", path="/appliance")
        self.assertNotIn("\u202e", text)
        self.assertNotIn("\U000e0041", text)
        decoded = json.loads(text)
        self.assertEqual(decoded["result"]["comment"], "ok\u202egnp.exe\U000e0041")  # lossless
        self.assertIn("untrusted", decoded["note"])

    def test_text_plain_bodies_are_sent_raw(self):
        class Raw(FakeClient):
            def request(self, method, path, **kwargs):
                self.calls.append((method, path, kwargs.get("binary_body"), kwargs.get("content_type"), kwargs.get("json_body")))
                return b""

        raw = Raw()
        self.server.orchestrators["lab"].client = raw
        text = "line1\nline2"
        for path in ("/thirdPartyServices/zscaler/countries", "/thirdPartyServices/zscaler/legacy"):
            error, _ = self.call("api_write", orchestrator="lab", method="POST", path=path, body=text)
            self.assertFalse(error)
        self.assertEqual(raw.calls, [("POST", p, b"line1\nline2", "text/plain", None) for p in ("/thirdPartyServices/zscaler/countries", "/thirdPartyServices/zscaler/legacy")])
        # JSON operations still get a JSON-encoded string
        raw.calls.clear()
        self.call("api_write", orchestrator="lab", method="POST", path="/ipObjects/addressGroup", body="x")
        self.assertEqual(raw.calls, [("POST", "/ipObjects/addressGroup", None, None, "x")])

    def test_truncation_and_stdio(self):
        self.prod_client.body = json.dumps(["x" * 100] * 100).encode()
        _, text = self.call("api_get", path="/appliance", max_chars=1000)
        self.assertIn("truncated", text)
        out = io.StringIO()
        self.server.serve(io.StringIO('{"jsonrpc":"2.0","id":7,"method":"ping"}\nnot json\n'), out)
        lines = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual(lines[0], {"jsonrpc": "2.0", "id": 7, "result": {}})
        self.assertEqual(lines[1]["error"]["code"], -32700)

    def test_openapi3_spec_is_downloaded_from_the_orchestrator(self):
        spec = {"openapi": "3.0.0", "servers": [{"url": "https://orch.example:/gms/rest"}], "paths": {"/gmsserver/info": {"get": {"summary": "Info"}}}}
        client = FakeClient(json.dumps(spec).encode())
        orchestrator = Orchestrator("o", Config(base_url="https://orch.example/gms/rest", api_key="K"), False, None, client)
        self.assertEqual(orchestrator.match("GET", "/gmsserver/info")["summary"], "Info")
        self.assertEqual(client.calls[0][:2], ("GET", "/apiDocs"))

    def test_passthrough_url_with_encoding_or_dot_segments_is_refused(self):
        self.server.orchestrators["lab"].passthrough = True
        for url in ("vr%72p", "a/../reboot", "a\\b"):
            error, text = self.call("api_write", orchestrator="lab", method="POST", path="/appliance/rest/2.NE", query={"url": url}, body={})
            self.assertTrue(error)
            self.assertIn("must not contain", text)
        self.assertEqual(self.lab_client.calls, [])

    def test_unexpected_errors_do_not_end_the_session(self):
        self.prod_client.request = lambda *a, **k: {}["boom"]
        error, text = self.call("api_get", path="/appliance")
        self.assertTrue(error)
        self.assertEqual(text, "Error: internal error (KeyError)")

    def test_redirects_are_refused_not_followed(self):
        from http.server import BaseHTTPRequestHandler, HTTPServer
        from threading import Thread
        from edgeconnect_mcp.client import ApiClient
        from edgeconnect_mcp.errors import ResponseFormatError
        seen = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append((self.path, self.headers.get("X-Auth-Token")))
                self.send_response(302)
                self.send_header("Location", "/elsewhere")
                self.end_headers()

            def log_message(self, *args):
                pass

        httpd = HTTPServer(("127.0.0.1", 0), Handler)
        Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            config = load_config(environ={"orchestrator_base_url": "http://127.0.0.1:{}".format(httpd.server_port), "orchestrator_api_key": "K"}, allow_http=True)
            with self.assertRaises(ResponseFormatError):
                ApiClient(config).get("/x")
        finally:
            httpd.shutdown()
            httpd.server_close()
        self.assertEqual(seen, [("/gms/rest/x", "K")])  # the redirect target never got the key

    def test_http_is_only_allowed_for_loopback(self):
        for url in ("http://127.0.0.1:8080", "http://localhost", "http://[::1]"):
            load_config(environ={"orchestrator_base_url": url, "orchestrator_api_key": "K"}, allow_http=True)
        for url in ("http://192.0.2.1", "http://127.evil.example"):
            with self.assertRaises(ConfigurationError):
                load_config(environ={"orchestrator_base_url": url, "orchestrator_api_key": "K"}, allow_http=True)

    def test_tls_pin_is_normalized_and_validated(self):
        env = {"orch_1": "lab", "lab_base_url": "https://192.0.2.1", "lab_api_key": "K", "lab_tls_sha256": "AB:" * 31 + "AB"}
        self.assertEqual(load_config(environ=env, orchestrator="lab").tls_sha256, "ab" * 32)
        with self.assertRaises(ConfigurationError):
            load_config(environ=dict(env, lab_tls_sha256="abc"), orchestrator="lab")

    def test_errors_are_short_and_explain_tls_failures(self):
        from urllib.error import URLError
        from edgeconnect_mcp.errors import ResourceNotFoundError, TransportError

        def html_404(*args, **kwargs):
            raise ResourceNotFoundError("HTTP 404: <html><body>" + "<p>Not found</p>" * 300 + "</body></html>", 404, "GET", "/appliance")

        self.prod_client.request = html_404
        _, text = self.call("api_get", path="/appliance")
        self.assertNotIn("<", text)
        self.prod_client.request = lambda *a, **k: (_ for _ in ()).throw(ResourceNotFoundError('HTTP 404: <html><script>"use strict"; const protocol = "https://";', 404, "GET", "/x"))
        _, text = self.call("api_get", path="/appliance")
        self.assertNotIn("use strict", text)
        self.assertLess(len(text.split("\n")[0]), 520)
        self.assertIn("untrusted", text)  # the Orchestrator's own error text is labelled like any result

        def bad_cert(*args, **kwargs):
            raise TransportError("transport failure: URLError") from URLError("[SSL: CERTIFICATE_VERIFY_FAILED] self-signed certificate")

        self.lab_client.request = bad_cert
        _, text = self.call("api_get", orchestrator="lab", path="/appliance")
        self.assertIn("CERTIFICATE_VERIFY_FAILED", text)
        self.assertIn("lab_tls_sha256", text)


if __name__ == "__main__":
    unittest.main()
