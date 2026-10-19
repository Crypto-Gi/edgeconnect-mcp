# Routing segmentation (VRF)
## What it is
VRF-style Layer 3 segments across the fabric. Each segment gets its own routing, overlays, firewall zone policies, inter-segment rules and loopbacks.
## Docs
- [Routing Segmentation](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/network/routing-seg/) - enabling, adding segments, per-segment settings (9.7)
- [Segmentation initial setup](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/segmentation) - turn on early, caveats, security policy placement (all)
- [CLI Reference: Segmentation](https://arubanetworking.hpe.com/techdocs/sdwan-PDFs/cli-ref/CLI-Reference_latest.pdf) - segment commands on the appliance (all)
## Key facts
- Needs Orchestrator and all appliances on 9.0 or later, in Inline Router mode (9.7).
- Disabled by default after upgrade; a Default segment (id 0) always exists and cannot be deleted. Enabling moves existing config into Default (9.7).
- Segment names: letters, digits and underscores, unique (9.7).
- Per-segment settings: overlays and breakout (include or skip each overlay), firewall zone policies, inter-segment routing and DNAT, inter-segment SNAT, loopback (9.7).
- BGP and OSPF are supported in all segments (all).
- Up to 9.5, only the default segment supports IPv6, branch NAT (fixed in 9.6), multicast and overlapping IP space (9.5).
- Recommended: turn segmentation on early and check release notes for caveats (all).
- With segmentation, do not apply a templated zone firewall policy; it works only in the Default segment and runs before the segment policy (all).
- Deactivate the Security Policies template in template groups after migration, or it overrides the default-default segment policy (9.7).
## MCP operations
- Find with `find_operations` terms "vrf", "segment".
- Enable: `GET /vrf/config/enable` reads the state. Turning segmentation on is a UI step (see the add-segment playbook); `POST /vrf/config/enable` was tested only by re-posting the current value.
- Segments: `GET /vrf/config/segments` (optional `id`), `POST /vrf/config/segments` (body `{"name"}`, returns `{"id": n}`), `PUT /vrf/config/segments` (rename, `id` query), `DELETE /vrf/config/segments` (`id` query).
- Inter-segment: `GET /vrf/config/maps`, `POST /vrf/config/maps`, `DELETE /vrf/config/maps` (DNAT); `GET /vrf/config/snatMaps`, `POST /vrf/config/snatMaps`; `GET /vrf/config/securityPolicies`, `POST /vrf/config/securityPolicies`.
- Per-segment reads: `GET /subnets/all`, `GET /bgp/config/allVrfs/neighbor`, `GET /ospf/config/allVrfs/system`, `GET /zones/vrfZonesMap`.
- Moving an interface into a segment is a deployment change: `POST /deployment/validate` can check it, but apply it in the Orchestrator UI.
## Gotchas
- Creating a segment makes the Orchestrator add one zone per global zone name for it; deleting the segment removes those zones. Segment ids and zone ids are not reused.
- LAN subnets of a non-default segment are not advertised until subnet sharing (`add_local_lan`) is set for the segment in the Orchestrator UI.
- Zones and segment security policies are whole-collection writes: read, add, write back. For a policy, that is the entire `data` object of the segment pair, every zone pair in it; a body with one zone pair deletes the others (9.7.1).
- The sharing options read with `GET /appliance/rest` (`nePk`, `url` `system/auto_subnet`), field `auto_subnet`. `POST /subnets/setSubnetSharingOptions` was tested only by posting that object back unchanged. `subnets3/configured` holds only static routes (9.7.1).
- If an overlay is set to Skip for a segment and nothing else matches, the traffic is dropped (9.7).
## Related
- [bgp](bgp.md)
- [ospf](ospf.md)
- [static-routes](static-routes.md)
- [loopback-orchestration](loopback-orchestration.md)
- [regional-routing](regional-routing.md)
