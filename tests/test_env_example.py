import re
import unittest
from pathlib import Path

from edgeconnect_mcp.config import ALIASES, parse_dotenv

ROOT = Path(__file__).resolve().parents[1]
SRC = "\n".join(path.read_text(encoding="utf-8") for path in sorted((ROOT / "src" / "edgeconnect_mcp").glob("*.py")))
EXAMPLE = ROOT / ".env.example"


def keys_read_by_code():
    """(full key names, per-nickname suffixes) the code reads from .env or the environment, found the way a reader greps for them."""
    full = set(re.findall(r'settings\.get\("([A-Za-z_]+)"', SRC))
    full |= set(re.findall(r'_networks\(settings, "([a-z_]+)"', SRC))
    full |= set(re.findall(r'os\.environ\.get\("([A-Z_]+)"\)', SRC))
    full |= {name for names in ALIASES.values() for name in names}
    suffixes = set(re.findall(r'\b(?:option|enabled)\("([a-z_]+)"', SRC))
    suffixes |= set(re.findall(r'settings\.get\("\{\}_([a-z_]+)"\.format', SRC))
    suffixes |= {field for group in re.findall(r'for field in \(([^)]*)\)', SRC) for field in re.findall(r'"([a-z_0-9]+)"', group)}
    return full, suffixes


class EnvExampleTest(unittest.TestCase):
    def test_every_key_the_code_reads_is_documented(self):
        text = EXAMPLE.read_text(encoding="utf-8")
        full, suffixes = keys_read_by_code()
        self.assertGreaterEqual(len(full), 30, "the key search found too few keys; update keys_read_by_code")
        self.assertGreaterEqual(len(suffixes), 12, "the suffix search found too few keys; update keys_read_by_code")
        missing = sorted(key for key in full if not re.search(r"(?<!\w){}(?!\w)".format(key), text))
        missing += sorted("<nickname>_" + suffix for suffix in suffixes if not re.search(r"_{}(?!\w)".format(suffix), text))
        self.assertEqual(missing, [], ".env.example does not mention these keys")

    def test_example_parses_with_the_server_parser(self):
        values = parse_dotenv(str(EXAMPLE))
        self.assertEqual(values["orch_1"], "lab")
        self.assertEqual(values["lab_api_key"], "<API_KEY>")


if __name__ == "__main__":
    unittest.main()
