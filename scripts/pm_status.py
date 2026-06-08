#!/usr/bin/env python3
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".pm-os" / "lib"))

from project import resolve_project, load_meta

STAGE_LABELS = {
    "01": "Brief", "02": "Scope", "03": "PRD",
    "04": "Design Spec", "05": "Prototype Brief",
    "06": "QA Plan", "07": "Metrics Plan",
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
    print(f"Created: {meta['created_at']}  GenAI: {genai}  PM-OS version: {meta['pm_os_version']}")
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
        print(f"  {s['id']} {label} [{status}]{detail}")

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


if __name__ == "__main__":
    main()
