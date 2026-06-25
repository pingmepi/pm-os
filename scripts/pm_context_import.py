#!/usr/bin/env python3
"""pm_context_import — mechanical state for the context-intake / ingest flow.

Judgment (reading sources, building the wiki, writing the understanding doc,
normalizing/reverse-generating stage artifacts) lives in the pm-context-import
SKILL.md. This script only moves bytes and updates state:

  register   preserve a raw source in .history/, register it in .sources.yaml,
             log a context_ingested event.
  preflight  print the backfill-feasibility verdicts for a provided combo
             (uses lib.project.resolve_backfill); exits non-zero if any gap is
             infeasible so a caller can block.
  commit     commit an artifact slot the SKILL already wrote, to draft or
             approved, stamping origin (generated|imported|backfilled), the body
             hash, meta + frontmatter, telemetry, and (on approve) post-approve.

The SKILL writes the markdown bodies; this script never generates content.
"""
import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.environ.get("PM_OS_LIB_PATH") or str(Path.home() / ".pm-os" / "lib"))

import yaml
from config import load_config, model_tier_for_stage
from project import (
    resolve_project, load_meta, save_meta, get_stage, artifact_path,
    upstream_stage_ids, downstream_stage_ids, resolve_backfill,
    STAGE_NAMES, STAGE_ORDER, CORE_STAGE_ORDER,
)
from hashing import hash_artifact_body
from frontmatter import read as fm_read, write as fm_write, update_status
from telemetry import log
from artifact_contracts import format_findings, validate_artifact


def _now():
    return datetime.now(timezone.utc).isoformat()


def _pm():
    try:
        return load_config()["pm_user"]
    except Exception:
        return "unknown"


# Document-like extensions worth ingesting when a whole folder is handed in.
# Anything else (images, archives, binaries, junk) is reported as skipped rather
# than silently snapshotted — honoring the skill's "nothing is silent" rule.
DOC_EXTS = {".md", ".markdown", ".txt", ".rst", ".pdf", ".docx", ".doc", ".rtf", ".csv"}
# Never descend into these — engine/state dirs and OS cruft, not PM context.
IGNORE_DIRS = {".history", ".git", "__pycache__", ".meta", "node_modules"}
IGNORE_NAMES = {".DS_Store", "Thumbs.db", ".meta.yaml", ".sources.yaml"}


def _register_one(root, src, src_type, ts, sources):
    """Snapshot one file and append a provenance entry to ``sources`` (in place)."""
    stamp = ts.replace(":", "").replace("-", "")[:15]
    src_id = f"src_{len(sources) + 1:03d}"
    history = root / ".history"
    history.mkdir(parents=True, exist_ok=True)
    snapshot = history / f"source-{stamp}-{src.name}"
    if snapshot.exists():  # collision (same name within the same second) — disambiguate
        snapshot = history / f"source-{stamp}-{src_id}-{src.name}"
    snapshot.write_bytes(src.read_bytes())

    sources.append({
        "id": src_id,
        "type": src_type,
        "uri": str(src),
        "captured_at": ts,
        "snapshot": str(snapshot.relative_to(root)),
        "summary_hash": None,
    })
    try:
        log("context_ingested", root, None, {
            "source_id": src_id,
            "source_type": src_type,
            "source_filename": src.name,
            "snapshot": str(snapshot.relative_to(root)),
        })
    except Exception as e:
        print(f"Warning: telemetry logging failed: {e}")
    return src_id, snapshot


