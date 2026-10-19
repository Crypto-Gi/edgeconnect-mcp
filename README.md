# edgeconnect-mcp

**Let Claude, or any other MCP client, read and safely change an HPE Aruba EdgeConnect SD-WAN Orchestrator through its REST API.**

> **Independent open-source project.** Not made, endorsed or supported by Hewlett Packard Enterprise. Provided "as is" under the [Apache License 2.0](LICENSE), without warranty or liability; you are responsible for what you, or an assistant you connect, change on your network. See [NOTICE](NOTICE).

MCP (Model Context Protocol) is the standard way AI assistants call external tools. This server gives an assistant five generic tools that cover the Orchestrator's whole REST API, about 1,200 operations on 9.7 / 10.0, by reading the API spec the Orchestrator itself serves. You ask in plain language ("which appliances on the lab are unreachable?") and the assistant finds the right operation and calls it.

- **Read-only unless you opt in**, per Orchestrator, with a blocklist of high-risk writes on top, and every write needs a second, confirmed call.
- **Secrets never reach the assistant.** Keys, passwords, PSKs and SNMP community strings come back redacted and are restored only when written back to where they came from.
- **Every call is audited** to a local JSON-lines log, and optionally to syslog and SQLite.
- **No dependencies.** Pure Python 3.9+ standard library. Runs over stdio, locally, over SSH or in a container, or as an HTTP endpoint behind an HTTPS proxy.
- **Current MCP spec.** Speaks MCP 2026-07-28 (stateless, `server/discover`) and still answers older clients that open with `initialize` (2025-11-25 back to 2024-11-05).
- **Comes with a guide skill** that tells the assistant which official docs and tested operations to use for each feature.

