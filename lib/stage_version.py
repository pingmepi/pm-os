"""Human-readable approval version per stage (backlog #71, schema v6).

`version: N` names an approved body. It increments when an approval binds a
content hash different from the one the current version names: a normal
approval, an approval after an edit, the gate's implicit re-approval, and an
import/backfill adoption. A `--reapprove` rebind, or re-approving an unchanged
stale stage, keeps N, so one number always names one body. Regenerating a
draft leaves `version` alone: it is the last approved revision, and the next
approval decides whether the new body earns N+1. (PM decision 2026-10-21.)

Each stage in `.meta.yaml` carries `version` and `version_hash` (the content
hash `version` names; kept separately because regeneration clears
`content_hash`). Approval stamps `version` into the artifact frontmatter too.
"""
from __future__ import annotations

import json
from pathlib import Path

# Telemetry events that bind an approved body to a stage, and the payload key
# that carries that body's hash.
APPROVAL_EVENTS = {
    "stage_approved": "approved_hash",
    "stage_imported": "approved_hash",
    "stage_backfilled": "approved_hash",
    "implicit_reapproval": "new_hash",
}
APPROVED_LIKE = {"approved", "edited", "stale"}


def bump(stage_meta: dict, content_hash: str | None) -> int:
    """Record an approval of ``content_hash`` on a meta stage entry and return
    its version. Increments only when the hash differs from `version_hash`."""
    current = int(stage_meta.get("version") or 0)
    if not current or stage_meta.get("version_hash") != content_hash:
        current += 1
    stage_meta["version"] = current
    stage_meta["version_hash"] = content_hash
    return current


def all_approval_hashes(project_root: Path) -> dict[str, list[str]]:
    """{stage id: approved-body hashes, oldest first} from one read of
    telemetry.jsonl.

    Read leniently: a malformed line is skipped, never fatal. The hash chain is
    `/pm-sync --verify`'s concern, not the migration's.
    """
    path = Path(project_root) / "telemetry.jsonl"
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return {}
    hashes: dict[str, list[str]] = {}
    for line in lines:
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(event, dict):
            continue
        key = APPROVAL_EVENTS.get(event.get("event_type"))
        payload = event.get("payload") or {}
        value = payload.get(key) if key and isinstance(payload, dict) else None
        if value:
            hashes.setdefault(str(event.get("stage")), []).append(str(value))
    return hashes


def approval_hashes(project_root: Path, stage_id: str) -> list[str]:
    """Approved-body hashes for one stage, oldest first, from telemetry.jsonl."""
    return all_approval_hashes(project_root).get(stage_id, [])


def count_versions(hashes: list[str]) -> int:
    """Number of approvals that bound a new body: each hash that differs from
    the one before it counts. Approving A, B, then A again is v3."""
    count, previous = 0, None
    for value in hashes:
        if value != previous:
            count += 1
        previous = value
    return count


def backfill(meta: dict, project_root: Path | None) -> bool:
    """Schema 5 -> 6: give every stage that has ever been approved a `version`.

    Counted from telemetry when it records approvals for the stage; an
    approved, edited or stale stage with no usable events gets 1. A stage
    never approved gets no version. `version_hash` is the stage's approved
    `content_hash`, or the last approved hash in telemetry when regeneration
    has since cleared it. Idempotent: a stage that already has a `version` key
    is left alone.
    """
    changed = False
    by_stage: dict[str, list[str]] | None = None
    for stage in meta.get("stages") or []:
        if not isinstance(stage, dict) or "version" in stage:
            continue
        if by_stage is None:
            by_stage = all_approval_hashes(project_root) if project_root else {}
        hashes = by_stage.get(str(stage.get("id")), [])
        version = count_versions(hashes)
        if not version and stage.get("status") in APPROVED_LIKE:
            version = 1
        if version:
            stage["version"] = version
            stage["version_hash"] = stage.get("content_hash") or (hashes[-1] if hashes else None)
        else:
            stage["version"] = None
            stage["version_hash"] = None
        changed = True
    return changed
