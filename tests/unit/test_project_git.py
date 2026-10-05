"""Unit tests for lib/project_git.py — per-project local git version history
(backlog #18, local half). Covers repo init, `.gitignore` handling, commit /
no-op, identity injection with no ambient git config, and warn-not-fail when git
is unavailable. See docs/guides/testing.md §5 (T1)."""
import subprocess

import pytest

import project_git as pg

pytestmark = pytest.mark.unit


def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def _commit_count(root):
    r = _git(root, "rev-list", "--count", "HEAD")
    return int(r.stdout.strip()) if r.returncode == 0 else 0


def test_init_creates_repo_and_initial_commit(tmp_path):
    """init_project_repo initializes .git, writes .gitignore, and makes one commit."""
    (tmp_path / "00-business-statement.md").write_text("hi", encoding="utf-8")
    status = pg.init_project_repo(tmp_path, pm_user="tester")
    assert status["ok"], status
    assert (tmp_path / ".git").is_dir()
    assert (tmp_path / ".gitignore").exists()
    assert _commit_count(tmp_path) == 1


def test_gitignore_written_with_codebase(tmp_path):
    """A fresh project gets a .gitignore that excludes the enhancement clone."""
    pg.ensure_gitignore(tmp_path)
    content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert ".codebase/" in content
    assert ".pm-os-sync.log" in content


def test_gitignore_preserves_existing_and_adds_codebase(tmp_path):
    """An existing .gitignore is preserved; .codebase/ is appended if missing."""
    gi = tmp_path / ".gitignore"
    gi.write_text("node_modules/\n", encoding="utf-8")
    pg.ensure_gitignore(tmp_path)
    content = gi.read_text(encoding="utf-8")
    assert "node_modules/" in content
    assert ".codebase/" in content


def test_commit_all_adds_commit(tmp_path):
    """A second commit_all after a change adds exactly one commit."""
    (tmp_path / "00-business-statement.md").write_text("one", encoding="utf-8")
    pg.init_project_repo(tmp_path, pm_user="tester")
    assert _commit_count(tmp_path) == 1
    (tmp_path / "01-brief.md").write_text("two", encoding="utf-8")
    status = pg.commit_all(tmp_path, "approve: stage 00 business-statement", pm_user="tester")
    assert status["ok"] and status["reason"] == "committed"
    assert _commit_count(tmp_path) == 2


def test_commit_all_nothing_to_commit(tmp_path):
    """commit_all on a clean tree is a successful no-op, not an error."""
    (tmp_path / "00-business-statement.md").write_text("one", encoding="utf-8")
    pg.init_project_repo(tmp_path, pm_user="tester")
    status = pg.commit_all(tmp_path, "no changes", pm_user="tester")
    assert status["ok"] and status["reason"] == "nothing to commit"
    assert _commit_count(tmp_path) == 1


def test_codebase_dir_is_not_tracked(tmp_path):
    """Files under .codebase/ never get committed (the clone has its own git)."""
    (tmp_path / "00-business-statement.md").write_text("one", encoding="utf-8")
    (tmp_path / ".codebase").mkdir()
    (tmp_path / ".codebase" / "huge.bin").write_text("x", encoding="utf-8")
    pg.init_project_repo(tmp_path, pm_user="tester")
    tracked = _git(tmp_path, "ls-files").stdout
    assert ".codebase/" not in tracked
    assert "00-business-statement.md" in tracked


def test_identity_injected_without_global_config(tmp_path, monkeypatch):
    """With no ambient git identity (env cleared, global/system config ignored),
    the -c injection still supplies a valid author AND committer = pm_user."""
    for var in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
                "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
        monkeypatch.delenv(var, raising=False)
    # Point global/system config at nonexistent files so no machine identity leaks in.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "no-global"))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(tmp_path / "no-system"))
    (tmp_path / "00-business-statement.md").write_text("one", encoding="utf-8")
    status = pg.init_project_repo(tmp_path, pm_user="alice")
    assert status["ok"], status
    assert _git(tmp_path, "log", "-1", "--format=%an").stdout.strip() == "alice"
    assert _git(tmp_path, "log", "-1", "--format=%cn").stdout.strip() == "alice"


