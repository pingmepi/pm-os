"""Phase 4b — the Jira handoff export end to end (scripts/pm_handoff.py).

`plan` reads the approved PRD (+ approved TRD) and writes a dry-run ticket map
(handoff/jira-plan.{md,json}) with no network; `record` writes created ticket
keys back into `.traceability.yaml` and logs a `handoff_exported` event. The
actual tracker (MCP) calls live in the pm-handoff skill and are not exercised
here. See docs/guides/testing.md §5 (Phase 4b)."""
import json

import pytest
import yaml

from helpers import run_script, make_draft

pytestmark = pytest.mark.integration


_PRD_BODY = """## User Stories with Acceptance Criteria
### US-001 — Rep sees only approved content
Implements FR-001.
### US-002 — Rep filters by specialty
Covers FR-002.
## Functional Requirements
- **FR-001 (must):** Surface only MLR-approved assets.
- **FR-002 (should):** Filter content by specialty.
- **FR-003 (could):** Log every content view.
"""

_TRD_BODY = """## Architecture
Prose.
## Work Breakdown
### TSK-001 — Build the approved-content query
- **Implements:** FR-001
### TSK-002 — Add the specialty filter
- **Implements:** FR-002
### TSK-003 — Audit log writer
- **Implements:** FR-003
## Open Technical Questions
- TSK-999 not a real task
"""


def _approve(pmos, proj, stage_id, body):
    make_draft(proj, stage_id, body=body)
    res = run_script(pmos, "pm_approve.py", stage_id, cwd=proj)
    assert res.returncode == 0, res.stderr


def test_plan_blocks_when_prd_not_approved(pmos, new_project):
    """`plan` refuses to run while the PRD is not approved — the export projects
    approved decisions only."""
    proj = new_project("ho-gate", "A problem")
    res = run_script(pmos, "pm_handoff.py", "plan", cwd=proj)
    assert res.returncode != 0
    assert "not approved" in (res.stdout + res.stderr).lower()
    assert not (proj / "handoff" / "jira-plan.json").exists()


