"""T2 — the gate (hooks/pre-stage.py): blocking unapproved upstreams, detecting
post-approval edits, and the non-interactive implicit-reapproval path. See docs/TESTING.md §5 (T2)."""
import pytest

from helpers import run_script, run_hook, make_draft, stage_status, read_events

pytestmark = pytest.mark.integration


def _approve_00_and_01(pmos, proj):
    run_script(pmos, "pm_approve.py", "00", cwd=proj)
    make_draft(proj, "01", body="Brief v1 body.\n")
    run_script(pmos, "pm_approve.py", "01", cwd=proj)


def test_gate_blocks_when_upstream_unapproved(pmos, new_project):
    """Running stage 02 while stage 01 is still pending is blocked (non-zero exit), and the
    blocking stage is named — the core safety gate."""
    proj = new_project("gate-block", "A problem")
    run_script(pmos, "pm_approve.py", "00", cwd=proj)  # 01 left pending
    res = run_hook(pmos, "pre-stage.py", "02", proj)
    assert res.returncode != 0
    assert "01" in res.stderr


def test_gate_allows_first_stage_after_00_approved(pmos, new_project):
    """Once the business statement (00) is approved, the stage-01 gate passes."""
    proj = new_project("gate-allow", "A problem")
    run_script(pmos, "pm_approve.py", "00", cwd=proj)
    res = run_hook(pmos, "pre-stage.py", "01", proj)
    assert res.returncode == 0, res.stderr


def test_editing_approved_upstream_marks_edited(pmos, new_project):
    """Editing an approved upstream's body, then running a downstream gate, detects the hash
    drift: the upstream is marked `edited` and a stage_edited_post_approval event is logged.
    Without a choice in non-interactive mode the gate then halts (exit != 0)."""
    proj = new_project("gate-edit", "A problem")
    _approve_00_and_01(pmos, proj)
    (proj / "01-brief.md").write_text(
        (proj / "01-brief.md").read_text() + "\nPM hand-edit after approval.\n", encoding="utf-8")
    res = run_hook(pmos, "pre-stage.py", "02", proj)  # no PM_OS_EDITED_UPSTREAM_CHOICE
    assert res.returncode != 0, "non-tty edited upstream must require an explicit choice"
    assert stage_status(proj, "01") == "edited"
    assert any(e["event_type"] == "stage_edited_post_approval" and e["stage"] == "01"
               for e in read_events(proj))


def test_non_tty_without_choice_is_clear_error(pmos, new_project):
    """In non-interactive mode an edited upstream with no PM_OS_EDITED_UPSTREAM_CHOICE fails
    with explicit guidance rather than hanging on input()."""
    proj = new_project("gate-nontty", "A problem")
    _approve_00_and_01(pmos, proj)
    (proj / "01-brief.md").write_text((proj / "01-brief.md").read_text() + "\nedit\n", encoding="utf-8")
    res = run_hook(pmos, "pre-stage.py", "02", proj)
    assert res.returncode != 0
    assert "PM_OS_EDITED_UPSTREAM_CHOICE" in res.stderr


def test_implicit_reapproval_continue(pmos, new_project):
    """With PM_OS_EDITED_UPSTREAM_CHOICE=continue, the gate implicitly re-approves the edited
    upstream (back to approved, new hash) and logs implicit_reapproval, then allows the run."""
    proj = new_project("gate-implicit", "A problem")
    _approve_00_and_01(pmos, proj)
    (proj / "01-brief.md").write_text((proj / "01-brief.md").read_text() + "\nedit\n", encoding="utf-8")
    res = run_hook(pmos, "pre-stage.py", "02", proj,
                   extra_env={"PM_OS_EDITED_UPSTREAM_CHOICE": "continue"})
    assert res.returncode == 0, res.stderr
    assert stage_status(proj, "01") == "approved"
    assert any(e["event_type"] == "implicit_reapproval" and e["stage"] == "01"
               for e in read_events(proj))
