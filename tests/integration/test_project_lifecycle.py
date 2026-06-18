"""T2 — project lifecycle integration: scaffold, approve the business statement, status,
and share. Runs the real scripts as subprocesses against the isolated temp install.
See docs/TESTING.md §5 (T2)."""
import pytest

from helpers import run_script, make_draft, event_types, read_events

pytestmark = pytest.mark.integration


def test_pm_new_creates_full_scaffold(pmos, new_project):
    """pm_new lays down the full project: .meta.yaml, business statement, empty telemetry +
    feedback, and .history; the genai flag is recorded; project_created telemetry is logged."""
    proj = new_project("life-demo", "Ship a thing", genai=False)
    for f in (".meta.yaml", "00-business-statement.md", "telemetry.jsonl", "feedback.jsonl"):
        assert (proj / f).exists(), f"missing {f}"
    assert (proj / ".history").is_dir()
    import project
    meta = project.load_meta(proj)
    assert meta["project_slug"] == "life-demo"
    assert meta["genai_flag"] is False
    assert "project_created" in event_types(proj)


def test_approve_business_statement_logs_telemetry(pmos, new_project):
    """Approving stage 00 flips it to approved in BOTH meta and frontmatter, records a
    content hash, and logs a stage_approved event."""
    proj = new_project("appr-demo", "Problem statement")
    res = run_script(pmos, "pm_approve.py", "00", cwd=proj)
    assert res.returncode == 0, res.stderr

    import project
    import frontmatter as fm
    meta_stage = project.get_stage(project.load_meta(proj), "00")
    fmd, _ = fm.read(str(proj / "00-business-statement.md"))
    assert meta_stage["status"] == "approved"
    assert fmd["status"] == "approved"
    assert meta_stage["content_hash"] and fmd["content_hash"] == meta_stage["content_hash"]
    assert any(e["event_type"] == "stage_approved" and e["stage"] == "00" for e in read_events(proj))


def test_pm_status_reports_state(pmos, new_project):
    """pm_status surfaces stage statuses, the feedback count, and recent telemetry — the
    PM's at-a-glance project view."""
    proj = new_project("status-demo", "A problem")
    run_script(pmos, "pm_approve.py", "00", cwd=proj)
    run_script(pmos, "pm_feedback.py", "00", "--rating", "5", "--skip-note", cwd=proj)
    res = run_script(pmos, "pm_status.py", cwd=proj)
    assert res.returncode == 0, res.stderr
    out = res.stdout.lower()
    assert "status-demo" in res.stdout
    assert "approved" in out  # stage 00 shows approved
    assert "feedback" in out  # feedback section/count present


def test_pm_share_includes_approved_excludes_pending(pmos, new_project):
    """pm_share exports approved/edited stage bodies and omits stages that are still
    pending/draft, so a shared bundle only contains signed-off content."""
    proj = new_project("share-demo", "A problem")
    run_script(pmos, "pm_approve.py", "00", cwd=proj)
    make_draft(proj, "01", body="The approved brief body.\n")
    run_script(pmos, "pm_approve.py", "01", cwd=proj)
    # stage 02 left pending on purpose
    res = run_script(pmos, "pm_share.py", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert "The approved brief body." in res.stdout
    assert "02-scope" not in res.stdout and "scope" not in res.stdout.lower()
