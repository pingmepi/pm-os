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
from project import artifact_path, load_meta


CONTRACT_VERSION = 3

# Contract versions this validator still accepts without a drift warning. v2 added
# recommended PRD enrichments (Impact Analysis, per-story acceptance shape) that
# feed the readable handoff package; v3 added the GenAI model-availability/fallback
# checks (stages 03/08). Every v2 and v3 check is WARNING-only, so a v1 PRD on disk
# keeps passing untouched (CLAUDE.md: existing projects must keep working).
SUPPORTED_CONTRACT_VERSIONS = {1, 2, 3}

# --- Stable requirement / test-case identifiers (Phase 3.5 traceability spine) ---
# Requirement IDs are the stable handles the traceability spine links against. The
# PRD already emits user-story (US-###) and functional-requirement (FR-###) ids;
# REQ-### is accepted as an explicit umbrella requirement id for projects that
# prefer it. All three are "requirement ids" for traceability purposes.
REQUIREMENT_ID_RE = re.compile(r"\b(?:REQ|US|FR)-\d{3,}\b", re.IGNORECASE)
TEST_CASE_ID_RE = re.compile(r"\bTC-\d{3,}\b", re.IGNORECASE)
USER_STORY_ID_RE = re.compile(r"\bUS-\d{3,}\b", re.IGNORECASE)
FUNCTIONAL_REQ_ID_RE = re.compile(r"\b(?:FR|REQ)-\d{3,}\b", re.IGNORECASE)
JOURNEY_ID_RE = re.compile(r"\bUJ-\d{3,}\b", re.IGNORECASE)
# Design-spec (stage 04) screens. SCR-### is the stable handle that lets the handoff
# package tell a developer which screens a user story touches; each screen declares
# the stories/requirements/journeys it serves.
SCREEN_ID_RE = re.compile(r"\bSCR-\d{3,}\b", re.IGNORECASE)
# TRD (stage 08) Work Breakdown tasks. TSK-### is the stable handle the tracker
# export keys tickets off; each task declares the requirement ids it implements.
TASK_ID_RE = re.compile(r"\bTSK-\d{3,}\b", re.IGNORECASE)


def requirement_ids(text: str) -> list[str]:
    """Return the unique, upper-cased requirement ids (REQ/US/FR-###) in ``text``,
    in first-seen order. Used by both the contract checks and the resolver."""
    seen: dict[str, None] = {}
    for match in REQUIREMENT_ID_RE.findall(text or ""):
        seen.setdefault(match.upper(), None)
    return list(seen)


def test_case_ids(text: str) -> list[str]:
    """Return the unique, upper-cased TC-### ids in ``text``, in first-seen order."""
    seen: dict[str, None] = {}
    for match in TEST_CASE_ID_RE.findall(text or ""):
        seen.setdefault(match.upper(), None)
    return list(seen)


def task_ids(text: str) -> list[str]:
    """Return the unique, upper-cased TSK-### ids in ``text``, in first-seen order."""
    seen: dict[str, None] = {}
    for match in TASK_ID_RE.findall(text or ""):
        seen.setdefault(match.upper(), None)
    return list(seen)


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
    "06": [
        "Test Strategy",
        "Functional Test Cases",
        "Non-Functional Tests",
        "Edge Cases",
        "Acceptance Criteria",
    ],
}

RECOMMENDED_SECTIONS = {
    "03": ["Journey-Requirement Traceability", "Assumptions & Open Decisions", "Impact Analysis"],
    "04": ["Responsive & Platform Behavior", "UX Content Rules"],
    "05": ["Prototype Data & Scenarios", "Known Limitations"],
    "06": ["Requirement-Test Traceability"],
}

# Stages validated without a required-section contract. Stage 08 (TRD) predates any
# section contract and existing TRDs on disk would fail a full required-section list,
# so it is validated for the GenAI model-serving check only — and is deliberately
# exempt from the `artifact_contract_version` frontmatter warning below, which
# belongs to stages that do declare a section contract.
_EXTRA_VALIDATED_STAGES = {"08"}

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


