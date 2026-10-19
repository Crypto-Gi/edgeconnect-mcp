# Route maps (redistribution)
## What it is
Route Redistribution Maps filter and rewrite routes (metric, tag) as they move between local/static, SD-WAN fabric, BGP and OSPF. Each map has ordered rules with match criteria and set actions.
## Docs
- [Routes Tab](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/network/routes/) - Route Maps section: where maps apply, limits (9.7)
- [Route Redistribution Maps Template](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/route-redist/) - merge or replace, per-target maps (9.7)
- [Route Redistribution Maps best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/route-redistribution-maps) - starter maps that prevent loops (all)
- [CLI Reference: IP Routing and Route Maps](https://arubanetworking.hpe.com/techdocs/sdwan-PDFs/cli-ref/CLI-Reference_latest.pdf) - route-map syntax on the appliance (all)
## Key facts
- Targets: SD-WAN Fabric, BGP Inbound, BGP Outbound, OSPF (9.7).
- Supported: match prefix, set metric, set tag (9.7).
- Limits: 20 maps per protocol per direction on the appliance, 128 rules per map, 6 prefixes per rule; the template allows 14 custom maps per target (9.7).
- Template rules use priorities 1000 to 9999. Merge overwrites only rules with matching priorities; Replace deletes every map on the appliance and installs the template's (9.7).
- A map with no enabled rules is deny-all, and so is an unset map at a redistribution point (9.7).
- Prefix match defaults to exact plus longer; use both LE and GE (for example LE 24 GE 24) for an exact match (all).
- Recommended starting values (not required): primary routes redistribute with metric 50, secondary with 70; start priorities at 2000 or 3000 to leave room (all).
- Recommended: keep all maps in one global template with Replace, and name starter maps with the "default_" prefix; maps not starting with "default_" are overwritten when the template applies (all).
- Starter set: BGP out primary and secondary (PE and branch) and deny, BGP in primary, secondary and deny, fabric out deny, primary and secondary, OSPF deny, primary and secondary (all).
## MCP operations
- Find with `find_operations` terms "route map", "routeMaps".
- Read: `GET /routeMaps` (`nePk` required, `cached=false` for the live appliance) returns route policy settings (match criteria and set actions); see [route-policies](route-policies.md).
- Redistribution maps are pushed with the Route Maps template of a template group: `GET /template/templateGroups`, then save only that template with `POST /template/templateGroups` as `{"name", "valObject"}`. An empty or partial map is deny-all, so read the current template first and post it back with your change.
## Gotchas
- Replace wipes locally made maps, including ones attached to live BGP peers; read first.
- In the Routes template, selecting a redistribution map overwrites the choice made on every appliance using it.
- With VRRP site/cluster tracking (9.6+) the primary and secondary fabric maps can collapse into one cluster map with equal metric (9.6+).
## Related
- [bgp](bgp.md)
- [ospf](ospf.md)
- [static-routes](static-routes.md)
- [peer-priority](peer-priority.md)
- [vrrp-ha](vrrp-ha.md)
