"""Unit tests for lib/config.py — config load + the model-tier policy that keeps skill
telemetry in lockstep with deep_reasoning_stages. See docs/guides/testing.md §5 (T1)."""
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
    """Deep-reasoning stages — context build (00w/00u), PRD (03), design (04), QA (06), TRD (08),
    roadmap (09) — resolve to 'deep-reasoning'; all others to the configured default. Single
    source of truth that skills derive their tier from."""
    for deep in ("00w", "00u", "03", "04", "06", "08", "09"):
        assert config.model_tier_for_stage(deep) == "deep-reasoning"
    for std in ("00", "01", "02", "05", "07"):
        assert config.model_tier_for_stage(std) == "standard"


def test_model_policy_defaults_merge_stale_config(pmos):
    """Older configs may have a deep-reasoning list from before context stages existed.
    Loading config should merge in required policy stages without dropping custom entries."""
    config.CONFIG_PATH.write_text(
        "schema_version: 1\n"
        "pm_user: tester\n"
        f"feedback_repo: {pmos.feedback}\n"
        f"projects_dir: {pmos.projects}\n"
        "pm_os_version: 0.0.0-test\n"
        "default_model_tier: standard\n"
        "deep_reasoning_stages: ['03', '06', '08', 'custom']\n",
        encoding="utf-8",
    )
    config._config_cache = None

    cfg = config.load_config()

    for deep in ("00w", "00u", "03", "04", "06", "08", "09", "custom"):
        assert deep in cfg["deep_reasoning_stages"]
    assert config.model_tier_for_stage("00w") == "deep-reasoning"
    assert config.model_tier_for_stage("custom") == "deep-reasoning"


def test_model_tier_falls_back_without_config(monkeypatch):
    """If config can't be loaded, the helper still returns a sane tier from module defaults
    rather than raising — telemetry logging must never fail on this lookup."""
    monkeypatch.setattr(config, "load_config", lambda: (_ for _ in ()).throw(RuntimeError("no config")))
    assert config.model_tier_for_stage("03") == "deep-reasoning"
    assert config.model_tier_for_stage("01") == "standard"
