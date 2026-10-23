import hashlib
import json
import re
from typing import Any, Mapping


# Key names whose string values are secrets. Checked against every property the 9.7.1 spec describes as a password,
# secret, key, community string or credential (tests/test_server.py lists them).
_SECRET_KEYS = re.compile(
    r"(?:api[-_]?key|authorization|cookie|csrf|password|passphrase|secret|token|psk|pre[-_]?shared|private[-_]?key|auth[-_]?key"
    r"|(?:ro|rw|trap[-_]?)community|account[-_]?key|^old[-_]?key$|(?:primary|secondary|privacy)[-_]?key|key[-_]?data|^key$"
    r"|credentials?$|barcode|licen[cs]e[-_]?key)", re.I)
_SECRET_TEXT = re.compile(r"(?i)(authorization|x-auth-token|api[-_]?key|password|secret|cookie)\s*[:=]\s*([^\s,;]+)")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _redact_secret(item: Any) -> Any:
    # Flags, numbers and empty values under secret-looking keys (passwordMinLen, csrfProtection) reveal nothing.
    if item is None or isinstance(item, (bool, int, float)) or item == "":
        return item
    return "<REDACTED>"


def redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _redact_secret(item) if _SECRET_KEYS.search(str(key)) else redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    if isinstance(value, str):
        return _SECRET_TEXT.sub(lambda match: match.group(1) + "=<REDACTED>", value)
    return value
