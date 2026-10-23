"""Known HPE Aruba EdgeConnect security advisories, for the lifecycle report.

There is no Orchestrator API for advisories, so this list is maintained by hand and is only as current as AS_OF.
Each entry names the product it applies to ("orchestrator" or "ecos") and, per release train, the first fixed build.
A version in a listed train below its fixed build is affected; a version in a train older than every listed train is
affected with no fix in that train (end of maintenance); newer trains are not listed because they are not affected.
Check the HPE security portal for anything newer: https://csaf.arubanetworking.hpe.com/
"""

AS_OF = "2026-10-23"

ADVISORIES = (
    {
        "id": "HPESBNW04992",
        "cves": ("CVE-2025-37181", "CVE-2025-37182", "CVE-2025-37183", "CVE-2025-37184", "CVE-2025-37185"),
        "product": "orchestrator",
        "title": "EdgeConnect SD-WAN Orchestrator: multiple vulnerabilities, including an unauthenticated MFA bypass (CVE-2025-37184)",
        "revised": "2026-06-25",
        "fixed_in": {"9.6": "9.6.1", "9.5": "9.5.6", "9.4": "9.4.8"},
        "url": "https://csaf.arubanetworking.hpe.com/2026/hpe_aruba_networking_-_hpesbnw04992.txt",
    },
)
