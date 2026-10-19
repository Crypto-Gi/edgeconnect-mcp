# Deployment and Deployment Profiles
## What it is
The per-appliance deployment (mode, interfaces, labels, zones, segments, bandwidth, NAT and firewall mode) and Deployment Profiles, reusable templates that provision a device with a standard layout.
## Docs
- [Deployment Tab](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/network/deployment/) - summary and detail fields, modes, EdgeHA, firewall modes (9.7)
- [Deployment Profiles](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/overlays/dep-profiles/) - label mapping, segments and zones, LAN DHCP and relay (9.7)
- [Deployment - EdgeHA](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/overlays/deploy-edgeha/) - EdgeHA pairing in the deployment (9.7)
- [Deployment best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/deployment-1) - circuit comments, export, check Stateful+SNAT (all)
- [CLI Reference: Interfaces](https://arubanetworking.hpe.com/techdocs/sdwan-PDFs/cli-ref/CLI-Reference_latest.pdf) - interface and deployment commands (all)
## Key facts
- Modes: Inline Router (use this), Bridge (bvi0, legacy WAN optimization) and Server (management and data on mgmt0) (9.7).
- Interface types: physical (wan0), sub-interface (wan0.100), IP alias (wan0:1) (9.7).
- WAN firewall modes: Allow All, Stateful (behind a WAN edge router), Stateful+SNAT (directly on the internet), Harden (IPsec tunnel and management traffic only) (9.7).
- WAN labels are mandatory and drive overlay tunnel building; LAN labels are optional. WAN segment cannot be changed (9.7).
- IP/Mask is appliance-specific and cannot be edited in a profile. Fill in DHCP Server Defaults before building profiles (9.7).
- Inbound and outbound bandwidth set here feeds the shaper; set it to the real circuit rate (all).
- EdgeHA: both appliances need the same site name and IPsec over UDP tunnel mode; the HA link uses a LAN or WAN port, never mgmt (9.7).
## MCP operations
- Find with `find_operations` terms "deployment", "portProfiles".
- Read the live deployment: `GET /deployment` (needs `nePk` and `cached`), `GET /interfaceState`, `GET /tunnelsConfiguration/deployment`.
- Deployment Profile templates: `GET /portProfiles/config`, `POST /portProfiles/config` (a copy of an existing profile renamed, no `id`; the reply is the new id as a quoted UUID string), `PUT /portProfiles/config` (needs `id`), `DELETE /portProfiles/config` (needs `id`); `GET /portProfiles/isLabelInUse` (needs `id` and lowercase `side`, `lan` or `wan`; replies `{"inUse": bool, "portProfileIds": [...]}`) checks a label before removal.
- Validate a change first: `GET /appliance/rest` with `nePk` and url `deployment`, edit the object, then `POST /deployment/validate` (replies `{"err": null, "rebootRequired": bool}`). In the deployment a label is the label id as a string, per-interface `maxBW` is `{"inbound": kbps, "outbound": kbps}` and `sysConfig.maxBW` is an integer.
- Pushing the deployment is not covered by this guide; apply it in the Orchestrator UI.
## Gotchas
- A deployment change can drop the WAN or LAN interface it touches. Never change the DHCP setting of wan0.4000 or mgmt0 on the lab.
- Validate the whole deployment object, keeping every interface as read.
- Each WAN label can appear once per appliance (EdgeHA pair included); a duplicate blocks the save or raises an alarm (all).
- Many staged appliances that are offline but not in maintenance mode slow down saving deployments in Orchestrator (9.7).
- Changing a label name in a profile renames the tunnels that use it (9.7).
## Related
- [interfaces-labels](interfaces-labels.md)
- [dhcp](dhcp.md)
- [wan-circuits-shaper](wan-circuits-shaper.md)
- [vrrp-ha](vrrp-ha.md)
- [segmentation](segmentation.md)
- [tunnels](tunnels.md)
