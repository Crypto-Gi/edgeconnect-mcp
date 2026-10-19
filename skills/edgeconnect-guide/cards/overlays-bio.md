# Business Intent Overlays
## What it is
Overlays are the logical networks that decide which application traffic uses which WAN labels, how links are bonded and where internet traffic breaks out. Orchestrator builds tunnels from them, and they are matched top to bottom.
## Docs
- [Business Intent Overlays](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/overlays/bios/) - topology, primary/secondary/backup labels, SLOs, bonding, breakout (9.7)
- [Apply Overlays](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/overlays/apply-overlays/) - add or remove overlays on appliances, view status (9.7)
- [Overlay Troubleshooting](https://arubanetworking.hpe.com/techdocs/sdwan/docs/troubleshooting/overlay_troubleshooting/) - wrong overlay match, wrong path (9.7)
- [BIO best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/bio-business-intent-overlays) - recommended topology, SLO and bonding values (all)
- [CLI Reference: Tunnels and Overlays](https://arubanetworking.hpe.com/techdocs/sdwan-PDFs/cli-ref/CLI-Reference_latest.pdf) - appliance-side overlay commands (all)
## Key facts
- Traffic is matched against overlay ACLs from the top of the priority list; the first match wins, then breakout policy or the bonding policy applies (9.7).
- Topology: mesh, hub and spoke, regional mesh, regional hub and spoke. A hub is a hub in every overlay that uses a hub topology; hubs of different regions mesh together (9.7).
- Labels sit in primary, secondary or backup lists; secondary and backup are used when higher tiers are down or miss the SLO. List order matters only for Custom bonding with Waterfall and Fixed Order (9.7).
- Cross connect groups let different labels (INETA and INETB) form tunnels; by default only same-named labels connect (9.7).
- Bonding: High Availability (1:1 FEC, halves usable bandwidth, real-time only), High Quality (adaptive FEC, default for the rest), High Throughput, High Efficiency, Custom (9.7).
- If every link violates the SLO, the system behaves as if no SLO were set (9.7).
- Recommended starting values (not required): regional hub and spoke, HA for real-time overlays and HQ for the others, loss 5% and latency 150 ms for real-time, 8-12% and 200-300 ms for the rest (all).
- Even without regions there is one Global region; changes are pending until "Save and Apply Changes to Overlays" (all).
- Several predefined overlays ship by default and can be edited; the maximum overlay count is readable from the API (9.7).
## MCP operations
- Find with `find_operations` terms "overlay", "gms overlays".
- Read: `GET /gms/overlays/config` (optional `overlayId`), `GET /gms/overlays/config/regions`, `GET /gms/overlays/config/maxNumOfOverlays`, `GET /gms/overlays/association`, `GET /gms/overlays/priority`. The association read is `{"<overlayId>": [nePk, ...]}` with ids only; join it with `GET /gms/overlays/config` for overlay names and `GET /appliance` for hostnames.
- Write: `POST /gms/overlays/config` (create), `PUT /gms/overlays/config` (needs `overlayId`), `DELETE /gms/overlays/config` (also removes the overlay from the priority list), `POST /gms/overlays/priority` (reorder), `POST /gms/overlays/association` (apply to appliances), `POST /gms/overlays/association/remove`, `PUT /gms/overlays/config/regions` (per-region settings).
- Tunnel state of an overlay: `GET /tunnels2/bonded` (filter `overlayId`).
## Gotchas
- `multiCrossConnect` may only name labels in the primary or backup list; otherwise the Orchestrator answers 400 "You cannot cross connect ports that are not used in the primary or backup list." (9.7.1).
- Create from a full copy of an existing overlay (drop `id`, set `name`, rename the ACL in `match.overlayAcl` to `Overlay_<name>`): a body with only documented fields returns HTTP 500 on 9.7.1. The response is the bare new id.
- Read-back `wanPorts` shows `primary`, `backup` and `multiCrossConnect`; a full-object post reads back equal, partial bodies do not (9.7.1).
- `POST /gms/overlays/priority` takes the full map `{"<rank>": <overlayId>}`, rank 1 highest; a new overlay is appended last and a delete closes the gap (9.7.1).
- Association and its removal both take `[{"nePk": "...", "overlayId": "<id>"}]`.
- `topologyType` 1 is mesh, 2 is hub-and-spoke.
- Pass both `overlayId` and `regionId` to `GET /gms/overlays/config/regions`; it returns `{overlayId: {regionId: settings}}`, and `PUT /gms/overlays/config/regions` takes `{"<overlayId>": {"<regionId>": settings}}`.
- A new overlay has no effect on an appliance until it is applied (association), and application matching needs the right interface labels and templates first.
- The Exclude Links setting covers only the Loss SLO; latency and jitter violations always drop the link from the overlay (9.7).
## Related
- [interfaces-labels](interfaces-labels.md)
- [tunnels](tunnels.md)
- [regional-routing](regional-routing.md)
- [internet-breakout-saas](internet-breakout-saas.md)
- [qos](qos.md)
- [segmentation](segmentation.md)
