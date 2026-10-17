"""Application configuration loaded from environment variables / .env.

Secrets (Neo4j password, API key) are typed as ``SecretStr`` so they are
never rendered in logs, reprs or API responses.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_VERSION = "0.1.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SHADOWGRAPH_",
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application -----------------------------------------------------
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8180"]
    )
    # Required for every state-changing request (header: X-API-Key).
    api_key: SecretStr = SecretStr("")

    # --- Neo4j -----------------------------------------------------------
    neo4j_uri: str = "bolt://localhost:7688"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr = SecretStr("")
    neo4j_database: str = "neo4j"
    neo4j_query_timeout_s: float = 15.0
    neo4j_connect_timeout_s: float = 5.0

    # --- Ingestion -------------------------------------------------------
    max_upload_bytes: int = 5 * 1024 * 1024
    max_records_per_upload: int = 5000
    max_text_chars: int = 20000
    # full | truncated | hash_only
    text_retention: Literal["full", "truncated", "hash_only"] = "full"
    truncated_retention_chars: int = 500

    # Allow-listed HTTP feeds as "feed_id=https://url" entries.
    feeds: list[str] = Field(default_factory=list)
    feed_timeout_s: float = 15.0

    # --- Optional Tor collector -----------------------------------------
    tor_enabled: bool = False
    tor_proxy: str = "socks5h://127.0.0.1:9050"

    # --- Identity scoring -----------------------------------------------
    clue_candidate_threshold: float = 0.30
    clue_high_priority_threshold: float = 0.70

    # --- Embeddings (BGE-M3) --------------------------------------------
    # disabled | ollama | sentence_transformers
    embedding_provider: Literal["disabled", "ollama", "sentence_transformers"] = "disabled"
    embedding_model: str = "bge-m3"
    embedding_model_path: str = ""
    embedding_dimensions: int = 1024
    embedding_cache_path: str = "data/cache/embeddings.sqlite3"

    # --- LLM (Ollama) ----------------------------------------------------
    llm_enabled: bool = True
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:1.7b"
    ollama_timeout_s: float = 120.0
    graphrag_max_evidence: int = 25

    # --- CERT-In reporting ----------------------------------------------
    certin_reporting_window_hours: int = 6

    @field_validator("clue_candidate_threshold", "clue_high_priority_threshold")
    @classmethod
    def _unit_interval(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("thresholds must be within [0, 1]")
        return v

    def feed_map(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for entry in self.feeds:
            if "=" in entry:
                key, url = entry.split("=", 1)
                out[key.strip()] = url.strip()
        return out


@lru_cache
def get_settings() -> Settings:
    return Settings()
