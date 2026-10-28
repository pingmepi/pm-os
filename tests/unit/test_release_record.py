"""Unit tests for lib/release_record.py and the two enhancement helpers it
uses (backlog #73, #75, #68). See docs/guides/testing.md §T1."""
import json

import pytest

import enhancement
import release_record as rr


def test_classify_change_and_stable_id_blocks():
    """`classify_change` names new/removed/modified and returns None when
    equal; `stable_id_blocks` splits a body by stable id like the delta does."""
    assert enhancement.classify_change(None, "a") == "new"
    assert enhancement.classify_change("a", None) == "removed"
    assert enhancement.classify_change("a", "b") == "modified"
    assert enhancement.classify_change("a", "a") is None
    blocks = enhancement.stable_id_blocks("### US-001 — One\nText.\n### US-002 — Two\nMore.\n")
    assert set(blocks) == {"US-001", "US-002"} and blocks["US-001"].endswith("Text.")


def test_ledger_ids_and_no_overwrite(tmp_path):
    """Release ids count up from REL-001, `latest` returns the highest, and a
    record is never overwritten."""
    assert rr.latest(tmp_path) is None and rr.next_id(tmp_path) == "REL-001"
    rr.write_record(tmp_path, {"id": "REL-001", "note": "a"})
    rr.write_record(tmp_path, {"id": "REL-002", "note": "b"})
    assert rr.next_id(tmp_path) == "REL-003"
    assert rr.latest(tmp_path)["note"] == "b"
    with pytest.raises(FileExistsError):
        rr.write_record(tmp_path, {"id": "REL-002", "note": "c"})


def test_diff_classifies_ids_and_outside_inputs():
    """Ids are compared per artifact by block hash; outside inputs that moved
    are listed with before and after."""
    previous = {"id": "REL-001", "stable_ids": {"03-prd.md": {"US-001": "h1", "US-002": "h2"}},
                "outside_inputs": {"Figma file K": "v1"}}
    now = {"03-prd.md": {"US-001": "h1", "US-002": "h9", "US-003": "h3"}}
    delta = rr.diff(previous, now, {"Figma file K": "v2"})
    assert delta["previous"] == "REL-001"
    assert {(c["id"], c["change"]) for c in delta["ids"]} == {("US-002", "modified"), ("US-003", "new")}
    assert delta["inputs"] == [{"input": "Figma file K", "before": "v1", "after": "v2"}]


def test_first_release_note_counts_ids_instead_of_listing_them():
    """With no earlier release the note gives a count per artifact, not every
    id as added; later notes list ids in code spans with the affected stories."""
    first = rr.diff(None, {"03-prd.md": {"US-001": "a", "FR-001": "b"}}, {})
    text = rr.render_changes(project_name="P", delta=first, stories={}, note=None,
                             release_id="REL-001", generated_at="t")
    assert "- 03-prd.md: 2 ids" in text and "`US-001`" not in text
    later = {"previous": "REL-001", "ids": [{"artifact": "03-prd.md", "id": "US-001", "change": "modified"}],
             "inputs": []}
    text = rr.render_changes(project_name="P", delta=later, stories={"US-001": ["US-001"]},
                             note="why", release_id=None, generated_at="t")
    assert "**Changed (1):** `US-001`" in text and "- `US-001`: its own text changed" in text
    assert "draft build" in text


