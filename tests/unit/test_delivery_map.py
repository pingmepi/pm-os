"""Unit coverage for the shared PRD delivery decomposition (delivery_map.py)."""
import pytest

from delivery_map import build_prd_delivery_map

pytestmark = pytest.mark.unit


_TIERED_PRD = """# PRD

## Product Epics
### EPIC-001 — Core workflow
### EPIC-002 — Later workflow

## User Journeys
### UJ-001 — Mvp journey
Traceability: US-001
### UJ-002 — Deferred journey
Traceability: US-002

## User Stories with Acceptance Criteria
### US-001 — Mvp story
Epic: EPIC-001
Tier: mvp
### US-002 — Later story
Epic: EPIC-002
Tier: v1

## Functional Requirements
- FR-001 — Mvp requirement.
  Epic: EPIC-001
  Tier: mvp
- FR-002 — Later requirement.
  Epic: EPIC-002
  Tier: later
"""


def test_delivery_map_default_keeps_whole_product():
    """Default (no mvp_only) is unchanged — the traceability spine and any
    full-product consumer must still see every tier's stories, requirements,
    journeys, and epics."""
    d = build_prd_delivery_map(_TIERED_PRD)
    assert set(d.story_blocks) == {"US-001", "US-002"}
    assert set(d.requirement_blocks) == {"FR-001", "FR-002"}
    assert set(d.journey_blocks) == {"UJ-001", "UJ-002"}
    assert set(d.epics) == {"EPIC-001", "EPIC-002"}


def test_delivery_map_mvp_only_drops_deferred_and_empty_epics():
    """`mvp_only` scopes the build handoff to the mvp band: deferred (v1/v2/later)
    stories/requirements are dropped, a journey serving only deferred requirements is
    dropped (derived-tier rule), and an epic left with no member is dropped — so the
    Jira export and readable package never turn roadmap-context stubs into build
    tickets/items."""
    d = build_prd_delivery_map(_TIERED_PRD, mvp_only=True)
    assert set(d.story_blocks) == {"US-001"}
    assert set(d.requirement_blocks) == {"FR-001"}
    assert set(d.journey_blocks) == {"UJ-001"}, "deferred-only journey must be dropped"
    assert set(d.epics) == {"EPIC-001"}, "epic with only deferred members must be dropped"
    # Mappings stay internally consistent with the filtered set.
    assert d.story_to_epic == {"US-001": "EPIC-001"}
    assert "US-002" not in d.story_requirements


_UNTAGGED_PRD = """# PRD

## Product Epics
### EPIC-001 — Core workflow
### EPIC-002 — Later workflow

## User Journeys
### UJ-001 — A journey
Traceability: US-001
### UJ-002 — Another journey
Traceability: US-002

## User Stories with Acceptance Criteria
### US-001 — Story one
Epic: EPIC-001
### US-002 — Story two
Epic: EPIC-002

## Functional Requirements
- FR-001 — Requirement one.
  Epic: EPIC-001
- FR-002 — Requirement two.
  Epic: EPIC-002
"""


def test_delivery_map_mvp_only_untagged_prd_is_unchanged():
    """Back-compat: a pre-tiering PRD with no Tier tags has every block default to
    mvp, so mvp_only returns the same set as the default map (nothing dropped)."""
    full = build_prd_delivery_map(_UNTAGGED_PRD)
    mvp = build_prd_delivery_map(_UNTAGGED_PRD, mvp_only=True)
    assert set(mvp.story_blocks) == set(full.story_blocks) == {"US-001", "US-002"}
    assert set(mvp.requirement_blocks) == set(full.requirement_blocks) == {"FR-001", "FR-002"}
    assert set(mvp.journey_blocks) == set(full.journey_blocks) == {"UJ-001", "UJ-002"}
