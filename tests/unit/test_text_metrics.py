import pytest

import text_metrics as tm

pytestmark = pytest.mark.unit


def test_char_edit_distance_known():
    assert tm.char_edit_distance("kitten", "sitting") == 3
    assert tm.char_edit_distance("abc", "abc") == 0
    assert tm.char_edit_distance("", "abc") == 3
    assert tm.char_edit_distance("abc", "") == 3


def test_normalized_edit_distance_range():
    assert tm.normalized_edit_distance("", "") == 0.0
    assert tm.normalized_edit_distance("abc", "abc") == 0.0
    nd = tm.normalized_edit_distance("abc", "abd")
    assert 0.0 < nd <= 1.0
    assert abs(nd - (1 / 3)) < 1e-9
    assert tm.normalized_edit_distance("abc", "xyz") == 1.0
