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
import hashlib
import os
import re
import shutil
import subprocess
import sys
import zipfile
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
from hashing import hash_artifact_body, stage_content_hash, CompositeHashError
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
# Anything else (archives, binaries, junk) is reported as skipped rather than
# silently snapshotted — honoring the skill's "nothing is silent" rule.
# v4 (adaptive context pack) adds images, PPTX, and XLSX: these are registered
# and modality-tagged here, but their *content* extraction is the runtime's job
# (multimodal reading or the pdf/pptx/xlsx skills) and may degrade explicitly.
TEXT_EXTS = {".md", ".markdown", ".txt", ".rst"}
PDF_EXTS = {".pdf"}
DOC_OFFICE_EXTS = {".docx", ".doc", ".rtf"}
SLIDE_EXTS = {".pptx", ".ppt"}
SHEET_EXTS = {".xlsx", ".xls", ".csv", ".tsv"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".svg"}
DOC_EXTS = TEXT_EXTS | PDF_EXTS | DOC_OFFICE_EXTS | SLIDE_EXTS | SHEET_EXTS | IMAGE_EXTS

# Inferred modality from extension — recorded deterministically at registration so
# the SKILL's synthesis knows what kind of source it is reading before it opens it.
# (Authority/role/date/extraction-quality are judgment fields the SKILL fills in.)
_MODALITY_BY_EXT = {}
for _e in TEXT_EXTS:
    _MODALITY_BY_EXT[_e] = "text"
for _e in PDF_EXTS:
    _MODALITY_BY_EXT[_e] = "pdf"
for _e in DOC_OFFICE_EXTS:
    _MODALITY_BY_EXT[_e] = "document"
for _e in SLIDE_EXTS:
    _MODALITY_BY_EXT[_e] = "slides"
for _e in SHEET_EXTS:
    _MODALITY_BY_EXT[_e] = "spreadsheet"
for _e in IMAGE_EXTS:
    _MODALITY_BY_EXT[_e] = "image"


def _modality_for(path: Path) -> str:
    return _MODALITY_BY_EXT.get(path.suffix.lower(), "unknown")


# Modalities whose text extraction *might* be lossy — image-only content, or a
# layout that can scramble on extraction. These are tagged `unverified` (NOT
# `lossy`) at registration: it is a "confirm before trusting" flag, not a verdict.
# A `.pptx`/`.xlsx` read through the pptx/xlsx skill extracts text, tables, and
# notes cleanly, so the SKILL resolves the tag to `clean` or `lossy` after actually
# reading the source. Until then the SKILL must not mark a claim sourced from one
# High confidence without confirming a clean extraction.
UNVERIFIED_BY_DEFAULT = {"image", "slides", "spreadsheet"}

# Never descend into these — engine/state dirs and OS cruft, not PM context.
IGNORE_DIRS = {".history", ".git", "__pycache__", ".meta", "node_modules"}
IGNORE_NAMES = {".DS_Store", "Thumbs.db", ".meta.yaml", ".sources.yaml"}

