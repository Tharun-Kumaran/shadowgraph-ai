"""Crawl orchestration: run the onion crawler, persist to Neo4j, track jobs."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from app.core.config import Settings
from app.core.logging import get_logger
from app.graph.client import Neo4jClient
from app.graph.repository import GraphRepository
from app.ingestion.collectors import FetchResult
from app.ingestion.crawler import (
    CrawlConfig,
    CrawlResult,
    OnionCrawler,
    discover_onions,
    make_tor_fetcher,
)
from app.ingestion.normalizer import normalize_record

log = get_logger(__name__)

_JOBS: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.Lock()


def persist_crawl(result: CrawlResult, repo: GraphRepository, settings: Settings) -> Dict[str, int]:
    """Store each crawled page as a live (non-synthetic) Tor observation + link graph."""
    stored = 0
    entity_counts: Dict[str, int] = {}
    for page in result.pages:
        body = f"{page.title}\n\n{page.text}".strip() if page.title else page.text
        record = {
            "text": f"URL: {page.url}\n{body}"[: settings.max_text_chars],
            "source": page.host,
            "source_name": f"onion:{page.host[:16]}…",
            "source_type": "tor",
            "source_url": f"http://{page.host}/",
        }
        try:
            obs = normalize_record(
                record,
                default_source=page.host,
                default_source_type="tor",
                max_text_chars=settings.max_text_chars,
                retention=settings.text_retention,
                collected_at=page.fetched_at,
                force_synthetic=False,
            )
            repo.store_observation(obs)
            stored += 1
            for ent in obs.entities:
                t = ent.get("type", "unknown")
                entity_counts[t] = entity_counts.get(t, 0) + 1
        except Exception as exc:
            result.errors.append({"url": page.url, "error": f"persist: {exc}"})
    links = repo.store_onion_links(sorted(result.edges), result.host_status)
    return {"pages_stored": stored, "links_stored": links, **{f"entity_{k}": v for k, v in entity_counts.items()}}


def run_crawl(
    settings: Settings,
    neo4j: Neo4jClient,
    *,
    seeds: List[str],
    query: Optional[str] = None,
    config: Optional[CrawlConfig] = None,
    fetch: Optional[Callable[[str], FetchResult]] = None,
) -> Dict[str, Any]:
    """Synchronous crawl+persist. ``fetch`` is injectable for tests."""
    cfg = (config or CrawlConfig()).clamp()
    fetch = fetch or make_tor_fetcher(settings.tor_proxy, max_bytes=1024 * 1024)
    discovered: List[str] = []
    discovery_errors: List[str] = []
    if query:
        discovered = discover_onions(fetch, query, errors=discovery_errors)
    all_seeds = list(dict.fromkeys([*seeds, *discovered]))
    result = OnionCrawler(fetch, cfg).run(all_seeds)
    stored = persist_crawl(result, GraphRepository(neo4j), settings)
    out = result.summary()
    out["discovered_seeds"] = discovered
    out["discovery_errors"] = discovery_errors
    out["stored"] = stored
    return out


# -- background job registry ---------------------------------------------

def start_job(settings: Settings, neo4j: Neo4jClient, **kwargs: Any) -> str:
    job_id = uuid.uuid4().hex[:12]
    with _LOCK:
        _JOBS[job_id] = {
            "job_id": job_id,
            "status": "running",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "result": None,
            "error": None,
        }

    def _work() -> None:
        try:
            res = run_crawl(settings, neo4j, **kwargs)
            update = {"status": "completed", "result": res}
        except Exception as exc:
            log.warning("crawl job %s failed: %s", job_id, exc)
            update = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
        with _LOCK:
            _JOBS[job_id].update(update, finished_at=datetime.now(timezone.utc).isoformat())

    threading.Thread(target=_work, name=f"crawl-{job_id}", daemon=True).start()
    return job_id


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        job = _JOBS.get(job_id)
        return dict(job) if job else None


def list_jobs() -> List[Dict[str, Any]]:
    with _LOCK:
        return [
            {k: v for k, v in j.items() if k != "result"} for j in _JOBS.values()
        ]