def test_git_unavailable_warns_not_raises(tmp_path, monkeypatch):
    """When git is unavailable both entry points degrade gracefully — no raise,
    no repo, ok=False with an explanatory reason."""
    monkeypatch.setattr(pg, "git_available", lambda: False)
    init = pg.init_project_repo(tmp_path, pm_user="tester")
    assert init["ok"] is False and "git not available" in init["reason"]
    assert not (tmp_path / ".git").exists()
    commit = pg.commit_all(tmp_path, "msg", pm_user="tester")
    assert commit["ok"] is False and "git not available" in commit["reason"]


def test_commit_all_leaves_out_untracked_files_pm_os_does_not_own(tmp_path):
    """Backlog #61. An approval commit includes PM-OS's own files and changes to
    files already tracked, but not a PM's untracked working files (scripts, notes,
    screenshots). Those are listed in ``untracked_left_out`` instead."""
    (tmp_path / "00-business-statement.md").write_text("one", encoding="utf-8")
    (tmp_path / "notes.md").write_text("personal", encoding="utf-8")
    pg.init_project_repo(tmp_path, pm_user="tester")
    assert "notes.md" not in _git(tmp_path, "ls-files").stdout

    (tmp_path / "01-brief.md").write_text("brief", encoding="utf-8")
    (tmp_path / ".history").mkdir()
    (tmp_path / ".history" / "01-brief.20260101T000000Z.generated.md").write_text("b", encoding="utf-8")
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "helper.py").write_text("print(1)", encoding="utf-8")
    (tmp_path / "screenshot.png").write_bytes(b"\x89PNG")
    status = pg.commit_all(tmp_path, "approve: stage 01 brief", pm_user="tester")
    assert status["ok"] and status["reason"] == "committed", status
    tracked = _git(tmp_path, "ls-files").stdout.split()
    assert "01-brief.md" in tracked
    assert ".history/01-brief.20260101T000000Z.generated.md" in tracked
    assert not any(p in tracked for p in ("notes.md", "tools/helper.py", "screenshot.png"))
    assert set(status["untracked_left_out"]) >= {"notes.md", "tools/helper.py", "screenshot.png"}


def test_commit_all_includes_changes_to_files_the_pm_already_tracks(tmp_path):
    """Backlog #61. A file the PM committed themselves stays versioned: its later
    edits (and its deletion) are included in the next approval commit."""
    (tmp_path / "00-business-statement.md").write_text("one", encoding="utf-8")
    pg.init_project_repo(tmp_path, pm_user="tester")
    (tmp_path / "decision-log.md").write_text("v1", encoding="utf-8")
    _git(tmp_path, "add", "decision-log.md")
    _git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "pm adds log")
    (tmp_path / "decision-log.md").write_text("v2", encoding="utf-8")
    status = pg.commit_all(tmp_path, "approve", pm_user="tester")
    assert status["reason"] == "committed", status
    assert _git(tmp_path, "show", "HEAD:decision-log.md").stdout == "v2"


def test_commit_all_nothing_owned_changed_is_a_no_op(tmp_path):
    """Backlog #61. If only non-PM-OS files changed, nothing is committed and the
    result is a successful no-op (not a failed commit with an empty index)."""
    (tmp_path / "00-business-statement.md").write_text("one", encoding="utf-8")
    pg.init_project_repo(tmp_path, pm_user="tester")
    (tmp_path / "scratch.txt").write_text("x", encoding="utf-8")
    status = pg.commit_all(tmp_path, "approve", pm_user="tester")
    assert status["ok"] and status["reason"] == "nothing to commit", status
    assert _commit_count(tmp_path) == 1


def test_index_lock_failure_names_the_fix(tmp_path):
    """GH #72. When .git/index.lock is held, the warning explains the usual causes
    and the fix instead of repeating git's raw "fatal:" line alone."""
    (tmp_path / "00-business-statement.md").write_text("one", encoding="utf-8")
    pg.init_project_repo(tmp_path, pm_user="tester")
    (tmp_path / "00-business-statement.md").write_text("two", encoding="utf-8")
    (tmp_path / ".git" / "index.lock").write_text("", encoding="utf-8")
    status = pg.commit_all(tmp_path, "approve", pm_user="tester")
    assert status["ok"] is False
    assert "delete .git/index.lock" in status["reason"]
    assert "approval is saved" in status["reason"]