It reads the same `.env` format as [edgeconnect-orchestrator-automation](https://github.com/Crypto-Gi/edgeconnect-orchestrator-automation), so one `.env` can serve both. For bulk firewall and object changes, use that project's CSV workflows instead: they add drift checks, readback and rollback that raw `api_write` calls do not.

## Choose what to install

| You want | Install |
|---|---|
| The MCP server and the guide skill in Claude Code | The [Claude Code plugin](#quick-start-claude-code): one install sets up both |
| The MCP server only, for any client | One [server command](#install-the-server), then [connect your client](docs/clients.md) |
| The guide skill in another agent (Codex, OpenCode, VS Code, Cursor, Windsurf, Devin and more) | [`npx skills add`](#add-the-guide-skill), plus the server above |

Everything installs straight from this GitHub repository, pinned to release `v0.2.0`, so a later change to the repository never reaches you until you change the version in the command. New versions are listed under [Releases](https://github.com/Crypto-Gi/edgeconnect-mcp/releases).

**Requirements:** Python 3.9 or later for the server, on Linux, macOS or Windows. Node.js 18+ for the `npx` commands; uv, pipx or Docker only for those routes. You also need an Orchestrator REST API key.

## Quick start (Claude Code)

1. Create your settings file and keep it private:

   ```bash
   mkdir -p ~/.edgeconnect-mcp
   curl -fsSL https://raw.githubusercontent.com/Crypto-Gi/edgeconnect-mcp/v0.2.0/.env.example -o ~/.edgeconnect-mcp/.env
   chmod 600 ~/.edgeconnect-mcp/.env
   ```

2. Fill in one Orchestrator (see [Configuration](#configuration) for the rest):

   ```dotenv
   orch_1=lab
   lab_base_url=https://192.0.2.10
   lab_api_key=<API_KEY>
   ```

3. Install the plugin. It runs the server with `python3` and reads `~/.edgeconnect-mcp/.env`:

   ```bash
   claude plugin marketplace add 'Crypto-Gi/edgeconnect-mcp#v0.2.0'
   claude plugin install edgeconnect@edgeconnect-mcp
   ```

   Inside Claude Code the same is `/plugin marketplace add Crypto-Gi/edgeconnect-mcp#v0.2.0`, then `/plugin install edgeconnect@edgeconnect-mcp`.

4. Restart Claude Code and ask: "list my EdgeConnect orchestrators", then "show the appliances on lab".

## Install the server

Pick one. Each gives you the `edgeconnect-mcp` command; pass it `--dotenv /absolute/path/.env`, or set `EDGECONNECT_DOTENV`. Without either, it reads `./.env`. Process environment variables override the file, so `--env-file` style setups work too.

| Route | Command |
|---|---|
| npx (runs the bundled Python server) | `npx -y github:Crypto-Gi/edgeconnect-mcp#v0.2.0 --dotenv /absolute/path/.env` |
| uvx | `uvx --from git+https://github.com/Crypto-Gi/edgeconnect-mcp@v0.2.0 edgeconnect-mcp --dotenv /absolute/path/.env` |
| pipx | `pipx install git+https://github.com/Crypto-Gi/edgeconnect-mcp@v0.2.0` |
| Docker | `docker build -t edgeconnect-mcp https://github.com/Crypto-Gi/edgeconnect-mcp.git#v0.2.0`, then `docker run -i --rm --env-file /absolute/path/.env edgeconnect-mcp` |

Or clone and install into a virtual environment. Upgrading pip matters on macOS's built-in Python 3.9, whose pip is too old for editable installs:

```bash
git clone --branch v0.2.0 https://github.com/Crypto-Gi/edgeconnect-mcp.git
cd edgeconnect-mcp
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
cp .env.example .env && chmod 600 .env
```

The npx route looks for `python3` (or `python`) on `PATH`; set `EDGECONNECT_PYTHON` to use another interpreter.

Register the command with your client. For Claude Code:

```bash
claude mcp add edgeconnect -- uvx --from git+https://github.com/Crypto-Gi/edgeconnect-mcp@v0.2.0 edgeconnect-mcp --dotenv /absolute/path/.env
```

[docs/clients.md](docs/clients.md) has the config for Claude Desktop, Codex, OpenCode, VS Code, Cursor, Windsurf and Devin. To run the server on another machine or behind an HTTPS proxy, see [Remote access](#remote-access).

## Tools

| Tool | What it does |
|---|---|
| `list_orchestrators` | Configured nicknames, host, and whether writes are enabled. Never shows keys. |
| `find_operations` | Keyword search over the Orchestrator's own API spec. |
| `describe_operation` | Parameters and request-body schema for one operation. |
| `api_get` | Any documented GET. |
| `api_write` | Any documented POST, PUT, PATCH or DELETE, only on Orchestrators with writes enabled. |

Paths are relative to `/gms/rest`, for example `/appliance` or `/gms/versions`. Responses are truncated to `max_chars` (default 60,000) so one call cannot flood the conversation.

## Guide skill

`skills/edgeconnect-guide/` is a skill that tells an assistant where to look before it calls these tools. It is an index, not a copy of the docs:

- **Cards:** for each feature, a card with the official doc pages, a few key facts and the operations that touch it.
- **Playbooks:** for common jobs, such as adding a BGP neighbor or a segment, a playbook that reads current state before writing and says how to roll back.

The playbooks are for reference only. Every operation the skill names passed in a real run on Orchestrator 9.7.1 between 2026-10-16 and 2026-10-18 (listed in `tested-operations.tsv`). Steps that could not be tested were left out, or point to the Orchestrator UI.

### Add the guide skill

- **Claude Code:** the [plugin](#quick-start-claude-code) includes it.
- **Other agents:** the open [`skills`](https://github.com/vercel-labs/skills) installer copies it into each agent's skills folder:

  ```bash
  npx skills add https://github.com/Crypto-Gi/edgeconnect-mcp.git#v0.2.0                                     # pick agents interactively
  npx skills add https://github.com/Crypto-Gi/edgeconnect-mcp.git#v0.2.0 -a codex opencode windsurf devin -y  # or name them
  npx skills add https://github.com/Crypto-Gi/edgeconnect-mcp.git#v0.2.0 -g -a claude-code -y                # -g: for your user, not this project
  ```

  It supports Claude Code, Codex, OpenCode, GitHub Copilot (VS Code), Cursor, Windsurf, Devin for Terminal and about 50 more.
- **claude.ai:** zip the folder from a clone, then upload it in Settings > Capabilities > Skills:

  ```bash
  cd skills && zip -r ../edgeconnect-guide.zip edgeconnect-guide -x '*/__pycache__/*'
  ```

- **By hand:** copy `skills/edgeconnect-guide` into the agent's skills folder, for example `~/.claude/skills/`.

`scripts/check_links.py` checks the cards and playbooks:

- their format;
- that every link is in a doc inventory;
- that every operation is in `tested-operations.tsv` and exists in an Orchestrator's API spec;
- that every playbook carries the reference-only notice.

It can also HTTP-check developer portal links. HPE techdocs refuse scripted requests, so those links are not HTTP-checked.

```bash
python3 skills/edgeconnect-guide/scripts/check_links.py --inventory <inventory>/*.tsv --spec <apiDocs.json> --http
```

## Safety model

- **Read-only by default.** `api_write` is refused unless `.env` has `<nickname>_mcp_writes=true` for that Orchestrator. Turn it on only for lab Orchestrators, or deliberately.
- **Raw passthroughs need a second opt-in.** `/appliance/rest` and `/broadcastCli` forward any request to an appliance's own API or CLI, so the spec cannot limit what they change. Writes through them also need `<nickname>_mcp_passthrough=true`.
- **Spec allowlist.** Every call must match a method and path in the spec the Orchestrator serves (`/gms/rest/apiDocs`, the same one Support > REST APIs shows). Undocumented paths, `..`, encoded separators and anything that would leave `/gms/rest` are rejected.
- **Separate read and write tools.** `api_write` is marked destructive, so MCP clients ask before each call; reads can be auto-approved.
- **Two-step writes, on by default.** The first `api_write` call sends nothing: it returns the exact change and a one-time code. The assistant shows you the change and, only after your yes, repeats the identical call with the code. A code works once, for 10 minutes, for that exact request and for the client it was issued to. Set `<nickname>_mcp_confirm_writes=false` to turn it off for an Orchestrator, for example for trusted unattended automation.
- **High-risk blocklist.** Even with writes on, whole categories of dangerous writes are refused. See [below](#high-risk-blocklist).
- **Secret redaction.** API keys are only sent as the `X-Auth-Token` header, and secrets in responses are replaced with restorable tokens. See [below](#secret-redaction).
- **Rate limits per Orchestrator.** Reads default to 10 per second and writes to 2 per second, each with a burst of twice that. Over the limit, calls wait rather than fail, so scripts slow down instead of breaking.
- **Audit trail.** Every tool call is appended as one JSON line to `~/.edgeconnect-mcp/audit.jsonl` (file 0600, folder 0700): UTC timestamp and weekday, session and call id, client address, tool, Orchestrator, method, path, what the operation does (its API summary), for writes the step (`awaiting_confirmation`, `confirmed` or `executed`) and the request body, redacted query, outcome, error, duration and response size. Secrets never reach it: bodies hold `<REDACTED:…>` tokens, and anything typed in clear under a secret-named key is masked. Optionally the same records also go to a syslog server (`mcp_audit_syslog`) and a SQLite database (`mcp_audit_sqlite`). In HTTP mode, requests turned away for a wrong token, client address or origin are logged too (`tool` is `http_refused`, with the client address and the reason, never the token). Every write is also logged to stderr (the MCP client's server log).
- **Untrusted results.** API results carry a note that their text is data, not instructions, and the server instructions say the same. Invisible and direction-changing characters (zero-width, bidi overrides, Unicode tag characters) are shown as `\uXXXX` JSON escapes, so hidden text is visible while the value still decodes exactly.
- **Strict TLS.** Certificates are verified and redirects are refused, so the API key can't follow a redirect to another host or to plain HTTP. A self-signed lab Orchestrator is supported by pinning its certificate (`<nickname>_tls_sha256`) or trusting a private CA (`<nickname>_ca_bundle`), never by turning verification off.
- **No network listener by default.** The server uses stdio unless you pass `--http`. HTTP listens on 127.0.0.1 unless `mcp_http_listen` says otherwise (the container image sets 0.0.0.0). Every request needs the token and is checked against the address allowlist on its own; requests run in parallel, up to 8 at once, and more get a 503 to retry.

### High-risk blocklist

These writes are refused unless `<nickname>_mcp_allow_high_risk` names their category (comma-separated, or `all`):

| Category | Covers |
|---|---|
| `auth` | Users, roles, RBAC, remote auth (TACACS, RADIUS, JWT), API keys, sessions |
| `certificates` | Certs, SSL/TLS, ciphers, EST and end-entity profiles, HTTPS |
| `licensing` | Licensing |
| `backup_restore` | Backup and restore |
| `upgrade` | Upgrades, ECOS image management |
| `reboot` | Reboot, shutdown, restart, factory reset |
| `orchestrator_ha` | Orchestrator HA, including failover |
| `appliance_lifecycle` | Add, delete, approve/deny/revoke, change password, EdgeHA, hostname, SSE connector, passthrough DELETE |
| `cloud_deployment` | AWS, Azure and GCP resources |
| `provisioning` | Preconfiguration apply, appliance and RMA wizards, ZTP, portal and support-case calls, registration, account keys |
| `orchestrator_admin` | Session timeout, REST API config, advanced properties and settings, SMTP and email actions, host OS settings, debug files, DB partitions |
| `identity_events` | ClearPass login/logout events |
| `cli` | `broadcastCli`, tcpdump, shell |
| `ip_allowlist` | IP allowlist |
| `traffic_disruptive` | Network memory erase, flow reset, DHCP config reset |

Punctuation is ignored when matching (`edge-ha` = `edgeha`), and passthrough writes are also checked against their `url`. Plain lookups stay allowed in the certificate, licensing, upgrade, auth and backup areas: an operation named `validate…`, `check…` or `parse…`, or one whose summary starts with validate, verify, check or parse.

To see exactly what the list refuses on one Orchestrator:

```bash
edgeconnect-mcp --dotenv .env --list-high-risk lab
```

### Secret redaction

String values under keys such as `apiKey`, `password`, `token`, `presharedKey`, `authKey`, `privateKey`, `accountKey` and `rocommunity`, and any PEM private key, come back as `<REDACTED:…>` tokens. Redaction goes by field name. The names were checked against every property in the 9.7.1 API spec that is described as a password, secret, key, community string or credential; a test covers a list of them, but it does not read the spec itself, so a field added in a later release can slip through. Flags and numbers (`passwordMinLen`, `csrfProtection`) stay readable.

Write a token back unchanged and the server puts the real value in, so read-modify-write of BGP, OSPF, overlays or tunnels round-trips exactly. A token is only restored under the same key it was read from, on the same API path or a parent or child of it (for appliance passthrough, the same `url`), on the same Orchestrator, during the same server run. Anything else is refused: a plain `<REDACTED>`, a token moved into a readable field or another feature's secret field, or a token from another Orchestrator or an earlier run. So a secret can never be overwritten with a placeholder or copied somewhere it could leak.

## Configuration

All settings live in `.env` ([`.env.example`](.env.example) has every key). Never commit it. Each Orchestrator gets a numbered slot and a nickname, and the nickname prefixes its settings:

```dotenv
orch_1=lab
lab_base_url=https://192.0.2.10
lab_api_key=<API_KEY>
lab_mcp_writes=true
lab_tls_sha256=<SHA-256 fingerprint>
```

| Key | Default | Meaning |
|---|---|---|
| `orch_<n>` | | Nickname for Orchestrator slot `n` |
| `<nickname>_base_url` | | `https://` address of the Orchestrator |
| `<nickname>_api_key` | | REST API key |
| `<nickname>_api_key_header` | `X-Auth-Token` | Header the key is sent in |
| `<nickname>_tls_sha256` | | Pin a self-signed certificate by its SHA-256 fingerprint |
| `<nickname>_ca_bundle` | | Private CA file for certificate verification |
| `<nickname>_mcp_writes` | off | `true` allows `api_write` |
| `<nickname>_mcp_passthrough` | off | `true` also allows writes through `/appliance/rest` and `/broadcastCli` |
| `<nickname>_mcp_confirm_writes` | on | `false` turns off two-step writes for that Orchestrator |
| `<nickname>_mcp_allow_high_risk` | none | Blocklist categories to allow, comma-separated, or `all` |
| `<nickname>_mcp_read_rate` | `10` | Reads per second, `0` = no limit |
| `<nickname>_mcp_write_rate` | `2` | Writes per second, `0` = no limit |
| `<nickname>_openapi` | download | Path to a saved `apiDocs.json` instead of downloading the spec on first use |
| `orch_default` | | Orchestrator used when a tool call names none |
| `mcp_audit_log` | `~/.edgeconnect-mcp/audit.jsonl` | Audit log path, or `off` |
| `mcp_audit_syslog` | none | Also send audit records to syslog: `/dev/log`, `udp://host:514` or `tcp://host:514` |
| `mcp_audit_sqlite` | none | Also write audit records to this SQLite database |

HTTP mode has its own keys (`mcp_http_token`, `mcp_http_allowed_clients`, `mcp_http_trusted_proxies`, `mcp_http_listen` and more); see [docs/remote-access.md](docs/remote-access.md#http-mode).

Get a certificate fingerprint to pin (check it on the Orchestrator console or another trusted path first):

```bash
openssl s_client -connect 192.0.2.10:443 </dev/null 2>/dev/null | openssl x509 -noout -fingerprint -sha256
```

## Remote access

Plain HTTP never crosses the network. [docs/remote-access.md](docs/remote-access.md) covers:

- **Over SSH:** the client starts the server over SSH, with one locked-down key per access level.
- **HTTP mode:** a token, a client allowlist and trusted proxies, all set in `.env`.
- **Caddy:** HTTPS in front of a server running directly on the machine.
- **Container:** stdio with `docker run -i`, or HTTP mode with `compose.yaml` published on the host's 127.0.0.1.
- **Nginx Proxy Manager:** HTTPS in front of the server container, on a shared Docker network.

## Orchestrator API notes

Found while driving a 9.7.1 Orchestrator with five ECOS 9.6/9.7 appliances through this server:

- Operations whose spec accepts only `text/plain` (Zscaler countries/timezones) take a plain string `body`, which `api_write` sends raw; a JSON-accepting operation gets it JSON-encoded.
- Deployment, BGP, OSPF, VRRP, static routes and IP SLA have no Orchestrator write operation in the 9.7.1 spec. Read the appliance's own config with `GET /appliance/rest?nePk=<NE>&url=<path>` (`deployment`, `subnets3/configured`, `bgp/config/neighbor`, `ospf/config/system`, `vrrp`, `ipsla/config/managers`), All of these reads are tested. As a write, posting the whole object back with `POST /appliance/rest` has been tested only for `bgp/config/neighbor`; check a deployment change with `POST /deployment/validate` and make it in the Orchestrator UI. `subnets/configured` returns 410; use `subnets3/configured`.
- Overlay `PUT /gms/overlays/config` is refused with 400 unless `multiCrossConnect` only names labels in the primary or backup list. On 9.7.1 a full-object post reads back equal; only partial bodies read back different, so compare intent fields. `topologyType` 1 is mesh and 2 is hub-and-spoke.
- `GET /gms/overlays/config/regions`: always pass both `overlayId` and `regionId` (one 9.7.1 Orchestrator accepted no parameters, another refused that with 400).
- User-defined applications are read with `GET /applicationDefinition?...&resourceKey=userDefined`; without it the call returns 200 with `{"result":"Not found"}`.
- LAN subnets in a non-default segment are not advertised until that VRF is added with `add_local_lan` via `POST /subnets/setSubnetSharingOptions`.
- Zone names allow only letters, digits and `_`. Zones and segment security policies are whole-collection writes: read, add, write back.

## Development

Run the tests from the repository root (they use only the standard library):

```bash
.venv/bin/python -m unittest discover -s tests
```

The tests read `./.env` if one exists, so move your real `.env` out of the repository root first, or the run fails on its Orchestrators.

## License

[Apache License 2.0](LICENSE). See [NOTICE](NOTICE) for the trademark and no-affiliation notice.
