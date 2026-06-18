#!/usr/bin/env python3
"""PM-OS updater. Tracks origin/main and reports version."""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


PM_OS_DIR = Path(os.environ.get("PM_OS_DIR", str(Path.home() / ".pm-os")))
CLAUDE_DIR = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude")))
CODEX_SKILLS_DIR = Path(os.environ.get("CODEX_SKILLS_DIR", str(Path.home() / ".agents" / "skills")))
TARGET_BRANCH = "main"
VALID_RUNTIMES = {"claude", "codex", "all"}


def runtime_help() -> str:
    return "Runtime skill target to sync after update. Required."


def print_runtime_required() -> None:
    print("Error: missing required --runtime argument.")
    print("Choose the runtime to sync:")
    print("  python3 ~/.pm-os/scripts/pm_os_update.py --runtime claude")
    print("  python3 ~/.pm-os/scripts/pm_os_update.py --runtime codex")


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
    result = run_git(["status", "--porcelain", "--untracked-files=no"], check=False)
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


def sync_skills(skills_dest: Path) -> None:
    skills_src = PM_OS_DIR / "skills"
    if skills_src.is_dir():
        skills_dest.mkdir(parents=True, exist_ok=True)
        for skill_dir in sorted(p for p in skills_src.iterdir() if p.is_dir()):
            target = skills_dest / skill_dir.name
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(skill_dir, target)


def sync_hooks(hooks_dest: Path) -> None:
    hooks_src = PM_OS_DIR / "hooks"
    if hooks_src.is_dir():
        hooks_dest.mkdir(parents=True, exist_ok=True)
        for hook in sorted(hooks_src.glob("*.py")):
            shutil.copy2(hook, hooks_dest / hook.name)


def sync_to_claude() -> None:
    """Copy skills and hooks from the PM-OS checkout into Claude Code's directories."""
    sync_skills(CLAUDE_DIR / "skills")
    sync_hooks(CLAUDE_DIR / "hooks")
    print(f"✓ Synced skills and hooks to {CLAUDE_DIR}")


def sync_to_codex() -> None:
    """Copy skills from the PM-OS checkout into Codex's user-level skill directory."""
    sync_skills(CODEX_SKILLS_DIR)
    print(f"✓ Synced skills to {CODEX_SKILLS_DIR}")


def sync_runtime(runtime: str) -> None:
    if runtime == "claude":
        sync_to_claude()
    elif runtime == "codex":
        sync_to_codex()
    elif runtime == "all":
        sync_to_claude()
        sync_to_codex()
    else:
        raise RuntimeError(f"Unsupported runtime '{runtime}'. Expected claude, codex, or all.")


def print_restart_guidance(runtime: str) -> None:
    if runtime == "claude":
        print("Restart your Claude Code session for updated skills and hooks to load.")
    elif runtime == "codex":
        print("Restart Codex or refresh /skills for updated skills to load.")
    else:
        print("Restart Claude Code and Codex, or refresh /skills, for updated skills to load.")
    print("Then run the PM-OS verifier for your runtime, if installed, to confirm installation health.")


def seed_context_overlay() -> None:
    """Seed any missing context-overlay files from context.example/ (never overwrites).

    Runs after the fast-forward so newly-added seed files (e.g. new stage packs) reach
    existing installs. The live ~/.pm-os/context/ is gitignored user data, so this is
    the only thing that touches it. Non-critical — a failure here never blocks an update.
    """
    try:
        sys.path.insert(0, str(PM_OS_DIR / "lib"))
        from context import seed_context
        n = seed_context()
        if n:
            print(f"✓ Seeded {n} new context-overlay file(s) into {PM_OS_DIR / 'context'}")
    except Exception as e:
        print(f"Warning: could not seed context overlay: {e}")


def finish_update(runtime: str) -> None:
    sync_runtime(runtime)
    seed_context_overlay()
    print_version()
    print()
    print_restart_guidance(runtime)


def main():
    parser = argparse.ArgumentParser(description="Update PM-OS from origin/main.")
    parser.add_argument(
        "--reset-main",
        action="store_true",
        help="Hard reset the local PM-OS checkout to origin/main if it has diverged.",
    )
    parser.add_argument(
        "--runtime",
        choices=sorted(VALID_RUNTIMES),
        help=runtime_help(),
    )
    args = parser.parse_args()
    if args.runtime is None:
        print_runtime_required()
        sys.exit(2)
    if args.runtime not in VALID_RUNTIMES:
        print(f"Error: runtime must be one of {', '.join(sorted(VALID_RUNTIMES))}.")
        sys.exit(1)

    print("PM-OS Update")
    print("============")
    print(f"Runtime: {args.runtime}")

    if not PM_OS_DIR.exists():
        print("Error: PM-OS not installed. Install PM-OS first.")
        print("  Claude: /pm-os-install")
        print("  Codex:  $pm-os-install")
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
            finish_update(args.runtime)
            return

        if ahead == 0 and behind > 0:
            result = run_git(["merge", "--ff-only", f"origin/{TARGET_BRANCH}"])
            output = result.stdout.strip() or f"Fast-forwarded to origin/{TARGET_BRANCH}"
            print(f"✓ {output}")
            finish_update(args.runtime)
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
        finish_update(args.runtime)
    except RuntimeError as exc:
        print(f"Error updating PM-OS:\n{exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
