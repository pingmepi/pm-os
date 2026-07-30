#!/usr/bin/env python3
"""Export the approved PM-OS pipeline to an external tracker (Phase 4b).

Mechanical only — no network. The judgment/orchestration and the actual tracker
(MCP) calls live in the `pm-handoff` skill; this script:

  plan    Parse the approved PRD (+ approved TRD) into a tracker-agnostic ticket
          map and write a PM-readable dry-run (handoff/jira-plan.md) plus a
          machine map (handoff/jira-plan.json). Read-only; no network.
  export  Render that same plan as a Jira CSV-importer file (handoff/jira-import.csv)
          plus an import guide, for PMs with no authorized Atlassian connector.
          Descriptions are converted to Jira wiki markup. Read-only; no network.
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
    python3 pm_handoff.py export                # write ./handoff/jira-import.csv
    python3 pm_handoff.py record --input m.json # record {id: ticket-key} back
    echo '{"US-001":"RA-1"}' | python3 pm_handoff.py record   # …or via stdin
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.environ.get("PM_OS_LIB_PATH") or str(Path.home() / ".pm-os" / "lib"))

from artifact_contracts import (  # noqa: E402
    _sections,
    split_task_blocks,
    work_breakdown_section,
)
from delivery_map import build_prd_delivery_map, body_of, title_of  # noqa: E402
from frontmatter import read as fm_read  # noqa: E402
from jira_markup import to_jira_markup  # noqa: E402
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

    Jira-native structure: PRD Product Epics (EPIC-###) become Jira Epics; each
    PRD user story (US-###) becomes a Jira Story under its declared epic; each
    functional requirement (FR-###/REQ-###) becomes a Jira Task under its declared
    epic. A TRD task that implements exactly one exported Story/Task becomes a
    Subtask under that item; one that implements multiple refs in the same epic
    becomes a Task under that epic; cross-epic/unresolved tasks stay unparented
    and are counted for PM review.
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
    # Jira tickets are build work — scope to the mvp band so deferred (v1/v2/later)
    # SOW-grade stubs stay roadmap context, not Stories/Tasks/Epics (AGENTS.md).
    delivery = build_prd_delivery_map(prd_body, mvp_only=True)
    story_blocks = delivery.story_blocks
    fr_blocks = delivery.requirement_blocks

    # Build the traceability view *fresh* rather than trusting the on-disk index.
    # An implicit re-approval (hooks/pre-stage.py) can re-approve the edited PRD and
    # cascade the TRD to stale *without* rebuilding .traceability.yaml, so load_index
    # could hand back stale requirement/task entries the export would then create.
    # build_index re-derives from the current artifact bodies (and already excludes a
    # non-approved TRD's tasks — Phase 3.5b).
    index = traceability.build_index(root)
    # Belt-and-suspenders: tasks are exportable only when the TRD is currently
    # approved. Gate on the live meta status (the cascade updates it reliably), so a
    # stale/edited TRD contributes no tasks even if its frontmatter status lagged.
    trd_status = _stage_status(meta, "08")
    index_tasks = (index.get("tasks") or {}) if trd_status == "approved" else {}
    trd_stamp = _stamp(root, "08") if index_tasks else None
    _trd_fm, trd_body = _read_artifact(root, "08") if trd_stamp else (None, None)
    task_blocks = split_task_blocks(work_breakdown_section(trd_body)) if trd_body else {}

    # req_id -> owning story id. This is logical ownership for PM review only;
    # Jira Tasks cannot be children of Jira Stories, so actual parentage comes from
    # each requirement's declared Product Epic.
    owner: dict[str, str] = {story_id: story_id for story_id in story_blocks}
    for story_id, reqs in delivery.story_requirements.items():
        for req_id in reqs:
            owner.setdefault(req_id, story_id)

    items: list[dict] = []
    for epic_ref, epic in delivery.epics.items():
        items.append({
            "ref": epic_ref,
            "type": "Epic",
            "summary": f"{epic_ref} — {epic.title}",
            "description": epic.body,
            "source": prd_stamp,
            "parent_ref": None,
            "children": [],
        })

    item_by_ref = {item["ref"]: item for item in items}
    unassigned_children: list[str] = list(delivery.unassigned)
    if not delivery.epics:
        unassigned_children.extend(list(story_blocks) + list(fr_blocks))

    for story_id, block in story_blocks.items():
        epic_ref = delivery.story_to_epic.get(story_id)
        if epic_ref in item_by_ref:
            item_by_ref[epic_ref]["children"].append(story_id)
        elif story_id not in unassigned_children:
            unassigned_children.append(story_id)
        item = {
            "ref": story_id,
            "type": "Story",
            "summary": f"{story_id} — {title_of(story_id, block)}",
            "description": body_of(block, story_id),
            "source": prd_stamp,
            "parent_ref": epic_ref if epic_ref in item_by_ref else None,
            "children": [],
        }
        items.append(item)
        item_by_ref[story_id] = item

    # FR/REQ standard Jira tasks under their declared Product Epic. They retain
    # logical ownership through ``story_ref`` because Jira cannot parent Task under
    # Story.
    for fr_id, fblk in fr_blocks.items():
        story_ref = owner.get(fr_id)
        epic_ref = delivery.requirement_to_epic.get(fr_id)
        if epic_ref in item_by_ref:
            item_by_ref[epic_ref]["children"].append(fr_id)
        elif fr_id not in unassigned_children:
            unassigned_children.append(fr_id)
        item = {
            "ref": fr_id,
            "type": "Task",
            "summary": f"{fr_id} — {title_of(fr_id, fblk)}",
            "description": body_of(fblk, fr_id),
            "source": prd_stamp,
            "parent_ref": epic_ref if epic_ref in item_by_ref else None,
            "story_ref": story_ref,
            "children": [],
        }
        items.append(item)
        item_by_ref[fr_id] = item

    # TRD task children. One implemented exported item maps to a Jira Subtask under
    # it. Multiple implemented refs in the same Product Epic map to a Jira Task
    # under that Epic. Cross-epic or unresolved tasks stay unparented so the PM can
    # correct the TRD/PRD instead of PM-OS silently choosing a parent.
    for tsk_id in index_tasks:
        implements = index_tasks[tsk_id].get("implements") or []
        exportable_impls = [ref for ref in implements if ref in item_by_ref]
        # The delivery map is mvp-only, so `item_by_ref` holds only mvp-band items. A
        # task that implements requirement(s) but none in the mvp band (i.e. it serves
        # only deferred v1/v2/later work) has no exportable parent — don't emit it as a
        # Jira ticket (AGENTS.md: the handoff is the mvp band). A task with no
        # `implements` at all (orphan) is left to /pm-check rather than silently dropped.
        if implements and not exportable_impls:
            continue
        parent_ref = None
        issue_type = "Task"
        if len(exportable_impls) == 1:
            parent_ref = exportable_impls[0]
            issue_type = "Subtask"
        elif len(exportable_impls) > 1:
            epic_refs = {
                delivery.story_to_epic.get(ref) or delivery.requirement_to_epic.get(ref)
                for ref in exportable_impls
            }
            epic_refs.discard(None)
            if len(epic_refs) == 1:
                parent_ref = next(iter(epic_refs))
                issue_type = "Task"
        if parent_ref in item_by_ref:
            item_by_ref[parent_ref]["children"].append(tsk_id)
        else:
            parent_ref = None
            if tsk_id not in unassigned_children:
                unassigned_children.append(tsk_id)
        block = task_blocks.get(tsk_id, "")
        item = {
            "ref": tsk_id,
            "type": issue_type,
            "summary": f"{tsk_id} — {title_of(tsk_id, block)}",
            "description": body_of(block, tsk_id),
            "source": trd_stamp,
            "parent_ref": parent_ref,
            "implements": implements,
        }
        items.append(item)
        item_by_ref[tsk_id] = item

    unassigned_children = list(dict.fromkeys(unassigned_children))
    counts = {
        "epics": sum(1 for i in items if i["type"] == "Epic"),
        "stories": sum(1 for i in items if i["type"] == "Story"),
        "tasks": sum(1 for i in items if i["type"] == "Task"),
        "subtasks": sum(1 for i in items if i["type"] == "Subtask"),
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
        "unassigned_refs": unassigned_children,
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
    lines.append(f"**{c['epics']} epic(s), {c['stories']} story(ies), "
                 f"{c['tasks']} task(s), {c['subtasks']} subtask(s)**"
                 + (f" · {c['unassigned']} unassigned" if c["unassigned"] else "")
                 + ". Review, then confirm to create.")
    lines.append("")

    by_ref = {i["ref"]: i for i in plan["items"]}
    epics = [i for i in plan["items"] if i["type"] == "Epic"]
    rendered_refs: set[str] = set()
    for epic in epics:
        rendered_refs.add(epic["ref"])
        lines.append(f"## {epic['summary']}")
        if epic["description"]:
            lines.append("")
            lines.append(epic["description"])
        for child_ref in epic.get("children", []):
            child = by_ref.get(child_ref)
            if not child:
                continue
            rendered_refs.add(child["ref"])
            lines.append("")
            lines.append(f"- **[{child['type']}] {child['summary']}**")
            if child.get("implements"):
                lines.append(f"  - implements: {', '.join(child['implements'])}")
            if child.get("story_ref"):
                lines.append(f"  - logical story: {child['story_ref']}")
            if child["description"]:
                snippet = " ".join(child["description"].split())
                if len(snippet) > 240:
                    snippet = snippet[:237] + "…"
                lines.append(f"  - {snippet}")
            for grandchild_ref in child.get("children", []):
                grandchild = by_ref.get(grandchild_ref)
                if not grandchild:
                    continue
                rendered_refs.add(grandchild["ref"])
                lines.append(f"  - **[{grandchild['type']}] {grandchild['summary']}**")
                if grandchild.get("implements"):
                    lines.append(f"    - implements: {', '.join(grandchild['implements'])}")
                if grandchild["description"]:
                    snippet = " ".join(grandchild["description"].split())
                    if len(snippet) > 200:
                        snippet = snippet[:197] + "…"
                    lines.append(f"    - {snippet}")
        lines.append("")
    unparented = [
        item for item in plan["items"]
        if item["ref"] not in rendered_refs and item["type"] != "Epic"
    ]
    if unparented:
        lines.append("## Unparented items")
        lines.append("")
        lines.append("These items have no valid declared Product Epic parent in the approved PRD/TRD.")
        for item in unparented:
            lines.append("")
            lines.append(f"- **[{item['type']}] {item['summary']}**")
            if item.get("implements"):
                lines.append(f"  - implements: {', '.join(item['implements'])}")
            if item.get("story_ref"):
                lines.append(f"  - logical story: {item['story_ref']}")
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
    print(f"  {c['epics']} epic(s), {c['stories']} story(ies), "
          f"{c['tasks']} task(s), {c['subtasks']} subtask(s)"
          + (f", {c['unassigned']} unparented/unassigned" if c["unassigned"] else "") + ".")


# --- export (offline CSV) --------------------------------------------------------

CSV_BASENAME = "jira-import"
# Jira's CSV importer links a child to a parent created in the *same* file by
# matching the child's `Parent Id` to the parent's `Issue Id` — plain integers we
# assign here, unrelated to any Jira key. `Labels` appears twice on purpose: the
# importer maps repeated columns onto a multi-value field, which is how a ticket
# gets both the `pm-os` marker and its own stable-id label.
CSV_COLUMNS = [
    "Issue Id", "Parent Id", "Issue Type", "Summary", "Description",
    "Labels", "Labels", "PM-OS Id",
]


def _label_for(ref: str) -> str:
    """The per-ticket label that carries the PM-OS stable id into Jira (`pm-os-us-001`),
    so the created keys can be recovered from a Jira export and fed back to `record`."""
    return f"pm-os-{ref.lower()}"


def _csv_description(item: dict) -> str:
    """The ticket body in Jira wiki markup, with a provenance footer naming the
    canonical artifact. Keeps the ticket honest about where it came from — the
    artifact is the source of truth, not the ticket."""
    parts = [to_jira_markup(item.get("description") or "").strip()]
    if item.get("implements"):
        parts.append("*Implements:* " + ", ".join(item["implements"]))
    source = item.get("source") or "the approved PM-OS pipeline"
    parts.append(
        f"----\n_Generated by PM-OS from {source}. "
        f"Canonical source is the PM-OS artifact — edit there and re-export, not here._"
    )
    return "\n\n".join(part for part in parts if part)


def build_csv_rows(plan: dict) -> list[dict]:
    """Flatten the plan into importer rows, parents first.

    Mirrors the MCP path's ownership rules exactly so the two routes create the same
    shape: Epic first, standard work items next (Stories/Tasks), then Subtasks so
    every `Parent Id` points to an issue already present in the same file.
    """
    items = plan["items"]
    ordered = (
        [i for i in items if i["type"] == "Epic"]
        + [i for i in items if i["type"] in ("Story", "Task")]
        + [i for i in items if i["type"] == "Subtask"]
    )
    issue_ids = {item["ref"]: index for index, item in enumerate(ordered, start=1)}

    rows: list[dict] = []
    for item in ordered:
        parent_ref = item.get("parent_ref")
        rows.append({
            "Issue Id": issue_ids[item["ref"]],
            "Parent Id": issue_ids.get(parent_ref, "") if parent_ref else "",
            "Issue Type": item["type"],
            "Summary": item["summary"],
            "Description": _csv_description(item),
            "Labels": ["pm-os", _label_for(item["ref"])],
            "PM-OS Id": item["ref"],
        })
    return rows


def _write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_COLUMNS)
        for row in rows:
            labels = row["Labels"]
            writer.writerow([
                row["Issue Id"], row["Parent Id"], row["Issue Type"], row["Summary"],
                row["Description"], labels[0], labels[1], row["PM-OS Id"],
            ])


def _render_import_guide(plan: dict, rows: list[dict], csv_name: str) -> str:
    unassigned = plan["counts"].get("unassigned") or 0
    lines = [
        f"# Importing {plan['project_name']} into Jira (offline)",
        "",
        f"> Generated {plan['generated_at']} from {plan['source_stamps']['prd']}"
        + (f", {plan['source_stamps']['trd']}" if plan["source_stamps"]["trd"] else "")
        + f". {len(rows)} issue(s) in `{csv_name}`.",
        "",
        "Use this when the Atlassian connector is not authorized for your session.",
        "Nothing here touches Jira — you run the import yourself.",
        "",
        "## 1. Import",
        "",
        "In Jira: **Settings → System → External System Import → CSV**, or a project's",
        f"**Issues → Import issues from CSV**. Upload `{csv_name}` and pick the target project.",
        "",
        "## 2. Map the fields",
        "",
        "| CSV column | Map to | Note |",
        "|---|---|---|",
        "| `Issue Id` | Issue Id | Required for parent linking; not a Jira key |",
        "| `Parent Id` | Parent Id | Links each story/task to its epic **inside this file** — map it or the hierarchy is lost |",
        "| `Issue Type` | Issue Type | `Epic` / `Story` / `Task` / `Subtask` — rename to match your project's scheme if it differs (for example `Sub-task`) |",
        "| `Summary` | Summary | |",
        "| `Description` | Description | Already Jira wiki markup |",
        "| `Labels` (both columns) | Labels | Two columns on purpose — Jira reads repeated columns as multiple values |",
        "| `PM-OS Id` | *(skip, or a custom field)* | The stable id; also carried as a `pm-os-<id>` label |",
        "",
        "## 3. Record the keys back into PM-OS",
        "",
        "After the import, get the created keys (a Jira issue search on the `pm-os` label,",
        "exported to CSV, gives you `Issue key` + `Labels`), then map each `pm-os-<id>`",
        "label back to its stable id and record them:",
        "",
        "```bash",
        'echo \'{"US-001":"RA-1","FR-001":"RA-2"}\' \\',
        "  | python3 ~/.pm-os/scripts/pm_handoff.py record",
        "```",
        "",
        "That writes each key into `.traceability.yaml` and logs the export event — the",
        "same step the connector path runs, so the two routes end in the same state.",
        "",
        "## Notes",
        "",
        "- **Re-importing creates duplicates.** Jira does not match on `PM-OS Id`; check",
        "  `.traceability.yaml` for already-recorded tickets before a second import.",
        "- **Derived, not canonical.** Regenerated on each run — never hand-edit it. Change",
        "  content by editing the approved stage artifact and re-exporting.",
    ]
    if unassigned:
        lines += [
            f"- **{unassigned} item(s) have no valid Product Epic parent.** They are",
            "  exported without a parent and should be reviewed for missing PRD/TRD ownership.",
        ]
    return "\n".join(lines) + "\n"


def cmd_export(root: Path, output: str | None, fmt: str) -> None:
    if fmt != "csv":
        raise SystemExit(f"Error: unsupported export format '{fmt}'. Only 'csv' is supported.")
    plan = build_plan(root)
    rows = build_csv_rows(plan)
    out_dir = _resolve_out_dir(root, output)
    csv_path = out_dir / f"{CSV_BASENAME}.csv"
    guide_path = out_dir / f"{CSV_BASENAME}-README.md"
    _write_csv(csv_path, rows)
    guide_path.write_text(_render_import_guide(plan, rows, csv_path.name), encoding="utf-8")

    c = plan["counts"]
    print("Jira CSV export written (offline — nothing created in Jira):")
    print(
        f"  {csv_path}   ({len(rows)} issue(s): {c['epics']} epic, "
        f"{c['stories']} story, {c['tasks']} task, {c['subtasks']} subtask)"
    )
    print(f"  {guide_path}   (import + field-mapping guide)")
    if c["unassigned"]:
        print(f"  Note: {c['unassigned']} item(s) have no valid Product Epic parent — review ownership.")
    print("Import it via Jira's CSV importer, then record the created keys with "
          "`pm_handoff.py record`.")


# --- record --------------------------------------------------------------------

# The id shapes the record step accepts, routed to the right index slot.
_EPIC_REF_RE = re.compile(r"^EPIC-\d{2,}$", re.IGNORECASE)
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
    epics = index.setdefault("epics", {})
    legacy_epics = index.setdefault("legacy_handoff_epics", {})
    old_handoff_epics = index.get("handoff_epics") or {}
    requirements = index.setdefault("requirements", {})
    tasks = index.setdefault("tasks", {})

    recorded: dict[str, str] = {}
    skipped: list[str] = []
    for ref, key in created.items():
        if ref == "UNASSIGNED":
            continue
        if _EPIC_REF_RE.match(ref):
            entry = epics.get(ref) or legacy_epics.get(ref) or old_handoff_epics.get(ref)
            slot = entry.setdefault("tickets", []) if entry is not None else None
        elif _REQ_REF_RE.match(ref):
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
    p_export = sub.add_parser("export", help="Render the plan as a Jira CSV-importer file (offline).")
    p_export.add_argument("--output", help="Output directory (default: ./handoff/).")
    p_export.add_argument("--format", default="csv", choices=["csv"], help="Export format (default: csv).")
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
    elif args.command == "export":
        cmd_export(root, args.output, args.format)
    elif args.command == "record":
        cmd_record(root, args.input)


if __name__ == "__main__":
    main()
