"""Unit tests for lib/telemetry.py — the append-only, hash-chained event log that is the
audit/diagnosis backbone. The chain must be tamper-evident and queryable. See docs/guides/testing.md §5 (T1)."""
import json

import pytest

import telemetry

pytestmark = pytest.mark.unit


def _project(tmp_path, slug="demo"):
    (tmp_path / ".meta.yaml").write_text(
        f"project_slug: {slug}\npm_os_version: 0.0.0-test\nstages: []\n", encoding="utf-8")
    return tmp_path


def test_log_appends_chained_events(tmp_path):
    """Each logged event appends one JSONL line and links prev_event_hash→event_hash, and
    the payload is preserved verbatim."""
    root = _project(tmp_path)
    telemetry.log("stage_started", root, "01", {})
    telemetry.log("stage_generated", root, "01", {"model": "claude-opus-4-8"})
    lines = [json.loads(l) for l in (root / "telemetry.jsonl").read_text().splitlines() if l.strip()]
    assert len(lines) == 2
    assert lines[0]["prev_event_hash"] is None
    assert lines[1]["prev_event_hash"] == lines[0]["event_hash"]
    assert lines[1]["payload"]["model"] == "claude-opus-4-8"


def test_last_event_filters(tmp_path):
    """last_event returns the most recent event matching the type/stage filter (used e.g.
    to find the matching stage_generated when computing time-to-approve)."""
    root = _project(tmp_path)
    telemetry.log("stage_started", root, "01", {})
    telemetry.log("stage_generated", root, "01", {"n": 1})
    telemetry.log("stage_generated", root, "02", {"n": 2})
    assert telemetry.last_event(root, "stage_generated", "01")["payload"]["n"] == 1
    assert telemetry.last_event(root, "stage_generated")["payload"]["n"] == 2
    assert telemetry.last_event(root, "nonexistent") is None


def test_verify_chain_ok_and_tamper(tmp_path):
    """An intact chain verifies ok; tampering with a middle event's payload is detected and
    reported with the 1-based break line and a reason — the integrity guarantee."""
    root = _project(tmp_path)
    for et in ("stage_started", "stage_generated", "stage_approved"):
        telemetry.log(et, root, "01", {})
    assert telemetry.verify_chain(root)["ok"] is True

    path = root / "telemetry.jsonl"
    lines = path.read_text().splitlines()
    d = json.loads(lines[1]); d["payload"]["x"] = "tampered"; lines[1] = json.dumps(d)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    res = telemetry.verify_chain(root)
    assert res["ok"] is False
    assert res["break_at"] == 2
    assert res["reason"]


def test_verify_chain_no_file(tmp_path):
    """A project with no telemetry file verifies ok with 0 events (absence is not corruption)."""
    res = telemetry.verify_chain(_project(tmp_path))
    assert res["ok"] is True
    assert res["events"] == 0
