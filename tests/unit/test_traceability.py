"""Unit coverage for the Phase 3.5 traceability spine (`lib/traceability.py`).

Verifies the local resolver: it builds a `.traceability.yaml` index from the PRD
(requirement ids) and QA plan (TC-### scenarios + their requirement links),
answers both directions of the "which scenario covers requirement REQ-X" query,
reports coverage gaps, degrades gracefully when artifacts are prose/absent, and
preserves reserved external-ref slots across a rebuild.
"""
from pathlib import Path

import pytest

import frontmatter
import traceability as trace

pytestmark = pytest.mark.unit


def _project(tmp_path: Path) -> Path:
    (tmp_path / ".meta.yaml").write_text(
        "schema_version: 3\nproject_slug: trace-test\nstages: []\n", encoding="utf-8"
    )
    return tmp_path


def _write(root: Path, filename: str, body: str, status: str = "draft") -> None:
    frontmatter.write(str(root / filename), {"stage": filename.removesuffix(".md"), "status": status}, body)


_PRD = """# PRD
## Functional Requirements
- FR-001 — Do the thing.
- FR-002 — Audit the thing.
## User Stories with Acceptance Criteria
### US-001 — Story
ok
"""

_QA = """# QA Plan
## Functional Test Cases
### TC-001 — Primary (covers US-001, FR-001)
steps
### TC-002 — Audit (covers FR-002)
steps
"""


def test_build_index_links_requirements_and_test_cases(tmp_path):
    """build_index extracts PRD requirement ids and QA TC-### ids, and links each
    scenario to the requirement ids mentioned in its block."""
    root = _project(tmp_path)
    _write(root, "03-prd.md", _PRD)
    _write(root, "06-qa-plan.md", _QA)
    index = trace.build_index(root)
    assert set(index["requirements"]) == {"FR-001", "FR-002", "US-001"}
    assert set(index["test_cases"]) == {"TC-001", "TC-002"}
    assert index["requirements"]["FR-001"]["test_cases"] == ["TC-001"]
    assert index["test_cases"]["TC-001"]["requirements"] == ["US-001", "FR-001"]


def test_build_index_parses_ordered_list_test_cases(tmp_path):
    """build_index recognizes ordered-list test cases (`1. TC-001 — covers FR-001`),
    not only headings/bullets — so a valid QA plan in that format is not reported as
    all-uncovered. Uses the shared splitter, keeping resolver and validator in sync."""
    root = _project(tmp_path)
    _write(root, "03-prd.md", _PRD)
    qa = """# QA Plan
## Functional Test Cases
1. TC-001 — covers FR-001
2. TC-002 — covers FR-002
"""
    _write(root, "06-qa-plan.md", qa)
    index = trace.build_index(root)
    assert set(index["test_cases"]) == {"TC-001", "TC-002"}
    assert index["requirements"]["FR-001"]["test_cases"] == ["TC-001"]
    assert index["requirements"]["FR-002"]["test_cases"] == ["TC-002"]


def test_last_tc_block_does_not_absorb_trailing_sections(tmp_path):
    """Regression: the final TC block must stop at the next ## section, not run to
    end of document. Otherwise a trailing Requirement-Test Traceability table or
    Acceptance Criteria section (which name every requirement id) gets swallowed
    into the last test case, linking it to requirements it does not cover."""
    root = _project(tmp_path)
    _write(root, "03-prd.md", _PRD)
    qa = """# QA Plan
## Functional Test Cases
### TC-001 — Primary (covers FR-001)
steps
### TC-002 — Audit (covers FR-002)
steps

## Requirement-Test Traceability
| Requirement | Covering Test Cases |
|---|---|
| FR-001 | TC-001 |
| FR-002 | TC-002 |

## Acceptance Criteria
All of FR-001 and FR-002 must pass.
"""
    _write(root, "06-qa-plan.md", qa)
    index = trace.build_index(root)
    # TC-002 must NOT absorb the trailing table/criteria mentioning FR-001.
    assert index["test_cases"]["TC-002"]["requirements"] == ["FR-002"]
    assert index["requirements"]["FR-001"]["test_cases"] == ["TC-001"]
    assert index["requirements"]["FR-002"]["test_cases"] == ["TC-002"]


def test_rebuild_writes_dotfile_at_project_root(tmp_path):
    """rebuild writes a flat .traceability.yaml sibling dotfile (not a hidden dir)."""
    root = _project(tmp_path)
    _write(root, "03-prd.md", _PRD)
    _write(root, "06-qa-plan.md", _QA)
    path = trace.traceability_path(root)
    assert not path.exists()
    trace.rebuild(root)
    assert path.exists() and path.is_file()
    assert path.name == ".traceability.yaml"


