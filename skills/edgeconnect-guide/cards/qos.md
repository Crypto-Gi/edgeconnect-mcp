# QoS and DSCP
## What it is
QoS policies that assign flows to shaper traffic classes and decide whether to trust or rewrite DSCP markings on the LAN and WAN side. The shaper defines the classes, the QoS policy assigns traffic to them.
## Docs
- [QoS Policies Tab](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/policy/qos-policies/) - rules, priorities, match criteria, DSCP handling (9.7)
- [QoS Policies Template](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/qos-policies/) - template version with priority range and prefix rules (9.7)
- [Schedule QoS Map Activation](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/policy/schedule-qos-map/) - time-based QoS maps (9.7)
- [Shaper/QoS Policy best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/shaper-1) - template, guest example, class tuning (all)
- [CLI Reference: Policy Maps (NAT, Optimization, QoS, Shaper)](https://arubanetworking.hpe.com/techdocs/sdwan-PDFs/cli-ref/CLI-Reference_latest.pdf) - QoS map commands (all)
## Key facts
- Set actions do two things: choose the traffic class and set LAN QoS and WAN QoS DSCP behavior. Both default to trust-lan (9.7).
- Optimized (tunneled) traffic: LAN QoS marks the inner header, WAN QoS marks the outer encapsulation header, which the far appliance strips (9.7).
- Passthrough traffic has no outer header: the LAN QoS action is ignored and WAN QoS replaces the existing marking, which stays on the packet to its destination (9.7).
- Priorities: the template owns 1000-9999 and deletes that whole range when applied; 1-999 beats it, 10000-19999 and 25000-65534 are lower; 20000-24999 is reserved. New rules step by 10 (9.7).
- Match criteria are shared across route, QoS, optimization, SaaS NAT and security maps: application, address map, domain, geo, interface, protocol, DSCP, IP/subnet, port, overlay, fabric or internet, user role (9.7).
- Prefix rules: four-octet form, ranges with a dash, a wildcard covers a whole octet, and CIDR cannot be mixed with a range or wildcard (9.7).
- Recommended starting values (not required): always push a QoS template, even a blank one; match guest traffic by label or segment rather than by interface (all).
- QoS maps can be scheduled by time from a template group already applied to the appliances (9.7).
## MCP operations
- Find with `find_operations` terms "qosMaps", "dscp", "trafficClass".
- Read: `GET /qosMaps` (`nePk`, optional `cached`), `GET /shaper`.
- Stats: `GET /stats/aggregate/dscp`, `GET /stats/timeseries/dscp`, `GET /stats/aggregate/trafficClass`, `GET /stats/timeseries/trafficClass`.
- QoS maps are changed in a template group: `GET /template/templateGroups`, then save only the QoS template with `POST /template/templateGroups` as `{"name", "valObject"}`. Saving pushes it to every associated appliance.
## Gotchas
- Applying the QoS template deletes every rule at priority 1000-9999 on the appliance, including hand-made ones.
- Overlays also set traffic class and LAN/WAN DSCP and show up as QoS entries; check both when markings look wrong (9.7).
- The shaper uses deployment bandwidth, so wrong circuit bandwidth skews every class (all).
## Related
- [wan-circuits-shaper](wan-circuits-shaper.md)
- [overlays-bio](overlays-bio.md)
- [optimization](optimization.md)
- [nat](nat.md)
- [route-policies](route-policies.md)
