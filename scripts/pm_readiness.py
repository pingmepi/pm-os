#!/usr/bin/env python3
"""Scaffold and check the readiness record, `readiness.yaml` (backlog #74).

    python3 pm_readiness.py init            # write the commented template if absent
    python3 pm_readiness.py check [--json]  # validate it and list overdue items

The file is ungated: nothing here hashes, approves or stales anything. The
agent edits the file on the PM's behalf; this script only scaffolds and
validates it (lib/readiness.py). `check` exits 1 on errors.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ.get("PM_OS_LIB_PATH") or str(Path.home() / ".pm-os" / "lib"))

from console import ensure_utf8_stdio  # noqa: E402
ensure_utf8_stdio()

import readiness  # noqa: E402
from project import resolve_project  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Scaffold or check readiness.yaml (ungated).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="Write the commented template if readiness.yaml is absent.")
    chk = sub.add_parser("check", help="Validate readiness.yaml and list overdue items.")
    chk.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        root = resolve_project()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if args.cmd == "init":
        path, created = readiness.scaffold(root)
        print(f"{'Created' if created else 'Kept existing'} {path.name}.")
        return

    issues, late, present = readiness.check_project(root)
    if args.json:
        print(json.dumps({
            "present": present,
            "issues": [issue.__dict__ for issue in issues],
            "overdue": late,
        }, indent=2))
    elif not present:
        print(f"No {readiness.READINESS_FILE} yet. Create it with `pm_readiness.py init`.")
    else:
        print(readiness.format_issues(issues) or "Readiness record: valid.")
        if late:
            print("\nOverdue (blocks a handoff release):")
            print(readiness.format_overdue(late))
    sys.exit(1 if any(issue.severity == "error" for issue in issues) else 0)


if __name__ == "__main__":
    main()
