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


# --- Composite (adaptive context pack) hashing -------------------------------

def _pack(tmp_path, evidence="claims:\n- id: c1\n  text: alpha\n- id: c2\n  text: beta\n"):
    """Build a minimal valid context pack: wiki index + sources.md + evidence.yaml + manifest."""
    (tmp_path / "00-context").mkdir(parents=True, exist_ok=True)
    (tmp_path / "00-context-wiki.md").write_text(
        "---\nstatus: draft\n---\n# Index\nwiki body\n", encoding="utf-8")
    (tmp_path / "00-context" / "sources.md").write_text(
        "---\nx: 1\n---\nsources body\n", encoding="utf-8")
    (tmp_path / "00-context" / "evidence.yaml").write_text(evidence, encoding="utf-8")
    (tmp_path / "00-context" / "manifest.yaml").write_text(
        "members:\n"
        "- path: 00-context-wiki.md\n  kind: markdown\n"
        "- path: 00-context/sources.md\n  kind: markdown\n"
        "- path: 00-context/evidence.yaml\n  kind: yaml\n",
        encoding="utf-8")
    return tmp_path


def test_composite_hash_stable_and_member_order_fixed(tmp_path):
    """The composite hash is reproducible for an unchanged pack and is driven by the
    manifest's declared member order, not filesystem order."""
    _pack(tmp_path)
    assert hashing.hash_composite_artifact(tmp_path) == hashing.hash_composite_artifact(tmp_path)


def test_composite_markdown_frontmatter_inert(tmp_path):
    """Editing only a markdown member's frontmatter does not move the composite hash
    (members are hashed body-only, reusing hash_artifact_body)."""
    _pack(tmp_path)
    h1 = hashing.hash_composite_artifact(tmp_path)
    (tmp_path / "00-context-wiki.md").write_text(
        "---\nstatus: approved\ncontent_hash: zzz\n---\n# Index\nwiki body\n", encoding="utf-8")
    assert hashing.hash_composite_artifact(tmp_path) == h1


def test_composite_yaml_cosmetic_reformat_inert(tmp_path):
    """Reordering an id-keyed YAML list, reordering keys, and adding comments are all inert —
    YAML members are hashed over a canonical serialization, not raw bytes."""
    _pack(tmp_path)
    h1 = hashing.hash_composite_artifact(tmp_path)
    (tmp_path / "00-context" / "evidence.yaml").write_text(
        "# a comment\nclaims:\n- text: beta\n  id: c2\n- text: alpha\n  id: c1\n", encoding="utf-8")
    assert hashing.hash_composite_artifact(tmp_path) == h1


def test_composite_detects_member_body_change(tmp_path):
    """A semantic change to any member's body moves the composite hash (drift detection)."""
    _pack(tmp_path)
    h1 = hashing.hash_composite_artifact(tmp_path)
    (tmp_path / "00-context" / "sources.md").write_text(
        "---\nx: 1\n---\nCHANGED sources body\n", encoding="utf-8")
    assert hashing.hash_composite_artifact(tmp_path) != h1


def test_composite_detects_stage_affinity_change(tmp_path):
    """Editing the manifest's stage_affinities (which decide what each downstream
    stage reads) moves the composite hash, so a routing change after 00w approval is
    detected as drift. Cosmetic reordering of the affinity map stays inert."""
    _pack(tmp_path)
    manifest = (
        "members:\n"
        "- path: 00-context-wiki.md\n  kind: markdown\n"
        "- path: 00-context/sources.md\n  kind: markdown\n"
        "- path: 00-context/evidence.yaml\n  kind: yaml\n"
    )
    base = hashing.hash_composite_artifact(tmp_path)
    # Adding a routing affinity changes the hash.
    (tmp_path / "00-context" / "manifest.yaml").write_text(
        manifest + "stage_affinities:\n  00-context/evidence.yaml: ['03', '06']\n", encoding="utf-8")
    with_aff = hashing.hash_composite_artifact(tmp_path)
    assert with_aff != base
    # Cosmetic reordering of keys/values in the affinity map is inert (canonical).
    (tmp_path / "00-context" / "manifest.yaml").write_text(
        manifest + "stage_affinities:\n  00-context/evidence.yaml:\n  - '03'\n  - '06'\n", encoding="utf-8")
    assert hashing.hash_composite_artifact(tmp_path) == with_aff


