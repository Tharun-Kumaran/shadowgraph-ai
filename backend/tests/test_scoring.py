from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.correlation import similarity as sim
from app.correlation.candidates import candidate_pairs, generate_clues
from app.correlation.scoring import (
    DEFAULT_WEIGHTS,
    EntityRef,
    HandleProfile,
    PostSummary,
    ScoringConfig,
    clue_id_for,
    compute_same_as_clue,
)
from app.models.entities import EntityType

UTC = timezone.utc
TOX = "tox_id:" + "AB" * 38


def post(pid: str, hour: int, h: str | None = None, day: int = 1) -> PostSummary:
    return PostSummary(pid, h or f"hash-{pid}", datetime(2026, 3, day, hour, 0, tzinfo=UTC), 200)


def ent(uid: str, etype: EntityType, *pids: str) -> EntityRef:
    return EntityRef(uid, etype, uid.split(":", 1)[1], True, set(pids))


def profile(name, posts=(), entities=(), embedding=None) -> HandleProfile:
    return HandleProfile(name, list(posts), {e.uid: e for e in entities}, embedding)


# ----------------------------------------------------------- primitives ---
def test_weights_preserved_from_poc():
    assert DEFAULT_WEIGHTS == {
        "technical_artifact_overlap": 0.65,
        "stylometry_similarity": 0.15,
        "lexical_similarity": 0.08,
        "graph_neighborhood_overlap": 0.07,
        "temporal_similarity": 0.05,
    }


def test_cosine_edge_cases():
    assert sim.cosine_similarity([], [1.0]) is None
    assert sim.cosine_similarity([0, 0], [1, 1]) is None
    assert sim.cosine_similarity([1, 2], [2, 4]) == pytest.approx(1.0)
    assert sim.cosine_similarity([1, 0], [-1, 0]) == pytest.approx(-1.0)
    with pytest.raises(ValueError):
        sim.cosine_similarity([1, 2], [1, 2, 3])


def test_lexical_measures():
    assert sim.jaro_winkler("martha", "marhta") == pytest.approx(0.9611, abs=1e-3)
    assert sim.jaro_winkler("abc", "abc") == 1.0
    assert sim.jaro_winkler("abc", "") == 0.0
    assert sim.normalized_levenshtein("kitten", "sitting") == pytest.approx(1 - 3 / 7)
    assert sim.handle_similarity("pepela", "P3p3la_99")[0] == 1.0
    assert sim.handle_similarity("pepela", "Spirigatito")[0] < 0.6


def test_jaccard():
    assert sim.jaccard(set(), set()) is None
    assert sim.jaccard({1}, set()) == 0.0
    assert sim.jaccard({1, 2}, {2, 3}) == pytest.approx(1 / 3)


@pytest.mark.parametrize("a,b,d", [(23, 1, 2), (0, 12, 12), (22.5, 0.5, 2), (5, 5, 0), (1, 23, 2)])
def test_circular_hours_midnight_wraparound(a, b, d):
    assert sim.circular_hour_difference(a, b) == pytest.approx(d)


def test_circular_mean_wraps():
    mean, r = sim.circular_mean_hour([23, 1])
    assert sim.circular_hour_difference(mean, 0) == pytest.approx(0, abs=1e-9)
    assert r > 0.9
    assert sim.circular_mean_hour([]) is None


# -------------------------------------------------------------- scoring ---
def test_exact_artifact_overlap_is_strong_not_certain():
    a = profile("pepela", [post("p1", 23), post("p2", 0)], [ent(TOX, EntityType.TOX_ID, "p1")])
    b = profile("Spirigatito", [post("p3", 1), post("p4", 22)], [ent(TOX, EntityType.TOX_ID, "p3")])
    c = compute_same_as_clue(a, b)
    s = c.signals["technical_artifact_overlap"]
    assert s.value == 1.0 and s.contribution == pytest.approx(0.65)
    assert TOX in c.evidence_ids and "p1" in c.evidence_ids and "p3" in c.evidence_ids
    assert c.score_type == "heuristic" and c.status.value == "candidate"
    assert c.signals["stylometry_similarity"].status == "missing"
    assert c.score < 1.0
    assert any("not a calibrated probability" in lim for lim in c.limitations)


def test_no_artifact_overlap_is_genuine_zero():
    a = profile("alpha", entities=[ent("wallet:0x1", EntityType.WALLET, "p1")])
    b = profile("bravo", entities=[ent("wallet:0x2", EntityType.WALLET, "p2")])
    s = compute_same_as_clue(a, b).signals["technical_artifact_overlap"]
    assert s.status == "available" and s.value == 0.0


def test_missing_artifacts_is_missing_not_zero():
    c = compute_same_as_clue(profile("alpha"), profile("bravo"))
    s = c.signals["technical_artifact_overlap"]
    assert s.status == "missing" and s.value is None
    assert any("MISSING" in e for e in c.explanation)
    assert c.coverage == pytest.approx(0.08)  # only lexical is available


def test_multiple_medium_artifacts_noisy_or_bounded():
    shared = [ent("domain:a.com", EntityType.DOMAIN, "p1"), ent("ip_address:8.8.8.8", EntityType.IP_ADDRESS, "p1")]
    c = compute_same_as_clue(profile("a1", entities=shared), profile("b1", entities=shared))
    v = c.signals["technical_artifact_overlap"].value
    assert v == pytest.approx(1 - (1 - 0.35) * (1 - 0.3), abs=1e-4)
    assert 0 <= c.score <= 1


