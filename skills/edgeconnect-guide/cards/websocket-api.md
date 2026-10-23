# Websocket alarm stream
## What it is
The Orchestrator Notification Service over a websocket: a client subscribes to one combined stream of appliance and Orchestrator alarms (or audit logs) and can ask for the active alarms, missed messages or the newest sequence number. The MCP server has no websocket tool, so an agent can only set up and inspect the receiver through REST; the client that holds the socket is outside the MCP.
## Docs
- [Websocket](https://developer.arubanetworks.com/edgeconnect/docs/websocket-api) - the five client operations and request JSON (9.3)
- [Websocket Examples](https://developer.arubanetworks.com/edgeconnect/docs/websocket-examples) - status check and alarm correlation rules (9.3)
- [Orchestrator Notification Service](https://developer.arubanetworks.com/edgeconnect/docs/monitoring-alarms-via-orchestrator) - receiver types, adding a websocket receiver, alarm schema (9.3)
- [Uniquely Identifying Alarms](https://developer.arubanetworks.com/edgeconnect/docs/uniquely-identifying-alarms) - decoding `msgId` (9.3)
- [Remote Log Receivers](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/support/tech-assistance/log-receivers/) - the page behind the REST operations (9.7)
- [Fast Websocket Failover](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/fast-websocket-failover) - a different feature: appliance-to-Orchestrator websocket recovery, needs Orchestrator and ECOS 9.4.2 or later (all)
## Key facts
- Add the receiver under Support > Technical Assistance > Remote Log Receivers > Add Receiver > Websocket: enable it, name it, choose log type (alarms or audit log) and list the source IPs allowed to connect (9.7).
- Client operations: open, request active alarms, request specific alarms by sequence ID, request the latest sequence ID, close (9.3).
- Request shapes, sent as stringified JSON: `ACTIVE_ALARMS` (type and data null), `RESUBMISSION` with type `SEQUENCE_ID` and data such as `["1","2","4-6","7-LATEST"]`, and `LATEST_SEQ_ID` (9.3).
- Active alarms arrive with sequence ID -1 and the latest-ID answer carries sequence ID -2; asking for active alarms pauses the live stream until they are sent (9.3).
- The socket is reliable while up, so alarms are not lost; the extra operations exist to resynchronise after a gap (9.3).
- On-prem Orchestrator needs the client IP on the allow list and the key sent either as header `X-Auth-Token` or as query parameter `key` on the websocket URL (9.3).
- Each message carries `sequenceId`, `timestamp`, `severity`, `msgId`, and a `data` block with `alarmId`, `raisedTime`, `clearedTime`, `source`, `description` and `recommendedAction`; sequence IDs are per receiver (9.3).
- Correlation rules from the docs: all underlays between two appliances down means every overlay is down; an overlay is never down while one underlay is up; an interface failure takes down all tunnels on it (9.3).
## MCP operations
- Find with `find_operations` term "remoteLogReceiver".
- Create the receiver: `POST /remoteLogReceiver` (array body, no `id`; the reply is the list of new ids). Update with `PUT /remoteLogReceiver` (send the object as read); delete with `DELETE /remoteLogReceiver` (`receiverId` query).
- Read: `GET /remoteLogReceiver` (optional `receiverId`), `GET /remoteLogReceiver/websocket/status` (connection state, client IP, last ping and message times), `GET /remoteLogReceiver/sequenceId/latest` (needs `logType`).
- Replay: `POST /remoteLogReceiver/subscribe` (`receiverId` query; body `{"id": ["<id>"], "logType": 0}`).
- Opening the websocket and sending `ACTIVE_ALARMS` or `RESUBMISSION` messages is not available through the MCP server. Poll alarms with `POST /alarm/appliance` (with `api_read_post`; body `nePks`) and `GET /alarm/gms` instead (see alarms-monitoring).
## Gotchas
- Creating the receiver only opens the endpoint; use the websocket status call to confirm a client is actually attached.
- Sequence IDs are per receiver, so keep each consumer's last ID with that receiver's `id`.
- Do not point a receiver at a host you do not control; alarm streams carry hostnames and addresses.
## Related
- [alarms-monitoring](alarms-monitoring.md)
- [api-auth-and-9.3-changes](api-auth-and-9.3-changes.md)
- [snmp-syslog-logging](snmp-syslog-logging.md)
