"""Deterministic content contracts for PM-OS product artifacts.

The agent still owns product judgment. These checks catch structural omissions and
high-signal cross-stage drift before they disappear into an approved pipeline.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable

from frontmatter import read as fm_read
from project import artifact_path


CONTRACT_VERSION = 1

_VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}


class _ReviewOnlyStripper(HTMLParser):
    """Collect text and script/style data that lives outside any element marked
    ``class="review-only"``, tracking nesting so a reviewer block containing
    nested tags is removed in full (a regex with a single closing tag cannot)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._out: list[str] = []
        self._stack: list[bool] = []  # per open element: did it open a review-only region?
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _VOID_ELEMENTS:
            return
        classes = next((value for key, value in attrs if key == "class" and value), "")
        opens_review = "review-only" in classes.split()
        self._stack.append(opens_review)
        if opens_review:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if self._stack and self._stack.pop() and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._skip == 0:
            self._out.append(data)

    def result(self) -> str:
        return "".join(self._out)


def _strip_review_only(html: str) -> str:
    """Return the participant-facing text/script content of ``html`` with
    reviewer-only subtrees removed. Falls back to the raw source on parse error."""
    stripper = _ReviewOnlyStripper()
    try:
        stripper.feed(html)
        stripper.close()
    except Exception:
        return html
    return stripper.result()


@dataclass(frozen=True)
class Finding:
    severity: str  # ERROR | WARNING
    code: str
    message: str

    def as_dict(self) -> dict:
        return {"severity": self.severity, "code": self.code, "message": self.message}


REQUIRED_SECTIONS = {
    "03": [
        "Overview",
        "Goals and Non-Goals",
        "User Journeys",
        "User Stories with Acceptance Criteria",
        "Functional Requirements",
        "Non-Functional Requirements",
        "Data & Governance",
        "Edge Cases",
        "Risks",
    ],
    "04": [
        "Information Architecture",
        "Journey-to-Flow Traceability",
        "Key User Flows",
        "Product UX Guardrails",
        "Design Principles",
        "Component Inventory",
        "Typography",
        "Color Tokens",
        "Spacing Tokens",
        "Iconography",
        "Accessibility Notes",
    ],
    "05": [
        "What to Prototype",
        "Fidelity Level",
        "Prototype Audience & Modes",
        "Screens to Include",
        "Interactions to Demonstrate",
        "Questions the Prototype Should Answer",
        "Validation Plan",
        "Non-Goals for Prototype",
    ],
}

RECOMMENDED_SECTIONS = {
    "03": ["Journey-Requirement Traceability", "Assumptions & Open Decisions"],
    "04": ["Responsive & Platform Behavior", "UX Content Rules"],
    "05": ["Prototype Data & Scenarios", "Known Limitations"],
}

_ALIASES = {
    "journey-requirement traceability": {
        "journey-requirement traceability",
        "journey–requirement traceability",
        "journey to requirement traceability",
    },
}


def _norm(value: str) -> str:
    value = value.strip().lower().replace("—", "-").replace("–", "-")
    return re.sub(r"\s+", " ", value)


def _sections(body: str) -> dict[str, str]:
    found: dict[str, list[str]] = {}
    current = None
    for line in body.splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            current = _norm(match.group(1))
            found[current] = []
        elif current is not None:
            found[current].append(line)
    return {title: "\n".join(lines).strip() for title, lines in found.items()}


def _section(sections: dict[str, str], title: str) -> str | None:
    key = _norm(title)
    candidates = _ALIASES.get(key, {key})
    for candidate in candidates:
        normalized = _norm(candidate)
        if normalized in sections:
            return sections[normalized]
    return None


def _missing_sections(stage_id: str, sections: dict[str, str]) -> list[Finding]:
    findings: list[Finding] = []
    for title in REQUIRED_SECTIONS.get(stage_id, []):
        content = _section(sections, title)
        if content is None:
            findings.append(Finding("ERROR", "REQUIRED_SECTION_MISSING", f"Missing required section: {title}"))
        elif not content.strip():
            findings.append(Finding("ERROR", "REQUIRED_SECTION_EMPTY", f"Required section is empty: {title}"))
    for title in RECOMMENDED_SECTIONS.get(stage_id, []):
        content = _section(sections, title)
        if content is None:
            findings.append(Finding("WARNING", "RECOMMENDED_SECTION_MISSING", f"Missing recommended section: {title}"))
        elif not content.strip():
            findings.append(Finding("WARNING", "RECOMMENDED_SECTION_EMPTY", f"Recommended section is empty: {title}"))
    return findings


def _blocks(markdown: str, pattern: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(pattern, markdown, re.MULTILINE | re.IGNORECASE))
    result = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        result.append((match.group(1).upper(), markdown[match.end():end]))
    return result


