"""Pure-stdlib text distance metrics (no third-party dependencies).

Used to quantify how much a PM edited a generated artifact between generation
and approval. ``char_edit_distance`` is a standard Levenshtein distance;
``normalized_edit_distance`` scales it to 0..1 by the longer input length so
short and long artifacts are comparable.

Exact Levenshtein is O(len(a)·len(b)). For a 466 KB PRD that is about 2×10¹¹
cells in pure Python, which made approval appear to hang (backlog #56). So
approval uses ``bounded_edit_distance``. It is exact when the part that
differs fits within a cell budget; it strips the shared prefix and suffix
first, which never changes the distance. Above the budget it falls back to a
line-level edit script from ``difflib``, which is an upper bound on the true
distance, and it reports which method produced the number.
"""
from __future__ import annotations

import difflib

# Roughly a second of pure-Python DP. Above this, approval falls back to the
# line-level estimate.
EXACT_CELL_BUDGET = 2_000_000


def _trim_common(a: str, b: str) -> tuple[str, str]:
    """Strip the shared prefix and suffix. The Levenshtein distance is unchanged."""
    limit = min(len(a), len(b))
    start = 0
    while start < limit and a[start] == b[start]:
        start += 1
    end = 0
    while end < limit - start and a[-1 - end] == b[-1 - end]:
        end += 1
    return a[start:len(a) - end], b[start:len(b) - end]


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    if len(b) > len(a):
        a, b = b, a  # keep the DP row on the shorter string
    # Two-row dynamic programming — O(len(a) * len(b)) time, O(len(b)) space.
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


def char_edit_distance(a: str, b: str) -> int:
    """Exact Levenshtein edit distance (insertions/deletions/substitutions).

    Unbounded. Prefer ``bounded_edit_distance`` for inputs the size of an artifact.
    """
    a, b = _trim_common(a, b)
    return _levenshtein(a, b)


def bounded_edit_distance(a: str, b: str, cell_budget: int = EXACT_CELL_BUDGET) -> tuple[int, str]:
    """Edit distance at bounded cost. Returns ``(distance, method)``.

    ``method`` is ``"exact"`` when the result is the true Levenshtein distance,
    and ``"line_approx"`` when the inputs were too large for that. In the
    approximate case the distance is the cost of a line-level edit script, an
    upper bound on the true distance. Each changed hunk is measured exactly
    when it fits the budget; otherwise it counts as the length of its longer side.
    """
    a, b = _trim_common(a, b)
    if len(a) * len(b) <= cell_budget:
        return _levenshtein(a, b), "exact"

    a_lines = a.splitlines(keepends=True)
    b_lines = b.splitlines(keepends=True)
    total = 0
    matcher = difflib.SequenceMatcher(None, a_lines, b_lines)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        old = "".join(a_lines[i1:i2])
        new = "".join(b_lines[j1:j2])
        if tag == "delete":
            total += len(old)
        elif tag == "insert":
            total += len(new)
        else:  # replace
            old_t, new_t = _trim_common(old, new)
            if len(old_t) * len(new_t) <= cell_budget:
                total += _levenshtein(old_t, new_t)
            else:
                total += max(len(old_t), len(new_t))
    return total, "line_approx"


def normalized_edit_distance(a: str, b: str, distance: int | None = None) -> float:
    """Edit distance scaled to 0..1 by the longer string length (0.0 == identical).

    Pass a precomputed ``distance`` to avoid computing it a second time.
    """
    if not a and not b:
        return 0.0
    longest = max(len(a), len(b))
    if longest == 0:
        return 0.0
    if distance is None:
        distance = char_edit_distance(a, b)
    return distance / longest
