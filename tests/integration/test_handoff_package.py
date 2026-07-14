"""Handoff package (Phase 4a) — the readable projection built by scripts/pm_handoff.py.

Approving 01/02/03/06 gives pm_handoff.py an approved pipeline + a
.traceability.yaml spine. The generator assembles per-story files in the boss
house-format by walking US-### -> FR-### -> UJ-### -> covering TC-###, plus an
overview and reference docs. It is a read-only projection: it must never touch the
gate/hash/status state machine, every file is stamped with source provenance, and
sections with no source content are flagged (not fabricated).
See docs/guides/testing.md §"Handoff package"."""
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


def test_handoff_generates_per_story_files_with_traceability(pmos, new_project):
    proj = new_project("handoff-e2e", "A problem")
    _approve_pipeline(pmos, proj)

    res = run_script(pmos, "pm_handoff.py", cwd=proj)
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


def test_handoff_flags_unsourced_sections_instead_of_fabricating(pmos, new_project):
    proj = new_project("handoff-gaps", "A problem")
    _approve_pipeline(pmos, proj)
    assert run_script(pmos, "pm_handoff.py", cwd=proj).returncode == 0

    # US-002 has no covering test case and no FR — those must be flagged, not invented.
    story = (proj / "handoff" / "stories" / "US-002-list-agencies.md").read_text()
    assert "— not captured in source —" in story


def test_handoff_overview_and_reference_docs(pmos, new_project):
    proj = new_project("handoff-ref", "A problem")
    _approve_pipeline(pmos, proj)
    assert run_script(pmos, "pm_handoff.py", cwd=proj).returncode == 0
    pkg = proj / "handoff"

    assert "Collections users at mid-size banks" in (pkg / "00-overview.md").read_text()
    assert "Pitboss" in (pkg / "reference" / "impact-analysis.md").read_text()
    assert "under 2s" in (pkg / "reference" / "nfrs.md").read_text()


def test_handoff_is_read_only_and_does_not_touch_state_machine(pmos, new_project):
    """Generating the handoff must not change .meta.yaml, artifact hashes, or statuses."""
    proj = new_project("handoff-readonly", "A problem")
    _approve_pipeline(pmos, proj)
    meta_before = (proj / ".meta.yaml").read_text()
    prd_before = (proj / "03-prd.md").read_text()

    assert run_script(pmos, "pm_handoff.py", cwd=proj).returncode == 0

    assert (proj / ".meta.yaml").read_text() == meta_before
    assert (proj / "03-prd.md").read_text() == prd_before


def test_handoff_requires_a_prd(pmos, new_project):
    """With no approved PRD, the generator refuses rather than emitting an empty package."""
    proj = new_project("handoff-noprd", "A problem")
    res = run_script(pmos, "pm_handoff.py", cwd=proj)
    assert res.returncode != 0
    assert "PRD" in (res.stdout + res.stderr)
