"""Unit coverage for Stage 03–05 artifact and prototype contracts."""
from pathlib import Path

import pytest

import artifact_contracts as contracts
import frontmatter

pytestmark = pytest.mark.unit


def _project(tmp_path: Path) -> Path:
    (tmp_path / ".meta.yaml").write_text(
        "schema_version: 3\nproject_slug: contract-test\nproject_name: Contract Test\n"
        "genai_flag: false\npm_os_version: 0\nstages: []\n",
        encoding="utf-8",
    )
    return tmp_path


def _write(root: Path, filename: str, body: str, contract_version=1) -> Path:
    path = root / filename
    frontmatter.write(str(path), {
        "stage": filename.removesuffix(".md"),
        "project": "contract-test",
        "status": "draft",
        "artifact_contract_version": contract_version,
    }, body)
    return path


def _valid_prd() -> str:
    return """# Product Requirements Document: Test

## Overview
Test product.
## Goals and Non-Goals
Goal and exclusions.
## User Journeys
### UJ-001 — Complete the primary task
**Primary user:** Operator
**Context and trigger:** A work item arrives.
**Goal:** Complete it safely.
**Preconditions:** Access is available.
**Happy path:** Open, review, and finish.
**Alternate/failure paths:** Recover from unavailable data.
**Completion signal:** Confirmation appears.
**Traceability:** US-001, FR-001.
## User Stories with Acceptance Criteria
### US-001 — Complete work
Happy path: The operator opens the item, reviews it, and completes it.
Edge cases / alternate paths: If required data is unavailable, show recovery guidance.
Acceptance criteria are observable.
## Functional Requirements
- FR-001 — Complete the work.
## Non-Functional Requirements
Measurable reliability.
## Data & Governance
No sensitive data.
## Journey–Requirement Traceability
UJ-001 → US-001 → FR-001.
## Assumptions & Open Decisions
None.
## Edge Cases
Unavailable data.
## Risks
Adoption.
"""


def test_valid_prd_contract_has_no_errors(tmp_path):
    root = _project(tmp_path)
    _write(root, "03-prd.md", _valid_prd())
    findings = contracts.validate_artifact(root, "03")
    assert contracts.error_count(findings) == 0, contracts.format_findings(findings)


def test_prd_without_journeys_is_an_error(tmp_path):
    root = _project(tmp_path)
    body = _valid_prd().replace("## User Journeys\n", "## Journey Notes\n")
    _write(root, "03-prd.md", body)
    codes = {finding.code for finding in contracts.validate_artifact(root, "03")}
    assert "REQUIRED_SECTION_MISSING" in codes
    assert "USER_JOURNEY_MISSING" in codes


def test_recommended_prd_sections_warn_without_blocking(tmp_path):
    root = _project(tmp_path)
    body = _valid_prd().replace("## Journey–Requirement Traceability\nUJ-001 → US-001 → FR-001.\n", "")
    _write(root, "03-prd.md", body)
    findings = contracts.validate_artifact(root, "03")
    assert any(f.code == "RECOMMENDED_SECTION_MISSING" for f in findings)
    assert contracts.error_count(findings) == 0


def test_design_contract_checks_journey_mapping_and_interaction_model(tmp_path):
    root = _project(tmp_path)
    _write(root, "03-prd.md", _valid_prd())
    body = """# Design Spec
## Information Architecture
Single surface.
## Journey-to-Flow Traceability
UJ-001 maps to the primary flow.
## Key User Flows
Start, act, recover, finish.
## Product UX Guardrails
Interaction model: retrieval-only
## Design Principles
Trust first.
## Component Inventory
Form and result.
## Responsive & Platform Behavior
Tablet first.
## UX Content Rules
Use find language.
## Typography
Readable.
## Color Tokens
Semantic.
## Spacing Tokens
Four-point scale.
## Iconography
Meaningful only.
## Accessibility Notes
Keyboard and screen reader.
"""
    _write(root, "04-design-spec.md", body)
    findings = contracts.validate_artifact(root, "04")
    assert contracts.error_count(findings) == 0, contracts.format_findings(findings)


