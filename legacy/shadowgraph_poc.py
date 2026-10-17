#!/usr/bin/env python3
"""
ShadowGraph AI — reconstructed proof of concept.

PROVENANCE NOTICE
-----------------
This file is a *reconstruction* written from the author's description of the
original ShadowGraph PoC. It is NOT byte-for-byte identical to the original
``shadowgraph_poc.py`` (which was not available in the repository). It keeps
the same core idea, function names, the five experimental scoring weights and
the four original regex families so the modular application can be traced
back to it.

The production implementation lives in ``backend/app``:

* ``safe_fetch_onion``       -> backend/app/ingestion/tor_collector.py
* ``REGEX_PATTERNS``         -> backend/app/extraction/patterns.py (extended)
* ``extract_entities``       -> backend/app/extraction/extractor.py
* ``cosine_similarity``      -> backend/app/correlation/similarity.py
* ``compute_same_as_clue``   -> backend/app/correlation/scoring.py
* ``generate_neo4j_cypher``  -> backend/app/graph/repository.py (parameterised)

All data in ``run_demo()`` is SYNTHETIC. "pepela" and "Spirigatito" are
fictional handles. The style vectors are hand-written test fixtures and are
NOT real authorship embeddings.

Run:  python legacy/shadowgraph_poc.py
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# --------------------------------------------------------------------------
# Experimental weights (preserved from the original PoC)
# --------------------------------------------------------------------------
WEIGHTS = {
    "technical_artifact_overlap": 0.65,
    "stylometry_similarity": 0.15,
    "lexical_similarity": 0.08,
    "graph_neighborhood_overlap": 0.07,
    "temporal_similarity": 0.05,
}

# --------------------------------------------------------------------------
# Regex patterns (original four families)
# --------------------------------------------------------------------------
REGEX_PATTERNS: dict[str, re.Pattern[str]] = {
    "cve": re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE),
    # Ethereum-style address: 0x + 40 hex characters
    "eth_address": re.compile(r"\b0x[a-fA-F0-9]{40}\b"),
    # 76-character hexadecimal identifier (e.g. Tox ID); must not be part of
    # a longer hex run
    "hex76_id": re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{76}(?![0-9A-Fa-f])"),
    "uuid": re.compile(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
    ),
}


@dataclass
class ForumPost:
    """A single (synthetic) forum observation."""

    post_id: str
    handle: str
    forum: str
    timestamp: datetime
    content: str
    entities: dict[str, list[str]] = field(default_factory=dict)


# --------------------------------------------------------------------------
# Optional isolated Tor fetcher (not used by the offline demo)
# --------------------------------------------------------------------------
def safe_fetch_onion(
    url: str,
    proxy: str = "socks5h://127.0.0.1:9050",
    timeout: tuple[float, float] = (10.0, 30.0),
    max_bytes: int = 2 * 1024 * 1024,
) -> str | None:
    """Fetch a single *authorised* .onion page as text via a SOCKS5 proxy.

    ``socks5h`` makes the proxy resolve DNS. Redirects are refused, only
    text content types are accepted, and the body is size-limited while
    streaming. Returns None on any failure. Content is never executed.
    """
    try:
        import requests  # imported lazily so the demo needs only stdlib
    except ImportError:  # pragma: no cover
        return None

    if not re.match(r"^https?://[a-z2-7]{56}\.onion(/|$)", url):
        return None
    proxies = {"http": proxy, "https": proxy}
    try:
        with requests.get(
            url, proxies=proxies, timeout=timeout, stream=True, allow_redirects=False
        ) as resp:
            if resp.status_code != 200:
                return None
            ctype = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if ctype not in {"text/html", "text/plain"}:
                return None
            chunks: list[bytes] = []
            total = 0
            for chunk in resp.iter_content(chunk_size=8192):
                total += len(chunk)
                if total > max_bytes:
                    return None
                chunks.append(chunk)
            return b"".join(chunks).decode(resp.encoding or "utf-8", errors="replace")
    except Exception:
        return None


# --------------------------------------------------------------------------
# Extraction and similarity
# --------------------------------------------------------------------------
def extract_entities(text: str) -> dict[str, list[str]]:
    """Return de-duplicated regex matches per pattern family (order preserved)."""
    out: dict[str, list[str]] = {}
    for name, pattern in REGEX_PATTERNS.items():
        seen: dict[str, None] = {}
        for m in pattern.finditer(text):
            value = m.group(0)
            value = value.upper() if name in {"cve", "hex76_id"} else value.lower()
            seen.setdefault(value, None)
        out[name] = list(seen)
    return out


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity clipped to [0, 1]. Returns 0.0 for empty/zero/mismatched vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (na * nb)))


def _lexical(a: str, b: str) -> float:
    """Normalised Levenshtein similarity of two handles."""
    a, b = a.lower(), b.lower()
    if a == b:
        return 1.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return 1.0 - prev[-1] / max(len(a), len(b))


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if (a or b) else 0.0


def _temporal(hours_a: list[int], hours_b: list[int]) -> float:
    """1 - circular distance between mean posting hours / 12."""
    if not hours_a or not hours_b:
        return 0.0

    def circ_mean(hours: list[int]) -> float:
        s = sum(math.sin(2 * math.pi * h / 24) for h in hours)
        c = sum(math.cos(2 * math.pi * h / 24) for h in hours)
        return (math.atan2(s, c) * 24 / (2 * math.pi)) % 24

    d = abs(circ_mean(hours_a) - circ_mean(hours_b))
    d = min(d, 24 - d)
    return 1.0 - d / 12.0


def compute_same_as_clue(
    posts_a: list[ForumPost],
    posts_b: list[ForumPost],
    style_a: list[float],
    style_b: list[float],
) -> dict[str, Any]:
    """Weighted SAME_AS *clue* between two handles (a heuristic, not proof)."""
    art_a = {v for p in posts_a for k in ("eth_address", "hex76_id", "uuid") for v in p.entities.get(k, [])}
    art_b = {v for p in posts_b for k in ("eth_address", "hex76_id", "uuid") for v in p.entities.get(k, [])}
    shared = sorted(art_a & art_b)
    cves_a = {v for p in posts_a for v in p.entities.get("cve", [])}
    cves_b = {v for p in posts_b for v in p.entities.get("cve", [])}

    signals = {
        "technical_artifact_overlap": 1.0 if shared else 0.0,
        "stylometry_similarity": cosine_similarity(style_a, style_b),
        "lexical_similarity": _lexical(posts_a[0].handle, posts_b[0].handle),
        "graph_neighborhood_overlap": _jaccard(cves_a, cves_b),
        "temporal_similarity": _temporal(
            [p.timestamp.astimezone(timezone.utc).hour for p in posts_a],
            [p.timestamp.astimezone(timezone.utc).hour for p in posts_b],
        ),
    }
    score = sum(WEIGHTS[k] * v for k, v in signals.items())
    return {
        "handle_a": posts_a[0].handle,
        "handle_b": posts_b[0].handle,
        "score": round(score, 4),
        "score_type": "heuristic",
        "status": "candidate",
        "signals": {k: round(v, 4) for k, v in signals.items()},
        "shared_artifacts": shared,
        "scoring_method_version": "poc-0.1",
    }


def generate_neo4j_cypher(clue: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Return a *parameterised* Cypher statement and its parameters.

    Values are never interpolated into the query text.
    """
    query = (
        "MERGE (a:Handle {name: $handle_a}) "
        "MERGE (b:Handle {name: $handle_b}) "
        "MERGE (a)-[r:SAME_AS]->(b) "
        "SET r.confidence_score = $score, r.score_type = $score_type, "
        "r.status = $status, r.signals_json = $signals_json, "
        "r.scoring_method_version = $version, r.updated_at = datetime()"
    )
    params = {
        "handle_a": clue["handle_a"],
        "handle_b": clue["handle_b"],
        "score": clue["score"],
        "score_type": clue["score_type"],
        "status": clue["status"],
        "signals_json": json.dumps(clue["signals"], sort_keys=True),
        "version": clue["scoring_method_version"],
    }
    return query, params


