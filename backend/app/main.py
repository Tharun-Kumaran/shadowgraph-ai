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

    return app


app = create_app()
