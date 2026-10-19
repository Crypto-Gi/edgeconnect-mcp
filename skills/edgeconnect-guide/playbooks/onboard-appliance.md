# Onboard and approve an appliance

> **Reference only.** Every step below was run on Orchestrator 9.7.1 (ECOS 9.6.2.1 lab appliances and an ECOS 9.6.4.0 production appliance, test objects only) between 2026-10-16 and 2026-10-18. Your version and configuration can behave differently: read first, show the change, get a yes, and verify each step yourself.

Bring a discovered EdgeConnect under Orchestrator, with a preconfiguration file ready before approval. Background: [appliance onboarding](../cards/appliance-onboarding.md).

## Before you start
- The appliance has checked in to the Cloud Portal and shows as discovered. On a lab it needs DHCP and outbound TCP 443; never change the DHCP setting of `wan0.4000` or `mgmt0`.
- Approving, adding, denying or deleting a discovered appliance, and applying a preconfiguration file, are not available through the MCP server; the user does them in the Orchestrator UI. Creating, validating, reading, changing and deleting preconfiguration files works through the server.
- UI path for approval: Configuration > Overlays & Security > Discovery > Discovered Appliances, select the appliance, Approve, pick the group and network role. Then Discovery > Preconfiguration to apply the file.
- Write only on an Orchestrator where writes are enabled and the user agreed. Collect: serial number (or tag for EC-V), hostname, site name, network role (0 non-hub, 1 hub, 2 NR-hub), group id.

## Steps
1. Call `api_get` on `GET /appliance/discovered` and find the serial; call `api_get` on `GET /appliance/approved` to confirm it is not already managed, `GET /gms/group` for the group id (such as `1.Network`) and `GET /gms/versions` for the Orchestrator version. Stop if the serial is not discovered: see the [onboarding card](../cards/appliance-onboarding.md) gotchas.
2. Call `describe_operation` on `POST /gms/appliance/preconfiguration` (body `name`, `configData` base64 YAML, `serialNum` or `tag`, `comment`, `autoApply`), then `api_get` on `GET /gms/appliance/preconfiguration/default` for the template listing every option. Keep only the sections you need; on lab appliances leave the deployment and interface sections out, or keep the `mgmt0` and `wan0.4000` DHCP settings exactly as read; policies (QoS, security) belong in template groups named under `templateGroups.groups`, see [template groups](../cards/templates-groups.md).
3. Build the YAML, base64 it, and check it with `api_write` `POST /gms/appliance/preconfiguration/validate` (body `configData`, optional `serialNum`, `name`). Validate saves nothing. Success is an empty (null) body. A problem is HTTP 400 with `YAML format incorrect, line:L, column:C`, or `YAML invalid, Unrecognized field: "x"` for a key it does not know. Fix every error before continuing.
4. Show the user the YAML and the body (`name`, `serialNum` or `tag`, `autoApply` false, `comment`). After a yes, call `api_write` `POST /gms/appliance/preconfiguration`. Keep `autoApply` false unless the user wants approval to apply it without a prompt. The reply is `{"id": n}`; `n` is the `preconfigId` for the later steps.
5. Call `api_get` on `GET /gms/appliance/preconfiguration` with `preconfigId` to read the file back; it returns one object. `filter` takes only `names` (a list of names) or `metadata` (files without `configData`), so it cannot select by name. Then `api_write` `POST /gms/appliance/preconfiguration/findMatch` (body `tag`) to confirm the file matches the appliance: it returns the file, or HTTP 404 when nothing matches.
6. To change the file (a comment or the YAML), show the user the whole object as read in step 5 with the change, and after a yes `api_write` `PUT /gms/appliance/preconfiguration` with query `preconfigId` and that full body. Read it back with `api_get` as in step 5.
7. Approval and apply happen in the Orchestrator UI (path in Before you start); give the user the path and wait until they say it is done. Then poll `api_get` on `GET /appliance/approved` and `GET /appliance` (`nePk`) until the appliance is reachable, and `GET /gms/appliance/preconfiguration/apply` (needs `preconfigId`) for the apply status. On a file that was never applied it answers `{"result": [], "completionStatus": false, "taskStatus": 0, ...}`. Software upgrade and config push can take 10 minutes and a reboot.
8. Rollback of the file only: after a yes, `api_write` `DELETE /gms/appliance/preconfiguration` with query `preconfigId`, then `api_get` `GET /gms/appliance/preconfiguration` to confirm it is gone. Removing an approved appliance is done in the Orchestrator UI (Administration > Software Management > Remove Appliance; see [onboarding](../cards/appliance-onboarding.md) Docs).

## Verify
- `GET /appliance` (with `nePk`) lists the appliance with the expected hostname and group.
- `GET /gms/appliance/preconfiguration/apply` (`preconfigId`) shows the apply finished, and `GET /deployment` (needs `nePk`, `cached` false) shows the interfaces and labels from the file.
- `GET /template/applianceAssociation` (`nePk`) lists the template groups named in the file; see [deployment profiles](../cards/deployment-profiles.md) and [licensing](../cards/licensing.md) for what the file does not cover.
- No new critical alarms: `POST /alarm/appliance` with body `nePks`.