def test_scenarios_for_requirement_both_directions(tmp_path):
    """The resolver answers requirement→scenarios and scenario→requirements,
    case-insensitively."""
    root = _project(tmp_path)
    _write(root, "03-prd.md", _PRD)
    _write(root, "06-qa-plan.md", _QA)
    trace.rebuild(root)
    assert trace.scenarios_for_requirement(root, "fr-001") == ["TC-001"]
    assert trace.scenarios_for_requirement(root, "FR-002") == ["TC-002"]
    assert trace.requirements_for_scenario(root, "tc-001") == ["US-001", "FR-001"]


def test_uncovered_requirements_reports_gaps(tmp_path):
    """A requirement no scenario references is reported as uncovered."""
    root = _project(tmp_path)
    # FR-002 has no covering TC.
    _write(root, "03-prd.md", _PRD)
    _write(root, "06-qa-plan.md", "## Functional Test Cases\n### TC-001 — only FR-001\nsteps\n")
    trace.rebuild(root)
    assert trace.uncovered_requirements(root) == ["FR-002", "US-001"]


def test_missing_artifacts_degrade_gracefully(tmp_path):
    """With no PRD/QA artifacts the index is empty and queries return empties
    rather than raising — existing prose projects never break the resolver."""
    root = _project(tmp_path)
    index = trace.build_index(root)
    assert index["requirements"] == {} and index["test_cases"] == {}
    assert trace.scenarios_for_requirement(root, "FR-001") == []
    assert trace.uncovered_requirements(root) == []


def test_qa_referencing_undeclared_requirement_is_kept(tmp_path):
    """A QA plan may reference a requirement the PRD did not stably id; the link is
    recorded (source=None) rather than silently dropped."""
    root = _project(tmp_path)
    _write(root, "06-qa-plan.md", "## Functional Test Cases\n### TC-001 — covers FR-999\nsteps\n")
    index = trace.build_index(root)
    assert "FR-999" in index["requirements"]
    assert index["requirements"]["FR-999"]["source"] is None
    assert index["requirements"]["FR-999"]["test_cases"] == ["TC-001"]


def test_rebuild_preserves_reserved_external_refs(tmp_path):
    """Reserved ticket/bug/code_ref slots populated by later phases survive a rebuild;
    derived fields are re-derived from the artifacts."""
    root = _project(tmp_path)
    _write(root, "03-prd.md", _PRD)
    _write(root, "06-qa-plan.md", _QA)
    index = trace.rebuild(root)
    # Simulate a later phase attaching a ticket + bug.
    index["requirements"]["FR-001"]["tickets"] = ["JIRA-42"]
    index["test_cases"]["TC-001"]["bugs"] = ["BUG-7"]
    trace.write_index(root, index)
    rebuilt = trace.rebuild(root)
    assert rebuilt["requirements"]["FR-001"]["tickets"] == ["JIRA-42"]
    assert rebuilt["test_cases"]["TC-001"]["bugs"] == ["BUG-7"]
    # Derived link still correct.
    assert rebuilt["requirements"]["FR-001"]["test_cases"] == ["TC-001"]


# --- TRD Work Breakdown tasks (Phase 3.5b, schema v2) --------------------------

_TRD = """# TRD
## Work Breakdown
### TSK-001 — Build the index
- **Implements:** US-001, FR-001
### TSK-002 — Audit logging
- **Implements:** FR-002
"""


def test_index_is_schema_v2_with_tasks_map(tmp_path):
    """The index declares schema_version 2 and always carries a tasks map."""
    root = _project(tmp_path)
    _write(root, "03-prd.md", _PRD)
    index = trace.build_index(root)
    assert index["schema_version"] == 2
    assert "tasks" in index


def test_build_index_links_tasks_and_requirements(tmp_path):
    """build_index extracts TSK-### tasks from the TRD, records what each implements,
    and back-links each requirement to the tasks that implement it."""
    root = _project(tmp_path)
    _write(root, "03-prd.md", _PRD)
    _write(root, "08-trd.md", _TRD, status="approved")
    index = trace.build_index(root)
    assert set(index["tasks"]) == {"TSK-001", "TSK-002"}
    assert index["tasks"]["TSK-001"]["implements"] == ["US-001", "FR-001"]
    assert index["tasks"]["TSK-001"]["source"] == "08-trd.md"
    assert index["requirements"]["FR-001"]["tasks"] == ["TSK-001"]
    assert index["requirements"]["FR-002"]["tasks"] == ["TSK-002"]


