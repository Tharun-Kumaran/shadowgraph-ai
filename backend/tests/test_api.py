"""
API endpoint tests covering health, ingest parsing, GraphRAG fallback, and security.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.main import create_app
from app.api.routes.api import get_neo4j, get_repo
from app.core.config import Settings, get_settings


@pytest.fixture
def mock_settings():
    return Settings(
        api_key="test-secret-key-12345",
        cors_origins=["http://localhost:5173"],
    )


@pytest.fixture
def mock_neo4j():
    client = MagicMock()
    client.health.return_value = {"status": "ok", "server": "Neo4j/5.18.0", "protocol": "5.4"}
    client.read.return_value = []
    client.write.return_value = []
    client.write_many.return_value = []
    return client


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.get_dashboard_metrics.return_value = {
        "observations": 12,
        "handles": 5,
        "indicators": 34,
        "candidate_clues": 2,
        "reviewed_clues": 1,
        "incidents": 1,
    }
    repo.list_clues.return_value = []
    repo.get_graph_elements.return_value = {"nodes": [], "edges": []}
    return repo


@pytest.fixture
def client(mock_settings, mock_neo4j, mock_repo):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: mock_settings
    app.dependency_overrides[get_neo4j] = lambda: mock_neo4j
    app.dependency_overrides[get_repo] = lambda: mock_repo
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert data["neo4j"]["status"] == "ok"


def test_dashboard_metrics(client):
    res = client.get("/api/v1/dashboard/metrics")
    assert res.status_code == 200
    data = res.json()
    assert data["observations"] == 12
    assert data["candidate_clues"] == 2


def test_graph_elements(client):
    res = client.get("/api/v1/graph/elements")
    assert res.status_code == 200
    assert "nodes" in res.json()
    assert "edges" in res.json()


def test_mutation_requires_api_key(client):
    # Missing API key header
    res = client.post("/api/v1/clues/clue_123/review", json={
        "status": "supported",
        "reviewer": "analyst_1",
        "notes": "Verified shared Tox ID"
    })
    assert res.status_code == 401

    # Invalid API key
    res = client.post("/api/v1/clues/clue_123/review", headers={"X-API-Key": "wrong-key"}, json={
        "status": "supported",
        "reviewer": "analyst_1",
        "notes": "Verified shared Tox ID"
    })
    assert res.status_code == 401


def test_mutation_with_valid_api_key(client, mock_repo):
    mock_repo.review_clue.return_value = {"clue_id": "clue_123", "status": "supported"}
    res = client.post("/api/v1/clues/clue_123/review", headers={"X-API-Key": "test-secret-key-12345"}, json={
        "status": "supported",
        "reviewer": "analyst_1",
        "notes": "Verified shared Tox ID"
    })
    assert res.status_code == 200
    assert res.json()["new_status"] == "supported"


def test_certin_report_drafting(client):
    res = client.post("/api/v1/incidents/draft-certin", json={
        "title": "Suspected Ransomware Reconnaissance",
        "category": "Ransomware / Extortion Activity",
        "severity": "HIGH",
        "summary": "Threat actor observed probing perimeter firewall CVE-2024-3400.",
        "affected_systems": ["FW-EDGE-01.corp"],
        "indicators": ["CVE-2024-3400", "198.51.100.7"],
        "containment_actions": ["Blocked C2 IP at perimeter."],
        "analyst_notes": "Initial analysis grounded in ShadowGraph threat clues."
    })
    assert res.status_code == 200
    data = res.json()
    assert "CERTIN-DRAFT-" in data["report_metadata"]["report_id"]
    assert "6 hours" in data["report_metadata"]["statutory_notice"]
    assert data["incident_details"]["preliminary_severity"] == "HIGH"


def test_graphrag_fallback_when_ollama_offline(client, monkeypatch):
    from app.graphrag.service import OllamaClient
    monkeypatch.setattr(OllamaClient, "check_health", lambda self: {"status": "unavailable", "model_ready": False})
    res = client.post("/api/v1/graphrag/query", json={
        "question": "What indicators are associated with handle pepela?"
    })
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data
    assert data["llm_available"] is False
    assert any("fallback" in lim.lower() for lim in data["limitations"])


def test_clue_detail_not_found(client, mock_repo):
    mock_repo.get_clue.return_value = None
    res = client.get("/api/v1/clues/clue_nonexistent")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_entity_details_not_found(client, mock_repo):
    mock_repo.get_entity_details.return_value = None
    res = client.get("/api/v1/entities/entity_nonexistent")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_export_endpoints(client, mock_neo4j):
    mock_neo4j.read.return_value = [
        {
            "uid": "cve:CVE-2024-3400",
            "type": "cve",
            "value": "CVE-2024-3400",
            "subtype": None,
            "valid": True,
            "post_evidence": ["SYN-POST-001"],
        }
    ]
    # JSON Export
    res_json = client.get("/api/v1/export/indicators/json")
    assert res_json.status_code == 200
    assert len(res_json.json()) == 1
    assert res_json.json()[0]["value"] == "CVE-2024-3400"

    # CSV Export
    res_csv = client.get("/api/v1/export/indicators/csv")
    assert res_csv.status_code == 200
    assert "CVE-2024-3400" in res_csv.text
    assert "indicator_uid,type,value" in res_csv.text

    # STIX 2.1 Export
    res_stix = client.get("/api/v1/export/stix")
    assert res_stix.status_code == 200
    bundle = res_stix.json()
    assert bundle["type"] == "bundle"
    assert any(obj["type"] == "indicator" for obj in bundle["objects"])


def test_upload_file_exceeds_max_bytes(client):
    large_payload = b"X" * (5 * 1024 * 1024 + 10)
    res = client.post(
        "/api/v1/ingest/upload",
        headers={"X-API-Key": "test-secret-key-12345"},
        files={"file": ("dump.txt", large_payload, "text/plain")},
    )
    assert res.status_code == 413
    assert "maximum upload size" in res.json()["detail"]


def test_upload_file_valid_ingestion(client, mock_repo):
    json_content = b'[{"id": "TEST-POST-1", "author": "threat_actor", "text": "Deploying exploit for CVE-2024-3400 at 198.51.100.55"}]'
    res = client.post(
        "/api/v1/ingest/upload",
        headers={"X-API-Key": "test-secret-key-12345"},
        files={"file": ("test_dump.json", json_content, "application/json")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["accepted"] == 1
    assert data["stored"] is True
    assert mock_repo.store_observation.called


def test_save_clue_cypher_preserves_analyst_status(mock_neo4j):
    from app.graph.repository import GraphRepository
    from app.schemas.clues import ClueResult, ClueStatus
    repo = GraphRepository(mock_neo4j)
    clue = ClueResult(
        clue_id="clue:test1234",
        handle_a="pepela",
        handle_b="Spirigatito",
        score=0.45,
        score_type="heuristic",
        status=ClueStatus.CANDIDATE,
        priority="normal",
        coverage=0.35,
        signals={},
        evidence_ids=["SYN-POST-001"],
        explanation=["Test explanation"],
        contradictions=[],
        limitations=[],
        scoring_method_version="1.0.0",
        weights={"technical_artifact_overlap": 0.65},
    )

    repo.save_clue(clue)
    assert mock_neo4j.write.called
    cypher_sent = mock_neo4j.write.call_args[0][0]
    assert "ON MATCH SET r.status = CASE WHEN r.status IN ['supported', 'rejected', 'under_review'] THEN r.status ELSE $status END" in cypher_sent


