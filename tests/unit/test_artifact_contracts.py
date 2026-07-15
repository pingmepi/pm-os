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
