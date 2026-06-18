"""Unit tests for lib/text_metrics.py — Levenshtein edit distance used to quantify how
much a PM edited a generated artifact before approving. See docs/TESTING.md §5 (T1)."""
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
