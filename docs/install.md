# Install guide

edgeconnect-mcp has three parts:

- **The server** gives your assistant the tools to talk to your Orchestrator. The same command also runs `edgeconnect-mcp report`, which builds reports.
- **The guide skill** (`edgeconnect-guide`) tells your assistant how to use those tools well: which docs to read, which operations were tested, how to roll back.
- **The report skill** (`edgeconnect-report`) tells your assistant how to build a report with `edgeconnect-mcp report`.

## Pick your route

| You use | Do this | Server needs |
|---|---|---|
| Claude Code | [Claude Code plugin](#claude-code-plugin): one command installs both parts | Python 3.9+ |
| Any other client, or Claude Code without the plugin | [npx](#npx) | Python 3.9+ and Node.js 18+ |
| No Node.js | [uvx, pipx or a clone](#uvx-pipx-or-a-clone) | Python 3.9+ and uv or pipx |
| Docker | [Docker](#docker) | Docker |

Every route except Docker reads the same settings file, so do step 0 first.

## Step 0: create your settings file (once)

```bash
curl -fsSL --create-dirs -o ~/.edgeconnect-mcp/.env https://raw.githubusercontent.com/Crypto-Gi/edgeconnect-mcp/main/.env.example
chmod 600 ~/.edgeconnect-mcp/.env
```

Open `~/.edgeconnect-mcp/.env` and fill in your Orchestrator:

```dotenv
orch_1=lab
lab_base_url=https://<ORCHESTRATOR_FQDN_OR_IP>
lab_api_key=<API_KEY>
```

HPE's [API Key](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/orchestrator/server/api-key/) page shows how to create the key. Give it Read-Only permission unless you plan to turn writes on. On Windows, save [.env.example](../.env.example) as `%USERPROFILE%\.edgeconnect-mcp\.env` instead.

## Claude Code plugin

**Step 1.** Install the plugin. It brings the server and both skills:

```bash
claude plugin marketplace add Crypto-Gi/edgeconnect-mcp && claude plugin install edgeconnect@edgeconnect-mcp
```

**Step 2.** Restart Claude Code and [check it works](#check-it-works).

To update later:

```bash
claude plugin marketplace update edgeconnect-mcp && claude plugin update edgeconnect@edgeconnect-mcp
```

## npx

The server command is `npx -y github:Crypto-Gi/edgeconnect-mcp`. It needs nothing else from you, because the server finds `~/.edgeconnect-mcp/.env` by itself.

**Step 1.** Add the server to your client:

| Client | Run this |
|---|---|
| Claude Code | `claude mcp add --scope user edgeconnect -- npx -y github:Crypto-Gi/edgeconnect-mcp` |
| Codex | `codex mcp add edgeconnect -- npx -y github:Crypto-Gi/edgeconnect-mcp` |
| Claude Desktop, OpenCode, VS Code, Cursor, Windsurf, Devin | Paste the config from [clients.md](clients.md) |

`--scope user` makes the server available in every Claude Code project, not just the current folder.

**Step 2.** Add the skills for the same agent:

| Agent | Run this |
|---|---|
| Claude Code | `npx skills add Crypto-Gi/edgeconnect-mcp -g -a claude-code -y` |
| Codex | `npx skills add Crypto-Gi/edgeconnect-mcp -g -a codex -y` |
| Any other, or several at once | `npx skills add Crypto-Gi/edgeconnect-mcp` (asks which agents) |

`-g` installs them for your user, so every project sees them. Leave `-g` out to install them in the current project only. More options are under [Skills](#skills).

**Step 3.** Restart your client and [check it works](#check-it-works).

## uvx, pipx or a clone

These run the same server without Node.js. Use the [npx](#npx) steps, but in step 1 replace `npx -y github:Crypto-Gi/edgeconnect-mcp` with one of these:

| Tool | Server command |
|---|---|
| uvx | `uvx --from git+https://github.com/Crypto-Gi/edgeconnect-mcp edgeconnect-mcp` |
| pipx | run `pipx install git+https://github.com/Crypto-Gi/edgeconnect-mcp` once; the command is then `edgeconnect-mcp` |
| A clone | set it up as below; the command is then `/absolute/path/to/edgeconnect-mcp/.venv/bin/edgeconnect-mcp` |

For example, uvx in Claude Code:

```bash
claude mcp add --scope user edgeconnect -- uvx --from git+https://github.com/Crypto-Gi/edgeconnect-mcp edgeconnect-mcp
```

To set up a clone. Upgrading pip matters on macOS's built-in Python 3.9, whose pip is too old for editable installs:

```bash
git clone https://github.com/Crypto-Gi/edgeconnect-mcp.git
cd edgeconnect-mcp
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
```

The skills (step 2) still install with `npx skills add`. Without Node.js, copy them [by hand](#skills).

## Docker

A container doesn't see your home folder, so Docker takes its settings from a `.env` file you point it at. Pick one of two ways.

### A. The client starts a container each time

**Step 1.** Build the image:

```bash
docker build -t edgeconnect-mcp https://github.com/Crypto-Gi/edgeconnect-mcp.git
```

**Step 2.** Add it to your client. The server command is `docker run -i --rm --env-file /absolute/path/.env edgeconnect-mcp`, for example:

```bash
claude mcp add --scope user edgeconnect -- docker run -i --rm --env-file /absolute/path/.env edgeconnect-mcp
```

**Step 3.** Add the skills (as in [npx](#npx) step 2), restart your client, and [check it works](#check-it-works).

### B. One container that keeps running

This keeps one server running in HTTP mode, and every client on the machine connects to it through `docker exec`. No client needs the HTTP token.

**Step 1.** Clone the repository and fill in its `.env`:

```bash
git clone https://github.com/Crypto-Gi/edgeconnect-mcp.git
cd edgeconnect-mcp
cp .env.example .env && chmod 600 .env
```

Besides your Orchestrator, HTTP mode needs `mcp_http_token` in this `.env`, at least 32 characters. Make one with `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'`.

**Step 2.** Start the container:

```bash
docker compose up -d
```

`compose.yaml` names it `edgeconnect-mcp` and publishes port 8765 on this machine's 127.0.0.1 only.

**Step 3.** Add it to your client. The server command is `docker exec -i edgeconnect-mcp python -m edgeconnect_mcp`:

| Client | Run this |
|---|---|
| Claude Code | `claude mcp add --scope user edgeconnect -- docker exec -i edgeconnect-mcp python -m edgeconnect_mcp` |
| Codex | `codex mcp add edgeconnect -- docker exec -i edgeconnect-mcp python -m edgeconnect_mcp` |
| JSON-config clients | Use the shape from [clients.md](clients.md) with `"command": "docker"` and `"args": ["exec", "-i", "edgeconnect-mcp", "python", "-m", "edgeconnect_mcp"]` |

**Step 4.** Add the skills (as in [npx](#npx) step 2), restart your client, and [check it works](#check-it-works).

To use the HTTP endpoint from another machine, put an HTTPS proxy in front of it: see [Remote access](remote-access.md).

## Check it works

Ask your assistant "list my EdgeConnect orchestrators". That calls `list_orchestrators`, which needs no network, and should return this, with your address as `host`:

```json
[{"name": "lab", "host": "192.0.2.10", "writes_enabled": false, "passthrough_writes_enabled": false,
  "write_confirmation": true, "read_posts_enabled": true, "high_risk_allowed": [], "default": true}]
```

Then ask "show the appliances on lab". That one reaches the Orchestrator, so a wrong address, key or certificate shows up there.

If the first question fails:

- `claude mcp list` (or `codex mcp list`) shows whether the client could start the server.
- `Orchestrator base URL and API key are required` means the server found no settings. Check `~/.edgeconnect-mcp/.env` exists and has your three lines, or, for Docker, the `--env-file` path.
- `needs Python 3.9 or later on PATH` comes from the npx route. Install Python, or set `EDGECONNECT_PYTHON` to the interpreter to use.

## How the server finds its settings

| How it runs | Settings come from |
|---|---|
| Plugin, npx, uvx, pipx, clone | The first of: `--dotenv /absolute/path/.env`, `$EDGECONNECT_DOTENV`, `~/.edgeconnect-mcp/.env`, `./.env` in the folder it starts in |
| `docker run --env-file` | The file you pass with `--env-file` |
| `docker compose` and `docker exec` | The `.env` next to `compose.yaml`, read when the container was created |

So it doesn't matter which folder you're in when you start your assistant. Environment variables with the same names override the file. `edgeconnect-mcp report` finds its settings the same way.

## Report command

The report skill runs `edgeconnect-mcp report ...`; `report` must come right after the command, before any option. Where `edgeconnect-mcp` is not on PATH, use one of these:

| Install | Report command |
|---|---|
| pipx, or a clone's `.venv` | `edgeconnect-mcp report ...` (or `.venv/bin/edgeconnect-mcp report ...`) |
| npx | `npx -y github:Crypto-Gi/edgeconnect-mcp report ...` |
| uvx | `uvx --from git+https://github.com/Crypto-Gi/edgeconnect-mcp edgeconnect-mcp report ...` |
| Claude Code plugin | the plugin adds no `edgeconnect-mcp` command; use the npx or uvx form |
| A clone, no install | `PYTHONPATH=src python3 -m edgeconnect_mcp report ...` from the clone |

`setup.sh`'s launcher runs it as `<folder>/bin/edgeconnect-mcp report ...` with the shared `.env`: a `--dotenv` before `report` is passed on to `collect` and `store`.

## Skills

The repository has two skills, `edgeconnect-guide` and `edgeconnect-report`. To install only one, add `-s <name>` to the commands below.

`npx skills add Crypto-Gi/edgeconnect-mcp` uses the open [`skills`](https://github.com/vercel-labs/skills) installer. It supports Claude Code, Codex, OpenCode, GitHub Copilot (VS Code), Cursor, Windsurf, Devin for Terminal and about 50 more. You can name several agents at once:

```bash
npx skills add Crypto-Gi/edgeconnect-mcp -g -a codex opencode cursor -y
```

To update them, run the same command again. It replaces the installed copies.

Without the installer:

- **claude.ai:** zip the guide skill's folder from a clone, then upload it in Settings > Capabilities > Skills. The report skill needs the `edgeconnect-mcp report` command on your own machine, so it does not fit there.

  ```bash
  cd skills && zip -r ../edgeconnect-guide.zip edgeconnect-guide -x '*/__pycache__/*'
  ```

- **By hand:** copy `skills/edgeconnect-guide` and `skills/edgeconnect-report` into the agent's skills folder, for example `~/.claude/skills/`.

## Pin a release

The commands above follow `main`, which only changes through pull requests that pass CI. To stay on one release, add its tag from [Releases](https://github.com/Crypto-Gi/edgeconnect-mcp/releases), shown here as `<tag>`:

| Install | Pinned form |
|---|---|
| Claude Code plugin | `claude plugin marketplace add 'Crypto-Gi/edgeconnect-mcp#<tag>'` |
| npx | `npx -y github:Crypto-Gi/edgeconnect-mcp#<tag>` |
| uvx | `uvx --from git+https://github.com/Crypto-Gi/edgeconnect-mcp@<tag> edgeconnect-mcp` |
| Skills | `npx skills add https://github.com/Crypto-Gi/edgeconnect-mcp.git#<tag>` |
| Docker | `docker build -t edgeconnect-mcp https://github.com/Crypto-Gi/edgeconnect-mcp.git#<tag>` |
| Settings template | `https://raw.githubusercontent.com/Crypto-Gi/edgeconnect-mcp/<tag>/.env.example` |
