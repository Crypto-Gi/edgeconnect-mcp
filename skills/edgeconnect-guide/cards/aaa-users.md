# Authentication, users and RBAC
## What it is
Two separate user systems. Orchestrator users log in to Orchestrator (local, RADIUS, TACACS+, OAuth, JWT or SAML, with MFA and RBAC roles). Appliance users log in to the EdgeConnect itself (local admin and monitor accounts, or RADIUS and TACACS+), and are pushed by templates.
## Docs
- [Orchestrator Users](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/orchestrator/server/manage-users/) - Orchestrator accounts, read-write or read-only, MFA (9.7)
- [Authentication (Orchestrator)](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/orchestrator/server/remote-auth/) - RADIUS, TACACS+, OAuth, JWT, SAML for Orchestrator logins (9.7)
- [Role Based Access Control](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/orchestrator/server/rbac/) - roles, appliance access groups, effect on the REST API (9.7)
- [Auth/Radius/TACACS+ Template](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/auth-radius-tacacs/) - appliance login order and servers (9.7)
- [Auth/RADIUS/TACACS+ Tab](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/administration/general/auth-radius-tacacs/) - per-appliance view and server fields (9.7)
- [User Management Template](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/user-mgmt/) - appliance local accounts and the enable password (9.7)
- [Appliance Users](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/administration/general/appliance-user-accts/) - accounts and live sessions per appliance (9.7)
- [Password Settings Template](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/password-settings/) - password policy for appliance users (9.6+)
- [Auth/Radius/TACACS best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/authradiustacacs) - where to configure it (all)
- [User Management best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/user-management) - admin password and accounts in the default template (all)
- [CLI Reference: AAA and User Authentication](https://arubanetworking.hpe.com/techdocs/sdwan-PDFs/cli-ref/CLI-Reference_latest.pdf) - aaa commands, password policy, lockout (all)
## Key facts
- Appliance local groups are admin (full, CLI configuration mode) and monitor (read and monitor, CLI enable mode). The built-in `admin` and `monitor` accounts cannot be deleted, only changed or disabled (9.7).
- Appliance RADIUS uses UDP, default port 1812, auth type pap or chap. Set server privilege levels so admin is 7 to 15 and monitor 1 to 6 (9.7).
- Appliance TACACS+ uses TCP, default port 49, auth type pap or ascii; server roles must be named admin and monitor (9.7).
- Recommended starting values (not required): use RADIUS or TACACS+ but not both; authentication order remote first, then local, then none; map order Remote-First; default role admin (9.7).
- With remote first and a CLI enable password set, the remote server needs a user `enableuser` with the same password (9.7).
- Orchestrator RADIUS attribute is `cisco-av-pair` with `LOGIN:priv-lvl=N` (7 and above admin, 6 and below monitor); TACACS+ uses `role=admin|monitor|manager`. RBAC roles come from `rbac-roles` and appliance access groups from `rbac-aag` (9.7).
- Orchestrator users are Read-Write or Read-Only; username up to 512 characters and cannot be renamed (delete and recreate). MFA by authenticator app or email is required on cloud Orchestrator (9.7).
- RBAC applies to the REST API as well as the UI since Orchestrator 9.3.0; an API key carries the role of its key (9.3).
- Password Settings template: minimum length 8 to 64 (default 8), expiry 30 to 360 days (default 90), history 4 to 8 (default 8), inactive-user deletion 30 to 360 days with 0 meaning off. Needs appliances on 9.6.0+ and the Orchestrator advanced property `enforcePasswordCriteria` true; enforcement cannot be disabled on an appliance once applied (9.6+).
- Lockout is set on the appliance with `aaa auth-failure deny` and `aaa auth-failure unlock-time` (all).
## MCP operations
- Find with `find_operations` terms "users", "gmsRemoteAuth", "rbac", "authRadiusTacacs".
- Orchestrator users: `GET /users` (optional `userId`), `GET /session/activeSessions`, `GET /gms/sessionTimeout`.
- Orchestrator remote auth: `GET /gmsRemoteAuth` (all types), `GET /gmsRemoteAuth/RADIUS`, `GET /gmsRemoteAuth/TACACS+`. The RADIUS and TACACS+ reads return 404 when nothing is configured; that is not an error.
- RBAC reads: `GET /rbac/role`, `GET /rbac/assignment`, `GET /rbac/asset`.
- Appliance state (read): `GET /authRadiusTacacs` (needs nePk), `GET /userAccount` (users and live sessions, needs nePk), `GET /userAccount/passwordSettings` (needs nePk).
- Appliance accounts and login settings are pushed by template groups: the `users` template holds local accounts (read with `GET /template/templateGroups`; its passwords read back empty, so change accounts in the Orchestrator UI).
- Creating or deleting Orchestrator users, remote auth servers, RBAC roles, assignments and assets, changing the session timeout and changing an appliance password are not available through the MCP server; do them in the Orchestrator UI (appliance logins go through the Auth/RADIUS/TACACS+ and User Management templates).
## Gotchas
- `/gmsRemoteAuth/*` configures Orchestrator logins; `GET /authRadiusTacacs` and the templates are about appliance logins. Do not mix them up.
- A wrong remote-auth order can lock out admins; keep a local account in the order until remote login is proven.
## Related
- [security-zones-firewall](security-zones-firewall.md)
- [snmp-syslog-logging](snmp-syslog-logging.md)
