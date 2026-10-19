# Remote access

Plain HTTP never crosses the network. A client on another machine reaches the server in one of two ways:

- **Over SSH** (simplest). The client starts the server over SSH, and nothing new listens on the network.
- **Over HTTPS.** The server runs in HTTP mode, and a reverse proxy (Caddy or Nginx Proxy Manager) terminates HTTPS in front of it.

The [Caddy](#caddy), [container](#run-in-a-container) and [Nginx Proxy Manager](#nginx-proxy-manager) setups below were tested end to end (Caddy 2.10.2, Nginx Proxy Manager 2.12.6): calls through the proxy work, a client outside the allowlist is refused, and so is one that fakes `X-Forwarded-For`.

## Over SSH

Install the server on one machine that can reach the Orchestrators, and let your MCP client start it over SSH. SSH does the encryption and login.

On the server machine:

- Use a dedicated user (here `mcp`) with key login only.
- Keep each `.env` readable only by that user (`chmod 600`).
- In `~mcp/.ssh/authorized_keys`, lock each key to the MCP server so it can't open a shell or forward ports.
- Use one key per access level, each with its own `.env`:

```text
command="/home/mcp/edgeconnect-mcp/.venv/bin/edgeconnect-mcp --dotenv /home/mcp/read-only.env",restrict ssh-ed25519 AAAA... laptop-read
command="/home/mcp/edgeconnect-mcp/.venv/bin/edgeconnect-mcp --dotenv /home/mcp/lab-write.env",restrict ssh-ed25519 AAAA... laptop-lab-write
```

Here `read-only.env` lists Orchestrators without `_mcp_writes`, and `lab-write.env` turns writes on for the lab only. The audit log records the SSH client address of each call.

On your machine, in Claude Code:

```bash
claude mcp add edgeconnect -- ssh -T -o BatchMode=yes -i ~/.ssh/edgeconnect_read mcp@mcp-host
```

In Claude Desktop:

```json
{
  "mcpServers": {
    "edgeconnect": {
      "command": "ssh",
      "args": ["-T", "-o", "BatchMode=yes", "-i", "/Users/you/.ssh/edgeconnect_read", "mcp@mcp-host"]
    }
  }
}
```

`BatchMode=yes` makes a missing key fail instead of hanging on a password prompt.

## HTTP mode

`edgeconnect-mcp --http 8765` serves MCP (streamable HTTP, JSON responses) at `http://127.0.0.1:8765/mcp`. Clients on MCP 2026-07-28 send `MCP-Protocol-Version`, `Mcp-Method` and `Mcp-Name` headers, which must match the request body; Caddy and nginx pass them through unchanged. Add these keys to `.env`:

```dotenv
# Required. At least 32 characters: python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
mcp_http_token=<read-write token>
# Optional: a second token that can read but never call api_write.
# mcp_http_read_token=<read-only token>
# Networks allowed to connect (IPs or subnets). Default: only this machine.
# mcp_http_allowed_clients=127.0.0.1,::1,10.1.2.0/24
# Proxies whose X-Forwarded-For header is believed. Default: only this machine.
# mcp_http_trusted_proxies=127.0.0.1,::1
# Address to listen on. Default 127.0.0.1; the container image sets 0.0.0.0.
# mcp_http_listen=127.0.0.1
# Browser origins allowed to call it. Default: none.
# mcp_http_allowed_origins=
```

Every request needs `Authorization: Bearer <token>`. The server refuses to start if the token is short or `.env` is readable by other users. It refuses any request that:

- carries a browser `Origin` that isn't on the list;
- comes from a client address that isn't on the list (the error names the address it saw);
- isn't `POST /mcp` with a JSON body;
- has a body over 2 MB.

It drops a connection that stalls for 30 seconds, and serves requests in parallel (up to 8 at once; more get a 503 with `Retry-After`).

**How the client address is found.** When the request comes straight from a trusted proxy (`mcp_http_trusted_proxies`), the client is the last entry of that proxy's `X-Forwarded-For` header. Otherwise the client is the connecting address, and any `X-Forwarded-For` it sends is ignored. So a client can't claim an allowed address by sending the header itself. A write confirmation code only works for the address found this way, so everyone who reaches the server through one address (every client behind a Docker bridge, say) shares it. The token remains the real access control, and the address list is a second check.

Point your client at the proxy's URL. In Claude Code:

```bash
claude mcp add --transport http edgeconnect https://mcp.example.internal/mcp --header "Authorization: Bearer <token>"
```

## Caddy

This runs the server directly on the machine (any [install](../README.md#install-the-server)) and Caddy on the same machine.

1. Start the server in HTTP mode, on 127.0.0.1:

   ```bash
   edgeconnect-mcp --http 8765 --dotenv ~/.edgeconnect-mcp/.env
   ```

2. Put this in your `Caddyfile`. `tls internal` uses Caddy's own CA, which suits an internal name. For a public DNS name, drop that line and Caddy gets a Let's Encrypt certificate.

   ```caddyfile
   mcp.example.internal {
   	tls internal
   	reverse_proxy 127.0.0.1:8765 {
   		request_buffers 4MB
   	}
   }
   ```

   `request_buffers` makes Caddy send a `Content-Length` header. Without it, a client that streams its request (some HTTP/2 clients do) gets `411 send a Content-Length body, not chunked`, because the server does not accept chunked bodies.

3. Run Caddy. If you run Caddy in Docker, it needs host networking to reach the server on 127.0.0.1:

   ```bash
   docker run -d --name caddy --network host -v "$PWD/Caddyfile:/etc/caddy/Caddyfile:ro" -v caddy_data:/data caddy:2.10.2
   ```

4. Allow your clients' networks in `.env`, then restart the server:

   ```dotenv
   mcp_http_allowed_clients=127.0.0.1,::1,10.1.2.0/24
   ```

Caddy sets `X-Forwarded-For` from the real peer, and arrives from 127.0.0.1, so the default `mcp_http_trusted_proxies` already fits.

## Run in a container

The image runs as a non-root user and needs nothing from PyPI. Build it from a clone:

```bash
git clone --branch v0.2.0 https://github.com/Crypto-Gi/edgeconnect-mcp.git
cd edgeconnect-mcp
docker build -t edgeconnect-mcp .
```

**stdio.** The MCP client starts the container. Pass settings with `--env-file`:

```bash
docker run -i --rm --env-file /absolute/path/.env edgeconnect-mcp
```

Claude Code:

```bash
claude mcp add edgeconnect -- docker run -i --rm --env-file /absolute/path/.env edgeconnect-mcp
```

**HTTP.** `compose.yaml` in the repository runs HTTP mode and publishes port 8765 on the host's 127.0.0.1 only. Inside the container the server listens on 0.0.0.0, so connections arrive from Docker's network rather than from 127.0.0.1. Allow the address the server sees in `.env`; the refusal message names it.

```bash
cp .env.example .env    # add an Orchestrator and mcp_http_token
chmod 600 .env
docker compose up -d
```

The audit log is kept in the `audit` volume.

## Nginx Proxy Manager

Nginx Proxy Manager (NPM) and the server both run in Docker, on a shared network with a fixed subnet. NPM reaches the server by its service name.

1. In your clone, replace `compose.yaml` with:

   ```yaml
   services:
     edgeconnect-mcp:
       build: .
       command: ["--http", "8765"]
       env_file: .env
       networks: [proxy]
     npm:
       image: jc21/nginx-proxy-manager:2.12.6
       environment:
         DISABLE_IPV6: "true"  # only where the host has no IPv6
       ports: ["80:80", "443:443", "127.0.0.1:81:81"]
       volumes: ["npm_data:/data", "npm_letsencrypt:/etc/letsencrypt"]
       networks: [proxy]
   networks:
     proxy:
       ipam:
         config: [{subnet: 172.30.0.0/24}]
   volumes:
     npm_data:
     npm_letsencrypt:
   ```

2. In `.env`, trust NPM's network and allow your clients:

   ```dotenv
   mcp_http_token=<read-write token>
   mcp_http_trusted_proxies=172.30.0.0/24
   mcp_http_allowed_clients=10.1.2.0/24
   ```

3. Run `docker compose up -d`. Then open the admin UI at `http://127.0.0.1:81` and change the default login.

4. Add a proxy host:
   - **Details:** domain `mcp.example.internal`, scheme `http`, forward hostname `edgeconnect-mcp`, forward port `8765`. Turn on Block Common Exploits.
   - **SSL:** upload your certificate (Custom; this is what was tested), or request a Let's Encrypt one for a public name. Turn on Force SSL.

NPM appends the real client to `X-Forwarded-For`. The server believes that header only because NPM connects from the trusted `172.30.0.0/24`. Plain HTTP on port 80 is redirected to HTTPS.