# A TC-### scenario can be declared as a heading (`### TC-001`), a bullet
# (`- TC-001`), an ordered-list item (`1. TC-001`), or a bare line — any of these
# with the id optionally bold-wrapped (`- **TC-001:**`). We match all of these at
# line start; any `##`-`######` heading bounds a block so the last TC does not
# absorb trailing subsections. Shared by the contract validator and the
# traceability resolver so they agree on what a "test case block" is.
_TC_BLOCK_START_RE = re.compile(
    r"^(?:(?P<hashes>#{1,6})\s+|[-*+]\s+|\d+\.\s+)?\*{0,2}(?P<id>TC-\d{3,})\b",
    re.MULTILINE | re.IGNORECASE,
)
# Any markdown heading, capturing its level so a block breaks only at a heading
# at or above the declaration's own level (a nested subsection does NOT end it).
_HEADING_LEVEL_RE = re.compile(r"^(#{1,6})\s", re.MULTILINE)


def _split_id_blocks(text: str, start_re: "re.Pattern") -> dict[str, str]:
    """Map each id declared by ``start_re`` to the text block that introduces it.

    A block runs from its declaration to the earliest of: the next such
    declaration, or the next heading at a level **<= the declaration's own heading
    level**. So a TC/US declared as a heading (``### TC-001``) keeps its nested
    ``#### Steps`` / ``#### Coverage`` detail but ends at a sibling/ancestor
    heading; one declared as a bullet/ordered-list/bare line (no heading level, so
    treated as level 7, deeper than any heading) ends at the next heading of any
    level — which is what stops an interleaved non-TC ``###`` subsection from being
    absorbed. First declaration wins; later mentions are references. Shared by the
    contract validator, the traceability resolver, and the handoff assembler so
    they all agree on what a "block" is.
    """
    headings = [(m.start(), len(m.group(1))) for m in _HEADING_LEVEL_RE.finditer(text)]
    matches = list(start_re.finditer(text))
    blocks: dict[str, str] = {}
    for index, match in enumerate(matches):
        _id = match.group("id").upper()
        if _id in blocks:
            continue
        start = match.start()
        level = len(match.group("hashes")) if match.group("hashes") else 7
        next_decl = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        next_break = next((pos for pos, lvl in headings if pos > start and lvl <= level), len(text))
        blocks[_id] = text[start:min(next_decl, next_break)]
    return blocks


def split_test_case_blocks(text: str) -> dict[str, str]:
    """Map each TC-### id to the text block that introduces it. See ``_split_id_blocks``."""
    return _split_id_blocks(text, _TC_BLOCK_START_RE)


# A US-### story can be declared as a heading (`### US-001`), a bullet
# (`- US-001`), an ordered-list item (`1. US-001`), or a bare line, id optionally
# bold-wrapped — the same shapes `split_test_case_blocks` accepts. Shared by the
# contract's per-story checks and the handoff assembler so both agree on what
# "a user-story block" is.
_US_BLOCK_START_RE = re.compile(
    r"^(?:(?P<hashes>#{1,6})\s+|[-*+]\s+|\d+\.\s+)?\*{0,2}(?P<id>US-\d{3,})\b",
    re.MULTILINE | re.IGNORECASE,
)


def split_user_story_blocks(text: str) -> dict[str, str]:
    """Map each US-### id to its introducing block. Mirrors ``split_test_case_blocks``
    (via ``_split_id_blocks``) so the handoff and the validator stay in lockstep."""
    return _split_id_blocks(text, _US_BLOCK_START_RE)


# A TSK-### task can be declared as a heading (`### TSK-001`), a bullet, an
# ordered-list item, or a bare line, id optionally bold-wrapped — the same shapes
# the US/TC splitters accept. Shared by the traceability index and /pm-check so
# both agree on what "a TRD task block" is.
_TSK_BLOCK_START_RE = re.compile(
    r"^(?:(?P<hashes>#{1,6})\s+|[-*+]\s+|\d+\.\s+)?\*{0,2}(?P<id>TSK-\d{3,})\b",
    re.MULTILINE | re.IGNORECASE,
)

# The `Implements:` line inside a task block, tolerating list/bold markers and an
# optional colon (`- **Implements:** US-003, FR-012`). Only this line is trusted as
# the task's requirement trace.
_IMPLEMENTS_LINE_RE = re.compile(
    r"^[\s>*+\-]*\*{0,2}\s*implements\b\s*:?\**\s*(?P<rest>.*)$",
    re.IGNORECASE | re.MULTILINE,
)


