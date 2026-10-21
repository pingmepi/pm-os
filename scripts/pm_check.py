#!/usr/bin/env python3
"""PM-OS project consistency checker (read-only). See lib/consistency.py.

`--release [PATH ...]` instead runs the release check (lib/release_check.py,
backlog #72) on a handoff folder or a `.zip` of one, PM-OS-built or hand-built,
inside or outside a project. With no PATH it checks every audience folder under
the current project's `handoff/`.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ.get("PM_OS_LIB_PATH") or str(Path.home() / ".pm-os" / "lib"))

from console import ensure_utf8_stdio  # noqa: E402
ensure_utf8_stdio()

from project import resolve_project
import release_check
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
    parser.add_argument(
        "--release", nargs="*", metavar="PATH",
        help="Run the release check on handoff folder(s) or .zip file(s) instead of the project "
             "check. With no PATH, checks each audience folder under this project's handoff/.",
    )
    parser.add_argument(
        "--ignore-ids", default="",
        help="With --release: comma-separated id prefixes or ids to skip in the undefined-id "
             "check (e.g. S,E for domain sample ids).",
    )
    parser.add_argument("--json", action="store_true", help="With --release: print the reports as JSON.")
    args = parser.parse_args()

    if args.release is not None:
        sys.exit(_release(args))

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


def _release(args) -> int:
    paths = [Path(p) for p in args.release]
    if not paths:
        try:
            root = resolve_project()
        except FileNotFoundError:
            print("Error: --release needs a path to a handoff folder or .zip when run outside a "
                  "PM-OS project.")
            return 2
        handoff = root / "handoff"
        paths = [p for p in sorted(handoff.iterdir()) if p.is_dir()] if handoff.is_dir() else []
        if not paths:
            print(f"Error: {handoff} has no audience folders yet. Build the package with "
                  "`/pm-handoff --package`, or pass a path.")
            return 2
    ignore = [part.strip() for part in args.ignore_ids.split(",") if part.strip()]
    reports = []
    for path in paths:
        if not path.exists():
            print(f"Error: {path} does not exist.")
            return 2
        try:
            reports.append(release_check.check_release(path, ignore_ids=ignore))
        except (FileNotFoundError, ValueError) as e:
            print(f"Error: {e}")
            return 2
    if args.json:
        print(json.dumps([r.as_dict() for r in reports], indent=2))
    else:
        for path, report in zip(paths, reports):
            print(release_check.format_report(report, label=str(path)))
            print()
        if ignore:
            print(f"Ignored id prefixes/ids: {', '.join(ignore)}")
    return 1 if any(r.errors for r in reports) else 0


if __name__ == "__main__":
    main()
