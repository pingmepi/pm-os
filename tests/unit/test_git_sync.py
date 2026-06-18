"""Unit tests for git_sync skip/failure paths — stubbed, never touches network/git."""
import subprocess

import pytest

import git_sync

pytestmark = pytest.mark.unit


def _project(dir_, slug, with_slug=True):
    d = dir_ / slug
    d.mkdir(parents=True)
    meta = f"project_slug: {slug}\n" if with_slug else "not_slug: x\n"
    (d / ".meta.yaml").write_text(meta + "stages: []\n", encoding="utf-8")
    (d / "telemetry.jsonl").write_text("{}\n", encoding="utf-8")
    return d


def _stub_git(monkeypatch):
    """No real git: clone/fetch is a no-op; diff reports staged changes; rest succeed."""
    monkeypatch.setattr(git_sync, "_ensure_repo", lambda url: None)

    class _R:
        def __init__(self, rc=0):
            self.returncode, self.stdout, self.stderr = rc, "", ""

    def fake_git(args, cwd, check=True):
        return _R(1) if args[:1] == ["diff"] else _R(0)

    monkeypatch.setattr(git_sync, "_git", fake_git)


def test_push_all_empty_dir_is_clean_noop(pmos, tmp_path):
    res = git_sync.push_all(str(tmp_path / "does-not-exist"))
    assert res["ok"] is True
    assert res["reason"] == "no projects"


def test_unconfigured_feedback_repo_skips(pmos, tmp_path, monkeypatch):
    _project(tmp_path, "good")
    monkeypatch.setattr(git_sync, "load_config", lambda: {"feedback_repo": "", "pm_user": "t"})
    res = git_sync.push_all(str(tmp_path))
    assert res["ok"] is False
    assert "not configured" in res["reason"]


def test_partial_staging_failure_flips_ok_false(pmos, tmp_path, monkeypatch):
    _project(tmp_path, "good")
    _project(tmp_path, "bad", with_slug=False)  # _project_slug() will raise on this one
    monkeypatch.setattr(git_sync, "load_config",
                        lambda: {"feedback_repo": str(pmos.feedback), "pm_user": "tester"})
    _stub_git(monkeypatch)
    res = git_sync.push_all(str(tmp_path))
    assert res["ok"] is False
    assert "bad" in res["failed"]
    assert "good" in res["synced"]


def test_deleted_project_dir_is_skipped_not_failed(pmos, tmp_path, monkeypatch):
    good = _project(tmp_path, "good")
    monkeypatch.setattr(git_sync, "load_config",
                        lambda: {"feedback_repo": str(pmos.feedback), "pm_user": "tester"})
    _stub_git(monkeypatch)
    # A root with no .meta.yaml (e.g. deleted) must be skipped, not counted as failure.
    res = git_sync._sync([good, tmp_path / "ghost"], label="mix")
    assert res["ok"] is True
    assert res["failed"] == []
    assert "good" in res["synced"]
