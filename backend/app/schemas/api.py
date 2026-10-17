"""
FastAPI Pydantic Schemas for API routes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.clues import ClueRecord, ClueResult, ClueStatus
from app.schemas.observations import IngestReport


class HealthResponse(BaseModel):
    status: str
    version: str
    neo4j: Dict[str, Any]
    ollama: Dict[str, Any]
    embeddings: Dict[str, Any]
    tor: Dict[str, Any]
    uptime_seconds: float


class CollectSourceRequest(BaseModel):
    url: str = Field(min_length=10, max_length=2048)
    source_id: Optional[str] = None
    source_name: Optional[str] = None


class TorStatusResponse(BaseModel):
    configured: bool
    enabled: bool
    proxy: str
    reachable: bool
    message: str


class DashboardMetricsResponse(BaseModel):
    observations: int
    handles: int
    indicators: int
    candidate_clues: int
    reviewed_clues: int
    incidents: int


class GraphElementsResponse(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


class IncidentCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    category: str
    severity: str = Field(pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    summary: str
    affected_systems: List[str] = Field(default_factory=list)
    indicators: List[str] = Field(default_factory=list)
    evidence_uids: List[str] = Field(default_factory=list)
    containment_actions: List[str] = Field(default_factory=list)
    analyst_notes: str = ""


class IncidentResponse(BaseModel):
    incident_id: str
    title: str
    category: str
    severity: str
    status: str
    summary: str
    affected_systems: List[str]
    indicators: List[str]
    evidence_uids: List[str]
    containment_actions: List[str]
    analyst_notes: str
    created_at: datetime
    updated_at: datetime


class GraphRAGQueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    focus_entity_uid: Optional[str] = None


class GraphRAGQueryResponse(BaseModel):
    question: str
    answer: str
    evidence_references: List[Dict[str, Any]]
    limitations: List[str]
    llm_available: bool
    model: str