def split_task_blocks(text: str) -> dict[str, str]:
    """Map each TSK-### id to its introducing block. Mirrors ``split_user_story_blocks``
    (via ``_split_id_blocks``) so the traceability index and /pm-check stay in lockstep."""
    return _split_id_blocks(text, _TSK_BLOCK_START_RE)


# A SCR-### screen can be declared as a heading (`### SCR-001`), a bullet, an
# ordered-list item, or a bare line, id optionally bold-wrapped — the same shapes the
# US/TC/TSK splitters accept. Shared by the design-spec contract, the traceability
# index, /pm-check and the handoff package so they all agree on what "a screen" is.
_SCR_BLOCK_START_RE = re.compile(
    r"^(?:(?P<hashes>#{1,6})\s+|[-*+]\s+|\d+\.\s+)?\*{0,2}(?P<id>SCR-\d{3,})\b",
    re.MULTILINE | re.IGNORECASE,
)

# The `Serves:` line inside a screen block, tolerating list/bold markers and an
# optional colon (`- **Serves:** US-003, FR-012, UJ-002`). Only this line is trusted
# as the screen's trace, mirroring the task `Implements:` rule.
_SERVES_LINE_RE = re.compile(
    r"^[\s>*+\-]*\*{0,2}\s*serves\b\s*:?\**\s*(?P<rest>.*)$",
    re.IGNORECASE | re.MULTILINE,
)


def split_screen_blocks(text: str) -> dict[str, str]:
    """Map each SCR-### id to its introducing block. Mirrors ``split_task_blocks``
    (via ``_split_id_blocks``) so the design-spec contract, the traceability index and
    the handoff package stay in lockstep."""
    return _split_id_blocks(text, _SCR_BLOCK_START_RE)


def screen_id_declarations(text: str) -> list[str]:
    """Return every SCR-### id *as declared at a block start*, including duplicates, in
    document order — so /pm-check can flag a reused id that ``split_screen_blocks``
    collapses."""
    return [match.group("id").upper() for match in _SCR_BLOCK_START_RE.finditer(text or "")]


def screen_serves(block: str) -> list[str]:
    """Return the ids a screen declares it serves, read from the block's ``Serves:``
    line(s), unique and upper-cased in first-seen order.

    Accepts requirement ids (``US``/``FR``/``REQ-###``) and journey ids (``UJ-###``) —
    a screen legitimately serves a journey step as well as a story. Only the ``Serves:``
    line is trusted; an id mentioned elsewhere in the block's prose is not counted,
    which is exactly the untraced-screen signal the contract flags."""
    seen: dict[str, None] = {}
    for match in _SERVES_LINE_RE.finditer(block or ""):
        rest = match.group("rest")
        for sid in REQUIREMENT_ID_RE.findall(rest) + JOURNEY_ID_RE.findall(rest):
            seen.setdefault(sid.upper(), None)
    return list(seen)


def information_architecture_section(body: str) -> str:
    """Return the text under the design spec's ``## Information Architecture`` heading
    (up to the next ``##``), or '' if absent. Screen parsing is scoped to this section
    so a stray ``SCR-###`` mentioned elsewhere in the spec (e.g. under Key User Flows)
    is not indexed as a screen in its own right."""
    return _section(_sections(body or ""), "Information Architecture") or ""


def work_breakdown_section(body: str) -> str:
    """Return the text under the TRD's ``## Work Breakdown`` heading (up to the next
    ``##``), or '' if absent. Task parsing is scoped to this section so a stray
    ``TSK-###`` mentioned elsewhere in the TRD (e.g. under Open Technical Questions)
    is neither indexed as a delivery task nor counted by /pm-check."""
    return _section(_sections(body or ""), "Work Breakdown") or ""


def task_id_declarations(text: str) -> list[str]:
    """Return every TSK-### id *as declared at a block start*, including duplicates,
    in document order. ``split_task_blocks`` collapses duplicates (first wins); this
    keeps them so /pm-check can flag a reused id."""
    return [match.group("id").upper() for match in _TSK_BLOCK_START_RE.finditer(text or "")]


