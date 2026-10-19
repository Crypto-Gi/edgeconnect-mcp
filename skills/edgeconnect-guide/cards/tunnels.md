# Tunnels
## What it is
The tunnels between appliances (underlay, bonded overlay, passthrough to third parties), their per-label settings, exceptions that block specific tunnels, and Auto MTU discovery.
## Docs
- [Tunnels Tab](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/network/tunnels/) - overlay, underlay, passthrough subtabs, statuses (9.7)
- [Tunnels Template](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/tunnels/) - mode, MTU, fastfail, FEC, IPsec settings (9.7)
- [Tunnel Exception](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/network/tunnel-exception/) - stop two appliances forming a tunnel on given labels (9.7)
- [Schedule Auto MTU Discovery](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/network/schedule-auto-mtu/) - scheduled MTU discovery (9.7)
- [Tunnel Troubleshooting](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/network/tunnel-trouble/) - per-tunnel diagnostics dialog (9.7)
- [Tunnels (operational troubleshooting)](https://arubanetworking.hpe.com/techdocs/sdwan/docs/troubleshooting/tunnels/) - why tunnels stay down (9.7)
- [Tunnel Settings best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/tunnel-settings) - retry count, mode, encryption (all)
- [Brief tunnel troubleshooting](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/brief-tunnel-trouble-shooting) - checklist and NAT cases (all)
- [Tunnel Estimation Tool](https://developer.arubanetworks.com/edgeconnect/docs/tunnel-budget-tool) - plan tunnel counts (9.3)
- [CLI Reference: Tunnels and Overlays](https://arubanetworking.hpe.com/techdocs/sdwan-PDFs/cli-ref/CLI-Reference_latest.pdf) - tunnel commands (all)
## Key facts
- Overlay tunnels are bonds of underlay tunnels. An overlay between two appliances stays down until at least one of their underlay tunnels is up (all).
- Underlay tunnels are one-way (name reads "from, to_"). Manually created tunnels cannot be used by overlays (9.7).
- Overlays (BIO) govern tunnel properties in an SD-WAN fabric; the Tunnels template is only for setups without overlays and only changes existing tunnels unless "make defaults for new tunnels" is set (9.7).
- Statuses: up-active, up-idle (no packet for 5 minutes), down, down in progress, down misconfigured (same system ID on both ends), up reduced functionality (9.7).
- MTU up to 9000; Auto overrides the configured MTU (9.7).
- Fastfail: disabled gives about 30 s failover; enabled about 1 s; continuous about 0.1 s (9.7).
- Recommended starting values (not required): IPsec over UDP mode, retry count 5 for cable, DIA, MPLS, LEO and business fiber, 30 for LTE and unreliable links, AES-GCM-256, anti-replay window 8192 (all).
- The estimation tool helps size tunnel counts before a large mesh or many labels (9.3).
## MCP operations
- Find with `find_operations` terms "tunnels", "exception tunnel".
- Read: `GET /tunnels2/physical`, `GET /tunnels2/bonded`, `GET /tunnels2/passThrough` (filter by `nePk`, `state`, `operStatus`), `POST /tunnels2/getTunnelsBetweenAppliances`, `POST /tunnels2/tunnelCounts`, `GET /tunnelsConfiguration/deployment`.
- Live state: `POST /tunnels/physical/state` and `POST /tunnels/bonded/state`.
- Exceptions: `GET /exception/tunnel`, `POST /exception/tunnel`, `POST /exception/tunnel/deleteByIds`.
- Tunnel settings and the Auto MTU schedule are set in the Tunnels template of a template group (`GET /template/templateGroups`, then save only that template with `POST /template/templateGroups`).
## Gotchas
- Manually created tunnels have ids starting `tunnelUi_` (`ptTunnelUi_` for pass-through) and an empty `destNePk` (10.0).
- `POST /tunnels2/getTunnelsBetweenAppliances` returns an empty `operStatus`; take the state from `GET /tunnels2/physical` or `POST /tunnels/physical/state`.
- A new WAN label has no tunnel settings until you configure it (retry count, encryption) (all).
- CG-NAT on both ends does not form tunnels reliably; hubs need a direct public IP, 1:1 NAT or port forwarding (all).
- A wrong NAT setting in the appliance deployment (behind NAT or not) makes NAT discovery fail and tunnels stay down (all).
- EdgeHA pairs need the same site name so Orchestrator gives each appliance its own IPsec UDP port, and the pair needs IPsec over UDP mode (9.7).
## Related
- [overlays-bio](overlays-bio.md)
- [interfaces-labels](interfaces-labels.md)
- [wan-circuits-shaper](wan-circuits-shaper.md)
- [deployment-profiles](deployment-profiles.md)
- [vrrp-ha](vrrp-ha.md)
