# Interfaces and labels
## What it is
Appliance interface status and settings (Interfaces tab) and the global interface labels, WAN labels that Orchestrator uses to build tunnels and LAN labels that tag traffic types.
## Docs
- [Interfaces Tab](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/network/interfaces/) - hardware, dynamic, PoE views and field meanings (9.7)
- [Interface Labels](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/overlays/interface-labels/) - create, edit, delete labels (9.7)
- [Labels best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/labels) - naming and label strategy (all)
- [CLI Reference: Interfaces](https://arubanetworking.hpe.com/techdocs/sdwan-PDFs/cli-ref/CLI-Reference_latest.pdf) - interface commands (all)
## Key facts
- WAN labels name the circuit (MPLS, INET1, LTE); tunnels form between WAN labels per the overlay. LAN labels name traffic types and can match traffic into overlays or be used in rules (9.7).
- Labels are global; Orchestrator pushes them to the appliances it manages. Renaming a label renames the tunnels that use it and affects availability statistics (9.7).
- A label type cannot be changed while the label is in use, and labels used in overlays cannot be deleted. Deleting a label removes it from policies, interfaces and profiles (9.7).
- A WAN label topology of "hub and spoke" excludes that label from full-mesh overlays, useful for CG-NAT circuits (9.7).
- Interface names: blan and bwan are bonded LAN or WAN, bvi0 is the bridge interface, tlan and twan are 10 Gbps fiber (9.7).
- Management interface IPs should be static. Duplex must not be half after negotiation (9.7).
- Recommended starting values (not required): short, all-caps names, symmetric WAN and LAN labels at hubs and branches (all).
- LAN and WAN IP changes are made through the deployment, mgmt0 through hostname/IP settings or CLI (9.7).
## MCP operations
- Find with `find_operations` terms "interface labels", "interfaceState".
- Labels: `GET /gms/interfaceLabels` (optional `type`, `active`; without `active` it returns inactive labels too), `POST /gms/interfaceLabels` (the whole map, wan and lan; add a label under a new id; optional `deleteDependencies`), `POST /interfaceLabels` (push labels to an appliance).
- Interfaces: `GET /interfaceState` (`nePk`, optional `cached`), `GET /deployment`.
- Check use before deleting: `GET /portProfiles/isLabelInUse` (needs `id` and lowercase `side`, `lan` or `wan`; replies `{"inUse": bool, "portProfileIds": [...]}`).
- Assigning a label to an interface means a deployment push: validate with `POST /deployment/validate`, then apply it in the Orchestrator UI.
## Gotchas
- `POST /gms/interfaceLabels` replaces all labels (WAN and LAN) with what you send: read first and post the full map back.
- Each EdgeConnect, an HA pair included, can have one interface per WAN label; a second interface with the same label is refused or raises an alarm (all).
- In a deployment, `applianceIPs[].label` is the label id as a string, and `POST /deployment/validate` does not check it (an unknown id passes), so verify the id against `GET /gms/interfaceLabels` (9.7.1).
- Per-interface `maxBW` in a deployment is `{"inbound": kbps, "outbound": kbps}`; `sysConfig.maxBW` stays an integer.
- A new WAN label needs its tunnel settings (retry count, encryption) before it behaves like the others (all).
- Labels only drive tunnels once an overlay lists them as primary, secondary or backup, and cross connect groups connect different labels (9.7).
## Related
- [overlays-bio](overlays-bio.md)
- [tunnels](tunnels.md)
- [deployment-profiles](deployment-profiles.md)
- [wan-circuits-shaper](wan-circuits-shaper.md)
