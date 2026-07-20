#!/usr/bin/env python3
"""Export the approved PM-OS pipeline to an external tracker (Phase 4b).

Mechanical only — no network. The judgment/orchestration and the actual tracker
(MCP) calls live in the `pm-handoff` skill; this script:

  plan    Parse the approved PRD (+ approved TRD) into a tracker-agnostic ticket
          map and write a PM-readable dry-run (handoff/jira-plan.md) plus a
          machine map (handoff/jira-plan.json). Read-only; no network.
  record  Take the {stable-id -> created ticket key} map the skill produced after
          creating tickets via MCP, and write each key back into the matching
          requirement's / task's `tickets: []` slot in .traceability.yaml, then
          log a `handoff_exported` telemetry event. (Implemented in Phase 4b.)

The flow is dry-run -> PM confirm -> create -> record: this script never creates
or mutates any external object. Only refs/ids/summaries are stored locally, never
bulk copies of external data.

Usage:
    python3 pm_handoff.py plan                 # write ./handoff/jira-plan.{md,json}
    python3 pm_handoff.py plan --output DIR     # write into DIR instead
    python3 pm_handoff.py record --input m.json # record {id: ticket-key} back
    echo '{"US-001":"RA-1"}' | python3 pm_handoff.py record   # …or via stdin
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.environ.get("PM_OS_LIB_PATH") or str(Path.home() / ".pm-os" / "lib"))

from artifact_contracts import (  # noqa: E402
    FUNCTIONAL_REQ_ID_RE,
    _sections,
    split_task_blocks,
    split_user_story_blocks,
    work_breakdown_section,
)
from frontmatter import read as fm_read  # noqa: E402
from project import artifact_path, load_meta, resolve_project  # noqa: E402
from telemetry import log as telemetry_log  # noqa: E402
import traceability  # noqa: E402

# Only one tracker in Phase 4b (the roadmap deliberately picks the single tracker
# the PM uses, not both). Jira is that tracker; the plan is otherwise
# tracker-agnostic so a second driver can reuse it later.
TRACKER = "jira"
PLAN_BASENAME = "jira-plan"

# A functional/umbrella requirement is declared as a bullet or ordered-list item
# in the stage-03 Functional Requirements section (never a heading). Mirrors
# scripts/pm_share.py so both exports agree on what an FR block is.
_FR_BLOCK_START_RE = re.compile(
    r"^(?:[-*+]\s+|\d+\.\s+)?\**(?P<id>(?:FR|REQ)-\d{3,})\b",
    re.MULTILINE | re.IGNORECASE,
)


# --- small shared helpers (kept in lockstep with pm_share.py) ------------------

def _stage_status(meta: dict, stage_id: str) -> str | None:
    for stage in meta.get("stages", []):
        if stage.get("id") == stage_id:
            return stage.get("status")
    return None


def _read_artifact(root: Path, stage_id: str):
    path = artifact_path(root, stage_id)
    if not path.exists():
        return None, None
    try:
        return fm_read(str(path))
    except Exception:
        return None, None


def _stamp(root: Path, stage_id: str) -> str | None:
    """`03-prd.md@<hash12>` provenance tag for a source artifact, or None."""
    fm, _body = _read_artifact(root, stage_id)
    if fm is None:
        return None
    name = artifact_path(root, stage_id).name
    h = fm.get("content_hash") or fm.get("generated_hash")
    return f"{name}@{h[:12]}" if h else name


def _section_of(body: str | None, title: str) -> str:
    if not body:
        return ""
    return _sections(body).get(title.strip().lower(), "")


def _split_blocks(text: str, start_re: "re.Pattern[str]") -> dict[str, str]:
    matches = list(start_re.finditer(text))
    blocks: dict[str, str] = {}
    for index, match in enumerate(matches):
        block_id = match.group("id").upper()
        if block_id in blocks:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        blocks[block_id] = text[match.start():end]
    return blocks


def _strip_decl(line: str, block_id: str) -> str:
    """Strip a block's declaration prefix from ``line``: the leading list/heading
    marker, the id, an optional ``(priority)`` parenthetical, and any separator
    (``:``/``—``/``-``) or bold markers. Handles both the FR bullet shape
    (``- **FR-001 (must):** text``) and the heading shape (``### TSK-001 — text``)."""
    t = re.sub(r"^(?:#{1,6}\s+|[-*+]\s+|\d+\.\s+)?", "", line)
    t = re.sub(
        rf"^\**\s*{re.escape(block_id)}\b\s*(?:\([^)]*\))?\s*[:—–-]*\s*\**\s*",
        "", t, flags=re.IGNORECASE,
    )
    return t.strip()


def _title_of(block_id: str, block: str) -> str:
    """Best-effort human title from a block's declaration line."""
    first = block.strip().splitlines()[0] if block.strip() else ""
    return _strip_decl(first, block_id) or block_id


def _body_of(block: str, block_id: str) -> str:
    """A block's description: the lines after the declaration for a multi-line block,
    or the declaration line's own text (id stripped) for a single-line block."""
    lines = block.strip().splitlines()
    if not lines:
        return ""
    if len(lines) > 1:
        return "\n".join(lines[1:]).strip()
    return _strip_decl(lines[0], block_id)


# --- plan ----------------------------------------------------------------------

def _resolve_out_dir(root: Path, output: str | None) -> Path:
    out = (Path(output) if output else root / "handoff").resolve()
    if out.exists() and out.is_file():
        raise SystemExit(f"Error: {out} is a file, not a directory.")
    out.mkdir(parents=True, exist_ok=True)
    return out


def build_plan(root: Path) -> dict:
    """Build the tracker-agnostic ticket map from the approved PRD (+ approved TRD).

    Structure: one Epic per PRD user story (US-###); each functional requirement
    (FR-###/REQ-###) the story owns becomes a child Story; each approved TRD task
    (TSK-###) becomes a child Task under the epic that owns the requirement it
    implements. Requirements/tasks with no owning story are surfaced under a
    synthetic 'Unassigned' epic rather than dropped.
    """
    meta = load_meta(root)
    project_name = meta.get("project_name") or meta.get("project_slug", "project")
    project_slug = meta.get("project_slug", "project")

    # The export projects *approved* product decisions — stage 03 must be exactly
    # `approved` (not draft/stale/pending, and deliberately not `edited`: an edited
    # PRD's body has drifted from the traceability index rebuilt at approval).
    prd_status = _stage_status(meta, "03")
    if prd_status != "approved":
        raise SystemExit(
            f"Error: stage 03 (PRD) is '{prd_status or 'not present'}', not approved "
            "— the handoff exports approved decisions only. Approve the PRD "
            "(/pm-approve 03) before exporting."
        )

    _prd_fm, prd_body = _read_artifact(root, "03")
    if not prd_body:
        raise SystemExit("Error: no approved PRD (03-prd.md) found — nothing to export.")

    prd_stamp = _stamp(root, "03")
    stories_section = _section_of(prd_body, "user stories with acceptance criteria")
    fr_section = _section_of(prd_body, "functional requirements")
    story_blocks = split_user_story_blocks(stories_section or prd_body)
    fr_blocks = _split_blocks(fr_section, _FR_BLOCK_START_RE)

    # Approved-TRD tasks come from the traceability index, which already excludes a
    # draft/stale TRD (Phase 3.5b). Descriptions come from the Work Breakdown body.
    index = traceability.load_index(root) or traceability.build_index(root)
    index_tasks = index.get("tasks") or {}
    trd_status = _stage_status(meta, "08")
    trd_stamp = _stamp(root, "08") if (index_tasks and trd_status == "approved") else None
    _trd_fm, trd_body = _read_artifact(root, "08") if trd_stamp else (None, None)
    task_blocks = split_task_blocks(work_breakdown_section(trd_body)) if trd_body else {}

    # req_id -> owning story id. A story owns the FRs it cites (forward) and the FRs
    # whose own block names the story (reverse), mirroring pm_share's linkage.
    owner: dict[str, str] = {}
    epics: list[dict] = []
    for story_id, block in story_blocks.items():
        owner.setdefault(story_id, story_id)
        forward = [m.upper() for m in FUNCTIONAL_REQ_ID_RE.findall(block)]
        reverse = [fid for fid, fblk in fr_blocks.items()
                   if re.search(rf"\b{re.escape(story_id)}\b", fblk, re.IGNORECASE)]
        owned_frs = list(dict.fromkeys(forward + reverse))
        for fid in owned_frs:
            owner.setdefault(fid, story_id)
        epics.append({
            "ref": story_id,
            "type": "Epic",
            "summary": f"{story_id} — {_title_of(story_id, block)}",
            "description": _body_of(block, story_id),
            "source": prd_stamp,
            "parent_ref": None,
            "children": list(owned_frs),  # filled/extended below
        })

    items: list[dict] = []
    unassigned_children: list[str] = []

    # Emit epics, then their FR children, then TRD task children.
    epic_by_ref = {e["ref"]: e for e in epics}
    for epic in epics:
        epic["children"] = []  # rebuilt as we attach, preserving order
    for epic in epics:
        items.append(epic)

    # FR child stories.
    for fr_id, fblk in fr_blocks.items():
        parent = owner.get(fr_id)
        (epic_by_ref[parent]["children"] if parent in epic_by_ref else unassigned_children).append(fr_id)
        items.append({
            "ref": fr_id,
            "type": "Story",
            "summary": f"{fr_id} — {_title_of(fr_id, fblk)}",
            "description": _body_of(fblk, fr_id),
            "source": prd_stamp,
            "parent_ref": parent if parent in epic_by_ref else "UNASSIGNED",
        })

    # TRD task children.
    for tsk_id in index_tasks:
        implements = index_tasks[tsk_id].get("implements") or []
        parent = next((owner[r] for r in implements if r in owner), None)
        (epic_by_ref[parent]["children"] if parent in epic_by_ref else unassigned_children).append(tsk_id)
        block = task_blocks.get(tsk_id, "")
        items.append({
            "ref": tsk_id,
            "type": "Task",
            "summary": f"{tsk_id} — {_title_of(tsk_id, block)}",
            "description": _body_of(block, tsk_id),
            "source": trd_stamp,
            "parent_ref": parent if parent in epic_by_ref else "UNASSIGNED",
            "implements": implements,
        })

    if unassigned_children:
        items.append({
            "ref": "UNASSIGNED",
            "type": "Epic",
            "summary": "Unassigned — requirements/tasks not owned by a user story",
            "description": "Items with no owning user story. Review before creating: "
                           "either link them to a story in the PRD or create them standalone.",
            "source": prd_stamp,
            "parent_ref": None,
            "children": list(unassigned_children),
        })

    counts = {
        "epics": sum(1 for i in items if i["type"] == "Epic" and i["ref"] != "UNASSIGNED"),
        "stories": sum(1 for i in items if i["type"] == "Story"),
        "tasks": sum(1 for i in items if i["type"] == "Task"),
        "unassigned": len(unassigned_children),
    }

    return {
        "tracker": TRACKER,
        "project_name": project_name,
        "project_slug": project_slug,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_stamps": {"prd": prd_stamp, "trd": trd_stamp},
        "items": items,
        "counts": counts,
    }


def _render_plan_md(plan: dict) -> str:
    lines: list[str] = []
    lines.append(f"# Handoff plan — {plan['project_name']} → {plan['tracker'].title()}")
    lines.append("")
    lines.append(f"> DRY RUN — nothing has been created. Generated {plan['generated_at']}.")
    lines.append(f"> Source: {plan['source_stamps']['prd']}"
                 + (f", {plan['source_stamps']['trd']}" if plan['source_stamps']['trd'] else "")
                 + ".")
    c = plan["counts"]
    lines.append("")
    lines.append(f"**{c['epics']} epic(s), {c['stories']} story(ies), {c['tasks']} task(s)**"
                 + (f" · {c['unassigned']} unassigned" if c["unassigned"] else "")
                 + ". Review, then confirm to create.")
    lines.append("")

    by_ref = {i["ref"]: i for i in plan["items"]}
    epics = [i for i in plan["items"] if i["type"] == "Epic"]
    for epic in epics:
        lines.append(f"## {epic['summary']}")
        if epic["description"]:
            lines.append("")
            lines.append(epic["description"])
        for child_ref in epic.get("children", []):
            child = by_ref.get(child_ref)
            if not child:
                continue
            lines.append("")
            lines.append(f"- **[{child['type']}] {child['summary']}**")
            if child.get("implements"):
                lines.append(f"  - implements: {', '.join(child['implements'])}")
            if child["description"]:
                snippet = " ".join(child["description"].split())
                if len(snippet) > 240:
                    snippet = snippet[:237] + "…"
                lines.append(f"  - {snippet}")
        lines.append("")
    lines.append("---")
    lines.append("_Confirm to create these in "
                 f"{plan['tracker'].title()}; ticket keys are then recorded back into "
                 ".traceability.yaml. Nothing here has touched the tracker._")
    return "\n".join(lines) + "\n"


def cmd_plan(root: Path, output: str | None) -> None:
    plan = build_plan(root)
    out_dir = _resolve_out_dir(root, output)
    json_path = out_dir / f"{PLAN_BASENAME}.json"
    md_path = out_dir / f"{PLAN_BASENAME}.md"
    json_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    md_path.write_text(_render_plan_md(plan), encoding="utf-8")
    c = plan["counts"]
    print(f"Handoff plan written (DRY RUN — nothing created):")
    print(f"  {md_path}   (review this)")
    print(f"  {json_path}   (machine map)")
    print(f"  {c['epics']} epic(s), {c['stories']} story(ies), {c['tasks']} task(s)"
          + (f", {c['unassigned']} unassigned" if c["unassigned"] else "") + ".")


# --- record --------------------------------------------------------------------

# The id shapes the record step accepts, routed to the right index slot.
_REQ_REF_RE = re.compile(r"^(?:REQ|US|FR)-\d{3,}$", re.IGNORECASE)
_TASK_REF_RE = re.compile(r"^TSK-\d{3,}$", re.IGNORECASE)


def _load_created_map(input_path: str | None) -> dict:
    """Load the {stable-id -> created ticket key} map the skill produced after
    creating tickets via MCP. From a JSON file (--input) or stdin."""
    raw = Path(input_path).read_text(encoding="utf-8") if input_path else sys.stdin.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Error: could not parse the created-ticket map as JSON: {exc}")
    # Accept either a flat {ref: key} map or {"created": {ref: key}}.
    created = data.get("created") if isinstance(data, dict) and "created" in data else data
    if not isinstance(created, dict) or not all(isinstance(v, str) for v in created.values()):
        raise SystemExit("Error: expected a JSON object mapping stable ids to ticket keys, "
                         'e.g. {"US-001": "RA-1", "TSK-001": "RA-3"}.')
    return {k.upper(): v for k, v in created.items()}


def cmd_record(root: Path, input_path: str | None) -> None:
    created = _load_created_map(input_path)
    index = traceability.load_index(root) or traceability.build_index(root)
    requirements = index.setdefault("requirements", {})
    tasks = index.setdefault("tasks", {})

    recorded: dict[str, str] = {}
    skipped: list[str] = []
    for ref, key in created.items():
        if ref == "UNASSIGNED":
            continue
        if _REQ_REF_RE.match(ref):
            entry = requirements.get(ref)
            slot = entry.setdefault("tickets", []) if entry is not None else None
        elif _TASK_REF_RE.match(ref):
            entry = tasks.get(ref)
            slot = entry.setdefault("tickets", []) if entry is not None else None
        else:
            slot = None
        if slot is None:
            skipped.append(ref)
            continue
        if key not in slot:
            slot.append(key)
        recorded[ref] = key

    traceability.write_index(root, index)

    # Telemetry: refs/counts/keys only — never bulk copies of external data.
    telemetry_log("handoff_exported", root, "08", {
        "tracker": TRACKER,
        "created_count": len(recorded),
        "tickets": recorded,
    })

    print(f"Recorded {len(recorded)} ticket ref(s) into {traceability.TRACEABILITY_FILENAME}.")
    for ref, key in recorded.items():
        print(f"  {ref} -> {key}")
    if skipped:
        print(f"Skipped {len(skipped)} id(s) not found in the traceability index "
              f"(re-run after approving the source stage, or check the ids): {', '.join(skipped)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the approved PM-OS pipeline to a tracker (Phase 4b).")
    sub = parser.add_subparsers(dest="command", required=True)
    p_plan = sub.add_parser("plan", help="Build a dry-run ticket map from the approved PRD (+ TRD).")
    p_plan.add_argument("--output", help="Output directory (default: ./handoff/).")
    p_record = sub.add_parser("record", help="Write created ticket keys back into .traceability.yaml.")
    p_record.add_argument("--input", help="JSON file of {stable-id: ticket-key} (default: stdin).")

    args = parser.parse_args()

    try:
        root = resolve_project()
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    if args.command == "plan":
        cmd_plan(root, args.output)
    elif args.command == "record":
        cmd_record(root, args.input)


if __name__ == "__main__":
    main()
