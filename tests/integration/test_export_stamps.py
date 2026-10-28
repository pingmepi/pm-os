"""Approval stamps on every exported file, and approved-only raw export
(backlog #71, APEX AL-01: the build team had to compute its own hash to know
which PRD version it held). See docs/guides/testing.md §T2."""
import pytest
import yaml

from helpers import make_draft, run_script

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
## Non-Functional Requirements
Performance: list loads under 2s.
"""

_QA = """## Functional Test Cases
### TC-001 — Add happy path (covers US-001, FR-001)
Given valid fields, the agency is saved.
"""


def _approved(pmos, new_project, slug):
    proj = new_project(slug, "A problem")
    for stage, body in (("01", "## Overview\nAgencies.\n"), ("02", "## MVP Boundary\nAdd.\n"),
                        ("03", _PRD), ("06", _QA)):
        make_draft(proj, stage, body=body)
        assert run_script(pmos, "pm_approve.py", stage, cwd=proj).returncode == 0
    return proj


def _frontmatter(path):
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    return yaml.safe_load(text[4:text.index("\n---\n", 4)])


def test_every_exported_file_carries_its_sources_approval(pmos, new_project):
    """Stories, requirements, epics and full projections carry the canonical
    source's status, version, approver, approval time and content hash, plus a
    `sources` record per artifact they draw on; the README lists the same in a
    Sources table."""
    import project
    proj = _approved(pmos, new_project, "stamps")
    res = run_script(pmos, "pm_share.py", "--package", cwd=proj)
    assert res.returncode == 0, res.stderr
    prd = project.get_stage(project.load_meta(proj), "03")
    dev = proj / "handoff" / "dev"
    files = [
        next((dev / "stories").glob("US-001-*.md")),
        next((dev / "requirements").glob("FR-001-*.md")),
        next((dev / "epics").glob("EPIC-001-*.md")),
        dev / "reference" / "prd.md",
    ]
    for path in files:
        fm = _frontmatter(path)
        assert fm["status"] == "approved", path
        assert fm["version"] == 1, path
        assert fm["approved_by"], path
        assert fm["approved_at"] == str(prd["approved_at"]), path
        assert fm["content_hash"] == prd["content_hash"], path
        assert fm["sources"][0]["artifact"] == "03-prd.md", path
    story = _frontmatter(files[0])
    assert [s["artifact"] for s in story["sources"]] == ["03-prd.md", "06-qa-plan.md"]
    readme = (dev / "README.md").read_text(encoding="utf-8")
    assert "## Sources" in readme
    assert f"| 03-prd.md | approved | v1 |" in readme and prd["content_hash"][:12] in readme


def test_unapproved_trd_is_recorded_but_not_tracked(pmos, new_project):
    """`reference/trd.md` for a project without an approved TRD lists no
    tracked source, so the release check never blocks on a TRD that is shown
    only as a "not approved" note."""
    proj = _approved(pmos, new_project, "stamps-trd")
    make_draft(proj, "08", body="## Work Breakdown\n### TSK-001 — Build\n- **Implements:** FR-001\n")
    res = run_script(pmos, "pm_share.py", "--package", "--audience", "dev", cwd=proj)
    assert res.returncode == 0, res.stderr
    fm = _frontmatter(proj / "handoff" / "dev" / "reference" / "trd.md")
    assert fm["generated_from"] == []
    assert fm["sources"][0]["status"] == "draft"


def test_raw_export_ships_only_approved_stages_by_default(pmos, new_project):
    """An `edited` stage (body changed after approval) is left out of the
    all-stages export with a note naming it; its header shows status and
    version for the stages that do go out."""
    proj = _approved(pmos, new_project, "raw-approved")
    brief = proj / "01-brief.md"
    brief.write_text(brief.read_text(encoding="utf-8") + "Edited after approval.\n", encoding="utf-8")
    import project  # mark it `edited` the way the gate does on detecting drift
    meta = project.load_meta(proj)
    project.get_stage(meta, "01")["status"] = "edited"
    project.save_meta(meta, proj)

    res = run_script(pmos, "pm_share.py", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert "Stage 01" not in res.stdout
    assert "not exported because not approved:" in res.stderr and "01 (edited)" in res.stderr
    assert "## Stage 03" in res.stdout
    assert "Status: approved | Version: v1 | Approved by:" in res.stdout


def test_raw_export_of_an_unapproved_stage_needs_the_flag(pmos, new_project):
    """A single draft stage is refused without --include-unapproved; with it,
    the stage is exported and marked NOT APPROVED in the output."""
    proj = _approved(pmos, new_project, "raw-draft")
    make_draft(proj, "04", body="## Information Architecture\nDraft.\n")
    res = run_script(pmos, "pm_share.py", "04", cwd=proj)
    assert res.returncode == 1
    assert "stage 04 is 'draft', not approved" in res.stdout
    assert "--include-unapproved" in res.stdout
    res = run_script(pmos, "pm_share.py", "04", "--include-unapproved", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert "**NOT APPROVED (draft)" in res.stdout
    assert "Draft." in res.stdout


def test_stage_edited_after_approval_is_not_exported_as_approved(pmos, new_project):
    """A body edited after approval (no gate has run since) is treated as `edited`:
    the raw export refuses it, the package refuses an edited PRD with the
    --reapprove hint, and /pm-status shows it as edited."""
    proj = _approved(pmos, new_project, "edited-export")
    prd = proj / "03-prd.md"
    prd.write_text(prd.read_text(encoding="utf-8") + "\nUnreviewed change.\n", encoding="utf-8")

    raw = run_script(pmos, "pm_share.py", "03", cwd=proj)
    assert raw.returncode == 1
    assert "'edited'" in raw.stdout and "Unreviewed change" not in raw.stdout

    pkg = run_script(pmos, "pm_share.py", "--package", cwd=proj)
    assert pkg.returncode != 0
    assert "--reapprove" in pkg.stderr + pkg.stdout
    assert not (proj / "handoff" / "dev").exists()

    status = run_script(pmos, "pm_status.py", cwd=proj)
    assert "edited since approval" in status.stdout


def test_package_blocks_a_qa_plan_edited_after_approval(pmos, new_project):
    """An approved QA plan edited after approval makes the release check fail with
    SOURCE_NOT_APPROVED, so its unreviewed text does not ship stamped approved."""
    proj = _approved(pmos, new_project, "edited-qa")
    qa = proj / "06-qa-plan.md"
    qa.write_text(qa.read_text(encoding="utf-8") + "\nUnreviewed QA change.\n", encoding="utf-8")
    res = run_script(pmos, "pm_share.py", "--package", cwd=proj)
    assert res.returncode != 0
    assert "SOURCE_NOT_APPROVED" in res.stderr + res.stdout
