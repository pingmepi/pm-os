"""The readiness record end to end (backlog #74): `pm_readiness.py`, its place
in `/pm-check` and `/pm-status`, the package carrying it, and the release
check blocking on overdue items, all without touching the stage state
machine. See docs/guides/testing.md §T2."""
import pytest

from helpers import make_draft, run_script, stage_status

pytestmark = pytest.mark.integration

_PRD = """## Product Epics
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

_QA = """## Functional Test Cases
### TC-001 — Add happy path (covers US-001, FR-001)
Given valid fields, the agency is saved.
"""

_RECORD = """schema_version: 1
milestones: [M0, M1]
current_milestone: M0
eval_sets:
  - id: EVAL-001
    ai_step: Interpret agency notes
    requirement: FR-001
    reviewer: Anika Kaur
    starter_count: 30
    target_count: 120
    due: {due}
    status: {status}
"""


def _approved(pmos, new_project, slug):
    proj = new_project(slug, "A problem")
    for stage, body in (("01", "## Overview\nAgencies.\n"), ("02", "## MVP Boundary\nAdd.\n"),
                        ("03", _PRD), ("06", _QA)):
        make_draft(proj, stage, body=body)
        assert run_script(pmos, "pm_approve.py", stage, cwd=proj).returncode == 0
    return proj


def test_init_and_check_and_pm_check_report_the_record(pmos, new_project):
    """`init` writes the template once; `check` passes on it and fails (exit 1)
    on an invalid item; `/pm-check` shows a Readiness section and counts its
    errors toward its own exit code."""
    proj = _approved(pmos, new_project, "ready-check")
    res = run_script(pmos, "pm_readiness.py", "init", cwd=proj)
    assert res.returncode == 0 and "Created readiness.yaml" in res.stdout
    assert "Kept existing" in run_script(pmos, "pm_readiness.py", "init", cwd=proj).stdout
    res = run_script(pmos, "pm_readiness.py", "check", cwd=proj)
    assert res.returncode == 0, res.stdout

    (proj / "readiness.yaml").write_text(_RECORD.format(due="M7", status="needed"), encoding="utf-8")
    res = run_script(pmos, "pm_readiness.py", "check", cwd=proj)
    assert res.returncode == 1 and "READINESS_MILESTONE_UNKNOWN EVAL-001" in res.stdout
    res = run_script(pmos, "pm_check.py", cwd=proj)
    assert "Readiness Record (readiness.yaml)" in res.stdout
    assert "Readiness: 1 error(s)" in res.stdout
    assert res.returncode == 1


def test_editing_the_record_never_touches_stage_state(pmos, new_project):
    """Ungated: writing and rewriting readiness.yaml leaves every stage approved
    and logs no approval or staleness event."""
    proj = _approved(pmos, new_project, "ready-ungated")
    before = (proj / "telemetry.jsonl").read_text(encoding="utf-8")
    (proj / "readiness.yaml").write_text(_RECORD.format(due="M0", status="needed"), encoding="utf-8")
    run_script(pmos, "pm_readiness.py", "check", cwd=proj)
    (proj / "readiness.yaml").write_text(_RECORD.format(due="M1", status="in_review"), encoding="utf-8")
    run_script(pmos, "pm_status.py", cwd=proj)
    for stage in ("01", "02", "03", "06"):
        assert stage_status(proj, stage) == "approved"
    assert (proj / "telemetry.jsonl").read_text(encoding="utf-8") == before


def test_overdue_eval_set_blocks_the_package_until_starter_ready(pmos, new_project):
    """An eval set due at the current milestone and still `needed` blocks
    `--package` (READINESS_EVAL_SET_NOT_READY). Once it is `starter_ready` the
    package publishes, every audience folder carries readiness.yaml, and the
    README links it under "Still owed". /pm-status shows the counts."""
    proj = _approved(pmos, new_project, "ready-gate")
    (proj / "readiness.yaml").write_text(_RECORD.format(due="M0", status="needed"), encoding="utf-8")
    res = run_script(pmos, "pm_status.py", cwd=proj)
    assert "Readiness: 1 eval set(s) not starter-ready" in res.stdout and "1 overdue" in res.stdout
    res = run_script(pmos, "pm_share.py", "--package", cwd=proj)
    assert res.returncode != 0
    assert "READINESS_EVAL_SET_NOT_READY" in res.stderr and "EVAL-001" in res.stderr
    assert not (proj / "handoff").exists()

    (proj / "readiness.yaml").write_text(_RECORD.format(due="M0", status="starter_ready"), encoding="utf-8")
    res = run_script(pmos, "pm_share.py", "--package", cwd=proj)
    assert res.returncode == 0, res.stderr
    for audience in ("dev", "design", "qa", "business"):
        folder = proj / "handoff" / audience
        assert (folder / "readiness.yaml").read_text(encoding="utf-8") == \
            (proj / "readiness.yaml").read_text(encoding="utf-8")
        assert "[Readiness record](readiness.yaml)" in (folder / "README.md").read_text(encoding="utf-8")
