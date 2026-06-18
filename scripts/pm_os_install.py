#!/usr/bin/env python3
"""PM-OS installer. Writes ~/.pm-os/config.yaml. Does NOT modify ~/.zshrc."""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".pm-os" / "lib"))

import yaml
# Single source of truth for the model policy — never duplicate the literals here.
from config import DEFAULT_MODEL_TIER, DEEP_REASONING_STAGES

PM_OS_DIR = Path.home() / ".pm-os"
CONFIG_PATH = PM_OS_DIR / "config.yaml"
PROJECTS_DIR = Path.home() / "pm-projects"
DEFAULT_FEEDBACK_REPO = "https://github.com/pingmepi/pm-os-feedback.git"


def choose_value(label, current, provided, env_name, *, reconfigure=False, default=""):
    env_value = os.environ.get(env_name, "")
    if provided is not None:
        return provided.strip()
    if env_value:
        return env_value.strip()
    if current and not reconfigure:
        print(f"✓ {label} already set: {current} (use --reconfigure to change)")
        return current
    if default and not sys.stdin.isatty():
        print(f"✓ {label} using default: {default}")
        return default
    if not sys.stdin.isatty():
        flag = label.replace("_", "-")
        print(f"✗ {label} required in non-interactive mode. Pass --{flag} or set {env_name}.")
        return ""
    prompt_default = current or default
    if prompt_default:
        return input(f"{label} [{prompt_default}]: ").strip() or prompt_default
    return input(f"{label}: ").strip()


def main():
    parser = argparse.ArgumentParser(description="Install or reconfigure PM-OS.")
    parser.add_argument("--reconfigure", action="store_true", help="Reconfigure existing install")
    parser.add_argument("--pm-user", help="PM username for non-interactive install")
    parser.add_argument("--feedback-repo", help="Feedback repo URL for non-interactive install")
    parser.add_argument("--projects-dir", help="Projects directory path")
    args = parser.parse_args()

    print("PM-OS Install")
    print("=============")

    steps_ok = []
    steps_fail = []

    # Load existing config if present
    existing = {}
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                existing = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Warning: could not read existing config: {e}")

    projects_dir = args.projects_dir or os.environ.get("PM_OS_PROJECTS_DIR") or existing.get("projects_dir", "") or str(PROJECTS_DIR)
    projects_path = Path(projects_dir).expanduser()

    # Step 1: projects directory exists
    projects_path.mkdir(parents=True, exist_ok=True)
    if projects_path.is_dir():
        print(f"✓ {projects_path} exists")
        steps_ok.append("projects_dir")
    else:
        print(f"✗ FAILED to create {projects_path}")
        steps_fail.append("projects_dir")

    # Step 2: pm_user
    current_user = existing.get("pm_user", "")
    pm_user = choose_value(
        "pm_user",
        current_user,
        args.pm_user,
        "PM_OS_USER",
        reconfigure=args.reconfigure,
    )
    if not pm_user:
        steps_fail.append("pm_user")

    # Step 3: feedback_repo
    current_repo = existing.get("feedback_repo", "")
    feedback_repo = choose_value(
        "feedback_repo",
        current_repo,
        args.feedback_repo,
        "PM_OS_FEEDBACK_REPO",
        reconfigure=args.reconfigure,
        default=DEFAULT_FEEDBACK_REPO,
    )
    if not feedback_repo:
        steps_fail.append("feedback_repo")

    if not pm_user or not feedback_repo:
        print()
        total = len(steps_ok) + len(steps_fail)
        print(f"Steps: {len(steps_ok)}/{total} passed")
        print(f"Failed: {', '.join(steps_fail)}")
        print("Install incomplete. Provide the missing values and re-run.")
        sys.exit(1)

    # Step 5: Build config
    version_path = PM_OS_DIR / "VERSION"
    pm_os_version = version_path.read_text().strip() if version_path.exists() else "0.1.0"

    config = {
        "schema_version": 1,
        "pm_user": pm_user,
        "feedback_repo": feedback_repo,
        "projects_dir": str(projects_path),
        "pm_os_version": pm_os_version,
        "default_model_tier": DEFAULT_MODEL_TIER,
        "deep_reasoning_stages": DEEP_REASONING_STAGES,
    }

    # Step 6: Write config.yaml atomically and verify
    tmp_path = CONFIG_PATH.with_suffix(".yaml.tmp")
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        tmp_path.rename(CONFIG_PATH)

        # Verify by reading back
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            written = yaml.safe_load(f)

        if written.get("pm_user") == pm_user:
            print(f"✓ pm_user written: {pm_user}")
            steps_ok.append("pm_user")
        else:
            print(f"✗ FAILED to verify pm_user (expected '{pm_user}', got '{written.get('pm_user')}')")
            steps_fail.append("pm_user")

        if written.get("feedback_repo") == feedback_repo:
            print(f"✓ feedback_repo written: {feedback_repo}")
            steps_ok.append("feedback_repo")
        else:
            print(f"✗ FAILED to verify feedback_repo write")
            steps_fail.append("feedback_repo")

    except Exception as e:
        print(f"✗ FAILED to write config.yaml: {e}")
        steps_fail.append("config_write")
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    # Step 7: seed the context overlay (user data) from context.example/ if missing.
    # Non-critical — a failure here never blocks the install.
    try:
        from context import seed_context
        n = seed_context()
        if n:
            print(f"✓ Seeded context overlay ({n} files) into {PM_OS_DIR / 'context'}")
        else:
            print("✓ Context overlay present (left untouched)")
    except Exception as e:
        print(f"Warning: could not seed context overlay: {e}")

    # Summary
    print()
    total = len(steps_ok) + len(steps_fail)
    print(f"Steps: {len(steps_ok)}/{total} passed")
    if steps_fail:
        print(f"Failed: {', '.join(steps_fail)}")
        print("Install incomplete. Fix the above and re-run.")
        sys.exit(1)
    else:
        print("Install complete.")
        print("Run the PM-OS verifier for your runtime, if installed, to confirm installation health.")


if __name__ == "__main__":
    main()