def task_implements(block: str) -> list[str]:
    """Return the requirement ids a TRD task declares it implements, read from the
    task block's ``Implements:`` line(s), unique and upper-cased in first-seen order.

    Only the ``Implements:`` line is trusted — a requirement id mentioned elsewhere in
    the block's prose is *not* counted as implemented. Empty when the block has no
    ``Implements:`` line or it cites no requirement id, which is exactly the
    orphan-task signal /pm-check flags."""
    seen: dict[str, None] = {}
    for match in _IMPLEMENTS_LINE_RE.finditer(block or ""):
        for rid in REQUIREMENT_ID_RE.findall(match.group("rest")):
            seen.setdefault(rid.upper(), None)
    return list(seen)


# Cues that a user-story block carries testable acceptance criteria. Kept broad so
# the check nudges rather than nags: any of these satisfies it.
_ACCEPTANCE_CUE_RE = re.compile(
    r"\bacceptance\b|\bdone\b|\bgiven\b.*\bthen\b|\bmust\b|\bshould\b",
    re.IGNORECASE | re.DOTALL,
)

_HAPPY_PATH_CUE_RE = re.compile(
    r"\bhappy path\b|\bprimary flow\b|\bsuccess path\b|\bnormal path\b",
    re.IGNORECASE,
)

_EDGE_CASE_CUE_RE = re.compile(
    r"\bedge cases?\b|\balternate paths?\b|\bfailure paths?\b|"
    r"\bcorner cases?\b|\bexceptions?\b|\brecovery\b",
    re.IGNORECASE,
)


# --- GenAI model-selection checks (contract v3) -------------------------------
# A GenAI product spec must answer two questions engineering cannot guess: is the
# model class actually available to this team, and what runs when it is not. Both
# cue sets are deliberately broad — this nudges rather than dictates wording — and
# every finding is WARNING-only so existing approved artifacts keep passing.

_MODEL_AVAILABILITY_CUE_RE = re.compile(
    r"\bavailab\w*|\baccess(?:ible|\s+path)?\b|\bself-hosted\b|\bhosted\b|\bon-?prem\w*|"
    r"\bgateway\b|\bprovider\b|\bvendor\b|\bregion\b|\bresidency\b|\bquota\b|"
    r"\brate limit\b|\bapproved\b|\bprocurement\b|\bdeploy(?:ment|ed)\b",
    re.IGNORECASE,
)

_MODEL_FALLBACK_CUE_RE = re.compile(
    r"\bfall\s?back\w*|\bfail\s?over\w*|\bsecondary model\b|\balternate model\b|"
    r"\bbackup model\b|\bdegrade[sd]?\b|\bdeprecat\w+",
    re.IGNORECASE,
)


def _genai_project(project_root: Path) -> bool:
    """True when the project's ``.meta.yaml`` sets ``genai_flag``.

    Degrades to False on any read failure so the GenAI-only checks can never break
    validation for a project whose meta is missing, unreadable, or pre-migration.
    """
    try:
        return bool(load_meta(project_root).get("genai_flag"))
    except Exception:
        return False


def _validate_model_selection(
    section: str | None, section_title: str, code: str
) -> list[Finding]:
    """Warn when a GenAI model section names neither availability nor a fallback.

    Shared by stage 03 (``Model Selection Rationale``, product level) and stage 08
    (``Model Serving & Selection``, buildable level): both must answer "can we
    actually get this model, and what runs if we can't". An absent section is not
    flagged here — the GenAI sections are appended conditionally, and a non-GenAI
    project legitimately has none.
    """
    if not (section or "").strip():
        return []
    missing = []
    if not _MODEL_AVAILABILITY_CUE_RE.search(section):
        missing.append("model availability (deployment path, vendor/region, quota)")
    if not _MODEL_FALLBACK_CUE_RE.search(section):
        missing.append("a fallback model and what triggers the switch")
    if not missing:
        return []
    return [Finding(
        "WARNING", code,
        f"{section_title} does not address: {'; '.join(missing)}.",
    )]


