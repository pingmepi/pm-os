#!/usr/bin/env python3
"""
post-approve hook — runs after pm-approve completes.

1. Push telemetry + feedback JSONL to feedback repo.
2. Cascade staleness: downstream approved stages → stale.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from project import resolve_project, load_meta, save_meta, get_stage, artifact_path, STAGE_ORDER, STAGE_NAMES
from frontmatter import update_status
from telemetry import log
from git_sync import push_feedback_repo


def main():
    stage_id = os.environ.get("PM_OS_STAGE")
    if not stage_id:
        sys.exit(0)

    try:
        project_root = resolve_project()
    except FileNotFoundError as e:
        print(f"[post-approve] ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    meta = load_meta(project_root)

    # --- Cascade staleness to downstream approved stages ---
    stage_idx = STAGE_ORDER.index(stage_id)
    downstream_ids = STAGE_ORDER[stage_idx + 1:]

    stale_logged = []
    for did in downstream_ids:
        ds_meta = get_stage(meta, did)
        if ds_meta["status"] == "approved":
            ds_meta["status"] = "stale"
            apath = artifact_path(project_root, did)
            if apath.exists():
                update_status(str(apath), "stale")
            log("stage_marked_stale", project_root, did, {
                "reason": "upstream_approved",
                "triggering_upstream_stage": stage_id,
            })
            stale_logged.append(did)

    if stale_logged:
        save_meta(meta, project_root)
        print(f"[post-approve] Marked downstream stages stale: {', '.join(stale_logged)}")

    # --- Push to feedback repo ---
    try:
        push_feedback_repo(project_root)
    except Exception as e:
        print(f"[post-approve] WARNING: Could not push to feedback repo: {e}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