def _validate_stage_03(sections: dict[str, str], body: str) -> list[Finding]:
    findings: list[Finding] = []
    journeys = _section(sections, "User Journeys") or ""
    journey_blocks = _blocks(journeys, r"^###\s+(UJ-\d{3})\b.*$")
    if not journey_blocks:
        findings.append(Finding("ERROR", "USER_JOURNEY_MISSING", "User Journeys must contain at least one UJ-### journey."))
    required_fields = [
        "primary user", "context and trigger", "goal", "preconditions", "happy path",
        "alternate/failure paths", "completion signal", "traceability",
    ]
    for journey_id, block in journey_blocks:
        normalized = _norm(block)
        missing = [field for field in required_fields if field not in normalized]
        if missing:
            findings.append(Finding(
                "ERROR", "USER_JOURNEY_FIELDS_MISSING",
                f"{journey_id} is missing fields: {', '.join(missing)}",
            ))
        if not re.search(r"\b(?:US|FR)-\d{3}\b", block, re.IGNORECASE):
            findings.append(Finding("ERROR", "USER_JOURNEY_TRACE_MISSING", f"{journey_id} does not reference a US-### or FR-### identifier."))

    stories = _section(sections, "User Stories with Acceptance Criteria") or ""
    if not re.search(r"\bUS-\d{3}\b", stories, re.IGNORECASE):
        findings.append(Finding("ERROR", "USER_STORY_IDS_MISSING", "User stories must use stable US-### identifiers."))
    requirements = _section(sections, "Functional Requirements") or ""
    if not re.search(r"\bFR-\d{3}\b", requirements, re.IGNORECASE):
        findings.append(Finding("ERROR", "FUNCTIONAL_REQUIREMENT_IDS_MISSING", "Functional requirements must use stable FR-### identifiers."))
    return findings


def _upstream_journey_ids(project_root: Path) -> set[str]:
    path = artifact_path(project_root, "03")
    if not path.exists():
        return set()
    try:
        _fm, body = fm_read(str(path))
    except Exception:
        return set()
    return {match.upper() for match in re.findall(r"\bUJ-\d{3}\b", body, re.IGNORECASE)}


def _validate_journey_references(project_root: Path, body: str, stage_id: str) -> list[Finding]:
    upstream = _upstream_journey_ids(project_root)
    if not upstream:
        return []
    present = {match.upper() for match in re.findall(r"\bUJ-\d{3}\b", body, re.IGNORECASE)}
    if stage_id == "05":
        if present & upstream:
            return []
        return [Finding(
            "ERROR", "PROTOTYPE_JOURNEY_TRACE_MISSING",
            "Prototype brief must reference at least one upstream UJ-### journey in its bounded slice.",
        )]
    missing = sorted(upstream - present)
    if not missing:
        return []
    return [Finding("WARNING", "JOURNEY_FLOW_TRACE_MISSING", f"Upstream journeys not referenced: {', '.join(missing)}")]


def _interaction_model(sections: dict[str, str]) -> str | None:
    guardrails = _section(sections, "Product UX Guardrails") or ""
    match = re.search(
        r"interaction\s+model\s*:\s*(retrieval-only|generative|mixed|non-ai)",
        guardrails,
        re.IGNORECASE,
    )
    return match.group(1).lower() if match else None


def _validate_stage_04(project_root: Path, sections: dict[str, str], body: str) -> list[Finding]:
    findings = _validate_journey_references(project_root, body, "04")
    if _interaction_model(sections) is None:
        findings.append(Finding(
            "ERROR", "INTERACTION_MODEL_MISSING",
            "Product UX Guardrails must declare Interaction model: retrieval-only | generative | mixed | non-AI.",
        ))
    return findings


def _validate_stage_05(project_root: Path, sections: dict[str, str], body: str) -> list[Finding]:
    findings = _validate_journey_references(project_root, body, "05")
    modes = _norm(_section(sections, "Prototype Audience & Modes") or "")
    for term in ("participant", "reviewer"):
        if term not in modes:
            findings.append(Finding("ERROR", "PROTOTYPE_MODE_INCOMPLETE", f"Prototype Audience & Modes must define {term} behavior."))
    if not any(term in modes for term in ("default", "primary", "initial", "unbiased", "standard")):
        findings.append(Finding(
            "ERROR", "PROTOTYPE_MODE_INCOMPLETE",
            "Prototype Audience & Modes must designate the default participant experience.",
        ))

    plan = _norm(_section(sections, "Validation Plan") or "")
    concepts = {
        "participants": ("participant", "audience"),
        "tasks": ("task", "scenario"),
        "comparator": ("comparator", "baseline", "current experience"),
        "measures": ("measure", "evidence", "metric"),
        "decision thresholds": ("threshold", "decision rule", "pass/fail"),
        "facilitator guidance": ("facilitator", "moderator"),
        "bias risks": ("bias", "priming"),
    }
    for label, terms in concepts.items():
        if not any(term in plan for term in terms):
            findings.append(Finding("ERROR", "VALIDATION_PLAN_INCOMPLETE", f"Validation Plan is missing {label}."))
    return findings