def test_task_resolver_both_directions(tmp_path):
    """The resolver answers requirement→tasks and task→requirements, case-insensitively."""
    root = _project(tmp_path)
    _write(root, "03-prd.md", _PRD)
    _write(root, "08-trd.md", _TRD, status="approved")
    trace.rebuild(root)
    assert trace.tasks_for_requirement(root, "fr-001") == ["TSK-001"]
    assert trace.requirements_for_task(root, "tsk-002") == ["FR-002"]


def test_task_implementing_undeclared_requirement_is_kept(tmp_path):
    """A task may implement a requirement the PRD did not stably id; the reverse link
    is recorded (source=None) rather than silently dropped."""
    root = _project(tmp_path)
    _write(root, "08-trd.md", "## Work Breakdown\n### TSK-001 — x\n- **Implements:** FR-999\n", status="approved")
    index = trace.build_index(root)
    assert "FR-999" in index["requirements"]
    assert index["requirements"]["FR-999"]["source"] is None
    assert index["requirements"]["FR-999"]["tasks"] == ["TSK-001"]


def test_rebuild_preserves_task_tickets_and_upgrades_v1(tmp_path):
    """A v1 index on disk (no tasks map, an externally-set ticket) upgrades to v2 on
    rebuild: schema bumps, the reserved ticket survives, and task tickets set by
    Phase 4b are preserved across a later rebuild."""
    root = _project(tmp_path)
    _write(root, "03-prd.md", _PRD)
    _write(root, "08-trd.md", _TRD, status="approved")
    # Simulate a legacy v1 file with a manually-populated requirement ticket.
    legacy = {
        "schema_version": 1,
        "requirements": {"FR-001": {"kind": "functional_requirement", "source": "03-prd.md",
                                    "test_cases": [], "tickets": ["JIRA-1"], "bugs": [], "code_refs": []}},
        "test_cases": {},
    }
    trace.write_index(root, legacy)
    rebuilt = trace.rebuild(root)
    assert rebuilt["schema_version"] == 2
    assert rebuilt["requirements"]["FR-001"]["tickets"] == ["JIRA-1"]
    assert rebuilt["requirements"]["FR-001"]["tasks"] == ["TSK-001"]
    # Now attach a task ticket (Phase 4b) and confirm it survives the next rebuild.
    rebuilt["tasks"]["TSK-001"]["tickets"] = ["JIRA-9"]
    trace.write_index(root, rebuilt)
    again = trace.rebuild(root)
    assert again["tasks"]["TSK-001"]["tickets"] == ["JIRA-9"]
    assert again["tasks"]["TSK-001"]["implements"] == ["US-001", "FR-001"]


def test_missing_trd_yields_empty_tasks(tmp_path):
    """With no TRD the tasks map is empty and task queries return empties rather than
    raising — TRD is an optional capstone."""
    root = _project(tmp_path)
    _write(root, "03-prd.md", _PRD)
    index = trace.build_index(root)
    assert index["tasks"] == {}
    assert trace.tasks_for_requirement(root, "FR-001") == []
    assert trace.requirements_for_task(root, "TSK-001") == []


def test_draft_or_stale_trd_tasks_excluded_from_index(tmp_path):
    """Only an approved TRD's tasks enter the index. A draft/stale TRD contributes
    nothing — so re-approving an upstream stage (which marks 08 stale) drops its now
    obsolete task links on rebuild, and a handoff export never sees them."""
    root = _project(tmp_path)
    _write(root, "03-prd.md", _PRD)
    _write(root, "08-trd.md", _TRD, status="draft")
    index = trace.build_index(root)
    assert index["tasks"] == {}
    assert index["requirements"]["FR-001"]["tasks"] == []
    # Flip to stale — still excluded.
    _write(root, "08-trd.md", _TRD, status="stale")
    assert trace.build_index(root)["tasks"] == {}
    # Approve — now indexed.
    _write(root, "08-trd.md", _TRD, status="approved")
    assert set(trace.build_index(root)["tasks"]) == {"TSK-001", "TSK-002"}


def test_task_outside_work_breakdown_is_not_indexed(tmp_path):
    """A TSK-### mentioned outside the ## Work Breakdown section (e.g. under Open
    Technical Questions) is not indexed as a delivery task."""
    root = _project(tmp_path)
    _write(root, "03-prd.md", _PRD)
    body = (
        "## Work Breakdown\n"
        "### TSK-001 — real task\n- **Implements:** US-001\n"
        "## Open Technical Questions\n"
        "- TSK-999 investigate migration risk (not a delivery task)\n"
    )
    _write(root, "08-trd.md", body, status="approved")
    index = trace.build_index(root)
    assert set(index["tasks"]) == {"TSK-001"}
    assert "TSK-999" not in index["tasks"]
