# Connect an MCP client

Every client starts the same command, and the server reads `~/.edgeconnect-mcp/.env` (see [Install](../README.md#install)). Any server command from the [install guide](install.md) works in its place.

```text
npx -y github:Crypto-Gi/edgeconnect-mcp
```

Claude Code, Codex and OpenCode were tested with this server. The VS Code, Cursor, Windsurf and Devin entries use each client's documented MCP config format, with the same command.

## Claude Code

The [plugin](../README.md#2-install) installs the server and the guide skill together. To add only the server:

```bash
claude mcp add edgeconnect -- npx -y github:Crypto-Gi/edgeconnect-mcp
```

## Claude Desktop

In `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "edgeconnect": {
      "command": "npx",
      "args": ["-y", "github:Crypto-Gi/edgeconnect-mcp"]
    }
  }
}
```

## Codex

```bash
codex mcp add edgeconnect -- npx -y github:Crypto-Gi/edgeconnect-mcp
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
      "command": ["npx", "-y", "github:Crypto-Gi/edgeconnect-mcp"],
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
      "command": "npx",
      "args": ["-y", "github:Crypto-Gi/edgeconnect-mcp"]
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
      "command": "npx",
      "args": ["-y", "github:Crypto-Gi/edgeconnect-mcp"]
    }
  }
}
```

## Devin

Add a local (stdio) MCP server in Devin's MCP settings, with the command and arguments above.

## Clients that need a URL

Run the server in HTTP mode behind an HTTPS proxy, then give the client the URL and the token header. See [Remote access](remote-access.md#http-mode).
