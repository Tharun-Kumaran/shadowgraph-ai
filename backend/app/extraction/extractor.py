"""Pluggable entity-extraction pipeline.

``RegexExtractor`` handles deterministic formats; ``GazetteerExtractor``
handles contextual entities (malware, organisations, products) from a
curated dictionary. Additional extractors (e.g. an NER model) can be added
by implementing the ``Extractor`` protocol — no NER model is bundled.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

from app.extraction import validators as v
from app.extraction.patterns import PGP_CONTEXT, REGEX_PATTERNS, refang
from app.models.entities import EntityType, ExtractedEntity

_URL_TRAILING = ".,;:!?)]}>'\""


class Extractor(Protocol):
    name: str

    def extract(self, text: str) -> list[ExtractedEntity]: ...


class RegexExtractor:
    name = "regex"

    def extract(self, text: str) -> list[ExtractedEntity]:
        text = refang(text)
        out: list[ExtractedEntity] = []
        P = REGEX_PATTERNS

        for m in P["cve"].finditer(text):
            ok, notes = v.validate_cve(m.group(1), m.group(2))
            out.append(ExtractedEntity(EntityType.CVE, m.group(0).upper(), m.group(0), None, ok, notes, *m.span()))

        for m in P["eth_address"].finditer(text):
            raw = m.group(0)
            notes = ["EIP-55 checksum not verified"] if raw[2:] not in (raw[2:].lower(), raw[2:].upper()) else []
            if len(set(raw[2:].lower())) < 3:
                notes.append("low-entropy address, likely placeholder")
            # Lower-casing is the canonical form of an EVM address (EIP-55
            # case only encodes a checksum), so normalising is safe here.
            out.append(ExtractedEntity(EntityType.WALLET, raw.lower(), raw, "evm", True, notes, *m.span()))

        for m in P["btc_legacy"].finditer(text):
            raw = m.group(0)
            if v.base58check_valid(raw):  # base58 is case-sensitive: keep as-is
                out.append(ExtractedEntity(EntityType.WALLET, raw, raw, "btc_base58", True, [], *m.span()))

        for m in P["btc_bech32"].finditer(text):
            raw = m.group(0)
            ok = v.bech32_valid(raw)
            if ok:
                out.append(ExtractedEntity(EntityType.WALLET, raw.lower(), raw, "btc_bech32", True, [], *m.span()))

        for m in P["hex76_id"].finditer(text):
            raw = m.group(0)
            ok = v.tox_checksum_valid(raw)
            notes = [] if ok else ["76-hex value failed Tox checksum; may be another identifier"]
            out.append(ExtractedEntity(EntityType.TOX_ID, raw.upper(), raw, "tox", ok, notes, *m.span()))

        for m in P["uuid"].finditer(text):
            out.append(ExtractedEntity(EntityType.UUID, m.group(0).lower(), m.group(0), None, True, [], *m.span()))

        pgp_spans: list[tuple[int, int]] = []
        for m in P["pgp_grouped"].finditer(text):
            norm = re.sub(r"\s+", "", m.group(0)).upper()
            pgp_spans.append(m.span())
            out.append(ExtractedEntity(EntityType.PGP_FINGERPRINT, norm, m.group(0), "v4", True, [], *m.span()))

        for m in P["hash"].finditer(text):
            raw = m.group(1)
            start = m.start(1)
            if any(a <= start < b for a, b in pgp_spans):
                continue
            if len(raw) == 40 and PGP_CONTEXT.search(text[max(0, start - 40) : start]):
                out.append(ExtractedEntity(EntityType.PGP_FINGERPRINT, raw.upper(), raw, "v4", True,
                                           ["classified as PGP from surrounding context"], *m.span(1)))
                continue
            algo = {32: "md5", 40: "sha1", 64: "sha256"}[len(raw)]
            notes, ok = [], True
            if v.hex_low_entropy(raw):
                ok, notes = False, ["low-entropy hex, likely placeholder"]
            if raw.isdigit():
                notes.append("all-digit value; may not be a hash")
            out.append(ExtractedEntity(EntityType.FILE_HASH, raw.lower(), raw, algo, ok, notes, *m.span(1)))

        for m in P["url"].finditer(text):
            raw = m.group(0).rstrip(_URL_TRAILING)
            try:
                parts = urlsplit(raw)
                host = (parts.hostname or "").lower()
                if not host:
                    continue
                netloc = host + (f":{parts.port}" if parts.port else "")
                norm = urlunsplit((parts.scheme.lower(), netloc, parts.path, parts.query, ""))
            except ValueError:
                continue
            out.append(ExtractedEntity(EntityType.URL, norm, raw, parts.scheme.lower(), True, [], m.start(), m.start() + len(raw)))

        for m in P["domain"].finditer(text):
            dom, tld = m.group(1).lower(), m.group(2).lower()
            if tld not in v.ALLOWED_TLDS:
                continue
            notes = []
            if tld == "onion":
                label = dom.rsplit(".", 2)[-2]
                if not re.fullmatch(r"[a-z2-7]{56}", label):
                    notes.append("not a valid v3 onion address")
            try:
                dom.encode("idna")
            except UnicodeError:
                continue
            out.append(ExtractedEntity(EntityType.DOMAIN, dom, m.group(1), tld, not notes, notes, *m.span(1)))

        for m in P["ipv4"].finditer(text):
            norm, notes = v.classify_ip(m.group(0))
            if norm:
                out.append(ExtractedEntity(EntityType.IP_ADDRESS, norm, m.group(0), "ipv4", True, notes, *m.span()))

        for m in P["ipv6"].finditer(text):
            raw = m.group(0)
            if "::" not in raw and raw.count(":") != 7:
                continue
            norm, notes = v.classify_ip(raw)
            if norm and ":" in norm:
                out.append(ExtractedEntity(EntityType.IP_ADDRESS, norm, raw, "ipv6", True, notes, *m.span()))

        for m in P["mention"].finditer(text):
            handle = m.group(1).rstrip(".-")
            if len(handle) >= 2:
                out.append(ExtractedEntity(EntityType.HANDLE, handle, m.group(0), "mention", True, [], *m.span()))

        return out


@dataclass
class GazetteerExtractor:
    """Dictionary-based contextual entity matcher (case-insensitive, word-bounded)."""

    entries: dict[EntityType, dict[str, str]] = field(default_factory=dict)
    name: str = "gazetteer"

    def __post_init__(self) -> None:
        self._patterns: list[tuple[EntityType, re.Pattern[str], dict[str, str]]] = []
        for etype, aliases in self.entries.items():
            if not aliases:
                continue
            lowered = {a.lower(): canon for a, canon in aliases.items()}
            alt = "|".join(re.escape(a) for a in sorted(lowered, key=len, reverse=True))
            self._patterns.append((etype, re.compile(rf"(?i)(?<![\w-])({alt})(?![\w-])"), lowered))

    @classmethod
    def from_file(cls, path: Path) -> "GazetteerExtractor":
        data = json.loads(path.read_text(encoding="utf-8"))
        entries: dict[EntityType, dict[str, str]] = {}
        for key, canon_map in data.items():
            if key.startswith("_"):
                continue
            etype = EntityType(key)
            aliases: dict[str, str] = {}
            for canonical, alias_list in canon_map.items():
                aliases[canonical] = canonical
                for alias in alias_list:
                    aliases[alias] = canonical
            entries[etype] = aliases
        return cls(entries)

    def extract(self, text: str) -> list[ExtractedEntity]:
        out = []
        for etype, pattern, lowered in self._patterns:
            for m in pattern.finditer(text):
                canon = lowered[m.group(1).lower()]
                out.append(ExtractedEntity(etype, canon, m.group(1), "gazetteer", True, [], *m.span(1)))
        return out


@dataclass
class ExtractionResult:
    entities: list[ExtractedEntity]
    counts: dict[str, int]
    extractors: list[str]

    def to_dict(self) -> dict:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "counts": self.counts,
            "extractors": self.extractors,
        }


class ExtractionPipeline:
    def __init__(self, extractors: list[Extractor]):
        self.extractors = extractors

    def run(self, text: str) -> ExtractionResult:
        seen: dict[str, ExtractedEntity] = {}
        for ex in self.extractors:
            for ent in ex.extract(text):
                seen.setdefault(ent.uid, ent)  # de-duplicate, keep first occurrence
        ents = sorted(seen.values(), key=lambda e: (e.start, e.type.value, e.value))
        counts = Counter(e.type.value for e in ents)
        return ExtractionResult(ents, dict(sorted(counts.items())), [e.name for e in self.extractors])


DEFAULT_GAZETTEER = Path(__file__).with_name("gazetteer.json")
_default: ExtractionPipeline | None = None


def default_pipeline() -> ExtractionPipeline:
    global _default
    if _default is None:
        _default = ExtractionPipeline([RegexExtractor(), GazetteerExtractor.from_file(DEFAULT_GAZETTEER)])
    return _default


def extract_entities(text: str) -> list[ExtractedEntity]:
    """Compatibility wrapper for the PoC function name."""
    return default_pipeline().run(text).entities
