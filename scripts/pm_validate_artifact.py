#!/usr/bin/env python3
"""Validate PM-OS stage artifacts and generated prototype HTML."""
import argparse
import sys
import os
from pathlib import Path

sys.path.insert(0, os.environ.get("PM_OS_LIB_PATH") or str(Path.home() / ".pm-os" / "lib"))

from artifact_contracts import error_count, format_findings, validate_artifact, validate_prototype_html
from project import resolve_project


def main():
    parser = argparse.ArgumentParser(description="Validate a PM-OS artifact contract.")
    parser.add_argument("stage_id", choices=["03", "04", "05", "05-html", "06"])
    parser.add_argument("--mode", choices=["strict", "warn"], default="strict")
    parser.add_argument("--path", default=None)
    args = parser.parse_args()

    try:
        root = resolve_project()
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    if args.stage_id == "05-html":
        findings = validate_prototype_html(root, args.path)
    else:
        findings = validate_artifact(root, args.stage_id, args.path)

    if not findings:
        print(f"Artifact contract passed: {args.stage_id}")
        return

    print(f"Artifact contract findings for {args.stage_id}:")
    print(format_findings(findings))
    if args.mode == "strict" and error_count(findings):
        sys.exit(1)


if __name__ == "__main__":
    main()
