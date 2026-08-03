"""Read-only helpers for projecting an active E2 enhancement delta."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from frontmatter import read as fm_read
from project import artifact_path, load_meta


STABLE_ID_RE = re.compile(
    r"(?m)^(?:#{1,6}\s+|[-*+]\s+(?:\*\*)?)"
    r"(?P<id>(?:EPIC|US|FR|REQ|NFR|UJ|SCR|TC|TSK|TR|ADR)-\d+)\b.*$",
    re.IGNORECASE,
)


class EnhancementDeltaError(Exception):
    """An active enhancement cannot be exported safely."""


def _blocks(body: str) -> dict[str, str]:
    matches = list(STABLE_ID_RE.finditer(body or ""))
    result: dict[str, str] = {}
    for index, match in enumerate(matches):
        stable_id = match.group("id").upper()
        if stable_id in result:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        result[stable_id] = body[match.start():end].strip()
    return result


def _declared(block: str | None) -> str | None:
    match = re.search(r"(?i)change\s+type:\s*(new|modified|removed)\b", block or "")
    return match.group(1).lower() if match else None


def active_enhancement_delta(root: Path, require_approved: bool = True) -> dict | None:
    """Return the active baseline-vs-current delta, or None outside E2.

    Handoff callers use ``require_approved`` so a stale or draft artifact can
    never leak into an implementation package.
    """
    root = Path(root)
    index_path = root / ".enhancements" / "index.yaml"
    if not index_path.exists():
        return None
    try:
        index = yaml.safe_load(index_path.read_text(encoding="utf-8")) or {}
        cycle_id = index.get("active_cycle")
        if not cycle_id:
            return None
        context_path = root / ".enhancements" / cycle_id / "context.yaml"
        context = yaml.safe_load(context_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        raise EnhancementDeltaError(f"enhancement context is invalid: {exc}")
    boundary = context.get("boundary") or {}
    if not boundary.get("recorded_at"):
        raise EnhancementDeltaError(
            "active enhancement boundary is not recorded; approve 00c/00u and run set-boundary"
        )

    meta = load_meta(root)
    statuses = {str(stage.get("id")): stage.get("status") for stage in meta.get("stages", [])}
    changes: list[dict] = []
    artifacts = (context.get("baseline") or {}).get("artifacts") or {}
    if not artifacts:
        raise EnhancementDeltaError("active enhancement has no frozen approved baseline")
    for stage_id, baseline in artifacts.items():
        snapshot = root / str(baseline.get("snapshot_path") or "")
        if not snapshot.is_file():
            raise EnhancementDeltaError(f"baseline snapshot is missing for stage {stage_id}")
        _before_fm, before_body = fm_read(str(snapshot))
        current = artifact_path(root, stage_id)
        after_body = None
        if current.is_file():
            _after_fm, after_body = fm_read(str(current))
        if after_body == before_body:
            continue
        if require_approved and statuses.get(str(stage_id)) != "approved":
            raise EnhancementDeltaError(
                f"changed stage {stage_id} is {statuses.get(str(stage_id)) or 'missing'}, not approved"
            )
        before_blocks = _blocks(before_body)
        after_blocks = _blocks(after_body or "")
        stable_ids = sorted(set(before_blocks) | set(after_blocks))
        if not stable_ids:
            changes.append({
                "stage": str(stage_id), "id": f"STAGE-{stage_id}",
                "change_type": "removed" if after_body is None else "modified",
                "declared_change_type": None, "before": before_body.strip(),
                "after": after_body.strip() if after_body is not None else None,
            })
            continue
        for stable_id in stable_ids:
            before = before_blocks.get(stable_id)
            after = after_blocks.get(stable_id)
            if before == after:
                continue
            change_type = "new" if before is None else "removed" if after is None else "modified"
            changes.append({
                "stage": str(stage_id), "id": stable_id, "change_type": change_type,
                "declared_change_type": _declared(after), "before": before, "after": after,
            })

    return {
        "schema_version": 1,
        "cycle_id": cycle_id,
        "baseline_captured_at": (context.get("baseline") or {}).get("captured_at"),
        "baseline_artifacts": artifacts,
        "boundary": boundary,
        "repository": context.get("repository") or {},
        "scan": context.get("scan") or {},
        "changes": changes,
    }
