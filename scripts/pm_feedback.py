#!/usr/bin/env python3
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".pm-os" / "lib"))

from config import load_config
from project import resolve_project, load_meta, STAGE_NAMES


def main():
    parser = argparse.ArgumentParser(description="Capture feedback for a PM-OS stage.")
    parser.add_argument("stage_id", help="Two-digit stage number (e.g. '01')")
    parser.add_argument("--rating", type=int, choices=range(1, 6), metavar="1-5", help="Quality rating")
    parser.add_argument("--note", type=str, help="Feedback text")
    parser.add_argument("--skip-rating", action="store_true", help="Do not prompt for a rating")
    parser.add_argument("--skip-note", action="store_true", help="Do not prompt for notes")
    args = parser.parse_args()

    stage_id = args.stage_id.zfill(2)
    if stage_id not in STAGE_NAMES:
        print(f"Error: unknown stage '{stage_id}'. Valid: {', '.join(STAGE_NAMES.keys())}")
        sys.exit(1)

    try:
        root = resolve_project()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    meta = load_meta(root)
    try:
        pm = load_config()["pm_user"]
    except Exception:
        pm = "unknown"

    rating = args.rating
    note = args.note

    if rating is None and not args.skip_rating:
        if not sys.stdin.isatty():
            print("Error: rating required in non-interactive mode. Pass --rating 1-5 or --skip-rating.")
            sys.exit(1)
        try:
            rating_str = input(f"Rating for stage {stage_id} (1-5, Enter to skip): ").strip()
            if rating_str:
                r = int(rating_str)
                rating = r if 1 <= r <= 5 else None
        except ValueError:
            rating = None

    if note is None and not args.skip_note:
        if not sys.stdin.isatty():
            print("Error: note required in non-interactive mode. Pass --note \"...\" or --skip-note.")
            sys.exit(1)
        try:
            note = input("Notes (Enter to skip): ").strip() or None
        except EOFError:
            note = None

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pm": pm,
        "project": meta["project_slug"],
        "stage_id": stage_id,
        "rating": rating,
        "note": note,
    }

    fpath = root / "feedback.jsonl"
    with open(fpath, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"Feedback captured for stage {stage_id}.")


if __name__ == "__main__":
    main()
