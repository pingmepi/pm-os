#!/usr/bin/env python3
import argparse
import sys
import os
from pathlib import Path

sys.path.insert(0, os.environ.get("PM_OS_LIB_PATH") or str(Path.home() / ".pm-os" / "lib"))

from project import resolve_project, load_meta, artifact_path, STAGE_NAMES, STAGE_ORDER
from frontmatter import read as fm_read


def main():
    parser = argparse.ArgumentParser(description="Share a PM-OS project or stage.")
    parser.add_argument("stage_id", nargs="?", help="Stage to share (e.g. '01'); omit for all approved")
    parser.add_argument("--output", type=str, help="Output file path (default: stdout)")
    args = parser.parse_args()

    try:
        root = resolve_project()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    meta = load_meta(root)

    if args.stage_id:
        stage_id = args.stage_id.zfill(2)
        if stage_id not in STAGE_NAMES:
            print(f"Error: unknown stage '{stage_id}'")
            sys.exit(1)
        stages_to_share = [stage_id]
    else:
        stages_to_share = [s["id"] for s in meta["stages"] if s["status"] in ("approved", "edited")]

    if not stages_to_share:
        print("No approved stages to share.")
        sys.exit(0)

    lines = [f"# {meta['project_name']}", f"Project: {meta['project_slug']} | PM-OS {meta['pm_os_version']}", ""]

    for sid in stages_to_share:
        apath = artifact_path(root, sid)
        if not apath.exists():
            continue
        fm, body = fm_read(str(apath))
        h = fm.get("content_hash")
        hash_short = h[:12] if h else "N/A"
        lines += [
            "---",
            f"## Stage {sid}: {STAGE_NAMES[sid].replace('-', ' ').title()}",
            f"Status: {fm.get('status', '?')} | Hash: {hash_short}",
            "",
            body.strip(),
            "",
        ]

    output = "\n".join(lines)

    if args.output:
        Path(args.output).write_text(output)
        print(f"Exported to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
