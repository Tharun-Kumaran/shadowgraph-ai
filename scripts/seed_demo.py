#!/usr/bin/env python3
"""
Seed script for ShadowGraph AI synthetic demo dataset.
Idempotent: safe to run multiple times without creating duplicates.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.config import get_settings
from app.graph.client import Neo4jClient
from app.graph.repository import GraphRepository
from app.graph.schema import init_schema
from app.ingestion.normalizer import normalize_record
from app.correlation.scoring import HandleProfile, PostSummary, EntityRef, compute_same_as_clue
from app.models.entities import EntityType


def seed():
    settings = get_settings()
    client = Neo4jClient(settings)

    print("Checking Neo4j connectivity...")
    health = client.health()
    if health.get("status") != "ok":
        print(f"Error: Neo4j is not accessible ({health.get('detail')}).")
        print(f"Target URI: {settings.neo4j_uri}")
        print("Please ensure Neo4j container is running.")
        sys.exit(1)

    print("Initializing schema constraints and indexes...")
    applied = init_schema(client)
    print(f"Verified/applied {applied} schema statements.")

    repo = GraphRepository(client)
    data_path = Path(__file__).resolve().parents[1] / "data" / "synthetic" / "demo_posts.json"
    records = json.loads(data_path.read_text(encoding="utf-8"))

    print(f"Loading {len(records)} synthetic observations...")
    profiles: dict[str, HandleProfile] = {}

    for r in records:
        obs = normalize_record(
            r,
            default_source="synthetic_seed",
            default_source_type="synthetic",
            max_text_chars=20000,
            force_synthetic=True,
        )
        repo.store_observation(obs)

        if obs.author_handle:
            h = obs.author_handle
            if h not in profiles:
                profiles[h] = HandleProfile(handle=h)
            profiles[h].posts.append(
                PostSummary(
                    post_id=obs.observation_id,
                    content_hash=obs.content_hash,
                    observed_at=obs.observed_at,
                    text_length=obs.text_length,
                )
            )
            for ent in obs.entities:
                raw_type = ent.get("type")
                try:
                    etype = EntityType(raw_type)
                except ValueError:
                    continue
                uid = ent["uid"]
                if uid not in profiles[h].entities:
                    profiles[h].entities[uid] = EntityRef(
                        uid=uid,
                        type=etype,
                        value=ent["value"],
                        valid=ent.get("valid", True),
                    )
                profiles[h].entities[uid].post_ids.add(obs.observation_id)

    print("Generating candidate identity clues (pepela vs Spirigatito)...")
    if "pepela" in profiles and "Spirigatito" in profiles:
        # Synthetic mock style vectors for offline demonstration
        profiles["pepela"].embedding = [0.12, 0.80, 0.33, 0.05, 0.41]
        profiles["pepela"].embedding_note = "Synthetic offline demonstration vector"
        profiles["Spirigatito"].embedding = [0.10, 0.78, 0.30, 0.09, 0.44]
        profiles["Spirigatito"].embedding_note = "Synthetic offline demonstration vector"

        clue = compute_same_as_clue(profiles["pepela"], profiles["Spirigatito"])
        repo.save_clue(clue)
        print(f"Generated candidate clue '{clue.clue_id}' between {clue.handle_a} and {clue.handle_b} (Score: {clue.score})")

    metrics = repo.get_dashboard_metrics()
    print("\n=== Seeding Complete ===")
    print(f"Observations:     {metrics['observations']}")
    print(f"Handles:          {metrics['handles']}")
    print(f"Indicators:       {metrics['indicators']}")
    print(f"Candidate Clues:  {metrics['candidate_clues']}")


if __name__ == "__main__":
    seed()
