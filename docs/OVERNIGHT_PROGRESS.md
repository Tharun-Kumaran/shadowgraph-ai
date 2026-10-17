# ShadowGraph AI — Overnight Autonomous Execution Log

**Initial Timestamp:** 2026-10-18T02:58:30+05:30  
**Lead Engineer:** AI Assistant  
**Repository:** `/home/tharun/Projects/shadowgraph-ai`  
**Current Branch:** `master` (Baseline Commit `cd512e2`)

---

## 1. Initial Project State

- **Neo4j Database:** Docker container `shadowgraph_neo4j` active. Bolt port `7688`, HTTP port `7475`. Schema constraints applied: 22 indexes/constraints.
- **Backend:** FastAPI application in `backend/app/main.py`. Running on port `8100`.
- **Frontend:** React + TypeScript + Cytoscape + Vite in `frontend/`. Running on port `5173`.
- **Tor Environment:** SOCKS5 proxy reachable at `127.0.0.1:9050` with Tor service active.
- **Ollama / LLM:** Ollama service reachable with `qwen3:1.7b` loaded.
- **Test Baseline:** 82 passing pytest unit/integration tests in `backend/tests/`.
- **Protected Processes:** Process on port `8000` is untouched/unrelated.

---

## 2. Stage-by-Stage Plan & Status

- [x] **Stage A — Baseline & Architectural Inspection:** Checked configuration, routes, dependencies, schemas, and live listeners (Neo4j, Ollama, Tor, Uvicorn, Vite).
- [x] **Stage B — Backend Verification:** Endpoints verified, schema validation, persistence verification, error handling tested, upload size bounds enforced.
- [x] **Stage C — CTI Ingestion & Tor:** SSRF bounds, redirect limits, 100KB payload limit, fail-closed onion transport, Tor live SOCKS5 detection.
- [x] **Stage D — Neo4j & Graph Integrity:** Provenance tracking, graph read-back, scoring honesty, synthetic vs live segregation, analyst review preservation in `save_clue`.
- [x] **Stage E — GraphRAG & Analyst Workflow:** Evidence-grounded queries, review queue persistence, STIX 2.1 & CERT-In export, bounded `num_predict: 512` for CPU LLM responsiveness with deterministic fallback.
- [x] **Stage F — Frontend Excellence:** React build verified (`tsc -b && vite build` passing), Cytoscape interactivity, responsive UI, real Tor & backend status reporting.
- [x] **Stage G — Comprehensive Testing:** Expanded tests for edge cases, 88 passed backend pytest suite.
- [x] **Stage H — Final Review & Verification:** Full diff audit, Dockerfile & docker-compose alignment, security check, restart commands documented.

---

## 3. Execution Log & Milestones

### Milestone 1: Baseline Establishment & Version Control
- Clean baseline git commit created (`cd512e2`) with comprehensive `.gitignore` safeguarding `.env`, secrets, caches, and node_modules.
- Network verification confirmed all core services active:
  - Neo4j Bolt port `7688` / HTTP port `7475` (Docker `shadowgraph_neo4j`)
  - FastAPI backend port `8100`
  - React/Vite frontend port `5173`
  - Tor SOCKS5 proxy port `9050`
  - Ollama local inference port `11434`
  - Protected unrelated port `8000` untouched

### Milestone 2: Graph Persistence & Analyst Review Integrity
- **Identified Risk:** In `backend/app/graph/repository.py`, calling `save_clue` previously unconditionally overwrote `r.status = $status`, which would reset analyst decisions (`supported`, `rejected`, `under_review`) back to `candidate` when new clues were generated.
- **Fix:** Implemented Cypher `ON MATCH SET r.status = CASE WHEN r.status IN ['supported', 'rejected', 'under_review'] THEN r.status ELSE $status END`.
- **Integrity Verified:** Clue `clue:cd36a0607f0bb81a` retains `status: "supported"`, `reviewer: "Lead_CTI_Tharun"`, and notes intact.

### Milestone 3: Ingestion Pipeline & Auto-Correlation
- Added automatic clue recalculation to `POST /api/v1/ingest/upload` so manual file uploads immediately participate in candidate identity correlation without requiring manual seeding.
- Enforced 5MB size limit (`max_upload_bytes`) returning HTTP 413 on oversized payloads.

### Milestone 4: GraphRAG Local LLM Optimization
- Added `num_predict: 512` to Ollama request parameters in `backend/app/graphrag/service.py` to prevent runaway generation on CPU.
- Verified deterministic fallback pipeline operates gracefully if LLM requests exceed timeout or service is offline.

### Milestone 5: Docker & Container Build Alignment
- Corrected `backend/Dockerfile` and `docker-compose.yml` build context:
  - Updated compose build context to root `.` with `backend/Dockerfile` so schema files in `database/` are correctly copied into the container filesystem at `/database`.
  - Added robust directory fallback resolution in `backend/app/graph/schema.py` (`SHADOWGRAPH_SCHEMA_DIR` -> `parents[3]/database` -> `parents[2]/database` -> `/database`).

### Milestone 6: Test Suite Expansion
- Added unit and integration tests in `backend/tests/test_api.py`:
  - `test_clue_detail_not_found` (HTTP 404 verification)
  - `test_entity_details_not_found` (HTTP 404 verification)
  - `test_export_endpoints` (JSON, CSV, and STIX 2.1 bundle structure)
  - `test_upload_file_exceeds_max_bytes` (HTTP 413 verification)
  - `test_upload_file_valid_ingestion` (Observation normalization and persistence)
  - `test_save_clue_cypher_preserves_analyst_status` (Cypher query assertion)
- Total test count expanded from 82 to **88 passed tests**.
- Frontend production build verified: `tsc -b && vite build` built in 626ms with 0 errors.

