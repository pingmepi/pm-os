import os
import shutil
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import yaml

from config import load_config


CACHE_DIR = Path.home() / ".pm-os-feedback-cache"
SYNCED_FILES = ["telemetry.jsonl", "feedback.jsonl"]


def _lock_dir() -> Path:
    # Sibling of the cache (never inside it — the cache is cloned/managed by git).
    return CACHE_DIR.parent / ".pm-os-feedback-cache.lock"


@contextmanager
def _cache_lock(timeout: float = 600.0, stale_after: float = 900.0, poll: float = 0.1):
    """Serialize access to the single shared feedback-repo cache.

    Two syncs must never interleave clone/add/commit/push on one working copy —
    e.g. two backgrounded post-approve pushes fired seconds apart (backlog #6/#34)
    would otherwise collide on clone/index-lock/non-fast-forward. Uses an atomic
    ``mkdir`` lock (portable — holds under Git Bash on Windows, where ``fcntl`` is
    unavailable), waits up to ``timeout`` for a holder to finish, and steals a
    lock older than ``stale_after`` (left by a crashed process). Yields True if
    acquired, False if it timed out — the caller reports and defers to /pm-sync.
    """
    lock = _lock_dir()
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    acquired = False
    while True:
        try:
            os.mkdir(lock)
            acquired = True
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > stale_after:
                    shutil.rmtree(lock, ignore_errors=True)
                    continue
            except FileNotFoundError:
                continue  # holder released between the mkdir and the stat — retry
            if time.monotonic() >= deadline:
                break
            time.sleep(poll)
    try:
        yield acquired
    finally:
        if acquired:
            shutil.rmtree(lock, ignore_errors=True)


def push_feedback_repo(project_root) -> dict:
    """Sync a single project's telemetry/feedback to the central feedback repo.

    Returns a status dict (see ``_sync``). Failures are reported loudly rather
    than swallowed, so a stranded project is visible instead of silent.
    """
    project_root = Path(project_root)
    try:
        label = _project_slug(project_root)
    except Exception:
        label = project_root.name
    return _sync([project_root], label=label)


def push_all(projects_dir=None) -> dict:
    """Sync every project under ``projects_dir`` (each dir containing .meta.yaml).

    This is the catch-up path: it backfills projects that never reached the
    central repo (created pre-0.4, or whose only sync attempt failed silently).
    Projects whose local dir was deleted are skipped gracefully.
    """
    if projects_dir is None:
        try:
            projects_dir = load_config().get("projects_dir")
        except Exception:
            projects_dir = None
    projects_dir = Path(projects_dir).expanduser() if projects_dir else (Path.home() / "pm-projects")

    roots = []
    if projects_dir.is_dir():
        for child in sorted(projects_dir.iterdir()):
            if child.is_dir() and (child / ".meta.yaml").exists():
                roots.append(child)

    if not roots:
        print(f"[git_sync] No projects found under {projects_dir}.")
        return {"ok": True, "reason": "no projects", "synced": []}

    return _sync(roots, label=f"{len(roots)} project(s)")


# --- internals ----------------------------------------------------------------

