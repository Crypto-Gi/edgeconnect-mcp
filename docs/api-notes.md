# Orchestrator API notes

Found while driving a 9.7.1 Orchestrator with five ECOS 9.6/9.7 appliances through this server:

- Operations whose spec accepts only `text/plain` (Zscaler countries/timezones) take a plain string `body`, which `api_write` sends raw; a JSON-accepting operation gets it JSON-encoded.
- Deployment, BGP, OSPF, VRRP, static routes and IP SLA have no Orchestrator write operation in the 9.7.1 spec. Read the appliance's own config with `GET /appliance/rest?nePk=<NE>&url=<path>` (`deployment`, `subnets3/configured`, `bgp/config/neighbor`, `ospf/config/system`, `vrrp`, `ipsla/config/managers`), All of these reads are tested. As a write, posting the whole object back with `POST /appliance/rest` has been tested only for `bgp/config/neighbor`; check a deployment change with `POST /deployment/validate` and make it in the Orchestrator UI. `subnets/configured` returns 410; use `subnets3/configured`.
- Overlay `PUT /gms/overlays/config` is refused with 400 unless `multiCrossConnect` only names labels in the primary or backup list. On 9.7.1 a full-object post reads back equal; only partial bodies read back different, so compare intent fields. `topologyType` 1 is mesh and 2 is hub-and-spoke.
- `GET /gms/overlays/config/regions`: always pass both `overlayId` and `regionId` (one 9.7.1 Orchestrator accepted no parameters, another refused that with 400).
- User-defined applications are read with `GET /applicationDefinition?...&resourceKey=userDefined`; without it the call returns 200 with `{"result":"Not found"}`.
- LAN subnets in a non-default segment are not advertised until that VRF is added with `add_local_lan` via `POST /subnets/setSubnetSharingOptions`.
- Zone names allow only letters, digits and `_`. Zones and segment security policies are whole-collection writes: read, add, write back.
- `GET /stats/aggregate/flow` wants `startTime` and `endTime` in epoch seconds; the spec says milliseconds, and millisecond values return an empty result with no error (tested 2026-10-20).
- The other `GET /stats/aggregate/*` reads (tunnel, application2, topTalkers, jitter, mos) also take epoch seconds, against the spec, on 9.7.1 and 10.0.0; alarm and audit windows (`/alarm/*`, `/action`, `/health/alarmPeriodSummary`) take milliseconds, and availability takes a `date` (tested 2026-10-23).
- Availability: `appliancereachability` and `samplecount` are minute counts, so percent = reachable / samples. In tunnel availability `count` is minute samples while `tunnel_state`, `blackout` and `brownout` are seconds, and `tunnel_state` equals `blackout` in every sample seen; the report skill uses 1 - downtime / (count x 60) (9.7.1 and 10.0.0, tested 2026-10-23).
- `GET /stats/timeseries/jitter` needs the deprecated `tunnel` (the internal id, such as `bondedTunnel_5`); the spec calls `tunnelAlias` required and the 400 error asks for `tunnelName`. `GET /stats/aggregate/mos` needs `nePk` (without it: 400 "null does not exist in GMS"), and `GET /stats/aggregate/topTalkers` returns `[]` without one (tested 2026-10-23).
- In `/stats/aggregate/tunnel`, `mos` is MOS x 100 (438 is 4.38); `/stats/aggregate/mos` returns the plain score (tested 2026-10-23).
- `GET /gmsLicense` returns the Orchestrator `licenseKey` in clear; the server now redacts any `licenseKey` field (tested 2026-10-23).
- `GET /flow`: `uptime=anytime` or `last24hr` returns only active flows, and `term24hr` (or no `uptime`) only ended ones, so a count of all flows needs both calls. `application` also takes DPI names outside the spec's list, such as `youtube` (ECOS 9.6.4.0, tested 2026-10-20).
