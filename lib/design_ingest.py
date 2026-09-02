"""Deterministic stage-04 ingest for external design-authority returns."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

import yaml

from artifact_contracts import information_architecture_section, split_screen_blocks
from design_input import (
    DesignFinding,
    design_error_count,
    load_design_input,
    state_node_url,
    validate_design_input,
)
from frontmatter import read as fm_read, write as fm_write
from hashing import hash_artifact_body
from project import artifact_path, get_stage, load_meta, save_meta


BRIEF_OWNED_SECTIONS = (
    "Input Behavior Reconciliation",
    "Product UX Guardrails",
    "Design Principles",
    "Responsive & Platform Behavior",
    "UX Content Rules",
    "Accessibility Notes",
)


@dataclass
class IngestResult:
    written: bool
    path: Path
    findings: list[DesignFinding]
    screen_ids: dict[str, str]


def ingest_design(project_root: Path) -> IngestResult:
    """Validate `design-in/` and rewrite stage 04 as an ingested draft.

    The operation is all-or-nothing for the stage artifact: validation errors
    return without touching `04-design-spec.md`.
    """
    project_root = Path(project_root)
    apath = artifact_path(project_root, "04")
    findings = validate_design_input(project_root)
    if design_error_count(findings):
        return IngestResult(False, apath, findings, {})
    if not apath.exists():
        return IngestResult(False, apath, [_finding("error", "DESIGN_BRIEF_MISSING", "04-design-spec.md does not exist.")], {})

    fm, brief_body = fm_read(str(apath))
    if _design_mode(fm, brief_body) != "brief":
        return IngestResult(False, apath, [_finding(
            "error",
            "DESIGN_BRIEF_MODE_INVALID",
            "Stage 04 must be a draft design brief (`design_mode: brief`) before ingest.",
        )], {})

    loaded = load_design_input(project_root / "design-in" / "ia.yaml")
    data = loaded.data
    screen_ids = assign_screen_ids(data, brief_body)
    body = render_ingested_design_spec(data, (project_root / "design-in" / "design-notes.md").read_text(encoding="utf-8"), brief_body, screen_ids)

    new_fm = dict(fm)
    figma = data.get("figma") or {}
    new_fm.update({
        "status": "draft",
        "approved_at": None,
        "approved_by": None,
        "content_hash": None,
        "design_mode": "ingested",
        "figma_file_key": figma.get("file_key"),
        "figma_file_url": figma.get("file_url"),
        "figma_version": figma.get("version"),
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    })
    notes = list(new_fm.get("generation_notes") or [])
    note = "Ingested external design-authority return from design-in/ia.yaml and design-in/design-notes.md."
    if note not in notes:
        notes.append(note)
    new_fm["generation_notes"] = notes

    fm_write(str(apath), new_fm, body)
    generated_hash = hash_artifact_body(str(apath))
    new_fm["generated_hash"] = generated_hash
    fm_write(str(apath), new_fm, body)
    _write_snapshot(project_root, apath)
    _update_meta(project_root, generated_hash)
    _log_ingest(project_root, data, generated_hash, len(findings), len(screen_ids))
    return IngestResult(True, apath, findings, screen_ids)


def assign_screen_ids(data: dict[str, Any], prior_body: str) -> dict[str, str]:
    """Return `{screen node_id: SCR-###}`, reusing prior ids by node id."""
    existing = _existing_screen_ids_by_node(prior_body)
    ordered = _screens_in_flow_order(data)
    used_ids = set(existing.values())
    next_num = _next_screen_number(used_ids)
    assigned: dict[str, str] = {}
    for screen in ordered:
        node_id = str(screen.get("node_id"))
        if node_id in existing:
            assigned[node_id] = existing[node_id]
            continue
        while f"SCR-{next_num:03d}" in used_ids:
            next_num += 1
        scr_id = f"SCR-{next_num:03d}"
        assigned[node_id] = scr_id
        used_ids.add(scr_id)
        next_num += 1
    return assigned


def render_ingested_design_spec(
    data: dict[str, Any],
    design_notes: str,
    brief_body: str,
    screen_ids: dict[str, str],
) -> str:
    figma = data.get("figma") or {}
    file_url = str(figma.get("file_url") or "")
    lines: list[str] = [
        "# Design Specification",
        "",
        "This design spec was ingested from the external design-authority return. PM-owned brief sections are preserved below; designer-owned IA, flow, component, token, and rationale sections are replaced from `design-in/`.",
        "",
        "## Design Provenance",
        "",
        f"- Figma file: {file_url or '— not captured —'}",
        f"- Figma file key: {figma.get('file_key') or '— not captured —'}",
        f"- Figma version: {figma.get('version') or '— not captured —'}",
        f"- Figma last modified: {figma.get('last_modified') or '— not captured —'}",
        f"- Design system: {', '.join(_string_list(figma.get('design_system'))) or '— not captured —'}",
        "",
        "## Information Architecture",
        "",
    ]
    screen_by_name = {str(screen.get("name")): screen for screen in data.get("screens") or [] if isinstance(screen, dict)}
    for screen in _screens_in_flow_order(data):
        name = str(screen.get("name"))
        scr_id = screen_ids[str(screen.get("node_id"))]
        serves = ", ".join(_string_list(screen.get("serves")))
        lines += [
            f"- **{scr_id} — {name}**",
            f"  - Purpose: {screen.get('purpose')}",
            f"  - Serves: {serves}",
            f"  - Node ID: {screen.get('node_id')}",
            f"  - Figma: {screen.get('node_url')}",
            f"  - Data fields: {', '.join(_string_list(screen.get('data_fields')))}",
            f"  - Components: {', '.join(_string_list(screen.get('components')))}",
            "  - States:",
        ]
        for state in screen.get("states") or []:
            if not isinstance(state, dict):
                continue
            url = state_node_url(file_url, str(state.get("node_id")), state.get("node_url"))
            transient = "transient" if state.get("transient") else "persistent"
            lines.append(
                f"    - State: {state.get('name')} — trigger: {state.get('trigger')} — {transient} — Figma: {url} — node_id: {state.get('node_id')}"
            )
        lines.append("")

    lines += ["## Journey-to-Flow Traceability", ""]
    for flow in data.get("flows") or []:
        if not isinstance(flow, dict):
            continue
        lines += [f"### {flow.get('journey')} — {flow.get('name') or flow.get('journey')}", ""]
        if flow.get("sequence"):
            lines.append("- Primary sequence:")
            for ref in flow.get("sequence") or []:
                lines.append(f"  - {_flow_ref(ref, screen_by_name, screen_ids, file_url)}")
        if flow.get("recovery"):
            lines.append("- Recovery/exception states:")
            for ref in flow.get("recovery") or []:
                lines.append(f"  - {_flow_ref(ref, screen_by_name, screen_ids, file_url)}")
        lines.append("")

    lines += ["## Key User Flows", "", "The canonical flow paths are listed in Journey-to-Flow Traceability above. Engineering should treat each referenced screen/state URL as the implementation target for that state.", ""]
    lines += _preserved_sections(brief_body)
    lines += _component_section(data)
    lines += _token_sections(data)
    lines += _excluded_frames_section(data)
    lines += ["## Designer Rationale", "", _strip_frontmatter(design_notes).strip() or "— not captured —", ""]
    return "\n".join(lines).rstrip() + "\n"


def _finding(severity: str, code: str, message: str) -> DesignFinding:
    return DesignFinding(severity, code, message)


def _design_mode(fm: dict, body: str) -> str | None:
    if fm.get("design_mode"):
        return str(fm.get("design_mode"))
    if "This is a design brief, not a finished design spec" in (body or ""):
        return "brief"
    return None


def _existing_screen_ids_by_node(body: str) -> dict[str, str]:
    existing: dict[str, str] = {}
    for scr_id, block in split_screen_blocks(information_architecture_section(body or "")).items():
        match = re.search(r"\bNode ID:\s*`?([^`\n]+?)`?\s*$", block, re.IGNORECASE | re.MULTILINE)
        if match:
            existing[match.group(1).strip()] = scr_id
    return existing


def _next_screen_number(ids: set[str]) -> int:
    nums = [int(match.group(1)) for sid in ids if (match := re.match(r"SCR-(\d+)$", sid))]
    return (max(nums) + 1) if nums else 1


def _screens_in_flow_order(data: dict[str, Any]) -> list[dict[str, Any]]:
    screens = [item for item in data.get("screens") or [] if isinstance(item, dict)]
    by_name = {str(screen.get("name")): screen for screen in screens}
    ordered: list[dict[str, Any]] = []
    for flow in data.get("flows") or []:
        if not isinstance(flow, dict):
            continue
        for ref in list(flow.get("sequence") or []) + list(flow.get("recovery") or []):
            if not isinstance(ref, dict):
                continue
            screen = by_name.get(str(ref.get("screen")))
            if screen and screen not in ordered:
                ordered.append(screen)
    for screen in screens:
        if screen not in ordered:
            ordered.append(screen)
    return ordered


def _flow_ref(ref: dict, screen_by_name: dict[str, dict], screen_ids: dict[str, str], file_url: str) -> str:
    screen = screen_by_name.get(str(ref.get("screen"))) or {}
    scr_id = screen_ids.get(str(screen.get("node_id")), "SCR-???")
    state_name = str(ref.get("state") or "")
    state = next((s for s in screen.get("states") or [] if isinstance(s, dict) and str(s.get("name")) == state_name), {})
    url = state_node_url(file_url, str(state.get("node_id") or screen.get("node_id") or ""), state.get("node_url") or screen.get("node_url"))
    note = f" — {ref.get('note')}" if ref.get("note") else ""
    return f"{scr_id} / {ref.get('screen')} / State: {state_name} — trigger: {state.get('trigger') or '— not captured —'} — Figma: {url}{note}"


def _preserved_sections(brief_body: str) -> list[str]:
    lines: list[str] = []
    for title in BRIEF_OWNED_SECTIONS:
        section = _section_with_heading(brief_body, title).strip()
        if section:
            lines += [section, ""]
    return lines


def _section_with_heading(markdown: str, title: str) -> str:
    match = re.search(rf"^##\s+{re.escape(title)}\s*$", markdown or "", re.IGNORECASE | re.MULTILINE)
    if not match:
        return ""
    next_match = re.search(r"^##\s+", markdown[match.end():], re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(markdown)
    return markdown[match.start():end].strip()


def _component_section(data: dict[str, Any]) -> list[str]:
    components = data.get("components") or {}
    lines = ["## Component Inventory", "", "### Reused design-system components", ""]
    reused = _string_list(components.get("reused"))
    lines += [f"- {name}" for name in reused] or ["— not captured —"]
    lines += ["", "### New or composed components", ""]
    new = [item for item in components.get("new") or [] if isinstance(item, dict)]
    if not new:
        lines.append("— none —")
    for comp in new:
        lines += [
            f"- **{comp.get('name')}**",
            f"  - Node ID: {comp.get('node_id') or '— not captured —'}",
            f"  - Rationale: {str(comp.get('rationale') or '').strip()}",
        ]
    lines.append("")
    return lines


def _token_sections(data: dict[str, Any]) -> list[str]:
    tokens = data.get("tokens") or {}
    lines = [
        "## Typography",
        "",
        "Use typography from the declared design-system collections; no product-specific type scale is introduced here.",
        "",
        "## Color Tokens",
        "",
        f"Collections used: {', '.join(_string_list(tokens.get('collections_used'))) or '— not captured —'}.",
        "",
        "## Spacing Tokens",
        "",
        "Use spacing from the declared design-system collections; no product-specific spacing scale is introduced here.",
        "",
        "## Iconography",
        "",
        "Use iconography from the declared design-system/library components unless an approved component rationale says otherwise.",
        "",
        "## Token Exceptions",
        "",
    ]
    outside = tokens.get("outside_system") or []
    if not outside:
        lines.append("— none —")
    for entry in outside:
        if isinstance(entry, dict):
            lines.append(f"- {entry.get('name') or entry.get('token') or 'Token exception'} — {entry.get('rationale') or entry.get('reason') or entry.get('justification')}")
        else:
            lines.append(f"- {entry}")
    lines.append("")
    return lines


def _excluded_frames_section(data: dict[str, Any]) -> list[str]:
    lines = ["## Excluded Frames", ""]
    frames = [item for item in data.get("excluded_frames") or [] if isinstance(item, dict)]
    if not frames:
        lines.append("— none —")
    for frame in frames:
        lines.append(f"- {frame.get('name')} (`{frame.get('node_id')}`) — {frame.get('reason')}")
    if data.get("open_questions"):
        lines += ["", "## Open Questions", ""]
        lines += [f"- {str(q).strip()}" for q in data.get("open_questions") or []]
    lines.append("")
    return lines


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 4)
    return text[end + 5:] if end != -1 else text


def _write_snapshot(project_root: Path, apath: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    hist = project_root / ".history"
    hist.mkdir(exist_ok=True)
    dest = hist / f"{apath.stem}.{stamp}.generated.md"
    suffix = 1
    while dest.exists():
        dest = hist / f"{apath.stem}.{stamp}.{suffix}.generated.md"
        suffix += 1
    dest.write_text(apath.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


def _update_meta(project_root: Path, generated_hash: str) -> None:
    meta = load_meta(project_root)
    stage = get_stage(meta, "04")
    stage["status"] = "draft"
    stage["content_hash"] = None
    stage["approved_at"] = None
    stage["upstream_hashes_at_approval"] = {}
    stage["generated_hash"] = generated_hash
    stage["origin"] = "generated"
    stage["regeneration_count"] = int(stage.get("regeneration_count") or 0) + 1
    save_meta(meta, project_root)


def _log_ingest(project_root: Path, data: dict[str, Any], generated_hash: str, finding_count: int, screen_count: int) -> None:
    try:
        from config import model_tier_for_stage
        from telemetry import log
    except Exception:
        return
    log("stage_generated", project_root, "04", {
        "generated_hash": generated_hash,
        "model": "deterministic-design-ingest",
        "model_tier": model_tier_for_stage("04"),
        "prompt_version": None,
        "notes": ["external design-authority ingest"],
        "design_mode": "ingested",
        "figma_file_key": (data.get("figma") or {}).get("file_key"),
        "figma_version": (data.get("figma") or {}).get("version"),
        "validation_findings": finding_count,
        "screens": screen_count,
    })
