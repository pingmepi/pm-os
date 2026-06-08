#!/usr/bin/env python3
"""PM-OS installer. Writes ~/.pm-os/config.yaml. Does NOT modify ~/.zshrc."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".pm-os" / "lib"))

import yaml

PM_OS_DIR = Path.home() / ".pm-os"
CONFIG_PATH = PM_OS_DIR / "config.yaml"
PROJECTS_DIR = Path.home() / "pm-projects"


def main():
    parser = argparse.ArgumentParser(description="Install or reconfigure PM-OS.")
    parser.add_argument("--reconfigure", action="store_true", help="Reconfigure existing install")
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

    # Step 1: ~/pm-projects/ exists
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    if PROJECTS_DIR.is_dir():
        print(f"✓ {PROJECTS_DIR} exists")
        steps_ok.append("projects_dir")
    else:
        print(f"✗ FAILED to create {PROJECTS_DIR}")
        steps_fail.append("projects_dir")

    # Step 2: pm_user
    current_user = existing.get("pm_user", "")
    if args.reconfigure or not current_user:
        try:
            pm_user = input(f"PM username [{current_user or 'enter name'}]: ").strip() or current_user
        except EOFError:
            pm_user = current_user
    else:
        pm_user = current_user
        print(f"✓ pm_user already set: {pm_user} (use --reconfigure to change)")

    # Step 3: feedback_repo
    current_repo = existing.get("feedback_repo", "")
    if args.reconfigure or not current_repo:
        try:
            default = current_repo or "https://github.com/org/repo.git"
            feedback_repo = input(f"Feedback repo URL (HTTPS) [{default}]: ").strip() or current_repo
        except EOFError:
            feedback_repo = current_repo
    else:
        feedback_repo = current_repo
        print(f"✓ feedback_repo already set: {feedback_repo} (use --reconfigure to change)")

    # Step 4: projects_dir (keep existing or default)
    projects_dir = existing.get("projects_dir", "") or str(PROJECTS_DIR)

    # Step 5: Build config
    version_path = PM_OS_DIR / "VERSION"
    pm_os_version = version_path.read_text().strip() if version_path.exists() else "0.1.0"

    config = {
        "schema_version": 1,
        "pm_user": pm_user,
        "feedback_repo": feedback_repo,
        "projects_dir": projects_dir,
        "pm_os_version": pm_os_version,
        "default_stage_model": "claude-sonnet-4-6",
        "opus_stages": ["03", "06"],
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
        print("Run /pm-os-verify to confirm installation health.")


if __name__ == "__main__":
    main()
