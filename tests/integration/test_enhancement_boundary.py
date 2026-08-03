"""E2 decision boundary and repository-stability gate."""
import subprocess
from pathlib import Path

import pytest
import yaml

from helpers import run_script, write_artifact

pytestmark = pytest.mark.integration


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "product"
    repo.mkdir()
    (repo / "api.py").write_text("def export_account(): return {}\n", encoding="utf-8")
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
    _git(repo, "config", "user.name", "tester")
    _git(repo, "config", "user.email", "tester@example.com")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "baseline")
    return repo


def _approved_context_stage(proj: Path, stage_id: str, filename: str, body: str) -> None:
    import frontmatter
    import project
    from hashing import hash_artifact_body

    path = write_artifact(proj / filename, stage=stage_id, project=proj.name, body=body)
    content_hash = hash_artifact_body(str(path))
    frontmatter.update_status(
        str(path), "approved", approved_at="2026-08-03T00:00:00+00:00",
        approved_by="tester", content_hash=content_hash,
    )
    meta = project.load_meta(proj)
    meta["stages"] = [stage for stage in meta["stages"] if stage["id"] != stage_id]
    meta["stages"].append({
        "id": stage_id,
        "name": project.STAGE_NAMES[stage_id],
        "status": "approved",
        "approved_at": "2026-08-03T00:00:00+00:00",
        "content_hash": content_hash,
        "upstream_hashes_at_approval": {},
        "regeneration_count": 0,
        "optional": False,
        "origin": "generated",
    })
    project.save_meta(meta, proj)


def _setup(pmos, new_project, tmp_path: Path):
    repo = _repo(tmp_path)
    proj = new_project("boundary-product")
    approved = run_script(pmos, "pm_approve.py", "00", cwd=proj)
    assert approved.returncode == 0
    _approved_context_stage(
        proj,
        "00c",
        "00-codebase-understanding.md",
        "## Repository identity\nPinned.\n\n## Affected slice\nAccount export.\n",
    )
    _approved_context_stage(
        proj,
        "00u",
        "00-context-understanding.md",
        "## Enhancement Boundary\nExport without changing login.\n",
    )
    ask = proj / "ask.md"
    ask.write_text("Add account export.\n", encoding="utf-8")
    started = run_script(
        pmos, "pm_enhance.py", "start", "--ask-file", str(ask),
        "--codebase", str(repo), cwd=proj,
    )
    assert started.returncode == 0, started.stdout + started.stderr
    return proj, repo


def _boundary_args():
    return (
        "set-boundary",
        "--current-behavior", "Accounts cannot be exported.",
        "--target-behavior", "Authorized users can export their account as JSON.",
        "--surface", "api",
        "--surface", "data",
        "--affected-id", "FR-012",
        "--non-touch", "Login and session issuance",
        "--invariant", "Existing sessions remain valid",
        "--success", "99% of valid exports complete within 10 seconds",
        "--compatibility", "Existing clients receive unchanged account responses",
        "--rollout", "Feature flag for internal accounts first",
        "--rollback", "Disable the export flag without data rollback",
        "--authority", "Product manager",
    )


def test_set_boundary_requires_approved_context_and_records_full_decision(pmos, new_project, tmp_path):
    """Approved 00c/00u plus stable repo produce a complete binding boundary."""
    proj, repo = _setup(pmos, new_project, tmp_path)

    result = run_script(pmos, "pm_enhance.py", *_boundary_args(), cwd=proj)

    assert result.returncode == 0, result.stdout + result.stderr
    context = yaml.safe_load(
        (proj / ".enhancements" / "EH-001" / "context.yaml").read_text(encoding="utf-8")
    )
    boundary = context["boundary"]
    assert boundary["current_behavior"] == "Accounts cannot be exported."
    assert boundary["target_behavior"].startswith("Authorized users")
    assert boundary["affected_surfaces"] == ["api", "data"]
    assert boundary["affected_ids"] == ["FR-012"]
    assert boundary["regression_invariants"] == ["Existing sessions remain valid"]
    assert boundary["decision_authority"] == "Product manager"
    assert boundary["source_artifact"] == "00-context-understanding.md"
    assert context["repository"]["scan_end_sha"] == _git(repo, "rev-parse", "HEAD")
    assert context["repository"]["fingerprint_after"] == context["repository"]["fingerprint_before"]


def test_set_boundary_refuses_unaccepted_blocking_unknown(pmos, new_project, tmp_path):
    """A load-bearing unknown blocks the boundary unless the same risk is explicit."""
    proj, _repo_path = _setup(pmos, new_project, tmp_path)

    blocked = run_script(
        pmos, "pm_enhance.py", *_boundary_args(),
        "--blocking-unknown", "Production export retention is unknown", cwd=proj,
    )
    assert blocked.returncode != 0
    assert "blocking unknown" in (blocked.stdout + blocked.stderr).lower()

    accepted = run_script(
        pmos, "pm_enhance.py", *_boundary_args(),
        "--blocking-unknown", "Production export retention is unknown",
        "--accepted-risk", "Production export retention is unknown", cwd=proj,
    )
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    context = yaml.safe_load(
        (proj / ".enhancements" / "EH-001" / "context.yaml").read_text(encoding="utf-8")
    )
    assert context["boundary"]["accepted_risks"] == ["Production export retention is unknown"]


def test_set_boundary_refuses_repository_drift_without_rewriting_context(pmos, new_project, tmp_path):
    """Code drift after scan start blocks approval and keeps the prior context intact."""
    proj, repo = _setup(pmos, new_project, tmp_path)
    context_path = proj / ".enhancements" / "EH-001" / "context.yaml"
    before = context_path.read_bytes()
    (repo / "api.py").write_text("def export_account(): return {'changed': True}\n", encoding="utf-8")

    result = run_script(pmos, "pm_enhance.py", *_boundary_args(), cwd=proj)

    assert result.returncode != 0
    assert "repository changed" in (result.stdout + result.stderr).lower()
    assert context_path.read_bytes() == before
