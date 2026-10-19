# Orchestrator settings, orchestration and backups
## What it is
Orchestrator-wide switches that decide how and when it pushes configuration (Orchestration Settings, tunnel UDP ports, pausing), plus backups: the Orchestrator database and Stats Collector (self-hosted only), appliance configuration backups, restore, and the Snapshot Sentinel before/after comparison tool.
## Docs
- [Orchestration Settings](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/orchestrator/server/orchestration/) - orchestrate, reset flows, autosave, apply templates, idle time, IPsec UDP ports (9.7)
- [Schedule Orchestrator Backup](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/orchestrator/sw-setup/schedule-backup/) - destination, retention, schedule, appliance backup behaviour (9.7)
- [Schedule Stats Collector Backup](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/orchestrator/sw-setup/schedule-stats-backup/) - separate destination and schedule for stats (9.7)
- [Back Up on Demand](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/orchestrator/sw-setup/backup/) - Orchestrator database backup now (9.7)
- [Appliance Configuration Backup](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/administration/sw-mgmt/appliance-config-backup/) - per-appliance backup now (9.7)
- [Restore a Backup to an Appliance](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/administration/sw-mgmt/restore-backup/) - restore cautions (9.7)
- [View Configuration History](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/administration/sw-mgmt/view-config-history/) - compare stored configurations (9.7)
- [Move or Restore Orchestrator](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch-install-upgrade/move-backup-restore/) - rebuilding a self-hosted server from a backup (9.7)
- [Orchestrator Blueprint Export](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/orchestrator/server/blueprint/) - clean template of the server configuration (9.7)
- [Orchestration Settings best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/orchestration-settings) - idle time, flow reclassify, firewall rules (all)
- [Orchestrator Backup best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/orchestrator-backup) - why backups are mandatory when self-hosted (all)
- [Snapshot Sentinel](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/snapshot-sentinel) - before and after comparison of exported fabric tables (all)
- [Initial Orchestrator settings](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/initial-orchestrator-settings) - starting point for the other settings pages (all)
## Key facts
- Orchestration Settings switches: orchestrate appliances (on by default; off stops overlay pushes and IPsec UDP tunnel creation and rebuilds), reset all flows on overlay or policy edits, autosave appliance changes, apply templates, idle time, auto flow reclassify (9.7).
- Recommended starting values (not required): idle time 30 seconds under about 100 appliances, 60 above; leave auto flow reclassify at 60 because a low value can crash during a flow burst such as a security scan (all).
- IPsec UDP: the 9.7 page gives default port 10002 and an EdgeHA increment such as 1000; the best-practice page describes 12000 and 12010 with steps of 10 per appliance sharing a site name. Read the live values instead of assuming (9.7).
- Scheduled Orchestrator backups exist only on self-hosted servers and cover the Orchestrator and appliance configs; destination protocols are FTP, SCP, HTTP, HTTPS and SFTP, with a Test button and a maximum number to retain (9.7).
- Cloud Orchestrator has no scheduled backup. Appliance configs are also backed up automatically: the schedule page says daily at 12:00 and a file is kept only if it changed, while the appliance backup page says weekly (9.7).
- The Stats Collector can follow the Orchestrator backup settings or have its own; if you untick the shared setting and fill nothing in, it is not backed up (9.7).
- Restoring from a backup older than the latest loses config changes and appliances added since, and IPsec UDP tunnels can blip while the new seed applies; a static mgmt0 IP in the backup can clash (9.7).
- Self-hosted: set up and test the backup in the first-run wizard; losing the Orchestrator does not stop the data path but removes management and visibility (all).
- Snapshot Sentinel compares a before and an after set of exported tables (routes, tunnels, BGP, OSPF, alarms, flows, reachability) and reports MISSING, NEW and CHANGED rows; the automated variant needs a Read-Only API key and a PC that can reach Orchestrator (all).
## MCP operations
- Find with `find_operations` terms "overlayManagerProperties", "backup", "pauseOrchestration".
- Orchestration settings: `GET /overlayManagerProperties`, `GET /overlayManagerProperties/default` (factory values), `POST /overlayManagerProperties` (post the object back as read with your change; tested by re-posting the current value).
- Pause per appliance: `GET /pauseOrchestration`, `POST /pauseOrchestration` (body is the whole list of nePks and replaces the existing list; `[]` clears it); for alarms too, use `POST /maintenanceMode` (see upgrades-maintenance).
- Tunnel key material: `GET /ikeless/config`, `GET /ikeless/seedStatus`, `GET /ikeless/seedHistory`.
- Backup reads: `GET /gms/backup` (404 means no backup is configured), `GET /statsCollector/backup/useGmsConfig` (HTTP 401 on a container-mode Orchestrator, 10.0), `GET /appliance/backup` (needs `nePk`), `GET /appliance/restore/status` (needs `nePk`).
- Related reads: `GET /gmsserver/info`, `GET /gms/versions`, `GET /gms/scheduleTimezone`, `GET /gms/advancedProperties`.
- Creating, restoring or deleting backups, changing the backup destination and changing advanced properties are not available through the MCP server; do them in the Orchestrator UI.
## Gotchas
- Turning orchestration off stops tunnel creation and repair fleet-wide; turn it back on and check `GET /pauseOrchestration` is empty.
- `POST /pauseOrchestration` replaces the whole list; read it first and send the union.
- Run a backup before any upgrade or large template change and keep the backup comment with the change number.
- The Snapshot Sentinel is a downloadable page on the developer portal, not an API; its hand-export route table cannot see a primary-to-backup flip, so spot-check critical prefixes.
## Related
- [upgrades-maintenance](upgrades-maintenance.md)
- [templates-groups](templates-groups.md)
- [ntp-time](ntp-time.md)
- [snmp-syslog-logging](snmp-syslog-logging.md)
- [flows-stats](flows-stats.md)
