"""T3 — documentation/spec drift: stable facts asserted from the code's own source-of-truth
constants, so docs/reference and code can't silently diverge. See docs/guides/testing.md §5 (T3)."""
import pytest

import project
import config
from helpers import REPO_ROOT, stage_skill_dir

pytestmark = pytest.mark.contract


def test_stage_order_shape():
    """The pipeline shape is the documented one: stage-00 understanding group leads, then the
    seven core stages, then the optional capstones."""
    assert project.STAGE_ORDER[:4] == ["00", "00c", "00w", "00u"]
    assert project.CORE_STAGE_ORDER == ["01", "02", "03", "04", "05", "06", "07"]
    assert project.STAGE_ORDER[-2:] == ["08", "09"]


def test_every_pipeline_stage_has_a_skill():
    """Code↔skills: every core + capstone stage id has a matching skill directory."""
    for sid in project.CORE_STAGE_ORDER + ["08", "09"]:
        assert stage_skill_dir(sid).is_dir(), f"no skill for stage {sid}"


def test_model_policy_constant():
    """The model policy is the documented one: default standard; deep-reasoning for the
    context-build docs (00w/00u), PRD/design/QA/TRD/roadmap (03/04/06/08/09)."""
    assert config.DEFAULT_MODEL_TIER == "standard"
    assert config.DEEP_REASONING_STAGES == ["00w", "00u", "03", "04", "06", "08", "09"]


def test_spec_event_list_covers_emitted_events():
    """The spec's telemetry event list documents the events the code actually emits — guards
    against the spec going stale when an event type is added."""
    spec = (REPO_ROOT / "docs" / "reference" / "pm-os-spec.md").read_text()
    for event in ("stage_started", "stage_generated", "stage_approved", "stage_imported",
                  "stage_backfilled", "context_ingested", "stage_edited_via_note",
                  "artifact_validation_warning", "feedback_submitted", "stage_marked_stale"):
        assert event in spec, f"reference/pm-os-spec.md does not document event '{event}'"


def test_architecture_documents_runtime_paths():
    """ARCHITECTURE.md records the canonical runtime/sync paths the installer/updater use."""
    arch = (REPO_ROOT / "ARCHITECTURE.md").read_text()
    assert "~/.claude/skills" in arch
    assert "~/.agents/skills" in arch
    assert "~/.pm-os/hooks" in arch