def cmd_register(args):
    root = resolve_project()
    src = Path(args.file).expanduser()
    if not src.exists():
        print(f"Error: source not found: {src}")
        sys.exit(1)

    ts = _now()
    sources_path = root / ".sources.yaml"
    sources = []
    if sources_path.exists():
        sources = yaml.safe_load(sources_path.read_text()) or []

    # --- Single file ---
    if src.is_file():
        src_id, snapshot = _register_one(root, src, args.type, ts, sources)
        sources_path.write_text(
            yaml.dump(sources, default_flow_style=False, allow_unicode=True, sort_keys=False)
        )
        print(f"Registered {src_id} ({args.type}) — raw preserved at {snapshot.relative_to(root)}")
        return

    # --- Folder: walk recursively, register document files, report coverage ---
    registered, skipped, subdirs = [], [], set()
    for path in sorted(src.rglob("*")):
        rel = path.relative_to(src)
        if any(part in IGNORE_DIRS or part.startswith(".") for part in rel.parts[:-1]):
            continue  # inside an ignored or hidden subdirectory
        if not path.is_file():
            continue
        if path.name in IGNORE_NAMES or path.name.startswith("."):
            continue
        if path.parent != src:
            subdirs.add(str(path.parent.relative_to(src)))
        if path.suffix.lower() in DOC_EXTS:
            src_id, _ = _register_one(root, path, args.type, ts, sources)
            registered.append((src_id, str(rel)))
        else:
            skipped.append(str(rel))

    sources_path.write_text(
        yaml.dump(sources, default_flow_style=False, allow_unicode=True, sort_keys=False)
    )

    if not registered:
        print(f"Warning: no document files ({', '.join(sorted(DOC_EXTS))}) found under {src}")
    print(f"Registered {len(registered)} file(s) across {len(subdirs) + 1} folder(s) "
          f"(including subfolders) from {src}:")
    for src_id, rel in registered:
        print(f"  {src_id}  {rel}")
    if skipped:
        print(f"Skipped {len(skipped)} non-document file(s) — review if any hold context:")
        for rel in skipped:
            print(f"  (skipped) {rel}")


def cmd_preflight(args):
    provided = [s.strip().zfill(2) for s in args.provided.split(",") if s.strip()]
    bad = [s for s in provided if s not in CORE_STAGE_ORDER]
    if bad:
        print(f"Error: --provided must be core stage ids 01-07; got {bad}")
        sys.exit(2)

    gaps = resolve_backfill(provided)
    infeasible = [g["stage"] for g in gaps if g["verdict"] == "infeasible"]
    lossy = [g["stage"] for g in gaps if g["verdict"] == "lossy"]

    label = {"faithful": "✅ faithful", "lossy": "⚠️  lossy", "infeasible": "⛔ infeasible"}
    print(f"Provided: {', '.join(provided) or '(none)'}")
    if not gaps:
        print("No upstream gaps to backfill.")
    for g in gaps:
        nm = STAGE_NAMES.get(g["stage"], g["stage"])
        frm = f"  (from {g['derived_from']})" if g["derived_from"] else ""
        print(f"  {g['stage']} {nm}: {label[g['verdict']]}{frm}")

    if infeasible:
        print()
        print("⛔ BLOCKED — these stages cannot be faithfully reconstructed from what")
        print("   you provided:", ", ".join(infeasible))
        print("   Provide at least a PRD (03) and/or design spec (04), or the listed")
        print("   stages directly, then retry.")
        sys.exit(1)
    if lossy:
        print()
        print("⚠️  Lossy backfill for:", ", ".join(lossy),
              "— review these carefully before approving.")
    sys.exit(0)


def _ensure_stage_entry(meta, stage_id, origin):
    try:
        return get_stage(meta, stage_id)
    except KeyError:
        pass
    entry = {
        "id": stage_id,
        "name": STAGE_NAMES[stage_id],
        "status": "pending",
        "approved_at": None,
        "content_hash": None,
        "upstream_hashes_at_approval": {},
        "regeneration_count": 0,
        "optional": stage_id in {"08", "09"},
        "origin": origin,
    }
    # Insert in canonical STAGE_ORDER position so stages[] stays ordered.
    order = {sid: i for i, sid in enumerate(STAGE_ORDER)}
    idx = len(meta["stages"])
    for i, s in enumerate(meta["stages"]):
        if order.get(s["id"], 999) > order.get(stage_id, 999):
            idx = i
            break
    meta["stages"].insert(idx, entry)
    return entry


