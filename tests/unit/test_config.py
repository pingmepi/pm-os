import pytest

import config

pytestmark = pytest.mark.unit


def test_load_config_reads_temp_install(pmos):
    cfg = config.load_config()
    assert cfg["pm_user"] == "tester"
    assert cfg["projects_dir"] == str(pmos.projects)
    # model policy defaults applied
    assert cfg["default_model_tier"] == "standard"
    assert "03" in cfg["deep_reasoning_stages"]


def test_model_tier_for_stage(pmos):
    for deep in ("03", "06", "08"):
        assert config.model_tier_for_stage(deep) == "deep-reasoning"
    for std in ("01", "02", "04", "05", "07", "09"):
        assert config.model_tier_for_stage(std) == "standard"


def test_model_tier_falls_back_without_config(monkeypatch):
    # If load_config raises, the helper must still return a sane tier.
    monkeypatch.setattr(config, "load_config", lambda: (_ for _ in ()).throw(RuntimeError("no config")))
    assert config.model_tier_for_stage("03") == "deep-reasoning"
    assert config.model_tier_for_stage("01") == "standard"
