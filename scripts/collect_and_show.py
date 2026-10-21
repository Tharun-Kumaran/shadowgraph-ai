"""Collect live data from onion sources through Tor, persist to Neo4j, and show it.

Usage: python scripts/collect_and_show.py [URL ...]
Uses the existing authenticated pipeline (POST /api/v1/ingest/collect), which
stores a Post/Source/entities with source_type="tor" (live provenance).
The API key is read from .env and never printed.
"""
import json
import sys
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8100/api/v1"
ROOT = Path(__file__).resolve().parents[1]

TARGETS = [
    ("ddg-onion", "DuckDuckGo Onion (live Tor)",
     "https://duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad.onion/"),
    ("tor-project-onion", "Tor Project Onion (live Tor)",
     "http://2gzyxa5ihm7nsggfxnu52rck2vv4rvmdlkiu3zzui5du4xyclen53wid.onion/"),
]


def api_key() -> str:
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith(("SHADOWGRAPH_API_KEY=", "API_KEY=")):
            return line.split("=", 1)[1].strip().strip('"\'')
    return ""


def main() -> None:
    headers = {"X-API-Key": api_key()}
    targets = [(f"onion-{i}", u, u) for i, u in enumerate(sys.argv[1:])] or TARGETS
    for sid, name, url in targets:
        print(f"\n=== COLLECT {url}")
        r = requests.post(f"{BASE}/ingest/collect", headers=headers, timeout=180,
                          json={"url": url, "source_id": sid, "source_name": name})
        print("HTTP", r.status_code)
        print(json.dumps(r.json(), indent=2)[:1200])

    print("\n=== STORED IN NEO4J: tor-sourced posts (live provenance)")
    sys.path.insert(0, str(ROOT / "backend"))
    from app.core.config import get_settings
    from app.graph.client import Neo4jClient

    client = Neo4jClient(get_settings())
    rows = client.read(
        "MATCH (p:Post)-[:OBSERVED_IN]->(s:Source {type:'tor'}) "
        "OPTIONAL MATCH (p)-[:MENTIONS|REFERENCES]->(e) "
        "RETURN s.name AS source, s.url AS url, p.synthetic AS synthetic, "
        "toString(p.collected_at) AS collected_at, p.text_length AS chars, "
        "p.text AS text, collect(DISTINCT e.type + ':' + e.value)[..8] AS entities "
        "ORDER BY collected_at DESC LIMIT 10"
    )
    if not rows:
        print("(no tor-sourced posts stored)")
    for row in rows:
        text = (row.pop("text") or "")[:300]
        print(json.dumps(row, indent=2, default=str))
        print("  text preview:", text, "\n")
    client.close()



if __name__ == "__main__":
    main()
