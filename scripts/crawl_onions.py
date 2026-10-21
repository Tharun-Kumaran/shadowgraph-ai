"""Run a live onion crawl through the API and print what was stored.

Usage:
  python scripts/crawl_onions.py --query "data breach" --pages 15 --depth 1
  python scripts/crawl_onions.py --seed http://<56-char>.onion/ --pages 10

Requires SHADOWGRAPH_TOR_ENABLED=true and SHADOWGRAPH_CRAWL_ENABLED=true.
The API key is read from .env and never printed.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8100/api/v1"


def api_key() -> str:
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith(("SHADOWGRAPH_API_KEY=", "API_KEY=")):
            return line.split("=", 1)[1].strip().strip("\"'")
    return ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="append", default=[])
    ap.add_argument("--query")
    ap.add_argument("--pages", type=int, default=15)
    ap.add_argument("--depth", type=int, default=1)
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--budget", type=float, default=240)
    a = ap.parse_args()

    h = {"X-API-Key": api_key()}
    body = {"seeds": a.seed, "query": a.query, "max_pages": a.pages, "max_depth": a.depth,
            "delay_s": a.delay, "time_budget_s": a.budget}
    r = requests.post(f"{BASE}/crawl", json=body, headers=h, timeout=30)
    print("start:", r.status_code, r.text[:300])
    if r.status_code != 202:
        sys.exit(1)
    job = r.json()["job_id"]
    while True:
        j = requests.get(f"{BASE}/crawl/{job}", timeout=30).json()
        if j["status"] != "running":
            break
        time.sleep(5)
        print("  ...running")
    print(json.dumps(j, indent=2, default=str)[:4000])


if __name__ == "__main__":
    main()
