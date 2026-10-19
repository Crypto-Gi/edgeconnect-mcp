# Date, time zone and NTP
## What it is
Time zone and clock source for appliances (manual or NTP servers), pushed by the Date/Time template, plus the separate time zone Orchestrator uses for scheduled jobs and reports.
## Docs
- [Date/Time Setting](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/date-time/) - template fields, NTP servers, how stats time is stored (9.7)
- [Date/Time Tab](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/administration/general/date-time/) - per-appliance view, time drift against Orchestrator and browser (9.7)
- [Timezone for Scheduled Jobs](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/orchestrator/sw-setup/timezone-jobs/) - Orchestrator-side job time zone (9.7)
- [Date/Time best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/appliance-time) - default template, per-region groups, firewall rules (all)
- [CLI Reference: System Settings](https://arubanetworking.hpe.com/techdocs/sdwan-PDFs/cli-ref/CLI-Reference_latest.pdf) - `clock set`, `clock timezone`, NTP commands (all)
## Key facts
- Template choices: pick a time zone, then Manual or NTP Time Synchronization. Manual matches the appliance to your web client's clock at the moment the template is applied (9.7).
- NTP servers are entered by IP or host name with protocol version 3 or 4. With several servers, they are used in the listed order; two or more are recommended (9.7).
- Orchestrator stores all stats in UTC and shows them in the browser's time zone (9.7).
- Appliance clocks should be within one minute of Orchestrator and the browser; a larger gap raises an appliance alarm and gives mismatched timestamps in charts (9.7).
- Recommended starting values (not required): set the zone and NTP servers in the default template (UTC is the default zone); if sites span time zones, make a separate template group for Date/Time per zone (all).
- Template group order decides which Date/Time wins over the default template (all).
- NTP must be allowed by the firewall: a loopback in the MGMT zone needs rules for NTP and the NIST time sources (all).
- The scheduled-jobs time zone is an Orchestrator setting and does not change any appliance clock (9.7).
## MCP operations
- Find with `find_operations` terms "timezone", "systemInfo".
- Orchestrator job time zone: `GET /gms/scheduleTimezone`, `POST /gms/scheduleTimezone` (body `defaultTimezone`, a Java time zone ID such as `Europe/London`; post the object back as read with your change), `GET /gms/scheduleTimezone/allTimezones` lists valid IDs.
- Appliance clock: `GET /systemInfo` (`nePk`, `cached`) includes the appliance `datetime` and `gmtOffset`.
- Appliance time and NTP servers are set in the Date/Time template of a template group: read with `GET /template/templateGroups` (`templateGroup`), save only that template with `POST /template/templateGroups` as `{"name", "valObject"}` (see templates-groups). On the lab, template apply stopped at the Date/Time template; confirm with `GET /template/history` (`nePk`, `latestOnly` true) that it applied.
## Gotchas
- `GET /systemInfo` with `cached=true` shows Orchestrator's last copy, so compare with `cached=false` when checking drift.
- The appliance passthrough has no `ntp` url (`GET /appliance/rest` returns 404); read the clock from `GET /systemInfo` and the NTP servers from the Date/Time template.
- If NTP is not syncing, check the firewall rule for NTP from the zone the NTP traffic leaves from (see security-zones-firewall).
## Related
- [dns](dns.md)
- [security-zones-firewall](security-zones-firewall.md)
- [snmp-syslog-logging](snmp-syslog-logging.md)
