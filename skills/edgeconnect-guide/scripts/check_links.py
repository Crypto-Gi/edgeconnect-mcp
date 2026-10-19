#!/usr/bin/env python3
"""Format, link and operation checker for the edgeconnect-guide skill (standard library only).

Every check returns a list of problem strings, empty when clean.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urldefrag, urlparse

ALLOWED_HOSTS = ("arubanetworking.hpe.com", "developer.arubanetworks.com")
CARD_HEADINGS = ["What it is", "Docs", "Key facts", "MCP operations", "Gotchas", "Related"]
PLAYBOOK_HEADINGS = ["Before you start", "Steps", "Verify"]
TOOLS = ("find_operations", "describe_operation", "api_get", "api_write")
MAX_CARD_LINES, MAX_ROUTER_LINES = 120, 150

# One level of balanced parentheses is allowed inside the URL.
LINK_RE = re.compile(r"\[[^\]]*\]\(((?:[^()\s]|\([^()\s]*\))+)\)")
CODE_SPAN_RE = re.compile(r"`[^`\n]*`")
VERSION_TAG_RE = re.compile(r"\((all|\d+\.\d+\+?)\)\s*$")
OPERATION_RE = re.compile(r"`(GET|POST|PUT|PATCH|DELETE) (/[^`\s?]+)")
REFERENCE_NOTICE = "**Reference only.**"
HEDGE_RE = re.compile(r"\buntested\b", re.IGNORECASE)


def _links(text: str) -> list[str]:
    """Markdown link targets, ignoring anything inside code spans."""
    return LINK_RE.findall(CODE_SPAN_RE.sub("", text))


def _section(text: str, heading: str) -> str:
    match = re.search(r"^## %s\n(.*?)(?=^## |\Z)" % re.escape(heading), text, re.S | re.M)
    return match.group(1) if match else ""


def _headings_and_length_problems(path: Path, expected: list[str], max_lines: int) -> list[str]:
    text = path.read_text(encoding="utf-8")
    problems = []
    if len(text.splitlines()) > max_lines:
        problems.append("%s: longer than %d lines" % (path.name, max_lines))
    found = re.findall(r"^## (.+?)\s*$", text, re.M)
    missing = [h for h in expected if h not in found]
    problems += ["%s: missing heading '## %s'" % (path.name, h) for h in missing]
    if not missing and [h for h in found if h in expected] != expected:
        problems.append("%s: headings out of order, expected %s" % (path.name, ", ".join(expected)))
    return problems


def _link_format_problems(path: Path) -> list[str]:
    """Host allow-list for external links, existence for relative ones."""
    problems = []
    for url in _links(path.read_text(encoding="utf-8")):
        if url.startswith(("http://", "https://")):
            host = urlparse(url).hostname
            if host not in ALLOWED_HOSTS:
                problems.append("%s: link host %s is not allowed (%s)" % (path.name, host, url))
        elif not url.startswith("#") and not (path.parent / urldefrag(url)[0]).is_file():
            problems.append("%s: relative link %s does not exist" % (path.name, url))
    return problems


def card_problems(path: Path) -> list[str]:
    problems = _headings_and_length_problems(path, CARD_HEADINGS, MAX_CARD_LINES)
    # A bullet is its first line plus indented continuation lines; the tag must close the last one.
    for bullet in re.findall(r"(?m)^- .*(?:\n[ \t]+\S.*)*", _section(path.read_text(encoding="utf-8"), "Docs")):
        if not VERSION_TAG_RE.search(bullet.strip()):
            problems.append("%s: Docs bullet lacks a version tag like (all) or (9.6+): %s" % (path.name, bullet.splitlines()[0]))
    return problems + _link_format_problems(path)


def _steps(text: str) -> list[str]:
    # A step runs from its number to the next one, so a tool name on a wrapped line still counts.
    return re.split(r"(?m)^(?=\d+\. )", _section(text, "Steps"))[1:]


def playbook_problems(path: Path) -> list[str]:
    problems = _headings_and_length_problems(path, PLAYBOOK_HEADINGS, MAX_CARD_LINES)
    steps = _steps(path.read_text(encoding="utf-8"))
    if not steps:
        problems.append("%s: no numbered steps under '## Steps'" % path.name)
    numbers = [int(step.split(".", 1)[0]) for step in steps]
    if numbers != list(range(1, len(steps) + 1)):
        problems.append("%s: step numbering should run 1..%d, found %s" % (path.name, len(steps), numbers))
    for step in steps:
        label = step.splitlines()[0]
        if not any("`%s`" % tool in step for tool in TOOLS):
            problems.append("%s: step names no MCP tool: %s" % (path.name, label))
        if step.startswith("1. ") and "`api_write`" in step:
            problems.append("%s: step 1 must not use `api_write`" % path.name)
    if REFERENCE_NOTICE not in path.read_text(encoding="utf-8"):
        problems.append("%s: missing the %s notice" % (path.name, REFERENCE_NOTICE))
    return problems + _link_format_problems(path)


def _guide_files(skill_dir: Path) -> tuple[list[Path], list[Path]]:
    return sorted((skill_dir / "cards").glob("*.md")), sorted((skill_dir / "playbooks").glob("*.md"))


def _markdown_files(skill_dir: Path) -> list[Path]:
    top = [skill_dir / name for name in ("SKILL.md", "sources.md")]
    return [p for p in top if p.is_file()] + sum(_guide_files(skill_dir), [])


def router_problems(skill_dir: Path) -> list[str]:
    router = skill_dir / "SKILL.md"
    if not router.is_file():
        return ["SKILL.md is missing"]
    text = router.read_text(encoding="utf-8")
    problems = _link_format_problems(router)
    if (skill_dir / "sources.md").is_file():
        problems += _link_format_problems(skill_dir / "sources.md")
    if len(text.splitlines()) > MAX_ROUTER_LINES:
        problems.append("SKILL.md: longer than %d lines" % MAX_ROUTER_LINES)
    linked = {(skill_dir / urldefrag(u)[0]).resolve() for u in _links(text) if not u.startswith(("http://", "https://", "#"))}
    for path in sum(_guide_files(skill_dir), []):
        if path.resolve() not in linked:
            problems.append("SKILL.md: does not link %s/%s" % (path.parent.name, path.name))
    return problems


def link_problems(skill_dir: Path, known_urls: set[str]) -> list[str]:
    problems = []
    for path in _markdown_files(skill_dir):
        for url in _links(path.read_text(encoding="utf-8")):
            if url.startswith(("http://", "https://")) and urldefrag(url)[0] not in known_urls:
                problems.append("%s: link not in the inventory: %s" % (path.name, url))
    return problems


def operation_problems(skill_dir: Path, spec: dict) -> list[str]:
    # Whole file, not only the operations section: drift in Key facts or Verify counts too.
    problems = []
    for path in _markdown_files(skill_dir):
        for method, route in OPERATION_RE.findall(path.read_text(encoding="utf-8")):
            if method.lower() not in spec.get("paths", {}).get(route, {}):
                problems.append("%s: `%s %s` is not in the spec" % (path.name, method, route))
    return problems


def load_tested(path: Path) -> set[tuple[str, str]]:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line and not line.startswith("#")]
    return {(row["method"], row["path"]) for row in csv.DictReader(lines, delimiter="\t")}


def tested_problems(skill_dir: Path, tested: set[tuple[str, str]]) -> list[str]:
    # The skill may only name operations that passed in a real run, and never hedge with "untested".
    problems = []
    for path in _markdown_files(skill_dir):
        text = path.read_text(encoding="utf-8")
        for method, route in OPERATION_RE.findall(text):
            if (method, route) not in tested:
                problems.append("%s: `%s %s` is not in tested-operations.tsv" % (path.name, method, route))
        if HEDGE_RE.search(text):
            problems.append("%s: says 'untested'; drop the claim or test it" % path.name)
    return problems


def load_known_urls(tsv_paths: list[Path]) -> set[str]:
    urls = set()
    for tsv in tsv_paths:
        with open(tsv, encoding="utf-8", newline="") as handle:
            # QUOTE_NONE: titles and summaries carry stray quote characters.
            for row in csv.DictReader(handle, delimiter="\t", quoting=csv.QUOTE_NONE):
                if row["url"] and row.get("status", "ok") in ("ok", "search-only"):
                    urls.add(urldefrag(row["url"])[0])
    return urls


RETRY_STATUSES = (429, 503)


def _fetch_status(url: str, attempts: int = 4) -> int | str:
    """HTTP status of url, or an error string. Rate limits are retried, honouring Retry-After."""
    for attempt in range(attempts):
        retry_after = None
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "check_links"}), timeout=20) as resp:
                return resp.status
        except urllib.error.HTTPError as exc:
            status, retry_after = exc.code, exc.headers.get("Retry-After") if exc.headers else None
        except (urllib.error.URLError, OSError) as exc:
            return "request failed: %s" % exc
        if status not in RETRY_STATUSES:
            return status
        if attempt < attempts - 1:
            time.sleep(min(float(retry_after), 60.0) if retry_after and retry_after.isdigit() else 4.0 * 2 ** attempt)
    return status


def http_problems(skill_dir: Path, hosts: tuple[str, ...] = ("developer.arubanetworks.com",), delay: float = 1.0) -> list[str]:
    # HPE techdocs answer scripts with 403, so only hosts the caller names are fetched.
    urls = set()
    for path in _markdown_files(skill_dir):
        for url in _links(path.read_text(encoding="utf-8")):
            if urlparse(url).hostname in hosts:
                urls.add(urldefrag(url)[0])
    problems = []
    for index, url in enumerate(sorted(urls)):
        if index:
            time.sleep(delay)  # the portal rate-limits bursts
        status = _fetch_status(url)
        if status == 200:
            continue
        if isinstance(status, str):
            problems.append("%s: %s" % (url, status))
        elif status in RETRY_STATUSES:
            problems.append("%s: HTTP %d, rate limited, not checked" % (url, status))
        else:
            problems.append("%s: HTTP %d" % (url, status))
    return problems


def main(argv: list[str] | None = None) -> int:
    default_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-dir", type=Path, default=default_dir)
    parser.add_argument("--inventory", nargs="+", type=Path, help="TSV inventories to check links against")
    parser.add_argument("--spec", type=Path, help="OpenAPI/Swagger JSON to check operations against")
    parser.add_argument("--http", action="store_true", help="fetch developer-portal links")
    args = parser.parse_args(argv)

    skill_dir = args.skill_dir
    cards, playbooks = _guide_files(skill_dir)
    problems = router_problems(skill_dir)
    for path in cards:
        problems += card_problems(path)
    for path in playbooks:
        problems += playbook_problems(path)
    tested_file = skill_dir / "tested-operations.tsv"
    if tested_file.is_file():
        problems += tested_problems(skill_dir, load_tested(tested_file))
    if args.inventory:
        problems += link_problems(skill_dir, load_known_urls(args.inventory))
    if args.spec:
        problems += operation_problems(skill_dir, json.loads(args.spec.read_text(encoding="utf-8")))
    if args.http:
        problems += http_problems(skill_dir)
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
