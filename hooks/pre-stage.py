#!/usr/bin/env python3
"""
pre-stage hook — gates stage execution.

Checks:
  1. All upstream stages are approved or edited (not pending/draft/stale).
  2. Recomputes upstream artifact hashes; marks drift as 'edited'.
  3. If any upstream is 'edited', prints implicit-reapproval prompt.
  4. On implicit re-approval, cascades staleness to downstream approved stages
     (including intermediate ones) so they get re-approved against new content.
  5. After the cascade, re-checks whether any of the newly staled stages are
     themselves upstream of the target stage — if so, blocks rather than
     proceeding with unapproved intermediate artifacts.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from pathlib import Path
from project import resolve_project, load_meta, save_meta, get_stage, upstream_stage_ids, downstream_stage_ids, artifact_path, STAGE_NAMES
from hashing import hash_artifact_body
from frontmatter import update_status
from telemetry import log


def read_edited_choice(stage_id: str) -> str:
    env_choice = os.environ.get("PM_OS_EDITED_UPSTREAM_CHOICE", "").strip().lower()
    choices = {
        "1": "1",
        "continue": "1",
        "implicit-reapproval": "1",
        "implicit_reapproval": "1",
        "2": "2",
        "reapprove": "2",
        "explicit-reapproval": "2",
        "explicit_reapproval": "2",
        "3": "3",
        "cancel": "3",
    }
    if env_choice:
        if env_choice not in choices:
            print(
                "[pre-stage] ERROR: PM_OS_EDITED_UPSTREAM_CHOICE must be "
                "continue, reapprove, or cancel.",
                file=sys.stderr,
            )
            sys.exit(1)
        return choices[env_choice]
    if not sys.stdin.isatty():
        # Non-interactive (agent session or CI). Implicitly re-approving an edited
        # upstream is the PM's decision, not the agent's — so we BLOCK here and do
        # NOT advertise the env-var escape, otherwise an agent reads the hint and
        # bypasses the human. PM_OS_EDITED_UPSTREAM_CHOICE (handled above) remains
        # the deliberate hatch for genuinely unattended CI/cron runs only.
        print(
            f"[pre-stage] BLOCKED: upstream stage(s) were edited after approval, so "
            f"stage {stage_id} cannot be generated yet.\n"
            "Re-approving an edited stage is the PM's decision. Agent: STOP — do not "
            "re-approve on the PM's behalf. Tell the PM which stage changed, then ask "
            "them to either:\n"
            "  - re-approve it explicitly:  /pm-approve <NN>   (Codex: $pm-approve <NN>)\n"
            "  - or confirm in their own words that you should continue.\n"
            "Re-run this stage only after the PM has acted.",
            file=sys.stderr,
        )
        sys.exit(1)
    return input("Choice [1/2/3]: ").strip()


def cascade_stale_for_edited(meta, project_root, edited_ids):
    """Mark downstream approved stages stale after an upstream is re-approved.

    An edited upstream that gets (implicitly) re-approved has new body content, so
    every approved stage built on top of it is now stale — including intermediate
    stages between the edited one and the stage being generated. Stages in
    ``edited_ids`` are skipped: they were just reconciled to current content.
    Mirrors the cascade in post-approve.py for the explicit-reapproval path.
    """
    if not edited_ids:
        return []
    downstream_ids = sorted({
        did
        for uid in edited_ids
        for did in downstream_stage_ids(uid, meta)
    })
    stale_logged = []
    for did in downstream_ids:
        if did in edited_ids:
            continue
        try:
            ds_meta = get_stage(meta, did)
        except KeyError:
            continue
        if ds_meta["status"] == "approved":
            ds_meta["status"] = "stale"
            apath = artifact_path(project_root, did)
            if apath.exists():
                update_status(str(apath), "stale")
            log("stage_marked_stale", project_root, did, {
                "reason": "upstream_edited_reapproved",
                "triggering_upstream_stages": sorted(edited_ids),
            })
            stale_logged.append(did)
    return stale_logged


def main():
    # Determine which stage is being run from the environment variable set by the skill
    stage_id = os.environ.get("PM_OS_STAGE")
    if not stage_id:
        # Cannot gate without knowing the stage — allow through
        sys.exit(0)

    try:
        project_root = resolve_project()
    except FileNotFoundError as e:
        print(f"[pre-stage] ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    meta = load_meta(project_root)
    upstream_ids = upstream_stage_ids(stage_id, meta)

    # --- Step 1: recompute hashes and detect drift ---
    edited_stages = []
    for uid in upstream_ids:
        stage_meta = get_stage(meta, uid)
        apath = artifact_path(project_root, uid)

        if stage_meta["status"] == "approved" and apath.exists():
            current_hash = hash_artifact_body(str(apath))
            if current_hash != stage_meta.get("content_hash"):
                # Drift detected — mark as edited
                stage_meta["status"] = "edited"
                update_status(str(apath), "edited")
                log("stage_edited_post_approval", project_root, uid, {
                    "old_hash": stage_meta.get("content_hash"),
                    "new_hash": current_hash,
                    "detected_via": "pre_stage_hook",
                })
                stage_meta["content_hash"] = current_hash
                save_meta(meta, project_root)

    # --- Step 2: gate check ---
    blocking = []
    edited = []
    for uid in upstream_ids:
        stage_meta = get_stage(meta, uid)
        status = stage_meta["status"]
        if status in ("pending", "draft", "stale"):
            blocking.append((uid, STAGE_NAMES[uid], status))
        elif status == "edited":
            edited.append((uid, STAGE_NAMES[uid]))

    if blocking:
        print("\n[pre-stage] ERROR: Cannot run stage — upstream stages are not approved:\n", file=sys.stderr)
        for uid, name, status in blocking:
            print(f"  Stage {uid} ({name}): {status}", file=sys.stderr)
        print("\nApprove or regenerate blocking stages before proceeding.", file=sys.stderr)
        sys.exit(1)

    # --- Step 3: implicit reapproval prompt for edited upstreams ---
    if edited:
        print("\n[pre-stage] WARNING: Upstream stage(s) were edited after approval:\n")
        for uid, name in edited:
            stage_meta = get_stage(meta, uid)
            apath = artifact_path(project_root, uid)
            current_hash = hash_artifact_body(str(apath)) if apath.exists() else "?"
            print(f"  Stage {uid} ({name})")
            print(f"    Approved hash: {stage_meta.get('content_hash', '?')}")
            print(f"    Current hash:  {current_hash}")

        print(f"""
