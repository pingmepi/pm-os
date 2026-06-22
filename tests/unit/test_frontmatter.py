"""Unit tests for lib/frontmatter.py — YAML frontmatter + body read/write/update.

This module is the lockstep point between an artifact's on-disk metadata and the rest of
the state machine, so round-trip fidelity and body-preservation matter. See docs/guides/testing.md §5 (T1).
"""
import pytest

import frontmatter

pytestmark = pytest.mark.unit


def test_read_write_roundtrip(tmp_path):
    """Frontmatter values and body survive a write→read cycle intact."""
    p = tmp_path / "a.md"
    frontmatter.write(str(p), {"stage": "01-brief", "status": "draft"}, "Body text.\n")
    fm, body = frontmatter.read(str(p))
    assert fm["stage"] == "01-brief"
    assert fm["status"] == "draft"
    assert body == "Body text.\n"


def test_read_no_frontmatter_returns_empty_dict(tmp_path):
    """A doc with no frontmatter yields ({}, full-content) rather than erroring."""
    p = tmp_path / "plain.md"
    p.write_text("no frontmatter here\n", encoding="utf-8")
    fm, body = frontmatter.read(str(p))
    assert fm == {}
    assert body == "no frontmatter here\n"


def test_read_crlf_normalized(tmp_path):
    """CRLF input is normalized so downstream body handling/hashing is line-ending agnostic."""
    p = tmp_path / "crlf.md"
    p.write_bytes(b"---\r\nstatus: draft\r\n---\r\nbody\r\n")
    fm, body = frontmatter.read(str(p))
    assert fm["status"] == "draft"
    assert "\r" not in body


def test_update_status_flips_and_sets_kwargs(tmp_path):
    """update_status flips `status` and sets extra fields atomically WITHOUT touching the
    body — the path approval/gate code uses to keep frontmatter in sync with meta."""
    p = tmp_path / "a.md"
    frontmatter.write(str(p), {"status": "draft", "content_hash": None}, "Body.\n")
    frontmatter.update_status(str(p), "approved", content_hash="deadbeef", approved_by="tester")
    fm, body = frontmatter.read(str(p))
    assert fm["status"] == "approved"
    assert fm["content_hash"] == "deadbeef"
    assert fm["approved_by"] == "tester"
    assert body == "Body.\n", "update_status must not touch the body"


def test_empty_frontmatter_roundtrip(tmp_path):
    """write({}, body) emits a parseable empty block that reads back as ({}, body)."""
    p = tmp_path / "e.md"
    frontmatter.write(str(p), {}, "body only\n")
    fm, body = frontmatter.read(str(p))
    assert fm == {}
    assert body == "body only\n"


def test_bare_dashes_treated_as_no_frontmatter(tmp_path):
    """A doc that merely starts with '---\\n---\\n' has no valid closing delimiter (which
    needs a preceding newline), so it is returned verbatim as body — documents the quirk."""
    p = tmp_path / "d.md"
    p.write_text("---\n---\nbody only\n", encoding="utf-8")
    fm, body = frontmatter.read(str(p))
    assert fm == {}
    assert body == "---\n---\nbody only\n"