def test_prototype_brief_requires_modes_validation_and_a_journey(tmp_path):
    root = _project(tmp_path)
    _write(root, "03-prd.md", _valid_prd())
    body = """# Prototype Brief
## What to Prototype
UJ-001 primary slice.
## Fidelity Level
Interactive HTML.
## Prototype Audience & Modes
Participant mode is the default; reviewer mode is enabled separately.
## Screens to Include
Primary screen.
## Interactions to Demonstrate
Complete the task.
## Prototype Data & Scenarios
Synthetic scenario.
## Questions the Prototype Should Answer
Can users finish?
## Validation Plan
Participants complete tasks against a current-experience comparator. Measures and evidence use a decision threshold. Facilitator guidance avoids bias and priming.
## Known Limitations
Simulated backend.
## Non-Goals for Prototype
No production integration.
"""
    _write(root, "05-prototype-brief.md", body)
    findings = contracts.validate_artifact(root, "05")
    assert contracts.error_count(findings) == 0, contracts.format_findings(findings)


def test_retrieval_html_flags_generic_generation_patterns(tmp_path):
    root = _project(tmp_path)
    _write(root, "04-design-spec.md", """# Design
## Product UX Guardrails
Interaction model: retrieval-only
""")
    html = root / "05-prototype-mockup.html"
    html.write_text("""<!doctype html><html><body>
<div class="review-only">questions</div><label for="q">Query</label><input id="q">
<p>Generating result with confidence</p><script>
const review = new URLSearchParams(window.location.search).get('review') === '1';
setInterval(() => {}, 10);
</script></body></html>""", encoding="utf-8")
    codes = {finding.code for finding in contracts.validate_prototype_html(root)}
    assert "RETRIEVAL_USES_GENERATING" in codes
    assert "RETRIEVAL_USES_STREAMING" in codes
    assert "RETRIEVAL_USES_CONFIDENCE" in codes


def test_retrieval_html_ignores_nested_review_only_content(tmp_path):
    root = _project(tmp_path)
    _write(root, "04-design-spec.md", """# Design
## Product UX Guardrails
Interaction model: retrieval-only
""")
    html = root / "05-prototype-mockup.html"
    html.write_text("""<!doctype html><html><body>
<label for="q">Query</label><input id="q">
<div class="review-only"><section><p>Generating with confidence</p></section><button>Override</button></div>
<p>Approved matches shown.</p>
<script>const review = new URLSearchParams(window.location.search).get('review') === '1';</script>
</body></html>""", encoding="utf-8")
    codes = {finding.code for finding in contracts.validate_prototype_html(root)}
    assert not any(code.startswith("RETRIEVAL_USES_") for code in codes), codes


def _valid_qa() -> str:
    return """# QA Plan: Test
## Test Strategy
Risk-based manual and automated coverage.
## Functional Test Cases
### TC-001 — Complete the primary task (covers US-001, FR-001)
Steps and expected results.
### TC-002 — Recover from failure (covers FR-001)
Steps and expected results.
## Non-Functional Tests
Performance and accessibility.
## Edge Cases
Invalid input handling.
## Acceptance Criteria
Must-pass gates and no-go conditions.
## Requirement-Test Traceability
US-001 → TC-001; FR-001 → TC-001, TC-002.
"""


def test_valid_qa_plan_contract_has_no_errors(tmp_path):
    """A QA plan whose scenarios carry TC-### ids and trace to PRD requirement ids
    passes the stage-06 contract with no errors (coverage gaps may still warn)."""
    root = _project(tmp_path)
    _write(root, "03-prd.md", _valid_prd())
    _write(root, "06-qa-plan.md", _valid_qa())
    findings = contracts.validate_artifact(root, "06")
    assert contracts.error_count(findings) == 0, contracts.format_findings(findings)


