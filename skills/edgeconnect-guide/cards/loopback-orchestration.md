# Loopback orchestration
## What it is
Orchestrator allocates loopback interface addresses to appliances from pools, per segment and optionally per region. Loopbacks are the source for IP SLA, DNS proxy, TACACS, NetFlow, SNMP and similar management traffic.
## Docs
- [Loopback Orchestration](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/network/loopback-orch/) - fields, pools, reclaim, regional behaviour (9.7)
- [Loopback Orchestration best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/loopback-orchestration-1) - setup steps and tips (all)
## Key facts
- Create a LAN-side label (for example "Loopback") and a management firewall zone before setting up (9.7).
- One pool per region and per segment; a Global entry covers regions without their own (9.7).
- Orchestrated loopbacks are numbered from lo20000; manually added loopbacks are not overwritten (all).
- Regional loopbacks are numbered sequentially (lo20001, lo20002); features such as BGP refer to loopbacks by name, so adjust them afterwards (9.7).
- Management IP: tick it on the Default-segment loopback; only one per appliance, except one per region when regions have their own loopbacks (9.7).
- Pool size must be larger than the number of interfaces drawing from it (9.7).
- Removing an appliance retires its address as Deleted; re-adding restores the same address, and Reclaim returns deleted addresses to the pool (9.7).
- Without orchestration, set the management IP on the appliance with the CLI command `ip mgmt-ip` (all).
## MCP operations
- Find with `find_operations` term "loopback".
- Settings: `GET /loopbackOrch`, `POST /loopbackOrch` (whole map keyed by segment id, with `ipv4`/`ipv6` `loopbackPool` and `interfaces`).
- Pool state: `GET /loopbackOrch/pool`, `GET /loopbackOrch/pool/history` (needs `seg`; 9.7.1, not in the 10.0 API spec).
- Reclaiming deleted addresses is not covered by this guide; do it in the Orchestrator UI (loopback orchestration, Reclaim).
- Appliance loopbacks: `GET /virtualif/loopback` (`nePk`).
## Gotchas
- `POST /loopbackOrch` was tested by re-posting the current map: read it and post the whole thing back with your change.
- Interfaces cannot be deleted from an appliance in Orchestrator; use Appliance Manager (9.7).
- Loopbacks must be configured consistently across appliances (9.7).
## Related
- [segmentation](segmentation.md)
- [regional-routing](regional-routing.md)
- [bgp](bgp.md)
