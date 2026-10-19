# IP SLA
## What it is
IP SLA rules poll an interface, a ping target, an HTTP/HTTPS URL or a VRRP state, and take an action when the result changes: disable a breakout tunnel, withdraw or re-metric subnets, change VRRP priority, revoke a route-label route, or only raise an alarm. Orchestrator also creates IP SLA rules itself for internet breakout and for cloud security services.
## Docs
- [IP SLA Tab](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/policy/ipsla/) - monitor types, down and up actions, six use cases (9.7)
- [IPSLA best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/ipsla) - targets, starting values, SSE and breakout rules (all)
- [Business Intent Overlays](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/overlays/bios/) - breakout settings the IP SLA tab refers to for IPv6 targets (9.7)
## Key facts
- Monitor choices: Interface (operational state), Ping (IPv4 address), HTTP/HTTPS (needs a 200 response, redirects unsupported), VRRP Monitor (true when Master) (9.7).
- HTTP/HTTPS monitors must not use a loopback source interface. If the source is a tunnel, a second source interface supplies the packet's source IP. In the URL field, only an https URL needs the scheme written (9.7).
- Down actions include remove auto subnets, increase or decrease VRRP priority, enable or disable a passthrough tunnel, disable subnet sharing, modify subnet metric, advertise subnets, raise alarm only. Up actions: default subnet action, VRRP default, tunnel enable or disable, VRRP priority, clear alarm only. A default up action must match the down action (9.7).
- A route label can be attached to a rule so a static route is revoked when the rule is down; whether one down rule or all must be down is the label's IP SLA condition (9.7).
- IPv6 local breakout needs IPv6-capable targets and Orchestrator 9.6 or later (9.6+).
- A rule is marked down only when all its targets are down (all).
- Recommended starting values (not required): one DNS target plus one IP target, so DNS failure alone does not isolate the appliance; ping interval 1 second, rolling average 60, reachability zeroed, loss as the main trigger and latency used carefully; Check IPSLA interval not below 10 (use 15 or 20 on heavily loaded appliances, or shorten the rolling average to about 30 for faster reaction); HTTP/HTTPS polling not below 2 (all).
- HPE-owned test endpoints for the default breakout rule are `sp-ipsla.silverpeak.cloud` (IPv4 only) and `sp-ipsla2.silverpeak.cloud` (IPv4 and IPv6) (all).
- Breakout IP SLA and cloud-service (SSE, Zscaler, Netskope) IP SLA are separate and each must be set up; overlays without a breakout option get no orchestrated IP SLA (all).
- For SSE rules the best practice tests through the service and uses a loopback source interface so firewall rules stay simple (all).
## MCP operations
- Find with `find_operations` terms "ipsla".
- Read rules and state: `GET /ipsla/config/managers` and `GET /ipsla/state/managers` (both need `nePk` and `fromGms`). `GET /appliance/rest` with `nePk` and url `ipsla/config/managers` reads the same rules.
- Editing IP SLA rules on an appliance is not covered by this guide; do it in the Orchestrator UI.
- Stats: `POST /stats2/aggregate/ipsla` (needs startTime, endTime, granularity; body `nePks`).
- Orchestrated rules for cloud services: `GET /thirdPartyServices/zscaler/ipslaSetting`, `GET /thirdPartyServices/netskope/ipslaSetting`, `GET /thirdPartyServices/axis/ipslaSetting` (HPE SSE), `GET /thirdPartyServices/serviceOrchestration/ipslaSetting` (needs `serviceId`, the `serviceId` field of `GET /thirdPartyServices/serviceOrchestration/serviceProviders`). Zscaler's setting is written with `POST /thirdPartyServices/zscaler/ipslaSetting` (body `enableIpslaRuleOrchestration`).
- Zscaler tunnels with their IP SLA status: `GET /thirdPartyServices/zscaler/connectionStatus` (needs nePk).
## Gotchas
- Rules Orchestrator creates for breakout and cloud services come from the overlay and cloud-service settings; change targets there rather than on the appliance rule.
- Too aggressive intervals or a low rolling window make healthy links flap; start loose and tighten.
- Latency thresholds are measured to the IP SLA targets only, not end to end (all).
## Related
- [internet-breakout-saas](internet-breakout-saas.md)
- [overlays-bio](overlays-bio.md)
- [vrrp-ha](vrrp-ha.md)
- [static-routes](static-routes.md)
- [dns](dns.md)
