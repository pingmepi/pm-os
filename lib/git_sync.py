import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


CACHE_DIR = Path.home() / ".pm-os-feedback-cache"


def push_feedback_repo(project_root: Path) -> None:
    """Copy local telemetry/feedback JSONL to the feedback repo, commit, and push."""
    feedback_repo_url = os.environ.get("PM_OS_FEEDBACK_REPO", "")
    pm = os.environ.get("PM_OS_USER", "unknown")

    import yaml
    with open(project_root / ".meta.yaml", "r") as f:
        meta = yaml.safe_load(f)
    project_slug = meta["project_slug"]

    if not feedback_repo_url:
        print("[git_sync] PM_OS_FEEDBACK_REPO not set — skipping push.")
        return

    _ensure_repo(feedback_repo_url)

    dest_dir = CACHE_DIR / "telemetry" / pm / project_slug
    dest_dir.mkdir(parents=True, exist_ok=True)

    for filename in ["telemetry.jsonl", "feedback.jsonl"]:
        src = project_root / filename
        if src.exists():
            shutil.copy2(src, dest_dir / filename)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    _git(["add", "-A"], cwd=CACHE_DIR)
    result = _git(
        ["diff", "--cached", "--quiet"],
        cwd=CACHE_DIR,
        check=False,
    )
    if result.returncode != 0:
        _git(
            ["commit", "-m", f"telemetry: {pm} {project_slug} {timestamp}"],
            cwd=CACHE_DIR,
        )
        _git(["push"], cwd=CACHE_DIR)
    else:
        print("[git_sync] Nothing to push.")


def _ensure_repo(url: str) -> None:
    if (CACHE_DIR / ".git").exists():
        _git(["fetch", "--quiet"], cwd=CACHE_DIR)
    else:
        CACHE_DIR.parent.mkdir(parents=True, exist_ok=True)
        _git(["clone", url, str(CACHE_DIR)])


def _git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        check=check,
        capture_output=True,
        text=True,
    )
