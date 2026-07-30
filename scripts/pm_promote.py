#!/usr/bin/env python3
"""Preview the cost of promoting/demoting a requirement's release tier.

Read-only. A tier change is a body edit to the PRD, so this computes the current
tier, the target tier, and which downstream stages would re-stale on the next
re-approval — WITHOUT modifying any artifact or state. The `/pm-promote` skill
performs the actual re-tag + mini-spec regeneration; the state machine (hash
drift + staleness cascade) handles the consequences. Keeping this script
read-only honors the golden rule: never write gate/hash/status here.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ.get("PM_OS_LIB_PATH") or str(Path.home() / ".pm-os" / "lib"))

from project import resolve_project, load_meta, get_stage, downstream_stage_ids, STAGE_NAMES, artifact_path  # noqa: E402
from artifact_contracts import (  # noqa: E402
    DEFAULT_TIER,
    TIERS,
    split_functional_requirement_blocks,
    split_user_story_blocks,
)
from frontmatter import read as fm_read  # noqa: E402
import traceability  # noqa: E402

# Release bands ordered earliest → latest. Promote steps toward mvp; demote away.
_TIER_ORDER = ["mvp", "v1", "v2", "later"]


def _step_tier(current: str, promote: bool) -> str | None:
    i = _TIER_ORDER.index(current)
    j = i - 1 if promote else i + 1
    return _TIER_ORDER[j] if 0 <= j < len(_TIER_ORDER) else None


def preview(req_id: str, to: str | None = None, demote: bool = False) -> None:
    root = resolve_project()
    meta = load_meta(root)
    req_id = req_id.upper()

    # Gate on ids actually DECLARED as a US/FR block in the PRD. An id merely
    # referenced (e.g. a story tracing to an undeclared FR-999) has no block to
    # re-tag, so promoting it is meaningless — even though the traceability index,
    # which indexes every referenced id, would happily report a tier.
    prd_path = artifact_path(root, "03")
    prd_body = ""
    if prd_path.exists():
        try:
            _fm, prd_body = fm_read(str(prd_path))
        except Exception:
            prd_body = ""
    declared = {
        d.upper() for d in (
            set(split_user_story_blocks(prd_body)) | set(split_functional_requirement_blocks(prd_body))
        )
    }
    if req_id not in declared:
        raise SystemExit(
            f"{req_id} is not a declared US-###/FR-### block in the PRD "
            f"(absent, or only referenced). Promote operates on declared story/requirement blocks."
        )

    # Build fresh from the current PRD body so the preview reflects unsaved-tier
    # reality, not the last-approved index.
    entry = (traceability.build_index(root).get("requirements") or {}).get(req_id) or {}
    current = entry.get("tier") or DEFAULT_TIER

    if to:
        target = to.lower()
        if target not in TIERS:
            raise SystemExit(f"Invalid target tier '{to}'. Choose one of: {', '.join(TIERS)}.")
    else:
        target = _step_tier(current, promote=not demote)
        if target is None:
            edge = "highest (mvp)" if not demote else "lowest (later)"
            raise SystemExit(f"{req_id} is already at the {edge} tier; nothing to do.")

    if target == current:
        raise SystemExit(f"{req_id} is already tier '{current}'; nothing to do.")

    # Cost model: re-tagging edits the PRD (03) body → hash drift → on re-approval
    # every currently-approved downstream stage cascades to stale.
    prd_status = get_stage(meta, "03").get("status")
    will_restale = [
        d for d in downstream_stage_ids("03", meta)
        if get_stage(meta, d).get("status") == "approved"
    ]

    print(f"Promote {req_id}: {current} → {target}")
    if prd_status in ("pending", "draft"):
        print("  Cost: FREE — the PRD isn't approved yet, so re-tagging cascades nothing.")
    elif not will_restale:
        print("  Cost: LOW — re-approve 03 (PRD); no approved downstream stage to re-stale.")
    else:
        names = ", ".join(f"{d} ({STAGE_NAMES[d]})" for d in will_restale)
        print(f"  Cost: CASCADE — on re-approval of the PRD these re-stale: {names}")

    if target == "mvp":
        print(f"  {req_id} enters the MVP band → its mini-spec must be elaborated to full fidelity.")
    elif current == "mvp":
        print(f"  {req_id} leaves the MVP band → it becomes a SOW-grade stub.")

    print("\nPreview only — no files changed. Use /pm-promote to apply the re-tag and regenerate.")


def main() -> None:
    p = argparse.ArgumentParser(
        description="Preview a PM-OS requirement tier promotion/demotion (read-only)."
    )
    p.add_argument("req_id", help="Requirement id, e.g. US-003 or FR-012.")
    p.add_argument("--to", help="Target tier (mvp|v1|v2|later). Omit to step one band.")
    p.add_argument("--demote", action="store_true",
                   help="Step one band later instead of earlier (ignored when --to is given).")
    args = p.parse_args()
    preview(args.req_id, to=args.to, demote=args.demote)


if __name__ == "__main__":
    main()
