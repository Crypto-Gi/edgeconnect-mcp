# Deployment best practices
## What it is
Field advice from the EdgeConnect deployment engineers' "EC SD-WAN Day 0+" guide on the developer portal, for a first deployment or a design review: what to prepare, how to design the site, and the settings that cause outages when changed. The guide says to work through it top down; the order is in [first deployment](../playbooks/first-deployment.md). Feature details are in the other cards.
## Docs
- [EC SD-WAN Day 0+](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/launchpad) - the guide's start page; follow it top down (all)
- [Getting Started](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/getting-started) - Orchestrator as a service or self-hosted, first login, keep it simple (all)
- [Design Notes](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/design-notes) - EC as layer 3 gateway or routing link, DNS and traffic through the EC (all)
- [Implementation Checklist](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/implementation-checklist) - firewall, network, server and cloud team tasks before day 0 (all)
- [Initial Templates and settings](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/initial-templates-and-settings) - template everything, default group first (all)
- [Management Services](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/management-services) - which services to leave on "any" (all)
- [Management Services Template](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/mgmt-svcs/) - the template fields (9.7)
- [Local Appliance Setup](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/local-device-setup) - sites with no DHCP circuit, mgmt0 and mgmt1 use (all)
- [Adding appliance to Orch](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/adding-appliance-to-orch) - approval wizard choices (all)
- [Preparing for tunnels](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/preparing-for-tunnels) - points to the link bonding deep dive (all)
- [Established Tunnels](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/establishing-tunnels) - underlay first, tunnel states (all)
- [Application Tips and tricks](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/application-tips-and-tricks) - custom applications (all)
- [Application Definitions](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/policy/app-defs/) - where custom applications are made (9.7)
- [Orch Tips and Tricks](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/orch-tips-and-tricks) - troubleshooting tabs and table columns (all)
- [Integration Points for EdgeConnect Orchestrator and Gateways](https://developer.arubanetworks.com/edgeconnect/docs/best-practices) - which interface to use for alarms, logs, flows, preconfiguration and stats (9.3+)
- [Resources and Links](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/resources-and-links) - training, release notes, validated designs, security bulletins, cloud status (all)
- [Deployment Guides (PDF)](https://arubanetworking.hpe.com/techdocs/sdwan/docs/deployments/deploy-pdf/) - installing a self-hosted Orchestrator or an EC-V (all)
- [Best Practices, Tech Tips, and Other Guides](https://arubanetworking.hpe.com/techdocs/sdwan/docs/best-practices/) - HPE's list, including scan guidance (all)
## Key facts
- Keep the first build simple: turn on only the features the requirements name, and add more later (all).
- Orchestrator as a service is the recommended choice. Self-hosted means you patch the OS, back up the database, keep the OS admin and root credentials, and protect it with ACLs or firewall rules (all).
- After first login, generate a new Cloud Portal account key; the one sent by email is the original (all).
- Make every change in Orchestrator, and every appliance-level change through a template unless it lives on the deployment page; avoid the appliance UI and CLI (all).
- In the appliance tree, nothing selected means everything selected (all).
- Put the EC in the path of all traffic, and let client DNS requests and replies pass through it: the application engine snoops DNS to identify traffic on the first packet (all).
- EC as the LAN layer 3 gateway gives the full security feature set: up to 64 LAN sub-interfaces, each with its own zone and segment, VRRP for redundancy, inter-VLAN traffic visible in flows and covered by the firewall, DHCP server or relay, IDS/IPS with the advanced license. As a routing link (BGP, OSPF, static) it gets one zone and one segment per routing interface and does not see inter-VLAN traffic (all).
- If a firewall shares the same internet circuit, lower the EC deployment bandwidth by the firewall's share (for example 800 of a 1000 Mbps circuit), or the EC overdrives the link and drops packets (all).
- Do not put the EC WAN behind a layer 7 firewall; an L3/L4 edge firewall is acceptable if it handles full WAN throughput. Behind a firewall allow UDP 12000 and 12010 (ten more per extra appliance at the site), give hubs 1:1 static NAT and inbound rules, prefer 1:1 NAT at spokes, and set the UDP session timeout for tunnel traffic to about 1 hour (all).
- Outbound rules every site's firewall needs (bypass SSL inspection for all): `*.silverpeak.cloud` TCP 443 (Orchestrator, portal, stats collectors), ICMP to `sp-ipsla.silverpeak.cloud` and `sp-ipsla2.silverpeak.cloud`, `*.brightcloud.com` for IDS/IPS, and `*.com.s3.amazonaws.com` for case file uploads (all).
- Mesh sites need static public IPs; hub-and-spoke spokes do not. Order diverse ISPs everywhere, and give every spoke at least one DHCP circuit (an LTE backup counts) so it can call home (all).
- A cloud Orchestrator sends alarms and audit logs and reaches TACACS or RADIUS over the internet, so a private collector or server (such as a 10.x syslog) needs a path the Orchestrator can reach; appliance syslog goes from the appliance itself (all).
- Plan before day 0: IP space for MPLS and data center, a BGP ASN pool and a loopback range, syslog and SNMP collectors, TACACS or RADIUS, SSO for Orchestrator users (all).
- Security scanners create one flow per port per host (about 130,000 for a full scan); EC 10108 and smaller hold 256,000 flows, medium and larger 2 million. Protect with a firewall protection profile and stagger scans across sites (all).
- Use mgmt0 only to onboard (behind a firewall, never on a bare internet link), then unplug or shut it. Tunnels never build on mgmt0 or mgmt1, mgmt1 is direct access only (169.254.0.1), and mgmt traffic is not in the flows table (all).
- Management services: set them in a template, and leave HTTP(S), Cloud Portal, Orchestrator, SSH and DHCP on "any" with the default segment (all).
- Make granular custom applications (address, protocol and port) such as an "ORG-DNS" for internal DNS: they make flows readable and shorten firewall rules. A flow that matches two applications gets one at random (all).
- Underlay tunnels must be up before overlay tunnels; one up underlay between two ECs is enough. Active passed traffic in the last 5 minutes, Idle is ready but quiet, Down needs troubleshooting (all).
- Integration: alarms and audit logs from the Orchestrator notification service (syslog, HTTPS, websocket or Kafka), flows from the appliance (IPFIX or NetFlow), firewall denies from appliance syslog, day 0 config as YAML preconfiguration, topology and stats by REST polling (9.3+).
## MCP operations
- Find with `find_operations` terms "mgmtServices", "tunnels2", "preconfiguration".
- Management services: `GET /mgmtServices` (`nePk`) to read; change them only through the Management Services template in the UI.
- Underlay and overlay tunnels: `GET /tunnels2/physical` and `GET /tunnels2/bonded` (`nePk`).
- Custom applications and the Cloud Portal account key: no MCP route in this guide; use Configuration > Templates & Policies > Applications & SaaS > Application Definitions, and Orchestrator > Orchestrator Server > Licensing > Cloud Portal.
## Gotchas
- Moving HTTP(S), Cloud Portal or Orchestrator off "any" can isolate the appliance until someone is on site (all).
- SSH set to anything but "any" breaks the Orchestrator CLI session feature (all).
- DHCP off "any" (or mgmt0 connected) sources relay traffic from one interface, so hosts can get no or wrong addresses unless the DHCP server handles option 82 and that source (all).
- A new custom application can steal traffic from an application a firewall rule allows (a "WEB-Servers" app on 443 no longer matches "https") and block it (all).
- Two WAN interfaces with the same label, HA pairs included, raise an alarm and build no tunnels; use INET-HA and INET-HB style labels (all).
- To stop spoke-to-spoke hairpin through a hub, untick WAN to WAN routing in the hub's system settings and make sure a route (usually 0.0.0.0/0) covers all traffic (all).
## Related
- [appliance-onboarding](appliance-onboarding.md)
- [templates-groups](templates-groups.md)
- [wan-circuits-shaper](wan-circuits-shaper.md)
- [deployment-profiles](deployment-profiles.md)
- [interfaces-labels](interfaces-labels.md)
- [firewall-protection-profile](firewall-protection-profile.md)
- [tunnels](tunnels.md)
