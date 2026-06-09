#!/usr/bin/env python3
import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".pm-os" / "lib"))

import yaml
from config import load_config


def main():
    parser = argparse.ArgumentParser(description="Scaffold a new PM-OS project.")
    parser.add_argument("slug", help="kebab-case project identifier")
    parser.add_argument("statement", help="One-line business problem statement")
    parser.set_defaults(genai=None)
    genai_group = parser.add_mutually_exclusive_group()
    genai_group.add_argument("--genai", dest="genai", action="store_true")
    genai_group.add_argument("--no-genai", dest="genai", action="store_false")
    args = parser.parse_args()

    if not re.match(r"^[a-z0-9][a-z0-9-]*$", args.slug):
        print(f"Error: slug '{args.slug}' must be kebab-case (lowercase letters, numbers, hyphens; start with letter/digit)")
        sys.exit(1)

    projects_dir = Path.home() / "pm-projects"
    project_root = projects_dir / args.slug

    if project_root.exists():
        print(f"Error: project '{args.slug}' already exists at {project_root}")
        sys.exit(1)

    if args.genai is None:
        try:
            resp = input("Is this a GenAI/agentic product? [y/n]: ").strip().lower()
            genai_flag = resp.startswith("y")
        except EOFError:
            genai_flag = False
    else:
        genai_flag = args.genai

    version_path = Path.home() / ".pm-os" / "VERSION"
    pm_os_version = version_path.read_text().strip() if version_path.exists() else "0.1.0"

    try:
        pm = load_config()["pm_user"]
    except Exception as e:
        print(f"Warning: could not load config ({e}) — using 'unknown'")
        pm = "unknown"

    ts = datetime.now(timezone.utc).isoformat()

    project_root.mkdir(parents=True)
    (project_root / ".history").mkdir()

    bs_fm = {
        "stage": "00-business-statement",
        "project": args.slug,
        "status": "approved",
        "approved_at": ts,
        "approved_by": pm,
        "content_hash": None,
        "generated_hash": None,
        "pm_os_version": pm_os_version,
        "genai_flag": genai_flag,
    }
    fm_text = yaml.dump(bs_fm, default_flow_style=False, allow_unicode=True, sort_keys=False)
    bs_content = f"---\n{fm_text}---\n\n{args.statement}\n"
    (project_root / "00-business-statement.md").write_text(bs_content)

    project_name = " ".join(w.capitalize() for w in args.slug.split("-"))
    stages = []
    for sid, name in [
        ("01", "brief"), ("02", "scope"), ("03", "prd"),
        ("04", "design-spec"), ("05", "prototype-brief"),
        ("06", "qa-plan"), ("07", "metrics-plan"),
        ("08", "trd"),
    ]:
        stages.append({
            "id": sid, "name": name, "status": "pending",
            "approved_at": None, "content_hash": None,
            "upstream_hashes_at_approval": {}, "regeneration_count": 0,
            "optional": sid == "08",
        })

    meta = {
        "schema_version": 1,
        "project_slug": args.slug,
        "project_name": project_name,
        "created_at": ts,
        "created_by": pm,
        "genai_flag": genai_flag,
        "pm_os_version": pm_os_version,
        "stages": stages,
    }
    with open(project_root / ".meta.yaml", "w") as f:
        yaml.dump(meta, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    (project_root / "telemetry.jsonl").touch()
    (project_root / "feedback.jsonl").touch()

    try:
        from telemetry import log
        log("project_created", project_root, None, {})
    except Exception as e:
        print(f"Warning: telemetry logging failed: {e}")

    print(f"Project '{args.slug}' created at {project_root}/")
    print(f"GenAI flag: {'yes' if genai_flag else 'no'}")
    print(f"Next step: cd {project_root} && run /pm-stage-01-brief")


if __name__ == "__main__":
    main()
