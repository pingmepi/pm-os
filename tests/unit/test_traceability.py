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


def _write(root: Path, filename: str, body: str) -> None:
    frontmatter.write(str(root / filename), {"stage": filename.removesuffix(".md"), "status": "draft"}, body)


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
