"""T2 — the gate (hooks/pre-stage.py): blocking unapproved upstreams, detecting
post-approval edits, and the non-interactive implicit-reapproval path. See docs/guides/testing.md §5 (T2)."""
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

    # T10: once drift flips a stage to 'edited', invariant 2 no longer re-flags it as
    # drifted (edited IS the settled "drift already surfaced" state) — and invariant 3
    # allows an 'edited' upstream on principle (nothing downstream was approved here).
    import consistency
    issues = consistency.check_project(proj)
    assert not any(i.code == consistency.CODE_BODY_HASH_DRIFT and i.stage == "01" for i in issues)
    assert not any(i.code == consistency.CODE_APPROVED_UPSTREAM_NOT_READY for i in issues)


def test_non_tty_without_choice_routes_to_pm(pmos, new_project):
    """In non-interactive mode an edited upstream with no PM_OS_EDITED_UPSTREAM_CHOICE blocks
    and routes the re-approval decision back to the PM (/pm-approve) rather than hanging on
    input() — and it must NOT advertise the env-var bypass, so an agent can't self-approve."""
    proj = new_project("gate-nontty", "A problem")
    _approve_00_and_01(pmos, proj)
    (proj / "01-brief.md").write_text((proj / "01-brief.md").read_text() + "\nedit\n", encoding="utf-8")
    res = run_hook(pmos, "pre-stage.py", "02", proj)
    assert res.returncode != 0
    assert "/pm-approve" in res.stderr
    assert "PM_OS_EDITED_UPSTREAM_CHOICE" not in res.stderr


def test_enhancement_project_scaffolds(pmos):
    """pm_new.py --mode enhancement writes project_type=enhancement and schema_version=4 to meta,
    with codebase_path set when --codebase is provided."""
    import yaml
    res = run_script(pmos, "pm_new.py", "enhance-test", "Add feature X",
                     "--no-genai", "--mode", "enhancement",
                     "--codebase", "/tmp/some-repo")
    assert res.returncode == 0, res.stderr
    proj = pmos.projects / "enhance-test"
    meta = yaml.safe_load((proj / ".meta.yaml").read_text(encoding="utf-8"))
    assert meta["project_type"] == "enhancement"
    assert meta["schema_version"] == 4
    assert meta["context_pack"] is None
    assert meta["codebase_path"] == "/tmp/some-repo"
    assert meta["codebase_ref"] is None


def test_brief_gates_on_00c_when_present(pmos, new_project):
    """When a 00c stage entry exists in meta, the stage-01 gate requires it to be approved.
    Absent 00c (greenfield) must not gate stage 01."""
    proj = new_project("gate-00c", "A problem")
    run_script(pmos, "pm_approve.py", "00", cwd=proj)

    # Inject 00c as draft via pm_context_import.py commit
    from helpers import write_artifact
    write_artifact(proj / "00-codebase-understanding.md",
                   stage="00c-codebase-understanding", project=proj.name,
                   status="draft", body="## TL;DR\nSome codebase.\n")
    res_commit = run_script(pmos, "pm_context_import.py", "commit", "00c",
                            "--kind", "generated", "--status", "draft",
                            "--model", "test", cwd=proj)
    assert res_commit.returncode == 0, res_commit.stderr

    # Gate for 01 must block while 00c is draft
    res_block = run_hook(pmos, "pre-stage.py", "01", proj)
    assert res_block.returncode != 0, "gate must block when 00c is present but draft"
    assert "00c" in res_block.stderr

    # Approving 00c unblocks stage 01
    run_script(pmos, "pm_approve.py", "00c", cwd=proj)
    res_pass = run_hook(pmos, "pre-stage.py", "01", proj)
    assert res_pass.returncode == 0, res_pass.stderr


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
