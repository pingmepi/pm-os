"""T2 — approval side effects (hooks/post-approve.py): downstream staleness cascade,
frontmatter↔meta sync, and HTML companion rendering for stages 04/05. See docs/guides/testing.md §5 (T2)."""
import pytest

from helpers import run_script, make_draft, generate_stage, stage_status, read_events

pytestmark = pytest.mark.integration


def test_approval_syncs_frontmatter_and_meta(pmos, new_project):
    """Approval records the SAME content hash and approved status in both .meta.yaml and the
    artifact frontmatter — the two sources of truth stay in lockstep."""
    proj = new_project("sync-demo", "A problem")
    run_script(pmos, "pm_approve.py", "00", cwd=proj)
    make_draft(proj, "01", body="Brief body.\n")
    res = run_script(pmos, "pm_approve.py", "01", cwd=proj)
    assert res.returncode == 0, res.stderr
    import project
    import frontmatter as fm
    meta_stage = project.get_stage(project.load_meta(proj), "01")
    fmd, _ = fm.read(str(proj / "01-brief.md"))
    assert meta_stage["status"] == fmd["status"] == "approved"
    assert meta_stage["content_hash"] == fmd["content_hash"]

    # T10: the shared checker agrees the freshly approved, in-sync project is healthy
    # on this invariant.
    import consistency
    issues = consistency.check_project(proj)
    assert not any(i.code in (consistency.CODE_META_FRONTMATTER_STATUS_MISMATCH,
                              consistency.CODE_META_FRONTMATTER_HASH_MISMATCH) for i in issues)


