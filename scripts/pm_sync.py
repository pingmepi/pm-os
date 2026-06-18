#!/usr/bin/env python3
"""pm_sync — manual catch-up sync of all PM-OS projects to the feedback repo.

The per-approval push (post-approve hook) only ever syncs the project being
approved, and older projects created before central sync existed never reach the
repo at all. This walks every project under ``projects_dir`` and pushes them in
one commit, reporting loudly on failure.

  pm_sync.py            push every project's telemetry/feedback centrally
  pm_sync.py --verify   validate every project's telemetry hash chain (no push)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".pm-os" / "lib"))

from config import load_config
from git_sync import push_all
from telemetry import verify_chain


def _projects_dir() -> Path:
    try:
        pd = load_config().get("projects_dir")
    except Exception:
        pd = None
    return Path(pd).expanduser() if pd else (Path.home() / "pm-projects")


def cmd_verify() -> int:
    projects_dir = _projects_dir()
    if not projects_dir.is_dir():
        print(f"No projects directory at {projects_dir}.")
        return 0

    roots = sorted(p for p in projects_dir.iterdir() if p.is_dir() and (p / ".meta.yaml").exists())
    if not roots:
        print(f"No projects found under {projects_dir}.")
        return 0

    broken = 0
    for root in roots:
        res = verify_chain(root)
        if res["ok"]:
            print(f"  ✓ {root.name}: chain intact ({res['events']} events)")
        else:
            broken += 1
            print(f"  ✗ {root.name}: BROKEN at line {res['break_at']} — {res['reason']}")

    print()
    if broken:
        print(f"FAIL: {broken} project(s) have a broken telemetry chain.")
        return 1
    print(f"PASS: all {len(roots)} project chains intact.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Catch-up sync of all PM-OS projects.")
    parser.add_argument("--verify", action="store_true",
                        help="Validate every project's telemetry hash chain instead of pushing.")
    args = parser.parse_args()

    if args.verify:
        sys.exit(cmd_verify())

    status = push_all()
    sys.exit(0 if status.get("ok") else 1)


if __name__ == "__main__":
    main()
