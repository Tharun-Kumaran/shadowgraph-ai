"""Similarity primitives used by the identity-resolution engine.

Functions return ``None`` when a similarity is *undefined* (e.g. empty
input) so callers can distinguish missing evidence from a genuine zero.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Sequence


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float | None:
    """Cosine similarity in [-1, 1]; None for empty or zero-norm vectors.

    Raises ValueError for incompatible dimensions (a programming error that
    must not be silently scored as zero).
    """
    if not a or not b:
        return None
    if len(a) != len(b):
        raise ValueError(f"incompatible vector dimensions: {len(a)} vs {len(b)}")
    dot = math.fsum(x * y for x, y in zip(a, b))
    na = math.sqrt(math.fsum(x * x for x in a))
    nb = math.sqrt(math.fsum(y * y for y in b))
    if na == 0.0 or nb == 0.0 or math.isnan(dot):
        return None
    return max(-1.0, min(1.0, dot / (na * nb)))


def mean_vector(vectors: Sequence[Sequence[float]]) -> list[float] | None:
    vectors = [v for v in vectors if v]
    if not vectors:
        return None
    dim = len(vectors[0])
    if any(len(v) != dim for v in vectors):
        raise ValueError("cannot average vectors of different dimensions")
    return [math.fsum(v[i] for v in vectors) / len(vectors) for i in range(dim)]


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a or not b:
        return max(len(a), len(b))
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def normalized_levenshtein(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    return 1.0 - levenshtein(a, b) / max(len(a), len(b))


def jaro(a: str, b: str) -> float:
    if a == b:
        return 1.0
    la, lb = len(a), len(b)
    if not la or not lb:
        return 0.0
    window = max(max(la, lb) // 2 - 1, 0)
    ma, mb = [False] * la, [False] * lb
    matches = 0
    for i, ca in enumerate(a):
        lo, hi = max(0, i - window), min(lb, i + window + 1)
        for j in range(lo, hi):
            if not mb[j] and b[j] == ca:
                ma[i] = mb[j] = True
                matches += 1
                break
    if not matches:
        return 0.0
    t, k = 0, 0
    for i in range(la):
        if ma[i]:
            while not mb[k]:
                k += 1
            if a[i] != b[k]:
                t += 1
            k += 1
    t //= 2
    return (matches / la + matches / lb + (matches - t) / matches) / 3.0


def jaro_winkler(a: str, b: str, p: float = 0.1, max_prefix: int = 4) -> float:
    j = jaro(a, b)
    prefix = 0
    for ca, cb in zip(a[:max_prefix], b[:max_prefix]):
        if ca != cb:
            break
        prefix += 1
    return min(1.0, j + prefix * p * (1.0 - j))


_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})


def handle_skeleton(handle: str) -> str:
    """Case-fold, strip accents, map leetspeak, drop separators and trailing digits."""
    h = unicodedata.normalize("NFKD", handle).encode("ascii", "ignore").decode().casefold()
    h = h.translate(_LEET)
    h = re.sub(r"[^a-z0-9]", "", h)
    return re.sub(r"\d+$", "", h) or h


def handle_similarity(a: str, b: str) -> tuple[float, str]:
    """Return (similarity, method) — max of direct and skeleton Jaro-Winkler."""
    direct = jaro_winkler(a.casefold(), b.casefold())
    skel = jaro_winkler(handle_skeleton(a), handle_skeleton(b))
    return (direct, "jaro_winkler") if direct >= skel else (skel, "jaro_winkler_skeleton")


def jaccard(a: set, b: set) -> float | None:
    if not a and not b:
        return None
    return len(a & b) / len(a | b)


def circular_hour_difference(h1: float, h2: float) -> float:
    """Smallest distance between two hours-of-day on a 24h circle (0..12)."""
    d = abs((h1 % 24) - (h2 % 24))
    return min(d, 24.0 - d)


def circular_mean_hour(hours: Sequence[float]) -> tuple[float, float] | None:
    """Return (mean hour, resultant length R in [0,1]) or None if empty.

    R near 1 means activity is concentrated; near 0 means spread out (the
    mean is then not meaningful).
    """
    if not hours:
        return None
    s = math.fsum(math.sin(2 * math.pi * h / 24) for h in hours)
    c = math.fsum(math.cos(2 * math.pi * h / 24) for h in hours)
    r = math.hypot(s, c) / len(hours)
    mean = (math.atan2(s, c) * 24 / (2 * math.pi)) % 24
    return mean, r
