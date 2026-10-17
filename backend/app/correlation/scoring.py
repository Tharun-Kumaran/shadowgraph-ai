"""Identity-resolution scoring (refactored ``compute_same_as_clue``).

The weighted formula from the PoC is kept as a configurable *experimental
baseline*:

    score = 0.65*artifact + 0.15*stylometry + 0.08*lexical
          + 0.07*graph_neighbourhood + 0.05*temporal

Missing signals contribute 0 (conservative) and are reported separately via
``coverage`` and ``status="missing"`` — they are never treated as a genuine
zero similarity in explanations. The score is a heuristic ranking value,
NOT a probability: no calibration against labelled data has been performed.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.correlation import similarity as sim
from app.models.entities import ARTIFACT_SPECIFICITY, CONTEXT_TYPES, EntityType
from app.schemas.clues import ClueResult, ClueStatus, SignalResult

SCORING_METHOD_VERSION = "1.0.0"

DEFAULT_WEIGHTS: dict[str, float] = {
    "technical_artifact_overlap": 0.65,
    "stylometry_similarity": 0.15,
    "lexical_similarity": 0.08,
    "graph_neighborhood_overlap": 0.07,
    "temporal_similarity": 0.05,
}

BASE_LIMITATIONS = [
    "Heuristic score for ranking analyst attention; it is not a calibrated probability.",
    "Shared technical artifacts can be sold, leaked, copied or deliberately planted; they indicate shared artifact use, not shared identity.",
    "No real-world identity is inferred; handles are pseudonymous accounts.",
]


@dataclass
class PostSummary:
    post_id: str
    content_hash: str
    observed_at: datetime | None
    text_length: int = 0


@dataclass
class EntityRef:
    uid: str
    type: EntityType
    value: str
    valid: bool = True
    post_ids: set[str] = field(default_factory=set)


@dataclass
class HandleProfile:
    handle: str
    posts: list[PostSummary] = field(default_factory=list)
    entities: dict[str, EntityRef] = field(default_factory=dict)
    # Aggregated style/semantic embedding; None when unavailable.
    embedding: list[float] | None = None
    embedding_post_ids: list[str] = field(default_factory=list)
    embedding_note: str = ""

    def artifacts(self) -> dict[str, EntityRef]:
        return {u: e for u, e in self.entities.items() if e.type in ARTIFACT_SPECIFICITY and e.valid}

    def context(self) -> dict[str, EntityRef]:
        return {u: e for u, e in self.entities.items() if e.type in CONTEXT_TYPES and e.valid}


@dataclass
class ScoringConfig:
    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    candidate_threshold: float = 0.30
    high_priority_threshold: float = 0.70
    min_posts_temporal: int = 2
    version: str = SCORING_METHOD_VERSION

    def __post_init__(self) -> None:
        if set(self.weights) != set(DEFAULT_WEIGHTS):
            raise ValueError(f"weights must define exactly {sorted(DEFAULT_WEIGHTS)}")
        if any(w < 0 for w in self.weights.values()):
            raise ValueError("weights must be non-negative")
        if abs(sum(self.weights.values()) - 1.0) > 1e-6:
            raise ValueError("weights must sum to 1.0")
        for t in (self.candidate_threshold, self.high_priority_threshold):
            if not 0 <= t <= 1:
                raise ValueError("thresholds must be within [0,1]")


def clue_id_for(a: str, b: str) -> str:
    x, y = sorted([a.casefold(), b.casefold()])
    return "clue:" + hashlib.sha256(f"{x}|{y}".encode()).hexdigest()[:16]


def _clip(x: float) -> float:
    return max(0.0, min(1.0, x))


def _signal(name: str, cfg: ScoringConfig, value: float | None, method: str, details: str,
            evidence: list[str] | None = None, reliability: str = "normal") -> SignalResult:
    w = cfg.weights[name]
    if value is None:
        return SignalResult(name=name, weight=w, value=None, status="missing", contribution=0.0,
                            method=method, details=details, evidence_ids=sorted(set(evidence or [])))
    v = _clip(value)
    return SignalResult(name=name, weight=w, value=round(v, 4), status="available",
                        contribution=round(w * v, 4), reliability=reliability, method=method,
                        details=details, evidence_ids=sorted(set(evidence or [])))


def _artifact_signal(a: HandleProfile, b: HandleProfile, cfg: ScoringConfig, copied_posts: set[str]):
    art_a, art_b = a.artifacts(), b.artifacts()
    name = "technical_artifact_overlap"
    if not art_a or not art_b:
        who = [p.handle for p, s in ((a, art_a), (b, art_b)) if not s]
        return _signal(name, cfg, None, "noisy_or_specificity",
                       f"No validated technical artifacts observed for: {', '.join(who)}"), []
    shared = sorted(set(art_a) & set(art_b))
    if not shared:
        return _signal(name, cfg, 0.0, "noisy_or_specificity",
                       f"{len(art_a)} and {len(art_b)} artifacts observed; none shared"), []
    prod = 1.0
    evidence: list[str] = []
    for uid in shared:
        prod *= 1.0 - ARTIFACT_SPECIFICITY[art_a[uid].type]
        evidence.append(uid)
        evidence.extend(art_a[uid].post_ids | art_b[uid].post_ids)
    only_copied = all((art_a[u].post_ids | art_b[u].post_ids) <= copied_posts for u in shared)
    detail = "Shared: " + ", ".join(f"{art_a[u].type.value}={art_a[u].value}" for u in shared)
    return _signal(name, cfg, 1.0 - prod, "noisy_or_specificity", detail, evidence,
                   "low" if only_copied else "normal"), shared


def _style_signal(a: HandleProfile, b: HandleProfile, cfg: ScoringConfig):
    name = "stylometry_similarity"
    if a.embedding is None or b.embedding is None:
        notes = "; ".join(n for n in (a.embedding_note, b.embedding_note) if n) or "embeddings unavailable"
        return _signal(name, cfg, None, "embedding_cosine", f"Stylometry disabled: {notes}")
    try:
        cos = sim.cosine_similarity(a.embedding, b.embedding)
    except ValueError as exc:
        return _signal(name, cfg, None, "embedding_cosine", f"Stylometry disabled: {exc}")
    if cos is None:
        return _signal(name, cfg, None, "embedding_cosine", "Stylometry disabled: zero or empty embedding")
    return _signal(name, cfg, max(0.0, cos), "embedding_cosine", f"cosine={cos:.3f} over mean post embeddings",
                   a.embedding_post_ids + b.embedding_post_ids)


def _lexical_signal(a: HandleProfile, b: HandleProfile, cfg: ScoringConfig):
    value, method = sim.handle_similarity(a.handle, b.handle)
    return _signal("lexical_similarity", cfg, value, method, f"'{a.handle}' vs '{b.handle}' = {value:.3f}",
                   [f"handle:{a.handle.casefold()}", f"handle:{b.handle.casefold()}"])


def _graph_signal(a: HandleProfile, b: HandleProfile, cfg: ScoringConfig):
    ca, cb = a.context(), b.context()
    j = sim.jaccard(set(ca), set(cb))
    name = "graph_neighborhood_overlap"
    if j is None:
        return _signal(name, cfg, None, "jaccard_context_entities", "No contextual entities (CVE/malware/org/product) for either handle")
    shared = sorted(set(ca) & set(cb))
    evidence = list(shared)
    for u in shared:
        evidence.extend(ca[u].post_ids | cb[u].post_ids)
    return _signal(name, cfg, j, "jaccard_context_entities",
                   f"{len(shared)} shared of {len(set(ca) | set(cb))} contextual entities"
                   + (f": {', '.join(ca[u].value for u in shared)}" if shared else ""), evidence)


def _temporal_signal(a: HandleProfile, b: HandleProfile, cfg: ScoringConfig):
    name = "temporal_similarity"

    def hours(p: HandleProfile) -> list[float]:
        out = []
        for post in p.posts:
            if post.observed_at is not None:
                ts = post.observed_at if post.observed_at.tzinfo else post.observed_at.replace(tzinfo=timezone.utc)
                ts = ts.astimezone(timezone.utc)
                out.append(ts.hour + ts.minute / 60.0)
        return out

    ha, hb = hours(a), hours(b)
    if len(ha) < cfg.min_posts_temporal or len(hb) < cfg.min_posts_temporal:
        return _signal(name, cfg, None, "circular_mean_utc_hour",
                       f"Need >= {cfg.min_posts_temporal} timestamped posts per handle (have {len(ha)} and {len(hb)})")
    (ma, ra), (mb, rb) = sim.circular_mean_hour(ha), sim.circular_mean_hour(hb)
    diff = sim.circular_hour_difference(ma, mb)
    reliability = "low" if min(ra, rb) < 0.5 else "normal"
    detail = f"mean UTC hours {ma:.1f} vs {mb:.1f}; circular difference {diff:.1f}h"
    if reliability == "low":
        detail += " (activity widely spread; low reliability)"
    evidence = [p.post_id for p in a.posts + b.posts if p.observed_at is not None]
    return _signal(name, cfg, 1.0 - diff / 12.0, "circular_mean_utc_hour", detail, evidence, reliability)


def compute_same_as_clue(a: HandleProfile, b: HandleProfile, cfg: ScoringConfig | None = None) -> ClueResult:
    """Score a candidate SAME_AS clue between two handle profiles."""
    cfg = cfg or ScoringConfig()
    if a.handle.casefold() == b.handle.casefold():
        raise ValueError("cannot score a handle against itself")
    if a.handle.casefold() > b.handle.casefold():
        a, b = b, a  # deterministic ordering

    hashes_a = {p.content_hash: p.post_id for p in a.posts}
    copied = {p.post_id for p in b.posts if p.content_hash in hashes_a} | {
        hashes_a[p.content_hash] for p in b.posts if p.content_hash in hashes_a
    }

    art, shared = _artifact_signal(a, b, cfg, copied)
    signals = {
        "technical_artifact_overlap": art,
        "stylometry_similarity": _style_signal(a, b, cfg),
        "lexical_similarity": _lexical_signal(a, b, cfg),
        "graph_neighborhood_overlap": _graph_signal(a, b, cfg),
        "temporal_similarity": _temporal_signal(a, b, cfg),
    }
    score = _clip(sum(s.contribution for s in signals.values()))
    coverage = _clip(sum(s.weight for s in signals.values() if s.status == "available"))

    explanation: list[str] = []
    for s in sorted(signals.values(), key=lambda s: -s.contribution):
        if s.status == "missing":
            explanation.append(f"{s.name}: MISSING — {s.details} (contributes 0; not evidence of dissimilarity)")
        else:
            explanation.append(f"{s.name}: {s.value:.2f} x {s.weight:.2f} = {s.contribution:.3f} — {s.details}")

    contradictions: list[str] = []
    av = {k: s.value for k, s in signals.items() if s.status == "available"}
    art_v, sty_v, lex_v, tmp_v = (av.get(k) for k in (
        "technical_artifact_overlap", "stylometry_similarity", "lexical_similarity", "temporal_similarity"))
    if art_v is not None and art_v >= 0.9:
        if tmp_v is not None and tmp_v < 0.5:
            contradictions.append("Strong shared artifact but clearly different activity hours — consider a shared, sold or leaked artifact, or multiple operators.")
        if sty_v is not None and sty_v < 0.5:
            contradictions.append("Strong shared artifact but low writing/semantic similarity.")
    if lex_v is not None and lex_v >= 0.9 and art_v == 0.0:
        contradictions.append("Very similar handle names but no shared technical artifacts — possible coincidence or impersonation.")
    if sty_v is not None and sty_v >= 0.85 and art_v == 0.0:
        contradictions.append("High text similarity without shared artifacts — templated or copied posts are common.")
    if copied:
        contradictions.append(f"{len(copied)} post(s) have identical content across both handles (possible repost/copy); treat related signals with caution.")

    limitations = list(BASE_LIMITATIONS)
    missing = [k for k, s in signals.items() if s.status == "missing"]
    if missing:
        limitations.append(f"Missing signals ({', '.join(missing)}) lower coverage to {coverage:.2f}; the score is conservative.")
    if any(s.reliability == "low" for s in signals.values()):
        limitations.append("One or more signals are flagged low-reliability.")
    if signals["graph_neighborhood_overlap"].status == "available":
        limitations.append("Common CVE/malware mentions are weak evidence: many unrelated actors discuss the same topics.")

    evidence = sorted({e for s in signals.values() for e in s.evidence_ids})
    return ClueResult(
        clue_id=clue_id_for(a.handle, b.handle),
        handle_a=a.handle,
        handle_b=b.handle,
        score=round(score, 4),
        status=ClueStatus.CANDIDATE,
        priority="high" if score >= cfg.high_priority_threshold else "normal",
        coverage=round(coverage, 4),
        signals=signals,
        evidence_ids=evidence,
        explanation=explanation,
        contradictions=contradictions,
        limitations=limitations,
        scoring_method_version=cfg.version,
        weights=dict(cfg.weights),
    )
