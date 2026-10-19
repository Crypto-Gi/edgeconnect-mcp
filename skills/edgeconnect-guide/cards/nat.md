# NAT
## What it is
Branch NAT rules and pools that translate overlapping LAN addresses into routable fabric addresses, plus the SaaS NAT policy map and the inter-segment SNAT and DNAT exceptions.
## Docs
- [NAT](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/network/nat/) - rules, pools, directions, segments (9.7)
- [SaaS NAT Policies Template](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/nat-policies/) - dynamic and manual NAT policy maps (9.7)
- [Inter-Segment SNAT Exceptions](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/network/inter-seg-snat/) - NAT between segments (9.7)
- [Inter-Segment Routing and DNAT Exceptions](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/network/inter-seg-dnat/) - DNAT between segments (9.7)
- [CLI Reference: Policy Maps (NAT, Optimization, QoS, Shaper)](https://arubanetworking.hpe.com/techdocs/sdwan-PDFs/cli-ref/CLI-Reference_latest.pdf) - NAT map commands (all)
## Key facts
- Branch NAT rules apply to all LAN-to-WAN traffic: tunneled, internet-bound and passthrough (9.7).
- Supported translations: 1:1 IP, subnet to subnet, many-to-one source, and source NAT pools (9.7).
- Direction: outbound rules match flows started on the LAN, inbound rules flows started on the WAN. Return traffic needs no extra rule, and every rule needs a destination IP (9.7).
- Rule fields: priority, LAN interface or any, segment, direction, protocol, source, destination, destination port, translated source or pool, translated destination and port, enabled, comment (9.7).
- A rule with a NAT pool must match the pool's segment and direction. Deleting a segment removes its NAT rules (9.7).
- NAT is not applied to the EdgeConnect's own addresses, and NAT between segments is not supported here; use the inter-segment SNAT exceptions (9.7).
- Internet breakout uses Stateful+SNAT, not this NAT feature (9.7).
- For overlapping subnets: stop advertising the local static routes, add announce-only static routes for the NAT pools, and allow them in the "redistribute to SD-WAN fabric" route map (9.7).
- SaaS NAT map: dynamic policies use priority 40000-50000, the no-NAT default is 65535; "NAT all" also covers passthrough traffic; Fallback moves to the next IP when ports run out (9.7).
- A rule that uses the same subnet as source, destination and translation acts as an explicit "do not NAT" (9.7).
## MCP operations
- Find with `find_operations` terms "nat", "snat", "dnat".
- Read: `GET /nat` (all NAT config), `GET /natMaps`, `GET /natMapsDynamic`, `GET /nat/natPools`, `GET /natAll`, `GET /dnatMaps`, `GET /snatMaps`. All take `nePk` and optional `cached`.
- Inter-segment SNAT: `GET /vrf/config/snatMaps`, `POST /vrf/config/snatMaps`; DNAT: `GET /vrf/config/maps`, `POST /vrf/config/maps`.
- Changing branch NAT rules or the SaaS NAT map is not covered here; use the Orchestrator UI.
## Gotchas
- NAT configuration is not available in Appliance Manager, only in Orchestrator (9.7).
- Overlapping addresses plus advertised local routes create ambiguous routes; withdraw the originals first.
- Manual SaaS NAT priorities must stay out of 40000-50000 so they do not collide with dynamic entries.
## Related
- [segmentation](segmentation.md)
- [internet-breakout-saas](internet-breakout-saas.md)
- [static-routes](static-routes.md)
- [route-maps](route-maps.md)
- [qos](qos.md)
