"""Unit tests for lib/text_metrics.py — Levenshtein edit distance used to quantify how
much a PM edited a generated artifact before approving. See docs/guides/testing.md §5 (T1)."""
import pytest

import text_metrics as tm

pytestmark = pytest.mark.unit


def test_char_edit_distance_known():
    """Levenshtein distance on a canonical pair (kitten→sitting = 3), identical strings,
    and empty-string boundaries."""
    assert tm.char_edit_distance("kitten", "sitting") == 3
    assert tm.char_edit_distance("abc", "abc") == 0
    assert tm.char_edit_distance("", "abc") == 3
    assert tm.char_edit_distance("abc", "") == 3


def test_normalized_edit_distance_range():
    """Normalized distance is 0.0 for identical (incl. empty/empty), scales by the longer
    length, and is 1.0 for fully-different strings — keeping long/short artifacts comparable."""
    assert tm.normalized_edit_distance("", "") == 0.0
    assert tm.normalized_edit_distance("abc", "abc") == 0.0
    nd = tm.normalized_edit_distance("abc", "abd")
    assert 0.0 < nd <= 1.0
    assert abs(nd - (1 / 3)) < 1e-9
    assert tm.normalized_edit_distance("abc", "xyz") == 1.0


def _reference_levenshtein(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def test_bounded_distance_is_exact_within_budget_and_an_upper_bound_beyond():
    """Backlog #56. On random inputs, ``char_edit_distance`` (now prefix/suffix
    trimmed) still equals a reference Levenshtein. ``bounded_edit_distance`` returns
    the exact value when it reports ``exact``, and never undercounts when it falls
    back to ``line_approx``."""
    import random
    rng = random.Random(7)
    saw_approx = False
    for _ in range(1500):
        a = "".join(rng.choice("ab\n") for _ in range(rng.randint(0, 25)))
        b = "".join(rng.choice("ab\n") for _ in range(rng.randint(0, 25)))
        truth = _reference_levenshtein(a, b)
        assert tm.char_edit_distance(a, b) == truth
        dist, method = tm.bounded_edit_distance(a, b, cell_budget=40)
        if method == "exact":
            assert dist == truth
        else:
            saw_approx = True
            assert method == "line_approx"
            assert dist >= truth
    assert saw_approx


def test_bounded_distance_on_artifact_sized_input_is_fast():
    """Backlog #56. A ~500 KB body with scattered edits finishes in well under a second
    (exact Levenshtein would be ~10^11 cells), reports ``line_approx``, and stays
    proportional to the edits rather than to the document size."""
    import time
    lines = [f"Line {i}: the system shall record requirement {i} for the PRD." for i in range(8000)]
    a = "\n".join(lines)
    edited = list(lines)
    for k in range(0, 8000, 400):
        edited[k] = edited[k].replace("record", "persist")
    b = "\n".join(edited)
    assert len(a) > 400_000
    start = time.perf_counter()
    dist, method = tm.bounded_edit_distance(a, b)
    assert time.perf_counter() - start < 5
    assert method == "line_approx"
    assert 0 < dist < 20 * 20  # 20 edited lines, each a short word swap
