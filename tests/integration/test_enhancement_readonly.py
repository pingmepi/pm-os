"""E2 repository identity and target-read-only guarantees."""
import hashlib
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from helpers import run_script

pytestmark = pytest.mark.integration


def _run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def _make_repo(tmp_path: Path, dirty: bool = False) -> Path:
    repo = tmp_path / ("dirty-product-repo" if dirty else "product-repo")
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "api.py").write_text("def export_account():\n    return {}\n", encoding="utf-8")
    (repo / "README.md").write_text("# Product\n", encoding="utf-8")
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
    _run_git(repo, "config", "user.name", "tester")
    _run_git(repo, "config", "user.email", "tester@example.com")
    _run_git(repo, "add", ".")
    _run_git(repo, "commit", "-m", "baseline")
    if dirty:
        (repo / "src" / "api.py").write_text(
            "def export_account():\n    return {'draft': True}\n", encoding="utf-8"
        )
    return repo


def _tree_digest(repo: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(repo.rglob("*")):
        if ".git" in path.relative_to(repo).parts or not path.is_file():
            continue
        digest.update(path.relative_to(repo).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _set_read_only(repo: Path, read_only: bool) -> None:
    file_mode = 0o444 if read_only else 0o644
    dir_mode = 0o555 if read_only else 0o755
    for current, directories, files in os.walk(repo, topdown=False):
        for name in files:
            os.chmod(Path(current) / name, file_mode)
        for name in directories:
            os.chmod(Path(current) / name, dir_mode)
    os.chmod(repo, dir_mode)


def _approve_and_ask(pmos, new_project, slug: str):
    proj = new_project(slug)
    approved = run_script(pmos, "pm_approve.py", "00", cwd=proj)
    assert approved.returncode == 0, approved.stdout + approved.stderr
    ask = proj / "enhancement-ask.md"
    ask.write_text("Add an account export API without changing login.\n", encoding="utf-8")
    return proj, ask


def test_start_records_reproducible_repository_identity_without_mutation(
    pmos, new_project, tmp_path
):
    """A clean local checkout records SHA/fingerprint and stays byte-for-byte unchanged."""
    repo = _make_repo(tmp_path)
    proj, ask = _approve_and_ask(pmos, new_project, "readonly-identity")
    sha_before = _run_git(repo, "rev-parse", "HEAD")
    status_before = _run_git(repo, "status", "--porcelain")
    digest_before = _tree_digest(repo)

    result = run_script(
        pmos,
        "pm_enhance.py",
        "start",
        "--ask-file",
        str(ask),
        "--codebase",
        str(repo),
        "--ref",
        "main",
        cwd=proj,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    context = yaml.safe_load(
        (proj / ".enhancements" / "EH-001" / "context.yaml").read_text(encoding="utf-8")
    )
    identity = context["repository"]
    assert identity["requested_ref"] == "main"
    assert identity["resolved_sha"] == sha_before
    assert identity["scan_start_sha"] == sha_before
    assert identity["dirty"] is False
    assert identity["porcelain_before"] == ""
    assert len(identity["fingerprint_before"]) == 64
    assert identity["fingerprint_algorithm"] == "sha256(git-visible-path+kind+bytes)"
    assert _run_git(repo, "rev-parse", "HEAD") == sha_before
    assert _run_git(repo, "status", "--porcelain") == status_before
    assert _tree_digest(repo) == digest_before


def test_start_succeeds_when_entire_target_checkout_is_read_only(pmos, new_project, tmp_path):
    """E2 performs no target write even when repository permissions forbid all writes."""
    repo = _make_repo(tmp_path)
    proj, ask = _approve_and_ask(pmos, new_project, "permissions-proof")
    digest_before = _tree_digest(repo)
    _set_read_only(repo, True)
    try:
        result = run_script(
            pmos, "pm_enhance.py", "start", "--ask-file", str(ask),
            "--codebase", str(repo), cwd=proj,
        )
    finally:
        _set_read_only(repo, False)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _tree_digest(repo) == digest_before
    assert _run_git(repo, "status", "--porcelain") == ""


def test_start_records_dirty_checkout_as_non_reproducible(pmos, new_project, tmp_path):
    """Dirty checkout evidence is retained instead of being silently called reproducible."""
    repo = _make_repo(tmp_path, dirty=True)
    proj, ask = _approve_and_ask(pmos, new_project, "dirty-proof")

    result = run_script(
        pmos, "pm_enhance.py", "start", "--ask-file", str(ask),
        "--codebase", str(repo), cwd=proj,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    context = yaml.safe_load(
        (proj / ".enhancements" / "EH-001" / "context.yaml").read_text(encoding="utf-8")
    )
    identity = context["repository"]
    assert identity["dirty"] is True
    assert "src/api.py" in identity["porcelain_before"]
    assert identity["non_reproducible_reason"] == "checkout has uncommitted or untracked files"
