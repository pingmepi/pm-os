"""Unit tests for lib/config.py — config load + the model-tier policy that keeps skill
telemetry in lockstep with deep_reasoning_stages. See docs/TESTING.md §5 (T1)."""
import pytest

import config

pytestmark = pytest.mark.unit


def test_load_config_reads_temp_install(pmos):
    """load_config reads the isolated temp config and applies model-policy defaults."""
    cfg = config.load_config()
    assert cfg["pm_user"] == "tester"
    assert cfg["projects_dir"] == str(pmos.projects)
    assert cfg["default_model_tier"] == "standard"
    assert "03" in cfg["deep_reasoning_stages"]


def test_model_tier_for_stage(pmos):
    """Deep-reasoning stages (03/06/08) resolve to 'deep-reasoning'; all others to the
    configured default — the single source of truth skills derive their tier from."""
    for deep in ("03", "06", "08"):
        assert config.model_tier_for_stage(deep) == "deep-reasoning"
    for std in ("01", "02", "04", "05", "07", "09"):
        assert config.model_tier_for_stage(std) == "standard"


def test_model_tier_falls_back_without_config(monkeypatch):
    """If config can't be loaded, the helper still returns a sane tier from module defaults
    rather than raising — telemetry logging must never fail on this lookup."""
    monkeypatch.setattr(config, "load_config", lambda: (_ for _ in ()).throw(RuntimeError("no config")))
    assert config.model_tier_for_stage("03") == "deep-reasoning"
    assert config.model_tier_for_stage("01") == "standard"