def _sync(roots, label: str) -> dict:
    """Ensure the cache repo, copy each project's JSONL, then single commit+push.

    Returns {"ok": bool, "reason": str, "synced": [slug, ...]}.
    """
    try:
        cfg = load_config()
        feedback_repo_url = cfg.get("feedback_repo", "")
        pm = cfg.get("pm_user", "unknown")
    except Exception as e:
        return _fail("config", e, "Run: python3 ~/.pm-os/scripts/pm_os_install.py --reconfigure")

    if not feedback_repo_url:
        print("[git_sync] SKIPPED — feedback_repo not configured.")
        return {"ok": False, "reason": "feedback_repo not configured", "synced": []}

    with _cache_lock() as acquired:
        if not acquired:
            print("[git_sync] SKIPPED — another sync holds the cache lock; /pm-sync will catch up.")
            return {"ok": False, "reason": "cache busy (another sync in progress)", "synced": []}

        try:
            _ensure_repo(feedback_repo_url)
        except subprocess.CalledProcessError as e:
            return _fail("clone/fetch", e)

        synced = []
        failed = []
        for root in roots:
            root = Path(root)
            if not (root / ".meta.yaml").exists():
                # Local project dir deleted/moved — skip, don't crash the whole sync.
                print(f"[git_sync] skipping {root} (no .meta.yaml — deleted?)")
                continue
            try:
                if _copy_project(root, pm):
                    synced.append(_project_slug(root))
            except Exception as e:
                # A project we *meant* to sync but couldn't stage (bad .meta.yaml,
                # unreadable JSONL). This is the recovery path, so don't bury it —
                # record it and fail the overall result while still pushing the rest.
                print(f"[git_sync] WARNING — could not stage {root.name}: {e}")
                failed.append(root.name)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        try:
            _git(["add", "-A"], cwd=CACHE_DIR)
            staged = _git(["diff", "--cached", "--quiet"], cwd=CACHE_DIR, check=False)
            if staged.returncode == 0:
                print("[git_sync] Nothing new to push.")
                return _result(failed, "nothing to push", synced)
            _git(["commit", "-m", f"telemetry: {pm} {label} {timestamp}"], cwd=CACHE_DIR)
            _git(["push"], cwd=CACHE_DIR)
        except subprocess.CalledProcessError as e:
            return _fail("commit/push", e)

    print(f"[git_sync] Pushed {len(synced)} project(s): {', '.join(synced) or '(none)'}")
    return _result(failed, "pushed", synced)


def _result(failed, reason: str, synced) -> dict:
    """Build a sync status dict, flipping ok to false if any project failed to stage."""
    if failed:
        print(f"[git_sync] FAILED to stage {len(failed)} project(s): {', '.join(failed)}. "
              f"Fix the listed project(s) and retry: /pm-sync")
        return {"ok": False, "reason": f"failed to stage: {', '.join(failed)}",
                "synced": synced, "failed": failed}
    return {"ok": True, "reason": reason, "synced": synced, "failed": []}


def _copy_project(project_root: Path, pm: str) -> bool:
    """Copy a project's telemetry/feedback JSONL into the cache. True if anything copied."""
    slug = _project_slug(project_root)
    dest_dir = CACHE_DIR / "telemetry" / pm / slug
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied = False
    for filename in SYNCED_FILES:
        src = project_root / filename
        if src.exists():
            shutil.copy2(src, dest_dir / filename)
            copied = True
    return copied


def _project_slug(project_root: Path) -> str:
    with open(Path(project_root) / ".meta.yaml", "r") as f:
        return yaml.safe_load(f)["project_slug"]


def _fail(stage: str, err, hint: str = "") -> dict:
    detail = ""
    if isinstance(err, subprocess.CalledProcessError):
        out = (err.stderr or err.stdout or "").strip().splitlines()
        detail = out[-1] if out else str(err)
    else:
        detail = str(err).splitlines()[0] if str(err) else repr(err)
    print(f"[git_sync] FAILED — {stage}: {detail}")
    print("[git_sync]   Check auth (gh/git credentials) and network, then retry: /pm-sync"
          + (f"\n[git_sync]   {hint}" if hint else ""))
    return {"ok": False, "reason": f"{stage}: {detail}", "synced": []}


def _ensure_repo(url: str) -> None:
    if (CACHE_DIR / ".git").exists():
        _git(["fetch", "--quiet"], cwd=CACHE_DIR)
    else:
        parent = CACHE_DIR.parent
        parent.mkdir(parents=True, exist_ok=True)
        _git(["clone", url, str(CACHE_DIR)], cwd=parent)


def _git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        check=check,
        capture_output=True,
        text=True,
    )