def test_reapproving_upstream_cascades_downstream_stale(pmos, new_project):
    """Re-approving an upstream stage marks its downstream approved stages stale (so they get
    regenerated against new content) and logs stage_marked_stale."""
    proj = new_project("stale-demo", "A problem")
    run_script(pmos, "pm_approve.py", "00", cwd=proj)
    make_draft(proj, "01"); run_script(pmos, "pm_approve.py", "01", cwd=proj)
    make_draft(proj, "02"); run_script(pmos, "pm_approve.py", "02", cwd=proj)
    assert stage_status(proj, "02") == "approved"

    # Regenerate + re-approve 01 -> 02 must go stale.
    make_draft(proj, "01", body="Brief v2 body.\n")
    res = run_script(pmos, "pm_approve.py", "01", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert stage_status(proj, "02") == "stale"
    assert any(e["event_type"] == "stage_marked_stale" and e["stage"] == "02"
               for e in read_events(proj))


def test_approve_reconciles_pending_frontmatter_with_generation_evidence(pmos, new_project):
    """A generated stage whose frontmatter `status` drifted back to 'pending' (failed hook,
    interrupted write, hand-edit) still approves: pm_approve reconciles from ground truth — a
    non-empty body plus a stage_generated event — instead of reporting a real artifact as
    'not generated yet' (GH #61)."""
    import frontmatter as fm
    proj = new_project("reconcile-pending", "A problem")
    run_script(pmos, "pm_approve.py", "00", cwd=proj)
    apath = generate_stage(proj, "01", body="Real generated brief body.\n")  # draft + telemetry
    # Simulate the drift: frontmatter status regresses to 'pending' while the body and the
    # stage_generated event remain.
    fmd, body = fm.read(str(apath))
    fmd["status"] = "pending"
    fm.write(str(apath), fmd, body)

    res = run_script(pmos, "pm_approve.py", "01", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert "reconcil" in res.stdout.lower()
    assert stage_status(proj, "01") == "approved"


def test_approve_still_refuses_truly_ungenerated_stage(pmos, new_project):
    """The reconciliation must not paper over a genuinely ungenerated slot: an empty-bodied
    artifact with no generation event still fails with the 'generate it first' message (GH #61
    guard against over-reconciling)."""
    import frontmatter as fm
    proj = new_project("no-evidence", "A problem")
    run_script(pmos, "pm_approve.py", "00", cwd=proj)
    apath = proj / "01-brief.md"
    fm.write(str(apath), {
        "stage": "01-brief", "project": proj.name, "status": "pending",
        "approved_at": None, "approved_by": None, "content_hash": None,
    }, "")  # empty body, no telemetry
    res = run_script(pmos, "pm_approve.py", "01", cwd=proj)
    assert res.returncode != 0
    assert "not been generated" in res.stdout
    assert stage_status(proj, "01") != "approved"


def test_reapprove_rejects_without_flag(pmos, new_project):
    """Without --reapprove, re-running approve on an already-approved stage is a no-op that
    tells the PM about the --reapprove escape hatch (backlog #7's 'drift dance')."""
    proj = new_project("reapprove-noflag", "A problem")
    make_draft(proj, "01"); run_script(pmos, "pm_approve.py", "01", cwd=proj)
    (proj / "01-brief.md").write_text(
        (proj / "01-brief.md").read_text().rstrip("\n") + "\nDirectly edited by the PM.\n",
        encoding="utf-8",
    )
    res = run_script(pmos, "pm_approve.py", "01", cwd=proj)
    assert res.returncode == 0
    assert "already approved" in res.stdout
    assert "--reapprove" in res.stdout
    assert stage_status(proj, "01") == "approved"  # unchanged, no drift recorded


def test_reapprove_with_flag_reapproves_direct_edit(pmos, new_project):
    """--reapprove lets a PM re-approve an artifact they edited directly while it was still
    'approved' — no downstream stage's gate has to run first to demote it to 'edited'."""
    proj = new_project("reapprove-flag", "A problem")
    make_draft(proj, "01"); run_script(pmos, "pm_approve.py", "01", cwd=proj)
    make_draft(proj, "02"); run_script(pmos, "pm_approve.py", "02", cwd=proj)
    assert stage_status(proj, "02") == "approved"

    apath = proj / "01-brief.md"
    apath.write_text(apath.read_text().rstrip("\n") + "\nDirectly edited by the PM.\n", encoding="utf-8")

    res = run_script(pmos, "pm_approve.py", "01", "--reapprove", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert stage_status(proj, "01") == "approved"
    assert stage_status(proj, "02") == "stale"  # cascades like any other re-approval

    events = read_events(proj)
    reapprove_events = [e for e in events if e["event_type"] == "stage_approved" and e["stage"] == "01"]
    assert reapprove_events[-1]["payload"]["reapproved_from_approved"] is True


def test_reapprove_noop_when_unchanged(pmos, new_project):
    """--reapprove on an approved stage whose body has NOT drifted is a no-op — it must not
    re-log a spurious stage_approved event or touch downstream staleness."""
    proj = new_project("reapprove-noop", "A problem")
    make_draft(proj, "01"); run_script(pmos, "pm_approve.py", "01", cwd=proj)
    make_draft(proj, "02"); run_script(pmos, "pm_approve.py", "02", cwd=proj)
    events_before = read_events(proj)

    res = run_script(pmos, "pm_approve.py", "01", "--reapprove", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert "unchanged since approval" in res.stdout
    assert stage_status(proj, "02") == "approved"  # not cascaded stale
    assert read_events(proj) == events_before


def test_stage_04_approval_renders_html(pmos, new_project):
    """Approving stage 04 triggers post-approve to render the 04-design-spec.html companion,
    with artifact content escaped into it."""
    proj = new_project("html04", "A problem")
    make_draft(proj, "04", body="## Information Architecture\nNav and layout.\n\n## States\nLoading, error.\n")
    res = run_script(pmos, "pm_approve.py", "04", cwd=proj)
    assert res.returncode == 0, res.stderr
    html = proj / "04-design-spec.html"
    assert html.exists(), "stage 04 approval should render the HTML companion"
    assert "Information Architecture" in html.read_text()


def test_stage_05_approval_renders_prototype_html(pmos, new_project):
    """Approving stage 05 renders the 05-prototype-mockup.html companion (which draws on the
    approved stages 04 + 05)."""
    proj = new_project("html05", "A problem")
    make_draft(proj, "04", body="## Information Architecture\nNav.\n\n## Components\nButton, card.\n")
    run_script(pmos, "pm_approve.py", "04", cwd=proj)
    make_draft(proj, "05", body="## Screens\nHome, detail.\n\n## Interactions\nTap, swipe.\n")
    res = run_script(pmos, "pm_approve.py", "05", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert (proj / "05-prototype-mockup.html").exists()


def test_pm_check_flags_downstream_approved_against_changed_upstream(pmos, new_project):
    """Regression for backlog #31: if an approval's stale-cascade is interrupted
    (timeout/crash after the upstream is re-approved but before downstream cascade),
    a downstream stage stays `approved` while its recorded upstream hash no longer
    matches the upstream's current content_hash. /pm-check must detect this invalid
    state — the upstream_hashes_at_approval field was written but never read."""
    import consistency
    import project

    proj = new_project("half-approved", "A problem")
    run_script(pmos, "pm_approve.py", "00", cwd=proj)
    for sid in ("01", "02", "03"):
        make_draft(proj, sid)
        assert run_script(pmos, "pm_approve.py", sid, cwd=proj).returncode == 0
    make_draft(proj, "04", body="## Information Architecture\nNav.\n\n## States\nLoading.\n")
    assert run_script(pmos, "pm_approve.py", "04", cwd=proj).returncode == 0

    # A correctly-approved chain has no such mismatch.
    assert not any(i.code == consistency.CODE_DOWNSTREAM_UPSTREAM_STALE
                   for i in consistency.check_project(proj))

    # Simulate the interrupted cascade: 04 stays approved, but its recorded upstream
    # hash for 03 is stale (03 moved forward; the downstream cascade never ran).
    meta = project.load_meta(proj)
    recorded = project.get_stage(meta, "04")["upstream_hashes_at_approval"]
    assert "03" in recorded
    recorded["03"] = "0" * 16
    project.save_meta(meta, proj)

    issues = consistency.check_project(proj)
    assert any(i.code == consistency.CODE_DOWNSTREAM_UPSTREAM_STALE and i.stage == "04"
               for i in issues), [i.code for i in issues]
