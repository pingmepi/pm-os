"""E2 same-project enhancement lifecycle and immutable baseline capture."""
import hashlib
import os
from pathlib import Path

import pytest
import yaml

from helpers import read_events, run_script

pytestmark = pytest.mark.integration


def _approve_statement(pmos, proj):
    result = run_script(pmos, "pm_approve.py", "00", cwd=proj)
    assert result.returncode == 0, result.stdout + result.stderr


def _write_ask(proj: Path, text: str = "Add account export without changing login.\n") -> Path:
    path = proj / "enhancement-ask.md"
    path.write_text(text, encoding="utf-8")
    return path


def _load(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_start_captures_approved_baseline_and_preserves_project_identity(pmos, new_project):
    """Starting E2 snapshots approved artifacts and never flips project_type."""
    proj = new_project("native-product")
    _approve_statement(pmos, proj)
    before_meta = _load(proj / ".meta.yaml")
    ask = _write_ask(proj)

    result = run_script(pmos, "pm_enhance.py", "start", "--ask-file", str(ask), cwd=proj)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "EH-001" in result.stdout
    index = _load(proj / ".enhancements" / "index.yaml")
    context = _load(proj / ".enhancements" / "EH-001" / "context.yaml")
    after_meta = _load(proj / ".meta.yaml")
    assert index["active_cycle"] == "EH-001"
    assert index["cycles"] == ["EH-001"]
    assert index["next_sequence"] == 2
    assert context["id"] == "EH-001"
    assert context["previous_cycle_id"] is None
    assert context["completed_at"] is None
    assert context["ask"]["sha256"] == hashlib.sha256(ask.read_bytes()).hexdigest()
    assert (proj / context["ask"]["snapshot_path"]).read_text() == ask.read_text()
    baseline = context["baseline"]["artifacts"]["00"]
    assert baseline["status"] == "approved"
    assert (proj / baseline["snapshot_path"]).exists()
    assert baseline["content_hash"] == before_meta["stages"][0]["content_hash"]
    assert after_meta["project_type"] == before_meta["project_type"] == "new_product"
    assert after_meta["entry_route"] == before_meta["entry_route"] == "new"


def test_start_is_idempotent_for_same_ask_and_refuses_different_active_cycle(pmos, new_project):
    """A retry returns the active cycle, while different work cannot overwrite it."""
    proj = new_project("retry-product")
    _approve_statement(pmos, proj)
    ask = _write_ask(proj)
    first = run_script(pmos, "pm_enhance.py", "start", "--ask-file", str(ask), cwd=proj)
    assert first.returncode == 0

    retry = run_script(pmos, "pm_enhance.py", "start", "--ask-file", str(ask), cwd=proj)
    assert retry.returncode == 0
    assert "already active" in retry.stdout

    other = _write_ask(proj, "Replace the billing provider.\n")
    refused = run_script(pmos, "pm_enhance.py", "start", "--ask-file", str(other), cwd=proj)
    assert refused.returncode != 0
    assert "active enhancement" in (refused.stdout + refused.stderr).lower()
    index = _load(proj / ".enhancements" / "index.yaml")
    assert index["cycles"] == ["EH-001"]


def test_start_records_enhancement_telemetry_without_stage_state(pmos, new_project):
    """Enhancement lifecycle emits provenance but adds no approval/status state."""
    proj = new_project("telemetry-product")
    _approve_statement(pmos, proj)
    ask = _write_ask(proj)

    result = run_script(pmos, "pm_enhance.py", "start", "--ask-file", str(ask), cwd=proj)

    assert result.returncode == 0
    context = _load(proj / ".enhancements" / "EH-001" / "context.yaml")
    assert "status" not in context
    assert "approved" not in context
    event = [event for event in read_events(proj) if event["event_type"] == "enhancement_started"][-1]
    assert event["stage"] is None
    assert event["payload"]["cycle_id"] == "EH-001"
    assert event["payload"]["baseline_artifact_ids"] == ["00"]


def test_stale_lock_without_live_owner_is_reclaimed(pmos, new_project):
    """A leftover lock from a crashed op does not wedge future lifecycle work."""
    proj = new_project("stale-lock-product")
    _approve_statement(pmos, proj)
    ask = _write_ask(proj)
    lock = proj / ".enhancements" / ".lock"
    lock.mkdir(parents=True)
    # No owner file: the shape a crash between mkdir and the owner-write leaves.

    result = run_script(pmos, "pm_enhance.py", "start", "--ask-file", str(ask), cwd=proj)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "EH-001" in result.stdout
    assert not lock.exists()


def test_live_lock_owner_blocks_concurrent_lifecycle_op(pmos, new_project):
    """A lock whose recorded owner is still running is respected, not stolen."""
    proj = new_project("live-lock-product")
    _approve_statement(pmos, proj)
    ask = _write_ask(proj)
    lock = proj / ".enhancements" / ".lock"
    lock.mkdir(parents=True)
    (lock / "owner").write_text(str(os.getpid()), encoding="utf-8")  # this test process is alive

    result = run_script(pmos, "pm_enhance.py", "start", "--ask-file", str(ask), cwd=proj)

    assert result.returncode != 0
    assert "already running" in (result.stdout + result.stderr).lower()
    assert not (proj / ".enhancements" / "index.yaml").exists()
