# DHCP
## What it is
DHCP server and relay settings for LAN interfaces: global server defaults, per-interface settings, active leases, and DHCP failover between two EdgeConnects.
## Docs
- [DHCP Server Defaults](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/network/dhcp-server-defaults/) - none, server or relay; pool, lease, option 82 (9.7)
- [DHCP Leases](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/network/dhcp-leases/) - lease table and statuses (9.7)
- [DHCP Failover](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/network/dhcp-failover/) - roles, ports, MCLT, split; appliances older than 9.7.0 (9.6)
- [DHCP Failover State](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/network/dhcp-failover-state/) - peer states; appliances older than 9.7.0 (9.6)
- [Deployment Profiles](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/overlays/dep-profiles/) - where LAN DHCP is applied per interface (9.7)
## Key facts
- Three modes per LAN interface: no DHCP / no RA, DHCP server, or DHCP/BOOTP relay. The global default is used for Router-mode LAN interfaces in profiles and changes only affect new configurations (9.7).
- Server fields: pool and mask, exclude first and last N addresses, default and maximum lease, gateway, DNS, NTP, NetBIOS servers and node type, failover (9.7).
- Relay needs a relay interface chosen in Management Services first. Option 82 settings (enable, policy append / replace / forward / discard, sub-options) apply to every LAN interface acting as relay on that appliance (9.7).
- IPv6 LAN interfaces use router advertisements instead (9.7).
- Lease statuses: free, backup, active, abandoned. Each failover peer backs up its partner's leases (9.7).
- Failover is IPv4 only. Defaults: TCP port 647, MCLT 60 minutes, split 128 (even); both peers need the same NTP server and the same interface label per physical interface (9.6).
- Failover states: Normal, Communications-Interrupted, Partner-Down, Recover, Recover-Wait, Recover-Done, Unknown (9.6).
- From Orchestrator 9.7.0, failover is set in the DHCP Settings dialog and monitored on the Failover state subtab of the DHCP Manager tab; the older pages describe appliances before 9.7.0 (9.7).
## MCP operations
- Find with `find_operations` terms "dhcp", "dhcpConfig".
- Global defaults: `GET /dhcpConfig`, `POST /dhcpConfig` (send the whole object as read).
- Per appliance: `GET /dhcpConfig/dhcpSettings` (`nePk`, optional `cached`), `GET /dhcpConfig/leases` (needs `maxLease` and `cached=false`), `GET /dhcpConfig/state/failover`, `GET /dhcpConfig/scope`, `GET /dhcpConfig/relay`.
- Reservations: `GET /dhcpConfig/reservations`, `POST /dhcpConfig/reservations`, `POST /dhcpConfig/reservations/gms`.
- Utilization alert threshold: `GET /dhcpConfig/utilizationThreshold` (can return 404 "Failed to get data from appliance"), `POST /dhcpConfig/utilizationThreshold`.
- Changing an appliance's DHCP settings is not covered by this guide; do it in the Orchestrator UI (DHCP Manager, or the deployment profile). Resetting DHCP reservations is not available through the MCP server; use the Orchestrator UI.
## Gotchas
- Lab guardrail: never change the DHCP setting of wan0.4000 or mgmt0, whatever the DHCP settings object offers.
- Lease time units differ between the pages (hours on Server Defaults, seconds in profiles); read the live object and keep its unit.
- Nothing cross-checks the two failover peers, so the pools, peer IPs and ports have to be made to agree manually (9.6).
- Failover depends on clocks: peers on different NTP servers will break it. Taking EdgeHA down for an RMA invalidates failover and may blank the My IP and Peer IP fields (9.6).
- `POST /dhcpConfig` was tested by re-posting the current value: start from the GET.
## Related
- [deployment-profiles](deployment-profiles.md)
- [interfaces-labels](interfaces-labels.md)
- [vrrp-ha](vrrp-ha.md)
- [segmentation](segmentation.md)
