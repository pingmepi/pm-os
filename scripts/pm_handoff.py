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
    FUNCTIONAL_REQ_ID_RE,
    _sections,
    split_task_blocks,
    split_user_story_blocks,
    work_breakdown_section,
)
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
    shape: the synthetic ``UNASSIGNED`` epic is *not* emitted as a ticket, and its
    children are emitted parentless for the PM to place — rather than manufacturing
    an "Unassigned" epic in the PM's Jira.
    """
    items = [i for i in plan["items"] if i["ref"] != "UNASSIGNED"]
    # Epics first so a parent's Issue Id is always defined before a child cites it.
    ordered = [i for i in items if i["type"] == "Epic"] + [i for i in items if i["type"] != "Epic"]
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
        "| `Issue Type` | Issue Type | `Epic` / `Story` / `Task` — rename to match your project's scheme if it differs |",
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
            f"- **{unassigned} item(s) have no owning user story.** They are exported with no",
            "  `Parent Id` and will import as top-level issues. Fix ownership in the PRD and",
            "  re-export if you would rather they sat under an epic.",
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
    print(f"  {csv_path}   ({len(rows)} issue(s): {c['epics']} epic, {c['stories']} story, {c['tasks']} task)")
    print(f"  {guide_path}   (import + field-mapping guide)")
    if c["unassigned"]:
        print(f"  Note: {c['unassigned']} item(s) have no owning user story — exported without a parent.")
    print("Import it via Jira's CSV importer, then record the created keys with "
          "`pm_handoff.py record`.")


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
