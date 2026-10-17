"""Pydantic schemas for candidate identity clues."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ClueStatus(str, Enum):
    CANDIDATE = "candidate"
    UNDER_REVIEW = "under_review"
    SUPPORTED = "supported"
    REJECTED = "rejected"


class SignalResult(BaseModel):
    name: str
    weight: float = Field(ge=0, le=1)
    value: float | None = Field(default=None, ge=0, le=1)
    status: Literal["available", "missing"]
    contribution: float = Field(ge=0, le=1)
    reliability: Literal["normal", "low"] = "normal"
    method: str
    details: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


class ClueResult(BaseModel):
    clue_id: str
    handle_a: str
    handle_b: str
    score: float = Field(ge=0, le=1)
    score_type: Literal["heuristic"] = "heuristic"
    status: ClueStatus = ClueStatus.CANDIDATE
    priority: Literal["high", "normal"] = "normal"
    coverage: float = Field(ge=0, le=1, description="Share of total weight backed by available signals")
    signals: dict[str, SignalResult]
    evidence_ids: list[str]
    explanation: list[str]
    contradictions: list[str]
    limitations: list[str]
    scoring_method_version: str
    weights: dict[str, float]


class ClueRecord(ClueResult):
    """A clue as stored in the graph, including review metadata."""

    created_at: datetime | None = None
    updated_at: datetime | None = None
    reviewed_at: datetime | None = None
    reviewer: str | None = None
    review_notes: str | None = None


class ReviewRequest(BaseModel):
    status: ClueStatus
    reviewer: str = Field(min_length=1, max_length=64)
    notes: str = Field(default="", max_length=4000)

    @field_validator("status")
    @classmethod
    def _reviewable(cls, v: ClueStatus) -> ClueStatus:
        if v == ClueStatus.CANDIDATE:
            raise ValueError("a review must set under_review, supported or rejected")
        return v


class AuditEvent(BaseModel):
    event_id: str
    action: str
    target_id: str
    actor: str
    timestamp: datetime
    details: dict = Field(default_factory=dict)
