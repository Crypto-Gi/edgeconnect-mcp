# Configure BGP neighbors

> **Reference only.** Every step below was run on Orchestrator 9.7.1 (ECOS 9.6.2.1 lab appliances and an ECOS 9.6.4.0 production appliance, test objects only) between 2026-10-16 and 2026-10-18. Your version and configuration can behave differently: read first, show the change, get a yes, and verify each step yourself.

Add, change or remove a BGP peer on one appliance. BGP has no Orchestrator write operation in 9.7.1, so the change goes through the appliance passthrough with the whole neighbor object. Background: [BGP](../cards/bgp.md).

## Before you start
- BGP must already be enabled on the appliance; enable it in the Orchestrator UI if not.
- Passthrough writes need `<nickname>_mcp_passthrough=true` as well as `<nickname>_mcp_writes=true` for the Orchestrator. If a write is refused, tell the user which flag is missing; they set it in `.env`.
- Collect: appliance `nePk`, peer IP, remote ASN, inbound and outbound route maps (a peer with none selected is deny-all in that direction), timers. Recommended starting values (not required): keepalive 5, hold 15, graceful restart yes (max 30, stale 60), AS-path propagate yes.
- Limit 64 peers per appliance. BGP and VRRP should not share a VLAN or virtual IP.
- Put shared defaults in a BGP template (template group) so new neighbors inherit them: see [template groups](../cards/templates-groups.md). The ASN pool only affects new appliances.
- Lab test: a peer at `192.0.2.250` with remote ASN `65999` on one lab appliance, removed afterwards.

## Steps
1. Call `api_get` on `GET /bgp/config/system` (check BGP is enabled) and `GET /bgp/config/neighbor` (both need `nePk`; `GET /bgp/config/allVrfs/neighbor` shows other segments) and `GET /bgp/state` (needs `nePk`).
   Also read the live object with `GET /appliance/rest`, `nePk` and `url` `bgp/config/neighbor`. On 9.7.1 both reads return the same object, keyed by peer IP (fields such as `self`, `remote_as`, `enable`, `hold`, `ka`, `rtmap_inbound`, `rtmap_outbound`, `lcl_interface`, `type`, `next_hop_self`, `bfd_desired`). Take the `GET /appliance/rest` one as the snapshot and the base of every edit. The POST replaces the whole object, so a partial object wipes the other peers.
   Template check: `api_get` `GET /template/applianceAssociation` with `nePk` returns the template groups the appliance belongs to; `GET /template/templateSelection` with each `templateGroup` lists the templates selected in it. If a BGP template is selected there, change the template instead (see [template groups](../cards/templates-groups.md)).
2. Call `describe_operation` on `POST /appliance/rest` (needs `nePk`, `url`; the body is the object the appliance expects).
3. Build the new object (no call yet; use the `api_get` `GET /appliance/rest` result from step 1): the whole object with your peer added (copy an existing peer's fields and change the IP, ASN and map names), edited in place, or removed. Strip nothing you do not understand; keep every other peer. Secrets such as passwords read as `<REDACTED:...>` tokens: leave those tokens unchanged so the server restores them. Only the server process that issued a token can restore it: after a server restart, read the object again first.
4. Show the user the exact `nePk`, `url` and full body, with a diff against the snapshot. After a yes, call `api_write` `POST /appliance/rest` with query `nePk` and `url` `bgp/config/neighbor` and that body.
5. Read back: `api_get` `GET /appliance/rest` (`nePk`, `url` `bgp/config/neighbor`; `GET /bgp/config/neighbor`, with or without `fromGms` false, returned the identical object) and compare the intent fields of your peer (IP, remote ASN, enable, maps, timers) and that every other peer is unchanged. Poll `GET /bgp/state` (`nePk`) until the peer shows Established, or note why not. An unreachable test peer shows `Connect`, `Active` or `Idle` in `neighbor.neighborState[].peer_state_str` (with no peer up at all, the `neighbor` key is missing and only `summary.num_bgp_peers_active` tells you); after a removal a row with peer_ip `::` can appear for a few seconds.
6. When a route map or policy changed, check the peer with `api_get` `GET /bgp/state`. A soft reset is a UI action ([BGP](../cards/bgp.md)) with no operation in this guide; tell the user when Soft Reconfiguration is off for the peer, and do not reset sessions on production appliances without asking.
7. Rollback: show the user the step 1 snapshot and after a yes `api_write` `POST /appliance/rest` with the same `nePk`, `url` `bgp/config/neighbor` and the snapshot as the whole body. Read it back as in step 5.

## Verify
- `GET /appliance/rest` (`nePk`, `url` `bgp/config/neighbor`) contains the peer with the intended ASN and maps, and every pre-existing peer is unchanged.
- `GET /bgp/state` shows the peer's state and received prefixes; routes appear in `GET /subnets` (needs `cached`, `nePk`).
- No new alarms: `POST /alarm/appliance` (body `nePks`). See [route maps](../cards/route-maps.md), [segmentation](../cards/segmentation.md) and [regional routing](../cards/regional-routing.md) if routes do not propagate as expected.
