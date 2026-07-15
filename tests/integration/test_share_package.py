"""pm-share package mode (Phase 4a) — the readable projection built by
`scripts/pm_share.py --package` (merged from the former scripts/pm_handoff.py).

Approving 01/02/03/06 gives pm_share.py an approved pipeline + a
.traceability.yaml spine. --package assembles per-story files in the boss
house-format by walking US-### -> FR-### -> UJ-### -> covering TC-###, plus an
overview and reference docs. It is a read-only projection: it must never touch the
gate/hash/status state machine, every file is stamped with source provenance, and
sections with no source content are flagged (not fabricated).
See docs/guides/testing.md §"Share package mode"."""
import pytest

from helpers import run_script, make_draft

pytestmark = pytest.mark.integration


_BRIEF = """## Target User
Collections users at mid-size banks.
## Overview
Overdue cases pile up because agencies aren't managed in-system.
"""

_SCOPE = """## MVP Boundary
Add and list external agencies. No allocation engine in v1.
"""

_PRD = """## User Journeys
### UJ-001 — Manage agencies
Primary user: Collections user. Traceability: US-001.
## User Stories with Acceptance Criteria
### US-001 — Add external agency
As a Collections user, I want to add agencies, so that cases can be allocated.
Traceability: UJ-001, FR-001.
Data fields: Agency Code, Status.
Acceptance: agency saved with status Sent for approval.
### US-002 — List agencies
As a user, I want to list agencies.
## Functional Requirements
FR-001 — The system stores agencies.
## Non-Functional Requirements
Performance: list loads under 2s for 10k agencies.
## Impact Analysis
Impacted components: PS, Pitboss.
"""

_QA = """## Functional Test Cases
### TC-001 — Add happy path (covers US-001, FR-001)
Given valid fields, the agency is saved.
### TC-002 — Duplicate code (covers US-001)
Given a duplicate code, an error is returned.
"""


def _approve_pipeline(pmos, proj):
    for stage, body in (("01", _BRIEF), ("02", _SCOPE), ("03", _PRD), ("06", _QA)):
        make_draft(proj, stage, body=body)
        assert run_script(pmos, "pm_approve.py", stage, cwd=proj).returncode == 0


def test_package_generates_per_story_files_with_traceability(pmos, new_project):
    proj = new_project("handoff-e2e", "A problem")
    _approve_pipeline(pmos, proj)

    res = run_script(pmos, "pm_share.py", "--package", cwd=proj)
    assert res.returncode == 0, res.stderr

    pkg = proj / "handoff"
    assert (pkg / "README.md").exists()
    assert (pkg / "00-overview.md").exists()
    assert (pkg / "epics" / "EPIC-01-mvp.md").exists()

    story = (pkg / "stories" / "US-001-add-external-agency.md").read_text()
    # Assembled from the spine: both covering test cases resolved and listed together.
    assert "TC-001" in story and "TC-002" in story
    assert "TC-001, TC-002" in story  # the joined "Covering test cases" line
    # Authored story content is carried through.
    assert "cases can be allocated" in story
    # Provenance stamp + non-canonical banner.
    assert "03-prd.md@" in story
    assert "DO NOT EDIT HERE" in story


def test_package_flags_unsourced_sections_instead_of_fabricating(pmos, new_project):
    proj = new_project("handoff-gaps", "A problem")
    _approve_pipeline(pmos, proj)
    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0

    # US-002 has no covering test case and no FR — those must be flagged, not invented.
    story = (proj / "handoff" / "stories" / "US-002-list-agencies.md").read_text()
    assert "— not captured in source —" in story


def test_package_resolves_reverse_declared_fr_and_uj_links(pmos, new_project):
    """A story that never self-cites its FR/UJ ids (only the FR/journey block
    names the story, the other direction) must still resolve them and pull in
    the test cases that trace only to that FR — the fix for backlog #12 (IMP-008,
    Bug B): forward-only regex scanning of the story's own block used to miss this."""
    prd = """## User Journeys
### UJ-001 — Manage agencies
Primary user: Collections user. Traceability: US-001.
## User Stories with Acceptance Criteria
### US-001 — Add external agency
As a Collections user, I want to add agencies, so that cases can be allocated.
## Functional Requirements
- FR-001 (Agency storage) — The system stores agencies. *(US-001)*
"""
    qa = """## Functional Test Cases
### TC-001 — Add happy path (covers FR-001)
Given valid fields, the agency is saved.
"""
    proj = new_project("handoff-reverse", "A problem")
    for stage, body in (("01", _BRIEF), ("02", _SCOPE), ("03", prd), ("06", qa)):
        make_draft(proj, stage, body=body)
        assert run_script(pmos, "pm_approve.py", stage, cwd=proj).returncode == 0

    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0
    story = (proj / "handoff" / "stories" / "US-001-add-external-agency.md").read_text()
    assert "FR-001" in story
    assert "UJ-001" in story
    assert "TC-001" in story
    assert "— not captured in source —" not in story.split("## Traceability")[-1]


