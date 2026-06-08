import os
from pathlib import Path

import yaml

CONFIG_PATH = Path.home() / ".pm-os" / "config.yaml"
REQUIRED_KEYS = ["pm_user", "feedback_repo", "projects_dir"]

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
        "default_stage_model": "claude-sonnet-4-6",
        "opus_stages": ["03", "06"],
    }

    if not feedback_repo:
        print("[pm-os] Migration: feedback_repo not set. Enter it now.")
        try:
            feedback_repo = input("Feedback repo URL (HTTPS): ").strip()
        except EOFError:
            feedback_repo = ""

    config["feedback_repo"] = feedback_repo

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _write_config_atomic(config)
    print(f"[pm-os] Migrated config written to {CONFIG_PATH}")
    return config


def _write_config_atomic(config: dict) -> None:
    tmp = CONFIG_PATH.with_suffix(".yaml.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    tmp.rename(CONFIG_PATH)


def _read_version() -> str:
    vpath = Path.home() / ".pm-os" / "VERSION"
    return vpath.read_text().strip() if vpath.exists() else "0.1.0"
