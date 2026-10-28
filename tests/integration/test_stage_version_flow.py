"""The approval version per stage through every approval path (backlog #71):
`pm_approve.py`, `--reapprove` (edit and rebind), the gate's implicit
re-approval, and a regenerated draft. The rule (PM decision 2026-10-21): a new
approved body earns the next version; the same body keeps it. See
docs/guides/testing.md §T2."""
import pytest

from helpers import make_draft, read_events, run_hook, run_script

pytestmark = pytest.mark.integration


def _version(proj, sid):
    import frontmatter as fm
    import project
    meta_stage = project.get_stage(project.load_meta(proj), sid)
    fmd, _ = fm.read(str(project.artifact_path(proj, sid)))
    return meta_stage.get("version"), fmd.get("version")


def _edit(proj, name, extra):
    path = proj / name
    path.write_text(path.read_text(encoding="utf-8") + extra, encoding="utf-8")


def test_version_increments_for_new_bodies_and_holds_for_the_same_body(pmos, new_project):
    """v1 on first approval (in meta, frontmatter, telemetry and the printed
    result); an edit re-approved with --reapprove is v2; re-running
    --reapprove on the unchanged body is a no-op that keeps v2; regenerating
    a draft keeps v2 until the new body is approved as v3."""
    proj = new_project("version-flow", "A problem")
    run_script(pmos, "pm_approve.py", "00", cwd=proj)
    make_draft(proj, "01", body="Brief v1.\n")
    res = run_script(pmos, "pm_approve.py", "01", cwd=proj)
    assert "Stage 01 approved (version 1)." in res.stdout
    assert _version(proj, "01") == (1, 1)
    approved = [e for e in read_events(proj) if e["event_type"] == "stage_approved" and e["stage"] == "01"]
    assert approved[-1]["payload"]["version"] == 1

    _edit(proj, "01-brief.md", "Edited after approval.\n")
    assert run_script(pmos, "pm_approve.py", "01", "--reapprove", cwd=proj).returncode == 0
    assert _version(proj, "01") == (2, 2)
    res = run_script(pmos, "pm_approve.py", "01", "--reapprove", cwd=proj)
    assert "No action taken" in res.stdout
    assert _version(proj, "01") == (2, 2)

    make_draft(proj, "01", body="Regenerated brief.\n")
    assert _version(proj, "01")[0] == 2
    assert run_script(pmos, "pm_approve.py", "01", cwd=proj).returncode == 0
    assert _version(proj, "01") == (3, 3)


def test_reapproving_a_stale_stage_with_an_unchanged_body_keeps_its_version(pmos, new_project):
    """A stage marked stale by an upstream re-approval, then approved again
    without changing its own body, names the same body, so it keeps its
    version."""
    proj = new_project("version-stale", "A problem")
    run_script(pmos, "pm_approve.py", "00", cwd=proj)
    for sid in ("01", "02"):
        make_draft(proj, sid, body=f"Stage {sid}.\n")
        assert run_script(pmos, "pm_approve.py", sid, cwd=proj).returncode == 0
    _edit(proj, "01-brief.md", "Brief change.\n")
    assert run_script(pmos, "pm_approve.py", "01", "--reapprove", cwd=proj).returncode == 0
    import project
    assert project.get_stage(project.load_meta(proj), "02")["status"] == "stale"
    assert run_script(pmos, "pm_approve.py", "02", cwd=proj).returncode == 0
    assert _version(proj, "02") == (1, 1)


def test_gate_implicit_reapproval_mints_a_new_version(pmos, new_project):
    """The gate's implicit re-approval of an edited upstream binds a new body,
    so the upstream moves to the next version and the event records it."""
    proj = new_project("version-gate", "A problem")
    run_script(pmos, "pm_approve.py", "00", cwd=proj)
    make_draft(proj, "01", body="Brief.\n")
    assert run_script(pmos, "pm_approve.py", "01", cwd=proj).returncode == 0
    _edit(proj, "01-brief.md", "Hand edit.\n")
    run_hook(pmos, "pre-stage.py", "02", proj)
    res = run_hook(pmos, "pre-stage.py", "02", proj, extra_env={"PM_OS_EDITED_UPSTREAM_CHOICE": "continue"})
    assert res.returncode == 0, res.stderr
    assert _version(proj, "01") == (2, 2)
    implicit = [e for e in read_events(proj) if e["event_type"] == "implicit_reapproval"]
    assert implicit[-1]["payload"]["version"] == 2


def test_pm_status_shows_the_version(pmos, new_project):
    """/pm-status prints the approved version next to each approved stage."""
    proj = new_project("version-status", "A problem")
    run_script(pmos, "pm_approve.py", "00", cwd=proj)
    make_draft(proj, "01", body="Brief.\n")
    run_script(pmos, "pm_approve.py", "01", cwd=proj)
    res = run_script(pmos, "pm_status.py", cwd=proj)
    assert "v1  approved" in res.stdout
