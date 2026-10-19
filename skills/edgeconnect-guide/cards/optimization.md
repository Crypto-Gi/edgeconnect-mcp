# Optimization policies
## What it is
TCP and WAN optimization rules that choose, per flow, Network Memory, compression and TCP or protocol acceleration. These need a Boost license; SaaS optimization is a separate feature.
## Docs
- [Optimization Policies Tab](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/policy/opt-policies/) - priorities, set actions, TCP acceleration options (9.7)
- [Optimization Policies Template](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/opt-policies/) - template version of the same rules (9.7)
- [Optimization Policies best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/optimization-policies) - template set to replace (all)
- [SaaS Optimization Template](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/saas-opt/) - SaaS services to optimize or advertise (9.7)
- [CLI Reference: Policy Maps (NAT, Optimization, QoS, Shaper)](https://arubanetworking.hpe.com/techdocs/sdwan-PDFs/cli-ref/CLI-Reference_latest.pdf) - optimization map commands (all)
## Key facts
- Set actions: Network Memory (Maximize Reduction, Minimize Latency, Balanced default, Disabled), IP header compression, payload compression, TCP acceleration, protocol acceleration for SSL, SRDF, Citrix and iSCSI (9.7).
- The site that starts the flow (the client side) decides the protocol-specific optimization state (9.7).
- Priorities follow the other policy maps: template owns 1000-9999 and deletes that range on apply, 1-999 higher, 10000-19999 and 25000-65534 lower, 20000-24999 reserved (9.7).
- TCP acceleration advanced options (MSS adjust to tunnel MTU, SYN option exchange, slow LAN defense, WAN congestion control optimized / standard / aggressive and more) ship with defaults; change them only with Support guidance (9.7).
- Disable "Enable TCP SYN option exchange" if a LAN-side firewall drops SYNs that carry the unfamiliar option (9.7).
- Recommended: apply an Optimization template set to replace, even a blank one, to prevent configuration drift. It is used only with a Boost license (all).
- Each overlay has its own WAN Optimization enabled or disabled setting (9.7).
## MCP operations
- Find with `find_operations` terms "optimizationMaps", "flowOptimization", "boost".
- Read: `GET /optimizationMaps` (`nePk`, optional `cached`), `GET /flow/flowOptimization`, `GET /stats/aggregate/boost`.
- SSL side: `GET /ssl`, `GET /sslCACertificate`.
- Optimization maps are changed in a template group: `GET /template/templateGroups`, then save only the Optimization template with `POST /template/templateGroups` as `{"name", "valObject"}`. Saving pushes it to every associated appliance.
## Gotchas
- Applying the template deletes every rule at priority 1000-9999 first.
- An overlay with WAN Optimization set to Disabled does not get WAN optimization for its traffic; check the overlay before blaming the policy (9.7).
- Optimization on asymmetric routes may need route policy override or flow redirection; read the TCP options page before changing it (9.7).
## Related
- [qos](qos.md)
- [internet-breakout-saas](internet-breakout-saas.md)
- [overlays-bio](overlays-bio.md)
- [route-policies](route-policies.md)
- [wan-circuits-shaper](wan-circuits-shaper.md)