def test_qa_plan_without_tc_ids_is_an_error(tmp_path):
    """A prose QA plan with no TC-### scenario ids fails strict validation so stable
    test-case handles are required for newly generated plans."""
    root = _project(tmp_path)
    body = """# QA Plan
## Test Strategy
Risk-based coverage.
## Functional Test Cases
We will test login and the dashboard end to end.
## Non-Functional Tests
Performance.
## Edge Cases
Invalid input.
## Acceptance Criteria
Must-pass gates.
"""
    _write(root, "06-qa-plan.md", body)
    codes = {f.code for f in contracts.validate_artifact(root, "06")}
    assert "TEST_CASE_IDS_MISSING" in codes


def test_qa_plan_test_case_must_trace_to_a_requirement(tmp_path):
    """A QA plan with TC-### ids but no requirement reference fails the trace check."""
    root = _project(tmp_path)
    body = """# QA Plan
## Test Strategy
s
## Functional Test Cases
### TC-001 — A scenario with no requirement link
Steps.
## Non-Functional Tests
n
## Edge Cases
e
## Acceptance Criteria
a
"""
    _write(root, "06-qa-plan.md", body)
    codes = {f.code for f in contracts.validate_artifact(root, "06")}
    assert "TEST_CASE_TRACE_MISSING" in codes


def test_qa_plan_uncovered_requirement_warns_not_errors(tmp_path):
    """A PRD requirement with no covering TC-### produces a WARNING coverage gap,
    never a hard error — so partial coverage does not block approval."""
    root = _project(tmp_path)
    # PRD declares FR-002 but the QA plan only covers US-001/FR-001.
    _write(root, "03-prd.md", _valid_prd().replace("- FR-001 — Complete the work.", "- FR-001 — Complete the work.\n- FR-002 — Audit the work."))
    _write(root, "06-qa-plan.md", _valid_qa())
    findings = contracts.validate_artifact(root, "06")
    gap = [f for f in findings if f.code == "REQUIREMENT_COVERAGE_GAP"]
    assert gap and gap[0].severity == "WARNING"
    assert "FR-002" in gap[0].message
    assert contracts.error_count(findings) == 0


def test_prd_functional_requirements_accept_req_only_ids(tmp_path):
    """A PRD that uses only REQ-### (umbrella) ids in Functional Requirements passes
    strict validation — the contract text and error message both say REQ is accepted,
    so the FR-### check must not reject a REQ-only requirements section."""
    root = _project(tmp_path)
    prd = _valid_prd().replace("- FR-001 — Complete the work.", "- REQ-001 — Complete the work.")
    # Keep the journey/story trace ids resolvable (UJ traces to US-001 still present).
    _write(root, "03-prd.md", prd)
    codes = {f.code for f in contracts.validate_artifact(root, "03")}
    assert "FUNCTIONAL_REQUIREMENT_IDS_MISSING" not in codes


def test_qa_plan_per_test_case_trace_is_enforced(tmp_path):
    """Each TC must cite a requirement id, not just 'some id appears in the body'. A
    plan where TC-002 has no link must fail even though TC-001 (and a traceability
    table) carry requirement ids — and the finding names the untraced scenario."""
    root = _project(tmp_path)
    _write(root, "03-prd.md", _valid_prd())
    body = """# QA Plan
## Test Strategy
s
## Functional Test Cases
### TC-001 — Linked scenario (covers FR-001)
Steps.
### TC-002 — Unlinked scenario
Steps.
## Non-Functional Tests
n
## Edge Cases
e
## Acceptance Criteria
a
## Requirement-Test Traceability
FR-001 → TC-001.
"""
    _write(root, "06-qa-plan.md", body)
    trace = [f for f in contracts.validate_artifact(root, "06") if f.code == "TEST_CASE_TRACE_MISSING"]
    assert trace, "expected TEST_CASE_TRACE_MISSING for the unlinked TC-002"
    assert "TC-002" in trace[0].message and "TC-001" not in trace[0].message


