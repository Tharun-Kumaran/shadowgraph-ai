"""
Export Service for SIEM (JSON, CSV, STIX 2.1) and CERT-In Incident Reports.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any, Dict, List
import uuid

from app.graph.client import Neo4jClient


class ExportService:
    def __init__(self, neo4j: Neo4jClient):
        self.neo4j = neo4j

    def export_indicators_json(self) -> List[Dict[str, Any]]:
        """Export normalized indicators with provenance and evidence IDs."""
        query = (
            "MATCH (i:Indicator) "
            "OPTIONAL MATCH (p:Post)-[:MENTIONS]->(i) "
            "RETURN i.uid AS uid, i.type AS type, i.value AS value, i.subtype AS subtype, "
            "i.valid AS valid, collect(DISTINCT p.post_id) AS post_evidence "
            "ORDER BY i.type, i.value"
        )
        rows = self.neo4j.read(query)
        indicators = []
        for r in rows:
            indicators.append({
                "uid": r["uid"],
                "type": r["type"],
                "value": r["value"],
                "subtype": r["subtype"],
                "valid": r["valid"],
                "evidence_posts": r["post_evidence"],
                "export_timestamp": datetime.now(timezone.utc).isoformat(),
            })
        return indicators

    def export_indicators_csv(self) -> str:
        """Export CSV format suitable for SIEM/EDR blocklists."""
        indicators = self.export_indicators_json()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["indicator_uid", "type", "value", "subtype", "valid", "evidence_posts", "exported_at"])
        for ind in indicators:
            writer.writerow([
                ind["uid"],
                ind["type"],
                ind["value"],
                ind["subtype"] or "",
                ind["valid"],
                ";".join(ind["evidence_posts"]),
                ind["export_timestamp"],
            ])
        return output.getvalue()

    def export_stix21_bundle(self) -> Dict[str, Any]:
        """Export indicators and malware references formatted as a STIX 2.1 bundle."""
        indicators = self.export_indicators_json()
        stix_objects = []

        # Identity representing ShadowGraph AI
        identity_id = f"identity--{uuid.uuid5(uuid.NAMESPACE_DNS, 'shadowgraph.ai')}"
        stix_objects.append({
            "type": "identity",
            "spec_version": "2.1",
            "id": identity_id,
            "created": datetime.now(timezone.utc).isoformat(),
            "modified": datetime.now(timezone.utc).isoformat(),
            "name": "ShadowGraph AI CTI Platform",
            "identity_class": "system",
        })

        for ind in indicators:
            stix_id = f"indicator--{uuid.uuid5(uuid.NAMESPACE_DNS, ind['uid'])}"
            stix_objects.append({
                "type": "indicator",
                "spec_version": "2.1",
                "id": stix_id,
                "created": datetime.now(timezone.utc).isoformat(),
                "modified": datetime.now(timezone.utc).isoformat(),
                "name": f"{ind['type']}: {ind['value']}",
                "description": f"Extracted by ShadowGraph AI from observations: {ind['evidence_posts']}",
                "pattern": f"[{ind['type']}:value = '{ind['value']}']",
                "pattern_type": "stix",
                "valid_from": datetime.now(timezone.utc).isoformat(),
                "created_by_ref": identity_id,
            })

        return {
            "type": "bundle",
            "id": f"bundle--{uuid.uuid4()}",
            "objects": stix_objects,
        }

    def generate_certin_report(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare structured CERT-In compliant preliminary incident draft.
        Includes Section 70B advisory and draft limitations notice.
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        return {
            "report_metadata": {
                "report_id": f"CERTIN-DRAFT-{uuid.uuid4().hex[:8].upper()}",
                "generated_at": now_utc,
                "status": "DRAFT - ANALYST APPROVAL REQUIRED",
                "statutory_notice": (
                    "Under CERT-In Directions under Sub-section (6) of Section 70B of the IT Act, 2000, "
                    "cyber security incidents of specified categories are required to be reported to CERT-In "
                    "within 6 hours of noticing or being brought to notice of such incidents. "
                    "This automated draft must be reviewed, verified, and officially submitted by authorized security personnel."
                ),
            },
            "incident_details": {
                "title": incident_data.get("title"),
                "category": incident_data.get("category"),
                "preliminary_severity": incident_data.get("severity"),
                "summary": incident_data.get("summary"),
                "affected_systems_and_locations": incident_data.get("affected_systems", []),
                "detection_timestamp": incident_data.get("detection_timestamp", now_utc),
                "containment_actions_taken": incident_data.get("containment_actions", []),
                "indicators_of_compromise": incident_data.get("indicators", []),
                "supporting_evidence_ids": incident_data.get("evidence_uids", []),
                "analyst_assessment_and_notes": incident_data.get("analyst_notes", ""),
            },
            "disclaimer": (
                "ShadowGraph AI does not guarantee statutory or regulatory compliance. "
                "Candidate identity clues are probabilistic hypotheses and must never be represented as verified attribution without human intelligence corroboration."
            )
        }
