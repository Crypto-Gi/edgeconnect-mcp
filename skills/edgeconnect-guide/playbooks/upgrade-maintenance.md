# Plan an upgrade or maintenance window

> **Reference only.** Every step below was run on Orchestrator 9.7.1 (ECOS 9.6.2.1 lab appliances and an ECOS 9.6.4.0 production appliance, test objects only) between 2026-10-16 and 2026-10-18. Your version and configuration can behave differently: read first, show the change, get a yes, and verify each step yourself.

Checklist for a window: gather versions, a baseline and the existing restore points, put the appliances in maintenance mode, and compare after the window. The only write is maintenance mode. Upgrading, uploading images, creating backups, restoring and rebooting are not available through the MCP server; the user does them in the Orchestrator UI. Background: [upgrades and maintenance](../cards/upgrades-maintenance.md).

## Before you start
- Ask the user: target ECOS or Orchestrator version, which appliances, the window, the change number, whether the sites have HA pairs, and who watches the sites.
- Upgrade Orchestrator first: each ECOS release has a minimum Orchestrator release. On-prem Orchestrator upgrades can take hours and are done on the server, not through the API; back it up first.
- Never upgrade or reboot an appliance without the user's explicit yes for that appliance and window.
- Keep every read serialised: `GET /appliancesSoftwareVersions` takes one `nePk` per call.

## Steps
1. Call `api_get` on `GET /gms/versions` (Orchestrator), `GET /appliance` (the appliances, models, hostnames), then `GET /appliancesSoftwareVersions` once per `nePk` for ECOS versions. It returns one entry per partition; the running one has `active: true`. Add `GET /release` (ECOS builds are listed under `vxoabuilds`, Orchestrator builds under `gmsbuilds`) and `GET /vxoaImages` for what is available or already stored.
2. Call `find_operations` with "upgrade" to show the user the upgrade operations; the server refuses them as high risk, so the upgrade is a UI step. Compatibility is checked in the release notes and compatibility matrix in the card's Docs. Do not continue for any appliance the matrix lists as incompatible with the target.
3. Capture the baseline with `api_get` just before the window: `GET /alarm/count/appliance` (`nePk`), `GET /alarm/summary`, `GET /tunnels2/bonded` and `GET /tunnels2/physical` (per `nePk`), `GET /bgp/state` and `GET /ospf/config/system` (needs `nePk`, `fromGms`) per `nePk` where used, `GET /subnets` (needs `cached`, `nePk`; route counts), `GET /flow` (needs `nePk`, `maxFlows`) and `GET /stats/timeseries/appliance` (see [flows and stats](../cards/flows-stats.md) for its required parameters; if every stats call returns 500, the Orchestrator's stats database is the problem). Save the results for the comparison.
4. Check recovery with `api_get`: `GET /gms/backup` (Orchestrator backup settings; HTTP 404 means no backup is configured, so report that and do not treat it as an error) and `GET /appliance/backup` (needs `nePk`) for existing appliance backups. A new backup is made by the user in the Orchestrator UI (Backup Now, with the change number in the comment). Tell the user the 5 minute gap between EdgeHA peers and that hardware bypass drops flows on a single unit.
5. Maintenance mode: `api_get` `GET /maintenanceMode` and `GET /pauseOrchestration` to see what is already set. Show the user the body `{"action": "add", "nePks": ["<nePk>"], "data": {"pauseOrchestration": ["<nePk>"], "suppressAlarm": ["<nePk>"]}}` and tell them that suppressing alarms clears the appliance's open alarms, which come back with new ids after removal. After a yes, `api_write` `POST /maintenanceMode` with it, then re-read both GETs.
6. The upgrade itself is run by the user in the Orchestrator UI (Administration > Software Management > Upgrade Appliances: install and reboot, install and set next boot partition, or install only). While it runs, poll `api_get` `GET /appliance` until each appliance is reachable again (`state` 1).
7. After the window wait 5 minutes (10 to 15 if tunnels are still coming up), then repeat the step 3 reads with `api_get` and compare: ECOS versions (`GET /appliancesSoftwareVersions`), tunnels up, BGP established, alarms, route counts (investigate a change above 5), flows per hub.
8. End maintenance mode: after a yes, `api_write` `POST /maintenanceMode` with the step 5 body and `"action": "remove"`. If `GET /pauseOrchestration` still lists the appliance, `POST /pauseOrchestration` takes the whole list: post the step 5 read (`[]` when it was empty). Re-read both GETs.

## Verify
- Every target appliance shows the new ECOS version in `GET /appliancesSoftwareVersions` (`active: true`) and reachable status in `GET /appliance`.
- Tunnel, BGP, OSPF, alarm and route-count comparisons match the baseline, or each difference is explained to the user (suppressed alarms return with new ids).
- Maintenance mode was removed (`GET /maintenanceMode` and `GET /pauseOrchestration` no longer list the appliances).
- The user takes a Backup Now after, with the change number in the comment (see [Orchestrator settings and backup](../cards/orchestrator-settings-backup.md)).
