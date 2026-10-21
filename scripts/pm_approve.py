#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.environ.get("PM_OS_LIB_PATH") or str(Path.home() / ".pm-os" / "lib"))

from console import ensure_utf8_stdio  # noqa: E402
ensure_utf8_stdio()

from config import load_config
from project import (
    resolve_project, load_meta, save_meta, get_stage,
    artifact_path, upstream_stage_ids, downstream_stage_ids, STAGE_NAMES,
)
from hashing import hash_artifact_body, stage_content_hash, CompositeHashError
import stage_version  # noqa: E402
from frontmatter import update_status, read as fm_read
from telemetry import log, last_event
from text_metrics import bounded_edit_distance, normalized_edit_distance
from cascade import cascade_stale
from artifact_contracts import format_findings, validate_artifact


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


def _has_generation_evidence(project_root: Path, stage_id: str, apath: Path) -> bool:
    """True when the stage was really produced despite a 'pending' frontmatter.

    Ground truth is a non-empty artifact body plus a telemetry event that marks
    the stage as having been produced through any path (generated, imported, or
    backfilled). Used to reconcile a drifted `status` field so a real artifact is
    not misreported as ungenerated (GH #61).
    """
    try:
        _fm, body = fm_read(str(apath))
    except Exception:
        return False
    if not body.strip():
        return False
    for event_type in ("stage_generated", "stage_imported",
                       "stage_backfilled", "stage_backfilled_draft"):
        if last_event(project_root, event_type, stage_id) is not None:
            return True
    return False


def _post_approve_timeout() -> float:
    """Seconds the post-approve hook may run before approval stops waiting for it."""
    try:
        return max(1.0, float(os.environ.get("PM_OS_POST_APPROVE_TIMEOUT", "300")))
    except ValueError:
        return 300.0


