"""T2 — approval state integrity (backlog #54–#58): the gate blocks rather than crashing
on a Windows NUL stdin, keeps the approved hash when it detects drift, approval marks
downstream stages stale before the post-approve hook runs (so a hung hook cannot undo
it), --reapprove can rebind a stage to re-approved upstreams, and approving a large
artifact does not hang on the edit-distance metric. See docs/guides/testing.md §5 (T2)."""
import subprocess
import sys

import pytest

from helpers import run_script, run_hook, make_draft, generate_stage, stage_status, read_events

pytestmark = pytest.mark.integration


def _approve_chain(pmos, proj, *stage_ids):
    run_script(pmos, "pm_approve.py", "00", cwd=proj)
    for sid in stage_ids:
        make_draft(proj, sid, body=f"Stage {sid} body.\n")
        res = run_script(pmos, "pm_approve.py", sid, cwd=proj)
        assert res.returncode == 0, res.stdout + res.stderr


def _edit_body(proj, name, extra="\nPM hand-edit after approval.\n"):
    path = proj / name
    path.write_text(path.read_text(encoding="utf-8") + extra, encoding="utf-8")


def _hashes(proj, sid):
    import project
    import frontmatter as fm
    meta_stage = project.get_stage(project.load_meta(proj), sid)
    fmd, _ = fm.read(str(project.artifact_path(proj, sid)))
    return meta_stage, fmd


