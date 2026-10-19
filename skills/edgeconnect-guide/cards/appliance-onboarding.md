# Appliance onboarding and preconfiguration
## What it is
Bringing a new EdgeConnect into Orchestrator: the appliance shows up as discovered, is approved (or auto-approved through a preconfiguration file), and then gets its deployment, overlays and template groups. Covers discovery, approval and denial, preconfiguration files, the configuration wizard, local setup when there is no DHCP, and removal.
## Docs
- [Discovered Appliances](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/overlays/discoverd-appliances/) - approve, deny, show denied devices, account-key approval rule (9.7)
- [Preconfigure Appliances](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/overlays/preconfig/) - YAML file matched by serial or tag, auto approve (9.7)
- [Appliance Configuration Wizard](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/overlays/appliance-wizard/) - guided setup, recommended configuration list (9.7)
- [Adding a New Appliance](https://arubanetworking.hpe.com/techdocs/sdwan/docs/troubleshooting/add_appliance/) - why an appliance does not appear or register (9.7)
- [USB-Based Zero Touch Provisioning](https://arubanetworking.hpe.com/techdocs/sdwan/docs/deployments/deploy-html/usb-ztp/) - provisioning without network access at the site (9.7)
- [Remove Appliance from Orchestrator](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/administration/sw-mgmt/remove-appliance/) - decommissioning (9.7)
- [RMA Wizard](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/support/tech-assistance/rma/) - replace a failed unit (9.7)
- [Adding appliance to Orch](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/adding-appliance-to-orch) - field-tested walk-through and wizard settings (all)
- [Day 0 Preconfiguration and Templates](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/day-0-preconfiguration-and-templates) - what belongs in the file and what needs a template (9.6)
- [Local Appliance Setup](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/local-device-setup) - static-IP sites, MGMT0 and MGMT1 access (all)
## Key facts
- Factory defaults are DHCP on WAN0, WAN1, WAN2 and MGMT0; an appliance with DHCP and outbound HTTPS (443) to the internet checks in to the Cloud Portal and then appears under Discovered Appliances (all).
- Approve moves it under Orchestrator management; Deny hides it and Show Denied Devices plus Discover brings it back (9.7).
- A second Orchestrator using the same account name and key must be approved by the Orchestrator that was deployed first (9.7).
- A preconfiguration file is matched by serial number or appliance tag (tag is the match key for EC-V); with Auto Approve on it loads without a prompt, otherwise a user confirms the match (9.7).
- After approval the software upgrade and configuration push run automatically (9.7).
- The file carries per-appliance values (hostname, interfaces, IPs, bandwidth, HA, licensing, BGP neighbors, VRRP); policies such as QoS, security and ACLs need template groups, named under `templateGroups.groups` in the file (9.6).
- Most sections replace the appliance value when the file is applied again; `businessIntentOverlays`, `managementRoutes`, `tunnelConfiguration` and `pppoe` merge instead (9.6).
- Recommended starting values (not required): WAN FW zone Untrust with Stateful+SNAT, router mode, deployment bandwidth 1 to 5 percent under the paid circuit (cable about 90 percent), a different WAN label on every WAN interface including both EdgeHA peers (all).
- If a firewall sits in front of the WAN, allow UDP 12000 and 12010 (or the configured tunnel ports) and TCP 443 out without SSL inspection; the port rises by 10 per extra appliance with the same site name (all).
- MGMT0 and MGMT1 never build tunnels and their traffic is not shown in Active and Recent Flows; use MGMT0 only to onboard (all).
- Appliances added by hand are not licensed; an appliance can only be added once discovered (9.7).
## MCP operations
- Find with `find_operations` terms "appliance/discovered", "preconfiguration", "applianceWizard".
- List: `GET /appliance/discovered`, `GET /appliance/approved`, `GET /appliance` (optional `nePk`), `GET /gms/group` (group ids for approval).
- Approving, adding, denying or deleting a discovered appliance is not available through the MCP server; do it in the Orchestrator UI (Discovered Appliances). Re-discovering an appliance is not covered by this guide; do it in the Orchestrator UI.
- Preconfiguration files: `GET /gms/appliance/preconfiguration` (optional `preconfigId` returns one object; optional `filter` takes `names` or `metadata`), `POST /gms/appliance/preconfiguration` (body `name`, `configData` as base64 YAML, `serialNum`, `tag`, `comment`, `autoApply`; reply `{"id": n}`), `PUT /gms/appliance/preconfiguration` (needs `preconfigId`; send the whole object as read, for example with a new `comment`), `DELETE /gms/appliance/preconfiguration` (needs `preconfigId`).
- Preconfiguration helpers: `GET /gms/appliance/preconfiguration/default` (template with every option), `POST /gms/appliance/preconfiguration/validate` (checks without saving; success is a null body, errors are 400 with a line and column or an unknown key), `POST /gms/appliance/preconfiguration/findMatch` (body `tag`; returns the file, 404 when none matches).
- Apply status: `GET /gms/appliance/preconfiguration/apply` (needs `preconfigId`; works on a file that was never applied), `GET /gms/applianceWizard/apply` returns the running wizard (9.7.1; it timed out on a 10.0 Orchestrator), then `GET /action/status` (needs `key`).
- Applying a preconfiguration file and running the appliance wizard are not available through the MCP server; do them in the Orchestrator UI after approval.
- Pre-flight: `POST /deployment/validate` (needs `nePk`) checks a deployment body and replies `{"err": null, "rebootRequired": bool}`.
## Gotchas
- A discovered appliance only appears after the Cloud Portal knows the serial; an air-gapped Orchestrator uses its own discovery flow (see the Air-Gap guide).
- The wizard and deployment steps can take 10 minutes and sometimes need a reboot; a greyed-out appliance with a question mark is not talking to Orchestrator (all).
- Do not change the DHCP setting of WAN or MGMT interfaces on the lab appliances while onboarding.
- Pushing the deployment is not covered by this guide; apply it in the Orchestrator UI (see deployment-profiles).
## Related
- [deployment-profiles](deployment-profiles.md)
- [templates-groups](templates-groups.md)
- [licensing](licensing.md)
- [interfaces-labels](interfaces-labels.md)
- [loopback-orchestration](loopback-orchestration.md)
