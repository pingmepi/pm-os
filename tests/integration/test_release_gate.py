"""The release check end to end (backlog #72): `pm_check.py --release` on any
folder or zip, and the gate `pm_share.py --package` runs on its staged build
before publishing anything under handoff/. See docs/guides/testing.md
§"Release check"."""
import json
import zipfile

import pytest

from helpers import make_draft, read_events, run_script

pytestmark = pytest.mark.integration


_PRD = """## Product Epics
### EPIC-001 — Agency onboarding
**Outcome:** Collections users can add external agencies.
**Scope:** Agency creation.
**Success signal:** An agency is saved.
## User Journeys
### UJ-001 — Manage agencies
Primary user: Collections user. Traceability: US-001.
## Prioritization Method
MoSCoW.
## User Stories with Acceptance Criteria
### US-001 — Add external agency
**Priority:** Must
**Epic:** EPIC-001
As a Collections user, I want to add agencies. Traceability: UJ-001, FR-001.
### US-002 — List agencies
**Priority:** Should
**Epic:** EPIC-001
As a user, I want to list agencies.
## Functional Requirements
- **FR-001** — The system stores agencies.
  **Priority:** Must
  **Epic:** EPIC-001
## Non-Functional Requirements
Performance: list loads under 2s.
"""

_QA_FULL = """## Functional Test Cases
### TC-001 — Add happy path (covers US-001, FR-001)
Given valid fields, the agency is saved.
### TC-002 — List (covers US-002)
Given agencies exist, they are listed.
"""

_QA_GAP = """## Functional Test Cases
### TC-001 — Add happy path (covers US-001, FR-001)
Given valid fields, the agency is saved.
"""


def _approve(pmos, proj, qa_body):
    for stage, body in (("01", "## Overview\nAgencies.\n"), ("02", "## MVP Boundary\nAdd and list.\n"),
                        ("03", _PRD), ("06", qa_body)):
        make_draft(proj, stage, body=body)
        assert run_script(pmos, "pm_approve.py", stage, cwd=proj).returncode == 0


def _hand_built(root):
    (root / "stories").mkdir(parents=True)
    (root / "README.md").write_text(
        "# Sprint\n\n[PRD](../PRD.md) · [story](stories/S1-US-01-a.md)\n", encoding="utf-8")
    (root / "stories" / "S1-US-01-a.md").write_text(
        "---\nstory_id: S1-US-01\n---\n# S1-US-01\n\nFollows R-01, R-02 and R-03.\n", encoding="utf-8")
    return root


def test_pm_check_release_reports_findings_and_exits_nonzero(pmos, tmp_path):
    """`pm_check.py --release <folder>` works outside any project, prints each
    finding with file:line, code and fix, and exits 1 on errors; `--json`
    returns the same findings machine-readably."""
    pkg = _hand_built(tmp_path / "sprint-1")
    res = run_script(pmos, "pm_check.py", "--release", str(pkg), cwd=tmp_path)
    assert res.returncode == 1, res.stdout + res.stderr
    assert "README.md:3  LINK_BROKEN" in res.stdout
    assert "stories/S1-US-01-a.md:1  STORY_PRIORITY_MISSING" in res.stdout
    assert "`R-01` is cited but nothing in the package defines it" in res.stdout
    assert "Fix:" in res.stdout

    res = run_script(pmos, "pm_check.py", "--release", str(pkg), "--json", cwd=tmp_path)
    reports = json.loads(res.stdout)
    codes = {f["code"] for f in reports[0]["findings"]}
    assert {"LINK_BROKEN", "ID_UNDEFINED", "STORY_EPIC_MISSING", "STORY_PRIORITY_MISSING"} <= codes
    assert reports[0]["kind"] == "hand-built"