def _validate_stage_03(project_root: Path, sections: dict[str, str], body: str) -> list[Finding]:
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
        if not REQUIREMENT_ID_RE.search(block):
            findings.append(Finding("ERROR", "USER_JOURNEY_TRACE_MISSING", f"{journey_id} does not reference a stable requirement id (REQ-### / US-### / FR-###)."))

    stories = _section(sections, "User Stories with Acceptance Criteria") or ""
    if not USER_STORY_ID_RE.search(stories):
        findings.append(Finding("ERROR", "USER_STORY_IDS_MISSING", "User stories must use stable US-### identifiers so traceability survives regeneration."))
    # v2 (WARNING-only): each story block should carry acceptance criteria so the
    # handoff can render a Done/acceptance section per story instead of a blank.
    unacc = sorted(
        us_id for us_id, block in split_user_story_blocks(stories).items()
        if not _ACCEPTANCE_CUE_RE.search(block)
    )
    if unacc:
        findings.append(Finding(
            "WARNING", "USER_STORY_ACCEPTANCE_MISSING",
            f"User stories with no visible acceptance criteria: {', '.join(unacc)}",
        ))
    missing_happy = sorted(
        us_id for us_id, block in split_user_story_blocks(stories).items()
        if not _HAPPY_PATH_CUE_RE.search(block)
    )
    if missing_happy:
        findings.append(Finding(
            "WARNING", "USER_STORY_HAPPY_PATH_MISSING",
            f"User stories with no explicit happy path: {', '.join(missing_happy)}",
        ))
    missing_edges = sorted(
        us_id for us_id, block in split_user_story_blocks(stories).items()
        if not _EDGE_CASE_CUE_RE.search(block)
    )
    if missing_edges:
        findings.append(Finding(
            "WARNING", "USER_STORY_EDGE_CASES_MISSING",
            f"User stories with no explicit edge cases / alternate paths: {', '.join(missing_edges)}",
        ))
    requirements = _section(sections, "Functional Requirements") or ""
    if not FUNCTIONAL_REQ_ID_RE.search(requirements):
        findings.append(Finding("ERROR", "FUNCTIONAL_REQUIREMENT_IDS_MISSING", "Functional requirements must use stable FR-### (or REQ-###) identifiers so traceability survives regeneration."))
    if _genai_project(project_root):
        findings.extend(_validate_model_selection(
            _section(sections, "Model Selection Rationale"),
            "Model Selection Rationale",
            "MODEL_SELECTION_INCOMPLETE",
        ))
    return findings


def _validate_stage_08(project_root: Path, sections: dict[str, str], body: str) -> list[Finding]:
    """Stage 08 (TRD) carries no required-section contract — existing TRDs predate one
    and adding a full list would fail them all. The only check here is the GenAI
    model-serving one (WARNING-only), so the TRD is held to naming a fallback and an
    availability path for the models it commits the build to."""
    if not _genai_project(project_root):
        return []
    return _validate_model_selection(
        _section(sections, "Model Serving & Selection"),
        "Model Serving & Selection",
        "MODEL_SERVING_INCOMPLETE",
    )


def _validate_stage_06(project_root: Path, sections: dict[str, str], body: str) -> list[Finding]:
    """Stage 06 (QA Plan) must give each scenario a stable TC-### id and tie the
    test cases back to the requirement ids the PRD established, so the traceability
    spine can answer "which scenarios cover requirement REQ-X" locally.

    Coverage is reported as a WARNING (not a hard error) so prose QA plans on
    existing projects degrade gracefully instead of failing approval/import.
    """
    findings: list[Finding] = []
    test_section = _section(sections, "Functional Test Cases") or ""
    # Both checks below — "are there declared TC ids?" and "does each TC cite a
    # requirement?" — must agree on what counts as a declared TC, and that must be
    # the same extractor the traceability resolver uses (split_test_case_blocks),
    # not the looser TEST_CASE_ID_RE — otherwise a QA plan can pass validation while
    # contributing nothing to .traceability.yaml. Fall back to scanning the whole
    # body only if the named section has no recognizable TC declarations.
    tc_blocks = split_test_case_blocks(test_section) or split_test_case_blocks(body)
    tc_ids = list(tc_blocks.keys())
    if not tc_ids:
        findings.append(Finding(
            "ERROR", "TEST_CASE_IDS_MISSING",
            "Functional Test Cases must use stable TC-### identifiers so each scenario can be linked to requirements.",
        ))

    # Traceability: EACH test case must cite at least one requirement id — not just
    # "some id appears somewhere in the body" (which a traceability table would
    # satisfy while individual scenarios stay unlinked).
    untraced = sorted(tc for tc, block in tc_blocks.items() if not REQUIREMENT_ID_RE.search(block))
    if tc_blocks and untraced:
        findings.append(Finding(
            "ERROR", "TEST_CASE_TRACE_MISSING",
            f"Test cases with no requirement id (REQ-### / US-### / FR-###): {', '.join(untraced)}",
        ))

    # Coverage against the upstream PRD's requirement ids (warn only).
    upstream_reqs = _upstream_requirement_ids(project_root)
    if tc_ids and upstream_reqs:
        covered = {rid for rid in requirement_ids(body) if rid in upstream_reqs}
        uncovered = sorted(upstream_reqs - covered)
        if uncovered:
            findings.append(Finding(
                "WARNING", "REQUIREMENT_COVERAGE_GAP",
                f"Requirements with no covering TC-### in the QA plan: {', '.join(uncovered)}",
            ))
    return findings


