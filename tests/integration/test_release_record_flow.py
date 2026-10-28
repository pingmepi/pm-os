"""Handoff releases end to end (backlog #73, #75, #68): every package build
writes CHANGES.md and manifest.json per audience; a build given
`--release-note` is recorded in `.releases/REL-###.yaml` and logs
`handoff_released`; the next release's change note lists the stable ids that
changed and the stories they affect; and a rebuild deletes only the files the
previous manifest lists. See docs/guides/testing.md §T2."""
import json

import pytest
import yaml

from helpers import make_draft, read_events, run_script

pytestmark = pytest.mark.integration

_PRD_V1 = """## Product Epics
### EPIC-001 — Agency onboarding
**Outcome:** Agencies can be added.
## User Journeys
### UJ-001 — Manage agencies
Primary user: Collections user. Traceability: US-001.
## User Stories with Acceptance Criteria
### US-001 — Add external agency
**Priority:** Must
**Epic:** EPIC-001
As a Collections user, I want to add agencies. Traceability: UJ-001, FR-001.
## Functional Requirements
- **FR-001** — The system stores agencies.
  **Priority:** Must
  **Epic:** EPIC-001
"""

# v2 changes US-001's text and adds US-002 with its own requirement.
_PRD_V2 = """## Product Epics
### EPIC-001 — Agency onboarding
**Outcome:** Agencies can be added.
## User Journeys
### UJ-001 — Manage agencies
Primary user: Collections user. Traceability: US-001.
## User Stories with Acceptance Criteria
### US-001 — Add external agency
**Priority:** Must
**Epic:** EPIC-001
As a Collections user, I want to add and name agencies. Traceability: UJ-001, FR-001.
### US-002 — List agencies
**Priority:** Should
**Epic:** EPIC-001
As a Collections user, I want to see every agency. Traceability: UJ-001, FR-002.
## Functional Requirements
- **FR-001** — The system stores agencies.
  **Priority:** Must
  **Epic:** EPIC-001
- **FR-002** — The system lists agencies.
  **Priority:** Should
  **Epic:** EPIC-001
"""

_QA_V1 = """## Functional Test Cases
### TC-001 — Add happy path (covers US-001, FR-001)
Given valid fields, the agency is saved.
"""
_QA_V2 = _QA_V1 + """### TC-002 — List happy path (covers US-002, FR-002)
Given two agencies, both are listed.
"""


def _approve(pmos, proj, stage, body):
    make_draft(proj, stage, body=body)
    res = run_script(pmos, "pm_approve.py", stage, cwd=proj)
    assert res.returncode == 0, res.stdout + res.stderr


def _project(pmos, new_project, slug):
    proj = new_project(slug, "A problem")
    for stage, body in (("01", "## Overview\nAgencies.\n"), ("02", "## MVP Boundary\nAdd.\n"),
                        ("03", _PRD_V1), ("06", _QA_V1)):
        _approve(pmos, proj, stage, body)
    return proj