def test_plan_maps_stories_requirements_and_tasks(pmos, new_project):
    """`plan` maps each user story to an epic, its functional requirements to child
    stories, and each approved TRD task to a child task under the epic that owns the
    requirement it implements; unowned items go to an Unassigned bucket, and a TSK
    outside the Work Breakdown is excluded."""
    proj = new_project("ho-plan", "A problem")
    _approve(pmos, proj, "03", _PRD_BODY)
    _approve(pmos, proj, "08", _TRD_BODY)

    res = run_script(pmos, "pm_handoff.py", "plan", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert (proj / "handoff" / "jira-plan.md").exists()

    plan = json.loads((proj / "handoff" / "jira-plan.json").read_text())
    assert plan["tracker"] == "jira"
    assert plan["counts"] == {"epics": 2, "stories": 3, "tasks": 3, "unassigned": 2}

    items = {i["ref"]: i for i in plan["items"]}
    # US -> Epic, its FR -> child Story, its TSK -> child Task.
    assert items["US-001"]["type"] == "Epic"
    assert items["FR-001"]["type"] == "Story" and items["FR-001"]["parent_ref"] == "US-001"
    assert items["TSK-001"]["type"] == "Task" and items["TSK-001"]["parent_ref"] == "US-001"
    assert items["TSK-001"]["implements"] == ["FR-001"]
    # FR-003 / TSK-003 have no owning story -> Unassigned.
    assert items["FR-003"]["parent_ref"] == "UNASSIGNED"
    assert items["TSK-003"]["parent_ref"] == "UNASSIGNED"
    # A TSK only under Open Technical Questions is never a delivery task.
    assert "TSK-999" not in items


def test_plan_without_trd_exports_prd_only(pmos, new_project):
    """With no approved TRD, `plan` still exports PRD stories + functional requirements
    and simply carries no tasks."""
    proj = new_project("ho-notrd", "A problem")
    _approve(pmos, proj, "03", _PRD_BODY)

    res = run_script(pmos, "pm_handoff.py", "plan", cwd=proj)
    assert res.returncode == 0, res.stderr
    plan = json.loads((proj / "handoff" / "jira-plan.json").read_text())
    assert plan["counts"]["tasks"] == 0
    assert plan["source_stamps"]["trd"] is None
    assert plan["counts"]["stories"] == 3


def test_plan_excludes_tasks_when_trd_no_longer_approved(pmos, new_project):
    """Regression (Codex PR #36 P1): after the TRD is approved, an implicit
    re-approval of an edited PRD cascades stage 08 to stale *without* rebuilding
    .traceability.yaml — leaving task entries on disk. `plan` must not export those:
    it rebuilds the index fresh and gates tasks on the live meta status."""
    import project
    proj = new_project("ho-stale", "A problem")
    _approve(pmos, proj, "03", _PRD_BODY)
    _approve(pmos, proj, "08", _TRD_BODY)
    # The on-disk index has tasks after approving 08.
    data = yaml.safe_load((proj / ".traceability.yaml").read_text())
    assert data.get("tasks"), "precondition: approved TRD populated the index"

    # Simulate the implicit-reapproval cascade: stage 08 -> stale in meta (and its
    # frontmatter), but the derived .traceability.yaml is deliberately left unchanged.
    meta = project.load_meta(proj)
    project.get_stage(meta, "08")["status"] = "stale"
    project.save_meta(meta, proj)
    import frontmatter as fm_mod
    fm, body = fm_mod.read(str(project.artifact_path(proj, "08")))
    fm["status"] = "stale"
    fm_mod.write(str(project.artifact_path(proj, "08")), fm, body)
    assert yaml.safe_load((proj / ".traceability.yaml").read_text()).get("tasks"), \
        "precondition: stale index still on disk"

    res = run_script(pmos, "pm_handoff.py", "plan", cwd=proj)
    assert res.returncode == 0, res.stderr
    plan = json.loads((proj / "handoff" / "jira-plan.json").read_text())
    assert plan["counts"]["tasks"] == 0, "must not export tasks from a stale TRD"
    assert plan["source_stamps"]["trd"] is None
    assert not any(i["type"] == "Task" for i in plan["items"])


def test_record_writes_ticket_keys_and_logs_telemetry(pmos, new_project):
    """`record` writes each created ticket key into the matching requirement's/task's
    `tickets` slot in .traceability.yaml, skips ids not in the index, and logs a
    handoff_exported telemetry event carrying refs/counts/keys only."""
    proj = new_project("ho-record", "A problem")
    _approve(pmos, proj, "03", _PRD_BODY)
    _approve(pmos, proj, "08", _TRD_BODY)
    run_script(pmos, "pm_handoff.py", "plan", cwd=proj)

    created = '{"US-001": "RA-1", "FR-001": "RA-2", "TSK-001": "RA-3", "BOGUS-9": "RA-9"}'
    res = run_script(pmos, "pm_handoff.py", "record", cwd=proj, stdin=created)
    assert res.returncode == 0, res.stderr
    assert "BOGUS-9" in res.stdout  # reported as skipped

    data = yaml.safe_load((proj / ".traceability.yaml").read_text())
    assert data["requirements"]["US-001"]["tickets"] == ["RA-1"]
    assert data["requirements"]["FR-001"]["tickets"] == ["RA-2"]
    assert data["tasks"]["TSK-001"]["tickets"] == ["RA-3"]

    # Ticket refs survive a later rebuild of the derived index.
    assert run_script(pmos, "pm_trace.py", "rebuild", cwd=proj).returncode == 0
    data = yaml.safe_load((proj / ".traceability.yaml").read_text())
    assert data["requirements"]["US-001"]["tickets"] == ["RA-1"]
    assert data["tasks"]["TSK-001"]["tickets"] == ["RA-3"]

    events = [json.loads(l) for l in (proj / "telemetry.jsonl").read_text().splitlines() if l.strip()]
    handoff = [e for e in events if e.get("event_type") == "handoff_exported"]
    assert handoff, "record must log a handoff_exported event"
    payload = handoff[-1]["payload"]
    assert payload["tracker"] == "jira"
    assert payload["created_count"] == 3
    assert payload["tickets"] == {"US-001": "RA-1", "FR-001": "RA-2", "TSK-001": "RA-3"}


def _csv_rows(proj):
    import csv as _csv
    with open(proj / "handoff" / "jira-import.csv", newline="", encoding="utf-8") as handle:
        return list(_csv.reader(handle))


def test_export_csv_writes_importer_file_and_guide(pmos, new_project):
    """`export` renders the same plan as a Jira CSV-importer file plus an import guide,
    entirely offline: one row per exportable item, epics before their children, and the
    stable id carried both as a column and as a `pm-os-<id>` label so created keys can be
    recovered and fed back to `record`."""
    proj = new_project("ho-csv", "A problem")
    _approve(pmos, proj, "03", _PRD_BODY)
    _approve(pmos, proj, "08", _TRD_BODY)

    res = run_script(pmos, "pm_handoff.py", "export", cwd=proj)
    assert res.returncode == 0, res.stderr
    guide = (proj / "handoff" / "jira-import-README.md").read_text()
    assert "Import issues from CSV" in guide and "pm_handoff.py record" in guide

    rows = _csv_rows(proj)
    header, body = rows[0], rows[1:]
    assert header == ["Issue Id", "Parent Id", "Issue Type", "Summary", "Description",
                      "Labels", "Labels", "PM-OS Id"]
    by_ref = {row[7]: row for row in body}
    # 2 epics + 3 stories + 3 tasks; the synthetic UNASSIGNED epic is never a ticket.
    assert len(body) == 8 and "UNASSIGNED" not in by_ref
    assert [row[2] for row in body[:2]] == ["Epic", "Epic"], "epics must precede their children"

    # Parent Id points at the owning epic's Issue Id, inside this file.
    assert by_ref["FR-001"][1] == by_ref["US-001"][0]
    assert by_ref["TSK-001"][1] == by_ref["US-001"][0]
    # An item with no owning story is exported parentless rather than under a fake epic.
    assert by_ref["FR-003"][1] == ""
    # Labels: the marker + the stable-id label used to map keys back.
    assert by_ref["US-001"][5] == "pm-os" and by_ref["US-001"][6] == "pm-os-us-001"


def test_export_csv_descriptions_are_jira_markup_with_provenance(pmos, new_project):
    """Descriptions are converted from Markdown to Jira wiki markup and carry a
    provenance footer naming the source artifact, so a ticket never reads as canonical."""
    proj = new_project("ho-csv-markup", "A problem")
    _approve(pmos, proj, "03", "## User Stories with Acceptance Criteria\n"
                               "### US-001 — Rep sees **approved** content\n"
                               "- Happy path: covered by `FR-001`\n"
                               "## Functional Requirements\n"
                               "- **FR-001 (must):** Surface approved assets.\n")
    assert run_script(pmos, "pm_handoff.py", "export", cwd=proj).returncode == 0

    description = {row[7]: row[4] for row in _csv_rows(proj)[1:]}["US-001"]
    assert "* Happy path: covered by {{FR-001}}" in description
    assert "**" not in description and "`" not in description
    assert "03-prd.md@" in description and "Canonical source" in description


def test_export_csv_blocks_when_prd_not_approved(pmos, new_project):
    """`export` reuses the plan builder's gate: no approved PRD, no CSV on disk."""
    proj = new_project("ho-csv-gate", "A problem")
    res = run_script(pmos, "pm_handoff.py", "export", cwd=proj)
    assert res.returncode != 0
    assert not (proj / "handoff" / "jira-import.csv").exists()
