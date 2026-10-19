FROM python:3.12-slim

# The server is pure standard library, so no pip install is needed.
COPY src/edgeconnect_mcp /app/edgeconnect_mcp
RUN useradd --create-home --uid 10001 mcp
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1
# HTTP mode (--http) must listen beyond the container's own loopback; who may connect is still
# limited by the token and mcp_http_allowed_clients / mcp_http_trusted_proxies in .env.
ENV MCP_HTTP_LISTEN=0.0.0.0

USER mcp
ENTRYPOINT ["python", "-m", "edgeconnect_mcp"]
