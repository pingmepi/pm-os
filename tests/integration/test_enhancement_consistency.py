"""E2 consistency findings and status guidance."""
import subprocess
from pathlib import Path

import pytest
import yaml

from helpers import make_draft, run_script

pytestmark = pytest.mark.integration


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def _active_project(pmos, new_project, tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("FEATURE = 'baseline'\n", encoding="utf-8")
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
    _git(repo, "config", "user.name", "tester")
    _git(repo, "config", "user.email", "tester@example.com")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "baseline")
    proj = new_project("consistency-enhancement")
    assert run_script(pmos, "pm_approve.py", "00", cwd=proj).returncode == 0
    ask = proj / "ask.md"
    ask.write_text("Change feature.\n", encoding="utf-8")
    started = run_script(
        pmos, "pm_enhance.py", "start", "--ask-file", str(ask),
        "--codebase", str(repo), cwd=proj,
    )
    assert started.returncode == 0
    return proj, repo


def test_check_reports_active_boundary_missing(pmos, new_project, tmp_path):
    """An active cycle cannot look healthy before its approved boundary is recorded."""
    proj, _repo = _active_project(pmos, new_project, tmp_path)

    result = run_script(pmos, "pm_check.py", cwd=proj)

    assert result.returncode != 0
    assert "ENHANCEMENT_BOUNDARY_MISSING" in result.stdout
    assert "set-boundary" in result.stdout


def test_check_reports_repository_drift_after_boundary_scan(pmos, new_project, tmp_path):
    """Current checkout movement is an error against the active pinned cycle."""
    proj, repo = _active_project(pmos, new_project, tmp_path)
    context_path = proj / ".enhancements" / "EH-001" / "context.yaml"
    context = yaml.safe_load(context_path.read_text(encoding="utf-8"))
    context["boundary"].update({
        "recorded_at": "2026-08-03T00:00:00+00:00",
        "current_behavior": "baseline", "target_behavior": "changed",
        "affected_surfaces": ["service"], "affected_ids": [],
        "non_touch_surfaces": ["login"], "regression_invariants": ["login works"],
    })
    context["repository"]["scan_end_sha"] = context["repository"]["scan_start_sha"]
    context["repository"]["porcelain_after"] = context["repository"]["porcelain_before"]
    context["repository"]["fingerprint_after"] = context["repository"]["fingerprint_before"]
    context_path.write_text(yaml.safe_dump(context, sort_keys=False), encoding="utf-8")
    (repo / "app.py").write_text("FEATURE = 'drifted'\n", encoding="utf-8")

    result = run_script(pmos, "pm_check.py", cwd=proj)

    assert result.returncode != 0
    assert "ENHANCEMENT_REPOSITORY_DRIFT" in result.stdout


def test_check_reports_malformed_enhancement_context(pmos, new_project, tmp_path):
    """Malformed enhancement YAML is isolated as an actionable consistency error."""
    proj, _repo = _active_project(pmos, new_project, tmp_path)
    (proj / ".enhancements" / "EH-001" / "context.yaml").write_text(
        "id: [unterminated", encoding="utf-8"
    )

    result = run_script(pmos, "pm_check.py", cwd=proj)

    assert result.returncode != 0
    assert "ENHANCEMENT_CONTEXT_INVALID" in result.stdout


def test_status_shows_active_cycle_boundary_and_next_action(pmos, new_project, tmp_path):
    """Status derives E2 guidance without adding a stage-status state machine."""
    proj, _repo = _active_project(pmos, new_project, tmp_path)

    result = run_script(pmos, "pm_status.py", cwd=proj)

    assert result.returncode == 0
    assert "Enhancement: EH-001 active" in result.stdout
    assert "Boundary: not recorded" in result.stdout
    assert "Next: approve 00c/00u and run /pm-enhance set-boundary" in result.stdout


def test_check_reports_corrupted_frozen_baseline(pmos, new_project, tmp_path):
    proj, _repo = _active_project(pmos, new_project, tmp_path)
    context = yaml.safe_load(
        (proj / ".enhancements" / "EH-001" / "context.yaml").read_text()
    )
    snapshot = proj / context["baseline"]["artifacts"]["00"]["snapshot_path"]
    snapshot.write_text(snapshot.read_text() + "corrupt\n", encoding="utf-8")

    result = run_script(pmos, "pm_check.py", cwd=proj)

    assert result.returncode != 0
    assert "ENHANCEMENT_BASELINE_INVALID" in result.stdout


def test_check_traces_delta_surface_tests_tasks_and_migration(
    pmos, new_project, tmp_path,
):
    repo = tmp_path / "trace-repo"
    repo.mkdir()
    (repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
    _git(repo, "config", "user.name", "tester")
    _git(repo, "config", "user.email", "tester@example.com")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "baseline")
    proj = new_project("trace-enhancement")
    assert run_script(pmos, "pm_approve.py", "00", cwd=proj).returncode == 0
    make_draft(proj, "03", body="### FR-001 — Existing behavior\n")
    assert run_script(pmos, "pm_approve.py", "03", cwd=proj).returncode == 0
    ask = proj / "ask.md"
    ask.write_text("Add behavior.\n", encoding="utf-8")
    assert run_script(
        pmos, "pm_enhance.py", "start", "--ask-file", str(ask),
        "--codebase", str(repo), cwd=proj,
    ).returncode == 0
    context_path = proj / ".enhancements" / "EH-001" / "context.yaml"
    context = yaml.safe_load(context_path.read_text())
    context["boundary"].update({
        "recorded_at": "2026-08-03T00:00:00+00:00", "current_behavior": "old",
        "target_behavior": "new", "affected_ids": ["FR-001"],
        "affected_surfaces": ["service"], "regression_invariants": ["login works"],
        "compatibility_migration": ["migrate legacy rows"],
    })
    context_path.write_text(yaml.safe_dump(context, sort_keys=False), encoding="utf-8")
    make_draft(
        proj, "03",
        body=(
            "### FR-001 — Existing behavior\n"
            "### FR-002 — New unbounded behavior\n"
        ),
    )
    assert run_script(pmos, "pm_approve.py", "03", cwd=proj).returncode == 0
    make_draft(proj, "06", body="### TC-001 — unrelated\nCovers: FR-001\n")
    assert run_script(pmos, "pm_approve.py", "06", cwd=proj).returncode == 0
    make_draft(proj, "08", body="## Work Breakdown\nNo stable task.\n")
    assert run_script(pmos, "pm_approve.py", "08", cwd=proj).returncode == 0

    result = run_script(pmos, "pm_check.py", cwd=proj)

    assert result.returncode != 0
    assert "ENHANCEMENT_CHANGE_OUTSIDE_BOUNDARY" in result.stdout
    assert "ENHANCEMENT_CHANGE_TYPE_MISMATCH" in result.stdout
    assert "ENHANCEMENT_SURFACE_TRACE_MISSING" in result.stdout
    assert "ENHANCEMENT_IMPLEMENTATION_TRACE_MISSING" in result.stdout
    assert "ENHANCEMENT_INVARIANT_TRACE_MISSING" in result.stdout
    assert "ENHANCEMENT_MIGRATION_TRACE_MISSING" in result.stdout
