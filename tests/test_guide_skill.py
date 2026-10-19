import contextlib
import importlib.util
import io
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "edgeconnect-guide"
_spec = importlib.util.spec_from_file_location("check_links", SKILL_DIR / "scripts" / "check_links.py")
check_links = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_links)

BGP_URL = "https://arubanetworking.hpe.com/techdocs/sdwan/docs/orch/configuration/network/bgp/"
GOOD_CARD = """# BGP
## What it is
Peering with routers.
## Docs
- [BGP Tab](%s) (9.7)
## Key facts
- Keepalive 5, hold 15 as a starting point.
## MCP operations
- `GET /bgp/config/neighbor` reads neighbors.
## Gotchas
- None.
## Related
- [segmentation](segmentation.md)
""" % BGP_URL
GOOD_PLAYBOOK = """# Add a peer
> **Reference only.** Tested on a lab.
## Before you start
- Know the neighbor IP.
## Steps
1. Call `find_operations` for BGP.
2. Call `api_write` with `POST /appliance/rest?nePk=1.NE&url=vrrp`.
## Verify
- Call `api_get` on the neighbor.
"""
SPEC = {"paths": {"/bgp/config/neighbor": {"get": {}}, "/appliance/rest": {"post": {}}}}


class GuideSkillTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        (self.dir / "cards").mkdir()
        (self.dir / "playbooks").mkdir()
        self.card = self.write("cards/bgp.md", GOOD_CARD)
        (self.dir / "cards" / "segmentation.md").write_text(GOOD_CARD)

    def write(self, rel, text):
        path = self.dir / rel
        path.write_text(text)
        return path

    def test_good_card_passes(self):
        self.assertEqual(check_links.card_problems(self.card), [])

    def test_card_missing_heading(self):
        path = self.write("cards/bgp.md", GOOD_CARD.replace("## Gotchas\n- None.\n", ""))
        problems = check_links.card_problems(path)
        self.assertEqual(len(problems), 1)
        self.assertIn("Gotchas", problems[0])

    def test_card_headings_out_of_order(self):
        # Swap two sections without Docs bullets, so only the ordering check can object.
        swapped = GOOD_CARD.replace("## Key facts", "## TMP").replace("## MCP operations", "## Key facts").replace("## TMP", "## MCP operations")
        problems = check_links.card_problems(self.write("cards/bgp.md", swapped))
        self.assertEqual(len(problems), 1)
        self.assertIn("out of order", problems[0])

    def test_card_too_long(self):
        path = self.write("cards/bgp.md", GOOD_CARD + "x\n" * (121 - GOOD_CARD.count("\n")))
        self.assertTrue(any("120" in p for p in check_links.card_problems(path)))

    def test_docs_bullet_without_version_tag(self):
        path = self.write("cards/bgp.md", GOOD_CARD.replace(" (9.7)", ""))
        self.assertEqual(len(check_links.card_problems(path)), 1)

    def test_disallowed_host(self):
        path = self.write("cards/bgp.md", GOOD_CARD.replace(BGP_URL, "https://example.com/x"))
        self.assertTrue(any("example.com" in p for p in check_links.card_problems(path)))

    def test_relative_link_dead(self):
        path = self.write("cards/bgp.md", GOOD_CARD.replace("segmentation.md", "nope.md"))
        self.assertTrue(any("nope.md" in p for p in check_links.card_problems(path)))

    def test_link_not_in_inventory(self):
        self.assertEqual(len(check_links.link_problems(self.dir, set())), 2)  # bgp.md and segmentation.md

    def test_link_in_inventory(self):
        self.assertEqual(check_links.link_problems(self.dir, {BGP_URL}), [])

    def test_link_fragment_ignored(self):
        self.write("cards/bgp.md", GOOD_CARD.replace(BGP_URL, BGP_URL + "#add-peer"))
        self.assertEqual(check_links.link_problems(self.dir, {BGP_URL}), [])

    def test_operation_ok(self):
        self.assertEqual(check_links.operation_problems(self.dir, SPEC), [])

    def test_operation_wrong_method(self):
        self.write("cards/bgp.md", GOOD_CARD.replace("`GET /bgp", "`PUT /bgp"))
        self.assertEqual(len(check_links.operation_problems(self.dir, SPEC)), 1)

    def test_operation_query_ignored(self):
        self.write("cards/bgp.md", GOOD_CARD.replace("`GET /bgp/config/neighbor`", "`POST /appliance/rest?nePk=1.NE&url=vrrp`"))
        self.assertEqual(check_links.operation_problems(self.dir, SPEC), [])

    def test_operation_in_playbook_step(self):
        self.write("playbooks/peer.md", GOOD_PLAYBOOK.replace("/appliance/rest?", "/appliance/other?"))
        problems = check_links.operation_problems(self.dir, SPEC)
        self.assertEqual(len(problems), 1)
        self.assertIn("/appliance/other", problems[0])

    def test_router_orphan_card(self):
        self.write("SKILL.md", "# Guide\n[bgp](cards/bgp.md)\n[seg](cards/segmentation.md)\n")
        self.write("cards/ospf.md", GOOD_CARD)
        problems = check_links.router_problems(self.dir)
        self.assertEqual(len(problems), 1)
        self.assertIn("ospf.md", problems[0])

    def test_router_dead_link(self):
        self.write("SKILL.md", "# Guide\n[bgp](cards/bgp.md)\n[seg](cards/segmentation.md)\n[x](cards/missing.md)\n")
        self.assertTrue(any("missing.md" in p for p in check_links.router_problems(self.dir)))

    def test_router_too_long(self):
        self.write("SKILL.md", "[bgp](cards/bgp.md)\n[seg](cards/segmentation.md)\n" + "x\n" * 149)
        self.assertTrue(any("150" in p for p in check_links.router_problems(self.dir)))

    def test_good_playbook_passes(self):
        self.assertEqual(check_links.playbook_problems(self.write("playbooks/peer.md", GOOD_PLAYBOOK)), [])

    def test_playbook_first_step_writes(self):
        text = GOOD_PLAYBOOK.replace("1. Call `find_operations` for BGP.", "1. Call `api_write` first.")
        problems = check_links.playbook_problems(self.write("playbooks/peer.md", text))
        self.assertEqual(len(problems), 1)
        self.assertIn("api_write", problems[0])

    def test_playbook_step_without_tool(self):
        text = GOOD_PLAYBOOK.replace("2. Call `api_write`", "2. Just do it")
        self.assertEqual(len(check_links.playbook_problems(self.write("playbooks/peer.md", text))), 1)

    def test_playbook_wrapped_step_uses_continuation_line(self):
        text = GOOD_PLAYBOOK.replace("2. Call `api_write` with", "2. Send the change using\n   `api_write` with")
        self.assertEqual(check_links.playbook_problems(self.write("playbooks/peer.md", text)), [])

    def test_docs_bullet_tag_must_be_all_or_major_minor(self):
        for tag in ("(9)", "(1.2.3+)", "(v9.7)"):
            path = self.write("cards/bgp.md", GOOD_CARD.replace("(9.7)", tag))
            self.assertEqual(len(check_links.card_problems(path)), 1, tag)
        for tag in ("(all)", "(9.6+)", "(9.3)"):
            self.assertEqual(check_links.card_problems(self.write("cards/bgp.md", GOOD_CARD.replace("(9.7)", tag))), [], tag)

    def test_docs_bullet_wrapped_checks_last_line(self):
        wrapped = GOOD_CARD.replace("- [BGP Tab](%s) (9.7)" % BGP_URL, "- [BGP Tab](%s)\n  more words (9.7)" % BGP_URL)
        self.assertEqual(check_links.card_problems(self.write("cards/bgp.md", wrapped)), [])
        untagged = GOOD_CARD.replace("(9.7)", "").replace("- [BGP Tab](%s) " % BGP_URL, "- [BGP Tab](%s)\n  more words" % BGP_URL)
        self.assertEqual(len(check_links.card_problems(self.write("cards/bgp.md", untagged))), 1)
        tag_on_first_only = GOOD_CARD.replace("(9.7)", "(9.7)\n  trailing words")
        self.assertEqual(len(check_links.card_problems(self.write("cards/bgp.md", tag_on_first_only))), 1)

    def test_link_with_parenthesis_in_url_is_one_link(self):
        self.write("cards/bgp.md", GOOD_CARD.replace(BGP_URL, BGP_URL + "x_(y)"))
        problems = check_links.link_problems(self.dir, {BGP_URL})
        self.assertEqual(len(problems), 1)
        self.assertIn("x_(y)", problems[0])

    def test_link_in_code_span_ignored(self):
        self.write("cards/bgp.md", GOOD_CARD + "Write `[x](https://example.com/y)` literally.\n")
        self.assertEqual(check_links.card_problems(self.dir / "cards" / "bgp.md"), [])
        self.assertEqual(check_links.link_problems(self.dir, {BGP_URL}), [])

    def test_playbook_empty_steps_reported(self):
        text = GOOD_PLAYBOOK.replace("1. Call `find_operations` for BGP.\n2. Call `api_write` with `POST /appliance/rest?nePk=1.NE&url=vrrp`.\n", "")
        problems = check_links.playbook_problems(self.write("playbooks/peer.md", text))
        self.assertEqual(len(problems), 1)
        self.assertIn("no numbered steps", problems[0])

    def test_playbook_numbering_must_start_at_one(self):
        text = GOOD_PLAYBOOK.replace("1. Call `find", "2. Call `find").replace("2. Call `api_write`", "3. Call `api_write`")
        problems = check_links.playbook_problems(self.write("playbooks/peer.md", text))
        self.assertEqual(len(problems), 1)
        self.assertIn("numbering", problems[0])

    def test_docs_trailing_prose_is_not_part_of_last_bullet(self):
        text = GOOD_CARD.replace("## Key facts", "Notes after the list.\n\n## Key facts")
        self.assertEqual(check_links.card_problems(self.write("cards/bgp.md", text)), [])
        text = GOOD_CARD.replace("## Key facts", "Unindented line after the list.\n## Key facts")
        self.assertEqual(check_links.card_problems(self.write("cards/bgp.md", text)), [])

    def test_operation_checked_in_every_section(self):
        for section in ("Verify", "Key facts"):
            self.write("SKILL.md", "# Guide\n[bgp](cards/bgp.md)\n[seg](cards/segmentation.md)\n")
            text = GOOD_PLAYBOOK + "\nSee `GET /nope/here` too.\n" if section == "Verify" else GOOD_CARD.replace("- Keepalive", "- Uses `GET /nope/here`. Keepalive")
            self.write("playbooks/peer.md" if section == "Verify" else "cards/bgp.md", text)
            problems = check_links.operation_problems(self.dir, SPEC)
            self.assertEqual(len(problems), 1, section)
            self.assertIn("/nope/here", problems[0])
            (self.dir / "playbooks" / "peer.md").unlink(missing_ok=True)
            self.write("cards/bgp.md", GOOD_CARD)
        self.write("cards/bgp.md", GOOD_CARD)
        self.write("SKILL.md", "[b](cards/bgp.md)\nUse `GET /nope/there`.\n")
        self.assertTrue(any("/nope/there" in p for p in check_links.operation_problems(self.dir, SPEC)))

    def test_sources_page_is_link_checked(self):
        self.write("SKILL.md", "[bgp](cards/bgp.md)\n[seg](cards/segmentation.md)\n")
        self.write("sources.md", "# Sources\n[x](https://example.com/y)\n")
        self.assertTrue(any("example.com" in p for p in check_links.router_problems(self.dir)))
        self.assertTrue(any("not in the inventory" in p for p in check_links.link_problems(self.dir, {BGP_URL})))


    def test_load_known_urls(self):
        techdocs = self.write("a.tsv", "url\ttitle\tmenu_path\tsummary\tstatus\nhttp://h/ok/#frag\tt\tm\ts\tok\nhttp://h/so\tt\tm\ts\tsearch-only\nhttp://h/nf\tt\tm\ts\tnot-found\n\tt\tm\ts\tnot-found\n")
        devportal = self.write("b.tsv", "url\ttitle\tguide\tbytes\tupdated\tfirst_text\nhttp://d/x\tt\tg\t1\t2026\t\"quoted\n")
        urls = check_links.load_known_urls([techdocs, devportal])
        self.assertEqual(urls, {"http://h/ok/", "http://h/so", "http://d/x"})

    def test_real_skill_passes_format_checks(self):
        self.assertEqual(check_links.main([]), 0)

    def test_main_fails_on_problem(self):
        self.write("SKILL.md", "# Guide\n")  # leaves both cards orphaned
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = check_links.main(["--skill-dir", str(self.dir)])
        self.assertEqual(code, 1)
        self.assertIn("does not link cards/bgp.md", out.getvalue())


