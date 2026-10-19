# SNMP, syslog and logging
## What it is
Monitoring and log export. Appliance side: the SNMP agent and trap receivers, local log levels, facilities and remote syslog servers. Orchestrator side: remote log receivers for audit logs and alarms, and the audit log of what Orchestrator and users did.
## Docs
- [SNMP Template](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/snmp/) - agent, v1/v2c, v3 users, trap receivers (9.7)
- [SNMP](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/administration/general/snmp/) - per-appliance summary and edit (9.7)
- [Logging Template](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/logging/) - severity, facilities, remote syslog, anonymize, JSON (9.7)
- [Logging Tab](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/administration/general/logging/) - per-appliance log settings (9.7)
- [Audit Logs](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/orchestrator/server/audit-logs/) - Orchestrator and user actions, filters (9.7)
- [Orchestrator Remote Log Receivers](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/support/tech-assistance/log-receivers/) - HTTP, HTTPS, Kafka, syslog, WebSocket receivers (9.7)
- [Orchestrator and EdgeConnect Logging](https://arubanetworking.hpe.com/techdocs/sdwan/docs/white-paper/) - log types and syslog formats (9.5)
- [Logging best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/logging-1) - severity and facilities (all)
- [Audit logs best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/audit-logs) - reading audit logs while a site comes up (all)
- [CLI Reference: Logging and Monitoring](https://arubanetworking.hpe.com/techdocs/sdwan-PDFs/cli-ref/CLI-Reference_latest.pdf) - logging, alarms, flow-export commands (all)
- [CLI Reference: Management Access and Security](https://arubanetworking.hpe.com/techdocs/sdwan-PDFs/cli-ref/CLI-Reference_latest.pdf) - `snmp-server` commands (all)
## Key facts
- SNMP agent supports MIB-II and the EdgeConnect private MIBs, and sends cold and warm start traps plus a trap whenever an alarm is raised or cleared (9.7).
- Template fields: Enable SNMP, Enable SNMP Traps, default trap community (default `public`), read-only community (default `public`), up to three trap receivers each with host, version, community or v3 user, enabled flag (9.7).
- SNMP v3 users: SHA-1 authentication and AES-128 privacy are the only choices, and both passwords need at least 20 characters (9.7).
- Local logging: minimum severity, log file size and number of logs to keep, and one facility (local0 to local7) each for System, Audit, Firewall and IDS/IPS. The four facilities must be unique (9.7).
- Recommended starting value (not required): severity Notice everywhere; Info or Debug only when support asks, and for chosen devices only, because Debug slows packet forwarding (9.7).
- A minimum severity of None sends nothing, and the remote syslog server has its own severity filter that must accept what you forward (9.7).
- Remote syslog receivers: host, port (2 to 65535), UDP, TCP or TCP SSL, minimum severity, facility, optional client certificate and server verification for TCP SSL (9.7).
- Anonymize IPs masks log addresses (all, /8, /16 or /24); Jsonify exports firewall and IDS/IPS messages as JSON (9.7).
- Orchestrator receivers send audit logs or alarms as HTTP POST (HTTP, HTTPS, Kafka, WebSocket) or TCP/UDP (syslog). The page shows last-minute delay, queued and dropped counts per receiver (9.7).
- Audit Logs filter by status, level, appliance and user (`*` wildcard); default record count 500, maximum 10000 (9.7).
## MCP operations
- Find with `find_operations` terms "snmp", "logging", "remoteLogReceiver", "action".
- Appliance SNMP and logging (read): `GET /snmp` (needs nePk), `GET /logging` (needs nePk; `cached=false` for live), `GET /mgmtServices` (needs nePk) for the source interface of the syslog and SNMP services.
- Appliance SNMP and logging are set in the SNMP and Logging templates of a template group: `GET /template/templateGroups` with `templateGroup`, then save only that template with `POST /template/templateGroups` as `{"name", "valObject"}`.
- Orchestrator receivers: `GET /remoteLogReceiver` (optional `receiverId`), `POST /remoteLogReceiver` (body array, no `id`; the reply is the list of new ids), `PUT /remoteLogReceiver` (array, send the object as read), `DELETE /remoteLogReceiver` (`receiverId` query), `GET /remoteLogReceiver/websocket/status`.
- In receiver bodies `receiverType` is a number (0 HTTP, 1 HTTPS, 2 Kafka, 3 syslog, 4 WebSocket). A syslog receiver (3) needs `hostname`, `port` (as a string), `protocol`, `auditFacility`, `alarmFacility` and all seven severity fields; without them the post fails with 400 "auditFacility is missing or invalid".
- Subscribe a receiver: `POST /remoteLogReceiver/subscribe` (`receiverId` query, body `{"id": ["<id>"], "logType": 0}`).
- Audit log: `GET /action` (needs startTime, endTime; optional `limit`, `logLevel`, `appliance`, `username`).
- Global alarm notification switch: `POST /alarm/notification` (post the object back as read with your change).
## Gotchas
- Two syslog paths exist: appliance syslog (template, per appliance) and Orchestrator receivers (alarms and audit logs). Configure the one that carries what you need.
- Facilities in the Logging template must not overlap; give System, Audit, Firewall and IDS/IPS different localN values.
- `GET /remoteLogReceiver` leaves out the header value of HTTP and HTTPS receivers, so resend it when you update one.
- Audit logs show Orchestrator pausing for minutes between steps while a site comes up; wait before troubleshooting (all).
## Related
- [ids-ips](ids-ips.md)
- [security-zones-firewall](security-zones-firewall.md)
- [ntp-time](ntp-time.md)
- [aaa-users](aaa-users.md)
