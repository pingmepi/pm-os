#!/usr/bin/env python3
import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.environ.get("PM_OS_LIB_PATH") or str(Path.home() / ".pm-os" / "lib"))

from project import resolve_project, load_meta, artifact_path
from frontmatter import read as read_frontmatter
from artifact_contracts import validate_artifact
from consistency import check_project, summary_line

STAGE_LABELS = {
    "00": "Business Statement", "00c": "Codebase Understanding",
    "00w": "Context Wiki", "00u": "Understanding",
    "01": "Brief", "02": "Scope", "03": "PRD",
    "04": "Design Spec", "05": "Prototype Brief",
    "06": "QA Plan", "07": "Metrics Plan",
    "08": "TRD", "09": "Roadmap",
}


def main():
    try:
        root = resolve_project()
    except FileNotFoundError:
        print("Not inside a PM-OS project.")
        sys.exit(1)

    meta = load_meta(root)

    print(f"Project: {meta['project_slug']}")
    genai = "yes" if meta.get("genai_flag") else "no"
    vpath = Path.home() / ".pm-os" / "VERSION"
    installed = vpath.read_text().strip() if vpath.exists() else "unknown"
    created_with = meta.get("pm_os_version", "unknown")
    version_str = installed if created_with == installed else f"{installed} (project created with {created_with})"
    print(f"Created: {meta['created_at']}  GenAI: {genai}  PM-OS version: {version_str}")
    if meta.get("project_type") == "enhancement":
        codebase = meta.get("codebase_path") or "(not set)"
        drift = ""
        codebase_ref = meta.get("codebase_ref")
        if codebase_ref and codebase != "(not set)":
            try:
                import subprocess as _sp
                r = _sp.run(["git", "-C", codebase, "rev-parse", "HEAD"],
                            capture_output=True, text=True, timeout=5)
                if r.returncode == 0 and r.stdout.strip() != codebase_ref:
                    drift = "  ⚠ codebase drift — re-run /pm-context-import"
            except Exception:
                pass
        print(f"Mode: enhancement  Codebase: {codebase}{drift}")
    print()
    print("Stages:")

    now = datetime.now(timezone.utc)
    for s in meta["stages"]:
        label = STAGE_LABELS[s["id"]].ljust(18)
        status = s["status"]
        detail = ""
        if status == "approved" and s.get("approved_at"):
            try:
                t = datetime.fromisoformat(s["approved_at"])
                diff = int((now - t).total_seconds())
                age = f"{diff // 3600}h ago" if diff >= 3600 else f"{diff // 60}m ago"
                detail = f"  approved {age}"
            except Exception:
                pass
        elif status == "edited":
            detail = "  edited since approval"
        elif status == "stale":
            detail = "  upstream changed"
        elif status == "draft":
            detail = "  awaiting approval"

        notes_str = ""
        contract_str = ""
        try:
            apath = artifact_path(root, s["id"])
            if apath.exists():
                fm, _ = read_frontmatter(str(apath))
                gn = fm.get("generation_notes") or []
                if gn:
                    notes_str = f"  · {len(gn)} note{'s' if len(gn) != 1 else ''}"
                if s["id"] in {"03", "04", "05", "06"}:
                    findings = validate_artifact(root, s["id"], apath)
                    if findings:
                        contract_str = f"  · ⚠ contract warnings: {len(findings)}"
        except Exception:
            pass
        opt = "  (optional)" if s.get("optional") else ""
        origin = s.get("origin", "generated")
        status_tag = f"{status} · {origin}" if origin in ("imported", "backfilled") else status
        print(f"  {s['id']} {label} [{status_tag}]{detail}{notes_str}{contract_str}{opt}")

    tpath = root / "telemetry.jsonl"
    events = []
    if tpath.exists():
        lines = [line.strip() for line in tpath.read_text().splitlines() if line.strip()]
        events = lines[-5:]

    print()
    print("Recent events:")
    for ev in events:
        try:
            e = json.loads(ev)
            ts = e["timestamp"][:16].replace("T", " ")
            stage = e.get("stage") or "-"
            print(f"  {ts}  {e['event_type']}  stage={stage}")
        except Exception:
            pass
    if not events:
        print("  (none)")

    fpath = root / "feedback.jsonl"
    fc = 0
    if fpath.exists():
        fc = len([line for line in fpath.read_text().splitlines() if line.strip()])
    tc = 0
    if tpath.exists():
        tc = len([line for line in tpath.read_text().splitlines() if line.strip()])

    print()
    print(f"Feedback captured: {fc} entries")
    print(f"Telemetry events:  {tc}")

    print()
    try:
        print(summary_line(check_project(root)))
    except Exception as e:
        print(f"Consistency: check failed ({e})")


if __name__ == "__main__":
    main()