ANSWERED_RE = re.compile(r"^\s*-\s*\[[xX]\]\s*ANSWERED:\s*(.+?)\s*$")
SKIPPED_RE = re.compile(r"^\s*-\s*\[\s*\]\s*SKIPPED:\s*(.+?)\s*$")


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

    modality = _modality_for(src)
    sources.append({
        "id": src_id,
        "type": src_type,
        "uri": str(src),
        "captured_at": ts,
        "snapshot": str(snapshot.relative_to(root)),
        "summary_hash": None,
        # v4 adaptive-context-pack inferred metadata. Modality is deterministic
        # (from extension); the rest are judgment fields the SKILL fills in during
        # synthesis and the PM confirms only when uncertain or consequential. They
        # are seeded here so the shape is always present and never silently absent.
        "modality": modality,
        "inferred_role": None,        # brief | scope | prd | design | market-research | reviews | competitor | meeting-notes | ...
        "author": None,               # person/org credited as the source's author
        "document_date": None,        # the date the source itself carries, if any
        "authority": None,            # authoritative | secondary | hearsay
        "extraction_quality": ("unverified" if modality in UNVERIFIED_BY_DEFAULT else None),
        "uncertainty": ([f"{modality} extraction unverified — read with the matching skill "
                         f"(pptx/xlsx), then resolve to clean or lossy before High confidence"]
                        if modality in UNVERIFIED_BY_DEFAULT else []),
    })
    try:
        log("context_ingested", root, None, {
            "source_id": src_id,
            "source_type": src_type,
            "source_filename": src.name,
            "snapshot": str(snapshot.relative_to(root)),
            "modality": modality,
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


def _question_from_bullet(line: str):
    stripped = line.strip()
    if not stripped.startswith("- "):
        return None
    question = stripped[2:].strip()
    checkbox = re.match(r"^\[[ xX]\]\s*(?:(?:ANSWERED|SKIPPED|QUESTION):\s*)?(.*)$", question)
    if checkbox:
        question = checkbox.group(1).strip()
    return question or None


def _parse_interview_markdown(text: str, *, skip_all: bool = False) -> dict:
    answered = []
    skipped = []
    in_skipped_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("## "):
            in_skipped_section = stripped.lower() in {"## skipped", "## skipped questions"}
            continue
        if skip_all:
            question = _question_from_bullet(line)
            if question:
                skipped.append(question)
            continue
        answered_match = ANSWERED_RE.match(line)
        if answered_match:
            answered.append(answered_match.group(1).strip())
            continue
        skipped_match = SKIPPED_RE.match(line)
        if skipped_match:
            skipped.append(skipped_match.group(1).strip())
            continue
        if in_skipped_section and stripped.startswith("- "):
            question = stripped[2:].strip()
            if question:
                skipped.append(question)
    return {
        "answered": answered,
        "skipped": skipped,
        "asked": len(answered) + len(skipped),
    }


def _is_pending_questions_file(text: str) -> bool:
    return any(line.strip().lower() in {"## interview questions", "## pending interview questions"}
               for line in text.splitlines())


def _write_known_unknowns(root: Path, skipped_questions: list[str], source_id: str) -> None:
    if not skipped_questions:
        return
    context_dir = root / PACK_DIR
    context_dir.mkdir(exist_ok=True)
    path = context_dir / "known-unknowns.md"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = []
    if not existing.strip():
        lines.extend([
            "# Known unknowns",
            "",
            "Skipped or unanswered PM interview questions. These remain unresolved gaps, not assumptions.",
            "",
        ])
    for question in skipped_questions:
        bullet = f"- {question} (source: {source_id})"
        if bullet not in existing:
            lines.append(bullet)
    if lines:
        path.write_text(existing.rstrip() + ("\n\n" if existing.strip() else "") + "\n".join(lines) + "\n",
                        encoding="utf-8")


def _interview_source_ids(root: Path) -> list:
    sources_path = root / ".sources.yaml"
    if not sources_path.exists():
        return []
    sources = yaml.safe_load(sources_path.read_text(encoding="utf-8")) or []
    return [
        s["id"] for s in sources
        if s.get("origin") == "interview" and s.get("confidence") == "high" and s.get("id")
    ]


def cmd_record_interview(args):
    root = resolve_project()
    answers_arg = args.interview_answers or args.answers_file
    if not answers_arg:
        print("No interview answers supplied; nothing to record.")
        return
    src = Path(answers_arg).expanduser()
    if not src.exists():
        print(f"Error: interview answers file not found: {src}")
        sys.exit(1)
    if not src.is_file():
        print(f"Error: interview answers path must be a file: {src}")
        sys.exit(1)

    ts = _now()
    sources_path = root / ".sources.yaml"
    sources = []
    if sources_path.exists():
        sources = yaml.safe_load(sources_path.read_text()) or []

    src_id, snapshot = _register_one(root, src, "context", ts, sources)
    source = next(s for s in sources if s["id"] == src_id)
    source.update({
        "authorship": "pm",
        "origin": "interview",
        "confidence": "high",
        "author": _pm(),
    })
    sources_path.write_text(
        yaml.dump(sources, default_flow_style=False, allow_unicode=True, sort_keys=False)
    )
    text = src.read_text(encoding="utf-8")
    skip_all = (
        os.environ.get("PM_OS_INTERVIEW", "").strip().lower() == "skip"
        or (not sys.stdin.isatty() and not args.interview_answers and _is_pending_questions_file(text))
    )
    counts = _parse_interview_markdown(text, skip_all=skip_all)
    _write_known_unknowns(root, counts["skipped"], src_id)
    # On a standalone rerun (/pm-interview) the recorder stays silent: pm_interview.py
    # resolve logs the single interview_conducted mode:rerun event. Emitting here too
    # would double-count one rerun as both an intake and a rerun pass.
    if getattr(args, "mode", "intake") != "rerun":
        try:
            log("interview_conducted", root, None, {
                "source_id": src_id,
                "asked": counts["asked"],
                "answered": len(counts["answered"]),
                "skipped": len(counts["skipped"]),
            })
        except Exception as e:
            print(f"Warning: telemetry logging failed: {e}")
    print(f"Recorded interview answers as {src_id} (context) — raw preserved at {snapshot.relative_to(root)}")


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
    interview_sources = _interview_source_ids(root) if args.kind == "backfilled" else []
    if interview_sources:
        fm["interview_sources"] = interview_sources
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
                    "interview_sources": interview_sources,
                })
            except Exception as e:
                print(f"Warning: telemetry logging failed: {e}")
        print(f"Stage {stage_id} ({STAGE_NAMES[stage_id]}) committed as draft "
              f"(origin={args.kind}). Approve with /pm-approve {stage_id}.")
        return

    # status == approved
    validation_findings = []
    if stage_id in {"03", "04", "05", "06", "08"}:
        validation_findings = validate_artifact(root, stage_id, apath)
        if validation_findings:
            print(f"Warning: Stage {stage_id} has artifact contract findings; import approval will continue:")
            print(format_findings(validation_findings))

    try:
        content_hash = stage_content_hash(root, stage_id, apath)
    except CompositeHashError as e:
        print(f"Error: cannot commit stage {stage_id} — context pack is invalid: {e}")
        sys.exit(1)
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
        "interview_sources": interview_sources,
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


