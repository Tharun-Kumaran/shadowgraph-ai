"""Schema initialisation from the versioned files in ``database/``."""

from __future__ import annotations

import os
import re
from pathlib import Path

from app.graph.client import Neo4jClient

SCHEMA_FILES = ("constraints.cypher", "indexes.cypher")
_ALLOWED = re.compile(r"^CREATE (CONSTRAINT|INDEX|FULLTEXT INDEX) [a-z_]+ IF NOT EXISTS ", re.IGNORECASE)


def schema_dir() -> Path:
    env = os.environ.get("SHADOWGRAPH_SCHEMA_DIR")
    if env and Path(env).exists():
        return Path(env)
    # 1. Project root /database (when running from repo workspace)
    candidate_root = Path(__file__).resolve().parents[3] / "database"
    if candidate_root.exists():
        return candidate_root
    # 2. Local backend /database
    candidate_backend = Path(__file__).resolve().parents[2] / "database"
    if candidate_backend.exists():
        return candidate_backend
    # 3. Container filesystem /database
    if Path("/database").exists():
        return Path("/database")
    return candidate_root



def load_statements(directory: Path | None = None) -> list[str]:
    directory = directory or schema_dir()
    statements: list[str] = []
    for name in SCHEMA_FILES:
        text = (directory / name).read_text(encoding="utf-8")
        body = "\n".join(line for line in text.splitlines() if not line.strip().startswith("//"))
        for stmt in body.split(";"):
            stmt = " ".join(stmt.split())
            if not stmt:
                continue
            if not _ALLOWED.match(stmt):
                raise ValueError(f"schema file contains a non-schema statement: {stmt[:60]}")
            statements.append(stmt)
    return statements


def init_schema(client: Neo4jClient, directory: Path | None = None) -> int:
    statements = load_statements(directory)
    for stmt in statements:
        client.write(stmt)
    return len(statements)
