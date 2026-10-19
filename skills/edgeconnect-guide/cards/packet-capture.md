# Packet capture and tcpdump
## What it is
Capturing packets on appliances for deep troubleshooting: the Orchestrator Packet Capture page (runs tcpdump on selected appliances and interfaces and stores pcap files), plus the quick tcpdump command from an appliance CLI session. Written for an agent that will find the MCP tool for this on the server's high-risk blocklist.
## Docs
- [Packet Capture](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/support/tech-assistance/pcap/) - page fields, circular storage, run and stop (9.7)
- [Tech Support - Appliances](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/support/tech-assistance/sup-appliances/) - where captured files are listed and downloaded (9.7)
- [Basic Diagnostics](https://arubanetworking.hpe.com/techdocs/sdwan/docs/troubleshooting/diagnostics/) - what to try before capturing (9.7)
- [Packet Captures best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/packet-captures) - sizing, filters, download steps, reading the files (all)
- [TCPDump best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/tcp-dump) - quick checks from an Orchestrator CLI session (all)
- [CLI Reference: Diagnostics](https://arubanetworking.hpe.com/techdocs/sdwan-PDFs/cli-ref/CLI-Reference_latest.pdf) - `tcpdump` and related commands on the appliance (all)
## Key facts
- Orchestrator path: Support > Technical Assistance > Packet Capture, with the appliances chosen in the tree. The product page frames it as something to run when Support asks (9.7).
- Several appliances can be captured at once, and several interfaces on one appliance; selecting no interface captures on all of them (all).
- Fields: packet limit, IP filter, port filter, snap length (96 for headers only, 1500 for full frames), extra BPF-style filter such as `proto 17 src 1.1.1.1`, and circular storage with number of files and size per file (9.7).
- Recommended starting values (not required): two files; size per file 25 MB on ultra small, 50 on 10104 and 10106 and XS, 75 on 10108 and small, 100 on medium, large and XL; snap length 100 unless payload is needed (all).
- Leave circular storage off if a long capture is not needed: with it on the files are named `.pcap0`, `.pcap1` and so on instead of `.pcap` (all).
- Only one capture can run at a time on the Orchestrator; starting a second one while one runs is an error (9.7).
- Tunnel (WAN-side) captures show only outer headers because traffic is encrypted; LAN-side captures see traffic before encryption. Capturing at the source and destination appliance together shows where loss or latency appears (all).
- Download from the Tech Support - Appliances page ("Download to Orchestrator" is preferred), then extract twice to reach the per-interface pcaps (all).
- Active and Recent Flows already shows the packet path and timings, so check it before capturing (all).
- tcpdump from an appliance CLI session is for quick checks; for heavy, hard-to-filter traffic use the Packet Capture page and pcap software (all).
## MCP operations
- Find with `find_operations` terms "tcpdump", "debugFiles".
- Watch a capture: `GET /tcpdump/status` (needs `nePk`), `GET /tcpdump/tcpdumpStatus`.
- Files: `GET /debugFiles` (needs `nePk`) lists debug dumps, tech dumps, snapshots and tcpdump files on an appliance.
- Starting a capture and deleting debug files are not available through the MCP server; start the capture from the Packet Capture page in the Orchestrator UI (or an appliance CLI session), then use the read operations above to follow it.
## Gotchas
- Captures fill appliance disk; always set a file size and count, and stop the capture when done.
- Large packet limits (millions) need circular storage or a size cap to avoid filling the disk.
- Encrypted payloads are rarely needed; capturing more bytes only makes files bigger. HTTPS needs about 256 bytes to see the URL header, DNS needs full frames to read names.
- Captures hold real traffic, including credentials in clear text protocols; handle the files as sensitive.
## Related
- [flows-stats](flows-stats.md)
- [cli-basics](cli-basics.md)
- [tunnels](tunnels.md)
- [alarms-monitoring](alarms-monitoring.md)
