# Flows, statistics and capacity monitoring
## What it is
Looking at live and recent traffic flows, and pulling statistics (real-time, time series, aggregate) from Orchestrator or from the appliances. Covers the Active and Recent Flows view, flow details, flow reset, statistics collection and retention on Orchestrator, REST API monitoring rules and link-utilisation maths.
## Docs
- [Flows - Active and Recent](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/monitoring/bandwidth/flows/) - filters, segment and zone filters, flow characteristics (9.7)
- [Flow Monitoring](https://arubanetworking.hpe.com/techdocs/sdwan/docs/troubleshooting/flow_monitoring/) - reading flow details: overlay, application, routing, stats (9.7)
- [Statistics Retention](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/orchestrator/sw-setup/stats-retention/) - per-statistic collection and minute, hour, day retention (9.7)
- [Stats Collector Configuration](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/orchestrator/sw-setup/stats-collector/) - separate collector for stats (9.7)
- [Active and Recent Flows best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/active-and-recent-flows) - saved filters, one-way flows, direction convention (all)
- [Orch Tips and Tricks](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/orch-tips-and-tricks) - troubleshooting tabs and useful table columns (all)
- [REST API Monitoring](https://developer.arubanetworks.com/edgeconnect/docs/monitoring) - statistic types, naming, polling guidelines (9.3)
- [ECOS REST API for collecting and monitoring statistics](https://developer.arubanetworks.com/edgeconnect/docs/examples) - pulling per-minute stats files straight from appliances (9.3)
- [Capacity Management for Link Utilization](https://developer.arubanetworks.com/edgeconnect/docs/system-integration-best-practices) - utilisation formula from aggregate interface stats (9.3)
## Key facts
- Direction convention: outbound is LAN to WAN, inbound is WAN to LAN, seen from the appliance as a whole, not from a single port (all).
- Statistic names: Inbound LAN is LAN Tx, Outbound LAN is LAN Rx, Inbound WAN is WAN Rx, Outbound WAN is WAN Tx; `SP_LAN` and `SP_WAN` are bonded aggregates (9.3).
- Active and Recent Flows is the first stop for fabric traffic: it shows one-way flows, route, segment and firewall drops, boost, NAT and zone details. Several appliances can be selected at once to follow a flow hub to spoke (all).
- A one-way flow (traffic in from the WAN, nothing back out) usually means a LAN or endpoint fault such as ARP failing, a missing return route or a local firewall, not a fabric fault; confirm with a packet capture (all).
- MGMT0 and MGMT1 traffic is not shown in the flows table (all).
- The Zone filter needs a specific segment, not "any"; only one flow characteristic can be filtered at a time; EdgeHA flows are hidden unless Include EdgeHA is on (9.7).
- Dropped embryonic, firewall, route and IPS flows are highlighted red (9.7).
- Three statistic types exist: real-time (3 data points over 3 seconds), time series (a point per interval) and aggregate (sums, averages, min and max for minute, hour or day buckets) (9.3).
- Monitoring rules: serialise requests, loop over appliances one at a time, and avoid high-volume pulling from Orchestrator; for bulk or frequent data read the appliance directly (9.3).
- Each real-time reply covers 3 seconds, so poll at intervals shorter than 3 seconds to avoid gaps (9.7).
- Average utilisation percent = average bytes x 8 x 100 / (bucket seconds x average configured kbps x 1000), with bucket seconds 60, 3600 or 86400 for minute, hour or day granularity (9.3).
- Traffic type codes: 1 optimised, 2 pass-through shaped, 3 pass-through unshaped, 4 all (9.3).
- DoS statistics are kept 30 days; longer needs a storage subscription (9.7).
## MCP operations
- Find with `find_operations` terms "flow", "stats/timeseries", "stats/aggregate", "realtimeStats".
- Flows: `GET /flow` (needs `nePk`, `maxFlows`; many filters such as `ip1`, `port1`, `application`, `zone1`, `filter`, `uptime`), `GET /flow/flowDetails2` (needs `nePk`, `id`, `seq`), `GET /flow/flowBandwidthStats` (needs `nePk`, `id`, `seq`), `GET /flow/flowOptimization` (needs `nePk`, `id`, `seq`, `ignore`) shows optimisation action, warnings and errors for one flow.
- Flow counts and series: `POST /stats/aggregate/flow/active` (body `nePks`), `GET /stats/timeseries/flow` (needs `startTime`, `endTime`, `granularity`, `trafficType`, `flowType`; `nePk` or `groupPk`), `GET /stats/timeseries/appliance` (needs `startTime`, `endTime`, `granularity`, `trafficType`).
- Interface utilisation: `POST /stats/aggregate/interface` (needs `startTime`, `endTime`, `granularity`; body `nePks`; optional `trafficType`, `format`).
- Real-time: `POST /realtimeStats` (needs `nePk`; body `type`, `name`, `filter`). Types that return data: `trafficType` (name "0"), `drops` (name ""), `interface` (name "wan0", filter "0").
- Collection and retention: `GET /gms/stats/collection`, `PUT /gms/stats/collection` (needs `statType`, `isEnabled`; refused on container-mode Orchestrators with "Not available in Container Mode"), `GET /gms/stats/retention`, `GET /gms/stats/approximateDiskSpace` (needs `applianceCount`), `GET /appliance/statsConfig` (no required parameters).
- Reachability history: `GET /stats/aggregate/availability/appliance` (needs `nePk`, `date`, `granularity`).
- Resetting flows and clearing network memory are not available through the MCP server; use the Orchestrator UI. Changing stats retention is also a UI step.
## Gotchas
- Stats reads can be large; pass `max_chars`, narrow `nePk`, time range and granularity, and avoid looping over the whole fleet.
- `GET /flow` is proxied to the appliance and limited by `maxFlows`; filter instead of raising the cap.
- If every stats call returns 500, the Orchestrator's stats database is the problem; on a healthy Orchestrator the stats calls above all work.
- Disabling a statistic loses data from the charts; confirm first.
## Related
- [packet-capture](packet-capture.md)
- [alarms-monitoring](alarms-monitoring.md)
- [security-zones-firewall](security-zones-firewall.md)
- [wan-circuits-shaper](wan-circuits-shaper.md)
- [qos](qos.md)
- [tunnels](tunnels.md)
