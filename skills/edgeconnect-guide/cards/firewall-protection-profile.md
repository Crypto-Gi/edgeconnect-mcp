# Firewall protection profiles and DDoS
## What it is
Firewall protection profiles (FPP) add DoS and spoofing defence per segment and zone: threshold rules for flow rate, concurrent flows and half-open TCP, plus allowlist, blocklist and baseline-learning thresholds (Auto rate limit, Smart burst).
## Docs
- [Firewall Protection Profiles](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/overlays/fw-protection-profiles/) - baseline learning, Auto rate limit, Smart burst, per-appliance setup (9.7)
- [Firewall Protection Profiles Template](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/templates/fppt/) - profile fields, DoS thresholds, profile mappings (9.7)
- [Protection Profile Top Talkers](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/monitoring/security/fpp-top-talkers/) - who triggers thresholds (9.7)
- [Protection Profile Trends](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/monitoring/security/protection-profile-trends/) - threshold hits over time (9.7)
- [Firewall protection profile best practice](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/firewall-protection-profile) - starter profiles (all)
- [Security Features Guide](https://arubanetworking.hpe.com/techdocs/sdwan-PDFs/docs/tips/Security-Guide-9.5-Release-latest.pdf) - DoS, IP header and TCP protections, FPP limits (9.5)
## Key facts
- A profile is mapped to a segment and zone pair; one profile can serve several mappings (9.7).
- Security settings in a profile are check boxes; strict three-way TCP enforcement and deep packet inspection validation do not work with asymmetric routing (9.7).
- DoS thresholds: presets Lenient, Moderate, Strict, Auto rate limit, Smart burst, or custom. A custom threshold sets a classification (zone level or source level), a metric (flows per second, concurrent flows, embryonic flows), an IP protocol and a min and max value as a percentage of appliance flow capacity (9.7).
- Actions on a breach are Log, Rapid aging, Drop excess or Block source; the max action is normally the harsher one (9.7).
- Allowlist skips DoS analysis for an address group but not the security-setting checks; blocklist blocks an address group outright (9.7).
- Advanced settings: rapid aging seconds, block duration seconds, embryonic timeout seconds, share committed burst (on by default) (9.7).
- Baseline learning: model training default 14 days (7 to 56), recompute every 8 hours by default, data aggregation default 95 percent (75 to 100). Auto rate limit and Smart burst appear only after baseline learning is on, and all three need an Advanced Security or Dynamic Threat Defense license (9.7).
- Baseline learning cannot be turned off while a profile still uses Auto rate limit or Smart burst (9.7).
- Recommended starting value (not required): one WAN profile and one internal profile, applied per segment and zone (all).
## MCP operations
- Find with `find_operations` terms "protection", "ddos", "addos".
- Read profiles and zone mappings on an appliance: `GET /security/ddos/protectionProfiles/appliance` (needs nePk; optional `cached`).
- Stats: `POST /stats/timeseries/ddosTotalStats` and `POST /stats/timeseries/ddosPeakAndPeakDropRate` (need startTime, endTime, granularity, zoneId, metric, protocol, statIds, classification; body `nePk`), `POST /stats/timeseries/ddosTopTalkers` (needs startTime, endTime, granularity, statIds; body `nePk`).
- Baseline stats: `POST /stats/timeseries/addos/maxTimestamp` (body `nePk`) gives the latest baseline time; `POST /stats/timeseries/addos/trends/baselineZone` (needs startTime, endTime, zoneId, protocol, metric, classification; body `nePk`).
- No dedicated Orchestrator write for profiles in the 9.7.1 spec; edit them in the Orchestrator UI.
## Gotchas
- Profile mappings refer to zone names and segments, so create the zones first (see security-zones-firewall).
- Auto rate limit and Smart burst depend on baseline data and the training interval is at least 7 days, so start with a preset threshold in the meantime.
- Block source and Drop excess act on live traffic: tune with Log first on a few appliances.
- If every stats call returns 500, the Orchestrator's stats database is the problem.
## Related
- [security-zones-firewall](security-zones-firewall.md)
- [ids-ips](ids-ips.md)
- [segmentation](segmentation.md)
- [snmp-syslog-logging](snmp-syslog-logging.md)
