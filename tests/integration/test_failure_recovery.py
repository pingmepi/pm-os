"""T7 — negative / resilience: broken or hostile local state must fail with a clear error and
never corrupt the project. See docs/TESTING.md §5 (T7)."""
import subprocess

import pytest

from helpers import run_script

pytestmark = pytest.mark.integration


def test_malformed_meta_errors_cleanly(pmos, new_project):
    """A corrupted .meta.yaml causes a command to fail (non-zero) rather than crash silently or
    write garbage back."""
    proj = new_project("bad-meta", "p")
    (proj / ".meta.yaml").write_text("this: : : not valid yaml\n  - broken\n", encoding="utf-8")
    res = run_script(pmos, "pm_status.py", cwd=proj)
    assert res.returncode != 0


def test_not_inside_a_project_errors(pmos):
    """Running a project command outside any PM-OS project fails with the resolve error."""
    res = run_script(pmos, "pm_status.py", cwd=pmos.home)
    assert res.returncode != 0
    assert "project" in (res.stdout + res.stderr).lower()


def test_approve_artifact_without_frontmatter_fails(pmos, new_project):
    """An artifact with no frontmatter is treated as not-generated and cannot be approved."""
    proj = new_project("no-fm", "p")
    (proj / "01-brief.md").write_text("Just a body, no frontmatter.\n", encoding="utf-8")
    res = run_script(pmos, "pm_approve.py", "01", cwd=proj)
    assert res.returncode != 0


def test_corrupt_telemetry_detected_by_verify(pmos, new_project):
    """A tampered telemetry line is caught by pm_sync --verify (non-zero exit)."""
    proj = new_project("corrupt-tel", "p")
    run_script(pmos, "pm_approve.py", "00", cwd=proj)
    tel = proj / "telemetry.jsonl"
    lines = tel.read_text().splitlines()
    lines[0] = lines[0].replace('"event_type"', '"event_type_TAMPERED"', 1)
    tel.write_text("\n".join(lines) + "\n", encoding="utf-8")
    res = run_script(pmos, "pm_sync.py", "--verify", cwd=proj)
    assert res.returncode != 0


def test_pm_new_non_interactive_requires_genai_decision(pmos):
    """pm_new in non-interactive mode with no --genai/--no-genai and no env flag fails rather
    than hanging on the prompt."""
    env = dict(pmos.env)
    env.pop("PM_OS_GENAI_FLAG", None)
    res = subprocess.run(
        ["python3", str(pmos.install / "scripts" / "pm_new.py"), "needs-genai", "A problem"],
        cwd=str(pmos.projects), env=env, input="", capture_output=True, text=True, timeout=60)
    assert res.returncode != 0