def test_gate_blocks_instead_of_crashing_on_nul_stdin(pmos, new_project):
    """Backlog #54. Run the gate the way an agent shell does, with stdin from the null
    device (NUL on Windows, which reports isatty() True). An edited upstream must take
    the BLOCKED path that routes the decision to the PM, not crash in input() with
    EOFError."""
    proj = new_project("gate-nul", "A problem")
    _approve_chain(pmos, proj, "01")
    _edit_body(proj, "01-brief.md")
    env = dict(pmos.env, PM_OS_STAGE="02")
    res = subprocess.run([sys.executable, str(pmos.install / "hooks" / "pre-stage.py")],
                         cwd=str(proj), env=env, stdin=subprocess.DEVNULL,
                         capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert res.returncode != 0
    assert "EOFError" not in res.stderr and "Traceback" not in res.stderr, res.stderr
    assert "BLOCKED" in res.stderr and "/pm-approve" in res.stderr
    assert stage_status(proj, "01") == "edited"


def test_gate_keeps_approved_hash_when_it_detects_drift(pmos, new_project):
    """Backlog #55. When the gate marks an upstream 'edited', .meta.yaml must keep the
    approved content_hash, in lockstep with the frontmatter, and record the drifted hash
    separately. The warning shows two different hashes, and /pm-check does not report
    META_FRONTMATTER_HASH_MISMATCH."""
    import consistency
    proj = new_project("gate-hash", "A problem")
    _approve_chain(pmos, proj, "01")
    approved = _hashes(proj, "01")[0]["content_hash"]
    _edit_body(proj, "01-brief.md")

    res = run_hook(pmos, "pre-stage.py", "02", proj)
    assert res.returncode != 0
    meta_stage, fmd = _hashes(proj, "01")
    assert meta_stage["status"] == fmd["status"] == "edited"
    assert meta_stage["content_hash"] == fmd["content_hash"] == approved
    assert meta_stage["edited_hash"] and meta_stage["edited_hash"] != approved
    assert f"Approved hash: {approved}" in res.stdout
    assert f"Current hash:  {meta_stage['edited_hash']}" in res.stdout
    assert not any(i.code == consistency.CODE_META_FRONTMATTER_HASH_MISMATCH
                   for i in consistency.check_project(proj))


def test_approving_an_edited_stage_clears_the_drift_record(pmos, new_project):
    """Backlog #55. After the gate marks a stage edited, /pm-approve brings meta and
    frontmatter back to one new hash and drops ``edited_hash``. Implicit re-approval
    does the same."""
    proj = new_project("gate-clear", "A problem")
    _approve_chain(pmos, proj, "01")
    _edit_body(proj, "01-brief.md")
    run_hook(pmos, "pre-stage.py", "02", proj)
    res = run_script(pmos, "pm_approve.py", "01", cwd=proj)
    assert res.returncode == 0, res.stdout + res.stderr
    meta_stage, fmd = _hashes(proj, "01")
    assert meta_stage["status"] == "approved"
    assert meta_stage["content_hash"] == fmd["content_hash"]
    assert "edited_hash" not in meta_stage

    _edit_body(proj, "01-brief.md", "\nSecond edit.\n")
    run_hook(pmos, "pre-stage.py", "02", proj)
    res = run_hook(pmos, "pre-stage.py", "02", proj,
                   extra_env={"PM_OS_EDITED_UPSTREAM_CHOICE": "continue"})
    assert res.returncode == 0, res.stderr
    meta_stage, fmd = _hashes(proj, "01")
    assert meta_stage["content_hash"] == fmd["content_hash"]
    assert "edited_hash" not in meta_stage


def test_downstream_is_stale_even_when_the_hook_hangs(pmos, new_project):
    """Backlog #57 / #31 Part 1. Approval marks downstream stages stale in the same
    write as the approval, before the post-approve hook runs. With a hook that hangs,
    approval still returns (the hook is stopped at PM_OS_POST_APPROVE_TIMEOUT), and the
    downstream stage is already stale in meta, in frontmatter and in telemetry."""
    proj = new_project("hook-hang", "A problem")
    _approve_chain(pmos, proj, "01", "02")
    (pmos.install / "hooks" / "post-approve.py").write_text(
        "import time\ntime.sleep(120)\n", encoding="utf-8")
    _edit_body(proj, "01-brief.md")

    res = run_script(pmos, "pm_approve.py", "01", "--reapprove", cwd=proj,
                     extra_env={"PM_OS_POST_APPROVE_TIMEOUT": "2"})
    assert res.returncode == 0, res.stdout + res.stderr
    assert "did not finish within 2s" in res.stdout
    assert "Downstream stages now stale: 02" in res.stdout
    meta_stage, fmd = _hashes(proj, "02")
    assert meta_stage["status"] == fmd["status"] == "stale"
    types = [(e["event_type"], e["stage"]) for e in read_events(proj)]
    approved_at = max(i for i, t in enumerate(types) if t == ("stage_approved", "01"))
    assert ("stage_marked_stale", "02") in types[approved_at:]


def test_reapprove_rebinds_a_stage_to_its_reapproved_upstream(pmos, new_project):
    """Backlog #58. When an approved stage's recorded upstream hash no longer matches
    (the interrupted-cascade state /pm-check reports as DOWNSTREAM_UPSTREAM_STALE),
    `--reapprove` on that stage rebinds it: it stores the current upstream hashes, logs
    stage_rebound, leaves its own hash and downstream stages alone, and clears the
    finding. Without a mismatch it stays a no-op."""
    import consistency
    import project
    proj = new_project("rebind", "A problem")
    _approve_chain(pmos, proj, "01", "02", "03")

    meta = project.load_meta(proj)
    project.get_stage(meta, "02")["upstream_hashes_at_approval"]["01"] = "0" * 16
    project.save_meta(meta, proj)
    assert any(i.code == consistency.CODE_DOWNSTREAM_UPSTREAM_STALE and i.stage == "02"
               for i in consistency.check_project(proj))
    own_hash = _hashes(proj, "02")[0]["content_hash"]

    res = run_script(pmos, "pm_approve.py", "02", "--reapprove", cwd=proj)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "re-approved against the current upstream stage(s): 01" in res.stdout
    meta_stage, _ = _hashes(proj, "02")
    assert meta_stage["upstream_hashes_at_approval"]["01"] == _hashes(proj, "01")[0]["content_hash"]
    assert meta_stage["content_hash"] == own_hash
    assert stage_status(proj, "03") == "approved"
    rebound = [e for e in read_events(proj) if e["event_type"] == "stage_rebound"]
    assert rebound and rebound[-1]["stage"] == "02"
    assert list(rebound[-1]["payload"]["rebound_upstreams"]) == ["01"]
    assert not any(i.code == consistency.CODE_DOWNSTREAM_UPSTREAM_STALE
                   for i in consistency.check_project(proj))

    res = run_script(pmos, "pm_approve.py", "02", "--reapprove", cwd=proj)
    assert res.returncode == 0
    assert "No action taken" in res.stdout


def test_reapprove_refuses_to_rebind_onto_an_unapproved_upstream(pmos, new_project):
    """Backlog #58. Rebinding records that the stage was reviewed against approved
    upstreams, so it refuses while any upstream is not approved, and names it."""
    import project
    proj = new_project("rebind-refuse", "A problem")
    _approve_chain(pmos, proj, "01", "02")
    meta = project.load_meta(proj)
    project.get_stage(meta, "02")["upstream_hashes_at_approval"]["01"] = "0" * 16
    project.get_stage(meta, "01")["status"] = "draft"
    project.save_meta(meta, proj)

    res = run_script(pmos, "pm_approve.py", "02", "--reapprove", cwd=proj)
    assert res.returncode != 0
    assert "Stage 01: draft" in res.stdout
    assert not any(e["event_type"] == "stage_rebound" for e in read_events(proj))


def test_approving_a_large_edited_artifact_does_not_hang(pmos, new_project):
    """Backlog #56. Approving a ~400 KB generated stage after scattered PM edits
    completes inside the runner's 60 s timeout (exact Levenshtein would take hours) and
    records how the edit distance was measured."""
    proj = new_project("big-approve", "A problem")
    run_script(pmos, "pm_approve.py", "00", cwd=proj)
    body = "\n".join(f"- The brief states fact number {i} about the target users." for i in range(7000))
    apath = generate_stage(proj, "01", body=body + "\n")
    text = apath.read_text(encoding="utf-8")
    apath.write_text(text.replace("fact number 10 about", "fact no. 10 about").replace("fact number 6000 about", "fact #6000 about"),
                     encoding="utf-8")

    res = run_script(pmos, "pm_approve.py", "01", cwd=proj)
    assert res.returncode == 0, res.stdout + res.stderr
    approved = [e for e in read_events(proj) if e["event_type"] == "stage_approved" and e["stage"] == "01"]
    payload = approved[-1]["payload"]
    assert payload["edit_distance_method"] == "line_approx"
    assert 0 < payload["char_edit_distance"] < 200


def test_approving_over_unapproved_upstreams_warns(pmos, new_project):
    """An artifact that skipped the pre-stage gate (written by hand or by
    pm_finish_stage.py) can still be approved, but approval names the upstream
    stages that are not approved."""
    proj = new_project("approve-out-of-order", "A problem")
    make_draft(proj, "03", body="## Overview\nPRD.\n")
    res = run_script(pmos, "pm_approve.py", "03", cwd=proj)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "Warning: approving stage 03 while upstream stages are not approved" in res.stdout
    assert "01 (pending)" in res.stdout
    assert stage_status(proj, "03") == "approved"
