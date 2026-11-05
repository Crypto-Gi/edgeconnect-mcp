# Monthly docs refresh for the edgeconnect-guide skill

How to check that the skill's HPE doc links still work and to find new HPE pages. A scheduled Claude session follows these steps once a month; a person can follow them too.

`baseline.tsv` lists every known HPE page (url, title, status) as of the last run. Status is `ok` or `uncertain` (could not confirm either way).

## Rules

- Change only links: the `## Docs` lists in `skills/edgeconnect-guide/cards/`, `skills/edgeconnect-guide/sources.md` and `baseline.tsv`. Never add or change key facts, operations, gotchas, cards or playbooks: those need a lab test first.
- Link a new page only into a card whose topic it clearly covers, with a one-line description in your own words. Never copy HPE text.
- Remove a link only when the page is gone by two signs: the fetch fails, and its section contents page no longer lists it. Otherwise mark it `uncertain` and say so in the PR.
- Every result goes in one pull request for a person to review. Never merge it yourself.

## Steps

1. Developer portal (curl works): `python3 skills/edgeconnect-guide/scripts/check_links.py --http` lists dead links. Also fetch `https://developer.arubanetworks.com/edgeconnect/docs/intro` and `https://developer.arubanetworks.com/edgeconnect/v0.0.0/docs/getting-started`, collect the sidebar links (`/edgeconnect/docs/...`, `/edgeconnect/v0.0.0/docs/...`) and compare them with `baseline.tsv`.
2. Techdocs (`arubanetworking.hpe.com/techdocs/`): it returns 403 to curl and headless browsers, so use the Exa fetch tool. Send every techdocs URL in `baseline.tsv` in batches of about 40 with `maxCharacters` 20. A live page returns its title; a missing one returns `CRAWL_NOT_FOUND`. Retry failures once in a smaller batch.
3. For each failed URL, open its parent section page (the URL one level up) with a larger `maxCharacters` and read its table of contents. If the title is listed under a new name, guess the new URL from the contents, fetch it, and record a move only when the fetch works. If the title is no longer listed, record it as gone.
4. New pages: fetch every section page (each baseline URL that has child pages, plus `docs/orch/`, `docs/orch-install-upgrade/`, `docs/sysreq/`, `docs/troubleshooting/`, `docs/unified-fabric/`, `docs/best-practices/`, `docs/white-paper/`, `docs/fips/`) and compare the titles in its contents with baseline titles. Find the URL of each unknown title with an Exa search limited to `arubanetworking.hpe.com/techdocs/sdwan`, and confirm it with a fetch. Ignore `www.arubanetworks.com` copies: they are stale. `assets/js/search-data.json` is cut off by Exa at about 1M characters, so it can help but never covers the whole site.
5. Edit links in cards and `sources.md` per the rules. Update `baseline.tsv`: add new and moved pages, drop gone ones, keep `uncertain` rows for the next run.
6. Check: `python3 -m unittest tests.test_guide_skill` and `python3 skills/edgeconnect-guide/scripts/check_links.py --inventory docs/docs-refresh/baseline.tsv --http`. Both must pass.
7. Open a pull request titled `Docs refresh YYYY-MM`. In its body, list counts (live, moved, gone, uncertain, new), every link changed and why, new pages not linked (with a suggested card each), and any caveat. If nothing changed, open no PR and say so in the session.

## Caveat

Exa serves cached copies, so a page it returns may be older than the live site, and a page it has never crawled looks missing. Treat a single failed fetch as a question, not as proof.
