# Sources

The six places the cards link into. Every card link was checked against a page inventory kept by the maintainers (not shipped with the skill). Back to the [router](SKILL.md).

## 1. Techdocs user guide (Orchestrator)

- URL: [Using SD-WAN Orchestrator](https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/)
- Good for: how each Orchestrator screen and setting works, with the menu path (Configuration, Monitoring, Administration, Orchestrator). The main source for feature behaviour.
- Versions: written for the current release (the cards tag pages 9.7); older behaviour is in the versioned PDFs in section 2.
- How to read: HPE blocks scripts and cloud IPs with 403, so fetch pages with the Exa fetch tool. The site index `https://arubanetworking.hpe.com/techdocs/sdwan/assets/js/search-data.json` lists every page with a title and text; read it through Exa to find a page that no card links.

## 2. Techdocs other guides and PDFs

- URL: [User Guides](https://arubanetworking.hpe.com/techdocs/sdwan/user-guides/)
- Good for: version-specific Orchestrator user guide PDFs (9.1.1 to 9.7.0), supplemental guides (advanced segmentation, management services, zone-based firewall), Orchestrator-SP and Air-Gap guides, troubleshooting and white papers. The [Best Practices, Tech Tips, and Other Guides](https://arubanetworking.hpe.com/techdocs/sdwan/docs/best-practices/) page lists further tips.
- Versions: one PDF per release, so use it when a card says behaviour changed between versions.
- How to read: same as section 1; PDFs are large, so fetch with a character limit and search for the section.

## 3. Release notes

- URL: [Release Notes](https://arubanetworking.hpe.com/techdocs/sdwan/release-notes/)
- Good for: what changed, new features and known issues per Orchestrator and ECOS release (9.2 to 9.7). Use it to explain a behaviour difference or a failing call after an upgrade.
- Versions: Orchestrator and ECOS (appliance) notes are listed separately; match both against `GET /gms/versions` and `GET /appliancesSoftwareVersions`.
- How to read: Exa fetch; the notes are PDFs linked from the index.

## 4. CLI reference

- URL: [CLI Reference](https://arubanetworking.hpe.com/techdocs/sdwan/cli/)
- Good for: appliance CLI command syntax, useful when a setting has no API operation or for verifying state on the box.
- Versions: published per ECOS release.
- How to read: Exa fetch.

## 5. Developer portal: best practices

- URL: [Getting Started](https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/getting-started) (the guide's first page; sidebar lists the rest)
- Good for: field-tested setup advice by feature (overlays, segmentation, BGP, templates, flows). Its numbers are field advice rather than product limits, so quote them as recommended starting values.
- Versions: published as v0.0.0, written for recent releases (9.3 onward); no per-page version.
- How to read: add `.md` to the page URL and fetch it with curl, for example `curl -sSL <url>.md`.

## 6. Developer portal: API 9.3 guide

- URL: [Start Here](https://developer.arubanetworks.com/edgeconnect/docs/whats-new)
- Good for: authentication, websocket API, alarm identifiers and the 9.3 API change. The [Rest API Table for 9.3 Endpoints](https://developer.arubanetworks.com/edgeconnect/docs/rest-api-table-for-93) page maps each pre-9.3 endpoint to its 9.3 replacement, so use it when old scripts or examples fail.
- Versions: 9.3 and later; the lab spec (9.7.1) is authoritative for operations.
- How to read: add `.md` to the page URL.

## Operation names

Doc pages never replace the Orchestrator's own spec. Take the operation method and path from `find_operations` and `describe_operation`, and use the docs for meaning and order of steps.
