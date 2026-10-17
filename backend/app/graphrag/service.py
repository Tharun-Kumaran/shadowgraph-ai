"""
Ollama client and GraphRAG service.
Ensures application works even if Ollama is offline or model is missing.
Restricted read-only Cypher query templates prevent model injection.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import Settings
from app.core.logging import get_logger
from app.graph.client import Neo4jClient

log = get_logger(__name__)


class OllamaClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model
        self.timeout = settings.ollama_timeout_s

    def check_health(self) -> Dict[str, Any]:
        """Check if Ollama service is reachable and if configured model is pulled."""
        try:
            with httpx.Client(timeout=3.0) as client:
                res = client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    models = [m.get("name") for m in res.json().get("models", [])]
                    has_model = any(self.model in m or m.startswith(self.model.split(":")[0]) for m in models)
                    return {
                        "status": "ok",
                        "available_models": models,
                        "configured_model": self.model,
                        "model_ready": has_model,
                    }
                return {"status": "error", "detail": f"HTTP {res.status_code}"}
        except Exception as exc:
            return {"status": "unavailable", "detail": str(exc)}

    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2},
        }
        if system:
            payload["system"] = system

        with httpx.Client(timeout=self.timeout) as client:
            res = client.post(f"{self.base_url}/api/generate", json=payload)
            if res.status_code != 200:
                raise RuntimeError(f"Ollama returned HTTP {res.status_code}: {res.text}")
            return res.json().get("response", "")


class GraphRAGService:
    def __init__(self, settings: Settings, neo4j_client: Neo4jClient, ollama_client: OllamaClient):
        self.settings = settings
        self.neo4j = neo4j_client
        self.ollama = ollama_client

    def answer_question(self, question: str, focus_uid: Optional[str] = None) -> Dict[str, Any]:
        """
        Grounded GraphRAG pipeline:
        1. Query Neo4j using safe, constrained parameterised patterns.
        2. Synthesize context from graph entities and clues.
        3. Pass strictly to local LLM with citation instructions.
        4. Fallback to deterministic synthesis if LLM is unavailable.
        """
        # Step 1: Evidence retrieval
        evidence = self._retrieve_evidence(question, focus_uid)
        
        limitations = [
            "Answers are synthesized solely from retrieved Neo4j knowledge graph evidence.",
            "Candidate identity relationships are probabilistic hypotheses and not verified proof of identity.",
            "Untrusted text in forum posts is isolated and never treated as execution instructions."
        ]

        ollama_status = self.ollama.check_health()
        if not ollama_status.get("model_ready"):
            # Deterministic fallback when LLM is unavailable
            summary = self._deterministic_summary(question, evidence)
            limitations.append(f"Ollama service or model '{self.ollama.model}' is offline/not loaded; returned deterministic fallback graph summary.")
            return {
                "question": question,
                "answer": summary,
                "evidence_references": evidence,
                "limitations": limitations,
                "llm_available": False,
                "model": "deterministic-fallback",
            }

        # Step 2: Prompt LLM
        system_prompt = (
            "You are ShadowGraph AI, a defensive Cyber Threat Intelligence investigation assistant. "
            "Your answers must be strictly grounded in the provided Evidence JSON. "
            "Distinguish verified indicators from unverified claims and candidate identity clues. "
            "Never assert that two handles are definitely the same person—refer to them as candidate links. "
            "Cite evidence UIDs (e.g., [post:XYZ], [handle:pepela], [cve:CVE-...]) in your answer."
        )

        context_str = json.dumps(evidence, indent=2)
        prompt = (
            f"Question from Analyst: {question}\n\n"
            f"Retrieved Graph Evidence:\n{context_str}\n\n"
            "Please provide a structured, evidence-grounded investigation response citing the relevant evidence IDs."
        )

        try:
            answer = self.ollama.generate(prompt=prompt, system=system_prompt)
            return {
                "question": question,
                "answer": answer,
                "evidence_references": evidence,
                "limitations": limitations,
                "llm_available": True,
                "model": self.ollama.model,
            }
        except Exception as exc:
            log.warning("Ollama generation failed: %s", exc)
            summary = self._deterministic_summary(question, evidence)
            limitations.append(f"LLM generation failed ({type(exc).__name__}); returned deterministic fallback.")
            return {
                "question": question,
                "answer": summary,
                "evidence_references": evidence,
                "limitations": limitations,
                "llm_available": False,
                "model": "deterministic-fallback",
            }

    def _retrieve_evidence(self, question: str, focus_uid: Optional[str]) -> List[Dict[str, Any]]:
        evidence = []
        try:
            if focus_uid:
                stmt = (
                    "MATCH (n:SGNode {uid: $uid})-[r]-(other:SGNode) "
                    "RETURN n.uid AS root_uid, coalesce(n.name, n.value, n.post_id) AS root_name, "
                    "type(r) AS rel, other.uid AS other_uid, coalesce(other.name, other.value, other.post_id) AS other_name, "
                    "properties(r) AS rel_props LIMIT 20"
                )
                rows = self.neo4j.read(stmt, {"uid": focus_uid})
                for r in rows:
                    evidence.append(r)

            # Also query any candidate clues
            clue_stmt = (
                "MATCH (a:Handle)-[r:SAME_AS]->(b:Handle) "
                "RETURN r.clue_id AS clue_id, a.name AS handle_a, b.name AS handle_b, "
                "r.confidence_score AS score, r.status AS status, r.evidence_ids AS evidence_ids "
                "ORDER BY r.confidence_score DESC LIMIT 5"
            )
            clue_rows = self.neo4j.read(clue_stmt)
            for cr in clue_rows:
                evidence.append({"type": "candidate_clue", "data": cr})

        except Exception as exc:
            log.error("Error retrieving evidence from Neo4j: %s", exc)

        return evidence

    def _deterministic_summary(self, question: str, evidence: List[Dict[str, Any]]) -> str:
        if not evidence:
            return "No matching evidence was found in the ShadowGraph knowledge graph for your query."

        clues = [e["data"] for e in evidence if e.get("type") == "candidate_clue"]
        connections = [e for e in evidence if "root_uid" in e]

        lines = ["### ShadowGraph Grounded Retrieval Summary\n"]
        if connections:
            lines.append(f"**Entity Connections ({len(connections)} items):**")
            for c in connections[:10]:
                lines.append(f"- `{c['root_name']}` --[{c['rel']}]--> `{c['other_name']}` (Evidence: {c['other_uid']})")
            lines.append("")

        if clues:
            lines.append(f"**Identified Candidate Identity Clues ({len(clues)} items):**")
            for cl in clues:
                lines.append(
                    f"- Candidate link between **{cl['handle_a']}** and **{cl['handle_b']}** "
                    f"(Score: {cl['score']}, Status: {cl['status']}, Clue ID: `{cl['clue_id']}`)."
                )

        lines.append("\n*Note: Local LLM is currently in fallback mode. The above facts reflect direct database records.*")
        return "\n".join(lines)
