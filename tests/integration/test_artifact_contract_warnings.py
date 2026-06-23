"""Integration coverage for warning-only artifact validation at PM entrypoints."""
import pytest

import frontmatter
from helpers import make_draft, read_events, run_script

pytestmark = pytest.mark.integration


def test_approval_warns_records_and_continues(pmos, new_project):
    proj = new_project("contract-approve", "A problem")
    make_draft(proj, "03", body="## Overview\nIncomplete PRD.\n")
    res = run_script(pmos, "pm_approve.py", "03", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert "artifact contract findings" in res.stdout
    assert "USER_JOURNEY_MISSING" in res.stdout
    events = read_events(proj)
    assert any(event["event_type"] == "artifact_validation_warning" for event in events)
    assert any(event["event_type"] == "stage_approved" and event["stage"] == "03" for event in events)


def test_import_approval_warns_and_continues(pmos, new_project):
    proj = new_project("contract-import", "A problem")
    make_draft(proj, "03", body="## Overview\nImported PRD without journeys.\n")
    res = run_script(
        pmos, "pm_context_import.py", "commit", "03", "--kind", "imported",
        "--status", "approved", "--source-name", "source-prd.md", "--source-format", "md",
        cwd=proj,
    )
    assert res.returncode == 0, res.stderr
    assert "import approval will continue" in res.stdout
    events = read_events(proj)
    warning = next(event for event in events if event["event_type"] == "artifact_validation_warning")
    assert warning["payload"]["origin"] == "imported"


def test_status_surfaces_contract_warning_count(pmos, new_project):
    proj = new_project("contract-status", "A problem")
    path = make_draft(proj, "03", body="## Overview\nIncomplete PRD.\n")
    fm, body = frontmatter.read(str(path))
    fm["artifact_contract_version"] = 1
    frontmatter.write(str(path), fm, body)
    res = run_script(pmos, "pm_status.py", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert "contract warnings:" in res.stdout


def test_validator_cli_strict_fails_and_warn_mode_succeeds(pmos, new_project):
    proj = new_project("contract-cli", "A problem")
    make_draft(proj, "03", body="## Overview\nIncomplete PRD.\n")
    strict = run_script(pmos, "pm_validate_artifact.py", "03", "--mode", "strict", cwd=proj)
    warn = run_script(pmos, "pm_validate_artifact.py", "03", "--mode", "warn", cwd=proj)
    assert strict.returncode != 0
    assert warn.returncode == 0
    assert "USER_JOURNEY_MISSING" in strict.stdout
