#!/usr/bin/env python3
import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.environ.get("PM_OS_LIB_PATH") or str(Path.home() / ".pm-os" / "lib"))

import yaml
from config import load_config


def parse_bool(value):
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "genai"}:
        return True
    if normalized in {"0", "false", "no", "n", "non-genai", "no-genai"}:
        return False
    return None


def main():
    parser = argparse.ArgumentParser(description="Scaffold a new PM-OS project.")
    parser.add_argument("slug", help="kebab-case project identifier")
    parser.add_argument("statement", nargs="?", default=None,
                        help="One-line business problem statement (optional; can be added later)")
    parser.set_defaults(genai=None)
    genai_group = parser.add_mutually_exclusive_group()
    genai_group.add_argument("--genai", dest="genai", action="store_true")
    genai_group.add_argument("--no-genai", dest="genai", action="store_false")
    parser.add_argument("--mode", dest="mode", default=None,
                        choices=["new_product", "enhancement"],
                        help="Project mode (default: new_product). Env: PM_OS_PROJECT_TYPE.")
    parser.add_argument("--codebase", dest="codebase", default=None,
                        help="GitHub URL or local path to the existing codebase (enhancement mode).")
    args = parser.parse_args()

    if not re.match(r"^[a-z0-9][a-z0-9-]*$", args.slug):
        print(f"Error: slug '{args.slug}' must be kebab-case (lowercase letters, numbers, hyphens; start with letter/digit)")
        sys.exit(1)

    # Resolve project_type from flag → env var → default
    env_mode = os.environ.get("PM_OS_PROJECT_TYPE")
    if args.mode is not None:
        project_type = args.mode
    elif env_mode in ("new_product", "enhancement"):
        project_type = env_mode
    else:
        project_type = "new_product"

    if args.codebase and project_type == "new_product":
        print("Error: --codebase requires --mode enhancement.")
        sys.exit(1)

    try:
        cfg = load_config()
    except Exception as e:
        print(f"Warning: could not load config ({e}) — using defaults")
        cfg = {}

    projects_dir = Path(cfg.get("projects_dir") or (Path.home() / "pm-projects")).expanduser()
    project_root = projects_dir / args.slug

    if project_root.exists():
        print(f"Error: project '{args.slug}' already exists at {project_root}")
        sys.exit(1)

    env_genai = os.environ.get("PM_OS_GENAI_FLAG")
    if args.genai is None and env_genai is not None:
        parsed = parse_bool(env_genai)
        if parsed is None:
            print("Error: PM_OS_GENAI_FLAG must be one of yes/no, true/false, or 1/0.")
            sys.exit(1)
        genai_flag = parsed
    elif args.genai is None:
        if not sys.stdin.isatty():
            print("Error: GenAI decision required in non-interactive mode. Pass --genai or --no-genai.")
            sys.exit(1)
        resp = input("Is this a GenAI/agentic product? [y/n]: ").strip().lower()
        if resp not in {"y", "yes", "n", "no"}:
            print("Error: answer must be y or n.")
            sys.exit(1)
        genai_flag = resp.startswith("y")
    else:
        genai_flag = args.genai

    version_path = Path.home() / ".pm-os" / "VERSION"
    pm_os_version = version_path.read_text().strip() if version_path.exists() else "0.1.0"

    pm = cfg.get("pm_user", "unknown")

    ts = datetime.now(timezone.utc).isoformat()

    # Resolve business statement: provided inline, prompted on tty, or placeholder
    statement = args.statement
    if statement is None:
        if sys.stdin.isatty():
            resp = input("What do you want to build? (Enter to add later): ").strip()
            statement = resp if resp else None
        if statement is None:
            statement = "[Business statement pending — describe what you want to build here, then /pm-approve 00]"

    project_root.mkdir(parents=True)
    (project_root / ".history").mkdir()

    # The business statement is a normal gated stage (00): written as a draft the
    # PM approves via /pm-approve 00, just like every other stage. No special case.
    bs_fm = {
        "stage": "00-business-statement",
        "project": args.slug,
        "status": "draft",
        "approved_at": None,
        "approved_by": None,
        "content_hash": None,
        "generated_hash": None,
        "pm_os_version": pm_os_version,
        "genai_flag": genai_flag,
        "origin": "generated",
    }
    fm_text = yaml.dump(bs_fm, default_flow_style=False, allow_unicode=True, sort_keys=False)
    bs_content = f"---\n{fm_text}---\n\n{statement}\n"
    (project_root / "00-business-statement.md").write_text(bs_content)

    project_name = " ".join(w.capitalize() for w in args.slug.split("-"))
    stages = [{
        "id": "00", "name": "business-statement", "status": "draft",
        "approved_at": None, "content_hash": None,
        "upstream_hashes_at_approval": {}, "regeneration_count": 0,
        "optional": False, "origin": "generated",
    }]
    for sid, name in [
        ("01", "brief"), ("02", "scope"), ("03", "prd"),
        ("04", "design-spec"), ("05", "prototype-brief"),
        ("06", "qa-plan"), ("07", "metrics-plan"),
        ("08", "trd"), ("09", "roadmap"),
    ]:
        stages.append({
            "id": sid, "name": name, "status": "pending",
            "approved_at": None, "content_hash": None,
            "upstream_hashes_at_approval": {}, "regeneration_count": 0,
            "optional": sid in {"08", "09"}, "origin": "generated",
        })

    meta = {
        "schema_version": 4,
        "project_slug": args.slug,
        "project_name": project_name,
        "created_at": ts,
        "created_by": pm,
        "genai_flag": genai_flag,
        "project_type": project_type,
        "codebase_path": args.codebase,
        "codebase_ref": None,
        "context_pack": None,
        "pm_os_version": pm_os_version,
        "stages": stages,
    }
    with open(project_root / ".meta.yaml", "w") as f:
        yaml.dump(meta, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    (project_root / "telemetry.jsonl").touch()
    (project_root / "feedback.jsonl").touch()

    try:
        from telemetry import log
        log("project_created", project_root, None, {"project_type": project_type})
    except Exception as e:
        print(f"Warning: telemetry logging failed: {e}")

    print(f"Project '{args.slug}' created at {project_root}/")
    print(f"GenAI flag: {'yes' if genai_flag else 'no'}  Mode: {project_type}")
    if project_type == "enhancement" and args.codebase:
        print(f"Codebase: {args.codebase}")
    print(f"Next step: cd {project_root}")
    print("  Review and approve the business statement first (it is a gated stage):")
    print("    Claude: /pm-approve 00       Codex: $pm-approve 00")
    if project_type == "enhancement":
        print("  Then import context (docs + codebase scan):")
        print("    Claude: /pm-context-import   Codex: $pm-context-import")
    else:
        print("  Then start the pipeline:")
        print("    Claude: /pm-stage-01-brief   Codex: $pm-stage-01-brief")
        print("  Or seed from existing context: /pm-context-import <files-or-folder>")


if __name__ == "__main__":
    main()
