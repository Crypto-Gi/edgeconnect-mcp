# Firewall zones and zone-based firewall
## What it is
Zone-based firewall (ZBFW): zones are named on Orchestrator and attached to interfaces and overlays, and security policies decide which zone-to-zone traffic is allowed, denied or sent to IDS/IPS. With routing segmentation on, policies live per segment pair.
## Docs
- [Firewall Zones](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/overlays/fw-zones/) - zone naming and default zone behaviour (9.7)
- [Appliance Security Policies](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/overlays/appliance-security-policies/) - matrix and table views, rule fields, segmentation behaviour (9.7)
- [Security Policies Template](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/security-policies/) - template version, implicit drop logging, wildcard matching (9.7)
- [Firewall Drops](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/monitoring/security/firewall-drops/) - drop statistics per zone pair (9.7)
- [ZBFW/Segment/ACL tips](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/zbfw-tips-and-tricks) - rule limits, end-to-end evaluation, ACL logic (all)
- [Security Zones best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/security-zones) - starter zone list and MGMT zone rules (all)
- [Security Features Guide](https://arubanetworking.hpe.com/techdocs/sdwan-PDFs/docs/tips/Security-Guide-9.5-Release-latest.pdf) - firewall design overview, WAN interface modes (9.5)
- [CLI Reference: Segmentation](https://arubanetworking.hpe.com/techdocs/sdwan-PDFs/cli-ref/CLI-Reference_latest.pdf) - segment zone commands on the appliance (all)
## Key facts
- Same-zone traffic is allowed and different-zone traffic is dropped until a security policy says otherwise; new interfaces and overlays start in the Default zone (9.7).
- A zone name is 16 characters or fewer, letters, digits and underscore only, and cannot be Default (9.7).
- Creating a zone and moving one interface into it cuts that interface off from everything still in Default, so do it in a maintenance window (9.7).
- Rule actions are Allow, Deny and Inspect (send to IDS/IPS); a rule also has priority, match criteria, enabled flag, logging level, tag and comment (9.7).
- Implicit drop logging for inter-zone traffic defaults to Alert (9.7).
- With segmentation on, define policies per segment pair on the Routing Segmentation (VRF) page. Same-named zones in two segments are different zones; inter-segment traffic is denied by default (9.7).
- A security policy template applied while segmentation is on only affects the default segment and overrides its policy; remove it once migrated (9.7).
- Recommended starting values (not required): ALL CAPS zone names, create the most used zones first because order cannot change, a MGMT zone for loopbacks with rules for DNS, NTP and the Orchestrator app group (all).
- ZBFW is stateful; at most 6000 rules (all).
- End-to-end ZBFW checks the destination zone from the route table at the source appliance and drops there; regional routing must be on for hairpin traffic (all).
- In a rule, a referenced ACL means "match this ACL": permit lines match, deny lines exclude (all).
- Prefix match: four-octet IPv4, `-` for ranges, `*` only for a whole octet, and CIDR cannot be mixed with range or wildcard (9.7).
## MCP operations
- Find with `find_operations` terms "zones", "security policies", "securityMaps".
- Zones: `GET /zones` (optional `allVRFZones`), `GET /zones/nextId`, `GET /zones/vrfZonesMap`, `GET /zones/vrfSegmentZonesMap`.
- Write zones: `POST /zones` replaces the whole zone map. The body is the `GET /zones` global list (no `allVRFZones`) plus the new zone at `GET /zones/nextId`. With segmentation on, the Orchestrator creates one copy of the zone per segment; posting the original list removes them all. Never post the `allVRFZones` view (9.7.1).
- End-to-end switch: `GET /zones/eeEnable`, `POST /zones/eeEnable` (body `enable`).
- Segment policies: `GET /vrf/config/securityPoliciesSegments` lists `srcSeg_dstSeg` keys; `GET /vrf/config/securityPolicies` (needs `map`) and `POST /vrf/config/securityPolicies` (needs `map`, body `data`; optional `comment`).
- Policy body shape: the `map` query is the segment pair (`srcSeg_dstSeg`); the keys of `data.map1` are zone pairs (`<srcZoneId>_<dstZoneId>`), and `.prio.<priority>` holds `match`, `set.action`, `comment`, `misc`; `options` takes `merge` and `templateApply`.
- Appliance view: `GET /securityMaps` (needs `nePk`) returns the rules on one appliance.
- Stats: `GET /stats/aggregate/securityPolicy` (needs nePk, startTime, endTime, granularity), `GET /stats/timeseries/securityPolicy` (adds fromZone, toZone).
- Without segmentation the rules are the `securityMaps` template in a template group: `GET /template/templateGroups`, `POST /template/templateGroups` (needs `templateGroup`).
- Moving an interface into a zone is a deployment change: `POST /deployment/validate` can check it, but apply it in the Orchestrator UI.
## Gotchas
- Zones and segment security policies are whole-collection writes: read, add your zone or rule, write the full collection back.
- `POST /zones` removes any zone left out of the body, which breaks interfaces and rules that use it.
- `POST /vrf/config/securityPolicies` with `options.merge` false replaces every zone pair of the segment pair in `map`, not only the pair you edit. Always post the whole `data` object as read, with your change in it; a body with one zone pair deletes the others (9.7.1).
- `GET /securityMaps` (`nePk`) can lag the Orchestrator by more than 15 seconds.
- Flows denied with the reason "outbound pkt new dst zone" or "Zone change detected on outbound packet" have their own troubleshooting video, linked from the Security Policies Template page (9.7).
- ZBFW does not replace WAN interface firewall mode; see deployment-profiles for stateful and hardened modes.
## Related
- [segmentation](segmentation.md)
- [firewall-protection-profile](firewall-protection-profile.md)
- [ids-ips](ids-ips.md)
- [deployment-profiles](deployment-profiles.md)
- [regional-routing](regional-routing.md)
- [nat](nat.md)
