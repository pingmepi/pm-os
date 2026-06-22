"""T5 (connection) — real central sync against a LOCAL bare feedback repo (no network).
Exercises the actual git clone/copy/commit/push path the unit tests stubbed out.
See docs/guides/testing.md §5 (T5)."""
import subprocess

import pytest

from helpers import run_script

pytestmark = [pytest.mark.integration, pytest.mark.connection]


def _bare_has_commits(pmos):
    r = subprocess.run(["git", "-C", str(pmos.feedback), "log", "--oneline"],
                       capture_output=True, text=True)
    return r.returncode == 0 and bool(r.stdout.strip())


def test_approval_pushes_to_local_feedback_repo(pmos, new_project):
    """Approving a stage syncs telemetry/feedback into the cache and pushes to the (local bare)
    feedback repo — the real git path, end to end."""
    proj = new_project("sync-real", "A problem")
    res = run_script(pmos, "pm_approve.py", "00", cwd=proj)
    assert res.returncode == 0, res.stderr
    cache = pmos.home / ".pm-os-feedback-cache" / "telemetry" / "tester" / "sync-real"
    assert (cache / "telemetry.jsonl").exists(), "telemetry should be copied into the cache"
    assert _bare_has_commits(pmos), "the bare feedback repo should have received a pushed commit"


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
