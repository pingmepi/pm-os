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
    artifact_path, upstream_stage_ids, downstream_stage_ids, STAGE_NAMES,
)
from hashing import hash_artifact_body
from frontmatter import update_status, read as fm_read
from telemetry import log, last_event
from text_metrics import char_edit_distance, normalized_edit_distance


def stage_command(stage_id: str) -> str:
    return f"pm-stage-{stage_id}-{STAGE_NAMES[stage_id]}"


def _latest_generated_snapshot(project_root: Path, apath: Path):
    """Most recent .history/<stem>.<ts>.generated.md snapshot for this artifact, or None.

    History filenames embed an ISO8601 timestamp that sorts chronologically, so
    the lexicographically last match is the newest generation.
    """
    hist = project_root / ".history"
    if not hist.is_dir():
        return None
    matches = sorted(hist.glob(f"{apath.stem}.*.generated.md"))
    return matches[-1] if matches else None


def main():
    parser = argparse.ArgumentParser(description="Approve a PM-OS stage artifact.")
    parser.add_argument("stage_id", help="Two-digit stage number (e.g. '01')")
    parser.add_argument("--semantic-distance", dest="semantic_distance", type=float, default=None,
                        help="Optional agent-estimated semantic drift 0..1 (subjective judgment; "
                             "defaults to null when not supplied).")
    args = parser.parse_args()

    if args.semantic_distance is not None and not (0.0 <= args.semantic_distance <= 1.0):
        print("Error: --semantic-distance must be between 0 and 1.")
        sys.exit(1)

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
    upstream = {uid: get_stage(meta, uid)["content_hash"] for uid in upstream_stage_ids(stage_id, meta)}
    stage_meta["status"] = "approved"
    stage_meta["approved_at"] = ts
    stage_meta["content_hash"] = content_hash
    stage_meta["upstream_hashes_at_approval"] = upstream
    save_meta(meta, project_root)

    generated_hash = fm.get("generated_hash")
    regen_count = stage_meta.get("regeneration_count", 0)

    # --- Compute real timing + edit metrics ---
    # These are only meaningful when the stage was actually generated (has a
    # stage_generated event and a retained .history snapshot). Stage-00 group and
    # imported/backfilled artifacts have neither, so the fields stay None — correct.
    char_dist = norm_dist = time_to_approve = None

    snap = _latest_generated_snapshot(project_root, apath)
    if snap is not None:
        try:
            _, gen_body = fm_read(str(snap))
            char_dist = char_edit_distance(gen_body, body)
            norm_dist = round(normalized_edit_distance(gen_body, body), 6)
        except Exception:
            pass

    gen_ev = last_event(project_root, "stage_generated", stage_id)
    if gen_ev and gen_ev.get("timestamp"):
        try:
            t_gen = datetime.fromisoformat(gen_ev["timestamp"])
            t_app = datetime.fromisoformat(ts)
            time_to_approve = (t_app - t_gen).total_seconds()
        except Exception:
            pass

    try:
        log("stage_approved", project_root, stage_id, {
            "approved_hash": content_hash,
            "generated_hash": generated_hash,
            "char_edit_distance": char_dist,
            "normalized_edit_distance": norm_dist,
            "semantic_distance": args.semantic_distance,
            "time_to_approve_seconds": time_to_approve,
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
    downstream_stale = []
    for did in downstream_stage_ids(stage_id, meta_reloaded):
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
