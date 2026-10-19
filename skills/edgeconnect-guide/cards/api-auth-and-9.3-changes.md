# API authentication and the 9.3 endpoint change
## What it is
How callers authenticate to the Orchestrator REST API (API key or session with CSRF token), how Orchestrator-level and appliance-level APIs differ, and how the 9.3 rewrite of endpoint paths (path parameters became query parameters) explains old scripts and examples that fail. Includes the legacy (interop) switch and the Postman collection.
## Docs
- [API Key](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/orchestrator/server/api-key/) - key fields, permissions, expiry, IP allow list, header or query use (9.7)
- [Role Based Access Control](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/orchestrator/server/rbac/) - what a key or user may call (9.7)
- [Start Here](https://developer.arubanetworks.com/edgeconnect/docs/whats-new) - the 9.3 breaking change and what to review (9.3)
- [Authentication (CSRF Token and API Key)](https://developer.arubanetworks.com/edgeconnect/docs/authentication) - session login script, `orchCsrfToken`, creating keys (9.3)
- [Making API Requests](https://developer.arubanetworks.com/edgeconnect/docs/making-api-requests) - Orchestrator level versus appliance level, keys, base URLs (9.3)
- [Rest API Table for 9.3 Endpoints](https://developer.arubanetworks.com/edgeconnect/docs/rest-api-table-for-93) - every pre-9.3 path mapped to its 9.3 form (9.3)
- [Pre 9.3 Orchestrator API Endpoints](https://developer.arubanetworks.com/edgeconnect/docs/pre-93-orchestrator-api-end-points) - interop list and the legacy switch (9.3)
- [Postman Collection](https://developer.arubanetworks.com/edgeconnect/docs/postman-collection) - fork the HPE workspace and set variables (9.3)
- [Orchestrator and EdgeConnect API endpoints](https://developer.arubanetworks.com/edgeconnect/docs/aruba-orchestrator-and-edgeconnect-api-endpoints) - where the two API families live (9.3)
## Key facts
- Orchestrator API base is `https://<orchestrator>/gms/rest`; the MCP server's paths are relative to that (for example `/appliance`). The MCP server authenticates with a configured API key sent as the `X-Auth-Token` header (the default; `<nickname>_api_key_header` in `.env` can name another header), so no login or CSRF handling is needed in tool calls (9.7).
- Key styles: header `X-Auth-Token` or query parameter `apiKey`. A key has a name, Read-Only or Read-Write permission (or RBAC roles), optional expiry, active flag and an IP allow list; use one key per application (9.7).
- Session style: log in with `user`, `password`, `loginType` (0 local, 1 RADIUS, 2 TACACS); the reply sets cookie `orchCsrfToken`, which must be echoed as header `X-XSRF-TOKEN` when Enforce CSRF Check is on. Close the session with the logout call (9.3). The MCP server never needs this (9.7).
- Appliance level APIs (base `https://<appliance>/rest/json/`) need their own login per session (cookie `vxoaSessionID`) and a logout afterwards; an unclosed session breaks later calls. Prefer appliance-level calls for heavy stats to spare Orchestrator (9.3).
- Orchestrator 9.3.0 changed all endpoint definitions and they are not backward compatible: path parameters moved to query parameters, for example `appliance/{nePk}/{url}` became `appliance/rest` with `nePk` and `url`, and `acls/{neId}` became `acls` with `nePk` (9.3).
- Legacy switch: advanced property `enableLegacyApisSupport` (Orchestrator > Software & Setup > Setup > Advanced Properties) true on 9.3.1 and later serves the pre-9.3 paths on the interop list in addition to the new ones; 9.2 and earlier serve only old paths, 9.3.0 only new. OaaS needs a TAC case; a restart in a maintenance window is advised (9.3).
- RBAC applies to every endpoint from 9.3.0, interop paths included from 9.3.1; interop adds routing latency, so migrate scripts rather than depend on it (9.3).
- The Postman collection has Orchestrator-level and appliance-level folders; variables are `orchestratorBaseUrl`, `applianceBaseUrl`, `user`, `password` (9.3).
- The lab spec (9.7.1) is authoritative; docs only explain intent (9.7).
## MCP operations
- Find with `find_operations` terms "apiKey", "authentication", "rbac".
- Check the target: `GET /gms/versions`, `GET /authentication/loginStatus`, `GET /rbac/allowedRestApis` (optional `method`; endpoints the current key may call).
- Keys: `GET /apiKey` (optional `name`). Creating, changing or deleting keys, logging in or out, and the legacy switch are not available through the MCP server; use the Orchestrator UI (Orchestrator > Software & Setup > Setup for the advanced property).
- Legacy mapping: `GET /rbac/legacyApi` lists transformation entries (needs `enableLegacyApisSupport`); `GET /gms/advancedProperties` shows the property.
- Appliance passthrough: `GET /appliance/rest` (needs `nePk`, `url`) is the 9.3 form of the old `appliance/{nePk}/{url}`. Urls that read back on 9.7.1: `deployment`, `bgp/config/neighbor`, `bgp/config/system`, `ipsla/config/managers`, `ospf/config/system`, `ospf/config/areas`, `ospf/config/interfaces`, `resolver`, `dnsProxy/config`, `subnets3/configured`, `vrrp`, `memory`, `cpustat`.
- Writing through passthrough: `POST /appliance/rest` with url `bgp/config/neighbor` works (see bgp). For any other appliance setting, use the Orchestrator UI or the template-group route.
## Gotchas
- A doc example that uses the old path form will 404 on 9.3 and later; rewrite it with `find_operations` instead of guessing. The 9.3 table lists some paths with a trailing `/rest` (for example `acls/rest`) that does not exist in the 9.7.1 spec, where the path is `/acls`; trust the spec.
- `subnets/configured` returns 410 on 9.7.1; read `subnets3/configured` instead.
- `GET /appliance/rest` reads any appliance REST path; BGP, OSPF and VRRP also have dedicated Orchestrator reads (see their cards).
- The Postman variable names above are for humans; the MCP server needs only its `.env` key and base URL.
## Related
- [websocket-api](websocket-api.md)
- [aaa-users](aaa-users.md)
- [cli-basics](cli-basics.md)
- [flows-stats](flows-stats.md)
- [bgp](bgp.md)
