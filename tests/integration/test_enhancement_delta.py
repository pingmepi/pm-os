"""E2 canonical-artifact baseline versus current stable-ID delta."""
import json
from pathlib import Path

import pytest
import yaml

from helpers import run_script, write_artifact

pytestmark = pytest.mark.integration


BASELINE_PRD = """## Functional Requirements

### FR-001 — Existing login
Existing login remains unchanged.

### FR-002 — Account response
Accounts return an on-screen summary.

### FR-004 — Legacy CSV endpoint
The legacy endpoint returns CSV.
"""

CURRENT_PRD = """## Functional Requirements

### FR-001 — Existing login
Existing login remains unchanged.

### FR-002 — Account response
Change type: modified
Current behavior: Accounts return an on-screen summary.
Target behavior: Accounts can also return a JSON export.
Affected surfaces: api, data

### FR-003 — Export permission
Change type: new
Authorized users may request their own export.
Affected surfaces: api
"""


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


def test_delta_emits_only_changed_blocks_with_computed_change_types(pmos, new_project):
    """Unchanged stable IDs stay out; modified/new/removed IDs carry exact evidence."""
    proj = new_project("delta-product")
    approved = run_script(pmos, "pm_approve.py", "00", cwd=proj)
    assert approved.returncode == 0
    _set_approved(proj, "03", "03-prd.md", BASELINE_PRD)
    ask = proj / "ask.md"
    ask.write_text("Add JSON account export and remove legacy CSV.\n", encoding="utf-8")
    started = run_script(pmos, "pm_enhance.py", "start", "--ask-file", str(ask), cwd=proj)
    assert started.returncode == 0
    context_path = proj / ".enhancements" / "EH-001" / "context.yaml"
    context = yaml.safe_load(context_path.read_text(encoding="utf-8"))
    context["boundary"].update({
        "recorded_at": "2026-08-03T00:00:00+00:00", "current_behavior": "legacy export",
        "target_behavior": "JSON export", "affected_surfaces": ["api"],
        "affected_ids": ["FR-002", "FR-003", "FR-004"],
    })
    context_path.write_text(yaml.safe_dump(context, sort_keys=False), encoding="utf-8")
    _set_approved(proj, "03", "03-prd.md", CURRENT_PRD)

    result = run_script(pmos, "pm_enhance.py", "delta", "--json", cwd=proj)

    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(result.stdout)
    changes = {(item["id"], item["change_type"]): item for item in data["changes"]}
    assert set(changes) == {
        ("FR-002", "modified"), ("FR-003", "new"), ("FR-004", "removed")
    }
    assert "FR-001" not in {item["id"] for item in data["changes"]}
    assert changes[("FR-002", "modified")]["declared_change_type"] == "modified"
    assert changes[("FR-003", "new")]["declared_change_type"] == "new"
    assert changes[("FR-004", "removed")]["after"] is None
    assert data["unexpected_changed_ids"] == []
    assert data["baseline_cycle"] == "EH-001"


def test_delta_flags_changed_ids_outside_approved_boundary(pmos, new_project):
    """A changed stable ID outside the boundary is surfaced rather than silently exported."""
    proj = new_project("unexpected-delta")
    approved = run_script(pmos, "pm_approve.py", "00", cwd=proj)
    assert approved.returncode == 0
    _set_approved(proj, "03", "03-prd.md", BASELINE_PRD)
    ask = proj / "ask.md"
    ask.write_text("Modify account response only.\n", encoding="utf-8")
    assert run_script(pmos, "pm_enhance.py", "start", "--ask-file", str(ask), cwd=proj).returncode == 0
    context_path = proj / ".enhancements" / "EH-001" / "context.yaml"
    context = yaml.safe_load(context_path.read_text(encoding="utf-8"))
    context["boundary"].update({
        "recorded_at": "2026-08-03T00:00:00+00:00", "current_behavior": "legacy export",
        "target_behavior": "updated response", "affected_surfaces": ["api"],
        "affected_ids": ["FR-002"],
    })
    context_path.write_text(yaml.safe_dump(context, sort_keys=False), encoding="utf-8")
    _set_approved(proj, "03", "03-prd.md", CURRENT_PRD)

    result = run_script(pmos, "pm_enhance.py", "delta", "--json", cwd=proj)

    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["unexpected_changed_ids"] == ["FR-003", "FR-004"]
