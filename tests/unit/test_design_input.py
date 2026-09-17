"""Unit tests for external design-authority design-in validation."""

import pytest

from design_input import design_error_count, state_node_url, validate_design_data

pytestmark = pytest.mark.unit


def _fixture_data() -> dict:
    return {
        "ia_format_version": 1,
        "figma": {
            "file_key": "abc123",
            "file_url": "https://www.figma.com/design/abc123/File",
            "version": "1",
            "design_system": ["Core"],
        },
        "screens": [
            {
                "name": "Review queue",
                "node_id": "1:1",
                "node_url": "https://www.figma.com/design/abc123/File?node-id=1-1",
                "purpose": "Queue",
                "serves": ["US-001", "FR-001", "UJ-001"],
                "data_fields": ["asset_id", "status"],
                "components": ["DataTable"],
                "states": [
                    {"name": "default", "node_id": "1:1", "trigger": "Landing", "transient": False},
                    {"name": "loading", "node_id": "1:2", "trigger": "Fetch", "transient": True},
                ],
            }
        ],
        "flows": [
            {
                "journey": "UJ-001",
                "sequence": [
                    {"screen": "Review queue", "state": "loading"},
                    {"screen": "Review queue", "state": "default"},
                ],
            }
        ],
        "components": {"reused": ["DataTable"], "new": []},
        "tokens": {"collections_used": ["Core"], "outside_system": []},
        "excluded_frames": [{"name": "Scratch", "node_id": "9:9", "reason": "scratch"}],
        "open_questions": ["Confirm focus target."],
    }


def _prd() -> str:
    return """## Product Epics
### EPIC-001 - Review
**Outcome:** Review.
**Scope:** Queue.
**Success signal:** Done.
## User Journeys
### UJ-001 - Review queue
Traceability: US-001, FR-001.
## User Stories with Acceptance Criteria
### US-001 - Review asset
Epic: EPIC-001
Traceability: UJ-001, FR-001.
## Functional Requirements
FR-001 - Show assigned assets.
Epic: EPIC-001
"""


def _brief() -> str:
    return """## Input Behavior Reconciliation
### Required state inventory
| # | Serves | State | Trigger |
|---|---|---|---|
| 1 | US-001, FR-001 | Queue - default | Landing |
| 2 | US-001, FR-001 | Queue - loading | Fetch |

### Data fields per requirement
**US-001 - Review asset**
| Field | Type | Mandatory |
|---|---|---|
| asset_id | string | yes |
| status | enum | yes |
"""


def test_valid_design_input_has_warning_only_open_question():
    findings = validate_design_data(_fixture_data(), prd_body=_prd(), brief_body=_brief())
    assert design_error_count(findings) == 0
    assert [finding.code for finding in findings] == ["DESIGN_OPEN_QUESTION"]


def test_rejects_unsupported_version():
    data = _fixture_data()
    data["ia_format_version"] = 2
    codes = {finding.code for finding in validate_design_data(data, prd_body=_prd(), brief_body=_brief())}
    assert "DESIGN_INPUT_VERSION_UNSUPPORTED" in codes


def test_rejects_unknown_flow_state():
    data = _fixture_data()
    data["flows"][0]["sequence"].append({"screen": "Review queue", "state": "empty"})
    codes = {finding.code for finding in validate_design_data(data, prd_body=_prd(), brief_body=_brief())}
    assert "DESIGN_FLOW_STATE_UNKNOWN" in codes


def test_rejects_missing_required_field_coverage():
    brief = _brief().replace("| status | enum | yes |\n", "| owner | string | yes |\n")
    codes = {finding.code for finding in validate_design_data(_fixture_data(), prd_body=_prd(), brief_body=brief)}
    assert "DESIGN_FIELD_COVERAGE_MISSING" in codes


def test_default_state_can_share_screen_node_id_but_other_duplicates_fail():
    data = _fixture_data()
    findings = validate_design_data(data, prd_body=_prd(), brief_body=_brief())
    assert "DESIGN_NODE_ID_DUPLICATE" not in {finding.code for finding in findings}

    data["screens"][0]["states"].append({"name": "empty", "node_id": "1:2", "trigger": "None", "transient": False})
    codes = {finding.code for finding in validate_design_data(data, prd_body=_prd(), brief_body=_brief())}
    assert "DESIGN_NODE_ID_DUPLICATE" in codes


def test_state_node_url_builds_canonical_figma_deep_link():
    assert state_node_url("https://www.figma.com/design/abc123/File", "12:340") == (
        "https://www.figma.com/design/abc123/File?node-id=12-340"
    )
