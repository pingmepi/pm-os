import os
import sys
from pathlib import Path

import yaml

CONFIG_PATH = Path.home() / ".pm-os" / "config.yaml"
REQUIRED_KEYS = ["pm_user", "feedback_repo", "projects_dir"]
DEFAULT_FEEDBACK_REPO = "https://github.com/pingmepi/pm-os-feedback.git"
DEFAULT_MODEL_TIER = "standard"
DEEP_REASONING_STAGES = ["03", "06", "08"]

_config_cache = None


def load_config() -> dict:
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    if not CONFIG_PATH.exists():
        _config_cache = _migrate_from_env()
        return _config_cache

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    missing = [k for k in REQUIRED_KEYS if k not in config]
    if missing:
        raise RuntimeError(
            f"PM-OS config missing required keys: {', '.join(missing)}\n"
            f"Run: python3 ~/.pm-os/scripts/pm_os_install.py --reconfigure"
        )

    _apply_model_policy_defaults(config)
    _config_cache = config
    return _config_cache


def _migrate_from_env() -> dict:
    pm_user = os.environ.get("PM_OS_USER", "")
    feedback_repo = os.environ.get("PM_OS_FEEDBACK_REPO", "")

    if not pm_user and not feedback_repo:
        raise RuntimeError(
            "PM-OS config not found at ~/.pm-os/config.yaml\n"
            "Run: python3 ~/.pm-os/scripts/pm_os_install.py"
        )

    config = {
        "schema_version": 1,
        "pm_user": pm_user or "unknown",
        "projects_dir": str(Path.home() / "pm-projects"),
        "pm_os_version": _read_version(),
        "default_model_tier": DEFAULT_MODEL_TIER,
        "deep_reasoning_stages": DEEP_REASONING_STAGES,
    }

    if not feedback_repo:
        if not sys.stdin.isatty():
            feedback_repo = DEFAULT_FEEDBACK_REPO
            print(f"[pm-os] Migration: feedback_repo using default {DEFAULT_FEEDBACK_REPO}")
        else:
            print("[pm-os] Migration: feedback_repo not set. Enter it now.")
            feedback_repo = input(f"Feedback repo URL (HTTPS) [{DEFAULT_FEEDBACK_REPO}]: ").strip()
            feedback_repo = feedback_repo or DEFAULT_FEEDBACK_REPO
    if not feedback_repo:
        raise RuntimeError(
            "PM-OS config migration cancelled: feedback_repo is required.\n"
            "Run: python3 ~/.pm-os/scripts/pm_os_install.py --reconfigure"
        )

    config["feedback_repo"] = feedback_repo

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _write_config_atomic(config)
    print(f"[pm-os] Migrated config written to {CONFIG_PATH}")
    return config


def _apply_model_policy_defaults(config: dict) -> None:
    config.setdefault("default_model_tier", DEFAULT_MODEL_TIER)
    config.setdefault("deep_reasoning_stages", DEEP_REASONING_STAGES)


def model_tier_for_stage(stage_id: str) -> str:
    """Return the recommended model tier for a stage, derived from config.

    Single source of truth so skill telemetry can't drift from the model policy:
    stages listed in ``deep_reasoning_stages`` report ``"deep-reasoning"``, all
    others report ``default_model_tier``. Degrades to module defaults if config
    is unavailable so telemetry logging never fails on this.
    """
    try:
        cfg = load_config()
        deep = cfg.get("deep_reasoning_stages") or DEEP_REASONING_STAGES
        default = cfg.get("default_model_tier") or DEFAULT_MODEL_TIER
    except Exception:
        deep, default = DEEP_REASONING_STAGES, DEFAULT_MODEL_TIER
    return "deep-reasoning" if stage_id in deep else default


def _write_config_atomic(config: dict) -> None:
    tmp = CONFIG_PATH.with_suffix(".yaml.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    tmp.rename(CONFIG_PATH)


def _read_version() -> str:
    vpath = Path.home() / ".pm-os" / "VERSION"
    return vpath.read_text().strip() if vpath.exists() else "0.1.0"
