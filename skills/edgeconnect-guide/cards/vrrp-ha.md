# VRRP and EdgeHA
## What it is
Appliance redundancy at a site: VRRP instances on LAN interfaces, EdgeHA (two appliances joined by an HA link acting as one cluster), and Traditional HA (two independent appliances).
## Docs
- [VRRP Tab](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/network/vrrp/) - fields, restrictions, site/cluster tracking (9.7)
- [VRRP Template](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/vrrp/) - common VRRP parameters (9.7)
- [Deployment - EdgeHA](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/overlays/deploy-edgeha/) - enabling EdgeHA, HA link, VRRP priorities (9.7)
- [VRRP General](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/vrrp-1) - route selection order, choosing a tracking method (all)
- [VRRP with tracking](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/vrrp-with-tracking) - 9.6 site/cluster tracking design (9.6+)
- [VRRP without tracking](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/vrrp-without-tracking) - IP SLA +30 method for 9.5 and earlier (9.5)
- [HA and VRRP](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/edge-ha-failover-and-convergence) - EdgeHA versus Traditional HA, failover timers (all)
- [Traditional High Availability Deployment Guide](https://arubanetworking.hpe.com/techdocs/sdwan-PDFs/deployments/dg_SP-HA-Traditional_latest.pdf) - two independent appliances at a hub or large branch (all)
- [Troubleshooting: Routing](https://arubanetworking.hpe.com/techdocs/sdwan/docs/troubleshooting/routing/) - route and peer checks when failover misbehaves (all)
- [CLI Reference: VRRP](https://arubanetworking.hpe.com/techdocs/sdwan-PDFs/cli-ref/CLI-Reference_latest.pdf) - VRRP commands on the appliance (all)
## Key facts
- VRRP instance fields: group id 1 to 255, interface, version (2 is IPv4 only; 3 adds IPv6 and has no authentication string), virtual IP, priority, preemption, admin, hold down, advertisement timer (9.7).
- Defaults: hold down 60 s; advertisement 1 s (v2) or 1 centisecond (v3); max 4 VRRP instances per interface (9.7).
- Advertisement interval must be identical on every router in a VRRP group, master or backup (9.7).
- VRRP is supported on LAN interfaces only (9.5).
- Site/Cluster Tracking (9.6+): without it hub-to-site convergence can take up to 60 s (the reclassification interval); with it routes are tagged P or B and primary wins at step 4 of route selection (9.6+).
- With tracking, recommended: equal metric on both appliances and no IP SLA rule for VRRP; tracking affects inbound traffic while peer priority affects outbound (9.6+).
- Without tracking, recommended starting values: IP SLA VRRP rule on the primary only with metric +30, primary metric 50, secondary 55 to 70 (9.5).
- EdgeHA: needs an HA link on a LAN or WAN port (not mgmt), same code on both, tunnel type IPSec over UDP, no active/active ECMP, not supported in cloud; EdgeHA pairs get the same ASN (9.7).
- EdgeHA branch VRRP priorities in the guide: 128 for the primary, 127 for the secondary (9.7).
- Traditional HA suits hubs, large branches and cloud; appliances can run different code (all).
## MCP operations
- Find with `find_operations` terms "vrrp", "edge ha", "haGroups".
- VRRP read: `GET /vrrp` (`nePk` and `cached` both required), also through `GET /appliance/rest` with `nePk` and url `vrrp`.
- EdgeHA and HA reads: `GET /edge-ha/groups`, `GET /haGroups`, `GET /appliance/haPeerMeta`.
- Creating or changing VRRP instances is not covered by this guide; do it in the Orchestrator UI. Creating or changing EdgeHA groups and HA groups is not available through the MCP server; do it in the Orchestrator UI.
## Gotchas
- Avoid running a BGP session over the VLAN or virtual IP that VRRP uses; give VRRP its own VLAN (a /29 sub-interface) (all).
- If the VIP is on a different subnet than the LAN interfaces, do not use static routes on the LAN side, and DHCP server or relay on that VIP is unsupported (9.7).
- EdgeHA uses the 169.254 link-local range by default; avoid duplicates and do not share that subnet in route maps (9.7).
- Keep preemption on, with the hold down long enough for tunnels and routing to come back (9.7).
## Related
- [peer-priority](peer-priority.md)
- [route-maps](route-maps.md)
- [bgp](bgp.md)
- [ospf](ospf.md)