def test_qa_plan_bold_wrapped_bullet_ids_are_declared(tmp_path):
    """Backlog IMP-007: a bold-wrapped bullet id (`- **TC-001:** ...`) is a single
    Markdown style choice, not a different test case. The validator's
    TEST_CASE_IDS_MISSING check and split_test_case_blocks (which feeds both
    TEST_CASE_TRACE_MISSING and traceability.build_index) must agree it declares
    TC-001 — previously the loose validator regex saw it while the strict
    splitter returned an empty dict, so a QA plan could pass validation while
    contributing nothing to .traceability.yaml."""
    root = _project(tmp_path)
    _write(root, "03-prd.md", _valid_prd())
    body = """# QA Plan
## Test Strategy
s
## Functional Test Cases
- **TC-001:** Verify ranked results exclude expired assets. Covers FR-001.
## Non-Functional Tests
n
## Edge Cases
e
## Acceptance Criteria
a
"""
    _write(root, "06-qa-plan.md", body)
    findings = contracts.validate_artifact(root, "06")
    assert not any(f.code in ("TEST_CASE_IDS_MISSING", "TEST_CASE_TRACE_MISSING") for f in findings)

    blocks = contracts.split_test_case_blocks("- **TC-001:** Verify ranked results exclude expired assets. Covers FR-001.")
    assert "TC-001" in blocks, "strict splitter must also recognize the bold-wrapped bullet id"


def test_split_test_case_blocks_stops_at_any_heading_level(tmp_path):
    """Backlog IMP-007 (related bug): a non-TC ### subsection interleaved between two
    test cases must end the preceding TC's block, not get silently absorbed into it —
    previously the section-break regex only matched literal ## headings."""
    text = """## Functional Test Cases
### TC-017
Covers FR-001. Some scenario text.
### Metrics and compliance evidence
Editorial subsection with no TC id.
### TC-018
Covers FR-002. Another scenario.
"""
    blocks = contracts.split_test_case_blocks(text)
    assert "Metrics and compliance" not in blocks["TC-017"]
    assert "Covers FR-002" in blocks["TC-018"]


def test_split_test_case_blocks_preserves_nested_subheadings(tmp_path):
    """A heading-style TC (`### TC-001`) with its own nested `#### Coverage`/`#### Steps`
    subsections must keep that detail in its block — the break fires only at a heading at
    or above the TC's own level, not at a deeper nested one. Regression for the level-aware
    splitter: an earlier fix broke at *any* `##`-`######` heading, truncating such a TC at
    its first `####` and dropping requirement ids cited below it (false TEST_CASE_TRACE_MISSING
    + empty .traceability.yaml links even though the TC cites FR/US ids)."""
    text = """## Functional Test Cases
### TC-001
Verify ranked results exclude expired assets.
#### Coverage
Covers REQ-001 and FR-003.
#### Steps
1. Run the query. 2. Assert exclusion.

### TC-002
Covers REQ-002. Another scenario.
"""
    blocks = contracts.split_test_case_blocks(text)
    # The nested subsections (and the ids they carry) stay inside TC-001's block.
    assert "REQ-001" in blocks["TC-001"] and "FR-003" in blocks["TC-001"]
    assert "#### Steps" in blocks["TC-001"]
    # …but TC-001 still ends at the sibling TC-002 heading, not bleeding into it.
    assert "REQ-002" not in blocks["TC-001"]
    assert "REQ-002" in blocks["TC-002"]


def test_split_test_case_blocks_handles_ordered_list_items(tmp_path):
    """The shared splitter recognizes ordered-list test cases (`1. TC-001`), not only
    headings/bullets, so build_index and the contract validator agree on them."""
    text = """## Functional Test Cases
1. TC-001 — covers FR-001
2. TC-002 — covers FR-002
## Acceptance Criteria
FR-001, FR-002 must pass.
"""
    blocks = contracts.split_test_case_blocks(text)
    assert set(blocks) == {"TC-001", "TC-002"}
    # The last TC must not absorb the trailing Acceptance Criteria section.
    assert "FR-002" in blocks["TC-002"] and "must pass" not in blocks["TC-002"]