# --- Adaptive context pack (00-context/) mechanical operations -----------------
#
# The SKILL writes the wiki index, evidence ledger, source inventory, and views;
# these commands only move bytes, compute hashes, and validate manifest safety.
# Member order in the manifest is FIXED and canonical (it drives composite
# hashing): wiki index, then evidence ledger, then source inventory, then views
# in sorted filename order.

PACK_DIR = "00-context"
PACK_MANIFEST_REL = "00-context/manifest.yaml"
WIKI_INDEX_REL = "00-context-wiki.md"
EVIDENCE_REL = "00-context/evidence.yaml"
SOURCES_REL = "00-context/sources.md"
VIEWS_DIR_REL = "00-context/views"


def _pack_member_kind(relpath: str) -> str:
    return "yaml" if relpath.endswith((".yaml", ".yml")) else "markdown"


def _discover_pack_members(root: Path) -> list:
    """Enumerate context-pack members in FIXED canonical order, with computed hashes.

    Order: wiki index → evidence ledger → source inventory → views (sorted). Only
    files that exist are included; the wiki index is required. Never includes the
    manifest itself (would be circular).
    """
    from hashing import composite_member_hash

    ordered = []
    if (root / WIKI_INDEX_REL).exists():
        ordered.append(WIKI_INDEX_REL)
    if (root / EVIDENCE_REL).exists():
        ordered.append(EVIDENCE_REL)
    if (root / SOURCES_REL).exists():
        ordered.append(SOURCES_REL)
    views_dir = root / VIEWS_DIR_REL
    if views_dir.is_dir():
        for v in sorted(views_dir.glob("*.md")):
            ordered.append(str(v.relative_to(root)))

    members = []
    for rel in ordered:
        kind = _pack_member_kind(rel)
        m = {"path": rel, "kind": kind}
        members.append(m)
        # compute hash for the recorded table (validated separately from the
        # composite input, which excludes this table to avoid circularity).
        m["hash"] = composite_member_hash(root, m)
    return members


