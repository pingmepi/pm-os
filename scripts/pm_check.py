#!/usr/bin/env python3
"""PM-OS project consistency checker (read-only). See lib/consistency.py."""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ.get("PM_OS_LIB_PATH") or str(Path.home() / ".pm-os" / "lib"))

from project import resolve_project
from consistency import check_project, error_count, format_report, summary_line


def main():
    parser = argparse.ArgumentParser(
        description="Check a PM-OS project for internal consistency (read-only)."
    )
    parser.parse_args()

    try:
        project_root = resolve_project()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    issues = check_project(project_root)

    print(f"PM-OS Consistency Check — {project_root.name}")
    print("=" * 40)
    print()
    print(format_report(issues))
    print()
    print(summary_line(issues))

    sys.exit(1 if error_count(issues) else 0)


if __name__ == "__main__":
    main()
