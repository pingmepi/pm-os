"""T7 — idempotency: repeating a safe operation doesn't change the outcome or corrupt state.
See docs/TESTING.md §5 (T7)."""
import pytest

from helpers import run_script, make_draft

pytestmark = pytest.mark.integration


def test_approve_already_approved_is_noop(pmos, new_project):
    """Approving an already-approved stage is a clean no-op (exit 0, no state change)."""
    proj = new_project("idem-appr", "p")
    run_script(pmos, "pm_approve.py", "00", cwd=proj)
    import project
    hash_before = project.get_stage(project.load_meta(proj), "00")["content_hash"]
    res = run_script(pmos, "pm_approve.py", "00", cwd=proj)
    assert res.returncode == 0
    assert "already approved" in res.stdout.lower()
    assert project.get_stage(project.load_meta(proj), "00")["content_hash"] == hash_before


def test_status_is_stable_across_runs(pmos, new_project):
    """pm_status produces the same output on repeated runs (pure read, no side effects)."""
    proj = new_project("idem-status", "p")
    run_script(pmos, "pm_approve.py", "00", cwd=proj)
    a = run_script(pmos, "pm_status.py", cwd=proj)
    b = run_script(pmos, "pm_status.py", cwd=proj)
    assert a.returncode == 0 and b.returncode == 0
    # Strip the only volatile bit (relative "age" of approvals) and compare the rest.
    def _norm(s):
        return [ln for ln in s.splitlines() if "ago" not in ln.lower()]
    assert _norm(a.stdout) == _norm(b.stdout)


def test_html_render_idempotent(pmos, new_project):
    """Rendering the stage-04 companion twice yields identical output (deterministic render)."""
    import html_render
    proj = new_project("idem-html", "p")
    make_draft(proj, "04", body="## Information Architecture\nNav.\n\n## States\nLoading.\n")
    run_script(pmos, "pm_approve.py", "04", cwd=proj)  # first render via post-approve
    out1 = html_render.render_design_spec(proj).read_text()
    out2 = html_render.render_design_spec(proj).read_text()
    assert out1 == out2
