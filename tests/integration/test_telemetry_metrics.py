"""T6 — telemetry metrics computed at approval (scripts/pm_approve.py): time-to-approve,
char/normalized edit distance vs the generated snapshot, semantic-distance passthrough, model
capture, and regeneration count. See docs/TESTING.md §5 (T6)."""
import pytest

from helpers import run_script, generate_stage, make_draft, read_events

pytestmark = pytest.mark.integration


def _approved(proj, stage_id):
    evs = [e for e in read_events(proj)
           if e["event_type"] == "stage_approved" and e["stage"] == stage_id]
    assert evs, f"no stage_approved for {stage_id}"
    return evs[-1]["payload"]


def test_time_to_approve_recorded_when_generated(pmos, new_project):
    """Approving a generated stage records a non-null, non-negative time_to_approve_seconds
    (approval timestamp minus the matching stage_generated event)."""
    proj = new_project("m-time", "p")
    generate_stage(proj, "01")
    assert run_script(pmos, "pm_approve.py", "01", cwd=proj).returncode == 0
    tta = _approved(proj, "01")["time_to_approve_seconds"]
    assert tta is not None and tta >= 0


def test_edit_distance_zero_when_unchanged(pmos, new_project):
    """Approving a generated draft unchanged gives edit distance 0 (body == snapshot)."""
    proj = new_project("m-eq", "p")
    generate_stage(proj, "01", body="Stable brief body.\n")
    run_script(pmos, "pm_approve.py", "01", cwd=proj)
    p = _approved(proj, "01")
    assert p["char_edit_distance"] == 0 and p["normalized_edit_distance"] == 0


def test_edit_distance_positive_when_edited(pmos, new_project):
    """Editing the draft before approval yields a positive edit distance vs the snapshot."""
    proj = new_project("m-edit", "p")
    generate_stage(proj, "01", body="Original brief body.\n")
    (proj / "01-brief.md").write_text(
        (proj / "01-brief.md").read_text() + "\nSubstantial PM additions here.\n", encoding="utf-8")
    run_script(pmos, "pm_approve.py", "01", cwd=proj)
    assert _approved(proj, "01")["char_edit_distance"] > 0


def test_metrics_null_without_generation_snapshot(pmos, new_project):
    """Stages with no generation event/snapshot (e.g. the business statement) keep timing and
    edit-distance metrics null — expected, not a gap."""
    proj = new_project("m-null", "p")
    p = run_script(pmos, "pm_approve.py", "00", cwd=proj)
    assert p.returncode == 0
    pay = _approved(proj, "00")
    assert pay["time_to_approve_seconds"] is None
    assert pay["char_edit_distance"] is None and pay["normalized_edit_distance"] is None


def test_semantic_distance_passthrough_and_validation(pmos, new_project):
    """--semantic-distance is recorded verbatim in the payload; an out-of-range value is
    rejected without approving."""
    proj = new_project("m-sem", "p")
    generate_stage(proj, "01")
    assert run_script(pmos, "pm_approve.py", "01", "--semantic-distance", "0.25", cwd=proj).returncode == 0
    assert _approved(proj, "01")["semantic_distance"] == 0.25

    generate_stage(proj, "02")
    bad = run_script(pmos, "pm_approve.py", "02", "--semantic-distance", "1.5", cwd=proj)
    assert bad.returncode != 0  # rejected, 0..1 only


def test_model_and_tier_captured(pmos, new_project):
    """stage_generated records the model id, and model_tier is derived from config — a
    deep-reasoning stage (03) resolves to 'deep-reasoning'."""
    proj = new_project("m-model", "p")
    generate_stage(proj, "03", model="claude-opus-4-8")
    gen = [e for e in read_events(proj) if e["event_type"] == "stage_generated" and e["stage"] == "03"][-1]
    assert gen["payload"]["model"] == "claude-opus-4-8"
    assert gen["payload"]["model_tier"] == "deep-reasoning"


def test_regeneration_count_in_approval_payload(pmos, new_project):
    """The approval payload carries the stage's regeneration_count from meta."""
    import project
    proj = new_project("m-regen", "p")
    generate_stage(proj, "04")
    meta = project.load_meta(proj)
    project.get_stage(meta, "04")["regeneration_count"] = 3
    project.save_meta(meta, proj)
    run_script(pmos, "pm_approve.py", "04", cwd=proj)
    assert _approved(proj, "04")["regeneration_count"] == 3
