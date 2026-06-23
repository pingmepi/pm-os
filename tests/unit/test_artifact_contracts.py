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
