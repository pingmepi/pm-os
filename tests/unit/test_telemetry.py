import json

import pytest

import telemetry

pytestmark = pytest.mark.unit


def _project(tmp_path, slug="demo"):
    (tmp_path / ".meta.yaml").write_text(
        f"project_slug: {slug}\npm_os_version: 0.0.0-test\nstages: []\n", encoding="utf-8")
    return tmp_path


def test_log_appends_chained_events(tmp_path):
    root = _project(tmp_path)
    telemetry.log("stage_started", root, "01", {})
    telemetry.log("stage_generated", root, "01", {"model": "claude-opus-4-8"})
    lines = [json.loads(l) for l in (root / "telemetry.jsonl").read_text().splitlines() if l.strip()]
    assert len(lines) == 2
    assert lines[0]["prev_event_hash"] is None
    assert lines[1]["prev_event_hash"] == lines[0]["event_hash"]
    assert lines[1]["payload"]["model"] == "claude-opus-4-8"


def test_last_event_filters(tmp_path):
    root = _project(tmp_path)
    telemetry.log("stage_started", root, "01", {})
    telemetry.log("stage_generated", root, "01", {"n": 1})
    telemetry.log("stage_generated", root, "02", {"n": 2})
    assert telemetry.last_event(root, "stage_generated", "01")["payload"]["n"] == 1
    assert telemetry.last_event(root, "stage_generated")["payload"]["n"] == 2
    assert telemetry.last_event(root, "nonexistent") is None


def test_verify_chain_ok_and_tamper(tmp_path):
    root = _project(tmp_path)
    for et in ("stage_started", "stage_generated", "stage_approved"):
        telemetry.log(et, root, "01", {})
    assert telemetry.verify_chain(root)["ok"] is True

    # Tamper with the middle event's payload.
    path = root / "telemetry.jsonl"
    lines = path.read_text().splitlines()
    d = json.loads(lines[1]); d["payload"]["x"] = "tampered"; lines[1] = json.dumps(d)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    res = telemetry.verify_chain(root)
    assert res["ok"] is False
    assert res["break_at"] == 2
    assert res["reason"]


def test_verify_chain_no_file(tmp_path):
    res = telemetry.verify_chain(_project(tmp_path))
    assert res["ok"] is True
    assert res["events"] == 0
