"""E2 explicit refresh and same-project multi-cycle completion."""
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


def _repo(tmp_path):
    repo = tmp_path / "product"
    repo.mkdir()
    (repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
    _git(repo, "config", "user.name", "tester")
    _git(repo, "config", "user.email", "tester@example.com")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "v1")
    return repo


def _approve(pmos, project, stage, body):
    make_draft(project, stage, body=body)
    result = run_script(pmos, "pm_approve.py", stage, cwd=project)
    assert result.returncode == 0, result.stdout + result.stderr


def _record_boundary(project, affected=None):
    path = project / ".enhancements" / "EH-001" / "context.yaml"
    context = yaml.safe_load(path.read_text(encoding="utf-8"))
    context["boundary"].update({
        "recorded_at": "2026-08-03T00:00:00+00:00",
        "current_behavior": "v1", "target_behavior": "v2",
        "affected_ids": affected or [], "affected_surfaces": ["service"],
        "non_touch_surfaces": ["login"], "regression_invariants": ["login works"],
    })
    path.write_text(yaml.safe_dump(context, sort_keys=False), encoding="utf-8")
    return path


def test_refresh_repins_clean_checkout_preserves_baseline_and_stales_pipeline(
    pmos, new_project, tmp_path,
):
    repo = _repo(tmp_path)
    project = new_project("refresh-product")
    assert run_script(pmos, "pm_approve.py", "00", cwd=project).returncode == 0
    _approve(pmos, project, "03", "### FR-001 — Original\n")
    ask = project / "ask.md"
    ask.write_text("Change service.\n", encoding="utf-8")
    assert run_script(
        pmos, "pm_enhance.py", "start", "--ask-file", str(ask),
        "--codebase", str(repo), cwd=project,
    ).returncode == 0
    context_path = _record_boundary(project, ["FR-001"])
    before = yaml.safe_load(context_path.read_text(encoding="utf-8"))
    baseline_path = project / before["baseline"]["artifacts"]["03"]["snapshot_path"]
    baseline_bytes = baseline_path.read_bytes()
    (repo / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "v2")
    new_sha = _git(repo, "rev-parse", "HEAD")

    result = run_script(pmos, "pm_enhance.py", "refresh", "--ref", new_sha, cwd=project)

    assert result.returncode == 0, result.stdout + result.stderr
    after = yaml.safe_load(context_path.read_text(encoding="utf-8"))
    assert after["repository"]["scan_start_sha"] == new_sha
    assert after["boundary"].get("recorded_at") is None
    assert len(after["repository_refreshes"]) == 1
    assert baseline_path.read_bytes() == baseline_bytes
    meta = yaml.safe_load((project / ".meta.yaml").read_text(encoding="utf-8"))
    assert next(stage for stage in meta["stages"] if stage["id"] == "03")["status"] == "stale"


