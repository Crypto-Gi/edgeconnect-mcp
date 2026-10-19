# Peer priority
## What it is
The Peer Priority tab and template: a per-spoke list of hubs with a priority and an optional advertise metric. It breaks ties between equal fabric routes (outbound) and can steer the return path.
## Docs
- [Peer Priority Tab](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/network/peer-priority/) - peer, priority, advertise metric (9.7)
- [Peer Priority Template](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/peer-priority/) - same list as a template; needs 9.0.2.0 or later on version 9 (9.7)
- [Basic setup](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/basic-setup) - template group, reading the route table (all)
- [Peer Priority routing options](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/peer-priority-routing-options) - route selection order, with or without advertise metric (all)
- [Advertise Metric](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/advertise-metric) - return-path steering, HA pairs (all)
- [Without Advertise Metric](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/no-advertise-metric) - what the core sees when it is off (all)
- [Peer Priority explorer](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/peer-priority-explorer) - template layouts per region (all)
## Key facts
- Applies only among routes with the same prefix, admin distance and metric; lower number wins; default is 1024 when a peer is not listed (all).
- Route order from 9.6.2: longest prefix, admin distance, metric, VRRP state tracking, peer priority, BGP AS-path length, then ECMP. Before 9.6: prefix, AD, metric, peer priority, ECMP (9.6+).
- With no priorities set, flows spread randomly over equal peers (9.7).
- Advertise metric sets the metric of routes sent to that peer, which controls the return path (like MED); default is "preserve existing" (9.7).
- Recommended: apply to all spokes or none; on hubs only toward other hubs (all).
- Recommended: give each peer-priority template its own template group, the one exception to combining templates (all).
- Convention (not enforced): priorities in bands, 100s for the first DC, 200s for the second (all).
## MCP operations
- Find with `find_operations` term "peer priority".
- Read: `GET /appliance/peerPriorityList` (`nePk` required; `cached=false` reads the appliance).
- Peer priority is set in the Peer Priority template of a template group: `GET /template/templateGroups`, save only that template with `POST /template/templateGroups` as `{"name", "valObject"}`, and enable it with `POST /template/templateSelection` (body is the plain list of selected template names).
## Gotchas
- A BGP out-map that sets its own metric overwrites the advertise metric, so the core sees no difference (all).
- A VRRP or HA backup using the same template sends the site out at the master's own metric; give it a cloned template with a worse advertise metric (all).
- With VRRP site/cluster tracking (9.6+), keep the metric equal on both appliances; a differentiated advertise metric defeats it (9.6+).
- A hub still advertising a route while missing from the template gets priority 1024 and loses to any listed peer (all).
## Related
- [vrrp-ha](vrrp-ha.md)
- [route-maps](route-maps.md)
- [regional-routing](regional-routing.md)
- [bgp](bgp.md)
