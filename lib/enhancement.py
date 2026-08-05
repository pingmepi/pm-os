"""Read-only helpers for projecting an active E2 enhancement delta."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from artifact_contracts import split_stable_id_blocks
from frontmatter import read as fm_read
from project import CORE_STAGE_ORDER, artifact_path, load_meta


# Product/implementation stages the delta must cover even when they were authored
# *during* the enhancement (so absent from the frozen baseline). For an external
# product's first intake there is no prior PRD — stages 01-09 ARE the enhancement,
# and every block in them is `new`. Context pre-stages (00*) enter the delta only
# via the baseline, never as from-scratch.
PRODUCT_STAGE_IDS = tuple(CORE_STAGE_ORDER) + ("08", "09")


class EnhancementDeltaError(Exception):
    """An active enhancement cannot be exported safely."""


def _blocks(body: str) -> dict[str, str]:
    """Stable-id → block map, using the canonical cross-stage splitter.

    Delegates to ``artifact_contracts.split_stable_id_blocks`` so the delta accepts
    the same declaration shapes (heading, bullet, ordered-list, bare line, bold-wrap)
    and the same block boundaries as every other PM-OS parser — no bespoke regex.
    """
    return {stable_id: block.strip() for stable_id, block in split_stable_id_blocks(body or "").items()}


def _declared(block: str | None) -> str | None:
    match = re.search(r"(?i)change\s+type:\s*(new|modified|removed)\b", block or "")
    return match.group(1).lower() if match else None


def _stage_change_rows(stage_id: str, before_body: str | None, after_body: str | None) -> list[dict]:
    """Change dicts for one stage from its before/after bodies (``before`` None = all-new)."""
    if before_body == after_body:
        return []
    before_blocks = _blocks(before_body) if before_body is not None else {}
    after_blocks = _blocks(after_body or "")
    stable_ids = sorted(set(before_blocks) | set(after_blocks))
    if not stable_ids:
        # No stable ids anywhere: one coarse stage-level change.
        return [{
            "stage": str(stage_id), "id": f"STAGE-{stage_id}",
            "change_type": ("new" if before_body is None else "removed" if after_body is None else "modified"),
            "declared_change_type": None,
            "before": before_body.strip() if before_body is not None else None,
            "after": after_body.strip() if after_body is not None else None,
        }]
    rows: list[dict] = []
    for stable_id in stable_ids:
        before = before_blocks.get(stable_id)
        after = after_blocks.get(stable_id)
        if before == after:
            continue
        change_type = "new" if before is None else "removed" if after is None else "modified"
        rows.append({
            "stage": str(stage_id), "id": stable_id, "change_type": change_type,
            "declared_change_type": _declared(after), "before": before, "after": after,
        })
    return rows


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

    # 1. Baseline-captured stages: diff the frozen snapshot against the current body.
    seen: set[str] = set()
    for stage_id, baseline in artifacts.items():
        seen.add(str(stage_id))
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
        changes.extend(_stage_change_rows(str(stage_id), before_body, after_body))

    # 2. Product stages authored *during* the enhancement (absent from the frozen
    #    baseline): the whole stage is new. This is the external-product / first-
    #    intake case — no prior PRD existed, so stages 01-09 are the enhancement.
    for stage_id in PRODUCT_STAGE_IDS:
        if stage_id in seen:
            continue
        current = artifact_path(root, stage_id)
        if not current.is_file():
            continue
        status = statuses.get(stage_id)
        if status in (None, "pending"):
            continue  # not authored yet
        if require_approved and status != "approved":
            raise EnhancementDeltaError(
                f"changed stage {stage_id} is {status or 'missing'}, not approved"
            )
        _after_fm, after_body = fm_read(str(current))
        changes.extend(_stage_change_rows(stage_id, None, after_body))

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
