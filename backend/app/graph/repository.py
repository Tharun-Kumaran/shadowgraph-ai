"""
Graph Repository for Neo4j.
All queries are fully parameterized. User values are never interpolated.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.graph.client import Neo4jClient
from app.models.entities import ENTITY_LABELS, EntityType
from app.schemas.clues import ClueRecord, ClueResult, ClueStatus
from app.schemas.observations import Observation


class GraphRepository:
    def __init__(self, client: Neo4jClient):
        self.client = client

    def store_observation(self, obs: Observation) -> None:
        """
        Store an observation as a Post node, its Source, author Handle (if present),
        and all extracted entities with parameterised relationships.
        """
        statements: List[Tuple[str, Dict[str, Any]]] = []

        # 1. Source node
        source_stmt = (
            "MERGE (s:Source:SGNode {uid: $source_uid}) "
            "ON CREATE SET s.source_id = $source_id, s.name = $source_name, "
            "s.type = $source_type, s.url = $source_url, s.created_at = datetime() "
            "ON MATCH SET s.name = $source_name, s.url = coalesce($source_url, s.url)"
        )
        statements.append((source_stmt, {
            "source_uid": f"source:{obs.source_id}",
            "source_id": obs.source_id,
            "source_name": obs.source_name,
            "source_type": obs.source_type,
            "source_url": obs.source_url,
        }))

        # 2. Post node
        post_stmt = (
            "MERGE (p:Post:SGNode {uid: $uid}) "
            "ON CREATE SET p.post_id = $post_id, p.content_hash = $content_hash, "
            "p.text = $text, p.text_length = $text_length, p.text_retention = $retention, "
            "p.collected_at = datetime($collected_at), "
            "p.observed_at = CASE WHEN $observed_at IS NOT NULL THEN datetime($observed_at) ELSE null END, "
            "p.synthetic = $synthetic, p.author_handle = $author, p.language = $language, "
            "p.status = $status, p.created_at = datetime() "
            "WITH p "
            "MATCH (s:Source:SGNode {uid: $source_uid}) "
            "MERGE (p)-[:OBSERVED_IN]->(s)"
        )
        statements.append((post_stmt, {
            "uid": obs.uid,
            "post_id": obs.observation_id,
            "content_hash": obs.content_hash,
            "text": obs.text,
            "text_length": obs.text_length,
            "retention": obs.text_retention,
            "collected_at": obs.collected_at.isoformat(),
            "observed_at": obs.observed_at.isoformat() if obs.observed_at else None,
            "synthetic": obs.synthetic,
            "author": obs.author_handle,
            "language": obs.language,
            "status": obs.status,
            "source_uid": f"source:{obs.source_id}",
        }))

        # 3. Author Handle node
        if obs.author_handle:
            handle_uid = f"handle:{obs.author_handle.casefold()}"
            handle_stmt = (
                "MERGE (h:Handle:SGNode {uid: $handle_uid}) "
                "ON CREATE SET h.name = $name, h.created_at = datetime() "
                "WITH h "
                "MATCH (p:Post:SGNode {uid: $post_uid}) "
                "MERGE (h)-[:AUTHORED]->(p)"
            )
            statements.append((handle_stmt, {
                "handle_uid": handle_uid,
                "name": obs.author_handle,
                "post_uid": obs.uid,
            }))

        # 4. Extracted entities
        for ent in obs.entities:
            val = ent.get("value")
            raw_type = ent.get("type")
            if not val or not raw_type:
                continue

            try:
                etype = EntityType(raw_type)
            except ValueError:
                continue

            # Labels are looked up from fixed dictionary ONLY
            labels = ENTITY_LABELS.get(etype, ("Indicator",))
            label_str = ":" + ":".join(labels) + ":SGNode"

            # Determine relationship verb
            rel_verb = "REFERENCES" if etype == EntityType.CVE else "MENTIONS"

            ent_stmt = (
                f"MERGE (e{label_str} {{uid: $uid}}) "
                "ON CREATE SET e.value = $value, e.type = $type, e.subtype = $subtype, "
                "e.valid = $valid, e.created_at = datetime() "
                "WITH e "
                "MATCH (p:Post:SGNode {uid: $post_uid}) "
                f"MERGE (p)-[:{rel_verb}]->(e)"
            )
            statements.append((ent_stmt, {
                "uid": ent.get("uid", f"{raw_type}:{val}"),
                "value": val,
                "type": raw_type,
                "subtype": ent.get("subtype"),
                "valid": ent.get("valid", True),
                "post_uid": obs.uid,
            }))

        self.client.write_many(statements)

    def save_clue(self, clue: ClueResult) -> None:
        """
        Store a candidate SAME_AS relationship non-destructively.
        """
        stmt = (
            "MERGE (a:Handle:SGNode {uid: $handle_a_uid}) "
            "ON CREATE SET a.name = $handle_a, a.created_at = datetime() "
            "MERGE (b:Handle:SGNode {uid: $handle_b_uid}) "
            "ON CREATE SET b.name = $handle_b, b.created_at = datetime() "
            "MERGE (a)-[r:SAME_AS {clue_id: $clue_id}]->(b) "
            "ON CREATE SET r.status = $status, r.created_at = datetime() "
            "ON MATCH SET r.status = CASE WHEN r.status IN ['supported', 'rejected', 'under_review'] THEN r.status ELSE $status END "
            "SET r.confidence_score = $score, "
            "r.score_type = $score_type, "
            "r.priority = $priority, "
            "r.coverage = $coverage, "
            "r.signals_json = $signals_json, "
            "r.evidence_ids = $evidence_ids, "
            "r.explanation_json = $explanation_json, "
            "r.contradictions_json = $contradictions_json, "
            "r.limitations_json = $limitations_json, "
            "r.scoring_method_version = $version, "
            "r.updated_at = datetime()"
        )

        params = {
            "handle_a_uid": f"handle:{clue.handle_a.casefold()}",
            "handle_b_uid": f"handle:{clue.handle_b.casefold()}",
            "handle_a": clue.handle_a,
            "handle_b": clue.handle_b,
            "clue_id": clue.clue_id,
            "score": clue.score,
            "score_type": clue.score_type,
            "status": clue.status.value if hasattr(clue.status, "value") else clue.status,
            "priority": clue.priority,
            "coverage": clue.coverage,
            "signals_json": json.dumps({k: v.model_dump() for k, v in clue.signals.items()}),
            "evidence_ids": clue.evidence_ids,
            "explanation_json": json.dumps(clue.explanation),
            "contradictions_json": json.dumps(clue.contradictions),
            "limitations_json": json.dumps(clue.limitations),
            "version": clue.scoring_method_version,
        }
        self.client.write(stmt, params)

    def review_clue(self, clue_id: str, status: ClueStatus, reviewer: str, notes: str) -> Optional[Dict[str, Any]]:
        """
        Update the review status of a candidate relationship and append an audit event.
        """
        stmt = (
            "MATCH ()-[r:SAME_AS {clue_id: $clue_id}]->() "
            "SET r.status = $status, "
            "r.reviewer = $reviewer, "
            "r.review_notes = $notes, "
            "r.reviewed_at = datetime(), "
            "r.updated_at = datetime() "
            "RETURN properties(r) AS props"
        )
        params = {
            "clue_id": clue_id,
            "status": status.value if hasattr(status, "value") else status,
            "reviewer": reviewer,
            "notes": notes,
        }
        res = self.client.write(stmt, params)
        if not res:
            return None

        # Add Audit Event
        audit_stmt = (
            "CREATE (a:AuditEvent:SGNode {uid: $uid}) "
            "SET a.action = 'review_clue', a.target_id = $target_id, "
            "a.actor = $reviewer, a.status = $status, a.notes = $notes, "
            "a.timestamp = datetime()"
        )
        self.client.write(audit_stmt, {
            "uid": f"audit:{clue_id}:{datetime.now(timezone.utc).timestamp()}",
            "target_id": clue_id,
            "reviewer": reviewer,
            "status": status.value if hasattr(status, "value") else status,
            "notes": notes,
        })
        return res[0]["props"]

    @staticmethod
    def _safe_json_loads(val: Any, default: Any) -> Any:
        if not val:
            return default
        if isinstance(val, (dict, list)):
            return val
        try:
            return json.loads(val)
        except Exception:
            return default

    def _format_clue_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        r = row.get("props") or {}
        return {
            "clue_id": r.get("clue_id"),
            "handle_a": row.get("handle_a", ""),
            "handle_b": row.get("handle_b", ""),
            "score": r.get("confidence_score"),
            "score_type": r.get("score_type", "heuristic"),
            "status": r.get("status"),
            "priority": r.get("priority", "normal"),
            "coverage": r.get("coverage", 1.0),
            "signals": self._safe_json_loads(r.get("signals_json"), {}),
            "evidence_ids": r.get("evidence_ids") or [],
            "explanation": self._safe_json_loads(r.get("explanation_json"), []),
            "contradictions": self._safe_json_loads(r.get("contradictions_json"), []),
            "limitations": self._safe_json_loads(r.get("limitations_json"), []),
            "scoring_method_version": r.get("scoring_method_version"),
            "reviewer": r.get("reviewer"),
            "review_notes": r.get("review_notes"),
            "reviewed_at": str(r.get("reviewed_at")) if r.get("reviewed_at") else None,
        }

    def list_clues(self, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        where_clause = "WHERE r.status = $status " if status else ""
        query = (
            f"MATCH (a:Handle)-[r:SAME_AS]->(b:Handle) "
            f"{where_clause}"
            f"RETURN a.name AS handle_a, b.name AS handle_b, properties(r) AS props "
            f"ORDER BY r.confidence_score DESC LIMIT $limit"
        )
        params = {"limit": limit}
        if status:
            params["status"] = status
        rows = self.client.read(query, params)
        return [self._format_clue_row(row) for row in rows]

    def get_clue(self, clue_id: str) -> Optional[Dict[str, Any]]:
        query = (
            "MATCH (a:Handle)-[r:SAME_AS {clue_id: $clue_id}]->(b:Handle) "
            "RETURN a.name AS handle_a, b.name AS handle_b, properties(r) AS props "
            "LIMIT 1"
        )
        rows = self.client.read(query, {"clue_id": clue_id})
        if not rows:
            return None
        return self._format_clue_row(rows[0])

    def get_dashboard_metrics(self) -> Dict[str, Any]:
        """Real metrics queried from Neo4j."""
        query = """
        CALL {
            MATCH (p:Post) RETURN count(p) AS posts
        }
        CALL {
            MATCH (h:Handle) RETURN count(h) AS handles
        }
        CALL {
            MATCH (i:Indicator) RETURN count(i) AS indicators
        }
        CALL {
            MATCH ()-[r:SAME_AS]->() WHERE r.status = 'candidate' RETURN count(r) AS candidate_clues
        }
        CALL {
            MATCH ()-[r:SAME_AS]->() WHERE r.status IN ['supported', 'rejected', 'under_review'] RETURN count(r) AS reviewed_clues
        }
        CALL {
            MATCH (inc:Incident) RETURN count(inc) AS incidents
        }
        RETURN posts, handles, indicators, candidate_clues, reviewed_clues, incidents
        """
        res = self.client.read(query)
        if not res:
            return {
                "observations": 0,
                "handles": 0,
                "indicators": 0,
                "candidate_clues": 0,
                "reviewed_clues": 0,
                "incidents": 0,
            }
        d = res[0]
        return {
            "observations": d.get("posts", 0),
            "handles": d.get("handles", 0),
            "indicators": d.get("indicators", 0),
            "candidate_clues": d.get("candidate_clues", 0),
            "reviewed_clues": d.get("reviewed_clues", 0),
            "incidents": d.get("incidents", 0),
        }

    def get_graph_elements(
        self,
        entity_types: Optional[List[str]] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 150,
    ) -> Dict[str, Any]:
        """
        Query nodes and relationships formatted directly for Cytoscape.js.
        """
        # Node query
        node_query = (
            "MATCH (n:SGNode) "
            "WHERE NOT n:AuditEvent "
            + ("AND n.type IN $entity_types " if entity_types else "")
            + ("AND (toLower(n.value) CONTAINS toLower($search) OR toLower(n.name) CONTAINS toLower($search)) " if search else "")
            + "RETURN n LIMIT $limit"
        )
        params: Dict[str, Any] = {"limit": limit}
        if entity_types:
            params["entity_types"] = entity_types
        if search:
            params["search"] = search

        node_rows = self.client.read(node_query, params)
        nodes = []
        node_uids = set()

        for row in node_rows:
            n = row["n"]
            uid = n.get("uid")
            if not uid or uid in node_uids:
                continue
            node_uids.add(uid)

            # Determine type and label
            label = n.get("name") or n.get("value") or n.get("post_id") or uid
            node_type = n.get("type") or ("post" if "Post" in str(n) else "handle" if "Handle" in str(n) else "node")

            nodes.append({
                "data": {
                    "id": uid,
                    "label": label[:30],
                    "full_label": label,
                    "type": node_type,
                    "properties": n,
                }
            })

        # Relationships between retrieved nodes
        edges = []
        if node_uids:
            rel_query = (
                "MATCH (a:SGNode)-[r]->(b:SGNode) "
                "WHERE a.uid IN $uids AND b.uid IN $uids "
                + ("AND (type(r) <> 'SAME_AS' OR r.status = $status) " if status else "")
                + "RETURN a.uid AS source, b.uid AS target, type(r) AS type, properties(r) AS props LIMIT 300"
            )
            rel_params = {"uids": list(node_uids)}
            if status:
                rel_params["status"] = status
            rel_rows = self.client.read(rel_query, rel_params)

            for i, r in enumerate(rel_rows):
                edges.append({
                    "data": {
                        "id": f"edge_{i}_{r['source']}_{r['target']}",
                        "source": r["source"],
                        "target": r["target"],
                        "label": r["type"],
                        "properties": r["props"],
                    }
                })

        return {"nodes": nodes, "edges": edges}

    def get_entity_details(self, uid: str) -> Optional[Dict[str, Any]]:
        """Return comprehensive entity properties, provenance, and 1-hop connections."""
        node_stmt = "MATCH (n:SGNode {uid: $uid}) RETURN n"
        rows = self.client.read(node_stmt, {"uid": uid})
        if not rows:
            return None
        node = rows[0]["n"]

        rels_stmt = (
            "MATCH (n:SGNode {uid: $uid})-[r]-(other:SGNode) "
            "RETURN type(r) AS rel_type, startNode(r).uid = n.uid AS is_outgoing, "
            "properties(r) AS rel_props, other.uid AS other_uid, "
            "coalesce(other.name, other.value, other.post_id) AS other_label, "
            "labels(other) AS other_labels LIMIT 100"
        )
        rel_rows = self.client.read(rels_stmt, {"uid": uid})
        return {
            "entity": node,
            "connections": rel_rows,
        }