def _response(status):
    resp = mock.MagicMock()
    resp.status = status
    resp.__enter__.return_value = resp
    return resp


def _http_error(code, headers=None):
    return urllib.error.HTTPError("https://developer.arubanetworks.com/x", code, "msg", headers or {}, None)


class HttpProblemsTests(unittest.TestCase):
    URL = "https://developer.arubanetworks.com/edgeconnect/docs/x"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        (self.dir / "cards").mkdir()
        (self.dir / "cards" / "a.md").write_text("[a](%s)\n" % self.URL)

    def run_check(self, side_effect):
        with mock.patch("urllib.request.urlopen", side_effect=side_effect) as urlopen, mock.patch("time.sleep") as sleep:
            problems = check_links.http_problems(self.dir)
        return problems, urlopen, sleep

    def test_ok(self):
        problems, _, _ = self.run_check([_response(200)])
        self.assertEqual(problems, [])

    def test_429_is_retried_with_retry_after(self):
        problems, urlopen, sleep = self.run_check([_http_error(429, {"Retry-After": "7"}), _response(200)])
        self.assertEqual(problems, [])
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_any_call(7.0)

    def test_429_forever_is_reported_as_not_checked(self):
        problems, urlopen, _ = self.run_check([_http_error(429)] * 10)
        self.assertEqual(len(problems), 1)
        self.assertIn("rate limited, not checked", problems[0])
        self.assertLess(urlopen.call_count, 10)

    def test_404_is_a_broken_link_without_retry(self):
        problems, urlopen, _ = self.run_check([_http_error(404)])
        self.assertEqual(problems, ["%s: HTTP 404" % self.URL])
        self.assertEqual(urlopen.call_count, 1)

    def test_url_error_reported(self):
        problems, _, _ = self.run_check(urllib.error.URLError("boom"))
        self.assertIn("request failed", problems[0])

    def test_pause_between_requests(self):
        (self.dir / "cards" / "b.md").write_text("[b](%s2)\n" % self.URL)
        _, urlopen, sleep = self.run_check([_response(200), _response(200)])
        self.assertEqual(urlopen.call_count, 2)
        self.assertEqual(sleep.call_count, 1)


