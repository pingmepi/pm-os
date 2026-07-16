"""T5 (connection) — real central sync against a LOCAL bare feedback repo (no network).
Exercises the actual git clone/copy/commit/push path the unit tests stubbed out.
See docs/guides/testing.md §5 (T5)."""
import subprocess
import time

import pytest

from helpers import run_script, stage_status

pytestmark = [pytest.mark.integration, pytest.mark.connection]


def _bare_has_commits(pmos):
    r = subprocess.run(["git", "-C", str(pmos.feedback), "log", "--oneline"],
                       capture_output=True, text=True)
    return r.returncode == 0 and bool(r.stdout.strip())


def _wait_for_commits(pmos, timeout=15.0):
    """Poll the bare feedback repo until a commit lands or timeout (the deferred
    push runs in a detached process, so it completes shortly after approval)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _bare_has_commits(pmos):
            return True
        time.sleep(0.2)
    return False


def test_approval_pushes_to_local_feedback_repo(pmos, new_project):
    """Approving a stage syncs telemetry/feedback into the cache and pushes to the (local bare)
    feedback repo — the real git path, end to end."""
    proj = new_project("sync-real", "A problem")
    res = run_script(pmos, "pm_approve.py", "00", cwd=proj)
    assert res.returncode == 0, res.stderr
    cache = pmos.home / ".pm-os-feedback-cache" / "telemetry" / "tester" / "sync-real"
    assert (cache / "telemetry.jsonl").exists(), "telemetry should be copied into the cache"
    assert _bare_has_commits(pmos), "the bare feedback repo should have received a pushed commit"


def test_deferred_approval_sync_does_not_block(pmos, new_project):
    """With PM_OS_SYNC_BLOCKING unset (the interactive default), approval returns immediately
    without waiting on the network push (backlog #6): local state is approved, the output
    tells the PM the sync is backgrounded, and the detached push still lands in the bare repo."""
    proj = new_project("sync-deferred", "A problem")
    res = run_script(pmos, "pm_approve.py", "00", cwd=proj,
                     extra_env={"PM_OS_SYNC_BLOCKING": ""})
    assert res.returncode == 0, res.stderr
    # Approval is durable + confirmed regardless of the (still in-flight) push.
    assert stage_status(proj, "00") == "approved"
    assert "background" in (res.stdout + res.stderr).lower()
    # The detached push still completes shortly after, landing a commit centrally.
    assert _wait_for_commits(pmos), "deferred background push should still reach the feedback repo"


def test_pm_sync_backfills_all_and_verify(pmos, new_project):
    """pm_sync pushes every project, then --verify reports all telemetry chains intact."""
    p1 = new_project("proj-a", "A")
    p2 = new_project("proj-b", "B")
    run_script(pmos, "pm_approve.py", "00", cwd=p1)
    run_script(pmos, "pm_approve.py", "00", cwd=p2)

    push = run_script(pmos, "pm_sync.py", cwd=p1)
    assert push.returncode == 0, push.stderr
    for slug in ("proj-a", "proj-b"):
        assert (pmos.home / ".pm-os-feedback-cache" / "telemetry" / "tester" / slug / "telemetry.jsonl").exists()

    verify = run_script(pmos, "pm_sync.py", "--verify", cwd=p1)
    assert verify.returncode == 0, verify.stdout + verify.stderr
    assert "intact" in verify.stdout.lower()
