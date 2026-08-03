#!/usr/bin/env python3
"""pm_interview — mechanical state for the standalone /pm-interview re-run (E3).

Judgment (which still-open gaps to ask, how to batch them, the wording) lives in
skills/pm-interview/SKILL.md. This script only moves bytes:

  list-unknowns  print the OPEN known-unknowns (a bullet with no [resolved: ...]
                 marker) parsed from 00-context/known-unknowns.md, as JSON, so
                 the skill can drive the re-run from a stable contract.
  resolve        mark each open unknown the answers address as resolved *in
                 place* ([resolved: <source-id> <date>], never deleted), and log
                 an interview_conducted event with mode="rerun".

Answer *registration* (answers -> .sources.yaml as a PM-authored source) stays
the job of `pm_context_import.py record-interview`, which the skill invokes
separately and this script never duplicates.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.environ.get("PM_OS_LIB_PATH") or str(Path.home() / ".pm-os" / "lib"))

import yaml  # noqa: E402
from project import resolve_project  # noqa: E402
from telemetry import log  # noqa: E402

PACK_DIR = "00-context"
KU_FILE = "known-unknowns.md"

# Answers-file bullet forms (mirrors pm_context_import's ANSWERED_RE/SKIPPED_RE so
# one answers file feeds both `record-interview` and this resolver).
_ANSWERED_RE = re.compile(r"^-\s*\[[xX]\]\s*ANSWERED:\s*(.+?)\s*$")
_SKIPPED_RE = re.compile(r"^-\s*\[\s*\]\s*SKIPPED:\s*(.+?)\s*$")

# A known-unknown bullet, as written by pm_context_import._write_known_unknowns:
#   - <question> (source: <src_id>)
# and, once E3 closes it, with a trailing resolution marker:
#   - <question> (source: <src_id>) [resolved: <src_id> <YYYY-MM-DD>]
_BULLET_RE = re.compile(r"^-\s*(?P<question>.*?)\s*\(source:\s*(?P<source>[^)]+)\)\s*(?P<rest>.*)$")
_RESOLVED_MARK = "[resolved:"


def _ku_path(root: Path) -> Path:
    return root / PACK_DIR / KU_FILE


def _parse_bullet(line: str):
    """Return (question, source, is_resolved) for a known-unknown bullet, else None."""
    stripped = line.strip()
    if not stripped.startswith("- "):
        return None
    m = _BULLET_RE.match(stripped)
    if not m:
        return None
    return (
        m.group("question").strip(),
        m.group("source").strip(),
        _RESOLVED_MARK in m.group("rest"),
    )


def _open_unknowns(root: Path) -> list[dict]:
    """Distinct open known-unknowns, keyed by question text. The same gap can be flagged
    by more than one source (e.g. re-recorded on a later interview round), so we dedupe on
    the question — one gap, listed once, first source wins."""
    path = _ku_path(root)
    if not path.exists():
        return []
    items, seen = [], set()
    for line in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_bullet(line)
        if parsed and not parsed[2] and parsed[0] not in seen:
            seen.add(parsed[0])
            items.append({"question": parsed[0], "source": parsed[1]})
    return items


def cmd_list_unknowns(args):
    root = resolve_project()
    items = _open_unknowns(root)
    if args.json:
        print(json.dumps(items))
        return
    if not items:
        print("No open known-unknowns.")
        return
    for i in items:
        print(f"- {i['question']} (source: {i['source']})")


def _question_of(payload: str) -> str:
    """The verbatim question portion of an answers-file bullet. The PM may append their
    answer after a ' :: ' delimiter (``ANSWERED: <question> :: <answer>``); matching keys
    on the question alone, so a question-only bullet works too."""
    return payload.split(" :: ", 1)[0].strip()


def _parse_answers(text: str):
    """Return (answered_questions, skipped_questions) from an answers file."""
    answered, skipped = [], []
    for line in text.splitlines():
        m = _ANSWERED_RE.match(line)
        if m:
            answered.append(_question_of(m.group(1)))
            continue
        m = _SKIPPED_RE.match(line)
        if m:
            skipped.append(_question_of(m.group(1)))
    return answered, skipped


def _latest_interview_source(root: Path):
    """Newest PM interview source id in .sources.yaml, else None (mirrors E1's predicate)."""
    sources_path = root / ".sources.yaml"
    if not sources_path.exists():
        return None
    sources = yaml.safe_load(sources_path.read_text(encoding="utf-8")) or []
    ids = [
        s["id"] for s in sources
        if s.get("origin") == "interview" and s.get("confidence") == "high" and s.get("id")
    ]
    return ids[-1] if ids else None


def _mark_resolved(root: Path, answered_questions: list[str], source_id: str) -> list[str]:
    """Append a [resolved: <source> <date>] marker to each open bullet whose question was
    answered. Marks in place — the original question text is preserved, nothing is deleted."""
    path = _ku_path(root)
    if not path.exists() or not answered_questions:
        return []
    answered = {q.strip() for q in answered_questions}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    resolved = []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_bullet(line)
        if parsed and not parsed[2] and parsed[0] in answered:
            out.append(line.rstrip() + f" [resolved: {source_id} {today}]")
            resolved.append(parsed[0])
        else:
            out.append(line)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return resolved


def cmd_resolve(args):
    root = resolve_project()
    # Non-interactive escape (mirrors pm_context_import): skip resolves nothing and
    # leaves every unknown open — a skipped question never becomes a silent assumption.
    if os.environ.get("PM_OS_INTERVIEW", "").strip().lower() == "skip":
        open_now = _open_unknowns(root)
        print(f"PM_OS_INTERVIEW=skip: no unknowns resolved; {len(open_now)} remain open.")
        return
    answers_arg = args.interview_answers or args.answers_file
    if not answers_arg:
        open_now = _open_unknowns(root)
        print(f"No answers supplied; {len(open_now)} known-unknown(s) remain open.")
        return
    src = Path(answers_arg).expanduser()
    if not src.exists() or not src.is_file():
        print(f"Error: answers file not found: {src}")
        sys.exit(1)

    answered, skipped = _parse_answers(src.read_text(encoding="utf-8"))
    source_id = args.source or _latest_interview_source(root) or "interview"
    resolved = _mark_resolved(root, answered, source_id)

    try:
        log("interview_conducted", root, None, {
            "mode": "rerun",
            "asked": len(answered) + len(skipped),
            "answered": len(resolved),
            "skipped": len(skipped),
        })
    except Exception as e:
        print(f"Warning: telemetry logging failed: {e}")

    print(f"Resolved {len(resolved)} known-unknown(s); {len(_open_unknowns(root))} remain open.")


def main():
    parser = argparse.ArgumentParser(description="PM-OS standalone interview mechanical state (E3).")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list-unknowns", help="Print the open known-unknowns.")
    p_list.add_argument("--json", action="store_true", help="Emit JSON instead of a bullet list.")
    p_list.set_defaults(func=cmd_list_unknowns)

    p_res = sub.add_parser("resolve", help="Mark answered known-unknowns resolved in place.")
    p_res.add_argument("answers_file", nargs="?", help="Markdown answers file (ANSWERED/SKIPPED bullets).")
    p_res.add_argument("--interview-answers", dest="interview_answers", default=None,
                       help="Answers file for non-interactive runs (alias of the positional).")
    p_res.add_argument("--source", default=None,
                       help="Source id to credit on resolved markers (default: newest PM interview source).")
    p_res.set_defaults(func=cmd_resolve)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
