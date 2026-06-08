#!/usr/bin/env python3
"""PM-OS updater. Pulls latest from remote and reports version."""
import subprocess
import sys
from pathlib import Path


PM_OS_DIR = Path.home() / ".pm-os"


def main():
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

    result = subprocess.run(
        ["git", "pull", "--ff-only"],
        cwd=str(PM_OS_DIR),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Error pulling updates:\n{result.stderr}")
        sys.exit(1)

    print(f"✓ {result.stdout.strip()}")

    version_path = PM_OS_DIR / "VERSION"
    if version_path.exists():
        print(f"✓ PM-OS version: {version_path.read_text().strip()}")

    print()
    print("Update complete. Run /pm-os-verify to confirm installation health.")


if __name__ == "__main__":
    main()
