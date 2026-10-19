# Regional routing
## What it is
Regions group sites; regional routing controls how routes are exchanged inside and between regions across the fabric, and lets each region have its own overlay settings.
## Docs
- [Regions](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/network/regions/) - enable regional routing, add and edit regions (9.7)
- [Regional Routing (RR) best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/regional-routing-rr) - on versus off, route table limits (all)
- [BGP ASN Global Pool best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/bgp-asn-global-pool) - ASN pool is required with RR (all)
## Key facts
- Enabled with Enable Regional Routing on the Regions page; the default recommendation is on (9.7).
- Route table limit: 30,000 routes up to 9.3, 60,000 from 9.4 (all).
- RR on: every spoke receives the spoke routes a hub has learned, adding metric 50 per hop, maximum 2 hops (all).
- RR off: hubs do not forward other spokes' routes, so spokes need a default or summary route from the hub to hairpin (all).
- In a mesh each appliance has routes only for peers it has tunnels to (all).
- A BGP ASN pool is mandatory with RR as loop prevention (all).
- Overlays can be customised per region on the Business Intent Overlay page (9.7).
- Loopback pools are per region; regional loopbacks get sequential numbers (9.7).
## MCP operations
- Find with `find_operations` terms "regions", "regional overlay".
- Regions: `GET /regions`, `POST /regions` (body `{"regionName"}`, returns the bare regionId), `PUT /regions` (rename, `regionId` query), `DELETE /regions` (`regionId` query).
- Appliance membership: `GET /regions/appliances`, `PUT /regions/appliances` (single appliance), `GET /regions/appliances/regionId`.
- Regional overlay settings: `GET /gms/overlays/config/regions`, `PUT /gms/overlays/config/regions` (see overlays-bio for the shapes).
- The regional routing toggle is set on the Regions page in the Orchestrator UI; it has no operation here.
## Gotchas
- Pass both `overlayId` and `regionId` to `GET /gms/overlays/config/regions`.
- An appliance in a region with no loopback pool of its own falls back to the Global pool, or gets no loopback if there is none (9.7).
- View Status on the Regions page shows the result of adding appliances to regions.
- Without a hub default route, RR off isolates spokes from each other (all).
## Related
- [bgp](bgp.md)
- [loopback-orchestration](loopback-orchestration.md)
- [peer-priority](peer-priority.md)
- [segmentation](segmentation.md)
