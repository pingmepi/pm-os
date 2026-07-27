#!/usr/bin/env python3
"""Per-project local git version history (backlog #18, local half).

Every PM-OS project is its own local git repo: initialized at scaffold time
(`scripts/pm_new.py`) and committed on each approval (`hooks/post-approve.py`).
No remote, no network — `git init`, commit, diff and restore all work offline,
so a PM has a full history of every approved product decision and can recover a
prior version without any infrastructure.

This is the project's OWN repo (its artifacts + `.history/`), entirely separate
from the central feedback-repo sync in `lib/git_sync.py` (which pushes only
`telemetry.jsonl`/`feedback.jsonl` to a shared repo).

Everything here is **warn-not-fail**: a git problem must never break scaffolding
or approval — generating and approving artifacts is the job. Each function
returns a status dict ``{"ok": bool, "reason": str}`` and never raises for an
ordinary git failure.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

# Project-level ignores. `.codebase/` is the (potentially huge) enhancement-mode
# clone, which carries its own git and is reconstructable from its remote; the
# rest is transient cruft. `.history/` is deliberately NOT ignored — the lineage
# is exactly what we want versioned.
DEFAULT_GITIGNORE = (
    "# PM-OS project-level ignores\n"
    ".codebase/\n"
    ".pm-os-sync.log\n"
    "__pycache__/\n"
    ".DS_Store\n"
)


def git_available() -> bool:
    """True if a usable `git` binary is on PATH."""
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


def _identity_args(pm_user: str | None) -> list[str]:
    """`-c user.name/-c user.email` so commits succeed with no global git config.

    Note: real `GIT_AUTHOR_*`/`GIT_COMMITTER_*` env vars still take precedence
    over these (that is how the test harness pins its identity); this only
    guarantees a valid identity exists when nothing else provides one.
    """
    name = (pm_user or "").strip() or "pm-os"
    return ["-c", f"user.name={name}", "-c", f"user.email={name}@pm-os.local"]


def _run_git(project_root: Path, args: list[str], pm_user: str | None = None):
    cmd = ["git", "-C", str(project_root)]
    if pm_user is not None:
        cmd += _identity_args(pm_user)
    cmd += args
    return subprocess.run(cmd, capture_output=True, text=True)


def ensure_gitignore(project_root: Path) -> None:
    """Write the default `.gitignore` if absent; otherwise make sure `.codebase/`
    is listed. Compatible with `pm_context_import.py`, which appends `.codebase/`
    the same way when it clones an enhancement codebase."""
    gi = Path(project_root) / ".gitignore"
    if not gi.exists():
        gi.write_text(DEFAULT_GITIGNORE, encoding="utf-8")
        return
    content = gi.read_text(encoding="utf-8")
    if ".codebase/" not in content:
        gi.write_text(content.rstrip() + "\n.codebase/\n", encoding="utf-8")


def commit_all(project_root, message: str, pm_user: str | None = None) -> dict:
    """Stage everything (honoring `.gitignore`) and commit. No-op if the tree is
    clean. Warn-not-fail: returns a status dict, never raises for a git error."""
    project_root = Path(project_root)
    if not git_available():
        return {"ok": False, "reason": "git not available; skipping commit"}
    if not (project_root / ".git").exists():
        return {"ok": False, "reason": "not a git repo; skipping commit"}

    add = _run_git(project_root, ["add", "-A"])
    if add.returncode != 0:
        return {"ok": False, "reason": f"git add failed: {add.stderr.strip()}"}

    status = _run_git(project_root, ["status", "--porcelain"])
    if status.returncode == 0 and not status.stdout.strip():
        return {"ok": True, "reason": "nothing to commit"}

    commit = _run_git(project_root, ["commit", "-m", message], pm_user=pm_user)
    if commit.returncode != 0:
        detail = commit.stderr.strip() or commit.stdout.strip()
        return {"ok": False, "reason": f"git commit failed: {detail}"}
    return {"ok": True, "reason": "committed"}


def init_project_repo(project_root, pm_user: str | None = None,
                      initial_message: str = "Initialize PM-OS project") -> dict:
    """Initialize the project as a local git repo and make the initial commit.
    Writes `.gitignore` first. Idempotent: if the repo already exists it just
    commits any pending changes. Warn-not-fail."""
    project_root = Path(project_root)
    if not git_available():
        return {"ok": False, "reason": "git not available; skipping version history"}

    ensure_gitignore(project_root)

    if not (project_root / ".git").exists():
        init = _run_git(project_root, ["init"])
        if init.returncode != 0:
            return {"ok": False, "reason": f"git init failed: {init.stderr.strip()}"}

    return commit_all(project_root, initial_message, pm_user=pm_user)