def test_draft_build_writes_change_note_and_manifest_but_no_release(pmos, new_project):
    """A plain `--package` build writes CHANGES.md (marked draft) and a
    manifest.json listing every file with role, hash and reading order, links
    both from the README, and records no release."""
    proj = _project(pmos, new_project, "rel-draft")
    res = run_script(pmos, "pm_share.py", "--package", cwd=proj)
    assert res.returncode == 0, res.stderr
    dev = proj / "handoff" / "dev"
    changes = (dev / "CHANGES.md").read_text(encoding="utf-8")
    assert "draft build (not a recorded release)" in changes
    assert "No earlier release is recorded" in changes
    manifest = json.loads((dev / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["draft"] is True and manifest["release"] is None
    paths = {f["path"]: f for f in manifest["files"]}
    assert paths["README.md"]["read_order"] == 1 and paths["CHANGES.md"]["role"] == "index"
    assert paths["reference/prd.md"]["role"] == "source-of-truth"
    story = next(f for p, f in paths.items() if p.startswith("stories/"))
    assert story["role"] == "derived" and story["status"] == "approved" and story["version"] == 1
    assert "manifest.json" not in paths and ".pm-os-handoff" not in paths
    assert "[What changed](CHANGES.md)" in (dev / "README.md").read_text(encoding="utf-8")
    assert not (proj / ".releases").exists()
    assert "handoff_released" not in [e["event_type"] for e in read_events(proj)]


def test_two_releases_produce_a_change_note_naming_changed_ids_and_stories(pmos, new_project):
    """REL-001 is recorded with the note, sources and stable-id hashes. After
    the PRD changes US-001 and adds US-002 (and QA adds TC-002), REL-002's
    CHANGES.md lists exactly those ids and the two stories affected, and
    `handoff_released` is logged for each release."""
    proj = _project(pmos, new_project, "rel-two")
    res = run_script(pmos, "pm_share.py", "--package", "--release-note", "Sprint 1 kick-off", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert "Recorded release REL-001" in res.stdout
    rel1 = yaml.safe_load((proj / ".releases" / "REL-001.yaml").read_text(encoding="utf-8"))
    assert rel1["note"] == "Sprint 1 kick-off" and rel1["previous"] is None
    assert rel1["sources"]["03"]["version"] == 1
    assert set(rel1["stable_ids"]["03-prd.md"]) >= {"US-001", "FR-001", "EPIC-001"}
    assert json.loads((proj / "handoff" / "qa" / "manifest.json").read_text(encoding="utf-8"))["release"] == "REL-001"

    _approve(pmos, proj, "03", _PRD_V2)
    _approve(pmos, proj, "06", _QA_V2)
    res = run_script(pmos, "pm_share.py", "--package", "--release-note", "List view added", cwd=proj)
    assert res.returncode == 0, res.stderr
    rel2 = yaml.safe_load((proj / ".releases" / "REL-002.yaml").read_text(encoding="utf-8"))
    assert rel2["previous"] == "REL-001" and rel2["sources"]["03"]["version"] == 2
    changed = {(c["id"], c["change"]) for c in rel2["changes"]}
    assert {("US-001", "modified"), ("US-002", "new"), ("FR-002", "new"), ("TC-002", "new")} <= changed
    assert not any(ident == "FR-001" for ident, _ in changed)

    changes = (proj / "handoff" / "dev" / "CHANGES.md").read_text(encoding="utf-8")
    assert "REL-002" in changes and "List view added" in changes
    assert "`REL-001`" in changes
    assert "- `US-001`: its own text changed\n" in changes
    assert "- `US-002`: its own text changed; via `FR-002`, `TC-002`" in changes
    released = [e for e in read_events(proj) if e["event_type"] == "handoff_released"]
    assert [e["payload"]["release"] for e in released] == ["REL-001", "REL-002"]


def test_rebuild_keeps_files_pm_os_did_not_write(pmos, new_project):
    """A file someone saved into an audience folder survives a rebuild and is
    reported as kept; a generated file that no longer ships is removed (#68)."""
    proj = _project(pmos, new_project, "rel-keep")
    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0
    design = proj / "handoff" / "design"
    (design / "design-kit").mkdir()
    (design / "design-kit" / "tokens.json").write_text("{}", encoding="utf-8")
    (design / "stories" / "US-999-old.md").write_text("old", encoding="utf-8")
    manifest = json.loads((design / "manifest.json").read_text(encoding="utf-8"))
    manifest["files"].append({"path": "stories/US-999-old.md"})
    (design / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    res = run_script(pmos, "pm_share.py", "--package", "--audience", "design", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert (design / "design-kit" / "tokens.json").read_text(encoding="utf-8") == "{}"
    assert not (design / "stories" / "US-999-old.md").exists()
    assert "Kept 1 file(s) in handoff/design/" in res.stdout and "design-kit/tokens.json" in res.stdout


def test_blank_release_note_is_refused_before_writing(pmos, new_project):
    """`--release-note ""` is refused with nothing written, and the flag is
    rejected outside `--package`."""
    proj = _project(pmos, new_project, "rel-blank")
    res = run_script(pmos, "pm_share.py", "--package", "--release-note", "  ", cwd=proj)
    assert res.returncode != 0 and "one-line reason" in (res.stdout + res.stderr)
    assert not (proj / "handoff").exists() and not (proj / ".releases").exists()
    res = run_script(pmos, "pm_share.py", "--release-note", "x", cwd=proj)
    assert res.returncode != 0