def cmd_commit(args):
    root = resolve_project()
    stage_id = args.stage_id.zfill(2) if args.stage_id.isdigit() else args.stage_id
    if stage_id not in STAGE_NAMES:
        print(f"Error: unknown stage '{stage_id}'. Valid: {', '.join(STAGE_NAMES)}")
        sys.exit(1)

    apath = artifact_path(root, stage_id)
    if not apath.exists():
        print(f"Error: artifact slot {apath.name} does not exist. The skill must "
              f"write the body before commit.")
        sys.exit(1)

    meta = load_meta(root)
    stage_meta = _ensure_stage_entry(meta, stage_id, args.kind)
    stage_meta["origin"] = args.kind

    fm, body = fm_read(str(apath))
    fm.setdefault("stage", f"{stage_id}-{STAGE_NAMES[stage_id]}")
    fm.setdefault("project", meta.get("project_slug"))
    fm["origin"] = args.kind
    if args.source_name:
        fm["source_filename"] = args.source_name
    if args.source_format:
        fm["source_format"] = args.source_format

    if args.status == "draft":
        fm["status"] = "draft"
        stage_meta["status"] = "draft"
        fm_write(str(apath), fm, body)
        save_meta(meta, root)
        # The wiki/understanding docs are model-produced — record the model that
        # generated them, mirroring the stage skills' stage_generated event.
        if args.kind in ("generated", "backfilled"):
            event = "stage_generated" if args.kind == "generated" else "stage_backfilled_draft"
            try:
                log(event, root, stage_id, {
                    "generated_hash": hash_artifact_body(str(apath)),
                    "model": args.model,
                    "model_tier": model_tier_for_stage(stage_id),
                    "prompt_version": args.prompt_version,
                    "notes": [],
                    "origin": args.kind,
                })
            except Exception as e:
                print(f"Warning: telemetry logging failed: {e}")
        print(f"Stage {stage_id} ({STAGE_NAMES[stage_id]}) committed as draft "
              f"(origin={args.kind}). Approve with /pm-approve {stage_id}.")
        return

    # status == approved
    validation_findings = []
    if stage_id in {"03", "04", "05", "06"}:
        validation_findings = validate_artifact(root, stage_id, apath)
        if validation_findings:
            print(f"Warning: Stage {stage_id} has artifact contract findings; import approval will continue:")
            print(format_findings(validation_findings))

    content_hash = hash_artifact_body(str(apath))
    ts = _now()
    fm["status"] = "approved"
    fm["approved_at"] = ts
    fm["approved_by"] = _pm()
    fm["content_hash"] = content_hash
    fm_write(str(apath), fm, body)

    upstream = {uid: get_stage(meta, uid).get("content_hash")
                for uid in upstream_stage_ids(stage_id, meta)}
    stage_meta["status"] = "approved"
    stage_meta["approved_at"] = ts
    stage_meta["content_hash"] = content_hash
    stage_meta["upstream_hashes_at_approval"] = upstream
    save_meta(meta, root)

    event = "stage_imported" if args.kind == "imported" else (
        "stage_backfilled" if args.kind == "backfilled" else "stage_approved")
    payload = {
        "origin": args.kind,
        "approved_hash": content_hash,
        "source_format": args.source_format,
        "source_filename": args.source_name,
        "derived_from": args.derived_from,
    }
    # Backfilled (reverse-generated) and generated artifacts are model-produced;
    # imported ones are the PM's own authored docs, so no model applies there.
    if args.kind in ("generated", "backfilled"):
        payload["model"] = args.model
        payload["model_tier"] = model_tier_for_stage(stage_id)
    try:
        log(event, root, stage_id, payload)
    except Exception as e:
        print(f"Warning: telemetry logging failed: {e}")

    if validation_findings:
        try:
            log("artifact_validation_warning", root, stage_id, {
                "contract_version": fm.get("artifact_contract_version"),
                "origin": args.kind,
                "findings": [finding.as_dict() for finding in validation_findings],
            })
        except Exception as e:
            print(f"Warning: artifact validation telemetry failed: {e}")

    # Reuse post-approve for HTML companions (04/05), staleness cascade, push.
    hook = Path.home() / ".pm-os" / "hooks" / "post-approve.py"
    if hook.exists():
        env = os.environ.copy()
        env["PM_OS_STAGE"] = stage_id
        subprocess.run([sys.executable, str(hook)], env=env, cwd=str(root))

    print(f"Stage {stage_id} ({STAGE_NAMES[stage_id]}) committed as approved "
          f"(origin={args.kind}). Hash: {content_hash[:12]}")


