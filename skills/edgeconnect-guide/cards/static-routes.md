# Static routes
## What it is
Local and static routes on an appliance, subnet sharing into the SD-WAN fabric, and the separate management routes for mgmt interfaces.
## Docs
- [Routes Tab](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/network/routes/) - route table, route types, subnet sharing, route maps, CSV import (9.7)
- [Management Routes Tab](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/network/mgmt-routes/) - next-hops for management interfaces (9.7)
- [Routes Template](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/routes/) - subnet sharing defaults per template group (9.7)
- [Routes best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/routes) - route loop prevention settings (all)
- [CLI Reference: IP Routing and Route Maps](https://arubanetworking.hpe.com/techdocs/sdwan-PDFs/cli-ref/CLI-Reference_latest.pdf) - static route and route-table commands (all)
## Key facts
- The route table mixes automatic system routes, manual local/static routes, and routes learned from the fabric, BGP or OSPF (9.7).
- Static route metric is 0 to 100; the default for automatically added routes is 50 (9.7).
- A peer with several tunnels to the same subnet picks the one with the lower metric (9.7).
- Routes template options: advertise local LAN subnets, advertise local WAN subnets, include BGP local ASN toward the fabric, filter fabric routes carrying the local ASN, tag BGP communities (9.7).
- Recommended starting values: set include-local-ASN and filter-matching-ASN to Yes; leave the "route map to redistribute to the fabric" blank in the template (all).
- A route with a blank next hop is advertise-only: it is shared with peers (for example a default-originate or a summary) but not used to forward traffic on the appliance itself (9.7).
- Management routes are separate; with DHCP the appliance creates dynamic management routes, and those cannot be added or deleted by hand (9.7).
- CSV import has no header row and no spaces after commas; a table over 500,000 routes triggers a very-large-query warning, so filter by subnet or segment (9.7).
## MCP operations
- Find with `find_operations` terms "subnets", "subnet sharing".
- Read: `GET /subnets` (needs `cached` and `nePk`), `GET /subnets/all` (all segments), and the static route list through `GET /appliance/rest` with `nePk` and url `subnets3/configured`.
- Sharing options: read `auto_subnet` with `GET /appliance/rest` (`nePk`, `url` `system/auto_subnet`). `POST /subnets/setSubnetSharingOptions` was tested only by posting that object back unchanged; change sharing in the Orchestrator UI.
- Adding or changing static routes is not covered by this guide; do it in the Orchestrator UI.
## Gotchas
- `subnets/configured` returns 410 on current appliances; use `subnets3/configured`.
- LAN subnets of a non-default segment are not advertised until subnet sharing (`add_local_lan`) is set for that segment in the Orchestrator UI.
- Selecting a redistribution map in the Routes template overwrites the map chosen on every appliance that uses it (all).
- A route map with no enabled rules, or no map selected at a redistribution point, denies everything.
## Related
- [route-maps](route-maps.md)
- [segmentation](segmentation.md)
- [bgp](bgp.md)
- [ospf](ospf.md)