def test_refresh_refuses_dirty_checkout_without_mutating_context(pmos, new_project, tmp_path):
    repo = _repo(tmp_path)
    project = new_project("dirty-refresh")
    assert run_script(pmos, "pm_approve.py", "00", cwd=project).returncode == 0
    ask = project / "ask.md"
    ask.write_text("Change service.\n", encoding="utf-8")
    assert run_script(
        pmos, "pm_enhance.py", "start", "--ask-file", str(ask),
        "--codebase", str(repo), cwd=project,
    ).returncode == 0
    context_path = project / ".enhancements" / "EH-001" / "context.yaml"
    before = context_path.read_bytes()
    (repo / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")

    result = run_script(
        pmos, "pm_enhance.py", "refresh", "--ref", _git(repo, "rev-parse", "HEAD"),
        cwd=project,
    )

    assert result.returncode != 0
    assert "dirty" in (result.stdout + result.stderr).lower()
    assert context_path.read_bytes() == before


def test_complete_then_start_second_cycle_in_same_project(pmos, new_project):
    project = new_project("two-cycle-product")
    assert run_script(pmos, "pm_approve.py", "00", cwd=project).returncode == 0
    bodies = {
        "01": "Brief baseline.\n", "02": "Scope baseline.\n",
        "03": "### FR-001 — Baseline service\n",
        "04": "Design baseline.\n", "05": "Validation baseline.\n",
        "06": "QA baseline.\n", "07": "Metrics baseline.\n", "08": "TRD baseline.\n",
    }
    for stage, body in bodies.items():
        _approve(pmos, project, stage, body)
    ask_a = project / "ask-a.md"
    ask_a.write_text("Enhancement A.\n", encoding="utf-8")
    assert run_script(pmos, "pm_enhance.py", "start", "--ask-file", str(ask_a), cwd=project).returncode == 0
    _record_boundary(project, ["FR-001"])
    _approve(
        pmos, project, "03",
        (
            "### FR-001 — Updated service\n"
            "Change type: modified\n"
            "Affected surfaces: service\n"
        ),
    )
    # Reapprove downstream product-of-record artifacts after normal staleness cascade.
    for stage in ("04", "05"):
        result = run_script(pmos, "pm_approve.py", stage, cwd=project)
        assert result.returncode == 0, result.stdout + result.stderr
    _approve(
        pmos, project, "06",
        "### TC-001 — Service regression\nChange type: new\nCovers: FR-001\nInvariant: login works\n",
    )
    result = run_script(pmos, "pm_approve.py", "07", cwd=project)
    assert result.returncode == 0, result.stdout + result.stderr
    _approve(
        pmos, project, "08",
        "## Work Breakdown\n### TSK-001 — Update service\nChange type: new\n- **Implements:** FR-001\n",
    )

    completed = run_script(pmos, "pm_enhance.py", "complete", cwd=project)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    index = yaml.safe_load((project / ".enhancements" / "index.yaml").read_text())
    assert index["active_cycle"] is None
    cycle_a_path = project / ".enhancements" / "EH-001" / "context.yaml"
    cycle_a_bytes = cycle_a_path.read_bytes()
    assert yaml.safe_load(cycle_a_bytes)["completed_at"]

    ask_b = project / "ask-b.md"
    ask_b.write_text("Enhancement B.\n", encoding="utf-8")
    started_b = run_script(pmos, "pm_enhance.py", "start", "--ask-file", str(ask_b), cwd=project)
    assert started_b.returncode == 0, started_b.stdout + started_b.stderr
    context_b = yaml.safe_load(
        (project / ".enhancements" / "EH-002" / "context.yaml").read_text()
    )
    assert context_b["previous_cycle_id"] == "EH-001"
    baseline_b = project / context_b["baseline"]["artifacts"]["03"]["snapshot_path"]
    assert "Updated service" in baseline_b.read_text(encoding="utf-8")
    assert cycle_a_path.read_bytes() == cycle_a_bytes


def test_complete_retry_recovers_pointer_after_interrupted_atomic_writes(pmos, new_project):
    """If context landed before index clearing, retry repairs only the active pointer."""
    project = new_project("complete-recovery")
    assert run_script(pmos, "pm_approve.py", "00", cwd=project).returncode == 0
    ask = project / "ask.md"
    ask.write_text("Recovery test.\n", encoding="utf-8")
    assert run_script(pmos, "pm_enhance.py", "start", "--ask-file", str(ask), cwd=project).returncode == 0
    context_path = project / ".enhancements" / "EH-001" / "context.yaml"
    context = yaml.safe_load(context_path.read_text())
    context["completed_at"] = "2026-08-03T01:00:00+00:00"
    context["completion"] = {"delta_change_count": 1, "approved_product_stages": []}
    context_path.write_text(yaml.safe_dump(context, sort_keys=False), encoding="utf-8")
    completed_bytes = context_path.read_bytes()

    result = run_script(pmos, "pm_enhance.py", "complete", cwd=project)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "recovered" in result.stdout.lower()
    index = yaml.safe_load((project / ".enhancements" / "index.yaml").read_text())
    assert index["active_cycle"] is None
    assert context_path.read_bytes() == completed_bytes
