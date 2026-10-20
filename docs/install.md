# Other ways to install

The [README](../README.md#install) covers the usual setup: a settings file at `~/.edgeconnect-mcp/.env`, then the Claude Code plugin or `npx`. This page has the alternatives.

## Where the server finds its settings

It reads the first of these that is set or exists:

1. `--dotenv /absolute/path/.env`
2. the `EDGECONNECT_DOTENV` environment variable
3. `~/.edgeconnect-mcp/.env` (on Windows, `%USERPROFILE%\.edgeconnect-mcp\.env`)
4. `./.env` in the folder the server is started in

Process environment variables override the file, so `docker run --env-file` style setups work too.

## Other server commands

Each of these runs the same server as `npx -y github:Crypto-Gi/edgeconnect-mcp`. Use whichever tool you already have.

| Route | Command |
|---|---|
| uvx | `uvx --from git+https://github.com/Crypto-Gi/edgeconnect-mcp edgeconnect-mcp` |
| pipx | `pipx install git+https://github.com/Crypto-Gi/edgeconnect-mcp`, then `edgeconnect-mcp` |
| Docker | `docker build -t edgeconnect-mcp https://github.com/Crypto-Gi/edgeconnect-mcp.git`, then `docker run -i --rm --env-file /absolute/path/.env edgeconnect-mcp` |

The npx route looks for `python3` (or `python`) on `PATH`; set `EDGECONNECT_PYTHON` to use another interpreter. The Docker image doesn't see your home folder, so it takes its settings from `--env-file`.

Or clone and install into a virtual environment. Upgrading pip matters on macOS's built-in Python 3.9, whose pip is too old for editable installs:

```bash
git clone https://github.com/Crypto-Gi/edgeconnect-mcp.git
cd edgeconnect-mcp
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
```

To run the server on another machine or behind an HTTPS proxy, see [Remote access](remote-access.md).

## Pin a release

The usual commands follow `main`. To stay on one release, add its tag from [Releases](https://github.com/Crypto-Gi/edgeconnect-mcp/releases), shown here as `<tag>`:

| Install | Pinned form |
|---|---|
| Claude Code plugin | `claude plugin marketplace add 'Crypto-Gi/edgeconnect-mcp#<tag>'` |
| npx | `npx -y github:Crypto-Gi/edgeconnect-mcp#<tag>` |
| uvx | `uvx --from git+https://github.com/Crypto-Gi/edgeconnect-mcp@<tag> edgeconnect-mcp` |
| Guide skill | `npx skills add https://github.com/Crypto-Gi/edgeconnect-mcp.git#<tag>` |
| Settings template | `https://raw.githubusercontent.com/Crypto-Gi/edgeconnect-mcp/<tag>/.env.example` |

## Guide skill options

`npx skills add Crypto-Gi/edgeconnect-mcp` uses the open [`skills`](https://github.com/vercel-labs/skills) installer, which supports Claude Code, Codex, OpenCode, GitHub Copilot (VS Code), Cursor, Windsurf, Devin for Terminal and about 50 more. To skip its questions:

```bash
npx skills add Crypto-Gi/edgeconnect-mcp -a codex opencode -y        # name the agents, this project only
npx skills add Crypto-Gi/edgeconnect-mcp -g -a claude-code -y        # -g: for your user, every project
```

- **claude.ai:** zip the folder from a clone, then upload it in Settings > Capabilities > Skills:

  ```bash
  cd skills && zip -r ../edgeconnect-guide.zip edgeconnect-guide -x '*/__pycache__/*'
  ```

- **By hand:** copy `skills/edgeconnect-guide` into the agent's skills folder, for example `~/.claude/skills/`.

## Update

- **Claude Code plugin:** `claude plugin marketplace update edgeconnect-mcp && claude plugin update edgeconnect@edgeconnect-mcp`. The plugin moves when a release raises its version.
- **Guide skill:** run the same `npx skills add` command again; it replaces the installed copy.