def test_composite_yaml_value_change_detected(tmp_path):
    """A real value change in a YAML member (not cosmetic) does move the hash."""
    h_a = hashing.hash_composite_artifact(_pack(tmp_path / "a", "claims:\n- id: c1\n  text: alpha\n"))
    h_b = hashing.hash_composite_artifact(_pack(tmp_path / "b", "claims:\n- id: c1\n  text: CHANGED\n"))
    assert h_a != h_b


def test_stage_content_hash_dispatch_dual_mode(tmp_path):
    """stage_content_hash returns the composite hash for a 00w with a manifest and the plain
    body hash once the manifest is removed (legacy single-file wiki fallback)."""
    _pack(tmp_path)
    wiki = tmp_path / "00-context-wiki.md"
    composite = hashing.stage_content_hash(tmp_path, "00w", wiki)
    assert composite == hashing.hash_composite_artifact(tmp_path)

    # T10: the shared consistency checker's drift invariant (invariant 2) reuses
    # stage_content_hash too — a recorded hash matching the current composite hash
    # must not be flagged, while the manifest is still present.
    import consistency
    (tmp_path / ".meta.yaml").write_text(
        "schema_version: 4\nproject_slug: hash-drift\nstages:\n"
        "- id: '00w'\n  status: approved\n"
        f"  content_hash: '{composite}'\n  origin: generated\n", encoding="utf-8")
    issues = consistency.check_project(tmp_path)
    assert not any(i.code == consistency.CODE_BODY_HASH_DRIFT for i in issues)

    (tmp_path / "00-context" / "manifest.yaml").unlink()
    flat = hashing.stage_content_hash(tmp_path, "00w", wiki)
    assert flat == hashing.hash_artifact_body(str(wiki))
    assert flat != composite


def test_stage_content_hash_non_00w_always_body(tmp_path):
    """Any stage other than 00w is body-hashed even if a context pack happens to exist."""
    _pack(tmp_path)
    art = tmp_path / "01-brief.md"
    art.write_text("---\nstatus: draft\n---\nbrief body\n", encoding="utf-8")
    assert hashing.stage_content_hash(tmp_path, "01", art) == hashing.hash_artifact_body(str(art))


def test_manifest_safety_rejections(tmp_path):
    """load_manifest_members rejects missing manifests, path traversal, duplicates, self-listing,
    and members missing on disk — the unsafe-manifest guards behind the gate's block."""
    # missing manifest
    with pytest.raises(hashing.CompositeHashError):
        hashing.load_manifest_members(tmp_path)
    (tmp_path / "00-context").mkdir()
    mpath = tmp_path / "00-context" / "manifest.yaml"
    # path traversal
    mpath.write_text("members:\n- path: ../../etc/passwd\n  kind: markdown\n", encoding="utf-8")
    with pytest.raises(hashing.CompositeHashError):
        hashing.load_manifest_members(tmp_path)
    # member missing on disk
    mpath.write_text("members:\n- path: 00-context/nope.md\n  kind: markdown\n", encoding="utf-8")
    with pytest.raises(hashing.CompositeHashError):
        hashing.load_manifest_members(tmp_path)
    # manifest listing itself
    mpath.write_text("members:\n- path: 00-context/manifest.yaml\n  kind: yaml\n", encoding="utf-8")
    with pytest.raises(hashing.CompositeHashError):
        hashing.load_manifest_members(tmp_path)
    # duplicate member paths
    (tmp_path / "00-context-wiki.md").write_text("---\n---\nx\n", encoding="utf-8")
    mpath.write_text(
        "members:\n- path: 00-context-wiki.md\n  kind: markdown\n"
        "- path: 00-context-wiki.md\n  kind: markdown\n", encoding="utf-8")
    with pytest.raises(hashing.CompositeHashError):
        hashing.load_manifest_members(tmp_path)


def test_validate_manifest_hashes_detects_stale(tmp_path):
    """validate_manifest_hashes reports members whose recorded hash no longer matches the file,
    and an empty list when every recorded hash is current."""
    _pack(tmp_path)
    members = hashing.load_manifest_members(tmp_path)
    # record correct hashes
    recorded = []
    for m in members:
        recorded.append({**m, "hash": hashing.composite_member_hash(tmp_path, m)})
    (tmp_path / "00-context" / "manifest.yaml").write_text(
        __import__("yaml").dump({"members": recorded}), encoding="utf-8")
    assert hashing.validate_manifest_hashes(tmp_path) == []
    # now edit a member body -> its recorded hash goes stale
    (tmp_path / "00-context-wiki.md").write_text(
        "---\nstatus: draft\n---\n# Index\nDIFFERENT body\n", encoding="utf-8")
    assert "00-context-wiki.md" in hashing.validate_manifest_hashes(tmp_path)
