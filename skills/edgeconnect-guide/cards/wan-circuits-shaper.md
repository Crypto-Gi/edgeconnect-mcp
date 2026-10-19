# WAN circuits and shaper
## What it is
Which WAN circuit and NAT types can form tunnels, how to size and pair circuits, and the shaper that divides WAN bandwidth between traffic classes.
## Docs
- [WAN Circuit Guidance](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/circuit-guidance) - supported NAT pairings, carrier diversity, minimum bandwidth (all)
- [Shaper/QoS Policy best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/shaper-1) - starting shaper, deployment bandwidth, borrowing rules (all)
- [Shaper Tab](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/policy/shaper/) - traffic class fields, inbound and outbound shaping (9.7)
- [Shaper Template](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/shaper/) - global shaper, per-interface shaping, Dynamic Rate Control (9.7)
- [CLI Reference: Policy Maps (NAT, Optimization, QoS, Shaper)](https://arubanetworking.hpe.com/techdocs/sdwan-PDFs/cli-ref/CLI-Reference_latest.pdf) - shaper commands (all)
## Key facts
- Tunnel formation by NAT pairing: fully supported when the hub or local mesh side is a direct public IP or 1:1 NAT / port forward; SNAT with SNAT, PAT or CG-NAT is partly supported; PAT or CG-NAT on both ends, in any mix of the two, is unsupported (all).
- In a mesh, every location needs at least one circuit in the fully supported set. Burstable circuits are not recommended (all).
- Recommended: two diverse carrier circuits at every site. Circuits under about 1 Mbps up and 3 Mbps down cannot carry even one user, though they can add FEC capability (all).
- Shaper: ten traffic classes, four preset (RealTime, CriticalApps, BulkApps, Default). Outbound shaping is always on; inbound is off by default (9.7).
- Per class: priority 1-10, min and max as percent or absolute kbps, excess weighting 1-10000, max wait time, per-flow rate limit (9.7).
- Min above max: max wins. If minimums add to over 100%, low-priority classes can go short (9.7).
- Shaping uses the deployment bandwidth; if it exceeds the license, the shaper is capped at the licensed rate (all).
- Recommended starting values (not required): inbound and outbound match, use Min Bandwidth % so it scales per site, deployment bandwidth equal to the real circuit rate, push the shaper as a template (all).
- Per-interface shapers are not used for SD-WAN overlay traffic; overlay traffic is shaped by the total WAN shaper (9.7).
## MCP operations
- Find with `find_operations` terms "shaper", "inboundShaper".
- Read: `GET /shaper` and `GET /inboundShaper` (`nePk`, optional `cached`); deployment bandwidth: `GET /deployment`.
- Stats: `GET /stats/timeseries/shaper`, `POST /stats2/aggregate/shaper`, `POST /stats/aggregate/trafficClass`.
- The shaper is changed in a template group: `GET /template/templateGroups`, then save only the Shaper template with `POST /template/templateGroups` as `{"name", "valObject"}`. Saving pushes it to every associated appliance.
## Gotchas
- The Shaper template view does not show calculated bandwidth; look at the shaper on the appliance after applying.
- When every class uses its guarantee, nothing can be borrowed: raising excess weighting does not help. Lower other minimums, raise the minimum of the starved class, or move low-value traffic to a new class (all).
- A circuit that is CG-NAT on both ends can come up briefly and then flap (all).
- Microbursts can distort QoS results; check Monitoring > QoS for drops and waits (all).
## Related
- [qos](qos.md)
- [tunnels](tunnels.md)
- [interfaces-labels](interfaces-labels.md)
- [deployment-profiles](deployment-profiles.md)
- [overlays-bio](overlays-bio.md)
