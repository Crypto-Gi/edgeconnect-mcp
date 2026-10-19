# Template groups and applying templates
## What it is
Templates hold shared, feature-level settings (users, DNS, SNMP, security policies, QoS, routes defaults and more). Template groups bundle selected templates, appliances are associated with one or more groups, and Orchestrator keeps those settings enforced on every orchestration cycle.
## Docs
- [Configuration > Templates](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/) - index of every template page (9.7)
- [Apply Template Groups](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/apply-template-groups/) - assign groups, reorder, Remove versus Merge (9.7)
- [CLI Template](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/cli/) - raw CLI lines pushed as one batch (9.7)
- [Day 0 Preconfiguration and Templates](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/day-0-preconfiguration-and-templates) - which features are template-only, preconfiguration-only or both (9.6)
- [Adding templates to groups](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/adding-templates-to-groups) - drag a template into a group, Save as to clone (all)
- [Initial Templates and settings](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/initial-templates-and-settings) - suggested default group and overlap behaviour (all)
- [CLI VIA Template](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/cli-via-template) - using the CLI template for CLI-only features (all)
## Key facts
- A group does not need every template; typical split is a Default Template Group for global items plus small groups (for example one for Security Policies, one for Branch QoS) (9.6).
- An appliance can carry several groups; when two groups configure the same template, the group applied later wins. On the Apply Template Groups page that means lower in the list overwrites higher (9.7).
- Only overlapping templates are replaced, so groups stack; the replaced section is removed and then rewritten, which can interrupt traffic (all).
- Changing a group is Remove or Merge. Remove stops the group affecting the appliance but leaves current settings until another template overrides them; Merge overwrites overlapping settings and keeps the rest. Remove is the recommended one for uniform results (9.7).
- Saving a template pushes it to every associated appliance, and the dialog shows how many; a template does nothing until its group is applied to appliances (all).
- Save as clones a whole group, which is a safe way to try a change on lab appliances before production (all).
- Recommended starting value (not required): template everything, keep global items (time, peer priority, non-segmented ZBFW) in the default group and limit subset groups (all).
- The CLI template is sent to the appliance as one REST call with a 60 second timeout; keep the command set to about 30 seconds when typed by hand (9.7).
- Preconfiguration sets the initial state; afterwards the template group priority decides conflicts. Templates also have a "Don't apply" state that leaves the appliance value alone, which preconfiguration does not (9.6).
- `sslSubstituteCerts` (SSL for SaaS) is deprecated and removed in 9.7 (9.6).
## MCP operations
- Find with `find_operations` terms "template", "templateGroups", "applianceAssociation".
- Read: `GET /template/templateGroups` (optional `templateGroup`, `namesOnly`), `GET /template/templateSelection` (needs `templateGroup`) lists enabled templates, `GET /template/templateGroupsPriorities`, `GET /template/applianceAssociation` (optional `nePk`).
- Save a group: `POST /template/templateGroups` (needs `templateGroup`; body `name`, `comment`, `templates`). When body `name` equals `templateGroup` it updates; otherwise it clones: `templateGroup` = new name, body `name` = source, `templates` `[]`. A clone copies the templates, not the selection. There is no separate apply call; saving pushes to every associated appliance.
- Create from defaults: `POST /template/templateCreate` (body `name`, `comment`, `templates`) gives all 46 default templates and an empty selection. Delete: `POST /template/deleteTemplateGroup` (body `templateGroup`, `comment`); the Default Template Group cannot be deleted.
- Enable or disable templates in a group: `POST /template/templateSelection` (needs `templateGroup`; body is a plain list of selected template names).
- Order: `POST /template/templateGroupsPriorities` (body `priorities`, the ordered list). The last group in the list wins.
- Associate: `POST /template/applianceAssociation` (needs `nePk`; body `templateIds` replaces the appliance's whole list) and `POST /template/applianceAssociation2` for many appliances in one call.
- Confirm delivery: `GET /template/history` (needs `nePk`, `latestOnly=true`; false returns null) shows when each template was last applied successfully; `GET /template/history/groupList` (needs `nePk`) lists groups applied.
- Group, selection, priority and association writes are all allowed on writable Orchestrators.
## Gotchas
- When two groups configure the same template, the last group in `templateGroupsPriorities` wins, although the `describe_operation` text (9.7.1 and 10.0 specs) says groups listed first have higher priority; on the lab the change was applied within about a minute of association. The group name in `GET /template/history` can be wrong, so do not trust it.
- To change one template, post only that template (`templates`: `[{"name", "valObject"}]`); templates you omit are kept. Content reads in `value` with `valObject` null, so copy `value` into `valObject`. Never post the whole group back: secrets (NAC key, user passwords) read empty and the save fails with HTTP 500 (9.7.1).
- `qosMaps` can only be selected with a valid QoS Policies license.
- User passwords in the `users` template read back empty; leave that template alone and change accounts in the Orchestrator UI.
- On the lab, template changes were applied within about a minute of association; if orchestration is paused (maintenance mode, Orchestration Settings) nothing is pushed.
## Related
- [appliance-onboarding](appliance-onboarding.md)
- [orchestrator-settings-backup](orchestrator-settings-backup.md)
- [cli-basics](cli-basics.md)
- [aaa-users](aaa-users.md)
- [security-zones-firewall](security-zones-firewall.md)
- [bgp](bgp.md)