def _rebind_upstreams(project_root: Path, stage_id: str) -> None:
    """`--reapprove` on an approved stage whose body is unchanged (backlog #58).

    If an upstream was re-approved after this stage, the recorded
    ``upstream_hashes_at_approval`` no longer matches it. /pm-check reports that
    as DOWNSTREAM_UPSTREAM_STALE. An explicit --reapprove from the PM records
    that they reviewed this stage against the current upstreams, so the stored
    hashes are rebound. The body hash, approval time and approver stay as they
    are, because the body did not change. Exits the process.
    """
    meta = load_meta(project_root)
    stage_meta = get_stage(meta, stage_id)
    recorded = stage_meta.get("upstream_hashes_at_approval") or {}
    upstream_ids = upstream_stage_ids(stage_id, meta)
    current = {uid: get_stage(meta, uid).get("content_hash") for uid in upstream_ids}
    moved = [uid for uid in upstream_ids
             if recorded.get(uid) and current.get(uid) and recorded[uid] != current[uid]]
    if not moved:
        print(f"Stage {stage_id} is already approved and unchanged since approval, and its "
              "upstream stages have not changed since then. No action taken.")
        sys.exit(0)

    not_ready = [(uid, get_stage(meta, uid).get("status")) for uid in upstream_ids
                 if get_stage(meta, uid).get("status") != "approved"]
    if not_ready:
        print(f"Cannot re-approve stage {stage_id} yet: its upstream stages are not all approved.")
        for uid, status in not_ready:
            print(f"  Stage {uid}: {status}")
        print("Approve those first, then run this again:")
        print(f"  Claude: /pm-approve {stage_id} --reapprove")
        print(f"  Codex:  $pm-approve {stage_id} --reapprove")
        sys.exit(1)

    stage_meta["upstream_hashes_at_approval"] = current
    save_meta(meta, project_root)
    try:
        log("stage_rebound", project_root, stage_id, {
            "content_hash": stage_meta.get("content_hash"),
            "rebound_upstreams": {uid: {"from": recorded.get(uid), "to": current.get(uid)}
                                  for uid in moved},
        })
    except Exception as e:
        print(f"Warning: telemetry logging failed: {e}")
    print(f"Stage {stage_id} re-approved against the current upstream stage(s): {', '.join(moved)}.")
    print("Its content is unchanged, so its approval hash and downstream stages are unaffected.")
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Approve a PM-OS stage artifact.")
    parser.add_argument("stage_id", help="Two-digit stage number (e.g. '01')")
    parser.add_argument("--semantic-distance", dest="semantic_distance", type=float, default=None,
                        help="Optional agent-estimated semantic drift 0..1 (subjective judgment; "
                             "defaults to null when not supplied).")
    parser.add_argument("--reapprove", action="store_true",
                        help="Re-approve an already-approved stage whose body was directly "
                             "edited since approval, without requiring a downstream stage's "
                             "gate to first demote it to 'edited'. If the body is unchanged "
                             "but an upstream stage was re-approved since, re-approves this "
                             "stage against the current upstreams. Otherwise a no-op.")
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

    if current_status == "approved" and not args.reapprove:
        print(f"Stage {stage_id} is already approved. No action taken.")
        print("If you directly edited this artifact and the PM wants to re-approve it "
              "without running a downstream stage first, run:")
        print(f"  Claude: /pm-approve {stage_id} --reapprove")
        print(f"  Codex:  $pm-approve {stage_id} --reapprove")
        sys.exit(0)

    reapproved_from_approved = False
    if current_status == "approved" and args.reapprove:
        try:
            drift_hash = stage_content_hash(project_root, stage_id, apath)
        except CompositeHashError as e:
            print(f"Error: cannot check stage {stage_id} for drift — context pack is invalid: {e}")
            sys.exit(1)
        if drift_hash == fm.get("content_hash"):
            _rebind_upstreams(project_root, stage_id)  # exits
        # Body has drifted from the last approved snapshot — fall through to the
        # normal approval flow below, same as the draft/edited path.
        reapproved_from_approved = True

    if current_status == "pending":
        # The frontmatter `status` field can drift out of sync with reality: a
        # stage may have been generated (body written, `stage_generated` /
        # `stage_imported` / `stage_backfilled` telemetry recorded) yet still read
        # `pending` — e.g. a failed post-hook, an interrupted write, or a
        # hand-edit that reset the field. Refusing purely on that field wrongly
        # reports a real, generated artifact as "not generated yet" (GH #61).
        # Reconcile from ground truth (a non-empty body + a generation event)
        # before bailing out; only a genuinely ungenerated slot still stops here.
        if _has_generation_evidence(project_root, stage_id, apath):
            print(f"Note: stage {stage_id} frontmatter read 'pending' but a generation "
                  "event and body are present — reconciling to 'draft' and approving.")
            current_status = "draft"
        else:
            cmd = stage_command(stage_id)
            print(f"Stage {stage_id} has not been generated yet. Generate it first:")
            print(f"  Claude: /{cmd}")
            print(f"  Codex:  ${cmd}")
            sys.exit(1)

    validation_findings = []
    if stage_id in {"03", "04", "05", "06", "08"}:
        validation_findings = validate_artifact(project_root, stage_id, apath)
        if validation_findings:
            print(f"Warning: Stage {stage_id} has artifact contract findings; approval will continue:")
            print(format_findings(validation_findings))
            print()

    # Dual-mode: a 00w backed by a context-pack manifest is a composite artifact
    # (hash spans every manifest-declared member); every other stage — and a flat
    # single-file 00w — is body-hashed. A malformed/unsafe manifest must block
    # approval rather than silently fall back to a partial hash.
    try:
        content_hash = stage_content_hash(project_root, stage_id, apath)
    except CompositeHashError as e:
        print(f"Error: cannot approve stage {stage_id} — context pack is invalid: {e}")
        sys.exit(1)
    ts = datetime.now(timezone.utc).isoformat()
    try:
        pm = load_config()["pm_user"]
    except Exception:
        pm = "unknown"

    meta = load_meta(project_root)
    stage_meta = get_stage(meta, stage_id)
    # A new approved body earns the next version; re-approving the same body
    # keeps it (backlog #71). Stamped in meta and frontmatter together.
    version = stage_version.bump(stage_meta, content_hash)

    update_status(str(apath), "approved",
                  approved_at=ts,
                  approved_by=pm,
                  content_hash=content_hash,
                  version=version)

    upstream = {uid: get_stage(meta, uid)["content_hash"] for uid in upstream_stage_ids(stage_id, meta)}
    stage_meta["status"] = "approved"
    stage_meta["approved_at"] = ts
    stage_meta["content_hash"] = content_hash
    stage_meta["upstream_hashes_at_approval"] = upstream
    stage_meta.pop("edited_hash", None)
    # Mark downstream stages stale in the same meta write as the approval, before
    # the post-approve hook runs. A hung or killed hook then can no longer leave
    # them approved against content that has moved (backlog #31, #57). Their
    # telemetry events are logged below, after stage_approved.
    stale_events = []
    downstream_stale = cascade_stale(
        meta, project_root, [stage_id],
        {"reason": "upstream_approved", "triggering_upstream_stage": stage_id},
        log_to=stale_events,
    )
    save_meta(meta, project_root)

    if validation_findings:
        try:
            log("artifact_validation_warning", project_root, stage_id, {
                "contract_version": fm.get("artifact_contract_version"),
                "origin": stage_meta.get("origin", "generated"),
                "findings": [finding.as_dict() for finding in validation_findings],
            })
        except Exception as e:
            print(f"Warning: artifact validation telemetry failed: {e}")

    generated_hash = fm.get("generated_hash")
    regen_count = stage_meta.get("regeneration_count", 0)

    # --- Compute real timing + edit metrics ---
    # These are only meaningful when the stage was actually generated (has a
    # stage_generated event and a retained .history snapshot). Stage-00 group and
    # imported/backfilled artifacts have neither, so the fields stay None — correct.
    char_dist = norm_dist = time_to_approve = distance_method = None

    snap = _latest_generated_snapshot(project_root, apath)
    if snap is not None:
        try:
            _, gen_body = fm_read(str(snap))
            # Bounded: exact Levenshtein on a large PRD hung approval (backlog #56).
            char_dist, distance_method = bounded_edit_distance(gen_body, body)
            norm_dist = round(normalized_edit_distance(gen_body, body, char_dist), 6)
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
            "edit_distance_method": distance_method,
            "semantic_distance": args.semantic_distance,
            "time_to_approve_seconds": time_to_approve,
            "regeneration_count": regen_count,
            "implicit_reapproval": False,
            "reapproved_from_approved": reapproved_from_approved,
            "version": version,
        })
    except Exception as e:
        print(f"Warning: telemetry logging failed: {e}")
    for did, payload in stale_events:
        try:
            log("stage_marked_stale", project_root, did, payload)
        except Exception as e:
            print(f"Warning: stale-cascade telemetry failed for stage {did}: {e}")

    hook_path = Path.home() / ".pm-os" / "hooks" / "post-approve.py"
    if hook_path.exists():
        env = os.environ.copy()
        env["PM_OS_STAGE"] = stage_id
        timeout = _post_approve_timeout()
        try:
            # stdin=DEVNULL: nothing in the hook may wait for input, so a git or
            # credential prompt fails fast instead of hanging approval.
            result = subprocess.run(
                [sys.executable, str(hook_path)],
                env=env,
                cwd=str(project_root),
                stdin=subprocess.DEVNULL,
                timeout=timeout,
            )
            if result.returncode != 0:
                print(f"Warning: post-approve hook exited with code {result.returncode}")
        except subprocess.TimeoutExpired:
            print(f"Warning: post-approve hook did not finish within {timeout:.0f}s and was stopped. "
                  "The approval and the downstream stale-marking are already saved. "
                  "Companion HTML, the traceability index, the local git commit or the "
                  "central sync may be incomplete. Run /pm-check to inspect, and /pm-sync "
                  "to push. (Raise the limit with PM_OS_POST_APPROVE_TIMEOUT=<seconds>.)")

    # Report what is on disk now, which includes anything the hook changed.
    meta_reloaded = load_meta(project_root)
    for did in downstream_stage_ids(stage_id, meta_reloaded):
        try:
            if get_stage(meta_reloaded, did)["status"] == "stale" and did not in downstream_stale:
                downstream_stale.append(did)
        except KeyError:
            continue

    print(f"Stage {stage_id} approved (version {version}).")
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
