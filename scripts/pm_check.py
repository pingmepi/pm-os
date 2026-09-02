#!/usr/bin/env python3
"""PM-OS project consistency checker (read-only). See lib/consistency.py."""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ.get("PM_OS_LIB_PATH") or str(Path.home() / ".pm-os" / "lib"))

from project import resolve_project
from consistency import check_project, error_count, format_report, summary_line
from design_input import (
    design_error_count,
    format_design_findings,
    validate_design_input,
    validate_handoff_design,
)


def main():
    parser = argparse.ArgumentParser(
        description="Check a PM-OS project for internal consistency (read-only)."
    )
    parser.add_argument(
        "--design",
        action="store_true",
        help="Also validate design-in/ia.yaml and design-in/design-notes.md against the approved PRD/design brief.",
    )
    args = parser.parse_args()

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
    design_findings = []
    if args.design:
        design_findings = validate_design_input(project_root)
        design_findings.extend(validate_handoff_design(project_root))
        print()
        print("Design Input Check")
        print("=" * 40)
        print()
        print(format_design_findings(design_findings))
    print()
    print(summary_line(issues))
    if args.design:
        design_errors = design_error_count(design_findings)
        design_warnings = sum(1 for finding in design_findings if finding.severity == "warning")
        print(f"Design input: {design_errors} error(s), {design_warnings} warning(s)")

    sys.exit(1 if error_count(issues) or design_error_count(design_findings) else 0)


if __name__ == "__main__":
    main()
