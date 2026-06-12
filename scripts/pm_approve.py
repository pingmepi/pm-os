#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".pm-os" / "lib"))

from config import load_config
from project import (
    resolve_project, load_meta, save_meta, get_stage,
    artifact_path, upstream_stage_ids, STAGE_NAMES, STAGE_ORDER,
)
from hashing import hash_artifact_body
from frontmatter import update_status, read as fm_read
from telemetry import log


def stage_command(stage_id: str) -> str:
    return f"pm-stage-{stage_id}-{STAGE_NAMES[stage_id]}"


def main():
    parser = argparse.ArgumentParser(description="Approve a PM-OS stage artifact.")
    parser.add_argument("stage_id", help="Two-digit stage number (e.g. '01')")
    args = parser.parse_args()

    stage_id = args.stage_id.zfill(2)
    if stage_id not in STAGE_NAMES:
        print(f"Error: unknown stage '{stage_id}'. Valid: {', '.join(STAGE_NAMES.keys())}")
        sys.exit(1)

    try:
        project_root = resolve_project()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    apath = artifact_path(project_root, stage_id)
    if not apath.exists():
        cmd = stage_command(stage_id)
        print(f"Stage {stage_id} has not been generated yet. Generate it first:")
        print(f"  Claude: /{cmd}")
        print(f"  Codex:  ${cmd}")
        sys.exit(1)

    fm, body = fm_read(str(apath))
    current_status = fm.get("status", "pending")

    if current_status == "approved":
        print(f"Stage {stage_id} is already approved. No action taken.")
        sys.exit(0)

    if current_status == "pending":
        cmd = stage_command(stage_id)
        print(f"Stage {stage_id} has not been generated yet. Generate it first:")
        print(f"  Claude: /{cmd}")
        print(f"  Codex:  ${cmd}")
        sys.exit(1)

    content_hash = hash_artifact_body(str(apath))
    ts = datetime.now(timezone.utc).isoformat()
    try:
        pm = load_config()["pm_user"]
    except Exception:
        pm = "unknown"

    update_status(str(apath), "approved",
                  approved_at=ts,
                  approved_by=pm,
                  content_hash=content_hash)

    meta = load_meta(project_root)
    stage_meta = get_stage(meta, stage_id)
    upstream = {uid: get_stage(meta, uid)["content_hash"] for uid in upstream_stage_ids(stage_id)}
    stage_meta["status"] = "approved"
    stage_meta["approved_at"] = ts
    stage_meta["content_hash"] = content_hash
    stage_meta["upstream_hashes_at_approval"] = upstream
    save_meta(meta, project_root)

    generated_hash = fm.get("generated_hash")
    regen_count = stage_meta.get("regeneration_count", 0)
    try:
        log("stage_approved", project_root, stage_id, {
            "approved_hash": content_hash,
            "generated_hash": generated_hash,
            "char_edit_distance": None,
            "normalized_edit_distance": None,
            "semantic_distance": None,
            "time_to_approve_seconds": None,
            "regeneration_count": regen_count,
            "implicit_reapproval": False,
        })
    except Exception as e:
        print(f"Warning: telemetry logging failed: {e}")

    hook_path = Path.home() / ".pm-os" / "hooks" / "post-approve.py"
    if hook_path.exists():
        env = os.environ.copy()
        env["PM_OS_STAGE"] = stage_id
        result = subprocess.run(
            ["python3", str(hook_path)],
            env=env,
            cwd=str(project_root),
        )
        if result.returncode != 0:
            print(f"Warning: post-approve hook exited with code {result.returncode}")

    meta_reloaded = load_meta(project_root)
    stage_idx = STAGE_ORDER.index(stage_id)
    downstream_stale = []
    for did in STAGE_ORDER[stage_idx + 1:]:
        try:
            if get_stage(meta_reloaded, did)["status"] == "stale":
                downstream_stale.append(did)
        except KeyError:
            continue

    print(f"Stage {stage_id} approved.")
    print(f"Content hash: {content_hash}")
    if downstream_stale:
        print(f"Downstream stages now stale: {', '.join(downstream_stale)}")
    else:
        print("Downstream stages: none stale")
    print("Capture notes on this stage:")
    print(f"  Claude: /pm-feedback {stage_id}")
    print(f"  Codex:  $pm-feedback {stage_id}")


if __name__ == "__main__":
    main()
