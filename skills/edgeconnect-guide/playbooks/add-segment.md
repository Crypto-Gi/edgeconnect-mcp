# Add a segment (VRF) and map interfaces

> **Reference only.** Every step below was run on Orchestrator 9.7.1 (ECOS 9.6.2.1 lab appliances and an ECOS 9.6.4.0 production appliance, test objects only) between 2026-10-16 and 2026-10-18. Your version and configuration can behave differently: read first, show the change, get a yes, and verify each step yourself.

Create a segment on an Orchestrator with segmentation on and prepare the deployment that moves an interface into it. Background: [segmentation](../cards/segmentation.md).

## Before you start
- Needs Orchestrator and appliances on 9.0 or later, in Inline Router mode, with routing segmentation already on. Turning segmentation on is Orchestrator-wide (every appliance, existing config moves into the Default segment, end-to-end zone-based firewall comes on) and is not covered by this guide; the user turns it on in the Orchestrator UI, in a window.
- Segment names allow letters, digits and underscores. Creating the segment changes nothing on the wire; moving an interface into it moves that interface's traffic and can cut it off.
- Pushing the deployment is not covered by this guide; apply it in the Orchestrator UI. This playbook validates the interface move; the user pushes it.
- With segmentation on, do not use a templated zone firewall policy; use segment policies (see [zones and rules](../cards/security-zones-firewall.md)).
- Lab names: `ztest_seg`, one lab appliance; never change the DHCP setting of `wan0.4000` or `mgmt0`.

## Steps
1. Call `api_get` on `GET /vrf/config/enable` (stop if segmentation is off: see Before you start), `GET /vrf/config/segments` (ids and names), `GET /zones/vrfSegmentZonesMap`, `GET /subnets/all` (needs `nePk`, shows subnets per segment) and `GET /appliance/rest` with `nePk` and `url` `deployment`.
   Also read the current sharing options with `GET /appliance/rest` (`nePk`, `url` `system/auto_subnet`): `auto_subnet` holds `self`, a `vrf` map keyed by segment id and `vrf_pruning`. `subnets3/configured` holds only the static routes. Keep `auto_subnet` and the deployment object as the rollback snapshot.
2. Call `describe_operation` on `POST /vrf/config/segments` (body `name`).
3. Show the user the name. After a yes, call `api_write` `POST /vrf/config/segments` with `{"name": "ztest_seg"}`. The reply is `{"id": n}`, the new segment id (segment ids are not reused); confirm it by reading `GET /vrf/config/segments`. The Orchestrator adds one zone per global zone name for the new segment, with new ids: re-read `GET /zones/vrfSegmentZonesMap` to see them. A rename is `PUT /vrf/config/segments` with query `id`.
4. Advertising the segment's LAN subnets (subnet sharing for the new segment) is not covered by this guide; the user sets it in the Orchestrator UI. Afterwards re-read `api_get` `GET /appliance/rest` (`nePk`, `url` `system/auto_subnet`) and show the user the new segment's entry.
5. Prepare the interface move with the `api_get` `GET /appliance/rest` (`url` `deployment`) object from step 1: on the target `applianceIPs` entry set `vrf` to the segment id and `zone` to a zone id listed for the new segment in `GET /zones/vrfSegmentZonesMap`, and keep every other interface. `vrf` and `zone` are integers on every `applianceIPs` entry. Put the interface in a zone only once that zone's rules exist ([zones](../cards/security-zones-firewall.md)).
6. Check it with `api_write` `POST /deployment/validate` (needs `nePk`; body `sysConfig`, `modeIfs`, `dpRoutes` as read, with the edit). It answers `{"err": null, "rebootRequired": bool}`; tell the user if a reboot is needed. Validate checks types only, not existence (a string zone is refused with HTTP 400, `vrf` 999 passed), and a new segment may not yet appear in the appliance's `sysConfig.vrfs`. Show the user the diff. Pushing the deployment is not covered by this guide; apply it in the Orchestrator UI.
7. Per-segment policy, each its own change with its own read first (`api_get`, then `api_write` after a yes): overlays (include or skip each overlay for the segment; a Skip with no other match drops traffic) with the [overlay playbook](business-intent-overlay.md), zones and segment pair rules with the [zones playbook](security-zones-rule.md), BGP peers with the [BGP playbook](bgp-neighbors.md). Background: [overlays](../cards/overlays-bio.md), [BGP](../cards/bgp.md), [OSPF](../cards/ospf.md), [loopbacks](../cards/loopback-orchestration.md).
8. Rollback: if the user pushed the interface move, they undo it in the Orchestrator UI first and you compare `api_get` `GET /deployment` (`nePk`, `cached` false) with the step 1 object. If the user changed subnet sharing, they undo it in the Orchestrator UI. Then, after a yes, `api_write` `DELETE /vrf/config/segments` with query `id`; the delete also removes the segment's zones. Re-read `GET /vrf/config/segments`, `GET /zones/vrfSegmentZonesMap` and `GET /appliance/rest` (`url` `system/auto_subnet`) and compare with step 1. Segmentation stays on.

## Verify
- `GET /vrf/config/segments` lists the segment with the intended id and name; `GET /zones/vrfSegmentZonesMap` shows its zones.
- After the user's sharing change: `GET /appliance/rest` (`url` `system/auto_subnet`) shows `add_local_lan` true for the segment, and `GET /subnets/all` (`nePk`) shows the segment's LAN subnets.
- After the user's push: `GET /deployment` (`cached` false) shows the interface with the intended `vrf` and `zone`; `GET /interfaceState` shows it up.
- Routes and neighbours per segment: `GET /bgp/config/allVrfs/neighbor`, `GET /ospf/config/allVrfs/system`, `GET /zones/vrfZonesMap` (all need `nePk`).
