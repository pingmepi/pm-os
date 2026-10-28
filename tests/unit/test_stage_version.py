"""Unit tests for lib/stage_version.py and the schema 5 -> 6 migration: the
human-readable approval version per stage (backlog #71, PM decisions
2026-10-21: increment on new approved content only; backfill from telemetry).
See docs/guides/testing.md §5 (T1)."""
import json

import pytest

import project
import stage_version

pytestmark = pytest.mark.unit


def _telemetry(root, events):
    lines = [json.dumps({"event_type": e, "stage": s, "payload": p}) for e, s, p in events]
    (root / "telemetry.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_bump_increments_only_for_a_new_body():
    """The first approval is v1; approving a different body is v2; approving
    the same body again (a rebind, or an unchanged stale stage) stays v2."""
    stage = {"id": "03"}
    assert stage_version.bump(stage, "aaa") == 1
    assert stage_version.bump(stage, "bbb") == 2
    assert stage_version.bump(stage, "bbb") == 2
    assert stage == {"id": "03", "version": 2, "version_hash": "bbb"}


def test_count_versions_counts_changes_in_sequence():
    """Each approval whose hash differs from the previous one counts, so
    approving A, B, then A again is three versions; repeats don't count."""
    assert stage_version.count_versions([]) == 0
    assert stage_version.count_versions(["a", "a", "b", "b", "a"]) == 3


def test_approval_hashes_reads_every_approval_event_and_skips_bad_lines(tmp_path):
    """Approval, import, backfill and implicit re-approval events all bind a
    body; other stages, other events and malformed lines are ignored."""
    _telemetry(tmp_path, [
        ("stage_approved", "03", {"approved_hash": "a"}),
        ("stage_generated", "03", {"generated_hash": "x"}),
        ("implicit_reapproval", "03", {"new_hash": "b"}),
        ("stage_approved", "04", {"approved_hash": "z"}),
        ("stage_imported", "03", {"approved_hash": "c"}),
    ])
    with (tmp_path / "telemetry.jsonl").open("a", encoding="utf-8") as f:
        f.write("not json\n")
    assert stage_version.approval_hashes(tmp_path, "03") == ["a", "b", "c"]


def test_migration_backfills_versions_from_telemetry(tmp_path):
    """Schema 5 -> 6: an approved stage approved three times with two distinct
    consecutive bodies gets v2; an approved stage with no telemetry gets v1; a
    stage never approved gets no version. Re-running changes nothing."""
    _telemetry(tmp_path, [
        ("stage_approved", "03", {"approved_hash": "a"}),
        ("stage_approved", "03", {"approved_hash": "a"}),
        ("stage_approved", "03", {"approved_hash": "b"}),
    ])
    meta = {
        "schema_version": 5, "entry_route": "new", "context_pack": None,
        "project_type": "new_product", "codebase_path": None, "codebase_ref": None,
        "stages": [
            {"id": "00", "status": "approved", "content_hash": "s", "origin": "generated"},
            {"id": "03", "status": "approved", "content_hash": "b", "origin": "generated"},
            {"id": "06", "status": "pending", "content_hash": None, "origin": "generated"},
        ],
    }
    assert project.migrate_meta(meta, tmp_path) is True
    assert meta["schema_version"] == project.SCHEMA_VERSION == 6
    by_id = {s["id"]: s for s in meta["stages"]}
    assert (by_id["03"]["version"], by_id["03"]["version_hash"]) == (2, "b")
    assert (by_id["00"]["version"], by_id["00"]["version_hash"]) == (1, "s")
    assert by_id["06"]["version"] is None
    assert project.migrate_meta(meta, tmp_path) is False


def test_migration_keeps_last_approved_hash_for_a_regenerated_draft(tmp_path):
    """A stage regenerated after approval is `draft` with no content hash. It
    keeps its last approved version, and `version_hash` comes from telemetry,
    so approving an identical body later does not mint a new version."""
    _telemetry(tmp_path, [("stage_approved", "03", {"approved_hash": "a"})])
    meta = {"schema_version": 5, "stages": [
        {"id": "03", "status": "draft", "content_hash": None, "origin": "generated"}]}
    project.migrate_meta(meta, tmp_path)
    stage = next(s for s in meta["stages"] if s["id"] == "03")
    assert (stage["version"], stage["version_hash"]) == (1, "a")
    assert stage_version.bump(stage, "a") == 1
    assert stage_version.bump(stage, "b") == 2
