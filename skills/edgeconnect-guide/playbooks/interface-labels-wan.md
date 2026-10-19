# Set interface labels and WAN circuits

> **Reference only.** Every step below was run on Orchestrator 9.7.1 (ECOS 9.6.2.1 lab appliances and an ECOS 9.6.4.0 production appliance, test objects only) between 2026-10-16 and 2026-10-18. Your version and configuration can behave differently: read first, show the change, get a yes, and verify each step yourself.

Add or change a global WAN or LAN interface label, then prepare the appliance deployment that maps it to an interface and its circuit bandwidth. Background: [interface labels](../cards/interfaces-labels.md), [deployment](../cards/deployment-profiles.md), [WAN circuits](../cards/wan-circuits-shaper.md).

## Before you start
- `POST /gms/interfaceLabels` replaces every label (WAN and LAN) with what you send. A label left out is removed, so always send the whole map.
- Each appliance (an EdgeHA pair counts as one) can have one interface per WAN label, and every WAN interface needs its own label.
- Pushing the deployment is not covered by this guide; apply it in the Orchestrator UI. This playbook changes the labels and validates the deployment edit; the user pushes it in a window, one appliance first.
- Never change the DHCP setting of `wan0.4000` or `mgmt0`.
- Collect: label name (short, all caps recommended), WAN or LAN, hub-and-spoke topology needed (CG-NAT circuits), the appliance `nePk`, interface name, real circuit bandwidth in kbps. Lab name: `ztest_wan`.

## Steps
1. Call `api_get` on `GET /gms/interfaceLabels` and keep the whole response (it is the rollback snapshot and the base for the new list). Also read `GET /interfaceState` (needs `nePk`) and `GET /appliance/rest` with `nePk` and `url` `deployment`: that appliance-shaped object is the base for the deployment edit in step 6. On 9.7.1 `GET /deployment` (needs `nePk`, `cached` false) returned the same object; use it for comparison. Also `GET /gms/versions`.
2. Call `describe_operation` on `POST /gms/interfaceLabels` (body `wan` and `lan`, each keyed by label id with `name`, `active`, `topology`) and on `POST /deployment/validate` (needs `nePk`).
3. Build the label body: the full snapshot from step 1 with your label added under a new id (one above the highest id in the map, because ids in gaps can belong to inactive labels; `topology` 0 normal, 2 hub-and-spoke). To rename, change `name` in place; never remove an entry to rename it. Before removing a label, call `api_get` on `GET /portProfiles/isLabelInUse` with `id` and `side` in lower case (`lan` or `wan`); it answers `{"inUse": bool, "portProfileIds": [...]}`.
4. Show the user the complete body and the diff against the snapshot. After a yes call `api_write` `POST /gms/interfaceLabels` with that body.
5. A successful post answers null, so the read-back is the proof. Read back with `api_get` `GET /gms/interfaceLabels` and compare every id, `name`, `active` and `topology` against the intended list. If anything differs or is missing, restore it (step 8).
6. Prepare the deployment edit with the `api_get` `GET /appliance/rest` (`url` `deployment`) object from step 1. Edit only the target entry of `modeIfs[].applianceIPs[]`: `label` takes the label id as a string (for example `"2"`), not the name. Validate does not check labels (it accepted an unknown id and a plain name), so check the id yourself against `GET /gms/interfaceLabels`. The circuit rate is that entry's `maxBW`, `{"inbound": kbps, "outbound": kbps}`; `sysConfig.maxBW` stays a single integer for the whole system (an object there is refused with HTTP 400), so leave it alone. `sysConfig.ifLabels` lists labels as `{"id": "<id>", "name": "<name>"}` with string ids; validate passes with or without the new label there. Keep every other interface.
7. Check the edited object with `api_write` `POST /deployment/validate` (needs `nePk`; body `sysConfig`, `modeIfs`, `dpRoutes` as read, with your edit). It answers `{"err": null, "rebootRequired": bool}`. Show the user the diff and say so if a reboot is needed. Pushing the deployment is not covered by this guide; apply it in the Orchestrator UI (the appliance's Deployment page, same values as the validated object).
8. Rollback: after a yes, `api_write` `POST /gms/interfaceLabels` with the original label snapshot from step 1, then read it back with `api_get` `GET /gms/interfaceLabels` and compare. If the user pushed a deployment change, they undo it in the Orchestrator UI; compare `GET /deployment` (`cached` false) with the step 1 object afterwards.

## Verify
- `GET /gms/interfaceLabels` equals the intended list (`active` true, right `topology`).
- After the user's push: `GET /interfaceState` (`nePk`) shows the interface up, and `GET /deployment` (`cached` false) matches the validated object; the label appears once per appliance.
- The label only builds tunnels after an overlay lists it: see [overlays](../cards/overlays-bio.md) and [tunnels](../cards/tunnels.md). Check `GET /tunnels2/physical` (`nePk`) for the new tunnels and no new alarms (`POST /alarm/appliance`, body `nePks`).
- New WAN label: set its tunnel retry count and encryption before relying on it. Shaper and deployment bandwidth feed each other; see [WAN circuits](../cards/wan-circuits-shaper.md).
