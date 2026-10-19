# Internet breakout and SaaS
## What it is
How internet-bound traffic is told apart from fabric traffic and where it goes: backhaul, local breakout or a cloud security service. Also SaaS optimization, SaaS NAT and the cloud-service pages that steer internet traffic.
## Docs
- [Internet Traffic](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/overlays/internet-traffic/) - what counts as internet traffic (9.7)
- [Internal Subnets](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/overlays/internal-subnets/) - internal subnet list, non-default routes, segments (9.7)
- [Business Intent Overlays](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/overlays/bios/) - breakout policy order, link selection, IP SLA (9.7)
- [Internet traffic best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/internet-traffic) - routing public IPs back to a data center (all)
- [SaaS Optimization Template](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/saas-opt/) - advertise and optimize behavior, RTT settings (9.7)
- [SaaS NAT Policies Template](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/nat-policies/) - dynamic and manual NAT for SaaS (9.7)
- [SSL for SaaS Template](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/ssl-for-saas/) - certificate side of SaaS optimization (9.7)
- [Microsoft Office 365](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/cloud/o365/) - overlay layout for Office 365 (9.7)
- [Zscaler Internet Access](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/cloud/zscaler/) - tunnels to Zscaler (9.7)
## Key facts
- Internet traffic is anything not in the Internal Subnets list. The list is global across overlays and appliances, defaults to RFC 1918 and ULA, holds up to 512 IPv4 and 512 IPv6 entries, and can be set per segment (9.7).
- To send a public prefix to the data center, add it to the list, or tick "consider non-default routes as internal subnets" and advertise it by BGP, OSPF or local routes. Manual entries are checked first, then the route lookup (all).
- Breakout policy order defaults to Backhaul via Overlay, Break Out Locally and Drop. Services such as Zscaler need a passthrough tunnel per appliance (9.7).
- Hubs can have their own breakout policy (clear "Use Branch Settings") (9.7).
- Local breakout link selection: Waterfall (best label first until about 80% utilization) or Balanced (weighted by free bandwidth). A loss, latency or jitter threshold removes a link from eligibility (9.7).
- Break Out Locally needs the WAN interface set to Stateful+SNAT in the deployment (9.7).
- SaaS optimization needs SSL, subnet sharing and source NAT together, and the appliance must be registered with an account name and key (9.7).
- SaaS NAT policy priorities 40000-50000 are dynamic; do not use that range manually. The default no-NAT policy is 65535 (9.7).
## MCP operations
- Find with `find_operations` terms "internal subnets", "serviceOrchestration".
- Internal subnets: `GET /gms/internalSubnets2`, `POST /gms/internalSubnets2`.
- Breakout per overlay: set in the overlay body, `GET /gms/overlays/config` and `PUT /gms/overlays/config`.
- SaaS: `GET /spPortal/saasClassification`, `POST /applicationDefinition/saasClassification`.
- Third-party breakout services: `GET /thirdPartyServices/serviceOrchestration/serviceProviders`, then `GET /thirdPartyServices/serviceOrchestration/bioBreakout` with `serviceId` taken from the `serviceId` field of the provider list (another field gives 400 "Invalid query parameters"). Changing a breakout service is a UI step.
- Stats: `GET /stats/timeseries/internetBreakout`.
## Gotchas
- `POST /gms/internalSubnets2` was tested by re-posting the current value: read it and post the full object back with your change.
- Traffic matching an internal subnet skips local breakout and cloud security services.
- Office 365 Skype for Business, SharePoint Online and Exchange must break out locally, and the default overlay can use any policy order except Drop (9.7).
- SaaS optimization monitoring may show nothing at a 50 ms threshold; raise the RTT threshold or place the gateway closer (9.7).
## Related
- [overlays-bio](overlays-bio.md)
- [nat](nat.md)
- [optimization](optimization.md)
- [segmentation](segmentation.md)
- [static-routes](static-routes.md)