def test_requirement_and_test_case_id_extractors(tmp_path):
    """The shared id extractors return unique upper-cased ids in first-seen order
    and accept REQ/US/FR for requirements and TC for test cases."""
    assert contracts.requirement_ids("US-001 and fr-002, REQ-003, US-001") == ["US-001", "FR-002", "REQ-003"]
    assert contracts.test_case_ids("tc-001 TC-002 tc-001") == ["TC-001", "TC-002"]


def test_generative_html_allows_generation_patterns(tmp_path):
    root = _project(tmp_path)
    _write(root, "04-design-spec.md", """# Design
## Product UX Guardrails
Interaction model: generative
""")
    html = root / "05-prototype-mockup.html"
    html.write_text("""<!doctype html><html><body>
<div class="review-only">questions</div><p>Generating draft</p><script>
const review = new URLSearchParams(window.location.search).get('review') === '1';
</script></body></html>""", encoding="utf-8")
    codes = {finding.code for finding in contracts.validate_prototype_html(root)}
    assert not any(code.startswith("RETRIEVAL_USES_") for code in codes)


# --- v2 enrichments feeding the readable handoff package -----------------------

def test_split_user_story_blocks_bounds_by_declaration_and_section(tmp_path):
    """US-### blocks split on the next US declaration or the next ## section, so a
    story's block is exactly what the handoff assembler will render for it."""
    text = """### US-001 — Add
As a user, I want add.
### US-002 — List
As a user, I want list.
## Functional Requirements
FR-001 — stuff.
"""
    blocks = contracts.split_user_story_blocks(text)
    assert list(blocks) == ["US-001", "US-002"]
    assert "want add" in blocks["US-001"] and "want list" not in blocks["US-001"]
    assert "FR-001" not in blocks["US-002"]  # the ## section bounds the last block


def test_user_story_without_acceptance_warns_not_errors(tmp_path):
    """A story block carrying no acceptance cue is a WARNING (so the handoff can flag
    the gap) — never a hard error that would block approval of existing projects."""
    root = _project(tmp_path)
    body = _valid_prd().replace(
        "### US-001 — Complete work\n"
        "Happy path: The operator opens the item, reviews it, and completes it.\n"
        "Edge cases / alternate paths: If required data is unavailable, show recovery guidance.\n"
        "Acceptance criteria are observable.\n",
        "### US-001 — Complete work\nThe operator opens the item.\n",
    )
    _write(root, "03-prd.md", body)
    findings = contracts.validate_artifact(root, "03")
    assert any(f.code == "USER_STORY_ACCEPTANCE_MISSING" for f in findings)
    assert contracts.error_count(findings) == 0


def test_user_story_without_happy_path_or_edge_cases_warns_not_errors(tmp_path):
    """Per-story happy path and edge cases are explicit handoff cues, but missing
    cues warn only so existing PRDs remain approvable."""
    root = _project(tmp_path)
    body = _valid_prd().replace(
        "Happy path: The operator opens the item, reviews it, and completes it.\n"
        "Edge cases / alternate paths: If required data is unavailable, show recovery guidance.\n",
        "",
    )
    _write(root, "03-prd.md", body)
    findings = contracts.validate_artifact(root, "03")
    codes = {f.code for f in findings}
    assert "USER_STORY_HAPPY_PATH_MISSING" in codes
    assert "USER_STORY_EDGE_CASES_MISSING" in codes
    assert contracts.error_count(findings) == 0


def test_contract_version_1_is_still_supported(tmp_path):
    """Bumping CONTRACT_VERSION to 2 must not make existing v1 PRDs warn about their
    contract version — v1 and v2 are both supported (backward compatibility)."""
    root = _project(tmp_path)
    _write(root, "03-prd.md", _valid_prd(), contract_version=1)
    codes = {f.code for f in contracts.validate_artifact(root, "03")}
    assert "CONTRACT_VERSION_MISSING" not in codes