def cmd_prepare_codebase(args):
    root = resolve_project()
    raw = args.path

    if raw.startswith(("https://", "http://", "git@")):
        target = root / ".codebase"
        if target.exists():
            # Validate that the existing checkout matches the requested URL so a
            # retry with a different URL doesn't silently scan the wrong codebase.
            remote_r = subprocess.run(
                ["git", "-C", str(target), "remote", "get-url", "origin"],
                capture_output=True, text=True,
            )
            existing_url = remote_r.stdout.strip() if remote_r.returncode == 0 else "(unknown)"
            if existing_url != raw:
                print(
                    f"Error: .codebase/ already exists but its remote is\n"
                    f"  {existing_url!r}\n"
                    f"not the requested\n"
                    f"  {raw!r}\n"
                    "Remove .codebase/ manually to re-clone with the new URL, "
                    "or pass the same URL to reuse the existing checkout."
                )
                sys.exit(1)
            print(f"Reusing existing .codebase/ (remote matches {existing_url!r}).")
        else:
            print(f"Cloning {raw} → {target} (--depth 1)…")
            r = subprocess.run(
                ["git", "clone", "--depth", "1", raw, str(target)],
                capture_output=True, text=True,
            )
            if r.returncode != 0:
                print(f"Error: git clone failed:\n{r.stderr}")
                sys.exit(1)
        local_path = target
    else:
        local_path = Path(raw).resolve()
        if not local_path.is_dir():
            print(f"Error: codebase path '{raw}' is not a directory.")
            sys.exit(1)

    sha = None
    sha_r = subprocess.run(
        ["git", "-C", str(local_path), "rev-parse", "HEAD"],
        capture_output=True, text=True,
    )
    if sha_r.returncode == 0:
        sha = sha_r.stdout.strip()

    meta = load_meta(root)
    meta["codebase_path"] = str(local_path)
    if sha:
        meta["codebase_ref"] = sha
    save_meta(meta, root)

    gitignore = root / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text(encoding="utf-8")
        if ".codebase/" not in content:
            gitignore.write_text(content.rstrip() + "\n.codebase/\n", encoding="utf-8")
    else:
        gitignore.write_text(".codebase/\n", encoding="utf-8")

    print(f"Codebase prepared: {local_path}")
    if sha:
        print(f"Recorded codebase_ref: {sha[:12]}")


def main():
    parser = argparse.ArgumentParser(description="PM-OS context-intake mechanical state.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_reg = sub.add_parser("register", help="Preserve + register a raw source.")
    p_reg.add_argument("file")
    p_reg.add_argument("--type", default="context",
                       help="source type: context|brief|scope|prd|design|research|...")
    p_reg.set_defaults(func=cmd_register)

    p_pre = sub.add_parser("preflight", help="Backfill-feasibility verdicts for a combo.")
    p_pre.add_argument("--provided", required=True, help="comma-separated core stage ids, e.g. 02,03,04")
    p_pre.set_defaults(func=cmd_preflight)

    p_com = sub.add_parser("commit", help="Commit a written artifact slot to draft/approved.")
    p_com.add_argument("stage_id")
    p_com.add_argument("--kind", required=True, choices=["generated", "imported", "backfilled"])
    p_com.add_argument("--status", required=True, choices=["draft", "approved"])
    p_com.add_argument("--source-name", dest="source_name", default=None)
    p_com.add_argument("--source-format", dest="source_format", default=None)
    p_com.add_argument("--derived-from", dest="derived_from", default=None)
    p_com.add_argument("--model", default=None,
                       help="Actual model id that produced this artifact "
                            "(for generated/backfilled kinds; the agent fills in its own id).")
    p_com.add_argument("--prompt-version", dest="prompt_version", default=None,
                       help="prompt_version of the generating skill, recorded on generated "
                            "stage_generated events to match the documented schema.")
    p_com.set_defaults(func=cmd_commit)

    p_prep = sub.add_parser("prepare-codebase",
                             help="Clone or validate a codebase and record its git SHA in meta.")
    p_prep.add_argument("path", help="GitHub URL (https://... or git@...) or local directory path.")
    p_prep.set_defaults(func=cmd_prepare_codebase)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
