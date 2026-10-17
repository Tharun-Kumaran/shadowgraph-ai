# SHADOWGRAPH AI

> **Connect the clues. Map the network. Investigate with confidence.**

---

### Author & Hackathon Submission
- **Author:** Tharun Kumaran
- **Event:** CyberForge Hackathon 2026
- **Category:** Cyber Threat Intelligence, Graph Analytics, Local AI, Defensive Security

---

## 1. Overview & Architecture

ShadowGraph AI is a self-hosted Cyber Threat Intelligence (CTI) investigation platform designed to correlate fragmented underground observations, identify probabilistic candidate relationships between pseudonymous threat actors, explain supporting evidence, and prepare structured incident response drafts.

```text
       Raw Threat Telemetry (JSON / CSV / STIX / Plaintext)
                             |
                             v
              +-------------------------------+
              |   Regex & Gazetteer Pipeline  | (Refang, Normalization,
              +-------------------------------+  De-duplication, Validation)
                             |
                             v
              +-------------------------------+
              |    Neo4j Knowledge Graph      | (Parameterised Cypher,
              +-------------------------------+  Constraints, Stable UIDs)
                             |
              +--------------+---------------+
              |                              |
              v                              v
+---------------------------+  +---------------------------+
| Heuristic Clue Engine     |  | Grounded GraphRAG Layer   |
| (Artifact, Style, Lexical,|  | (Local Ollama /           |
|  Graph, Temporal Signals) |  |  Deterministic Fallback)  |
+---------------------------+  +---------------------------+
              |                              |
              +--------------+---------------+
                             |
                             v
        +-----------------------------------------+
        | Interactive Dark SOC Dashboard          |
        | - Cytoscape.js Knowledge Graph Explorer |
        | - Analyst Attribution Review Queue      |
        | - Local AI Evidence Chat                |
        | - SIEM Export (JSON/CSV/STIX) & CERT-In |
        +-----------------------------------------+
```

---

## 2. Implemented Features Status

| Feature Family | Implemented Status | Details |
|---|---|---|
| **PoC Preservation** | **Completed** | Reconstructed PoC preserved in `legacy/shadowgraph_poc.py` keeping 5 experimental weights (0.65, 0.15, 0.08, 0.07, 0.05). |
| **Entity Extraction** | **Completed** | CVE, EVM wallet, Bitcoin (Base58/Bech32), Tox ID checksum, UUID, PGP, Hashes (MD5/SHA1/SHA256), Domains, IPs, and Gazetteer. |
| **Graph Database** | **Completed** | Neo4j 5.x integration with strict parameterised queries, constraints, indexes, and provenance tracking. |
| **Candidate Clues** | **Completed** | Non-destructive `SAME_AS` edges, noisy-OR specificity, circular UTC temporal distance, and contradiction detection. |
| **Interactive SOC UI**| **Completed** | React 18, TypeScript, Vite, Cytoscape.js interactive graph, dark cyan/navy aesthetic, and clue review queue. |
| **Local AI & GraphRAG**| **Completed** | Ollama integration (`qwen3`) with citations, read-only query templates, and a deterministic database fallback. |
| **SIEM & Incident Export**| **Completed** | Structured JSON, CSV, STIX 2.1 bundle export, and CERT-In Section 70B 6-hour draft generator. |
| **Automated Testing** | **Completed** | 71 automated unit and integration tests passing (`pytest`). |

---

## 3. Quickstart & Local Setup

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm
- Docker and Docker Compose

### 1. Database (Neo4j)
Start the isolated Neo4j container (configured to avoid port conflicts with existing services):
```bash
docker compose up -d neo4j
```
- Neo4j HTTP Browser: `http://localhost:7475`
- Neo4j Bolt: `bolt://localhost:7688` (Default user: `neo4j`, password: `shadowgraph_secret_password`)

### 2. Backend Setup
```bash
# Set up virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# Run migrations/schema and seed synthetic demonstration dataset
python scripts/seed_demo.py

# Start FastAPI backend
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8100 --reload
```
API Documentation will be accessible at: `http://localhost:8100/docs`

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev -- --port 5173
```
Open your browser at: `http://localhost:5173`

---

## 4. Synthetic Demonstration Dataset

The project contains a synthetic dataset in `data/synthetic/demo_posts.json` modeling fictional underground accounts:
- **`pepela`**: Selling access to fictional vulnerability exploits (`CVE-2024-3400`) and listing a Tox ID.
- **`Spirigatito`**: Distributing a loader build sharing the exact same Tox ID and targeting the same CVE.

Running `python scripts/seed_demo.py` automatically correlates the profiles and creates a candidate identity clue for analyst review.

---

## 5. Security & Statutory Disclaimers

### Attribution Limitation
A high similarity score or matching technical artifact indicates **shared artifact use**, not definitive proof of shared personal identity. In underground ecosystems, tools, credentials, and accounts are routinely sold, shared, leaked, or planted. All `SAME_AS` edges are stored as candidate hypotheses and require manual human intelligence review.

### CERT-In Statutory Notice
Under the directions issued by CERT-In under Sub-section (6) of Section 70B of the Information Technology Act, 2000, designated cybersecurity incidents must be reported to CERT-In within **6 hours** of noticing or being informed. ShadowGraph AI drafts preliminary reports for authorized incident response teams; it does not automatically submit unverified external reports.
