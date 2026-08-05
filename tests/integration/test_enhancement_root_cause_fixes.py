"""Regression tests for the E2 root-cause fixes (Codex #1-4 + the 4a delta gap).

- Non-Git codebase is not falsely reported as repository drift (shared fingerprint).
- The delta surfaces a stage authored *during* the enhancement (no baseline) and
  recognizes ordered-list / bare-line / bold stable-id forms (canonical splitter).
- A removed baseline ref is recordable and never re-synthesized on re-export.
- An enhancement blocks product stages until the affected-slice boundary is recorded.
"""
import json
import subprocess
from pathlib import Path

import pytest
import yaml

from helpers import make_draft, run_hook, run_script, write_artifact

pytestmark = pytest.mark.integration


def _record_boundary(proj: Path, **overrides) -> None:
    context_path = proj / ".enhancements" / "EH-001" / "context.yaml"
    context = yaml.safe_load(context_path.read_text(encoding="utf-8"))
    boundary = {
        "recorded_at": "2026-08-03T00:00:00+00:00",
        "current_behavior": "before", "target_behavior": "after",
        "affected_surfaces": ["service"], "affected_ids": [],
        "regression_invariants": [], "non_touch_surfaces": [],
    }
    boundary.update(overrides)
    context["boundary"].update(boundary)
    context_path.write_text(yaml.safe_dump(context, sort_keys=False), encoding="utf-8")


def _set_approved(proj: Path, stage_id: str, filename: str, body: str) -> None:
    import frontmatter
    import project
    from hashing import hash_artifact_body

    path = write_artifact(proj / filename, stage=stage_id, project=proj.name, body=body)
    content_hash = hash_artifact_body(str(path))
    frontmatter.update_status(
        str(path), "approved", approved_at="2026-08-03T00:00:00+00:00",
        approved_by="tester", content_hash=content_hash,
    )
    meta = project.load_meta(proj)
    stage = project.get_stage(meta, stage_id)
    stage.update({
        "status": "approved", "approved_at": "2026-08-03T00:00:00+00:00",
        "content_hash": content_hash,
    })
    project.save_meta(meta, proj)


# --- Codex #1: a non-Git codebase must not read as drift ---------------------

