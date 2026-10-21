"""Smoke-test live Tor collection through the running ShadowGraph API.

Usage: python scripts/live_onion_check.py [URL ...]
Defaults to public, legal v3 onion services (DuckDuckGo, Tor Project).
"""
import json
import sys

import requests

API = "http://127.0.0.1:8100/api/tor-ingest"
DEFAULTS = [
    "https://duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad.onion/",
    "http://2gzyxa5ihm7nsggfxnu52rck2vv4rvmdlkiu3zzui5du4xyclen53wid.onion/",
]

for url in sys.argv[1:] or DEFAULTS:
    print(f"=== {url}")
    try:
        r = requests.post(API, json={"url": url}, timeout=120)
        d = r.json()
        print(json.dumps({
            "http": r.status_code,
            "mode": d.get("mode"),
            "live": d.get("live"),
            "live_error": d.get("live_error"),
            "fetch": d.get("fetch"),
            "entity_count": d.get("entity_count"),
            "text_preview": (d.get("raw_text") or "")[:200],
        }, indent=2))
    except Exception as exc:
        print("FAILED:", exc)