def test_pm_check_release_reads_a_zip_and_honours_ignore_ids(pmos, tmp_path):
    """A `.zip` is checked as its contents; `--ignore-ids R` drops the R-family
    undefined-id errors and says what it ignored."""
    pkg = _hand_built(tmp_path / "src")
    archive = tmp_path / "stories.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for path in pkg.rglob("*"):
            zf.write(path, path.relative_to(pkg).as_posix())
    res = run_script(pmos, "pm_check.py", "--release", str(archive), "--ignore-ids", "R", cwd=tmp_path)
    assert res.returncode == 1
    assert "ID_UNDEFINED" not in res.stdout
    assert "Ignored id prefixes/ids: R" in res.stdout


def test_pm_check_release_needs_a_path_outside_a_project(pmos, tmp_path):
    """Run with no PATH outside a project, `--release` exits 2 with a message
    instead of guessing a folder."""
    res = run_script(pmos, "pm_check.py", "--release", cwd=tmp_path)
    assert res.returncode == 2
    assert "needs a path" in res.stdout


def test_package_with_release_errors_is_blocked_and_writes_nothing(pmos, new_project):
    """Backlog #72 + #53(a): a story no TC covers is a release-check error, so
    `--package` exits non-zero, creates nothing under handoff/, and logs
    `release_check_blocked` with the error codes."""
    proj = new_project("release-blocked", "A problem")
    _approve(pmos, proj, _QA_GAP)
    res = run_script(pmos, "pm_share.py", "--package", cwd=proj)
    assert res.returncode != 0
    assert "REQUIREMENT_UNTESTED" in res.stderr and "US-002" in res.stderr
    assert "nothing was written" in res.stderr
    assert not (proj / "handoff").exists()
    blocked = [e for e in read_events(proj) if e["event_type"] == "release_check_blocked"]
    assert blocked and blocked[-1]["payload"]["codes"] == ["REQUIREMENT_UNTESTED"]


def test_blocked_package_leaves_the_previous_package_untouched(pmos, new_project):
    """A blocked rebuild must not wipe the package already on disk: the staged
    build is checked before any audience folder is replaced."""
    proj = new_project("release-keep", "A problem")
    _approve(pmos, proj, _QA_FULL)
    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0
    before = sorted(p.relative_to(proj).as_posix() for p in (proj / "handoff").rglob("*"))
    make_draft(proj, "06", body=_QA_GAP)
    assert run_script(pmos, "pm_approve.py", "06", cwd=proj).returncode == 0
    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode != 0
    after = sorted(p.relative_to(proj).as_posix() for p in (proj / "handoff").rglob("*"))
    assert after == before


def test_allow_release_errors_publishes_and_logs_the_overridden_codes(pmos, new_project):
    """`--allow-release-errors` publishes despite errors and logs
    `release_check_overridden` naming exactly the overridden codes."""
    proj = new_project("release-override", "A problem")
    _approve(pmos, proj, _QA_GAP)
    res = run_script(pmos, "pm_share.py", "--package", "--allow-release-errors", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert (proj / "handoff" / "dev" / "stories").is_dir()
    overridden = [e for e in read_events(proj) if e["event_type"] == "release_check_overridden"]
    assert overridden and overridden[-1]["payload"]["codes"] == ["REQUIREMENT_UNTESTED"]
    assert overridden[-1]["payload"]["surface"] == "handoff_package"


def test_clean_package_publishes_and_passes_a_standalone_recheck(pmos, new_project):
    """A fully traced pipeline publishes, priorities read clean in the story
    frontmatter (backlog #70), and `pm_check.py --release` with no PATH checks
    every audience folder of the project's handoff/ and finds no errors."""
    proj = new_project("release-clean", "A problem")
    _approve(pmos, proj, _QA_FULL)
    res = run_script(pmos, "pm_share.py", "--package", cwd=proj)
    assert res.returncode == 0, res.stderr
    story = next((proj / "handoff" / "dev" / "stories").glob("US-001-*.md")).read_text(encoding="utf-8")
    assert "priority: Must\n" in story
    res = run_script(pmos, "pm_check.py", "--release", cwd=proj)
    assert res.returncode == 0, res.stdout
    assert res.stdout.count("Release check:") == 4
    assert res.stdout.count("0 error(s)") == 4