def cmd_pack_manifest(args):
    """(Re)write 00-context/manifest.yaml from the files the SKILL populated.

    Deterministic: fixed member order, computed per-member hashes, safety-validated
    before write. Idempotent — re-running on an unchanged pack produces an
    identical manifest.
    """
    root = resolve_project()
    pack_dir = root / PACK_DIR
    if not pack_dir.is_dir():
        print(f"Error: {PACK_DIR}/ does not exist. The skill must write the pack "
              f"files (wiki index + 00-context/...) before building the manifest.")
        sys.exit(1)
    if not (root / WIKI_INDEX_REL).exists():
        print(f"Error: {WIKI_INDEX_REL} is required as the pack's index member.")
        sys.exit(1)

    members = _discover_pack_members(root)
    manifest = {
        "schema_version": 1,
        "stage": "00w",
        "members": members,
        "stage_affinities": args_affinities(args),
    }
    manifest_path = root / PACK_MANIFEST_REL
    manifest_path.write_text(
        yaml.dump(manifest, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    # Validate what we just wrote (catches a member the skill left unsafe).
    from hashing import load_manifest_members, CompositeHashError
    try:
        load_manifest_members(root)
    except CompositeHashError as e:
        print(f"Error: manifest failed safety validation after write: {e}")
        sys.exit(1)

    # Record context_pack metadata in meta so readers know the pack exists.
    meta = load_meta(root)
    meta["context_pack"] = {
        "manifest": PACK_MANIFEST_REL,
        "member_count": len(members),
    }
    save_meta(meta, root)

    print(f"Wrote {PACK_MANIFEST_REL} with {len(members)} member(s):")
    for m in members:
        print(f"  [{m['kind']}] {m['path']}  {m['hash'][:12]}")


def args_affinities(args):
    """Parse optional --affinity 'view.md=01,02' repeatable flags into a map."""
    out = {}
    for spec in (args.affinity or []):
        if "=" not in spec:
            continue
        path, stages = spec.split("=", 1)
        out[path.strip()] = [s.strip().zfill(2) for s in stages.split(",") if s.strip()]
    return out


def cmd_pack_validate(args):
    """Validate context-pack manifest safety and report stale recorded hashes."""
    root = resolve_project()
    from hashing import load_manifest_members, validate_manifest_hashes, CompositeHashError
    try:
        members = load_manifest_members(root)
    except CompositeHashError as e:
        print(f"⛔ Manifest invalid: {e}")
        sys.exit(1)
    stale = validate_manifest_hashes(root)
    print(f"Manifest OK — {len(members)} member(s), order fixed.")
    if stale:
        print("⚠️  Recorded hashes are stale for (pack edited since manifest build):")
        for s in stale:
            print(f"  {s}")
        print("Re-run `pm_context_import.py pack-manifest` to refresh the manifest, "
              "then re-approve 00w.")
        sys.exit(2)
    print("All recorded member hashes are current.")
    sys.exit(0)


def cmd_upgrade_pack(args):
    """Snapshot an existing flat single-file wiki and scaffold the modular pack dir.

    Preserves the old 00-context-wiki.md (and any PM annotations) in .history/,
    creates 00-context/ + views/, and flips 00w back to draft so the SKILL can
    rebuild the modular pack from the registered sources. The rebuilt 00w (and
    00u) remain drafts pending explicit PM approval — this never re-approves.
    """
    root = resolve_project()
    meta = load_meta(root)
    try:
        w = get_stage(meta, "00w")
    except KeyError:
        print("Error: this project has no 00w (context wiki) to upgrade. Run "
              "/pm-context-import first.")
        sys.exit(1)

    wiki = root / WIKI_INDEX_REL
    if not wiki.exists():
        print(f"Error: {WIKI_INDEX_REL} not found — nothing to upgrade.")
        sys.exit(1)
    if (root / PACK_MANIFEST_REL).exists():
        print("This project already has a modular context pack "
              f"({PACK_MANIFEST_REL}). Nothing to upgrade.")
        sys.exit(0)

    # Snapshot the current flat wiki (content + PM annotations) into history.
    hist = root / ".history"
    hist.mkdir(exist_ok=True)
    stamp = _now().replace(":", "").replace("-", "")[:15]
    snap = hist / f"00-context-wiki.{stamp}.pre-upgrade.md"
    snap.write_bytes(wiki.read_bytes())

    # Scaffold the modular pack directory.
    (root / PACK_DIR).mkdir(exist_ok=True)
    (root / VIEWS_DIR_REL).mkdir(parents=True, exist_ok=True)

    # Flip 00w back to draft so the rebuilt pack must be re-approved.
    w["status"] = "draft"
    w["content_hash"] = None
    save_meta(meta, root)
    try:
        update_status(str(wiki), "draft")
    except Exception:
        pass

    try:
        log("context_pack_upgrade_started", root, "00w", {
            "preserved_snapshot": str(snap.relative_to(root)),
        })
    except Exception as e:
        print(f"Warning: telemetry logging failed: {e}")

    print(f"Upgrade scaffolded. Old wiki preserved at {snap.relative_to(root)}.")
    print(f"Created {PACK_DIR}/ and {VIEWS_DIR_REL}/.")
    print("00w is now a draft. The skill should rebuild the modular pack from the")
    print("registered sources, run `pack-manifest`, then the PM re-approves 00w + 00u.")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_extract_zip(zip_path: Path, dest_dir: Path) -> None:
    """Extract a zip, refusing any member that would escape ``dest_dir``.

    The archive is untrusted PM input, so guard against zip-slip (absolute paths
    or ``..`` traversal) before writing anything to disk.
    """
    dest_dir = dest_dir.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.namelist():
            resolved = (dest_dir / member).resolve()
            if resolved != dest_dir and dest_dir not in resolved.parents:
                raise SystemExit(
                    f"Error: refusing to extract zip — entry escapes the extraction "
                    f"directory: {member!r}"
                )
        archive.extractall(dest_dir)


def _prepare_from_zip(root: Path, source: Path) -> Path:
    """Extract a codebase zip into .codebase/ as a self-contained git checkout.

    A synthetic single commit is created (unless the archive already carries its
    own .git) so the read-only inventory and the E2 lifecycle — both of which
    shell out to git for SHA pinning, dirty-state, and refresh — treat a zip
    source identically to a clone. The original zip on disk is never modified.
    """
    target = root / ".codebase"
    marker = root / ".codebase-source"
    zip_sha = _sha256_file(source)
    stamp = f"zip:{zip_sha}"

    if target.exists():
        prior = marker.read_text(encoding="utf-8").strip().splitlines()[0] if marker.exists() else ""
        if prior == stamp:
            print(f"Reusing existing .codebase/ (same zip: {source.name}).")
            return target
        print(
            f"Error: .codebase/ already exists but was not prepared from this zip.\n"
            "Remove .codebase/ (and .codebase-source) manually to re-extract, or pass "
            "the same archive to reuse the existing extraction."
        )
        sys.exit(1)

    temp = root / f".codebase.tmp-{os.getpid()}"
    if temp.exists():
        shutil.rmtree(str(temp), ignore_errors=True)
    temp.mkdir()
    try:
        print(f"Extracting {source.name} → {target}…")
        _safe_extract_zip(source, temp)
        # A cleanly zipped project is usually wrapped in one top-level folder;
        # unwrap it so .codebase/ is the code root, not code root's parent.
        entries = [item for item in temp.iterdir() if item.name != "__MACOSX"]
        content_root = entries[0] if len(entries) == 1 and entries[0].is_dir() else temp
        os.replace(str(content_root), str(target))
    finally:
        if temp.exists():
            shutil.rmtree(str(temp), ignore_errors=True)

    if not (target / ".git").is_dir():
        init = subprocess.run(
            ["git", "init", "-b", "main", str(target)], capture_output=True, text=True,
        )
        if init.returncode != 0:  # older git without -b: fall back to default branch
            subprocess.run(["git", "init", str(target)], capture_output=True, text=True)
        subprocess.run(["git", "-C", str(target), "add", "-A"], capture_output=True, text=True)
        subprocess.run(
            [
                "git", "-C", str(target),
                "-c", "user.email=pm-os@localhost", "-c", "user.name=PM-OS",
                "commit", "--quiet", "--allow-empty",
                "-m", f"PM-OS snapshot of {source.name} (sha256 {zip_sha[:12]})",
            ],
            capture_output=True, text=True,
        )

    marker.write_text(f"{stamp}\n{source}\n", encoding="utf-8")
    return target


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
        source = Path(raw).expanduser().resolve()
        if source.is_dir():
            local_path = source
        elif source.is_file() and zipfile.is_zipfile(source):
            local_path = _prepare_from_zip(root, source)
        elif source.is_file():
            print(f"Error: codebase path '{raw}' is a file but not a valid .zip archive.")
            sys.exit(1)
        else:
            print(f"Error: codebase path '{raw}' is not a git URL, a directory, or a .zip archive.")
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
    ignore_entries = [".codebase/", ".codebase-source"]
    if gitignore.exists():
        content = gitignore.read_text(encoding="utf-8")
        missing = [entry for entry in ignore_entries if entry not in content]
        if missing:
            gitignore.write_text(content.rstrip() + "\n" + "\n".join(missing) + "\n", encoding="utf-8")
    else:
        gitignore.write_text("\n".join(ignore_entries) + "\n", encoding="utf-8")

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

    p_int = sub.add_parser("record-interview",
                           help="Register PM interview answers as high-confidence context.")
    p_int.add_argument("answers_file", nargs="?", help="Markdown file containing PM interview answers.")
    p_int.add_argument("--interview-answers", dest="interview_answers", default=None,
                       help="Markdown answers file for non-interactive runs.")
    p_int.add_argument("--mode", choices=["intake", "rerun"], default="intake",
                       help="intake (default) logs an interview_conducted event; rerun stays silent "
                            "because pm_interview.py resolve logs the single rerun event.")
    p_int.set_defaults(func=cmd_record_interview)

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
                             help="Clone/extract or validate a codebase and record its git SHA in meta.")
    p_prep.add_argument(
        "path",
        help="git URL (https://…, http://…, or git@…), a local directory, or a .zip archive.",
    )
    p_prep.set_defaults(func=cmd_prepare_codebase)

    p_man = sub.add_parser("pack-manifest",
                           help="(Re)build 00-context/manifest.yaml from the pack files the skill wrote.")
    p_man.add_argument("--affinity", action="append", default=[],
                       help="Repeatable view affinity, e.g. --affinity 'views/voc.md=02,03'.")
    p_man.set_defaults(func=cmd_pack_manifest)

    p_pv = sub.add_parser("pack-validate",
                          help="Validate context-pack manifest safety + report stale hashes.")
    p_pv.set_defaults(func=cmd_pack_validate)

    p_up = sub.add_parser("upgrade-pack",
                          help="Snapshot an existing flat wiki and scaffold the modular pack (opt-in).")
    p_up.set_defaults(func=cmd_upgrade_pack)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
