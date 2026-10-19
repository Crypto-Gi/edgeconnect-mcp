# Licensing and Cloud Portal
## What it is
Appliance licences (EC-Enterprise tiers, metered, WAN Optimization and Advanced Security add-ons), the Orchestrator's own licence and registration with the Cloud Portal (account name and key, secondary accounts, Air-Gap mode), and how a licence limits features and bandwidth.
## Docs
- [Licenses](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/overlays/licenses/) - summary and per-appliance views, tiers, assign and revoke (9.7)
- [Cloud Portal (configuration)](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/overlays/cloud-portal/) - account name and key registration (9.7)
- [Cloud Portal (Orchestrator server)](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/orchestrator/server/cloud-portal/) - secondary accounts, AAS licence token, UUID (9.7)
- [Air-Gap](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/orchestrator/server/air-gap/) - isolated deployments, registration key exchange, file upload (9.7)
- [Licensing troubleshooting](https://arubanetworking.hpe.com/techdocs/sdwan/docs/troubleshooting/licensing/) - appliance will not register, Orchestrator portal reachability (9.7)
- [Remove Appliance from Orchestrator and Account](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/administration/sw-mgmt/remove-appliance-from-account/) - frees the licence (9.7)
- [Adding appliance to Orch](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/adding-appliance-to-orch) - licence choice in the wizard, circuit versus licensed bandwidth (all)
## Key facts
- Enterprise subscription tiers are Foundation, Advanced and On-Prem. Foundation allows up to three BIOs, two VRF segments, limited QoS, monitor-only AppExpress and four regions; Advanced and On-Prem allow up to seven BIOs, the maximum segments and regions, and AppExpress monitor and steer (9.7).
- Bandwidth tiers differ by subscription: Foundation 100 Mbps, 1 Gbps and Unlimited; Advanced 20 Mbps up to 2 Gbps and Unlimited (9.7).
- Add-ons: WAN Optimization (billed per Mbps per month) and Advanced Security / Dynamic Threat Defense (IDS/IPS, adaptive DDoS, SYN cookie, web security intelligence), which must be bought for every appliance (9.7).
- Bulk licence assignment needs every selected appliance on the same software version (9.7).
- If the circuit is faster than the licence, the shaper is automatically held at the licence limit (all).
- Registration needs the exact account name (case sensitive) and key; a stray space or typo stops registration (9.7).
- If an appliance reaches Orchestrator through another EdgeConnect, that intermediate one must be licensed too (9.7).
- Appliances added to Orchestrator by hand are never licensed; only discovered appliances can be (9.7).
- A self-hosted Orchestrator needs HTTPS and websocket reachability to the Cloud Portal; a second Orchestrator must be approved by the first one (9.7).
- Secondary accounts (up to 11) allow different licence end dates; hardware must sit in the same account as its licences, and any change to one secondary account re-registers all of them (9.7).
- The AAS licence token refreshes from the Cloud Portal every 24 hours and decides which Orchestrator features are available (9.7).
- Air-Gap mode is only for self-hosted Orchestrators and cannot be turned off once enabled except by Support (9.7).
## MCP operations
- Find with `find_operations` terms "license", "gmsLicense", "spPortal".
- Orchestrator licence: `GET /gmsLicense`, `GET /gmsLicense/validation` (needs `licenseKey`; checks a key without applying it), `GET /gmsLicense/aas/token/usage` (feature use against limits), `GET /license/managementSettings` (which appliance types are enabled).
- Portal licences: `GET /license/portal/summary` (optional `cached`), `GET /license/portal/summary/account`, `GET /license/portal/appliance` (optional `cached`), `GET /license/portal/appliance/account` (needs `nePk`), `GET /license/portal/appliance/account/discovered` (needs `discoveredId`), `GET /spPortal/status` (health of portal services).
- Applying an Orchestrator licence key, assigning, granting or revoking appliance licences and portal registration are not available through the MCP server; do them in the Orchestrator UI (Licensing).
## Gotchas
- Tier and feature licence calls need a minimum ECOS (tier 8.1.7.19 or later, feature licences 9.1.0.0 or later), so check `GET /appliancesSoftwareVersions` first.
- Revoking removes the appliance's base licence at the Cloud Portal; confirm the exact appliance first. Revoking the EC licence also revokes its WAN Optimization, advanced and legacy feature licences, and the licence must be revoked before an RMA (9.7).
- A metered appliance stops passing traffic when its licence expires (9.7).
- Licensing reads need the Orchestrator registered with the Cloud Portal; on an Air-Gap Orchestrator they return local cached data.
## Related
- [appliance-onboarding](appliance-onboarding.md)
- [optimization](optimization.md)
- [ids-ips](ids-ips.md)
- [wan-circuits-shaper](wan-circuits-shaper.md)
- [overlays-bio](overlays-bio.md)