def test_nongit_codebase_is_not_reported_as_repository_drift(pmos, new_project, tmp_path):
    """An unchanged non-Git codebase recomputes to the same fallback fingerprint,
    so /pm-check must not flag ENHANCEMENT_REPOSITORY_DRIFT (shared fingerprint +
    the removed `actual_sha is None` false-positive)."""
    plain = tmp_path / "plaincode"  # a directory, deliberately NOT a git checkout
    plain.mkdir()
    (plain / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    proj = new_project("nongit-enh")
    assert run_script(pmos, "pm_approve.py", "00", cwd=proj).returncode == 0
    ask = proj / "ask.md"
    ask.write_text("Change the non-git app.\n", encoding="utf-8")
    started = run_script(
        pmos, "pm_enhance.py", "start", "--ask-file", str(ask), "--codebase", str(plain), cwd=proj,
    )
    assert started.returncode == 0, started.stderr
    _record_boundary(proj)

    result = run_script(pmos, "pm_check.py", cwd=proj)

    assert "ENHANCEMENT_REPOSITORY_DRIFT" not in result.stdout, result.stdout


# --- 4a + Codex #2: from-scratch stage, mixed declaration forms --------------

FROM_SCRATCH_PRD = """## Functional Requirements

### FR-001 — Heading form
Change type: new
Export accounts as CSV.

1. FR-002 — Ordered-list form
Change type: new
Add a download button.

FR-003 — Bare-line form
Change type: new
Record export latency.
"""


def test_delta_surfaces_from_scratch_stage_with_all_declaration_forms(pmos, new_project):
    """An external-product PRD authored *during* the enhancement (never in the
    frozen baseline) is all-`new`, and heading / ordered-list / bare-line forms
    each yield a fine-grained FR change instead of one coarse STAGE-03 blob."""
    proj = new_project("fromscratch-enh")
    assert run_script(pmos, "pm_approve.py", "00", cwd=proj).returncode == 0
    ask = proj / "ask.md"
    ask.write_text("Add order CSV export.\n", encoding="utf-8")
    # Baseline captures only stage 00 — there is no prior PRD.
    started = run_script(pmos, "pm_enhance.py", "start", "--ask-file", str(ask), cwd=proj)
    assert started.returncode == 0, started.stderr
    _record_boundary(proj, affected_ids=["FR-001", "FR-002", "FR-003"])
    # Author + approve stage 03 as part of the enhancement (from scratch).
    _set_approved(proj, "03", "03-prd.md", FROM_SCRATCH_PRD)

    result = run_script(pmos, "pm_enhance.py", "delta", "--json", cwd=proj)

    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    by_id = {c["id"]: c for c in data["changes"]}
    assert {"FR-001", "FR-002", "FR-003"}.issubset(by_id), data["changes"]
    assert all(by_id[fid]["change_type"] == "new" for fid in ("FR-001", "FR-002", "FR-003"))
    assert all(by_id[fid]["stage"] == "03" for fid in ("FR-001", "FR-002", "FR-003"))
    assert "STAGE-03" not in by_id  # never collapsed to a coarse stage blob


# --- Codex #4: removed ref recordable + not duplicated on re-export ----------

BASELINE_PRD = """## Product Epics
### EPIC-001 — Core
Outcome: Core.
## User Stories with Acceptance Criteria
### US-001 — Core
Epic: EPIC-001
Implements FR-001.
## Functional Requirements
- **FR-001 (must):** Keep core.
  - Epic: EPIC-001
- **FR-003 (should):** Legacy switch to retire.
  - Epic: EPIC-001
"""

CURRENT_PRD = """## Product Epics
### EPIC-001 — Core
Outcome: Core.
## User Stories with Acceptance Criteria
### US-001 — Core
Epic: EPIC-001
Implements FR-001.
## Functional Requirements
- **FR-001 (must):** Keep core.
  - Epic: EPIC-001
"""


def _removal_project(pmos, new_project):
    proj = new_project("removal-enh", "Retire the legacy switch.")
    assert run_script(pmos, "pm_approve.py", "00", cwd=proj).returncode == 0
    make_draft(proj, "03", body=BASELINE_PRD)
    assert run_script(pmos, "pm_approve.py", "03", cwd=proj).returncode == 0
    ask = proj / "ask.md"
    ask.write_text("Remove the legacy switch (FR-003).\n", encoding="utf-8")
    assert run_script(pmos, "pm_enhance.py", "start", "--ask-file", str(ask), cwd=proj).returncode == 0
    _record_boundary(proj, affected_ids=["FR-003"], current_behavior="legacy", target_behavior="removed")
    make_draft(proj, "03", body=CURRENT_PRD)
    assert run_script(pmos, "pm_approve.py", "03", cwd=proj).returncode == 0
    return proj


def test_removed_ref_is_recorded_and_not_re_synthesized(pmos, new_project):
    """A removed baseline FR gets a removal ticket; once its key is recorded, a
    later plan must not create a duplicate removal ticket for it."""
    proj = _removal_project(pmos, new_project)

    first = run_script(pmos, "pm_handoff.py", "plan", cwd=proj)
    assert first.returncode == 0, first.stderr
    plan = json.loads((proj / "handoff" / "jira-plan.json").read_text(encoding="utf-8"))
    assert any(item["ref"] == "FR-003" and item["change_type"] == "removed" for item in plan["items"])

    # Record the created key for the removed ref, then re-plan.
    recorded = run_script(pmos, "pm_handoff.py", "record", cwd=proj, stdin='{"FR-003": "RA-9"}')
    assert recorded.returncode == 0, recorded.stderr
    assert "FR-003" in recorded.stdout  # recorded, not skipped as unknown

    second = run_script(pmos, "pm_handoff.py", "plan", cwd=proj)
    assert second.returncode == 0, second.stderr
    plan2 = json.loads((proj / "handoff" / "jira-plan.json").read_text(encoding="utf-8"))
    assert not any(item["ref"] == "FR-003" for item in plan2["items"]), "removal ticket re-synthesized"


# --- Fix #6: mandatory boundary gate for enhancement product stages ----------

def test_enhancement_product_stage_blocks_until_boundary_recorded(pmos):
    """A product stage in an enhancement is gated on a recorded affected-slice
    boundary; recording it clears the boundary gate."""
    created = run_script(pmos, "pm_new.py", "gate-enh", "Enhance the product", "--no-genai", "--entry", "enhancement")
    assert created.returncode == 0, created.stderr
    proj = pmos.projects / "gate-enh"
    assert run_script(pmos, "pm_approve.py", "00", cwd=proj).returncode == 0

    blocked = run_hook(pmos, "pre-stage.py", "01", proj)
    assert blocked.returncode != 0
    assert "record the affected slice" in blocked.stderr

    # Start the cycle and record the boundary; the boundary gate no longer fires.
    ask = proj / "ask.md"
    ask.write_text("Add a capability.\n", encoding="utf-8")
    assert run_script(pmos, "pm_enhance.py", "start", "--ask-file", str(ask), cwd=proj).returncode == 0
    _record_boundary(proj)
    after = run_hook(pmos, "pre-stage.py", "01", proj)
    assert "record the affected slice" not in after.stderr