if __name__ == "__main__":
    unittest.main()

    def test_playbook_without_reference_notice(self):
        text = GOOD_PLAYBOOK.replace("> **Reference only.** Tested on a lab.\n", "")
        problems = check_links.playbook_problems(self.write("playbooks/peer.md", text))
        self.assertEqual(len(problems), 1)
        self.assertIn("Reference only", problems[0])

    def test_tested_operations(self):
        tested_file = self.write("tested-operations.tsv", "# note\nmethod\tpath\nGET\t/bgp/config/neighbor\n")
        tested = check_links.load_tested(tested_file)
        self.assertEqual(tested, {("GET", "/bgp/config/neighbor")})
        self.assertEqual(check_links.tested_problems(self.dir, tested), [])
        self.write("playbooks/peer.md", GOOD_PLAYBOOK)
        problems = check_links.tested_problems(self.dir, tested)
        self.assertEqual(len(problems), 1)
        self.assertIn("POST /appliance/rest", problems[0])

    def test_untested_wording_flagged(self):
        self.write("cards/bgp.md", GOOD_CARD.replace("reads neighbors", "reads neighbors (untested)"))
        problems = check_links.tested_problems(self.dir, {("GET", "/bgp/config/neighbor")})
        self.assertEqual(len(problems), 1)
        self.assertIn("untested", problems[0])