def validate_artifact(project_root: Path | str, stage_id: str, path: Path | str | None = None) -> list[Finding]:
    project_root = Path(project_root)
    stage_id = stage_id.zfill(2)
    if stage_id not in REQUIRED_SECTIONS:
        return []
    artifact = Path(path) if path else artifact_path(project_root, stage_id)
    if not artifact.exists():
        return [Finding("ERROR", "ARTIFACT_MISSING", f"Artifact not found: {artifact}")]
    try:
        fm, body = fm_read(str(artifact))
    except Exception as exc:
        return [Finding("ERROR", "ARTIFACT_UNREADABLE", f"Could not read artifact: {exc}")]

    findings: list[Finding] = []
    if fm.get("artifact_contract_version") != CONTRACT_VERSION:
        findings.append(Finding(
            "WARNING", "CONTRACT_VERSION_MISSING",
            f"Artifact does not declare artifact_contract_version: {CONTRACT_VERSION}.",
        ))
    sections = _sections(body)
    findings.extend(_missing_sections(stage_id, sections))
    if stage_id == "03":
        findings.extend(_validate_stage_03(sections, body))
    elif stage_id == "04":
        findings.extend(_validate_stage_04(project_root, sections, body))
    elif stage_id == "05":
        findings.extend(_validate_stage_05(project_root, sections, body))
    return findings


def validate_prototype_html(project_root: Path | str, path: Path | str | None = None) -> list[Finding]:
    project_root = Path(project_root)
    html_path = Path(path) if path else project_root / "05-prototype-mockup.html"
    if not html_path.exists():
        return [Finding("ERROR", "PROTOTYPE_HTML_MISSING", f"Prototype not found: {html_path}")]
    text = html_path.read_text(encoding="utf-8")
    findings: list[Finding] = []

    if re.search(r"<(?:script|link|img)[^>]+(?:src|href)=[\"']https?://", text, re.IGNORECASE):
        findings.append(Finding("ERROR", "EXTERNAL_PROTOTYPE_ASSET", "Prototype must be self-contained with no remote assets."))
    if not re.search(r"review=1|URLSearchParams[^\n]+review", text, re.IGNORECASE):
        findings.append(Finding("ERROR", "REVIEW_MODE_MISSING", "Prototype must expose reviewer chrome only through ?review=1."))
    if "review-only" not in text:
        findings.append(Finding("WARNING", "REVIEW_CHROME_NOT_SEPARATED", "Reviewer-only content is not marked separately from participant UI."))

    design_path = artifact_path(project_root, "04")
    model = None
    design_body = ""
    if design_path.exists():
        try:
            _fm, design_body = fm_read(str(design_path))
            model = _interaction_model(_sections(design_body))
        except Exception:
            pass
    if model == "retrieval-only":
        forbidden = {
            "RETRIEVAL_USES_GENERATING": r"\bgenerating\b",
            "RETRIEVAL_USES_STREAMING": r"setInterval\s*\(",
            "RETRIEVAL_USES_CONFIDENCE": r"\bconfidence\b",
            "RETRIEVAL_USES_OVERRIDE": r"\boverride\b",
            "RETRIEVAL_USES_EDIT_RESULT": r"\bedit result\b",
        }
        participant_text = _strip_review_only(text)
        for code, pattern in forbidden.items():
            if re.search(pattern, participant_text, re.IGNORECASE):
                findings.append(Finding("WARNING", code, f"Retrieval-only participant UI contains forbidden pattern: {pattern}"))

    if re.search(r"flat hierarchy|one screen|single[- ]surface", design_body, re.IGNORECASE) and re.search(r"Step\s+1\s+of", text, re.IGNORECASE):
        findings.append(Finding("WARNING", "STATE_RENDERED_AS_STEP", "Single-surface product appears to render states as sequential steps."))

    inputs = re.findall(r"<(?:input|textarea)\b[^>]*\bid=[\"']([^\"']+)[\"']", text, re.IGNORECASE)
    for input_id in inputs:
        if not re.search(rf"<label\b[^>]*\bfor=[\"']{re.escape(input_id)}[\"']", text, re.IGNORECASE):
            findings.append(Finding("ERROR", "INPUT_LABEL_MISSING", f"Input #{input_id} has no explicit label."))
    return findings


def error_count(findings: Iterable[Finding]) -> int:
    return sum(1 for finding in findings if finding.severity == "ERROR")


def format_findings(findings: Iterable[Finding]) -> str:
    return "\n".join(f"  {finding.severity} [{finding.code}] {finding.message}" for finding in findings)
