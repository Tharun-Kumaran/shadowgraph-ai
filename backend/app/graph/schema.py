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
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3] / "database"


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
