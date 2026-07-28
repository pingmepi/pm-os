"""Interop between scripts/pm_handoff.py (Jira export) and scripts/pm_share.py
--package (handoff package), both invoked via the single /pm-handoff skill.

Both scripts default to writing into the same ./handoff/ directory. Before the
audience-folder rework, this was a live collision hazard: pm_share.py's package
build used to wipe-and-rebuild the *entire* handoff/ directory (guarded by a
.pm-os-handoff marker at its root), while pm_handoff.py's writer never wrote
that marker — so a plan/export that ran first would make a later --package run
refuse ("not a PM-OS handoff folder"). The audience-folder rework moved the
destructive wipe-and-marker guard one level down, to handoff/<audience>/, and
made the handoff/ root itself a plain non-destructive mkdir — so
jira-plan.*/jira-import.* (which live at the root, never inside an audience
folder) can no longer collide with a package build, in either run order. This
was previously untested; these tests close that gap.
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

_PRD = """## Product Epics
### EPIC-001 — Agency onboarding
**Outcome:** Collections users can add external agencies.
**Scope:** Agency creation and approval state.
**Success signal:** An agency is saved for approval.
## User Stories with Acceptance Criteria
### US-001 — Add external agency
Priority: Must
Epic: EPIC-001
As a Collections user, I want to add agencies, so that cases can be allocated.
## Functional Requirements
FR-001 — The system stores agencies.
Priority: Must
Epic: EPIC-001
"""


def _approve_pipeline(pmos, proj):
    for stage, body in (("01", _BRIEF), ("02", _SCOPE), ("03", _PRD)):
        make_draft(proj, stage, body=body)
        assert run_script(pmos, "pm_approve.py", stage, cwd=proj).returncode == 0


def test_jira_plan_then_package_does_not_collide(pmos, new_project):
    """pm_handoff.py plan first (writes handoff/jira-plan.*), then
    pm_share.py --package — the package build must succeed and the jira-plan
    files must be left byte-identical."""
    proj = new_project("interop-jira-first", "A problem")
    _approve_pipeline(pmos, proj)

    assert run_script(pmos, "pm_handoff.py", "plan", cwd=proj).returncode == 0
    plan_md_before = (proj / "handoff" / "jira-plan.md").read_text()
    plan_json_before = (proj / "handoff" / "jira-plan.json").read_text()

    res = run_script(pmos, "pm_share.py", "--package", cwd=proj)
    assert res.returncode == 0, res.stderr

    assert (proj / "handoff" / "jira-plan.md").read_text() == plan_md_before
    assert (proj / "handoff" / "jira-plan.json").read_text() == plan_json_before
    assert (proj / "handoff" / "dev" / "stories" / "US-001-add-external-agency.md").exists()


def test_package_then_jira_plan_does_not_collide(pmos, new_project):
    """The reverse order — pm_share.py --package first, then pm_handoff.py plan —
    must also succeed cleanly (this direction already worked before the rework,
    since --package used to write the marker; this locks in that it still does)."""
    proj = new_project("interop-package-first", "A problem")
    _approve_pipeline(pmos, proj)

    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0
    story_before = (proj / "handoff" / "dev" / "stories" / "US-001-add-external-agency.md").read_text()

    res = run_script(pmos, "pm_handoff.py", "plan", cwd=proj)
    assert res.returncode == 0, res.stderr

    assert (proj / "handoff" / "jira-plan.json").exists()
    assert (proj / "handoff" / "dev" / "stories" / "US-001-add-external-agency.md").read_text() == story_before


def test_audience_scoped_package_survives_either_order(pmos, new_project):
    """A scoped --audience dev rebuild must not disturb jira-plan.* regardless of
    whether the Jira plan was built before or after it — the two never share a
    directory anymore (jira-plan.* at the handoff/ root; --audience content one
    level down)."""
    proj = new_project("interop-audience-scoped", "A problem")
    _approve_pipeline(pmos, proj)

    assert run_script(pmos, "pm_handoff.py", "plan", cwd=proj).returncode == 0
    plan_before = (proj / "handoff" / "jira-plan.json").read_text()

    assert run_script(pmos, "pm_share.py", "--package", "--audience", "dev", cwd=proj).returncode == 0
    assert (proj / "handoff" / "jira-plan.json").read_text() == plan_before
    assert (proj / "handoff" / "dev" / ".pm-os-handoff").exists()

    # Re-running the Jira plan afterwards must also be unaffected by the audience folder.
    assert run_script(pmos, "pm_handoff.py", "plan", cwd=proj).returncode == 0
    assert (proj / "handoff" / "dev" / ".pm-os-handoff").exists()
