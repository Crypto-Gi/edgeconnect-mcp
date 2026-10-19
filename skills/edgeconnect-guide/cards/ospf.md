# OSPF
## What it is
OSPF on LAN and WAN interfaces: system settings, areas and interfaces. OSPF routes are subnet-shared into the fabric and can be redistributed to BGP.
## Docs
- [OSPF Tab](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/network/ospf/) - fields, areas, interfaces, neighbor limit (9.7)
- [OSPF Template](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/ospf/) - common OSPF settings per template group (9.7)
- [Route Redistribution Maps best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/route-redistribution-maps) - OSPF primary, secondary and deny maps (all)
- [CLI Reference: OSPF](https://arubanetworking.hpe.com/techdocs/sdwan-PDFs/cli-ref/CLI-Reference_latest.pdf) - area and interface commands on the appliance (all)
## Key facts
- Limit: 64 OSPF neighbors per appliance; extra neighbors are logged as errors and the lowest segment id and lowest neighbor IP are kept first, so the highest ones drop (9.7).
- Area types are Standard or NSSA; NSSA adds redistribution, summary and translator-role options (9.7).
- Router ID is an IPv4 address; opaque LSA support is a toggle (9.7).
- Interface fields: area id, cost, priority, admin status, hello and dead intervals (9.7).
- Redistribution into OSPF goes through a route redistribution map chosen on the OSPF page; routes become OSPF external (9.7).
- A route tag marks the source so redistributed routes can be filtered; the best-practice maps tag with 111 and a deny on that tag in the fabric-facing map stops LAN loops in HA (all).
## MCP operations
- Find with `find_operations` terms "ospf config", "ospf state".
- Read config: `GET /ospf/config/system`, `GET /ospf/config/areas`, `GET /ospf/config/interfaces`, plus `GET /ospf/config/allVrfs/system` and `GET /ospf/config/allVrfs/interfaces` for all segments.
- Read state: `GET /ospf/state/system`, `GET /ospf/state/neighbors`, `GET /ospf/state/interfaces`, and the `allVrfs` variants (for example `GET /ospf/state/allVrfs/neighbors`).
- The same config reads work through `GET /appliance/rest` with `nePk` and url `ospf/config/system`, `ospf/config/areas` or `ospf/config/interfaces`.
- Changing OSPF is not covered by this guide; do it in the Orchestrator UI.
## Gotchas
- Check neighbor count against the 64 limit before adding peers; the failure is a log line, not an API error.
- Segments other than Default need their own OSPF config; read the `allVrfs` operations to see them all.
- Traditional HA needs each side to deny the other's OSPF tag, or LAN loops form (all).
## Related
- [route-maps](route-maps.md)
- [bgp](bgp.md)
- [segmentation](segmentation.md)
- [vrrp-ha](vrrp-ha.md)
