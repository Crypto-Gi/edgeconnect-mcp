# BGP
## What it is
BGP peering between an EdgeConnect appliance and LAN or WAN routers, per segment. Covers the neighbor table, the per-segment BGP defaults, and the ASN pool Orchestrator hands to new appliances.
## Docs
- [BGP Tab](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/network/bgp/) - peer fields, communities, soft reset, limits (9.7)
- [BGP Template](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/bgp/) - per-segment defaults pushed to every appliance (9.7)
- [BGP ASN Global Pool](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/network/bgp-asn-pool/) - ASN range for new appliances (9.7)
- [BGP best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/bgp-1) - recommended template values (all)
- [BGP ASN Global Pool best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/bgp-asn-global-pool) - why the pool matters with regional routing (all)
- [CLI Reference: BGP](https://arubanetworking.hpe.com/techdocs/sdwan-PDFs/cli-ref/CLI-Reference_latest.pdf) - neighbor and timer commands on the appliance (all)
## Key facts
- Limit: 64 BGP peers per appliance, 200 next-hops per interface (9.7).
- ECMP works for eBGP and iBGP when all path attributes match (9.7).
- With no metric configured, a received MED above 0 is used as the metric; MED 0 or none gives admin distance + 50 (9.7).
- Local preference defaults to 100; MED lowest wins. Peers can be IPv4 or IPv6, but only IPv4 with VXLAN (9.7).
- Communities 100 to 105 with the local ASN are internal source markers and are stripped toward BGP peers (9.7).
- Recommended starting values (not required): AS-path propagate yes, graceful restart yes with max 30 and stale 60, keepalive 5, hold 15 (all).
- Put these defaults in a BGP template that includes every segment, so new neighbors inherit them (all).
- ASN pool: applies only to new appliances, never rewrites existing ASNs; EdgeHA pairs and appliances with the same site name get the same ASN; do not use 65534 or 1 (9.7).
- The ASN pool is mandatory when regional routing is on, as loop prevention (all).
- BGP route refresh happens only on request: use Soft Reset on the peer, and only when Soft Reconfiguration is off for it (9.7).
## MCP operations
- Find with `find_operations` terms "bgp neighbor", "bgp state".
- Read config: `GET /bgp/config/neighbor`, `GET /bgp/config/system` (default segment); `GET /bgp/config/allVrfs/neighbor`, `GET /bgp/config/allVrfs/system` (all segments). All take `nePk`.
- Read state: `GET /bgp/state` (default segment), `GET /bgp/state/allVrfs` (all segments). Both take `nePk`. With no peer up, `GET /bgp/state` has no `neighbor` key; read `summary.num_bgp_peers` and `summary.num_bgp_peers_active` instead (10.0).
- To show a peer list read-only: `GET /bgp/config/allVrfs/neighbor` (keyed by segment id, then peer IP) for what is configured, then the state reads above.
- No Orchestrator write for BGP in 9.7.1. Neighbors: `GET /appliance/rest` with `nePk` and url `bgp/config/neighbor`, edit, then `POST /appliance/rest` with the same `nePk` and url and the whole object. BGP must already be enabled on the appliance; enable it, or change `bgp/config/system`, in the Orchestrator UI.
- BGP template and ASN pool settings are not exposed as dedicated operations; the template lives in a template group (`GET /template/templateGroups`; see templates-groups for saving one template with `POST /template/templateGroups`).
## Gotchas
- Passthrough writes replace the object you post, so always start from the live GET and keep unrelated peers.
- VRRP and BGP should not share a VLAN or virtual IP (all).
- Regional loopbacks are numbered by Orchestrator (lo20001, lo20002); BGP refers to loopbacks by name, so recheck source interfaces after enabling them (9.7).
- Route maps are attached per peer (inbound and outbound); a peer with no map selected is a deny-all in that direction (9.7).
## Related
- [route-maps](route-maps.md)
- [regional-routing](regional-routing.md)
- [segmentation](segmentation.md)
- [vrrp-ha](vrrp-ha.md)
- [loopback-orchestration](loopback-orchestration.md)