Options:
  [1] Continue — generate stage {stage_id} using current upstream content
      (implicitly re-approves edited stages and marks downstream approved stages stale)
  [2] Re-approve edited stages explicitly first (recommended for significant edits)
  [3] Cancel
""")
        choice = read_edited_choice(stage_id)

        if choice == "1":
            for uid, name in edited:
                stage_meta = get_stage(meta, uid)
                apath = artifact_path(project_root, uid)
                current_hash = hash_artifact_body(str(apath)) if apath.exists() else stage_meta.get("content_hash")
                old_hash = stage_meta.get("content_hash")
                stage_meta["status"] = "approved"
                stage_meta["content_hash"] = current_hash
                update_status(str(apath), "approved", content_hash=current_hash)
                log("implicit_reapproval", project_root, uid, {
                    "stage": uid,
                    "old_hash": old_hash,
                    "new_hash": current_hash,
                })
            stale_logged = cascade_stale_for_edited(
                meta, project_root, {uid for uid, _ in edited})
            save_meta(meta, project_root)
            print("[pre-stage] Implicit re-approval logged.")
            if stale_logged:
                print("[pre-stage] Marked downstream stages stale: "
                      + ", ".join(stale_logged))

            # Re-check: if any of the staled stages are upstream of the
            # target, we must block. Example: editing stage 01 while
            # running stage 04 stales 02/03, which are also upstream of
            # 04 — proceeding would generate from unapproved intermediates.
            stale_upstream = [s for s in stale_logged if s in upstream_ids]
            if stale_upstream:
                print(
                    f"\n[pre-stage] BLOCKED: implicit re-approval staled "
                    f"intermediate stage(s) that are upstream of stage "
                    f"{stage_id}: {', '.join(sorted(stale_upstream))}.\n"
                    "Re-approve them first, then retry this stage.\n"
                    "  Claude: /pm-approve <NN>   Codex: $pm-approve <NN>",
                    file=sys.stderr,
                )
                sys.exit(1)
            print("[pre-stage] Proceeding.")
        elif choice == "2":
            print("[pre-stage] Halted. Re-approve each edited stage, then retry.")
            print("[pre-stage] Claude: /pm-approve <stage>")
            print("[pre-stage] Codex:  $pm-approve <stage>")
            sys.exit(1)
        else:
            print("[pre-stage] Cancelled.")
            sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
