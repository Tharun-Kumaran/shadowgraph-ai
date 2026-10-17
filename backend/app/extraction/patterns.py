"""Regular expressions for deterministic indicator formats.

Extends the PoC's four families (CVE, Ethereum-style address, 76-hex ID,
UUID) with Bitcoin, PGP, hashes, network indicators and @-mentions.
Boundary look-arounds stop a pattern from matching *inside* a longer token
(e.g. a SHA-256 inside a 76-character Tox ID).
"""

from __future__ import annotations

import re

HEX = "0-9A-Fa-f"

REGEX_PATTERNS: dict[str, re.Pattern[str]] = {
    # --- original PoC families ---------------------------------------
    # NB: [0-9] not \d — \d also matches non-ASCII digits (e.g. fullwidth).
    "cve": re.compile(r"(?<![\w-])CVE-([0-9]{4})-([0-9]{4,7})(?![\w-])", re.IGNORECASE),
    "eth_address": re.compile(rf"(?<![{HEX}\w])0x[{HEX}]{{40}}(?![{HEX}\w])"),
    "hex76_id": re.compile(rf"(?<![{HEX}\w])[{HEX}]{{76}}(?![{HEX}\w])"),
    "uuid": re.compile(
        rf"(?<![{HEX}\w-])[{HEX}]{{8}}-[{HEX}]{{4}}-[{HEX}]{{4}}-[{HEX}]{{4}}-[{HEX}]{{12}}(?![{HEX}\w-])"
    ),
    # --- extensions ---------------------------------------------------
    "btc_legacy": re.compile(r"(?<![\w])[13][a-km-zA-HJ-NP-Z1-9]{25,34}(?![\w])"),
    "btc_bech32": re.compile(r"(?<![\w])(?:bc1|BC1)[a-zA-HJ-NP-Z0-9]{11,71}(?![\w])"),
    "pgp_grouped": re.compile(rf"(?<![{HEX}\w])(?:[{HEX}]{{4}}\s{{1,2}}){{9}}[{HEX}]{{4}}(?![{HEX}\w])"),
    # 32/40/64 hex not preceded by 0x and not part of a longer hex run
    "hash": re.compile(rf"(?<![{HEX}\w])(?<!0[xX])([{HEX}]{{64}}|[{HEX}]{{40}}|[{HEX}]{{32}})(?![{HEX}\w])"),
    "url": re.compile(r"(?i)\b(?:https?|hxxps?)://[^\s<>\"'`]+"),
    "domain": re.compile(
        r"(?i)(?<![\w.@-])((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+([a-z]{2,63}))(?![\w-]|\.[a-z0-9])"
    ),
    "ipv4": re.compile(r"(?<![0-9.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9.]|\.[0-9])"),
    "ipv6": re.compile(rf"(?<![{HEX}:\w])(?:[{HEX}]{{0,4}}:){{2,7}}[{HEX}]{{0,4}}(?![{HEX}:\w])"),
    "mention": re.compile(r"(?<![\w@./])@([A-Za-z0-9_][A-Za-z0-9_.-]{1,31})"),
}

PGP_CONTEXT = re.compile(r"(?i)\b(pgp|gpg|openpgp|fingerprint|fpr)\b")

# Defanged indicator notation commonly used in CTI reports.
_REFANG = [
    (re.compile(r"\[\.\]|\(\.\)|\{\.\}|\[dot\]|\(dot\)", re.IGNORECASE), "."),
    (re.compile(r"\[:\]"), ":"),
    (re.compile(r"\bhxxp(s?)://", re.IGNORECASE), r"http\1://"),
]


def refang(text: str) -> str:
    for pattern, repl in _REFANG:
        text = pattern.sub(repl, text)
    return text