def test_manifest_roles_order_and_exclusions(tmp_path):
    """Each file gets a role, a hash and a reading order; the manifest itself
    and the marker are not listed; frontmatter version/status are carried."""
    (tmp_path / "stories").mkdir()
    (tmp_path / "stories" / "US-001-a.md").write_text(
        "---\nversion: 3\nstatus: approved\nsources:\n- artifact: 03-prd.md\n---\nBody\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".pm-os-handoff").write_text("m", encoding="utf-8")
    manifest = rr.build_manifest("P", "dev", tmp_path, None, "t")
    assert [f["path"] for f in manifest["files"]] == ["README.md", "stories/US-001-a.md"]
    story = manifest["files"][1]
    assert (story["role"], story["version"], story["status"], story["source"]) == \
        ("derived", 3, "approved", "03-prd.md")
    assert manifest["draft"] is True


def test_clear_generated_uses_previous_manifest(tmp_path):
    """Only files the previous manifest lists (plus the manifest and marker)
    are deleted; other files and their folders stay, and are returned as kept."""
    for rel in ("README.md", "stories/US-001.md", "stories/notes.md", "kit/logo.svg", ".pm-os-handoff"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("x", encoding="utf-8")
    (tmp_path / "manifest.json").write_text(json.dumps(
        {"files": [{"path": "README.md"}, {"path": "stories/US-001.md"}]}), encoding="utf-8")
    kept, moved = rr.clear_generated(tmp_path)
    assert kept == ["kit/logo.svg", "stories/notes.md"] and moved == {}
    assert not (tmp_path / "README.md").exists() and not (tmp_path / "manifest.json").exists()


def test_clear_generated_legacy_folder_keeps_unmarked_files(tmp_path):
    """A folder built before manifests loses the known top-level files, files
    the new build writes again, and Markdown that says PM-OS generated it.
    A designer's own Markdown/HTML in the package folders is kept (stack #93
    review: the old layout rule deleted it), and empty folders are removed."""
    files = {
        "README.md": "x", ".pm-os-handoff": "m",
        "stories/US-001.md": "---\ngenerated_from: [03-prd.md@abc]\n---\nBody\n",
        "stories/US-009-dropped.md": "---\ngenerated_from: [03-prd.md@abc]\n---\nOld\n",
        "reference/prd.md": "<!-- GENERATED — DO NOT EDIT HERE. Read-only projection -->\n",
        "wireframes/prototype.html": "<p>",
        "wireframes/kit-v2.html": "<p>mine",
        "reference/designer-notes.md": "notes",
        "my-notes.md": "x", "stories/sketch.png": "x",
    }
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    kept, moved = rr.clear_generated(tmp_path, {"README.md", "wireframes/prototype.html"})
    assert kept == ["my-notes.md", "reference/designer-notes.md", "stories/sketch.png",
                    "wireframes/kit-v2.html"]
    assert moved == {} and not (tmp_path / "stories" / "US-009-dropped.md").exists()


def test_clear_generated_moves_a_kept_file_the_build_would_overwrite(tmp_path):
    """Stack #93 review: a file the previous manifest does not list, at a path
    the new build writes, is renamed to `.mine` instead of silently replaced."""
    (tmp_path / "stories").mkdir()
    (tmp_path / "stories" / "US-009-foo.md").write_text("mine", encoding="utf-8")
    (tmp_path / "manifest.json").write_text(json.dumps({"files": []}), encoding="utf-8")
    kept, moved = rr.clear_generated(tmp_path, {"stories/US-009-foo.md"})
    assert moved == {"stories/US-009-foo.md": "stories/US-009-foo.mine.md"}
    assert kept == ["stories/US-009-foo.mine.md"]
    assert (tmp_path / "stories" / "US-009-foo.mine.md").read_text(encoding="utf-8") == "mine"


def test_malformed_manifest_falls_back_instead_of_crashing(tmp_path):
    """Stack #93 review: `files` holding strings raised AttributeError part way
    through publishing; an unusable manifest now falls back to the legacy rule."""
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    (tmp_path / "kit.svg").write_text("x", encoding="utf-8")
    (tmp_path / "manifest.json").write_text(json.dumps({"files": ["README.md"]}), encoding="utf-8")
    kept, _moved = rr.clear_generated(tmp_path)
    assert kept == ["kit.svg"]


def test_unreadable_latest_release_raises(tmp_path):
    """Stack #93 review: a broken newest REL file used to read as "no release",
    silently resetting the history; it now raises with the file named."""
    rr.write_record(tmp_path, {"id": "REL-001", "note": "a"})
    (tmp_path / ".releases" / "REL-002.yaml").write_text("- not\n- a mapping\n", encoding="utf-8")
    with pytest.raises(rr.ReleaseRecordError, match="REL-002"):
        rr.latest(tmp_path)
    (tmp_path / ".releases" / "REL-002.yaml").write_text("id: [unclosed\n", encoding="utf-8")
    with pytest.raises(rr.ReleaseRecordError):
        rr.latest(tmp_path)


def test_unapproved_source_keeps_previous_ids_and_is_named(tmp_path):
    """Stack #93 review: a stale/edited source used to drop out of the snapshot,
    listing all its ids as removed. Its previous ids are carried and the change
    note names it under "Not compared"."""
    previous = {"id": "REL-001", "stable_ids": {"06-qa-plan.md": {"TC-001": "h1"}}}
    prov = {"06": {"artifact": "06-qa-plan.md", "status": "stale"}}
    ids = rr.stable_id_hashes(tmp_path, prov, previous)
    assert ids == {"06-qa-plan.md": {"TC-001": "h1"}}
    held = rr.not_compared(prov)
    assert held == {"06-qa-plan.md": "stale"}
    delta = rr.diff(previous, ids, {})
    assert delta["ids"] == []
    text = rr.render_changes(project_name="P", delta=delta, stories={}, note=None,
                             release_id=None, generated_at="t", held=held)
    assert "06-qa-plan.md is stale" in text and "`REL-001`" in text


def test_removed_id_traces_through_the_previous_release():
    """Stack #93 review: a removed TC is in no current record, so it used to map
    to no story. The previous release's story_refs still trace it; an id no
    spine traces is listed for a manual check instead of "no story affected"."""
    current = {"US-002": ["FR-003", "US-002"]}
    previous = {"US-002": ["FR-003", "TC-007", "US-002"]}
    assert rr.affected_stories(["TC-007"], current, previous) == {"US-002": ["TC-007"]}
    assert rr.affected_stories(["TC-007"], current, None) == {}
    delta = {"previous": "REL-001", "inputs": [],
             "ids": [{"artifact": "06-qa-plan.md", "id": "TC-099", "change": "removed"}]}
    text = rr.render_changes(project_name="P", delta=delta, stories={}, note=None,
                             release_id=None, generated_at="t")
    assert "Not traced to any story: `TC-099`" in text and "No story is affected" not in text


def test_outside_inputs_reads_figma_version_and_test_input_hashes(tmp_path):
    """The Figma file version comes from design-in/ia.yaml; each readiness test
    input is hashed, or `missing` when its file is absent."""
    (tmp_path / "design-in").mkdir()
    (tmp_path / "design-in" / "ia.yaml").write_text(
        "figma:\n  file_key: K1\n  version: '42'\n  last_modified: '2026-10-20'\n", encoding="utf-8")
    (tmp_path / "inputs").mkdir()
    (tmp_path / "inputs" / "page.html").write_text("<p>", encoding="utf-8")
    (tmp_path / "readiness.yaml").write_text(
        "schema_version: 1\ntest_inputs:\n"
        "  - {id: TI-001, file: inputs/page.html, purpose: p, supplier: s, status: received}\n"
        "  - {id: TI-002, file: inputs/gone.html, purpose: p, supplier: s, status: needed}\n",
        encoding="utf-8")
    found = rr.outside_inputs(tmp_path)
    assert found["Figma file K1"] == "42 (2026-10-20)"
    assert found["TI-001 inputs/page.html"] == rr.sha256_file(tmp_path / "inputs" / "page.html")[:16]
    assert found["TI-002 inputs/gone.html"] == "missing"
