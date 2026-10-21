"""
ShadowGraph AI Backend Entrypoint.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.api import router as api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.graph.client import Neo4jClient
from app.graph.schema import init_schema

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    log.info("Starting ShadowGraph AI Backend v0.1.0...")

    # Attempt schema initialisation if Neo4j is reachable
    client = Neo4jClient(settings)
    health = client.health()
    if health.get("status") == "ok":
        try:
            applied = init_schema(client)
            log.info("Successfully verified/applied %d Neo4j schema constraints/indexes.", applied)
        except Exception as exc:
            log.warning("Could not auto-apply Neo4j schema: %s", exc)
    else:
        log.warning("Neo4j not yet connected (%s). Server starting in resilient degraded mode.", health.get("detail"))

    yield

    log.info("Shutting down ShadowGraph AI...")
    client.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="ShadowGraph AI",
        description="Connect the clues. Map the network. Investigate with confidence.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/health")
    def root_health():
        return {
            "status": "ok",
            "service": "shadowgraph-ai",
            "version": "0.1.0",
            "tor_socks5h": settings.tor_proxy if settings.tor_enabled else "socks5h://127.0.0.1:9050",
        }

    @app.post("/api/tor-ingest")
    def tor_ingest_endpoint(payload: dict):
        import html as html_lib
        import re

        url = (payload.get("url") or "").strip()
        fallback = payload.get("fallback_text") or ""
        mode = "LOCAL_REGEX_ENGINE"
        raw_text = fallback
        live_error = None
        fetch_meta: dict = {}

        if not settings.tor_enabled:
            live_error = "Tor collection disabled (SHADOWGRAPH_TOR_ENABLED=false)"
        elif not url:
            live_error = "no URL supplied"
        else:
            try:
                from app.ingestion.tor_collector import safe_fetch_onion
                result = safe_fetch_onion(url, proxy=settings.tor_proxy)
                body = result.body.decode("utf-8", errors="replace")
                title_m = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
                text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", body)
                text = re.sub(r"(?s)<[^>]+>", " ", text)
                text = re.sub(r"\s+", " ", html_lib.unescape(text)).strip()
                raw_text = text[:50000]
                mode = "LIVE_TOR_SOCKS5H"
                fetch_meta = {
                    "status_code": result.status_code,
                    "content_type": result.content_type,
                    "bytes": len(result.body),
                    "fetched_at": result.fetched_at.isoformat(),
                    "title": html_lib.unescape(title_m.group(1)).strip() if title_m else None,
                    **{k: v for k, v in result.metadata.items() if k in {"via", "host"}},
                }
            except Exception as exc:  # surface the reason instead of hiding it
                live_error = f"{type(exc).__name__}: {exc}"

        from app.extraction.extractor import RegexExtractor
        entities = RegexExtractor().extract(raw_text) if raw_text else []
        handle_match = re.search(r"Handle:\s*([a-zA-Z0-9_-]+)", raw_text, re.IGNORECASE)
        handle = handle_match.group(1) if handle_match else "unknown_actor"


        entity_list = []
        for e in entities:
            entity_list.append({
                "type": e.type.value if hasattr(e.type, "value") else str(e.type),
                "value": e.value,
                "raw": getattr(e, "raw", e.value),
                "valid": getattr(e, "valid", True),
                "notes": getattr(e, "notes", ""),
            })

        return {
            "url": url,
            "mode": mode,
            "live": mode == "LIVE_TOR_SOCKS5H",
            "live_error": live_error,
            "fetch": fetch_meta,
            "handle": handle,
            "raw_text": raw_text[:2000],
            "entity_count": len(entity_list),
            "entities": entity_list,
        }


    return app



app = create_app()