def test_impact_analysis_is_a_recommended_prd_section(tmp_path):
    """Impact Analysis missing warns (feeds the handoff's impact-analysis.md) but
    never blocks."""
    root = _project(tmp_path)
    _write(root, "03-prd.md", _valid_prd())  # _valid_prd has no Impact Analysis
    findings = contracts.validate_artifact(root, "03")
    assert any(
        f.code == "RECOMMENDED_SECTION_MISSING" and "Impact Analysis" in f.message
        for f in findings
    )
    assert contracts.error_count(findings) == 0


# --- TRD Work Breakdown task parsing (Phase 3.5b) ------------------------------

_TRD_WORK_BREAKDOWN = """# TRD
## Work Breakdown
### TSK-001 — Build retrieval index
- **Implements:** US-003, FR-012
- **Definition of Done:** TC-004 passes.
### TSK-002 — Wire audit logging
- **Implements:** FR-020 and the audit NFR
- **Depends on:** TSK-001

- **TSK-003:** orphan task
- **Description:** mentions FR-099 in prose but declares no Implements line.

## Open Technical Questions
Nothing here should be absorbed into TSK-003.
"""


def test_task_ids_and_split_task_blocks():
    """task_ids and split_task_blocks find every TSK-### declared as heading,
    bullet, or ordered-list item, in first-seen order, deduped."""
    assert contracts.task_ids(_TRD_WORK_BREAKDOWN) == ["TSK-001", "TSK-002", "TSK-003"]
    blocks = contracts.split_task_blocks(_TRD_WORK_BREAKDOWN)
    assert list(blocks) == ["TSK-001", "TSK-002", "TSK-003"]


def test_task_block_does_not_absorb_trailing_section():
    """A bullet-declared final task ends at the next heading, so TSK-003 does not
    swallow the Open Technical Questions section that follows it."""
    blocks = contracts.split_task_blocks(_TRD_WORK_BREAKDOWN)
    assert "Open Technical Questions" not in blocks["TSK-003"]


def test_task_implements_reads_only_the_implements_line():
    """task_implements trusts only the `Implements:` line — prose mentions of a
    requirement id elsewhere in the block are not counted (TSK-002 keeps FR-020
    but not 'the audit NFR'; TSK-003's prose FR-099 is ignored → orphan)."""
    blocks = contracts.split_task_blocks(_TRD_WORK_BREAKDOWN)
    assert contracts.task_implements(blocks["TSK-001"]) == ["US-003", "FR-012"]
    assert contracts.task_implements(blocks["TSK-002"]) == ["FR-020"]
    assert contracts.task_implements(blocks["TSK-003"]) == []


def test_task_id_declarations_keeps_duplicates():
    """task_id_declarations returns block-start ids including duplicates (so
    /pm-check can flag a reused id), unlike split_task_blocks which collapses them."""
    text = "### TSK-001 — a\n- x\n### TSK-001 — dup\n- y\n### TSK-002 — b\n- z\n"
    assert contracts.task_id_declarations(text) == ["TSK-001", "TSK-001", "TSK-002"]
    assert list(contracts.split_task_blocks(text)) == ["TSK-001", "TSK-002"]


def test_work_breakdown_section_scopes_task_parsing():
    """work_breakdown_section returns only the text under ## Work Breakdown, so a
    stray TSK-### under another heading is excluded; '' when the section is absent."""
    body = (
        "## Work Breakdown\n### TSK-001 — real\n- **Implements:** US-001\n"
        "## Open Technical Questions\n- TSK-999 not a delivery task\n"
    )
    section = contracts.work_breakdown_section(body)
    assert "TSK-001" in section and "TSK-999" not in section
    assert list(contracts.split_task_blocks(section)) == ["TSK-001"]
    assert contracts.work_breakdown_section("## Architecture\nNo breakdown here.\n") == ""


# --- GenAI model selection / serving (contract v3) ----------------------------

_MODEL_SECTION_COMPLETE = """## Model Selection Rationale
Needs deep reasoning over long clinical documents, so a frontier reasoning model.
Available today only through the approved vendor's EU-region hosted API (quota 1M
tokens/day); self-hosting is not approved. Primary is that model; the fallback is
the smaller fast model in the same family, triggered by quota exhaustion, a
provider outage, or deprecation of the pinned version — answers get terser.
"""

