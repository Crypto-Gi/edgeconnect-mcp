# Software upgrades and maintenance windows
## What it is
Upgrading ECOS on appliances and Orchestrator itself, checking ECOS and Orchestrator compatibility, planning the order, and running a maintenance window with before and after evidence (checklists, one-pager, maintenance mode, scheduled reboots).
## Docs
- [Upgrade Appliance Software](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/administration/sw-mgmt/upgrade-appliance-sw/) - upload or URL, compatibility check, install options (9.7)
- [Software Versions](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/administration/sw-mgmt/sw-versions/) - ECOS version per appliance (9.7)
- [Check for Orchestrator and Appliance Software Updates](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/orchestrator/sw-setup/check-for-updates/) - available downloads (9.7)
- [Upgrade Orchestrator or Stats Collectors](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch-install-upgrade/upgrade-orch-or-stats-coll/) - on-prem script and cloud upgrade, 9.6 stats collector note (9.7)
- [ECOS and Orchestrator Release Compatibility](https://arubanetworking.hpe.com/techdocs/sdwan/docs/sysreq/compat/ecos_orch/) - earliest Orchestrator for each ECOS release (9.7)
- [ECOS Compatibility Matrix](https://arubanetworking.hpe.com/techdocs/sdwan/docs/sysreq/compat/comp_matrix/) - hardware against ECOS (9.7)
- [Release Notes](https://arubanetworking.hpe.com/techdocs/sdwan/release-notes/) - fixes, known issues, behaviour changes per release (all)
- [Maintenance Mode](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/orchestrator/server/maint-mode/) - pause orchestration and suppress alarms (9.7)
- [Schedule an Appliance Reboot](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/administration/tools/schedule-reboot/) - reboot, erase network memory and reboot, shutdown (9.7)
- [Verified upgrade path](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/upgrade-path) - interactive planner for older versions; its content does not come through as text (all)
- [Maintenance Window One-Pager](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/maintenance-window-one-pager) - paired before and after checks (all)
- [Before Maintenance Window Checklist](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/before-outage-window-checklist) - baseline captures and filenames (all)
- [After Maintenance Window Checklist](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/post-maintenance-window-checklist) - the same list repeated and compared (all)
## Key facts
- Each ECOS release has a minimum Orchestrator release, for example ECOS 9.6.2.1 needs Orchestrator 9.6.2.40190 or later and ECOS 9.7.0.0 needs 9.7.0.43264; upgrade Orchestrator first (9.7).
- Appliance upgrade steps: pick targets, upload an image or give a URL, check compatibility (do not proceed when incompatible), choose an install option, upgrade, then watch Status until Success (9.7).
- Install options: install and reboot; install and set next boot partition; install only (stores the image in the inactive partition). Check no users are logged in on the appliance first (9.7).
- Physical appliances go to hardware bypass in bridge mode or an open-port state in router mode while rebooting; flows drop unless the pair is in a high-availability design (9.7).
- Maintenance mode from the appliance tree suppresses alarms and pauses orchestration together; the Orchestrator menu lets you choose each. Paused orchestration still keeps IPsec UDP key material current (9.7).
- Upgrading on-prem Orchestrator can take several hours; back it up first because a failed upgrade can leave it corrupt. From 9.6.0 the old distributed Stats Collector data is not migrated automatically (9.7).
- Cloud Orchestrator is upgraded from Orchestrator > Software & Setup > Upgrade and is unavailable while it runs (9.7).
- Recommended starting values (not required): capture the baseline just before the window, not days ahead; after the change wait 5 minutes, or 10 to 15 if tunnels are still coming up, before comparing; take a Backup Now before and after with the change number in the comment; set NMS maintenance mode too (all).
- Compare before and after for alarms, reachability, overlay/underlay/passthrough tunnels, routes (investigate a count change above 5), BGP peers Established, OSPF neighbours, flows per hub, and critical application tests (all).
- A hand-exported routes CSV cannot show a primary-to-backup flip; check critical prefixes in the UI (all).
## MCP operations
- Find with `find_operations` terms "vxoaImages", "maintenanceMode", "release".
- Versions: `GET /gms/versions`, `GET /appliancesSoftwareVersions` (needs `nePk`; optional `cached`), `GET /release` (available Orchestrator and ECOS releases), `GET /release/notifications`, `GET /vxoaImages` (images stored on Orchestrator), `GET /appliance` for model, hostname and running ECOS (`softwareVersion`). `GET /release` can be stale: on a 10.0 Orchestrator it listed builds only up to 9.4.1, so judge whether an appliance is behind from the fleet's own versions and the release notes.
- Maintenance mode: `GET /maintenanceMode`, `POST /maintenanceMode` with body `{"action": "add", "nePks": [nePk], "data": {"pauseOrchestration": [nePk], "suppressAlarm": [nePk]}}`; `"remove"` with the same body clears it. Pause list alone: `GET /pauseOrchestration`, `POST /pauseOrchestration` (whole list; `[]` clears it).
- Backups around the window: read with `GET /appliance/backup` (needs `nePk`); see orchestrator-settings-backup.
- Uploading images, upgrading and rebooting appliances, upgrading the Orchestrator and creating backups are not available through the MCP server; do them in the Orchestrator UI. Validating an upgrade path is not covered by this guide; do it in the Orchestrator UI.
## Gotchas
- `GET /appliancesSoftwareVersions` needs one `nePk` per call; loop over appliances and serialise the calls.
- Setting `suppressAlarm` clears the appliance's open alarms; they come back with new ids after `remove`.
- Never upgrade appliances ahead of the Orchestrator version they require; the portal check can say incompatible and the UI says not to continue.
- Remove maintenance mode after the window, otherwise alarms stay suppressed and orchestration stays paused.
## Related
- [orchestrator-settings-backup](orchestrator-settings-backup.md)
- [alarms-monitoring](alarms-monitoring.md)
- [vrrp-ha](vrrp-ha.md)
- [appliance-onboarding](appliance-onboarding.md)
- [licensing](licensing.md)
- [flows-stats](flows-stats.md)
