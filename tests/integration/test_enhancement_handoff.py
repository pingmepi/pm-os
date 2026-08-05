"""E2 exports only enhancement work plus the minimum ancestor closure."""
import json
import csv
from pathlib import Path

import pytest
import yaml

from helpers import make_draft, run_script

pytestmark = pytest.mark.integration


BASELINE_PRD = """## Product Epics
### EPIC-001 — Core
Outcome: Preserve core.
### EPIC-002 — Search
Outcome: Improve search.
## User Stories with Acceptance Criteria
### US-001 — Use core
Epic: EPIC-001
Implements FR-001.
### US-002 — Search records
Epic: EPIC-002
Implements FR-002.
## Functional Requirements
- **FR-001 (must):** Keep core behavior.
  - Epic: EPIC-001
- **FR-002 (must):** Search records.
  - Epic: EPIC-002
- **FR-003 (should):** Use the legacy search switch.
  - Epic: EPIC-002
"""

CURRENT_PRD = """## Product Epics
### EPIC-001 — Core
Outcome: Preserve core.
### EPIC-002 — Search
Outcome: Improve search.
## User Stories with Acceptance Criteria
### US-001 — Use core
Epic: EPIC-001
Implements FR-001.
### US-002 — Search records faster
Change type: modified
Epic: EPIC-002
Implements FR-002 and FR-004.
## Functional Requirements
- **FR-001 (must):** Keep core behavior.
  - Epic: EPIC-001
- **FR-002 (must):** Search records using the indexed path.
  Change type: modified
  - Epic: EPIC-002
- **FR-004 (must):** Record search latency.
  Change type: new
  - Epic: EPIC-002
"""


def _approve(pmos, project: Path, stage: str, body: str):
    make_draft(project, stage, body=body)
    result = run_script(pmos, "pm_approve.py", stage, cwd=project)
    assert result.returncode == 0, result.stderr


def _enhancement_project(pmos, new_project, tmp_path):
    project = new_project("enhancement-handoff", "Improve record search.")
    assert run_script(pmos, "pm_approve.py", "00", cwd=project).returncode == 0
    _approve(pmos, project, "03", BASELINE_PRD)
    ask = project / "ask.md"
    ask.write_text("Improve record search without changing core.\n", encoding="utf-8")
    started = run_script(pmos, "pm_enhance.py", "start", "--ask-file", str(ask), cwd=project)
    assert started.returncode == 0, started.stderr
    context_path = project / ".enhancements" / "EH-001" / "context.yaml"
    context = yaml.safe_load(context_path.read_text(encoding="utf-8"))
    context["boundary"].update({
        "recorded_at": "2026-08-03T00:00:00+00:00",
        "current_behavior": "Legacy search",
        "target_behavior": "Indexed search with latency telemetry",
        "affected_ids": ["US-002", "FR-002", "FR-003", "FR-004"],
        "affected_surfaces": ["api", "data", "service"],
        "non_touch_surfaces": ["core workflow"],
        "regression_invariants": ["FR-001 core behavior remains unchanged"],
        "compatibility_migration": ["Old and new indexes coexist during rollout"],
        "rollout": ["Canary indexed search"],
        "rollback": ["Disable indexed-search flag"],
    })
    context_path.write_text(yaml.safe_dump(context, sort_keys=False), encoding="utf-8")
    _approve(pmos, project, "03", CURRENT_PRD)
    return project


def test_jira_plan_is_delta_only_with_removal_and_ancestor_closure(
    pmos, new_project, tmp_path,
):
    project = _enhancement_project(pmos, new_project, tmp_path)

    result = run_script(pmos, "pm_handoff.py", "plan", cwd=project)

    assert result.returncode == 0, result.stderr
    plan = json.loads((project / "handoff" / "jira-plan.json").read_text())
    items = {item["ref"]: item for item in plan["items"]}
    assert set(items) == {"EPIC-002", "US-002", "FR-002", "FR-003", "FR-004"}
    assert items["EPIC-002"]["change_type"] == "ancestor"
    assert items["FR-003"]["change_type"] == "removed"
    assert items["FR-003"]["description"].startswith("Removal work")
    assert items["FR-002"]["enhancement"]["affected_surfaces"] == ["api", "data", "service"]
    assert plan["enhancement"]["cycle_id"] == "EH-001"
    assert "FR-001" not in items and "US-001" not in items and "EPIC-001" not in items

    exported = run_script(pmos, "pm_handoff.py", "export", cwd=project)
    assert exported.returncode == 0, exported.stderr
    with (project / "handoff" / "jira-import.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    description = next(row["Description"] for row in rows if row["PM-OS Id"] == "FR-002")
    assert "Change type: modified" in description
    assert "Affected surfaces:* api, data, service" in description
    assert "Must not break:* FR-001 core behavior remains unchanged" in description
    assert "Old and new indexes coexist" in description
    assert "Disable indexed-search flag" in description


def test_readable_package_excludes_unaffected_baseline_story(
    pmos, new_project, tmp_path,
):
    project = _enhancement_project(pmos, new_project, tmp_path)

    result = run_script(pmos, "pm_share.py", "--package", "--audience", "dev", cwd=project)

    assert result.returncode == 0, result.stderr
    story_files = {path.name for path in (project / "handoff" / "dev" / "stories").glob("*.md")}
    epic_files = {path.name for path in (project / "handoff" / "dev" / "epics").glob("*.md")}
    assert any(name.startswith("US-002-") for name in story_files)
    assert not any(name.startswith("US-001-") for name in story_files)
    assert any(name.startswith("EPIC-002-") for name in epic_files)
    assert not any(name.startswith("EPIC-001-") for name in epic_files)
    readme = (project / "handoff" / "dev" / "README.md").read_text()
    assert "EH-001" in readme
    assert "FR-003" in readme and "removed" in readme