_MODEL_SECTION_VAGUE = """## Model Selection Rationale
The product needs a model that reasons well over long documents and responds quickly.
"""


def _genai_project(tmp_path: Path) -> Path:
    (tmp_path / ".meta.yaml").write_text(
        "schema_version: 3\nproject_slug: contract-test\nproject_name: Contract Test\n"
        "genai_flag: true\npm_os_version: 0\nstages: []\n",
        encoding="utf-8",
    )
    return tmp_path


def test_genai_prd_model_rationale_without_availability_or_fallback_warns(tmp_path):
    """A GenAI PRD whose Model Selection Rationale names neither an availability path
    nor a fallback model warns (WARNING, never blocking) so the PM sees the gap before
    engineering has to guess what to build against."""
    root = _genai_project(tmp_path)
    _write(root, "03-prd.md", _valid_prd() + _MODEL_SECTION_VAGUE, contract_version=3)
    findings = contracts.validate_artifact(root, "03")
    warning = next(f for f in findings if f.code == "MODEL_SELECTION_INCOMPLETE")
    assert "availability" in warning.message and "fallback" in warning.message
    assert contracts.error_count(findings) == 0, contracts.format_findings(findings)


def test_genai_prd_model_rationale_with_availability_and_fallback_is_clean(tmp_path):
    """Naming the deployment path, region/quota, and a named fallback with its switch
    trigger satisfies the check — no MODEL_SELECTION_INCOMPLETE warning."""
    root = _genai_project(tmp_path)
    _write(root, "03-prd.md", _valid_prd() + _MODEL_SECTION_COMPLETE, contract_version=3)
    codes = {f.code for f in contracts.validate_artifact(root, "03")}
    assert "MODEL_SELECTION_INCOMPLETE" not in codes


def test_non_genai_project_skips_the_model_selection_check(tmp_path):
    """genai_flag=false projects have no GenAI sections by contract, so the check never
    fires for them — the same vague text is silent here."""
    root = _project(tmp_path)
    _write(root, "03-prd.md", _valid_prd() + _MODEL_SECTION_VAGUE, contract_version=3)
    codes = {f.code for f in contracts.validate_artifact(root, "03")}
    assert "MODEL_SELECTION_INCOMPLETE" not in codes


def test_trd_model_serving_check_is_warning_only_and_version_exempt(tmp_path):
    """Stage 08 is validated for the GenAI model-serving gap only: a vague section warns,
    a complete one is clean, and neither path emits CONTRACT_VERSION_MISSING — the TRD
    carries no section contract, so existing TRDs on disk stay quiet."""
    root = _genai_project(tmp_path)
    vague = "# TRD\n## Architecture\nServices.\n## Model Serving & Selection\nA strong model, called per request.\n"
    _write(root, "08-trd.md", vague, contract_version=None)
    findings = contracts.validate_artifact(root, "08")
    assert {f.code for f in findings} == {"MODEL_SERVING_INCOMPLETE"}
    assert contracts.error_count(findings) == 0

    complete = (
        "# TRD\n## Architecture\nServices.\n## Model Serving & Selection\n"
        "| Role | Primary | Fallback chain |\n"
        "Primary is pinned and served from the approved vendor's EU region (quota headroom 3x);\n"
        "fallback to the self-hosted small model on rate limit, outage, or deprecation.\n"
    )
    _write(root, "08-trd.md", complete, contract_version=None)
    assert contracts.validate_artifact(root, "08") == []


def test_missing_genai_sections_are_not_flagged(tmp_path):
    """An absent Model Selection Rationale is not a finding — the GenAI sections are
    appended conditionally, and flagging absence would fail every pre-v3 PRD."""
    root = _genai_project(tmp_path)
    _write(root, "03-prd.md", _valid_prd(), contract_version=3)
    codes = {f.code for f in contracts.validate_artifact(root, "03")}
    assert "MODEL_SELECTION_INCOMPLETE" not in codes
