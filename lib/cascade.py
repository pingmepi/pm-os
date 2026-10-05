"""The downstream stale-cascade, shared by every path that (re-)approves a stage.

When a stage is (re-)approved with new content, every *approved* stage built on
top of it must be re-reviewed, so it is demoted to ``stale``. Three callers need
this and must agree exactly:

- ``scripts/pm_approve.py`` — explicit approval. Runs the cascade in-process,
  in the same meta write as the approval itself, *before* the post-approve hook,
  so a hung or killed hook can no longer leave downstream stages approved
  against an upstream that has moved (backlog #31 Part 1, #57).
- ``hooks/post-approve.py`` — re-runs it as an idempotent safety net; after
  ``pm_approve.py`` it finds nothing left to demote.
- ``hooks/pre-stage.py`` — implicit re-approval of edited upstreams.

The function mutates ``meta`` and the downstream artifacts' frontmatter and logs
one ``stage_marked_stale`` event per demoted stage. It does not save ``meta``;
the caller does, so the demotions land in the same write as the approval.
"""
from __future__ import annotations

from project import artifact_path, downstream_stage_ids, get_stage
from frontmatter import update_status
from telemetry import log


def cascade_stale(meta, project_root, triggering_ids, payload: dict, skip=(),
                  log_to: list | None = None) -> list[str]:
    """Demote approved stages downstream of ``triggering_ids`` to ``stale``.

    ``payload`` is the telemetry payload for each ``stage_marked_stale`` event.
    Stages in ``skip`` are left alone (pre-stage passes the edited stages it
    just reconciled). Pass a list as ``log_to`` to collect ``(stage_id, payload)``
    pairs instead of logging them immediately; ``pm_approve.py`` uses this so its
    ``stage_approved`` event is logged first. Returns the demoted stage ids in order.
    """
    triggering_ids = list(triggering_ids)
    skip = set(skip)
    downstream_ids = []
    for uid in triggering_ids:
        for did in downstream_stage_ids(uid, meta):
            if did not in downstream_ids:
                downstream_ids.append(did)

    demoted = []
    for did in downstream_ids:
        if did in skip:
            continue
        try:
            ds_meta = get_stage(meta, did)
        except KeyError:
            continue
        if ds_meta.get("status") != "approved":
            continue
        ds_meta["status"] = "stale"
        apath = artifact_path(project_root, did)
        if apath.exists():
            update_status(str(apath), "stale")
        demoted.append(did)
        if log_to is not None:
            log_to.append((did, dict(payload)))
            continue
        try:
            log("stage_marked_stale", project_root, did, dict(payload))
        except Exception as e:  # telemetry must never break the state transition
            print(f"Warning: stale-cascade telemetry failed for stage {did}: {e}")
    return demoted