# --------------------------------------------------------------------------
# SYNTHETIC demonstration — fictional handles, fictional artifacts
# --------------------------------------------------------------------------
SYNTHETIC_TOX = (
    "56A1ADE4B65B86BCD51CC73E2CD4E542179F47959FE3E0E21B4B0ACDADE51855"
    "D34D34D3D1E5"
)


def run_demo() -> dict[str, Any]:
    utc = timezone.utc
    posts_a = [
        ForumPost("SYN-1", "pepela", "synthetic-forum-alpha", datetime(2026, 3, 1, 23, 10, tzinfo=utc),
                  f"[SYNTHETIC] Selling access, PoC for CVE-2024-3400 ready. Tox: {SYNTHETIC_TOX}"),
        ForumPost("SYN-2", "pepela", "synthetic-forum-alpha", datetime(2026, 3, 3, 0, 40, tzinfo=utc),
                  "[SYNTHETIC] Escrow to 0x1111111111111111111111111111111111111111 only."),
    ]
    posts_b = [
        ForumPost("SYN-3", "Spirigatito", "synthetic-forum-beta", datetime(2026, 3, 5, 1, 5, tzinfo=utc),
                  f"[SYNTHETIC] New loader build, contact tox {SYNTHETIC_TOX.lower()}"),
        ForumPost("SYN-4", "Spirigatito", "synthetic-forum-beta", datetime(2026, 3, 6, 22, 55, tzinfo=utc),
                  "[SYNTHETIC] Also interested in CVE-2024-3400 chains."),
    ]
    for p in posts_a + posts_b:
        p.entities = extract_entities(p.content)

    # Hand-written SYNTHETIC style vectors (test fixtures, not embeddings).
    style_pepela = [0.12, 0.80, 0.33, 0.05, 0.41]
    style_spirigatito = [0.10, 0.78, 0.30, 0.09, 0.44]

    clue = compute_same_as_clue(posts_a, posts_b, style_pepela, style_spirigatito)
    query, params = generate_neo4j_cypher(clue)
    return {"clue": clue, "cypher": query, "params": params}


if __name__ == "__main__":
    result = run_demo()
    print("== ShadowGraph PoC (reconstructed) — SYNTHETIC DATA ==")
    print(json.dumps(result["clue"], indent=2))
    print("\nParameterised Cypher:\n" + result["cypher"])
    print("\nParameters:\n" + json.dumps(result["params"], indent=2))
    print("\nNOTE: the score is a heuristic clue for analyst review, not proof of identity.")