def _upstream_journey_ids(project_root: Path) -> set[str]:
    path = artifact_path(project_root, "03")
    if not path.exists():
        return set()
    try:
        _fm, body = fm_read(str(path))
    except Exception:
        return set()
    return {match.upper() for match in JOURNEY_ID_RE.findall(body)}


def _upstream_requirement_ids(project_root: Path) -> set[str]:
    """Requirement ids (REQ/US/FR-###) declared in the approved PRD, used to check
    QA-plan coverage. Empty when the PRD is absent or carries no stable ids — so
    existing prose PRDs never trigger a false coverage gap."""
    path = artifact_path(project_root, "03")
    if not path.exists():
        return set()
    try:
        _fm, body = fm_read(str(path))
    except Exception:
        return set()
    return set(requirement_ids(body))


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
    findings.extend(_validate_screens(_section(sections, "Information Architecture") or ""))
    return findings


def _validate_screens(ia_section: str) -> list[Finding]:
    """Screens are the handoff's missing link: without a stable id and a declared
    trace, a story file cannot tell a developer which screens it touches.

    WARNING-only by design — design specs approved before contract v3 carry no
    ``SCR-###`` ids at all, and must keep passing (CLAUDE.md: existing projects keep
    working). The handoff degrades to "not captured in source" for them.
    """
    blocks = split_screen_blocks(ia_section)
    if not blocks:
        return [Finding(
            "WARNING", "SCREEN_IDS_MISSING",
            "Information Architecture declares no SCR-### screens, so the handoff package "
            "cannot map screens to user stories.",
        )]
    untraced = sorted(sid for sid, block in blocks.items() if not screen_serves(block))
    if untraced:
        return [Finding(
            "WARNING", "SCREEN_TRACE_MISSING",
            f"Screens with no `Serves:` trace to a story/requirement/journey: {', '.join(untraced)}",
        )]
    return []


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
    if stage_id not in REQUIRED_SECTIONS and stage_id not in _EXTRA_VALIDATED_STAGES:
        return []
    artifact = Path(path) if path else artifact_path(project_root, stage_id)
    if not artifact.exists():
        return [Finding("ERROR", "ARTIFACT_MISSING", f"Artifact not found: {artifact}")]
    try:
        fm, body = fm_read(str(artifact))
    except Exception as exc:
        return [Finding("ERROR", "ARTIFACT_UNREADABLE", f"Could not read artifact: {exc}")]

    findings: list[Finding] = []
    if stage_id in REQUIRED_SECTIONS and fm.get("artifact_contract_version") not in SUPPORTED_CONTRACT_VERSIONS:
        findings.append(Finding(
            "WARNING", "CONTRACT_VERSION_MISSING",
            f"Artifact does not declare a supported artifact_contract_version "
            f"(latest: {CONTRACT_VERSION}).",
        ))
    sections = _sections(body)
    findings.extend(_missing_sections(stage_id, sections))
    if stage_id == "03":
        findings.extend(_validate_stage_03(project_root, sections, body))
    elif stage_id == "04":
        findings.extend(_validate_stage_04(project_root, sections, body))
    elif stage_id == "05":
        findings.extend(_validate_stage_05(project_root, sections, body))
    elif stage_id == "06":
        findings.extend(_validate_stage_06(project_root, sections, body))
    elif stage_id == "08":
        findings.extend(_validate_stage_08(project_root, sections, body))
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