def test_package_keeps_full_body_for_single_line_test_cases(pmos, new_project):
    """A single-line-bullet QA scenario (the whole TC on one line, no separate
    body lines) must still render its description in the handoff file — the fix
    for backlog #12 (IMP-008, Bug A): the old strip-first-line logic emptied
    single-line blocks entirely."""
    qa = """## Functional Test Cases
- TC-001: Verify the agency saves with a valid code. Covers US-001, FR-001.
- TC-002: Verify a duplicate code is rejected. Covers US-001.
"""
    proj = new_project("handoff-singleline", "A problem")
    for stage, body in (("01", _BRIEF), ("02", _SCOPE), ("03", _PRD), ("06", qa)):
        make_draft(proj, stage, body=body)
        assert run_script(pmos, "pm_approve.py", stage, cwd=proj).returncode == 0

    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0
    story = (proj / "handoff" / "stories" / "US-001-add-external-agency.md").read_text()
    assert "Verify the agency saves with a valid code" in story
    assert "Verify a duplicate code is rejected" in story


def test_package_overview_and_reference_docs(pmos, new_project):
    proj = new_project("handoff-ref", "A problem")
    _approve_pipeline(pmos, proj)
    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0
    pkg = proj / "handoff"

    assert "Collections users at mid-size banks" in (pkg / "00-overview.md").read_text()
    assert "Pitboss" in (pkg / "reference" / "impact-analysis.md").read_text()
    assert "under 2s" in (pkg / "reference" / "nfrs.md").read_text()


def test_package_is_read_only_and_does_not_touch_state_machine(pmos, new_project):
    """Generating the package must not change .meta.yaml, artifact hashes, or statuses."""
    proj = new_project("handoff-readonly", "A problem")
    _approve_pipeline(pmos, proj)
    meta_before = (proj / ".meta.yaml").read_text()
    prd_before = (proj / "03-prd.md").read_text()

    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0

    assert (proj / ".meta.yaml").read_text() == meta_before
    assert (proj / "03-prd.md").read_text() == prd_before


def test_package_requires_a_prd(pmos, new_project):
    """With no approved PRD, the generator refuses rather than emitting an empty package."""
    proj = new_project("handoff-noprd", "A problem")
    res = run_script(pmos, "pm_share.py", "--package", cwd=proj)
    assert res.returncode != 0
    assert "PRD" in (res.stdout + res.stderr)


def test_package_refuses_a_draft_prd(pmos, new_project):
    """A PRD that exists but is only 'draft' (not approved/edited) must be refused —
    the package projects approved decisions only, so an unreviewed PRD must not be
    published as canonical handoff."""
    proj = new_project("handoff-draftprd", "A problem")
    for stage, body in (("01", _BRIEF), ("02", _SCOPE)):
        make_draft(proj, stage, body=body)
        assert run_script(pmos, "pm_approve.py", stage, cwd=proj).returncode == 0
    make_draft(proj, "03", body=_PRD)  # draft, never approved

    res = run_script(pmos, "pm_share.py", "--package", cwd=proj)
    assert res.returncode != 0
    assert "approved" in (res.stdout + res.stderr).lower()
    assert not (proj / "handoff").exists()


def test_package_refuses_destructive_output_dir(pmos, new_project):
    """--output pointing at the project root (or cwd) must be refused before any
    rmtree, so a stray --output . can never erase .meta.yaml/approved artifacts."""
    proj = new_project("handoff-destructive", "A problem")
    _approve_pipeline(pmos, proj)

    res = run_script(pmos, "pm_share.py", "--package", "--output", ".", cwd=proj)
    assert res.returncode != 0
    assert "refusing" in (res.stdout + res.stderr).lower()
    # The project itself is untouched.
    assert (proj / ".meta.yaml").exists()
    assert (proj / "03-prd.md").exists()


def test_package_refuses_existing_unmarked_dir(pmos, new_project):
    """An existing non-empty directory that this tool did not generate (no
    .pm-os-handoff marker) must not be deleted — only a prior package is cleared."""
    proj = new_project("handoff-unmarked", "A problem")
    _approve_pipeline(pmos, proj)
    target = proj / "existing-docs"
    target.mkdir()
    (target / "keepme.md").write_text("important\n", encoding="utf-8")

    res = run_script(pmos, "pm_share.py", "--package", "--output", str(target), cwd=proj)
    assert res.returncode != 0
    assert (target / "keepme.md").exists()

    # A prior package (carrying the marker) IS safely regenerated in place.
    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0
    assert (proj / "handoff" / ".pm-os-handoff").exists()
    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0


def test_raw_mode_unchanged_by_the_merge(pmos, new_project):
    """The pre-existing raw-export behavior (single stage or all-approved,
    verbatim text) must be untouched by folding --package in alongside it."""
    proj = new_project("share-raw", "A problem")
    _approve_pipeline(pmos, proj)

    res = run_script(pmos, "pm_share.py", "03", cwd=proj)
    assert res.returncode == 0
    assert "Stage 03" in res.stdout
    assert "As a Collections user" in res.stdout
    # Raw mode must not create a handoff/ package as a side effect.
    assert not (proj / "handoff").exists()
