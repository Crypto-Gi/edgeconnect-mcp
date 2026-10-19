# Route policies
## What it is
Route Policies decide how matching flows are forwarded: pass-through, drop, a chosen tunnel or interface, or best-path by loss, latency or load. This is not redistribution, see [route-maps](route-maps.md).
## Docs
- [Route Policies Tab](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/policy/route-policies/) - policies on each appliance, edit directly or open the template manager (9.7)
- [Route Policies Template](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/route-policies/) - rule priorities, match criteria, wildcard rules (9.7)
- [Route Policies best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/route-policies) - apply the template as replace (all)
- [CLI Reference: IP Routing and Route Maps](https://arubanetworking.hpe.com/techdocs/sdwan-PDFs/cli-ref/CLI-Reference_latest.pdf) - policy-map and route syntax on the appliance (all)
## Key facts
- Appliances auto-optimize all IP traffic by default (TCP-based, IP-based, and subnet sharing); rules are needed only for pass-through, drop, HA specifics, or application/VLAN/DSCP/ACL steering (9.7).
- Template rules use priority 1000 to 9999; applying the template deletes all existing rules in that range first (9.7).
- Local rules may use 1 to 999 and 10000 to 19999 and 25000 to 65534; 20000 to 24999 is reserved for Orchestrator (9.7).
- A new rule gets the previous priority plus 10 (9.7).
- With Business Intent Overlays Orchestrator creates the needed policies itself; the Internet breakout of SaaS or guest Wi-Fi still needs manual entries (9.7).
- Match options include application, address map, domain, geo location, interface, protocol, DSCP, IP/subnet, port, overlay, fabric or internet, user role; an ACL makes criteria reusable across policy maps (9.7).
- Recommended starting value: apply the template as replace; a blank policy is fine and prevents config drift (all).
## MCP operations
- Find with `find_operations` term "route policy".
- Read: `GET /routeMaps` returns route policy settings for one appliance (`nePk` required; `cached=false` reads the live appliance and refreshes the cache).
- Route policies are assigned through template groups: `GET /template/templateGroups`, save only the Route Policies template with `POST /template/templateGroups` as `{"name", "valObject"}`, and enable it with `POST /template/templateSelection`.
## Gotchas
- `GET /routeMaps` is the route-policy read (route maps with match criteria and set actions); it does not cover redistribution maps (see [route-maps](route-maps.md)).
- Template apply with replace removes hand-made rules in 1000 to 9999.
- Wildcards in addresses cover a whole octet only (10.130-139.*.64-95 is fine, 10.13*.1.1 is not).
## Related
- [route-maps](route-maps.md)
- [peer-priority](peer-priority.md)
