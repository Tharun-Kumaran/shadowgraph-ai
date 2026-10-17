"""Deterministic candidate-pair generation (blocking) for identity resolution."""

from __future__ import annotations

from itertools import combinations

from app.correlation.scoring import HandleProfile, ScoringConfig, compute_same_as_clue
from app.correlation.similarity import handle_similarity
from app.schemas.clues import ClueResult

LEXICAL_BLOCKING_THRESHOLD = 0.85


def candidate_pairs(profiles: list[HandleProfile]) -> list[tuple[str, str, list[str]]]:
    """Return sorted (handle_a, handle_b, reasons) pairs worth scoring.

    A pair is considered when the handles share a validated artifact, share a
    contextual entity, or have very similar names. Ordering is deterministic.
    """
    ordered = sorted(profiles, key=lambda p: p.handle.casefold())
    out = []
    for a, b in combinations(ordered, 2):
        reasons = []
        if set(a.artifacts()) & set(b.artifacts()):
            reasons.append("shared_artifact")
        if set(a.context()) & set(b.context()):
            reasons.append("shared_context")
        if handle_similarity(a.handle, b.handle)[0] >= LEXICAL_BLOCKING_THRESHOLD:
            reasons.append("similar_name")
        if reasons:
            out.append((a.handle, b.handle, reasons))
    return out


def generate_clues(profiles: list[HandleProfile], cfg: ScoringConfig | None = None) -> list[ClueResult]:
    cfg = cfg or ScoringConfig()
    by_name = {p.handle: p for p in profiles}
    clues = []
    for ha, hb, _ in candidate_pairs(profiles):
        clue = compute_same_as_clue(by_name[ha], by_name[hb], cfg)
        if clue.score >= cfg.candidate_threshold:
            clues.append(clue)
    return sorted(clues, key=lambda c: (-c.score, c.handle_a.casefold(), c.handle_b.casefold()))
