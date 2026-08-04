"""Unit tests for lib/delivery_map.py title extraction — specifically that an entity
title carries no stray Markdown emphasis into filenames, headings, or Jira summaries.
See docs/guides/testing.md §5 (T1)."""
import pytest

from delivery_map import normalize_title, title_of

pytestmark = pytest.mark.unit


def test_normalize_title_drops_dangling_bold_marker():
    """A bold-wrapped declaration whose opening ** is consumed with the id leaves a
    mid-string dangling ** that edge-only strip("*") can't reach; normalize_title clears
    it so the title is plain text (PMOS-011)."""
    assert normalize_title("Explainability, Compliance & Resilience** (cross-cutting)") == \
        "Explainability, Compliance & Resilience (cross-cutting)"


def test_normalize_title_preserves_snake_case_and_ampersands():
    """Only doubled underscores are emphasis, so snake_case tokens and `&` survive."""
    assert normalize_title("feature_flag rollout & audit") == "feature_flag rollout & audit"


def test_title_of_epic_strips_bold_wrapped_declaration():
    """title_of on a real bold-wrapped EPIC declaration yields a clean title with no
    unbalanced markup — the exact PMOS-011 shape that had propagated to handoff filenames,
    headings, and the Jira plan."""
    block = "### **EPIC-008: Explainability, Compliance & Resilience** (cross-cutting)\nEpic body.\n"
    assert title_of("EPIC-008", block) == "Explainability, Compliance & Resilience (cross-cutting)"


def test_title_of_falls_back_to_id_when_titleless():
    """A declaration with no human title after the id falls back to the id itself."""
    assert title_of("EPIC-009", "### EPIC-009\n") == "EPIC-009"
