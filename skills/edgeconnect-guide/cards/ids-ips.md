# IDS/IPS and signature profiles
## What it is
Intrusion detection and prevention on EdgeConnect: copies of traffic matched by a firewall rule with the Inspect action are checked against signatures that Orchestrator downloads from the Cloud Portal. Signature profiles choose what happens per rule (drop, inspect, allow), and a mode per appliance (IDS only, IPS-Performant, IPS-Inline, off) decides whether threats are only reported or also blocked.
## Docs
- [Intrusion Detection/Prevention System](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/overlays/ids/) - modes, prerequisites, applying IDS/IPS, auto updates, signature history (9.7)
- [Signature Profiles](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/overlays/ids-ips-profiles/) - default profiles, rule actions, creating profiles (9.7)
- [Appliance Security Policies](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/overlays/appliance-security-policies/) - the Inspect action that sends traffic to IDS/IPS (9.7)
- [Security Log Viewer](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/monitoring/security/security-log-viewer/) - threat events on Orchestrator (9.7)
- [Security Features Guide](https://arubanetworking.hpe.com/techdocs/sdwan-PDFs/docs/tips/Security-Guide-9.5-Release-latest.pdf) - IDS/IPS operation, license and resource needs, signature categories (9.5)
- [Orchestrator and EdgeConnect Logging](https://arubanetworking.hpe.com/techdocs/sdwan/docs/white-paper/) - IDS/IPS syslog format and JSON export (9.5)
## Key facts
- Traffic is only inspected when a firewall rule has the Inspect action; the mode on the appliance then decides IDS (detect) or IPS (detect and act) (9.7).
- Modes: IDS Only, IPS-Performant, IPS-Inline, Off. IPS-Inline needs ECOS 9.4.1 or later and older appliances ignore it (9.7).
- Prerequisites: IDS on ECOS 9.1 or later, IPS on ECOS 9.2 or later; EC-V needs at least 4 cores and 16 GB RAM; EC-XS (part numbers 200889, 200900) and EC-US are excluded; the appliance needs the Advanced Security license (9.7).
- Default profiles are `Default` (signature family 4.x) and `Default_S5` (family 5.x). They cannot be edited; create a custom profile to change rule actions (9.7).
- Out of the box every rule is enabled and the action is drop. Actions per rule: Drop, Inspect (detect and continue), Allow (rule excluded from IDS/IPS) (9.7).
- Custom profiles on family 5.x get an `_S5` suffix on the name, and 5.x profiles need IPS engine 6.x or later (9.7).
- Auto updates can be switched off so signature changes are reviewed first in the Signature History tab (9.7).
- IDS/IPS alarms are logged as syslog; give IDS/IPS its own logging facility and a remote receiver to ship them (9.7).
## MCP operations
- Find with `find_operations` terms "ids", "idps", "signature".
- Read: `GET /ids/state` (mode lists per appliance), `GET /ids/profilestate` (profile to appliances), `GET /ids/signatures/profiles` (optional `signature_family`), `GET /ids/config`, `GET /ids/autoSignatureUpdateState`, `GET /ids/signatures`, `GET /ids/signatures/rules`, `GET /ids/signatures/diff`.
- Changing the IDS/IPS mode of an appliance and downloading signatures now are not covered by this guide; do them in the Orchestrator UI.
- Assign profiles: `PUT /ids/profilestate` (body maps profile name to appliance list; an appliance can be in one profile).
- Profiles: `POST /ids/signatures/profiles` replaces the whole list (body array of `name`, `signature_family`, `config` with `allow`, `drop`, `inspect` rule ID lists); omitting a profile deletes it, so include the defaults. It returns true.
- Signatures: `PUT /ids/autoSignatureUpdateState` (body `auto`), `PUT /ids/config` (body is only `{"schedule": <configData.schedule as read>}`; the whole GET shape returns 400).
## Gotchas
- `POST /ids/signatures/profiles` deletes every profile you leave out of the body: read the list first and send it all back with your change.
- Read `GET /ids/signatures/profiles` before and after to confirm the Default profiles are still there.
- Nothing is inspected until a firewall rule uses the Inspect action, even with a mode and profile applied.
## Related
- [security-zones-firewall](security-zones-firewall.md)
- [firewall-protection-profile](firewall-protection-profile.md)
- [snmp-syslog-logging](snmp-syslog-logging.md)
