"""Unit tests for lib/readiness.py — the ungated readiness record of eval sets,
test inputs and open decisions owed to the build team (backlog #74; PM
decision 2026-10-21: milestone-based YAML the agent edits, Python only
scaffolds and validates). See docs/guides/testing.md §5 (T1)."""
import pytest
import yaml

import readiness

pytestmark = pytest.mark.unit


def _record(**overrides):
    data = {
        "schema_version": 1,
        "milestones": ["M0", "M1", "M2"],
        "current_milestone": "M1",
        "eval_sets": [{
            "id": "EVAL-001", "ai_step": "Interpret recommendations", "requirement": "FR-001",
            "reviewer": "Anika Kaur", "starter_count": 30, "target_count": 120, "have_count": 0,
            "due": "M1", "status": "needed",
        }],
        "test_inputs": [{
            "id": "TI-001", "purpose": "Bot-protected page", "supplier": "Karan",
            "needed_by": "M2", "file": "inputs/jardiance.html", "status": "requested",
        }],
        "open_decisions": [{
            "id": "OD-01", "question": "Emoji-only sentences?", "epics": ["EPIC-001"],
            "stories": ["US-001"], "owner": "Karan", "decide_by": "M0", "blocking": True,
            "status": "open",
        }],
    }
    data.update(overrides)
    return data


def test_scaffold_writes_a_valid_template_once(tmp_path):
    """`scaffold` writes a commented template that loads and validates clean,
    and never overwrites an existing file."""
    path, created = readiness.scaffold(tmp_path)
    assert created and path.name == "readiness.yaml"
    data, problem = readiness.load(path)
    assert problem is None and readiness.validate(data) == []
    path.write_text("schema_version: 1\nmilestones: [M0]\n", encoding="utf-8")
    _path, created = readiness.scaffold(tmp_path)
    assert not created and "milestones: [M0]" in path.read_text(encoding="utf-8")


def test_a_complete_record_is_valid(tmp_path):
    """A record with every required field, known milestones and real PRD ids has no issues."""
    assert readiness.validate(_record(), {"FR-001", "EPIC-001", "US-001"}) == []


def test_structural_problems_are_errors():
    """Missing fields, bad id formats, duplicates, unknown statuses and
    milestones, and non-integer counts are each reported as errors."""
    data = _record()
    data["eval_sets"].append(dict(data["eval_sets"][0], status="done", starter_count="thirty"))
    data["test_inputs"][0].pop("supplier")
    data["open_decisions"][0].update(id="DECISION-1", decide_by="M9")
    codes = {issue.code for issue in readiness.validate(data) if issue.severity == "error"}
    assert codes == {
        "READINESS_ID_DUPLICATE", "READINESS_STATUS_INVALID", "READINESS_COUNT_INVALID",
        "READINESS_FIELDS_MISSING", "READINESS_ID_FORMAT", "READINESS_MILESTONE_UNKNOWN",
    }


def test_due_milestone_is_only_required_once_milestones_exist():
    """A freshly seeded record with no milestones may leave due dates empty; once
    `milestones` is set, a missing due milestone is an error."""
    data = _record(milestones=[], current_milestone=None)
    data["eval_sets"][0]["due"] = None
    assert not [i for i in readiness.validate(data) if i.severity == "error"]
    data["milestones"] = ["M0", "M1"]
    assert any(i.code == "READINESS_FIELDS_MISSING" and i.item == "EVAL-001"
               for i in readiness.validate(data))


def test_role_reviewers_and_unknown_ids_are_warnings():
    """APEX asked for a *named* strategist: a role as reviewer warns, and so does
    a requirement/epic/story id the PRD does not declare."""
    data = _record()
    data["eval_sets"][0]["reviewer"] = "Strategist"
    issues = readiness.validate(data, {"FR-001"})
    assert {i.code for i in issues} == {"READINESS_REVIEWER_IS_A_ROLE", "READINESS_UNKNOWN_REFERENCE"}
    assert all(i.severity == "warning" for i in issues)


def test_overdue_follows_milestone_order():
    """At M1: the eval set due M1 and still `needed` is overdue, the blocking
    decision due M0 is overdue, the input needed at M2 is not. Ready, received,
    decided or non-blocking items are never overdue."""
    late = readiness.overdue(_record())
    assert [(i["section"], i["id"]) for i in late] == [("eval_sets", "EVAL-001"), ("open_decisions", "OD-01")]
    data = _record()
    data["eval_sets"][0]["status"] = "starter_ready"
    data["open_decisions"][0]["blocking"] = False
    assert readiness.overdue(data) == []
    assert readiness.overdue(_record(current_milestone=None)) == []


def test_invalid_yaml_is_reported_not_raised(tmp_path):
    """A file that is not YAML, or not a mapping, comes back as one issue."""
    path = tmp_path / "readiness.yaml"
    path.write_text("eval_sets: [\n", encoding="utf-8")
    data, problem = readiness.load(path)
    assert data is None and problem.code == "READINESS_INVALID_YAML"
    path.write_text(yaml.safe_dump(["a", "b"]), encoding="utf-8")
    assert readiness.load(path)[1].code == "READINESS_INVALID_YAML"
    assert readiness.load(tmp_path / "missing.yaml") == (None, None)


def test_summary_and_pending_files():
    """`summary` counts what /pm-status shows; `pending_files` lists test-input
    files still owed, as POSIX paths."""
    assert readiness.summary(_record()) == {
        "eval_sets_not_ready": 1, "test_inputs_owed": 1, "open_decisions": 1, "overdue": 2,
    }
    assert readiness.pending_files(_record()) == {"inputs/jardiance.html"}


def test_normalize_rel_strips_only_a_leading_dot_slash():
    """Stack #93 review: `lstrip("./")` stripped every leading dot and slash,
    turning `.fixtures/a.csv` into `fixtures/a.csv` and `../x` into `x`."""
    assert readiness.normalize_rel("./inputs/a.csv") == "inputs/a.csv"
    assert readiness.normalize_rel(".\\.fixtures\\a.csv") == ".fixtures/a.csv"
    assert readiness.normalize_rel("../x/b.csv") == "../x/b.csv"
