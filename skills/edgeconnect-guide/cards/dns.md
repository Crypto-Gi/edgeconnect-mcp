# DNS servers and DNS proxy
## What it is
Two things share the name. The appliance resolver (name servers and search domains the EdgeConnect itself uses) and the DNS proxy (the appliance answers LAN clients and forwards by domain to chosen servers, with caching).
## Docs
- [DNS Template](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/dns/) - name servers and domain names pushed to appliances (9.7)
- [DNS Proxy Template](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/dns-proxy/) - proxy interface, Server A and B, caching (9.7)
- [DNS (Domain Name Servers) Tab](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/administration/general/dns/) - per-appliance view and edit (9.7)
- [Management Services](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/network/mgmt-svcs/) - source interface the DNS service uses per segment (9.7)
- [DNS best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/dns-1) - server order, source interface, air-gap (all)
- [CLI Reference: System Settings](https://arubanetworking.hpe.com/techdocs/sdwan-PDFs/cli-ref/CLI-Reference_latest.pdf) - includes the `dns cache` command (all)
## Key facts
- Appliance DNS servers serve only traffic the EdgeConnect generates itself, such as Cloud Portal and Orchestrator lookups. Application identification and the flow table use DNS snooping, not these servers (all).
- If the appliance cannot resolve names it is isolated from the portal and Orchestrator (all).
- The user guide describes up to three name servers per appliance plus a list of domain names; the best practice page describes four slots (primary to quaternary). Check what the template on your Orchestrator offers (9.7).
- Recommended starting values (not required): external resolvers in the first two slots with source interface `any`, internal resolvers in the last slots with a LAN or loopback source interface (all).
- A DNS service on a loopback in a dedicated zone (for example MGMT) needs a firewall rule allowing DNS between zones (all).
- Air-gap or no-internet sites: replace the default 8.8.8.8 and 8.8.4.4 with an RFC 1918 DNS reachable without tunnels, or point the appliance at Orchestrator and the portal by IP address instead of name (all).
- DNS proxy is configurable only when loopback interfaces exist. Settings: on or off, loopback or LAN-side label, Server A addresses with their domain names, Server B for domains that match nothing in A, caching (on by default). Clear DNS Cache wipes both servers' cache (9.7).
- The source interface of the DNS service is a management service setting (`app_dns` in the API), which can be pinned to an interface and segment (9.7).
## MCP operations
- Find with `find_operations` terms "resolver", "dnsProxy", "mgmtServices", "dns".
- Read the resolver: `GET /resolver` (needs nePk; optional `cached`) returns name servers and search domains.
- Read the proxy: `GET /dnsProxy/config` (needs nePk; optional `cached`) returns profiles, domain groups and maps.
- Read DNS cache and snooping: `GET /appliance/dnsCache/config` (needs nePk; optional `cached`).
- Read the service source interfaces: `GET /mgmtServices` (needs nePk; optional `cached`).
- The same reads work through `GET /appliance/rest` with `nePk` and url `resolver` or `dnsProxy/config`.
- Stats: `GET /stats/aggregate/dns` (needs nePk, startTime, endTime).
- No Orchestrator write for resolver or proxy in the 9.7.1 spec. Change them in the Orchestrator UI, or in the DNS template of a template group (`GET /template/templateGroups` with `templateGroup`; see templates-groups for saving one template with `POST /template/templateGroups`).
## Gotchas
- Wrong or unreachable DNS isolates an appliance, so change one site first and confirm portal and Orchestrator reachability before pushing wider.
- `cached=true` reads Orchestrator's copy; use `cached=false` to see what the appliance currently has.
- A dns template in a group that is last in `templateGroupsPriorities` wins over the same template in earlier groups.
## Related
- [ntp-time](ntp-time.md)
- [security-zones-firewall](security-zones-firewall.md)
- [interfaces-labels](interfaces-labels.md)
- [loopback-orchestration](loopback-orchestration.md)