def test_embedding_cases():
    a = profile("aaa", embedding=[1.0, 0.0])
    assert compute_same_as_clue(a, profile("bbb", embedding=[1.0, 0.0])).signals["stylometry_similarity"].value == 1.0
    assert compute_same_as_clue(a, profile("bbb", embedding=[]))  # empty -> missing
    assert compute_same_as_clue(a, profile("bbb", embedding=[])).signals["stylometry_similarity"].status == "missing"
    assert compute_same_as_clue(a, profile("bbb", embedding=[0.0, 0.0])).signals["stylometry_similarity"].status == "missing"
    mismatch = compute_same_as_clue(a, profile("bbb", embedding=[1.0, 0.0, 0.0])).signals["stylometry_similarity"]
    assert mismatch.status == "missing" and "incompatible" in mismatch.details
    opposite = compute_same_as_clue(a, profile("bbb", embedding=[-1.0, 0.0])).signals["stylometry_similarity"]
    assert opposite.value == 0.0  # negative cosine clipped


def test_cve_sets_empty_and_overlapping():
    cve = ent("cve:CVE-2024-3400", EntityType.CVE, "p1")
    empty = compute_same_as_clue(profile("a1"), profile("b1")).signals["graph_neighborhood_overlap"]
    assert empty.status == "missing"
    both = compute_same_as_clue(profile("a1", entities=[cve]), profile("b1", entities=[cve]))
    g = both.signals["graph_neighborhood_overlap"]
    assert g.value == 1.0 and g.contribution == pytest.approx(0.07)
    assert any("weak evidence" in lim for lim in both.limitations)
    # A shared CVE alone stays far below a shared Tox ID.
    assert both.score < 0.2


def test_temporal_midnight_and_missing():
    a = profile("a1", [post("p1", 23), post("p2", 23)])
    b = profile("b1", [post("p3", 1), post("p4", 1)])
    t = compute_same_as_clue(a, b).signals["temporal_similarity"]
    assert t.value == pytest.approx(1 - 2 / 12, abs=1e-3)
    one_post = compute_same_as_clue(profile("a1", [post("p1", 3)]), b).signals["temporal_similarity"]
    assert one_post.status == "missing"


def test_contradictory_evidence_reported():
    a = profile("a1", [post("p1", 2), post("p2", 2)], [ent(TOX, EntityType.TOX_ID, "p1")])
    b = profile("b1", [post("p3", 14), post("p4", 14)], [ent(TOX, EntityType.TOX_ID, "p3")])
    c = compute_same_as_clue(a, b)
    assert any("different activity hours" in x for x in c.contradictions)


def test_similar_names_without_artifacts_contradiction():
    a = profile("pepela", entities=[ent("wallet:0x1", EntityType.WALLET, "p1")])
    b = profile("pepela_", entities=[ent("wallet:0x2", EntityType.WALLET, "p2")])
    assert any("impersonation" in x for x in compute_same_as_clue(a, b).contradictions)


def test_copied_posts_flagged():
    a = profile("a1", [post("p1", 1, h="same")], [ent(TOX, EntityType.TOX_ID, "p1")])
    b = profile("b1", [post("p2", 1, h="same")], [ent(TOX, EntityType.TOX_ID, "p2")])
    c = compute_same_as_clue(a, b)
    assert c.signals["technical_artifact_overlap"].reliability == "low"
    assert any("identical content" in x for x in c.contradictions)


def test_score_bounds_and_determinism():
    a = profile("Zed", [post("p1", 1), post("p2", 1)], [ent(TOX, EntityType.TOX_ID, "p1"), ent("cve:CVE-1", EntityType.CVE, "p1")], [1, 1])
    b = profile("zed2", [post("p3", 1), post("p4", 1)], [ent(TOX, EntityType.TOX_ID, "p3"), ent("cve:CVE-1", EntityType.CVE, "p3")], [1, 1])
    c1, c2 = compute_same_as_clue(a, b), compute_same_as_clue(b, a)
    assert c1.model_dump() == c2.model_dump()
    assert 0 <= c1.score <= 1 and c1.coverage == 1.0
    assert c1.clue_id == clue_id_for("zed2", "Zed")


def test_self_comparison_rejected():
    with pytest.raises(ValueError):
        compute_same_as_clue(profile("x1"), profile("X1"))


@pytest.mark.parametrize("weights", [
    {**DEFAULT_WEIGHTS, "lexical_similarity": 0.5},
    {**DEFAULT_WEIGHTS, "lexical_similarity": -0.08, "technical_artifact_overlap": 0.81},
    {"technical_artifact_overlap": 1.0},
])
def test_invalid_weights_rejected(weights):
    with pytest.raises(ValueError):
        ScoringConfig(weights=weights)


def test_candidate_generation_deterministic_and_thresholded():
    tox = ent(TOX, EntityType.TOX_ID, "p")
    profiles = [
        profile("Spirigatito", [post("p3", 1), post("p4", 22)], [tox]),
        profile("pepela", [post("p1", 23), post("p2", 0)], [tox]),
        profile("unrelated", [post("p9", 12)], [ent("wallet:0x9", EntityType.WALLET, "p9")]),
    ]
    pairs = candidate_pairs(profiles)
    assert pairs == [("pepela", "Spirigatito", ["shared_artifact"])]
    clues = generate_clues(profiles, ScoringConfig(candidate_threshold=0.3))
    assert [(c.handle_a, c.handle_b) for c in clues] == [("pepela", "Spirigatito")]
    assert generate_clues(profiles, ScoringConfig(candidate_threshold=0.99)) == []
