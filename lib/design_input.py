"""Read-only parser and validator for external design-authority returns.

The designer returns `design-in/ia.yaml` and `design-in/design-notes.md`.
PM-OS validates the YAML structure and reconciles it against the approved PRD
and the stage-04 brief before an ingest run may write the canonical design spec.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

import yaml

from artifact_contracts import (
    JOURNEY_ID_RE,
    USER_STORY_ID_RE,
    information_architecture_section,
    requirement_ids,
    screen_serves,
    split_screen_blocks,
)
from delivery_map import build_prd_delivery_map
from frontmatter import read as fm_read
from project import artifact_path, get_stage, load_meta


SUPPORTED_IA_FORMAT_VERSION = 1
PENDING_DESIGN_INPUT_MARKER = "Pending external design input"


@dataclass(frozen=True)
class DesignFinding:
    severity: str  # "error" | "warning" | "info"
    code: str
    message: str
    location: str | None = None


@dataclass
class DesignInput:
    path: Path
    data: dict[str, Any]
    findings: list[DesignFinding] = field(default_factory=list)


def _finding(severity: str, code: str, message: str, location: str | None = None) -> DesignFinding:
    return DesignFinding(severity, code, message, location)


def design_error_count(findings: list[DesignFinding]) -> int:
    return sum(1 for finding in findings if finding.severity == "error")


def format_design_findings(findings: list[DesignFinding]) -> str:
    if not findings:
        return "No design input issues found."
    lines: list[str] = []
    for finding in findings:
        loc = f" [{finding.location}]" if finding.location else ""
        lines.append(f"- {finding.severity.upper()} {finding.code}{loc}: {finding.message}")
    return "\n".join(lines)


def load_design_input(path: Path) -> DesignInput:
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return DesignInput(path, {}, [_finding("error", "DESIGN_INPUT_MISSING", f"{path} does not exist.")])
    except OSError as exc:
        return DesignInput(path, {}, [_finding("error", "DESIGN_INPUT_UNREADABLE", f"Could not read {path}: {exc}")])

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        return DesignInput(path, {}, [_finding("error", "DESIGN_INPUT_YAML_INVALID", f"Malformed YAML: {exc}")])

    if not isinstance(data, dict):
        return DesignInput(path, {}, [_finding("error", "DESIGN_INPUT_ROOT_INVALID", "ia.yaml must contain a mapping at the root.")])
    return DesignInput(path, data, [])


def validate_design_input(project_root: Path) -> list[DesignFinding]:
    project_root = Path(project_root)
    design_dir = project_root / "design-in"
    loaded = load_design_input(design_dir / "ia.yaml")
    findings = list(loaded.findings)
    notes = design_dir / "design-notes.md"
    if not notes.exists():
        findings.append(_finding("error", "DESIGN_NOTES_MISSING", "design-in/design-notes.md does not exist.", "design-in/design-notes.md"))
    if design_error_count(findings):
        return findings

    prd_body = _artifact_body(project_root, "03")
    brief_body = _artifact_body(project_root, "04")
    findings.extend(validate_design_data(loaded.data, prd_body=prd_body, brief_body=brief_body))
    return findings


def validate_handoff_design(project_root: Path) -> list[DesignFinding]:
    """Verify post-pilot handoff-readiness from canonical artifacts.

    Generated `handoff/` folders are checked only when present; the authoritative
    screen/story coverage is always derived from approved PRD + approved design
    spec bodies.
    """
    project_root = Path(project_root)
    findings: list[DesignFinding] = []
    try:
        meta = load_meta(project_root)
        design_status = get_stage(meta, "04").get("status")
    except Exception:
        design_status = None
    if design_status != "approved":
        findings.append(_finding("info", "DESIGN_HANDOFF_NO_APPROVED_SPEC", "No approved stage-04 design spec; handoff design readiness checks are informational until stage 04 is approved."))
        return findings

    prd_body = _artifact_body(project_root, "03")
    design_body = _artifact_body(project_root, "04")
    if not prd_body or not design_body:
        findings.append(_finding("error", "DESIGN_HANDOFF_ARTIFACT_MISSING", "Approved PRD and design spec are required for design handoff verification."))
        return findings

    import traceability

    delivery = build_prd_delivery_map(prd_body)
    spine = traceability.build_index(project_root)
    screen_blocks = split_screen_blocks(information_architecture_section(design_body))
    story_to_screens: dict[str, list[str]] = {}
    screenless = _screenless_story_ids(design_body)

    for story_id in delivery.story_blocks:
        if story_id in screenless:
            continue
        refs = delivery.story_requirements.get(story_id, [story_id])
        journeys = delivery.story_journeys.get(story_id, [])
        screens: list[str] = []
        for ref in refs:
            for scr in traceability.screens_for_requirement(project_root, ref, index=spine):
                if scr not in screens:
                    screens.append(scr)
        for journey in journeys:
            for scr in traceability.screens_for_requirement(project_root, journey, index=spine):
                if scr not in screens:
                    screens.append(scr)
        story_to_screens[story_id] = screens
        if not screens:
            findings.append(_finding("error", "DESIGN_HANDOFF_STORY_SCREEN_MISSING", f"No approved screen serves {story_id}."))

    known_ids = _known_prd_ids(prd_body)
    for scr_id, block in screen_blocks.items():
        serves = screen_serves(block)
        if not serves or not any(ref.upper() in known_ids for ref in serves):
            findings.append(_finding("error", "DESIGN_HANDOFF_SCREEN_ORPHANED", f"{scr_id} does not serve a known story, requirement, or journey."))
        refs = traceability.design_refs(block)
        if not any(ref.get("kind") == "screen" and ref.get("url") for ref in refs):
            findings.append(_finding("error", "DESIGN_HANDOFF_SCREEN_FIGMA_MISSING", f"{scr_id} has no default Figma link."))
        _validate_state_link_lines(scr_id, block, findings)

    _validate_generated_story_join(project_root, story_to_screens, findings)
    if not (project_root / "05-prototype-mockup.html").exists():
        findings.append(_finding("info", "DESIGN_HANDOFF_PROTOTYPE_HTML_MISSING", "No stage-05 prototype HTML found; Figma links remain the source for screen/state handoff."))
    return findings


def validate_design_data(
    data: dict[str, Any],
    *,
    prd_body: str | None = None,
    brief_body: str | None = None,
) -> list[DesignFinding]:
    findings: list[DesignFinding] = []
    _validate_schema(data, findings)
    if design_error_count(findings):
        return findings

    screens = _screens(data)
    flows = _flows(data)
    screen_by_name = {str(screen.get("name")): screen for screen in screens}
    state_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    screen_node_ids: list[str] = []
    screen_node_owner: dict[str, str] = {}
    state_nodes: list[tuple[str, str, str]] = []

    for screen in screens:
        screen_name = str(screen.get("name"))
        node_id = str(screen.get("node_id"))
        screen_node_ids.append(node_id)
        screen_node_owner[node_id] = screen_name
        for state in _states(screen):
            state_name = str(state.get("name"))
            state_node_id = str(state.get("node_id"))
            state_by_pair[(screen_name, state_name)] = state
            state_nodes.append((state_node_id, screen_name, state_name))

    duplicates = sorted({node_id for node_id in screen_node_ids if screen_node_ids.count(node_id) > 1})
    state_node_ids = [node_id for node_id, _screen, _state in state_nodes]
    duplicates.extend(
        sorted({node_id for node_id in state_node_ids if state_node_ids.count(node_id) > 1})
    )
    for node_id, screen_name, state_name in state_nodes:
        if node_id in screen_node_owner and (
            screen_node_owner[node_id] != screen_name or _norm_state(state_name) != "default"
        ):
            duplicates.append(node_id)
    duplicates = sorted(set(duplicates))
    if duplicates:
        findings.append(_finding("error", "DESIGN_NODE_ID_DUPLICATE", "Duplicate Figma node_id values: " + ", ".join(duplicates)))

    for flow in flows:
        for ref in list(flow.get("sequence") or []) + list(flow.get("recovery") or []):
            if not isinstance(ref, dict):
                findings.append(_finding("error", "DESIGN_FLOW_REF_INVALID", "Flow sequence/recovery entries must be mappings."))
                continue
            screen_name = str(ref.get("screen", ""))
            state_name = str(ref.get("state", ""))
            if screen_name not in screen_by_name:
                findings.append(_finding("error", "DESIGN_FLOW_SCREEN_UNKNOWN", f"Flow references unknown screen `{screen_name}`."))
            elif (screen_name, state_name) not in state_by_pair:
                findings.append(_finding("error", "DESIGN_FLOW_STATE_UNKNOWN", f"Flow references unknown state `{screen_name}/{state_name}`."))

    prd_ids = _known_prd_ids(prd_body or "")
    if prd_ids:
        for screen in screens:
            bad = [ref for ref in _string_list(screen.get("serves")) if ref.upper() not in prd_ids]
            if bad:
                findings.append(_finding("error", "DESIGN_SERVES_UNKNOWN_ID", f"{screen.get('name')} serves unknown PRD ids: {', '.join(bad)}."))

        flow_journeys = {str(flow.get("journey", "")).upper() for flow in flows if flow.get("journey")}
        missing_flows = sorted(ref for ref in prd_ids if ref.startswith("UJ-") and ref not in flow_journeys)
        if missing_flows:
            findings.append(_finding("error", "DESIGN_JOURNEY_FLOW_MISSING", "No returned flow for PRD journeys: " + ", ".join(missing_flows)))

        _validate_story_screen_coverage(prd_body or "", screens, findings, brief_body or "")
        _validate_field_coverage(brief_body or "", screens, findings)

    _validate_required_state_inventory(brief_body or "", state_by_pair, findings)
    _validate_tokens(data, findings)
    _validate_components(data, findings)
    _validate_excluded_frames(data, flows, findings)

    for index, question in enumerate(data.get("open_questions") or [], start=1):
        findings.append(_finding("warning", "DESIGN_OPEN_QUESTION", str(question).strip(), f"open_questions[{index}]"))

    return findings


def state_node_url(figma_file_url: str, node_id: str, explicit_url: str | None = None) -> str:
    if explicit_url:
        return explicit_url
    sep = "&" if "?" in figma_file_url else "?"
    return f"{figma_file_url}{sep}node-id={node_id.replace(':', '-')}"


def _artifact_body(project_root: Path, stage_id: str) -> str:
    path = artifact_path(project_root, stage_id)
    if not path.exists():
        return ""
    try:
        _fm, body = fm_read(str(path))
    except Exception:
        return ""
    return body or ""


def _validate_schema(data: dict[str, Any], findings: list[DesignFinding]) -> None:
    if data.get("ia_format_version") != SUPPORTED_IA_FORMAT_VERSION:
        findings.append(_finding(
            "error", "DESIGN_INPUT_VERSION_UNSUPPORTED",
            f"ia_format_version must be {SUPPORTED_IA_FORMAT_VERSION}.",
            "ia_format_version",
        ))
    figma = data.get("figma")
    if not isinstance(figma, dict):
        findings.append(_finding("error", "DESIGN_FIGMA_MISSING", "figma must be a mapping.", "figma"))
    else:
        for key in ("file_key", "file_url", "version"):
            if not figma.get(key):
                findings.append(_finding("error", "DESIGN_FIGMA_FIELD_MISSING", f"figma.{key} is required.", f"figma.{key}"))
        design_system = figma.get("design_system")
        if not _string_list(design_system):
            findings.append(_finding("error", "DESIGN_SYSTEM_MISSING", "figma.design_system must list the design-system collections.", "figma.design_system"))

    if not _screens(data):
        findings.append(_finding("error", "DESIGN_SCREENS_MISSING", "screens must contain at least one screen.", "screens"))
    for index, screen in enumerate(data.get("screens") or [], start=1):
        loc = f"screens[{index}]"
        if not isinstance(screen, dict):
            findings.append(_finding("error", "DESIGN_SCREEN_INVALID", "Each screen must be a mapping.", loc))
            continue
        for key in ("name", "node_id", "node_url", "purpose", "serves", "data_fields", "components", "states"):
            if not screen.get(key):
                findings.append(_finding("error", "DESIGN_SCREEN_FIELD_MISSING", f"Screen is missing `{key}`.", f"{loc}.{key}"))
        for state_index, state in enumerate(screen.get("states") or [], start=1):
            state_loc = f"{loc}.states[{state_index}]"
            if not isinstance(state, dict):
                findings.append(_finding("error", "DESIGN_STATE_INVALID", "Each state must be a mapping.", state_loc))
                continue
            for key in ("name", "node_id", "trigger", "transient"):
                if key not in state or state.get(key) in (None, ""):
                    findings.append(_finding("error", "DESIGN_STATE_FIELD_MISSING", f"State is missing `{key}`.", f"{state_loc}.{key}"))

    if not _flows(data):
        findings.append(_finding("error", "DESIGN_FLOWS_MISSING", "flows must contain at least one journey flow.", "flows"))
    for index, flow in enumerate(data.get("flows") or [], start=1):
        loc = f"flows[{index}]"
        if not isinstance(flow, dict):
            findings.append(_finding("error", "DESIGN_FLOW_INVALID", "Each flow must be a mapping.", loc))
            continue
        for key in ("journey", "sequence"):
            if not flow.get(key):
                findings.append(_finding("error", "DESIGN_FLOW_FIELD_MISSING", f"Flow is missing `{key}`.", f"{loc}.{key}"))

    components = data.get("components")
    if not isinstance(components, dict):
        findings.append(_finding("error", "DESIGN_COMPONENTS_MISSING", "components must be a mapping.", "components"))
    else:
        if "reused" not in components or "new" not in components:
            findings.append(_finding("error", "DESIGN_COMPONENT_LIST_MISSING", "components.reused and components.new are required.", "components"))

    tokens = data.get("tokens")
    if not isinstance(tokens, dict):
        findings.append(_finding("error", "DESIGN_TOKENS_MISSING", "tokens must be a mapping.", "tokens"))
    else:
        if not tokens.get("collections_used"):
            findings.append(_finding("error", "DESIGN_TOKEN_COLLECTIONS_MISSING", "tokens.collections_used is required.", "tokens.collections_used"))
        if "outside_system" not in tokens:
            findings.append(_finding("error", "DESIGN_OUTSIDE_SYSTEM_MISSING", "tokens.outside_system is required.", "tokens.outside_system"))

    if "excluded_frames" not in data:
        findings.append(_finding("error", "DESIGN_EXCLUDED_FRAMES_MISSING", "excluded_frames is required, even when empty.", "excluded_frames"))


def _validate_story_screen_coverage(
    prd_body: str,
    screens: list[dict[str, Any]],
    findings: list[DesignFinding],
    brief_body: str,
) -> None:
    delivery = build_prd_delivery_map(prd_body)
    screenless = _screenless_story_ids(brief_body)
    for story_id in delivery.story_blocks:
        if story_id in screenless:
            continue
        reqs = set(delivery.story_requirements.get(story_id, [story_id]))
        journeys = set(delivery.story_journeys.get(story_id, []))
        covered = False
        for screen in screens:
            serves = {ref.upper() for ref in _string_list(screen.get("serves"))}
            if story_id in serves or reqs & serves or journeys & serves:
                covered = True
                break
        if not covered:
            findings.append(_finding("error", "DESIGN_STORY_SCREEN_MISSING", f"No returned screen serves {story_id}."))


def _validate_required_state_inventory(
    brief_body: str,
    state_by_pair: dict[tuple[str, str], dict[str, Any]],
    findings: list[DesignFinding],
) -> None:
    for state_name in _required_state_names(brief_body):
        if not any(_required_state_matches(state_name, screen, name) for screen, name in state_by_pair):
            findings.append(_finding("error", "DESIGN_REQUIRED_STATE_MISSING", f"Required state not returned: {state_name}."))


def _validate_field_coverage(brief_body: str, screens: list[dict[str, Any]], findings: list[DesignFinding]) -> None:
    required = _fields_per_requirement(brief_body)
    if not required:
        return
    for req_id, fields in required.items():
        serving_screens = [
            screen for screen in screens
            if req_id.upper() in {ref.upper() for ref in _string_list(screen.get("serves"))}
        ]
        available = {
            str(field).strip().lower()
            for screen in serving_screens
            for field in _string_list(screen.get("data_fields"))
        }
        missing = sorted(field for field in fields if field.lower() not in available)
        if missing:
            findings.append(_finding(
                "error", "DESIGN_FIELD_COVERAGE_MISSING",
                f"{req_id} fields missing from screens that serve it: {', '.join(missing)}.",
            ))


def _validate_tokens(data: dict[str, Any], findings: list[DesignFinding]) -> None:
    outside = ((data.get("tokens") or {}).get("outside_system") or [])
    for index, entry in enumerate(outside, start=1):
        if isinstance(entry, dict):
            reason = entry.get("rationale") or entry.get("reason") or entry.get("justification")
            if reason:
                continue
        findings.append(_finding(
            "error", "DESIGN_TOKEN_OUTSIDE_SYSTEM_UNJUSTIFIED",
            "Every tokens.outside_system entry must include a rationale/reason/justification.",
            f"tokens.outside_system[{index}]",
        ))


def _validate_components(data: dict[str, Any], findings: list[DesignFinding]) -> None:
    for index, component in enumerate(((data.get("components") or {}).get("new") or []), start=1):
        if not isinstance(component, dict):
            findings.append(_finding("error", "DESIGN_NEW_COMPONENT_INVALID", "New components must be mappings.", f"components.new[{index}]"))
            continue
        if not component.get("name") or not component.get("rationale"):
            findings.append(_finding(
                "error", "DESIGN_NEW_COMPONENT_RATIONALE_MISSING",
                "Every new component must include name and rationale.",
                f"components.new[{index}]",
            ))


def _validate_excluded_frames(data: dict[str, Any], flows: list[dict[str, Any]], findings: list[DesignFinding]) -> None:
    excluded_names = {str(entry.get("name")) for entry in data.get("excluded_frames") or [] if isinstance(entry, dict)}
    excluded_nodes = {str(entry.get("node_id")) for entry in data.get("excluded_frames") or [] if isinstance(entry, dict)}
    for flow in flows:
        for ref in list(flow.get("sequence") or []) + list(flow.get("recovery") or []):
            if not isinstance(ref, dict):
                continue
            if str(ref.get("screen")) in excluded_names or str(ref.get("node_id")) in excluded_nodes:
                findings.append(_finding("error", "DESIGN_EXCLUDED_FRAME_USED", f"Flow uses excluded frame `{ref}`."))


def _known_prd_ids(prd_body: str) -> set[str]:
    ids = set(requirement_ids(prd_body))
    ids.update(match.upper() for match in JOURNEY_ID_RE.findall(prd_body or ""))
    ids.update(match.upper() for match in USER_STORY_ID_RE.findall(prd_body or ""))
    return ids


def _screens(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in data.get("screens") or [] if isinstance(item, dict)]


def _flows(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in data.get("flows") or [] if isinstance(item, dict)]


def _states(screen: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in screen.get("states") or [] if isinstance(item, dict)]


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _screenless_story_ids(brief_body: str) -> set[str]:
    ids: set[str] = set()
    for line in (brief_body or "").splitlines():
        if "screenless" not in line.lower():
            continue
        ids.update(match.upper() for match in USER_STORY_ID_RE.findall(line))
    return ids


def _required_state_names(brief_body: str) -> list[str]:
    section = _subsection(brief_body, "Required state inventory")
    states: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "---" in stripped.lower() or "state" in stripped.lower() and "trigger" in stripped.lower():
            continue
        cells = [cell.strip().strip("*") for cell in stripped.strip("|").split("|")]
        if len(cells) >= 3 and cells[2]:
            states.append(cells[2])
    return list(dict.fromkeys(states))


def _fields_per_requirement(brief_body: str) -> dict[str, list[str]]:
    section = _subsection(brief_body, "Data fields per requirement")
    current_req: str | None = None
    fields: dict[str, list[str]] = {}
    for line in section.splitlines():
        req_match = re.search(r"\b(US|FR|REQ)-\d{3,}\b", line, re.IGNORECASE)
        if req_match and line.strip().startswith("**"):
            current_req = req_match.group(0).upper()
            fields.setdefault(current_req, [])
            continue
        stripped = line.strip()
        if not current_req or not stripped.startswith("|") or "---" in stripped.lower() or "field" in stripped.lower() and "type" in stripped.lower():
            continue
        cells = [cell.strip().strip("`") for cell in stripped.strip("|").split("|")]
        if cells and cells[0]:
            fields[current_req].append(cells[0])
    return {key: list(dict.fromkeys(value)) for key, value in fields.items()}


def _subsection(markdown: str, title: str) -> str:
    pattern = re.compile(rf"^###\s+{re.escape(title)}\s*$", re.IGNORECASE | re.MULTILINE)
    match = pattern.search(markdown or "")
    if not match:
        return ""
    next_heading = re.search(r"^#{1,3}\s+", (markdown or "")[match.end():], re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(markdown or "")
    return (markdown or "")[match.end():end]


def _norm_state(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _required_state_matches(required: str, screen_name: str, state_name: str) -> bool:
    required_norm = _norm_state(required)
    state_norm = _norm_state(state_name)
    screen_norm = _norm_state(screen_name)
    if required_norm == state_norm or required_norm == f"{screen_norm} {state_norm}":
        return True
    parts = re.split(r"\s+[—–-]\s+", required, maxsplit=1)
    if len(parts) != 2:
        return False
    required_screen = _norm_state(parts[0])
    required_state = _norm_state(parts[1])
    if required_state != state_norm:
        required_screen_tokens = set(required_screen.split())
        required_state_tokens = set(required_state.split())
        state_tokens = set(state_norm.split())
        combined_tokens = set(screen_norm.split()) | state_tokens
        return bool(required_screen_tokens & combined_tokens) and bool(required_state_tokens & state_tokens)
    required_words = set(required_screen.split())
    screen_words = set(screen_norm.split())
    return bool(required_words & screen_words)


def _validate_state_link_lines(scr_id: str, block: str, findings: list[DesignFinding]) -> None:
    for line in (block or "").splitlines():
        if not re.search(r"\bState\s*:", line, re.IGNORECASE):
            continue
        if not re.search(r"https://(?:www\.)?figma\.com/", line, re.IGNORECASE):
            findings.append(_finding("error", "DESIGN_HANDOFF_STATE_FIGMA_MISSING", f"{scr_id} state lacks a Figma link: {line.strip()}"))
        if not re.search(r"\btrigger\s*:", line, re.IGNORECASE):
            findings.append(_finding("error", "DESIGN_HANDOFF_STATE_TRIGGER_MISSING", f"{scr_id} state lacks a trigger: {line.strip()}"))


def _validate_generated_story_join(
    project_root: Path,
    story_to_screens: dict[str, list[str]],
    findings: list[DesignFinding],
) -> None:
    dev_dir = project_root / "handoff" / "dev" / "stories"
    qa_dir = project_root / "handoff" / "qa" / "stories"
    if not dev_dir.exists() or not qa_dir.exists():
        findings.append(_finding("info", "DESIGN_HANDOFF_PACKAGE_NOT_BUILT", "Build `/pm-handoff --package` to compare generated dev and QA story joins."))
        return
    for story_id, expected in story_to_screens.items():
        dev = _story_file_for(dev_dir, story_id)
        qa = _story_file_for(qa_dir, story_id)
        if not dev or not qa:
            findings.append(_finding("error", "DESIGN_HANDOFF_STORY_FILE_MISSING", f"Generated dev/QA story file missing for {story_id}."))
            continue
        dev_text = dev.read_text(encoding="utf-8")
        qa_text = qa.read_text(encoding="utf-8")
        dev_screens = _traceability_screens(dev_text)
        qa_screens = _traceability_screens(qa_text)
        expected_sorted = sorted(expected)
        if dev_screens != qa_screens or dev_screens != expected_sorted:
            findings.append(_finding(
                "error",
                "DESIGN_HANDOFF_STORY_JOIN_MISMATCH",
                f"{story_id} dev/QA generated screen joins differ from canonical coverage: dev={dev_screens}, qa={qa_screens}, expected={expected_sorted}.",
            ))

    screen_map = project_root / "handoff" / "qa" / "reference" / "screen-map.md"
    if screen_map.exists():
        text = screen_map.read_text(encoding="utf-8")
        uncovered_tail = text.split("## Stories with no screen", 1)[1] if "## Stories with no screen" in text else ""
        for story_id, screens in story_to_screens.items():
            if screens and story_id in uncovered_tail:
                findings.append(_finding("error", "DESIGN_HANDOFF_SCREEN_MAP_MISMATCH", f"{story_id} is canonically covered but appears under Stories with no screen."))
    else:
        findings.append(_finding("info", "DESIGN_HANDOFF_SCREEN_MAP_NOT_BUILT", "Build `/pm-handoff --package` to verify generated screen-map/story agreement."))


def _story_file_for(directory: Path, story_id: str) -> Path | None:
    matches = sorted(directory.glob(f"{story_id}-*.md"))
    return matches[0] if matches else None


def _traceability_screens(text: str) -> list[str]:
    match = re.search(r"^\- \*\*Screens:\*\*\s*(.+)$", text or "", re.MULTILINE)
    if not match or "not captured" in match.group(1):
        return []
    return sorted(re.findall(r"\bSCR-\d{3,}\b", match.group(1)))
