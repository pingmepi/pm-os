"""Per-project local git version history end-to-end (backlog #18, local half):
scaffolding initializes a repo with an initial commit, each approval adds a
commit, and the enhancement clone stays ignored. Exercises the real pm_new.py
scaffold + pm_approve.py → post-approve.py commit path through the isolated
temp install. See docs/guides/testing.md §5 (T2)."""
import subprocess

import pytest

from helpers import run_script

pytestmark = pytest.mark.integration


def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def _commit_count(root):
    r = _git(root, "rev-list", "--count", "HEAD")
    return int(r.stdout.strip()) if r.returncode == 0 else 0


def test_scaffold_creates_git_repo(new_project):
    """pm_new.py leaves the project as a git repo with an initial commit and a
    .gitignore that excludes the enhancement clone."""
    proj = new_project(slug="vers-demo")
    assert (proj / ".git").is_dir()
    assert _commit_count(proj) == 1
    assert ".codebase/" in (proj / ".gitignore").read_text(encoding="utf-8")


def test_approval_adds_commit(new_project, pmos):
    """Approving a stage adds exactly one commit whose message names the stage."""
    proj = new_project(slug="vers-approve")
    before = _commit_count(proj)
    res = run_script(pmos, "pm_approve.py", "00", cwd=proj)
    assert res.returncode == 0, f"{res.stdout}\n{res.stderr}"
    assert _commit_count(proj) == before + 1
    subject = _git(proj, "log", "-1", "--format=%s").stdout.strip()
    assert subject.startswith("approve: stage 00")


def test_codebase_dir_ignored_end_to_end(new_project, pmos):
    """A .codebase/ clone present at approval time is never tracked."""
    proj = new_project(slug="vers-codebase")
    (proj / ".codebase").mkdir()
    (proj / ".codebase" / "clone.bin").write_text("x", encoding="utf-8")
    run_script(pmos, "pm_approve.py", "00", cwd=proj)
    assert ".codebase/" not in _git(proj, "ls-files").stdout
