"""Observation and ingestion-report schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SourceType = Literal["file", "feed", "tor", "synthetic", "stix", "manual"]


class Observation(BaseModel):
    observation_id: str
    source_id: str
    source_name: str
    source_type: SourceType
    source_url: str | None = None
    collected_at: datetime
    observed_at: datetime | None = None
    author_handle: str | None = None
    text: str | None = Field(default=None, description="Retained text per the retention policy")
    text_retention: Literal["full", "truncated", "hash_only"] = "full"
    text_length: int = 0
    content_hash: str
    language: str | None = None
    synthetic: bool = False
    entities: list[dict] = Field(default_factory=list)
    status: Literal["extracted", "error"] = "extracted"
    errors: list[str] = Field(default_factory=list)

    @property
    def uid(self) -> str:
        return f"post:{self.observation_id}"


class RejectedRecord(BaseModel):
    index: int
    reason: str


class IngestReport(BaseModel):
    batch_id: str
    filename: str | None
    format: str
    total_records: int
    accepted: int
    duplicates_in_batch: int
    duplicates_existing: int
    rejected: list[RejectedRecord]
    warnings: list[str] = Field(default_factory=list)
    extraction_summary: dict[str, int]
    observation_ids: list[str]
    stored: bool
