"""Unit tests for lib/hashing.py — content-addressed artifacts + telemetry chain links.

The body-only hash is the foundation of drift detection (frontmatter is metadata, the
body is the product), and hash_event is the link in the tamper-evident telemetry chain.
See docs/guides/testing.md §5 (T1).
"""
import pytest

import hashing

pytestmark = pytest.mark.unit


def _artifact(tmp_path, fm_value, body):
    p = tmp_path / "a.md"
    p.write_text(f"---\nstatus: {fm_value}\ncontent_hash: null\n---\n{body}", encoding="utf-8")
    return p


def test_body_hash_ignores_frontmatter(tmp_path):
    """KEY INVARIANT: editing only the frontmatter must not change the body hash —
    otherwise approving/recording metadata would falsely look like content drift."""
    a = _artifact(tmp_path, "draft", "The product body.\n")
    h1 = hashing.hash_artifact_body(str(a))
    a.write_text("---\nstatus: approved\ncontent_hash: abc\n---\nThe product body.\n", encoding="utf-8")
    h2 = hashing.hash_artifact_body(str(a))
    assert h1 == h2, "frontmatter edits must not change body hash"


def test_body_hash_changes_with_body(tmp_path):
    """Editing the body DOES change the hash — this is what the gate detects as `edited`."""
    a = _artifact(tmp_path, "draft", "Original.\n")
    h1 = hashing.hash_artifact_body(str(a))
    a.write_text("---\nstatus: draft\n---\nChanged body.\n", encoding="utf-8")
    assert hashing.hash_artifact_body(str(a)) != h1


def test_body_hash_crlf_normalized(tmp_path):
    """CRLF and LF versions of the same body hash equal, so line-ending churn (e.g. an
    editor on Windows) doesn't masquerade as drift."""
    lf = tmp_path / "lf.md"
    crlf = tmp_path / "crlf.md"
    lf.write_text("---\nx: 1\n---\nline one\nline two\n", encoding="utf-8")
    crlf.write_bytes(b"---\r\nx: 1\r\n---\r\nline one\r\nline two\r\n")
    assert hashing.hash_artifact_body(str(lf)) == hashing.hash_artifact_body(str(crlf))


def test_hash_event_excludes_event_hash_and_chains():
    """hash_event ignores the event's own `event_hash` field (computed after) and folds in
    prev_hash, so each event is bound to its predecessor."""
    ev = {"event_type": "x", "payload": {"a": 1}, "event_hash": "SHOULD_BE_IGNORED"}
    h_none = hashing.hash_event(ev, None)
    ev2 = dict(ev, event_hash="DIFFERENT")
    assert hashing.hash_event(ev2, None) == h_none
    assert hashing.hash_event(ev, "prevhash") != h_none


def test_hash_event_deterministic_and_unicode():
    """Canonicalization is key-order independent and unicode-safe, so the same event
    always yields the same hash regardless of dict ordering."""
    ev = {"b": 2, "a": 1, "emoji": "✅"}
    assert hashing.hash_event(ev, None) == hashing.hash_event({"a": 1, "b": 2, "emoji": "✅"}, None)
