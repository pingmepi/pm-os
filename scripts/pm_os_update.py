#!/usr/bin/env python3
"""PM-OS updater. Tracks origin/main and reports version."""
import argparse
import os
import subprocess
import sys
from pathlib import Path


PM_OS_DIR = Path(os.environ.get("PM_OS_DIR", str(Path.home() / ".pm-os")))
TARGET_BRANCH = "main"


def run_git(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", *args],
        cwd=str(PM_OS_DIR),
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git command failed")
    return result


def working_tree_clean() -> bool:
    result = run_git(["status", "--porcelain"], check=False)
    return result.returncode == 0 and not result.stdout.strip()


def local_branch_exists(branch: str) -> bool:
    return run_git(["show-ref", "--verify", f"refs/heads/{branch}"], check=False).returncode == 0


def remote_branch_exists(branch: str) -> bool:
    return run_git(["show-ref", "--verify", f"refs/remotes/origin/{branch}"], check=False).returncode == 0


def current_branch() -> str:
    result = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    return result.stdout.strip()


def ensure_main_checkout() -> None:
    branch = current_branch()
    if branch == TARGET_BRANCH:
        return

    if not working_tree_clean():
        raise RuntimeError(
            f"Current branch is '{branch}', but PM-OS updates track '{TARGET_BRANCH}'.\n"
            "Working tree has local changes, so automatic branch switching was skipped."
        )

    if local_branch_exists(TARGET_BRANCH):
        run_git(["checkout", TARGET_BRANCH])
    else:
        run_git(["checkout", "-b", TARGET_BRANCH, "--track", f"origin/{TARGET_BRANCH}"])

    print(f"✓ Switched to {TARGET_BRANCH}")


def ensure_main_upstream() -> None:
    run_git(["branch", "--set-upstream-to", f"origin/{TARGET_BRANCH}", TARGET_BRANCH])


def ahead_behind(remote_ref: str) -> tuple[int, int]:
    result = run_git(["rev-list", "--left-right", "--count", f"HEAD...{remote_ref}"])
    ahead, behind = result.stdout.strip().split()
    return int(ahead), int(behind)


def print_version() -> None:
    version_path = PM_OS_DIR / "VERSION"
    if version_path.exists():
        print(f"✓ PM-OS version: {version_path.read_text().strip()}")


def main():
    parser = argparse.ArgumentParser(description="Update PM-OS from origin/main.")
    parser.add_argument(
        "--reset-main",
        action="store_true",
        help="Hard reset the local PM-OS checkout to origin/main if it has diverged.",
    )
    args = parser.parse_args()

    print("PM-OS Update")
    print("============")

    if not PM_OS_DIR.exists():
        print("Error: PM-OS not installed. Run /pm-os-install first.")
        sys.exit(1)

    git_dir = PM_OS_DIR / ".git"
    if not git_dir.exists():
        print("Warning: ~/.pm-os is not a git repository. Cannot auto-update.")
        print("To update, manually replace ~/.pm-os with the latest version.")
        sys.exit(1)

    try:
        run_git(["fetch", "--tags", "origin"])

        if not remote_branch_exists(TARGET_BRANCH):
            raise RuntimeError(f"Remote branch origin/{TARGET_BRANCH} was not found.")

        ensure_main_checkout()
        ensure_main_upstream()

        ahead, behind = ahead_behind(f"origin/{TARGET_BRANCH}")

        if ahead == 0 and behind == 0:
            print(f"✓ Already up to date with origin/{TARGET_BRANCH}")
            print_version()
            print()
            print("Update complete. Run /pm-os-verify to confirm installation health.")
            return

        if ahead == 0 and behind > 0:
            result = run_git(["merge", "--ff-only", f"origin/{TARGET_BRANCH}"])
            output = result.stdout.strip() or f"Fast-forwarded to origin/{TARGET_BRANCH}"
            print(f"✓ {output}")
            print_version()
            print()
            print("Update complete. Run /pm-os-verify to confirm installation health.")
            return

        if not args.reset_main:
            raise RuntimeError(
                f"Local {TARGET_BRANCH} has diverged from origin/{TARGET_BRANCH} "
                f"(ahead {ahead}, behind {behind}).\n"
                "Automatic update stopped to avoid overwriting local history.\n"
                "If this installation is disposable, rerun with --reset-main to realign to origin/main."
            )

        if not working_tree_clean():
            raise RuntimeError(
                "Cannot reset because the working tree has local changes.\n"
                "Commit or discard them first, then rerun with --reset-main."
            )

        run_git(["reset", "--hard", f"origin/{TARGET_BRANCH}"])
        print(f"✓ Reset local {TARGET_BRANCH} to origin/{TARGET_BRANCH}")
        print_version()
        print()
        print("Update complete. Run /pm-os-verify to confirm installation health.")
    except RuntimeError as exc:
        print(f"Error updating PM-OS:\n{exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
