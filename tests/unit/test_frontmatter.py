import pytest

import frontmatter

pytestmark = pytest.mark.unit


def test_read_write_roundtrip(tmp_path):
    p = tmp_path / "a.md"
    frontmatter.write(str(p), {"stage": "01-brief", "status": "draft"}, "Body text.\n")
    fm, body = frontmatter.read(str(p))
    assert fm["stage"] == "01-brief"
    assert fm["status"] == "draft"
    assert body == "Body text.\n"


def test_read_no_frontmatter_returns_empty_dict(tmp_path):
    p = tmp_path / "plain.md"
    p.write_text("no frontmatter here\n", encoding="utf-8")
    fm, body = frontmatter.read(str(p))
    assert fm == {}
    assert body == "no frontmatter here\n"


def test_read_crlf_normalized(tmp_path):
    p = tmp_path / "crlf.md"
    p.write_bytes(b"---\r\nstatus: draft\r\n---\r\nbody\r\n")
    fm, body = frontmatter.read(str(p))
    assert fm["status"] == "draft"
    assert "\r" not in body


def test_update_status_flips_and_sets_kwargs(tmp_path):
    p = tmp_path / "a.md"
    frontmatter.write(str(p), {"status": "draft", "content_hash": None}, "Body.\n")
    frontmatter.update_status(str(p), "approved", content_hash="deadbeef", approved_by="tester")
    fm, body = frontmatter.read(str(p))
    assert fm["status"] == "approved"
    assert fm["content_hash"] == "deadbeef"
    assert fm["approved_by"] == "tester"
    assert body == "Body.\n", "update_status must not touch the body"


def test_empty_frontmatter_roundtrip(tmp_path):
    # write({}, body) emits a parseable empty block ("---\n{}\n---\n...").
    p = tmp_path / "e.md"
    frontmatter.write(str(p), {}, "body only\n")
    fm, body = frontmatter.read(str(p))
    assert fm == {}
    assert body == "body only\n"


def test_bare_dashes_treated_as_no_frontmatter(tmp_path):
    # A doc that merely starts with '---\n---\n' has no valid closing delimiter
    # (needs a preceding newline), so it is returned verbatim as body.
    p = tmp_path / "d.md"
    p.write_text("---\n---\nbody only\n", encoding="utf-8")
    fm, body = frontmatter.read(str(p))
    assert fm == {}
    assert body == "---\n---\nbody only\n"
