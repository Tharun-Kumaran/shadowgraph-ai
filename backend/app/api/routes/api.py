"""
FastAPI REST API routes for ShadowGraph AI.
Prefix: /api/v1
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import PlainTextResponse

from app.core.config import Settings, get_settings
from app.core.security import require_api_key
from app.graph.client import Neo4jClient
from app.graph.repository import GraphRepository
from app.graphrag.service import GraphRAGService, OllamaClient
from app.ingestion.normalizer import normalize_record
from app.ingestion.parsers import decode_bytes, detect_format, parse_content, safe_filename
from app.ingestion.pipeline import CollectionPipeline
from app.reporting.export import ExportService
from app.schemas.api import (
    CollectSourceRequest,
    DashboardMetricsResponse,
    GraphElementsResponse,
    GraphRAGQueryRequest,
    GraphRAGQueryResponse,
    HealthResponse,
    IncidentCreateRequest,
    IncidentResponse,
    TorStatusResponse,
)
from app.schemas.clues import ClueRecord, ClueStatus, ReviewRequest
from app.schemas.observations import IngestReport, RejectedRecord

router = APIRouter()
START_TIME = time.time()


def get_neo4j(settings: Settings = Depends(get_settings)) -> Neo4jClient:
    return Neo4jClient(settings)


def get_repo(client: Neo4jClient = Depends(get_neo4j)) -> GraphRepository:
    return GraphRepository(client)


# --- Health & Status ---

@router.get("/health", response_model=HealthResponse)
def health(
    settings: Settings = Depends(get_settings),
    neo4j: Neo4jClient = Depends(get_neo4j),
):
    neo4j_health = neo4j.health()
    ollama_health = OllamaClient(settings).check_health()
    tor_health = CollectionPipeline(settings, neo4j).check_tor_status()
    return HealthResponse(
        status="ok" if neo4j_health.get("status") == "ok" else "degraded",
        version="0.1.0",
        neo4j=neo4j_health,
        ollama=ollama_health,
        embeddings={"provider": settings.embedding_provider, "model": settings.embedding_model},
        tor=tor_health,
        uptime_seconds=round(time.time() - START_TIME, 2),
    )


# --- Dashboard ---

@router.get("/dashboard/metrics", response_model=DashboardMetricsResponse)
def get_dashboard_metrics(repo: GraphRepository = Depends(get_repo)):
    return repo.get_dashboard_metrics()


# --- Ingestion & Live Collection ---

@router.get("/ingest/tor-status", response_model=TorStatusResponse)
def get_tor_status(
    settings: Settings = Depends(get_settings),
    neo4j: Neo4jClient = Depends(get_neo4j),
):
    return CollectionPipeline(settings, neo4j).check_tor_status()


@router.post("/ingest/collect", response_model=IngestReport)
def collect_live_source(
    req: CollectSourceRequest,
    settings: Settings = Depends(get_settings),
    neo4j: Neo4jClient = Depends(get_neo4j),
    _auth: None = Depends(require_api_key),
):
    pipeline = CollectionPipeline(settings, neo4j)
    try:
        return pipeline.collect_and_ingest(
            req.url,
            source_id=req.source_id,
            source_name=req.source_name,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/ingest/upload", response_model=IngestReport)
async def upload_file(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
    repo: GraphRepository = Depends(get_repo),
    _auth: None = Depends(require_api_key),
):
    raw_bytes = await file.read()
    if len(raw_bytes) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds maximum upload size of {settings.max_upload_bytes} bytes")

    filename = safe_filename(file.filename)
    fmt = detect_format(filename)
    text = decode_bytes(raw_bytes)
    records, rejected, detected_fmt = parse_content(text, fmt)

    accepted = 0
    obs_ids = []
    extraction_summary: Dict[str, int] = {}

    for idx, rec in records:
        try:
            obs = normalize_record(
                rec,
                default_source=filename,
                default_source_type="file",
                max_text_chars=settings.max_text_chars,
                retention=settings.text_retention,
            )
            repo.store_observation(obs)
            accepted += 1
            obs_ids.append(obs.observation_id)
            for ent in obs.entities:
                t = ent.get("type", "unknown")
                extraction_summary[t] = extraction_summary.get(t, 0) + 1
        except Exception as exc:
            rejected.append(RejectedRecord(index=idx, reason=str(exc)))

    return IngestReport(
        batch_id=f"batch_{int(time.time())}",
        filename=filename,
        format=detected_fmt,
        total_records=len(records) + len(rejected),
        accepted=accepted,
        duplicates_in_batch=0,
        duplicates_existing=0,
        rejected=rejected,
        extraction_summary=extraction_summary,
        observation_ids=obs_ids,
        stored=True,
    )


# --- Graph & Exploration ---

@router.get("/graph/elements", response_model=GraphElementsResponse)
def get_graph_elements(
    types: Optional[List[str]] = Query(None),
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 150,
    repo: GraphRepository = Depends(get_repo),
):
    return repo.get_graph_elements(entity_types=types, status=status, search=search, limit=limit)


@router.get("/entities/{uid}")
def get_entity_details(uid: str, repo: GraphRepository = Depends(get_repo)):
    details = repo.get_entity_details(uid)
    if not details:
        raise HTTPException(status_code=404, detail=f"Entity '{uid}' not found in graph")
    return details


@router.get("/clues")
def list_clues(
    status: Optional[str] = None,
    limit: int = 50,
    repo: GraphRepository = Depends(get_repo),
):
    return repo.list_clues(status=status, limit=limit)


@router.get("/clues/{clue_id}")
def get_clue_detail(
    clue_id: str,
    repo: GraphRepository = Depends(get_repo),
):
    clue = repo.get_clue(clue_id)
    if not clue:
        raise HTTPException(status_code=404, detail=f"Clue '{clue_id}' not found")
    return clue


@router.post("/clues/{clue_id}/review")
def review_clue(
    clue_id: str,
    req: ReviewRequest,
    repo: GraphRepository = Depends(get_repo),
    _auth: None = Depends(require_api_key),
):
    updated = repo.review_clue(clue_id, req.status, req.reviewer, req.notes)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Clue '{clue_id}' not found")
    return {"status": "success", "clue_id": clue_id, "new_status": req.status}


# --- GraphRAG AI Assistant ---

@router.post("/graphrag/query", response_model=GraphRAGQueryResponse)
def query_graphrag(
    req: GraphRAGQueryRequest,
    settings: Settings = Depends(get_settings),
    neo4j: Neo4jClient = Depends(get_neo4j),
):
    service = GraphRAGService(settings, neo4j, OllamaClient(settings))
    return service.answer_question(req.question, req.focus_entity_uid)


# --- SIEM Export ---

@router.get("/export/indicators/json")
def export_indicators_json(neo4j: Neo4jClient = Depends(get_neo4j)):
    return ExportService(neo4j).export_indicators_json()


@router.get("/export/indicators/csv")
def export_indicators_csv(neo4j: Neo4jClient = Depends(get_neo4j)):
    csv_data = ExportService(neo4j).export_indicators_csv()
    return PlainTextResponse(content=csv_data, media_type="text/csv")


@router.get("/export/stix")
def export_stix(neo4j: Neo4jClient = Depends(get_neo4j)):
    return ExportService(neo4j).export_stix21_bundle()


# --- Incident & CERT-In Reporting ---

@router.post("/incidents/draft-certin")
def draft_certin_report(
    req: IncidentCreateRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
):
    return ExportService(neo4j).generate_certin_report(req.model_dump())
