# Connect an MCP client

Every client starts the same command. The examples use `uvx`; any server command from [Install the server](../README.md#install-the-server) works in its place (`npx -y github:Crypto-Gi/edgeconnect-mcp#v0.2.2`, a pipx or venv `edgeconnect-mcp`, or `docker run -i --rm --env-file …`). Use absolute paths, because clients don't start servers in your project folder.

```text
uvx --from git+https://github.com/Crypto-Gi/edgeconnect-mcp@v0.2.2 edgeconnect-mcp --dotenv /absolute/path/.env
```

Claude Code, Codex and OpenCode were tested with this server. The VS Code, Cursor, Windsurf and Devin entries use each client's documented MCP config format, with the same command.

## Claude Code

The [plugin](../README.md#quick-start-claude-code) installs the server and the guide skill together. To add only the server:

```bash
claude mcp add edgeconnect -- uvx --from git+https://github.com/Crypto-Gi/edgeconnect-mcp@v0.2.2 edgeconnect-mcp --dotenv /absolute/path/.env
```

## Claude Desktop

In `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "edgeconnect": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/Crypto-Gi/edgeconnect-mcp@v0.2.2", "edgeconnect-mcp", "--dotenv", "/absolute/path/.env"]
    }
  }
}
```

## Codex

```bash
codex mcp add edgeconnect -- uvx --from git+https://github.com/Crypto-Gi/edgeconnect-mcp@v0.2.2 edgeconnect-mcp --dotenv /absolute/path/.env
codex mcp list
```

## OpenCode

In `opencode.json` (project) or `~/.config/opencode/opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "edgeconnect": {
      "type": "local",
      "command": ["uvx", "--from", "git+https://github.com/Crypto-Gi/edgeconnect-mcp@v0.2.2", "edgeconnect-mcp", "--dotenv", "/absolute/path/.env"],
      "enabled": true
    }
  }
}
```

`opencode mcp list` should show `edgeconnect connected`.

## VS Code (GitHub Copilot)

In `.vscode/mcp.json`:

```json
{
  "servers": {
    "edgeconnect": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "git+https://github.com/Crypto-Gi/edgeconnect-mcp@v0.2.2", "edgeconnect-mcp", "--dotenv", "/absolute/path/.env"]
    }
  }
}
```

## Cursor and Windsurf

Cursor uses `~/.cursor/mcp.json` and Windsurf uses `~/.codeium/windsurf/mcp_config.json`, both in this shape:

```json
{
  "mcpServers": {
    "edgeconnect": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/Crypto-Gi/edgeconnect-mcp@v0.2.2", "edgeconnect-mcp", "--dotenv", "/absolute/path/.env"]
    }
  }
}
```

## Devin

Add a local (stdio) MCP server in Devin's MCP settings, with the command and arguments above.

## Clients that need a URL

Run the server in HTTP mode behind an HTTPS proxy, then give the client the URL and the token header. See [Remote access](remote-access.md#http-mode).
