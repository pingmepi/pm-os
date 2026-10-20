#!/usr/bin/env python3
"""Finish a stage whose artifact has been written: record it as a generated draft.

Does, in one call, the mechanical end-of-stage steps a stage skill otherwise
spells out one by one:

1. stamp ``generated_hash`` and write the ``.history/`` snapshot (``pm_snapshot``);
2. set the artifact frontmatter and ``.meta.yaml`` to ``draft``, clear any previous
   approval, reset ``upstream_hashes_at_approval`` and bump ``regeneration_count``;
3. log ``stage_generated`` (model, model tier, prompt version, notes).

Use it when a stage was generated outside its skill: written in parts because
it was too large for one pass, assembled by hand, or produced by another tool.
Without it there was no supported way to make such an artifact approvable
(backlog #63). It never approves anything; the PM still runs /pm-approve <NN>.

  python3 ~/.pm-os/scripts/pm_finish_stage.py 03 --model <model id> [--note "..."]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ.get("PM_OS_LIB_PATH") or str(Path.home() / ".pm-os" / "lib"))

from console import ensure_utf8_stdio  # noqa: E402
ensure_utf8_stdio()

sys.path.insert(0, str(Path(__file__).resolve().parent))  # sibling pm_snapshot.py

from config import model_tier_for_stage  # noqa: E402
from frontmatter import read as fm_read, write as fm_write  # noqa: E402
from project import STAGE_NAMES, artifact_path, get_stage, load_meta, resolve_project, save_meta  # noqa: E402
from telemetry import log  # noqa: E402
from pm_snapshot import snapshot  # noqa: E402


def _skill_prompt_version(stage_id: str) -> str:
    """The installed stage skill's ``prompt_version``, or "unknown"."""
    skill = (Path(__file__).resolve().parent.parent / "skills"
             / f"pm-stage-{stage_id}-{STAGE_NAMES[stage_id]}" / "SKILL.md")
    try:
        fm, _ = fm_read(str(skill))
        return str(fm.get("prompt_version") or "unknown")
    except Exception:
        return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record a written stage artifact as a generated draft (snapshot, state, telemetry).")
    parser.add_argument("stage_id", help="Stage id, e.g. 03")
    parser.add_argument("--model", required=True,
                        help="The model id that generated the artifact (recorded in telemetry).")
    parser.add_argument("--prompt-version", dest="prompt_version", default=None,
                        help="Defaults to the installed stage skill's prompt_version.")
    parser.add_argument("--note", action="append", default=None,
                        help="A --note value used for this generation (repeatable). "
                             "Replaces generation_notes when given.")
    args = parser.parse_args()

    stage_id = args.stage_id.zfill(2)
    if stage_id not in STAGE_NAMES:
        print(f"Error: unknown stage '{stage_id}'. Valid: {', '.join(STAGE_NAMES)}")
        sys.exit(1)
    try:
        root = resolve_project()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    apath = artifact_path(root, stage_id)
    if not apath.exists():
        print(f"Error: {apath.name} does not exist. Write the artifact first, then run this again.")
        sys.exit(1)
    try:
        fm, body = fm_read(str(apath))
    except Exception as e:
        print(f"Error: could not read {apath.name}: {e}")
        sys.exit(1)
    if not body.strip():
        print(f"Error: {apath.name} has no body below its frontmatter. Nothing to finish.")
        sys.exit(1)

    # Frontmatter first, so the snapshot copies the final draft state.
    meta = load_meta(root)
    fm.update({
        "stage": fm.get("stage") or f"{stage_id}-{STAGE_NAMES[stage_id]}",
        "project": fm.get("project") or meta.get("project_slug"),
        "status": "draft",
        "approved_at": None,
        "approved_by": None,
        "content_hash": None,
        "pm_os_version": fm.get("pm_os_version") or meta.get("pm_os_version"),
        "genai_flag": fm.get("genai_flag", meta.get("genai_flag")),
    })
    if args.note is not None:
        fm["generation_notes"] = list(args.note)
    fm.setdefault("generation_notes", [])
    fm_write(str(apath), fm, body)

    snap = snapshot(root, stage_id)  # stamps generated_hash; warns, never blocks
    generated_hash = fm_read(str(apath))[0].get("generated_hash")

    stage_meta = get_stage(meta, stage_id)
    stage_meta["status"] = "draft"
    stage_meta["approved_at"] = None
    stage_meta["content_hash"] = None
    stage_meta["upstream_hashes_at_approval"] = {}
    stage_meta["regeneration_count"] = int(stage_meta.get("regeneration_count") or 0) + 1
    stage_meta.pop("edited_hash", None)
    save_meta(meta, root)

    try:
        log("stage_generated", root, stage_id, {
            "generated_hash": generated_hash,
            "model": args.model,
            "model_tier": model_tier_for_stage(stage_id),
            "prompt_version": args.prompt_version or _skill_prompt_version(stage_id),
            "notes": list(fm.get("generation_notes") or []),
            "finished_via": "pm_finish_stage",
        })
    except Exception as e:
        print(f"Warning: telemetry logging failed: {e}")

    print(f"Stage {stage_id} recorded as a draft: {apath.name}")
    if snap is None:
        print("Warning: the .history snapshot could not be written (see above). "
              "Approval still works, but the edit-distance metric will be empty.")
    print("Review it, then:")
    print(f"  Claude: /pm-approve {stage_id}")
    print(f"  Codex:  $pm-approve {stage_id}")


if __name__ == "__main__":
    main()
