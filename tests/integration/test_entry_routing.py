"""T2 — pm-new entry routing: scaffold first, then guide new/prototype/enhancement paths."""
import pytest

import yaml

from helpers import read_events, run_script

pytestmark = pytest.mark.integration


def _meta(proj):
    return yaml.safe_load((proj / ".meta.yaml").read_text(encoding="utf-8"))


def test_pm_new_new_route_prints_greenfield_guidance(pmos):
    """--entry new keeps a new-product scaffold and points the PM to stage 01."""
    res = run_script(
        pmos,
        "pm_new.py",
        "route-new",
        "A new product idea",
        "--no-genai",
        "--entry",
        "new",
    )
    proj = pmos.projects / "route-new"

    assert res.returncode == 0, res.stderr
    assert _meta(proj)["project_type"] == "new_product"
    assert "/pm-stage-01-brief" in res.stdout


def test_pm_new_prototype_route_prints_import_guidance(pmos):
    """--entry prototype keeps new_product but records the route and points to context import."""
    res = run_script(
        pmos,
        "pm_new.py",
        "route-prototype",
        "A prototype already exists",
        "--no-genai",
        "--entry",
        "prototype",
    )
    proj = pmos.projects / "route-prototype"
    meta = _meta(proj)

    assert res.returncode == 0, res.stderr
    assert meta["project_type"] == "new_product"
    assert meta["entry_route"] == "prototype"
    assert "/pm-context-import" in res.stdout
    assert "prototype" in res.stdout.lower()


def test_pm_new_enhancement_route_prints_guidance_only(pmos):
    """--entry enhancement reuses today's enhancement scaffold and prints codebase import guidance."""
    res = run_script(
        pmos,
        "pm_new.py",
        "route-enhancement",
        "Improve a live product",
        "--no-genai",
        "--entry",
        "enhancement",
        "--codebase",
        "/tmp/some-repo",
    )
    proj = pmos.projects / "route-enhancement"
    meta = _meta(proj)

    assert res.returncode == 0, res.stderr
    assert meta["project_type"] == "enhancement"
    assert meta["codebase_path"] == "/tmp/some-repo"
    assert "/pm-context-import --codebase" in res.stdout


def test_pm_new_route_recorded_in_telemetry(pmos):
    """project_created telemetry carries the selected entry route."""
    res = run_script(
        pmos,
        "pm_new.py",
        "route-telemetry",
        "A prototype already exists",
        "--no-genai",
        "--entry",
        "prototype",
    )
    proj = pmos.projects / "route-telemetry"

    assert res.returncode == 0, res.stderr
    event = [e for e in read_events(proj) if e["event_type"] == "project_created"][-1]
    assert event["payload"]["entry_route"] == "prototype"


def test_pm_new_noninteractive_defaults_to_new_without_entry(pmos):
    """No tty and no --entry/--mode defaults to the new route and does not hang."""
    res = run_script(
        pmos,
        "pm_new.py",
        "route-default",
        "A new product idea",
        "--no-genai",
    )
    proj = pmos.projects / "route-default"

    assert res.returncode == 0, res.stderr
    assert _meta(proj)["project_type"] == "new_product"
    assert _meta(proj)["entry_route"] == "new"
    assert "/pm-stage-01-brief" in res.stdout
