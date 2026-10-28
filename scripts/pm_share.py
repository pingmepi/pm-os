#!/usr/bin/env python3
"""Export approved PM-OS artifacts in three modes.

Raw mode (default) — a single stage or every approved/edited stage,
concatenated verbatim, for a quick paste into email/Slack/a doc.

Package mode (--package) — a read-only, decomposed handoff package written
under `handoff/<audience>/` for one or all of dev/design/qa/business,
assembled by walking the traceability spine (US-### -> its FR-###s -> its
UJ-### journey -> its covering TC-###s -> its serving SCR-### screens). It
never touches gate/hash/status — regenerate it after any PRD/QA/design
re-approval. `--audience` scopes a rebuild to exactly one audience folder,
leaving sibling audience folders (built in earlier runs) untouched; omitting
it rebuilds all four in one pass.

The mechanics in this file are invoked by the `pm-handoff` skill (the sole
callable skill for raw/package/Jira export — see skills/pm-handoff/SKILL.md).
`pm_handoff.py` (Jira ticket export) writes into the same `./handoff/` root
directory but never into an audience subfolder, so the two scripts no longer
collide regardless of invocation order (see `_resolve_handoff_root` below).

Usage:
    python3 pm_share.py                    # raw text, all approved stages
    python3 pm_share.py 03                 # raw text, stage 03 only
    python3 pm_share.py --output out.md    # raw text to a file instead of stdout
    python3 pm_share.py --package                          # write handoff/{dev,design,qa,business}/
    python3 pm_share.py --package --audience dev           # rebuild only handoff/dev/
    python3 pm_share.py --package --output DIR             # write to DIR instead
    python3 pm_share.py --package --html                   # also emit an index.html per audience
    python3 pm_share.py ... --allow-secrets                # export despite likely secrets (logged)
    python3 pm_share.py --package --allow-release-errors   # publish despite release-check errors (logged)

Every mode first scans the artifacts it would export for likely secrets
(lib/secret_scan, GH #63 PMOS-001) and refuses — writing nothing — unless
--allow-secrets is given. Output names file:line + kind, never the value.

Package mode then builds into a temporary folder and runs the release check
(lib/release_check, backlog #72) on each audience folder exactly as it would
ship. Release-check errors refuse the export, again writing nothing under
handoff/, unless --allow-release-errors is given (logged). Only a package that
passes (or is overridden) is published into handoff/<audience>/.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, os.environ.get("PM_OS_LIB_PATH") or str(Path.home() / ".pm-os" / "lib"))

from console import ensure_utf8_stdio  # noqa: E402
ensure_utf8_stdio()

from artifact_contracts import (  # noqa: E402
    _sections,
    information_architecture_section,
    split_screen_blocks,
    split_stable_id_blocks,
    split_task_blocks,
    split_test_case_blocks,
    split_user_story_blocks,
    work_breakdown_section,
)
from delivery_map import build_prd_delivery_map, body_of, normalize_title, title_of  # noqa: E402
from enhancement import EnhancementDeltaError, active_enhancement_delta  # noqa: E402
from frontmatter import read as fm_read  # noqa: E402
from hashing import mark_edited_in_memory  # noqa: E402
from project import artifact_path, load_meta, resolve_project, STAGE_NAMES  # noqa: E402
import readiness  # noqa: E402
import release_check  # noqa: E402
import release_record  # noqa: E402
import secret_scan  # noqa: E402
import traceability  # noqa: E402

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:  # pragma: no cover - jinja2 is a declared runtime dep
    Environment = None  # type: ignore

NOT_CAPTURED = "— not captured in source —"
TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
# Dropped into each generated audience subfolder (handoff/<audience>/.pm-os-handoff)
# so a regeneration can safely clear a prior one without risking arbitrary user
# directories (see _prepare_audience_dir). The handoff/ root itself is never
# wiped — see _resolve_handoff_root.
HANDOFF_MARKER = ".pm-os-handoff"

AUDIENCES = ("dev", "design", "qa", "business")

# Which audience folders each category of content belongs in. A category may
# fan out into many files (stories, epics) or be a single file/tree. Kept as a
# single source of truth: both the write-dispatch loop and the per-audience
# README/HTML generators read from this, not scattered `if audience == "dev"`
# chains.
#
# Three rows (stories, epics, nfrs) came directly from examples given during
# scoping (backlog #29 / audience-folder design session); the rest are this
# implementation's proposal and are cheap to adjust later (one table edit).
# `wireframes` includes "dev" (not just design/qa) because each dev story file
# links directly into the prototype (backlog #29) — without the copy present
# in dev/, that link would dangle.
AUDIENCE_CATEGORIES: dict[str, set[str]] = {
    # Full read-only artifact projections (PMOS-002): the source-of-truth document
    # behind the decomposed stories/epics, not only the derived fragments. Dev gets
    # the PRD + TRD; design gets the PRD before design work and the design spec after
    # approval.
    "prd_full": {"dev", "design"},
    "trd_full": {"dev"},
    "design_spec_full": {"design"},
    "design_brief": {"design"},
    "designer_workflow": {"design"},
    "stories": {"dev", "design", "qa"},
    "requirements": {"dev", "qa"},
    "epics": {"dev", "business"},
    "overview": {"business"},
    "prioritization": {"dev", "business"},
    "user_journeys": {"dev", "design", "qa", "business"},
    "impact_analysis": {"dev", "design", "qa", "business"},
    "nfrs": {"dev", "design", "qa"},
    "qa_scenarios": {"qa"},
    "screen_map": {"design", "qa"},
    "wireframes": {"dev", "design", "qa"},
    # The readiness record (backlog #74): eval sets, test inputs and open
    # decisions still owed. Every audience sees what is outstanding.
    "readiness": {"dev", "design", "qa", "business"},
}


def _categories_for_audience(audience: str) -> set[str]:
    return {cat for cat, audiences in AUDIENCE_CATEGORIES.items() if audience in audiences}


def _load_live_meta(root: Path) -> dict:
    """.meta.yaml with stages edited since approval shown as `edited` (not saved), so
    an edited body is never exported or stamped as `approved`."""
    meta = load_meta(root)
    mark_edited_in_memory(root, meta)
    return meta


def _stage_status(meta: dict, stage_id: str) -> str | None:
    """Return the recorded status of a stage from .meta.yaml, or None if absent."""
    for stage in meta.get("stages", []):
        if stage.get("id") == stage_id:
            return stage.get("status")
    return None


def _design_mode(fm: dict | None, body: str | None) -> str | None:
    mode = (fm or {}).get("design_mode")
    if mode:
        return str(mode)
    if body and "This is a design brief, not a finished design spec" in body:
        return "brief"
    return None


def _resolve_handoff_root(out_dir: Path, root: Path) -> Path:
    """Resolve and validate the top-level `handoff/` directory, non-destructively.

    Unlike a package audience subfolder (see `_prepare_audience_dir`), the root
    is never wiped: `pm_handoff.py` writes `jira-plan.*`/`jira-import.*` at this
    same level, and this function's job is only to refuse an unsafe target
    (project root/ancestor/cwd) and ensure the directory exists — never to
    inspect or clear its contents.
    """
    out = _validate_handoff_root(out_dir, root)
    out.mkdir(parents=True, exist_ok=True)
    return out


def _validate_handoff_root(out_dir: Path, root: Path) -> Path:
    """The refusals of `_resolve_handoff_root`, without creating anything, so a
    caller can run them before the release check decides whether to publish."""
    out = out_dir.resolve()
    root_r = root.resolve()
    if out == root_r or out in root_r.parents:
        raise SystemExit(
            f"Error: refusing to write the handoff package to {out} — it is the "
            "project root or a parent of it, and would be erased. Pick a "
            "subdirectory (default: ./handoff/)."
        )
    if out == Path.cwd().resolve():
        raise SystemExit(
            f"Error: refusing to use the current directory ({out}) as the handoff "
            "output — it would be erased. Pick a dedicated subdirectory."
        )
    if out.exists() and out.is_file():
        raise SystemExit(f"Error: {out} is a file, not a directory.")
    return out


def _prepare_audience_dir(handoff_root: Path, audience: str) -> Path:
    """Resolve, validate, and clear ONE audience subfolder (handoff/<audience>/),
    leaving sibling audience folders and any root-level files (jira-plan.*,
    jira-import.*, the hub README) untouched. Mirrors the old whole-package
    guard, just scoped one directory deeper: refuses to `rmtree` an existing
    non-empty folder that lacks this tool's marker.
    """
    out = _check_audience_dir(handoff_root, audience)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    return out


def _check_audience_dir(handoff_root: Path, audience: str) -> Path:
    """The marker refusal of `_prepare_audience_dir`, without deleting anything."""
    out = (handoff_root / audience).resolve()
    if out.exists():
        if out.is_file():
            raise SystemExit(f"Error: {out} is a file, not a directory.")
        others = [p for p in out.iterdir() if p.name != HANDOFF_MARKER]
        if others and not (out / HANDOFF_MARKER).exists():
            raise SystemExit(
                f"Error: {out} already exists and is not a PM-OS handoff folder "
                f"(no {HANDOFF_MARKER} marker). Refusing to delete it. Remove it "
                "manually if it is stale, or pick a different --output."
            )
    return out


# A functional/umbrella requirement can be declared as a bullet
# (`- **FR-001 (...):**`) or an ordered-list item; never as a heading in the
# current stage-03 format. Bounded by the next such declaration.
_FR_BLOCK_START_RE = re.compile(
    r"^(?:[-*+]\s+|\d+\.\s+)?\**(?P<id>(?:FR|REQ)-\d{3,})\b",
    re.MULTILINE | re.IGNORECASE,
)
# A journey is always declared as a `###` heading per the stage-03 contract.
_UJ_BLOCK_START_RE = re.compile(
    r"^(?:#{1,6}\s+)?(?P<id>UJ-\d{3,})\b",
    re.MULTILINE | re.IGNORECASE,
)


def _split_blocks(text: str, start_re: "re.Pattern[str]") -> dict[str, str]:
    """Map each id `start_re` declares to the text block that introduces it,
    bounded by the next declaration (or end of text). `text` is expected to
    already be a single extracted section body, so no `##`-boundary handling
    is needed (mirrors split_test_case_blocks/split_user_story_blocks in
    lib/artifact_contracts.py, generalized for bullet- and heading-style ids)."""
    matches = list(start_re.finditer(text))
    blocks: dict[str, str] = {}
    for index, match in enumerate(matches):
        block_id = match.group("id").upper()
        if block_id in blocks:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        blocks[block_id] = text[match.start():end]
    return blocks


# --- package-mode helpers -----------------------------------------------------

# Filename slugs are capped. A requirement title written as a sentence once
# produced ~500-character filenames: past Windows' 260-character path limit
# (the package build crashed partway through) and past the 255-byte filename
# limit on macOS/Linux too (backlog #59). Every package filename is id-first
# (`REQ-001-<slug>.md`), so a truncated slug stays unique.
SLUG_MAX_CHARS = 60


def _slug(text: str, fallback: str = "item") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    if len(slug) > SLUG_MAX_CHARS:
        cut = slug[:SLUG_MAX_CHARS]
        # Prefer a word boundary, unless that would throw away most of the slug.
        boundary = cut.rfind("-")
        slug = (cut[:boundary] if boundary >= SLUG_MAX_CHARS // 2 else cut).strip("-")
    return slug or fallback


def _read_artifact(root: Path, stage_id: str):
    """Return (frontmatter, body) for a stage artifact, or (None, None) if absent."""
    path = artifact_path(root, stage_id)
    if not path.exists():
        return None, None
    try:
        return fm_read(str(path))
    except Exception:
        return None, None


def _stamp(root: Path, stage_id: str) -> str | None:
    """`03-prd.md@<hash12>` provenance tag for a source artifact, or None."""
    fm, _body = _read_artifact(root, stage_id)
    if fm is None:
        return None
    name = artifact_path(root, stage_id).name
    h = fm.get("content_hash") or fm.get("generated_hash")
    return f"{name}@{h[:12]}" if h else name


# Approval fields stamped on every exported file (backlog #71): a reader such as a
# build team's agent can tell which approved revision of which artifact it holds
# without recomputing a hash.
APPROVAL_KEYS = ("status", "version", "approved_by", "approved_at", "content_hash")


def _provenance(root: Path, meta: dict) -> dict[str, dict]:
    """Per-stage approval record for every stage artifact on disk, from meta
    (status, version, approval time, approved hash) and frontmatter (approver)."""
    records: dict[str, dict] = {}
    for stage in meta.get("stages", []):
        sid = str(stage.get("id"))
        try:
            apath = artifact_path(root, sid)
        except KeyError:
            continue
        if not apath.exists():
            continue
        fm, _ = _read_artifact(root, sid)
        fm = fm or {}
        approved_at = stage.get("approved_at") or fm.get("approved_at")
        records[sid] = {
            "artifact": apath.name,
            "status": stage.get("status") or fm.get("status"),
            "version": stage.get("version"),
            "approved_by": fm.get("approved_by"),
            "approved_at": str(approved_at) if approved_at else None,
            "content_hash": stage.get("content_hash") or fm.get("content_hash"),
        }
    return records


def _approval_fields(prov: dict[str, dict], stage_ids) -> dict:
    """Frontmatter fields for an exported file: the first (canonical) source's
    approval record at top level, and every source's record under `sources`."""
    records = [prov[sid] for sid in stage_ids if sid in prov]
    fields = {key: records[0][key] for key in APPROVAL_KEYS} if records else {}
    fields["sources"] = records
    return fields


def _section_of(body: str | None, title: str) -> str:
    if not body:
        return ""
    return _sections(body).get(title.strip().lower(), "")


def _story_title(story_id: str, block: str) -> str:
    """Best-effort human title from a block's declaration line.

    Tolerates a bold-wrapped id (`- **SCR-001 — Case queue**`, the design spec's screen
    shape) as well as the PRD's plain heading form, so the same helper names stories
    and screens.
    """
    first = block.strip().splitlines()[0] if block.strip() else ""
    cleaned = re.sub(r"^(?:#{1,6}\s+|[-*+]\s+|\d+\.\s+)?", "", first)
    cleaned = re.sub(rf"^\**{re.escape(story_id)}\**\b[\s:—–-]*", "", cleaned, flags=re.IGNORECASE)
    # normalize_title also clears a *mid-string* dangling ** that edge-only strip("*")
    # misses, matching the epic-title fix (PMOS-011).
    return normalize_title(cleaned) or story_id


def _strip_decl_line(block: str, decl_id: str | None = None) -> str:
    """Return a block with its leading id-declaration removed, so the template
    can supply a uniform heading regardless of how the source declared it.

    Multi-line blocks (e.g. a `### TC-001` heading followed by body
    paragraphs) drop the whole first line, as before. A single-line block
    (the common QA-plan style — `- TC-001: <description>. Covers REQ-001.`,
    the entire scenario on one line) instead has only the leading marker + id
    stripped from that line, so the body is preserved rather than emptied.
    """
    lines = block.strip().splitlines()
    if not lines:
        return ""
    if len(lines) > 1:
        return "\n".join(lines[1:]).strip()
    line = lines[0]
    cleaned = re.sub(r"^(?:#{1,6}\s+|[-*+]\s+|\d+\.\s+)?", "", line)
    if decl_id:
        cleaned = re.sub(rf"^\**{re.escape(decl_id)}\**[\s:—–-]*", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _screen_body(block: str, scr_id: str) -> str:
    """Screen body for a story file, trimmed to the screen's own content.

    A bullet-declared screen (`- **SCR-001 — …**` with indented sub-bullets) is bounded
    to its indented sub-list: any following non-indented prose (e.g. a global
    Information-Architecture narrative that isn't under its own heading, which
    _split_id_blocks folds into the preceding screen's block) is dropped rather than
    leaking into every story that touches the screen (backlog #35). A heading-declared
    screen keeps its full body — its content legitimately sits at column 0."""
    lines = block.rstrip().splitlines()
    if not lines:
        return ""
    first = lines[0]
    if not re.match(r"\s*[-*+]\s", first):  # heading/single-line — legitimately unindented
        return _strip_decl_line(block, scr_id)
    # Bullet-declared: keep only the lines more indented than the declaration (its own
    # sub-list). The first line at or below the declaration's indent is a new bullet or
    # unrelated prose and ends the screen.
    decl_indent = len(first) - len(first.lstrip())
    kept: list[str] = []
    for line in lines[1:]:
        if line.strip() == "":
            kept.append(line)
            continue
        if (len(line) - len(line.lstrip())) > decl_indent:
            kept.append(line)
        else:
            break
    return "\n".join(kept).strip()


def _render_story(ctx: dict) -> str:
    """Render the per-story Markdown via the overridable template.

    Uses a dedicated non-autoescaping environment: html_render._render_template
    autoescapes ``.j2`` (right for HTML, wrong for Markdown — it would turn ``&``
    into ``&amp;`` etc.).
    """
    if Environment is None:
        raise RuntimeError("jinja2 is required to render the handoff package")
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    # Serialize the frontmatter as a single YAML block rather than interpolating each
    # scalar unquoted in the template — a title/priority containing a colon-space
    # (e.g. "Search: filters and sort") otherwise emits invalid YAML (backlog #33).
    fm_fields = {
        "story_id": ctx.get("story_id"),
        "title": ctx.get("title"),
        "epic": ctx.get("epic"),
        "priority": ctx.get("priority"),
        **(ctx.get("approval") or {}),
        "generated_from": list(ctx.get("generated_from") or []),
        "canonical_source": ctx.get("canonical_source"),
        "generated_at": ctx.get("generated_at"),
    }
    frontmatter_block = yaml.safe_dump(
        fm_fields, default_flow_style=False, sort_keys=False, allow_unicode=True
    )
    return env.get_template("handoff-story.md.j2").render(frontmatter=frontmatter_block, **ctx)


def _render_requirement(ctx: dict) -> str:
    if Environment is None:
        raise RuntimeError("jinja2 is required to render the handoff package")
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    fm_fields = {
        "requirement_id": ctx.get("requirement_id"),
        "title": ctx.get("title"),
        "epic": ctx.get("epic"),
        "priority": ctx.get("priority"),
        "owning_stories": list(ctx.get("owning_stories") or []),
        **(ctx.get("approval") or {}),
        "generated_from": list(ctx.get("generated_from") or []),
        "canonical_source": ctx.get("canonical_source"),
        "generated_at": ctx.get("generated_at"),
    }
    frontmatter_block = yaml.safe_dump(
        fm_fields, default_flow_style=False, sort_keys=False, allow_unicode=True
    )
    return env.get_template("handoff-requirement.md.j2").render(frontmatter=frontmatter_block, **ctx)


def _screen_link(scr_id: str, has_proto: bool, anchored_ids: set[str]) -> str | None:
    """Relative link from a `stories/` or `reference/` file (both one level under
    an audience folder, same as `wireframes/`) into the copied prototype.

    Returns a working hash-anchored link only when the prototype actually
    declares `id="SCR-XXX"` for this screen (checked once, up front, against
    the copied prototype text) — otherwise falls back to a plain link to the
    prototype file (still useful, just not scrolled-to), or None if no
    prototype was copied at all. This is what keeps a project whose
    `05-prototype-mockup.html` predates the anchor requirement (backlog #29)
    safe: no dead `#SCR-XXX` link is ever emitted."""
    if not has_proto:
        return None
    if scr_id in anchored_ids:
        return f"../wireframes/prototype.html#{scr_id}"
    return "../wireframes/prototype.html"


def _screen_design_refs(spine: dict, scr_id: str) -> list[dict]:
    entry = ((spine.get("screens") or {}).get(scr_id) or {})
    return list(entry.get("design_refs") or [])


_DELTA_BASELINE_NOTE = (
    "> _Baseline reference — unchanged by this enhancement. The delta is in the "
    "changed stories and the enhancement dossier (README); the full artifact "
    "remains the canonical product-of-record and is not reproduced here._"
)

# Which stage each whole-artifact / project-level projection is scoped against.
_REF_STAGE = {
    "prioritization": "03", "user_journeys": "03", "impact_analysis": "03",
    "nfrs": "03", "qa_scenarios": "06", "prd_full": "03", "trd_full": "08",
    "design_spec_full": "04", "screen_map": "04",
}


def _enhancement_scope(enhancement_delta: dict | None) -> dict | None:
    """Delta-scoping sets for the package, or None outside an active enhancement."""
    if not enhancement_delta:
        return None
    changes = enhancement_delta["changes"]
    return {
        "changed_refs": {c["id"] for c in changes},
        "changed_stages": {str(c["stage"]) for c in changes},
        "baseline_stage_ids": {str(s) for s in (enhancement_delta.get("baseline_artifacts") or {})},
    }


def _delta_body(body: str | None, stage_id: str | None, scope: dict | None) -> str | None:
    """Scope a whole-artifact projection to the active enhancement delta.

    - Not an enhancement (scope None): full body unchanged.
    - Stage authored fresh (not in the frozen baseline): full body — the whole
      artifact *is* the enhancement (external-product / first-intake case).
    - In-place edit of a baselined stage: only its changed stable-id blocks.
    - Nothing in this stage changed: a short baseline-reference note (keeps the
      file present so package links never dangle) instead of the full baseline.
    """
    if scope is None or not body or stage_id is None:
        return body
    if stage_id not in scope["baseline_stage_ids"]:
        return body
    blocks = split_stable_id_blocks(body)
    if blocks:
        kept = [block.strip() for sid, block in blocks.items() if sid in scope["changed_refs"]]
        return ("\n\n".join(kept) + "\n") if kept else (_DELTA_BASELINE_NOTE + "\n")
    # No stable-id blocks (non-UI design/reference: API contracts, schemas, run-
    # books, validation notes). Then only a coarse STAGE-<id> change marks it
    # changed — ship the whole artifact in that case rather than hiding it behind
    # the baseline note; otherwise it is genuinely unchanged baseline.
    if f"STAGE-{stage_id}" in scope["changed_refs"]:
        return body
    return _DELTA_BASELINE_NOTE + "\n"


def build_package(
    root: Path, out_dir: Path, with_html: bool = False, audience: str | None = None
) -> list[Path]:
    if audience is not None and audience not in AUDIENCES:
        raise SystemExit(f"Error: --audience must be one of {', '.join(AUDIENCES)}.")

    meta = _load_live_meta(root)
    try:
        enhancement_delta = active_enhancement_delta(root)
    except EnhancementDeltaError as exc:
        raise SystemExit(f"Error: enhancement handoff refused: {exc}")
    if enhancement_delta is not None and not enhancement_delta["changes"]:
        print(
            f"Note: active enhancement {enhancement_delta['cycle_id']} has no artifact "
            "delta yet — the package will contain only the enhancement dossier. Regenerate "
            "the affected stages before handing off.",
            file=sys.stderr,
        )
    project_name = meta.get("project_name") or meta.get("project_slug", "project")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # The package projects *approved* product decisions, so stage 03 must be
    # exactly `approved` — not draft/stale/pending, and deliberately not `edited`.
    # `edited` means the PRD body drifted after approval (unreviewed changes), and
    # the traceability index (rebuilt only at approval, in post-approve.py) is then
    # stale relative to that body, so covering-test-case resolution would mix a
    # current body with a pre-edit index. Re-approve to refresh both.
    prd_status = _stage_status(meta, "03")
    if prd_status != "approved":
        raise SystemExit(
            f"Error: stage 03 (PRD) is '{prd_status or 'not present'}', not "
            "approved — the handoff package projects approved decisions only. "
            + ("It changed after approval: review it, then /pm-approve 03 --reapprove "
               "before packaging." if prd_status == "edited"
               else "Approve the PRD (/pm-approve 03) before packaging.")
        )

    prd_fm, prd_body = _read_artifact(root, "03")
    _qa_fm, qa_body = _read_artifact(root, "06")
    _brief_fm, brief_body = _read_artifact(root, "01")
    _scope_fm, scope_body = _read_artifact(root, "02")
    # Screens come from the design spec, but only when stage 04 is exactly `approved`
    # — the same rule traceability.build_index applies to it. Reading a draft/stale/
    # edited spec here would put unapproved screen names into the package (and stamp
    # them as a source) while the spine deliberately excluded them.
    design_body = None
    design_fm, raw_design_body = _read_artifact(root, "04")
    if _stage_status(meta, "04") == "approved":
        design_body = raw_design_body
    design_brief_body = None
    if _stage_status(meta, "04") == "draft" and _design_mode(design_fm, raw_design_body) == "brief":
        design_brief_body = raw_design_body
    # TRD tasks (the backend/technical work implementing each requirement) come from
    # stage 08, and only when it is exactly `approved` — same rule as the design spec.
    # A draft/stale/edited TRD contributes no tasks (the fresh spine excludes them too),
    # so a story then renders "not captured in source" for backend work.
    trd_body = None
    if _stage_status(meta, "08") == "approved":
        _trd_fm, trd_body = _read_artifact(root, "08")

    if prd_body is None:
        raise SystemExit("Error: no approved PRD (03-prd.md) found — nothing to hand off.")

    # Build the spine fresh rather than trusting .traceability.yaml on disk: stage-04
    # approval rebuilds it, but a project whose index predates screens (schema v2) or
    # was written before this release would otherwise resolve every story to zero
    # screens. Same reasoning as pm_handoff.build_plan. build_index re-derives from the
    # current artifact bodies and already excludes a non-approved design spec.
    spine = traceability.build_index(root)

    tc_blocks = split_test_case_blocks(qa_body) if qa_body else {}
    # Screens the design spec declares, so each story can name the surfaces it touches.
    # Empty for a spec written before SCR-### ids existed, or one that is not currently
    # approved (gated above) — the story template then renders "not captured in source".
    screen_blocks = (
        split_screen_blocks(information_architecture_section(design_body)) if design_body else {}
    )
    # TRD Work Breakdown tasks (TSK-###), so each story can name the backend/technical
    # work implementing it. Empty for a TRD that is absent or not currently approved
    # (gated above) — the story template then renders "not captured in source".
    task_blocks = (
        split_task_blocks(work_breakdown_section(trd_body)) if trd_body else {}
    )

    # Shared PRD delivery map: stories, requirements, journeys, and declared
    # Product Epics. This is the same decomposition `pm_handoff.py` uses.
    delivery = build_prd_delivery_map(prd_body)

    # --- prototype: read once, detect anchors once (backlog #29) ---
    proto = root / "05-prototype-mockup.html"
    has_proto = proto.exists()
    proto_bytes = proto.read_bytes() if has_proto else b""
    anchored_ids: set[str] = set()
    if has_proto:
        proto_text = proto_bytes.decode("utf-8", errors="replace")
        anchored_ids = {
            scr for scr in screen_blocks
            if re.search(rf'id=["\']{re.escape(scr)}["\']', proto_text, re.IGNORECASE)
        }

    prd_stamp = _stamp(root, "03")
    design_stamp = _stamp(root, "04")
    trd_stamp = _stamp(root, "08")
    prov = _provenance(root, meta)

    # --- compute all content ONCE in memory, keyed by output-fragment path ---
    # (render once, write into every audience folder a category belongs to —
    # this guarantees byte-identical duplicates across audiences, since `now`
    # and every rendered string are computed exactly once for the whole call.)
    stories: list[dict] = []  # {id, title, filename, content, epic, priority, requirements}
    story_index: list[dict] = []
    requirements: list[dict] = []
    requirement_index: list[dict] = []
    # Story ids that resolved to >=1 screen, captured from the same per-story
    # resolution the story files use (requirements *and* journeys). The screen map's
    # "Stories with no screen" list is derived from this set, not from each screen's
    # literal `serves` ids — otherwise a story covered only via a journey link
    # (a screen serves UJ-001, which serves US-001) would be reported uncovered in
    # the map while its own story file lists that screen.
    covered_story_ids: set[str] = set()

    scope = _enhancement_scope(enhancement_delta)
    changed_refs = (
        {item["id"] for item in enhancement_delta["changes"]}
        if enhancement_delta else set()
    )
    # The prototype (a stage-04/05 artifact) ships only when the design/prototype
    # surface is part of the delta; an unchanged baseline prototype is not handoff.
    emit_proto = has_proto and (
        scope is None or bool({"04", "05"} & scope["changed_stages"])
    )
    # When the prototype is intentionally excluded, no story or screen-map row may
    # link to it — those files are not in the audience folder. `emit_proto` is the
    # single source of truth for every prototype link below (backlog: dangling link).
    if not emit_proto:
        anchored_ids = set()
    selected_story_ids = set(delivery.story_blocks)
    if enhancement_delta:
        selected_story_ids = {
            story_id for story_id in delivery.story_blocks
            if story_id in changed_refs
            or set(delivery.story_requirements.get(story_id, [])) & changed_refs
        }

    selected_requirement_ids = set(delivery.requirement_blocks)
    if enhancement_delta:
        selected_requirement_ids = {
            req_id for req_id in delivery.requirement_blocks
            if req_id in changed_refs
        }
        for story_id in selected_story_ids:
            selected_requirement_ids.update(
                req_id for req_id in delivery.story_requirements.get(story_id, [])
                if req_id in delivery.requirement_blocks
            )

    requirement_to_stories: dict[str, list[str]] = {req_id: [] for req_id in delivery.requirement_blocks}
    for story_id, req_ids in delivery.story_requirements.items():
        for req_id in req_ids:
            if req_id == story_id or req_id not in delivery.requirement_blocks:
                continue
            requirement_to_stories.setdefault(req_id, []).append(story_id)

    for req_id, req_block in delivery.requirement_blocks.items():
        if req_id not in selected_requirement_ids:
            continue
        req_title = title_of(req_id, req_block)
        req_filename = f"{req_id}-{_slug(req_title, req_id.lower())}.md"
        owning_stories = requirement_to_stories.get(req_id, [])
        rendered_req = _render_requirement({
            "requirement_id": req_id,
            "title": req_title,
            "epic": delivery.requirement_to_epic.get(req_id) or NOT_CAPTURED,
            "priority": delivery.priorities.get(req_id) or NOT_CAPTURED,
            "owning_stories": owning_stories,
            "requirement_body": req_block.strip() or NOT_CAPTURED,
            "approval": _approval_fields(prov, ["03"]),
            "generated_from": [prd_stamp] if prd_stamp else [],
            "canonical_source": "03-prd.md",
            "generated_at": now,
        })
        requirements.append({
            "id": req_id,
            "title": req_title,
            "filename": req_filename,
            "content": rendered_req,
        })
        requirement_index.append({
            "id": req_id,
            "title": req_title,
            "filename": req_filename,
            "epic": delivery.requirement_to_epic.get(req_id),
            "priority": delivery.priorities.get(req_id),
            "owning_stories": owning_stories,
        })

    for story_id, block in delivery.story_blocks.items():
        if story_id not in selected_story_ids:
            continue
        title = _story_title(story_id, block)
        epic_ref = delivery.story_to_epic.get(story_id)
        epic_rec = delivery.epics.get(epic_ref) if epic_ref else None
        reqs = delivery.story_requirements.get(story_id, [story_id])
        journeys = delivery.story_journeys.get(story_id, [])
        story_requirement_blocks = []
        for req in [r for r in reqs if r != story_id]:
            req_block = delivery.requirement_blocks.get(req)
            story_requirement_blocks.append({
                "id": req,
                "title": title_of(req, req_block) if req_block else req,
                "body": req_block.strip() if req_block else NOT_CAPTURED,
            })
        story_acceptance_blocks = []
        for ac in delivery.story_acceptance.get(story_id, []):
            ac_block = delivery.acceptance_blocks.get(ac)
            story_acceptance_blocks.append({
                "id": ac,
                "body": body_of(ac_block, ac) if ac_block else NOT_CAPTURED,
            })

        tc_ids: list[str] = []
        for r in reqs:
            for tc in traceability.scenarios_for_requirement(root, r):
                if tc not in tc_ids:
                    tc_ids.append(tc)
        test_cases = [
            {"id": tc, "body": _strip_decl_line(tc_blocks.get(tc, ""), tc) or NOT_CAPTURED}
            for tc in tc_ids
        ]

        # Screens this story touches. Direct attribution first: screens that serve one
        # of the story's requirements (its US id + any FR/REQ). Then a journey fallback:
        # a screen that serves one of the story's journeys but names NO story/requirement
        # of its own (a journey-only screen) is attributed to every story in that journey.
        # A screen that DOES name specific stories/requirements is left to those — without
        # this, every screen in a multi-story journey was over-attributed to all its
        # stories (backlog #36), while the journey-only coverage case still resolves.
        screen_ids: list[str] = []
        for ref in reqs:
            for scr in traceability.screens_for_requirement(root, ref, index=spine):
                if scr not in screen_ids:
                    screen_ids.append(scr)
        for journey in journeys:
            for scr in traceability.screens_for_requirement(root, journey, index=spine):
                if scr in screen_ids:
                    continue
                serves = traceability.requirements_for_screen(root, scr, index=spine)
                names_specific = any(not sid.upper().startswith("UJ-") for sid in serves)
                if not names_specific:
                    screen_ids.append(scr)
        screens = [
            {
                "id": scr,
                "name": _story_title(scr, screen_blocks.get(scr, "")),
                "body": _screen_body(screen_blocks.get(scr, ""), scr) or NOT_CAPTURED,
                "link": _screen_link(scr, emit_proto, anchored_ids),
                "design_refs": _screen_design_refs(spine, scr),
            }
            for scr in screen_ids
        ]
        if screen_ids:
            covered_story_ids.add(story_id)

        # Backend/technical work: the TRD tasks implementing this story's requirements
        # (resolved over reqs only — a TSK implements a requirement, never a journey —
        # mirroring the test-case resolution). Against the fresh spine, so a
        # non-approved TRD contributes nothing.
        tsk_ids: list[str] = []
        for r in reqs:
            for tsk in traceability.tasks_for_requirement(root, r, index=spine):
                if tsk not in tsk_ids:
                    tsk_ids.append(tsk)
        tasks = [
            {
                "id": tsk,
                "name": _story_title(tsk, task_blocks.get(tsk, "")),
                "body": _strip_decl_line(task_blocks.get(tsk, ""), tsk) or NOT_CAPTURED,
            }
            for tsk in tsk_ids
        ]

        generated_from = [s for s in (prd_stamp, _stamp(root, "06")) if s]
        source_ids = ["03", "06"]
        if screens and design_stamp:
            generated_from.append(design_stamp)
            source_ids.append("04")
        if tasks and trd_stamp:
            generated_from.append(trd_stamp)
            source_ids.append("08")
        rendered = _render_story({
            "story_id": story_id,
            "title": title,
            "epic": epic_ref or NOT_CAPTURED,
            "epic_title": epic_rec.title if epic_rec else NOT_CAPTURED,
            "epic_context": epic_rec.body.strip() if epic_rec else "",
            "priority": delivery.priorities.get(story_id) or NOT_CAPTURED,
            "story_body": _strip_decl_line(block, story_id) or NOT_CAPTURED,
            "requirements": [r for r in reqs if r != story_id],
            "requirement_blocks": story_requirement_blocks,
            "acceptance_blocks": story_acceptance_blocks,
            "impact_analysis": (_section_of(prd_body, "impact analysis").strip() or NOT_CAPTURED),
            "nfrs": (_section_of(prd_body, "non-functional requirements").strip() or NOT_CAPTURED),
            "journeys": journeys,
            "test_cases": test_cases,
            "test_case_ids": tc_ids,
            "screens": screens,
            "screen_ids": screen_ids,
            "tasks": tasks,
            "task_ids": tsk_ids,
            "approval": _approval_fields(prov, source_ids),
            "generated_from": generated_from,
            "canonical_source": "03-prd.md",
            "generated_at": now,
        })
        filename = f"{story_id}-{_slug(title, story_id.lower())}.md"
        stories.append({"id": story_id, "title": title, "filename": filename, "content": rendered})
        story_index.append({
            "id": story_id,
            "title": title,
            "filename": filename,
            "epic": epic_ref,
            "priority": delivery.priorities.get(story_id),
            "requirements": [r for r in reqs if r != story_id],
        })

    # --- overview (Business Perspective from brief + scope) ---
    who = _first_para(_section_of(brief_body, "target user") or _section_of(brief_body, "audience"))
    what_why = _first_para(
        _section_of(brief_body, "overview")
        or _section_of(brief_body, "problem")
        or brief_body
    )
    how = _first_para(
        _section_of(scope_body, "mvp boundary")
        or _section_of(scope_body, "in scope")
        or scope_body
    )
    overview_body = (
        f"## Who\n\n{who or NOT_CAPTURED}\n\n"
        f"## What & Why\n\n{what_why or NOT_CAPTURED}\n\n"
        f"## How\n\n{how or NOT_CAPTURED}\n"
    )
    # The overview is drawn from the brief (01) + scope (02); under an enhancement
    # it ships only if either of those stages is part of the delta.
    if scope is not None and not ({"01", "02"} & scope["changed_stages"]):
        overview_body = _DELTA_BASELINE_NOTE + "\n"
    overview_stamps = [s for s in (_stamp(root, "01"), _stamp(root, "02")) if s]
    overview_content = _stamped_doc(
        f"{project_name} — Handoff Overview",
        overview_stamps,
        now,
        overview_body,
        approval=_approval_fields(prov, ["01", "02"]),
        tracked=overview_stamps,
    )

    # --- epic indexes (one file per Product Epic declared in the PRD) ---
    epics: list[dict] = []  # {id, title, filename, content}
    epic_index: list[dict] = []
    selected_epics = {story.get("epic") for story in story_index if story.get("epic")}
    selected_epics.update(
        epic_ref for req_id, epic_ref in delivery.requirement_to_epic.items()
        if req_id in changed_refs and epic_ref
    )
    for epic_ref, epic_rec in delivery.epics.items():
        if enhancement_delta and epic_ref not in selected_epics:
            continue
        header = [
            "## Outcome and scope",
            "",
            epic_rec.body.strip() or NOT_CAPTURED,
            "",
            "## Stories in this epic",
            "",
        ]
        epic_stories = [story for story in story_index if story.get("epic") == epic_ref]
        # Two story-list variants: a linked one for audiences that carry the story
        # files (dev/qa), and a plain-text one for audiences that don't (business) —
        # otherwise the ../stories/ links dangle where no stories/ folder exists
        # (backlog #34).
        linked_story_lines: list[str] = []
        plain_story_lines: list[str] = []
        if epic_stories:
            for story in epic_stories:
                linked_story_lines.append(
                    f"- **{story['id']}** [{story['title']}](../stories/{story['filename']})"
                )
                plain_story_lines.append(f"- **{story['id']}** {story['title']}")
        else:
            linked_story_lines.append(NOT_CAPTURED)
            plain_story_lines.append(NOT_CAPTURED)
        footer = [
            "",
            "## Functional requirements in this epic",
            "",
        ]
        epic_requirements = [
            req_id for req_id, req_epic in delivery.requirement_to_epic.items()
            if req_epic == epic_ref
        ]
        linked_req_lines: list[str] = []
        plain_req_lines: list[str] = []
        if epic_requirements:
            req_lookup = {req["id"]: req for req in requirement_index}
            for req in epic_requirements:
                req_rec = req_lookup.get(req)
                if req_rec:
                    linked_req_lines.append(
                        f"- **{req}** [{req_rec['title']}](../requirements/{req_rec['filename']})"
                    )
                    plain_req_lines.append(f"- **{req}** {req_rec['title']}")
                else:
                    linked_req_lines.append(f"- **{req}**")
                    plain_req_lines.append(f"- **{req}**")
        else:
            linked_req_lines.append(NOT_CAPTURED)
            plain_req_lines.append(NOT_CAPTURED)

        def _epic_doc(story_lines: list[str], req_lines: list[str]) -> str:
            return _stamped_doc(
                f"{epic_ref} · {epic_rec.title}",
                [prd_stamp] if prd_stamp else [],
                now,
                "\n".join(header + story_lines + footer + req_lines) + "\n",
                approval=_approval_fields(prov, ["03"]),
                tracked=[prd_stamp] if prd_stamp else [],
            )

        filename = f"{epic_ref}-{_slug(epic_rec.title, epic_ref.lower())}.md"
        epics.append({
            "id": epic_ref,
            "title": epic_rec.title,
            "filename": filename,
            "content": _epic_doc(linked_story_lines, linked_req_lines),
            "content_plain": _epic_doc(plain_story_lines, plain_req_lines),
        })
        epic_index.append({"id": epic_ref, "title": epic_rec.title, "filename": filename})

    # --- reference docs ---
    reference_docs: dict[str, tuple[str, str]] = {}  # category -> (filename, content)
    plain_references = {
        "prioritization": ("prioritization.md", "Prioritization Method", _section_of(prd_body, "prioritization method"), prd_stamp),
        "user_journeys": ("user-journeys.md", "User Journeys", _section_of(prd_body, "user journeys"), prd_stamp),
        "impact_analysis": ("impact-analysis.md", "Impact Analysis", _section_of(prd_body, "impact analysis"), prd_stamp),
        "nfrs": ("nfrs.md", "Non-Functional Requirements", _section_of(prd_body, "non-functional requirements"), prd_stamp),
        "qa_scenarios": (
            "qa-scenarios.md", "QA Scenarios",
            _section_of(qa_body, "functional test cases") or (qa_body or ""),
            _stamp(root, "06"),
        ),
    }
    for category, (filename, heading, content, stamp) in plain_references.items():
        content = _delta_body(content, _REF_STAGE.get(category), scope)
        doc = _stamped_doc(
            heading, [stamp] if stamp else [], now, ((content or "").strip() or NOT_CAPTURED) + "\n",
            approval=_approval_fields(prov, [_REF_STAGE[category]]),
            tracked=[stamp] if stamp else [],
        )
        reference_docs[category] = (filename, doc)

    # Full read-only artifact projections (PMOS-002). Always emitted so their
    # README/HTML links never dangle; a not-yet-approved optional source projects an
    # explicit note instead of a body. Stamped with the source hash like every other
    # projection, so a dev/design reviewer can trace it back to the approved artifact.
    prd_projection = _delta_body(prd_body, "03", scope)
    reference_docs["prd_full"] = ("prd.md", _stamped_doc(
        "Product Requirements (PRD)", [prd_stamp] if prd_stamp else [], now,
        ((prd_projection or "").strip() or NOT_CAPTURED) + "\n",
        approval=_approval_fields(prov, ["03"]), tracked=[prd_stamp] if prd_stamp else []))
    trd_projection = (_delta_body(trd_body, "08", scope) or "").strip() if trd_body else (
        NOT_CAPTURED + "\n\n_Stage 08 (TRD) is not approved for this project, so no "
        "technical requirements are projected here. Approve the TRD (/pm-approve 08) and "
        "regenerate to include it._")
    reference_docs["trd_full"] = ("trd.md", _stamped_doc(
        "Technical Requirements (TRD)", [trd_stamp] if trd_stamp else [], now,
        trd_projection + "\n",
        approval=_approval_fields(prov, ["08"]),
        tracked=[trd_stamp] if trd_stamp and trd_body else []))
    design_projection = (_delta_body(design_body, "04", scope) or "").strip() if design_body else (
        NOT_CAPTURED + "\n\n_Stage 04 (design spec) is not approved, so no design spec is "
        "projected here. Approve the design spec (/pm-approve 04) and regenerate to include it._")
    reference_docs["design_spec_full"] = ("design-spec.md", _stamped_doc(
        "Design Spec", [design_stamp] if design_stamp else [], now,
        design_projection + "\n",
        approval=_approval_fields(prov, ["04"]),
        tracked=[design_stamp] if design_stamp and design_body else []))
    if design_brief_body:
        reference_docs["design_brief"] = ("design-brief.md", _stamped_doc(
            "Draft Design Brief",
            [design_stamp] if design_stamp else [],
            now,
            "> This is an unapproved design brief for external design work, not a canonical design spec.\n\n"
            + design_brief_body.strip()
            + "\n",
            # Deliberately a draft: recorded under `sources`, never tracked as a
            # source the release check would require to be approved.
            approval=_approval_fields(prov, ["04"]),
            tracked=[],
        ))

    # --- screen map (the reverse view: screen → the stories it serves) ---
    # An unchanged, baselined design spec contributes no delta, so its screen map
    # is baseline reference rather than handoff.
    if scope is not None and "04" in scope["baseline_stage_ids"] and "04" not in scope["changed_stages"]:
        screen_map_table = _DELTA_BASELINE_NOTE + "\n"
    else:
        screen_map_table = _screen_map_table(
            root, spine, screen_blocks, story_index, covered_story_ids, emit_proto, anchored_ids)
    screen_map_content = _stamped_doc(
        "Screen Map", [design_stamp] if design_stamp else [], now, screen_map_table,
        approval=_approval_fields(prov, ["04"]),
        tracked=[design_stamp] if design_stamp and design_body else [])
    reference_docs["screen_map"] = ("screen-map.md", screen_map_content)

    # --- resolve which audiences to (re)build ---
    audiences_to_build = [audience] if audience else list(AUDIENCES)

    handoff_root = _resolve_handoff_root(out_dir, root)

    # Prepare (validate + wipe + recreate) every requested audience folder
    # before writing any content into any of them, so a marker conflict on
    # one requested audience doesn't leave the others half-rebuilt with new
    # directories but stale/missing content.
    audience_dirs: dict[str, Path] = {}
    for aud in audiences_to_build:
        audience_dirs[aud] = _prepare_audience_dir(handoff_root, aud)

    written: list[Path] = []
    for aud in audiences_to_build:
        aud_dir = audience_dirs[aud]
        cats = _categories_for_audience(aud)
        if aud == "design" and not design_brief_body:
            cats.discard("design_brief")
            cats.discard("designer_workflow")
        (aud_dir / HANDOFF_MARKER).write_text(
            "PM-OS handoff package — generated by /pm-handoff --package. "
            "A rebuild replaces only the files listed in manifest.json; files you add here are kept.\n",
            encoding="utf-8",
        )

        if "stories" in cats:
            (aud_dir / "stories").mkdir(parents=True, exist_ok=True)
            for story in stories:
                path = aud_dir / "stories" / story["filename"]
                path.write_text(story["content"], encoding="utf-8")
                written.append(path)

        if "requirements" in cats:
            (aud_dir / "requirements").mkdir(parents=True, exist_ok=True)
            for requirement in requirements:
                path = aud_dir / "requirements" / requirement["filename"]
                path.write_text(requirement["content"], encoding="utf-8")
                written.append(path)

        if "epics" in cats:
            (aud_dir / "epics").mkdir(parents=True, exist_ok=True)
            # Link into ../stories/ only when this audience actually carries the
            # story files; otherwise use the plain-text variant (backlog #34).
            epic_key = "content" if "stories" in cats else "content_plain"
            for epic in epics:
                path = aud_dir / "epics" / epic["filename"]
                path.write_text(epic[epic_key], encoding="utf-8")
                written.append(path)

        if "overview" in cats:
            path = aud_dir / "00-overview.md"
            path.write_text(overview_content, encoding="utf-8")
            written.append(path)

        if "designer_workflow" in cats:
            path = aud_dir / "DESIGNER-WORKFLOW.md"
            path.write_text(_designer_workflow_doc(project_name, now), encoding="utf-8")
            written.append(path)

        reference_cats = [c for c in reference_docs if c in cats]
        if reference_cats:
            (aud_dir / "reference").mkdir(parents=True, exist_ok=True)
            for cat in reference_cats:
                filename, content = reference_docs[cat]
                path = aud_dir / "reference" / filename
                path.write_text(content, encoding="utf-8")
                written.append(path)

        readiness_src = root / readiness.READINESS_FILE
        if "readiness" in cats and readiness_src.is_file():
            path = aud_dir / readiness.READINESS_FILE
            path.write_bytes(readiness_src.read_bytes())
            written.append(path)

        if "wireframes" in cats and emit_proto:
            (aud_dir / "wireframes").mkdir(parents=True, exist_ok=True)
            path = aud_dir / "wireframes" / "prototype.html"
            path.write_bytes(proto_bytes)
            written.append(path)

        readme = _audience_readme(
            project_name, now, story_index, epic_index, requirement_index, generated_sources(root),
            emit_proto and "wireframes" in cats, aud, cats,
            provenance=[prov[sid] for sid in ("01", "02", "03", "04", "05", "06", "08") if sid in prov],
            has_readiness="readiness" in cats and (root / readiness.READINESS_FILE).is_file(),
        )
        if enhancement_delta:
            boundary = enhancement_delta["boundary"]
            change_lines = [
                f"- {item['id']}: {item['change_type']}"
                for item in enhancement_delta["changes"]
            ] or ["- No artifact delta detected"]
            dossier = (
                f"\n## Enhancement {enhancement_delta['cycle_id']} delta\n\n"
                + "\n".join(change_lines)
                + "\n\nAffected surfaces: "
                + ", ".join(boundary.get("affected_surfaces") or [])
                + "\n\nMust not break: "
                + "; ".join(boundary.get("regression_invariants") or [])
                + "\n\nCompatibility/migration: "
                + "; ".join(boundary.get("compatibility_migration") or [])
                + "\n\nRollout: " + "; ".join(boundary.get("rollout") or [])
                + "\n\nRollback: " + "; ".join(boundary.get("rollback") or [])
                + "\n"
            )
            readme += dossier
        (aud_dir / "README.md").write_text(readme, encoding="utf-8")
        written.append(aud_dir / "README.md")

        if with_html:
            html_path = _write_html_index(aud_dir, project_name, now, story_index, epic_index, cats)
            if html_path:
                written.append(html_path)

    # --- top-level hub README: always rewritten, holds no unique content ---
    hub_path = _write_hub_readme(handoff_root, project_name, now)
    written.append(hub_path)

    return written


def _screen_map_table(
    root: Path, spine: dict, screen_blocks: dict, story_index, covered_story_ids: set[str],
    has_proto: bool, anchored_ids: set[str],
) -> str:
    """The reverse of the per-story Screens section: one row per screen, listing the
    ids it serves plus a link into the prototype, and the stories no screen covers.

    Each row's `Serves` shows what the screen literally declares (requirement *or*
    journey ids). The "Stories with no screen" list, however, is taken from
    ``covered_story_ids`` — the set of stories that actually resolved to a screen in
    the per-story pass (over requirements *and* journeys) — so the map and the story
    files can never disagree. Using each screen's literal `serves` ids here instead
    would wrongly flag a story that is covered only through a journey link."""
    if not screen_blocks:
        return (
            f"{NOT_CAPTURED}\n\n"
            "The approved design spec declares no `SCR-###` screens in its Information "
            "Architecture, so screens cannot be mapped to stories. Add screen ids with a "
            "`Serves:` line to `04-design-spec.md`, re-approve it, and regenerate.\n"
        )

    lines = ["| Screen | Name | Serves | Figma | Prototype |", "|---|---|---|---|---|"]
    for scr_id, block in screen_blocks.items():
        served = traceability.requirements_for_screen(root, scr_id, index=spine)
        name = _story_title(scr_id, block)
        refs = _screen_design_refs(spine, scr_id)
        default = next((ref for ref in refs if ref.get("kind") == "screen"), None)
        figma_cell = f"[Open]({default['url']})" if default and default.get("url") else NOT_CAPTURED
        link = _screen_link(scr_id, has_proto, anchored_ids)
        link_cell = f"[Open]({link})" if link else NOT_CAPTURED
        lines.append(f"| {scr_id} | {name} | {', '.join(served) if served else NOT_CAPTURED} | {figma_cell} | {link_cell} |")

    uncovered = [
        f"{story['id']} · {story['title']}"
        for story in story_index
        if story["id"] not in covered_story_ids
    ]
    if uncovered:
        lines += [
            "",
            "## Stories with no screen",
            "",
            "No screen in the approved design spec declares it serves these — either the "
            "story is not yet designed, or a screen is missing its `Serves:` trace:",
            "",
        ]
        lines += [f"- {entry}" for entry in uncovered]
    return "\n".join(lines) + "\n"


def _first_para(text: str) -> str:
    """First non-empty paragraph of a section body, lightly trimmed."""
    if not text:
        return ""
    para: list[str] = []
    for line in text.strip().splitlines():
        if line.strip():
            para.append(line.strip())
        elif para:
            break
    return " ".join(para).strip()


def _stamped_doc(heading: str, sources: list[str], when: str, body: str,
                 approval: dict | None = None, tracked: list[str] | None = None) -> str:
    """A generated reference doc. With ``approval`` (backlog #71) it starts with
    frontmatter carrying the source's approval record; ``tracked`` lists the
    `artifact@hash` stamps whose content the doc actually projects, which the
    release check compares against the current artifacts. A source shown only
    as a note (an unapproved TRD) or deliberately unapproved (a draft design
    brief) is listed under `sources` but not tracked."""
    src = ", ".join(sources) if sources else "the approved pipeline"
    head = ""
    if approval is not None:
        fields = {**approval, "generated_from": list(tracked or []), "generated_at": when}
        head = "---\n" + yaml.safe_dump(fields, default_flow_style=False, sort_keys=False,
                                        allow_unicode=True) + "---\n\n"
    return head + (
        f"<!-- GENERATED — DO NOT EDIT HERE. Read-only projection of {src}. "
        f"Edit the canonical artifact and regenerate with `/pm-handoff --package`. -->\n\n"
        f"# {heading}\n\n"
        f"> Generated from {src} on {when}. Do not edit here — edit the source and regenerate.\n\n"
        f"{body}"
    )


def generated_sources(root: Path) -> list[str]:
    return [s for s in (_stamp(root, sid) for sid in ("01", "02", "03", "04", "05", "06", "08")) if s]


def _audience_readme(
    project_name: str, when: str, story_index, epic_index, requirement_index, sources, has_proto: bool,
    audience: str, cats: set[str], provenance: list[dict] | None = None,
    has_readiness: bool = False,
) -> str:
    """A reading guide scoped to exactly the files present in this audience folder."""
    lines = [
        f"# {project_name} — Handoff Package ({audience})",
        "",
        f"> Generated {when} from: {', '.join(sources) if sources else 'the approved pipeline'}.",
        "> **This package is read-only.** It is a projection of the approved PM-OS",
        "> artifacts. To change anything, edit the canonical stage artifact and re-run",
        "> `/pm-handoff --package` — do not edit files here.",
        "> This folder is one of four audience views (dev/design/qa/business); see",
        "> `../README.md` for the others.",
        "",
        "## Start here",
    ]
    if "overview" in cats:
        lines.append("- [Overview](00-overview.md) — who / what & why / how (for stakeholders)")
    if "epics" in cats and epic_index:
        for epic in epic_index:
            lines.append(f"- [{epic['id']} · {epic['title']}](epics/{epic['filename']}) — Jira epic and story index")
    elif "epics" in cats:
        lines.append("- Product epics: not captured in source")
    if "stories" in cats:
        lines += ["", "## User stories"]
        for story in story_index:
            lines.append(f"- [{story['id']} · {story['title']}](stories/{story['filename']})")
    if "requirements" in cats:
        lines += ["", "## Functional requirements"]
        if requirement_index:
            for req in requirement_index:
                lines.append(f"- [{req['id']} · {req['title']}](requirements/{req['filename']})")
        else:
            lines.append("- Functional requirements: not captured in source")
    reference_lines = {
        "prd_full": "- [Product requirements (PRD)](reference/prd.md) — the full approved PRD",
        "trd_full": "- [Technical requirements (TRD)](reference/trd.md) — architecture & backend work breakdown",
        "design_spec_full": "- [Design spec](reference/design-spec.md) — the full approved design spec",
        "design_brief": "- [Draft design brief](reference/design-brief.md) — unapproved work order for external design",
        "prioritization": "- [Prioritization method](reference/prioritization.md)",
        "user_journeys": "- [User journeys](reference/user-journeys.md)",
        "screen_map": "- [Screen map](reference/screen-map.md) — which screens serve which stories, with prototype links",
        "qa_scenarios": "- [QA scenarios](reference/qa-scenarios.md)",
        "impact_analysis": "- [Impact analysis](reference/impact-analysis.md)",
        "nfrs": "- [Non-functional requirements](reference/nfrs.md)",
    }
    present_reference = [line for cat, line in reference_lines.items() if cat in cats]
    if present_reference:
        lines += ["", "## Reference"] + present_reference
    if "designer_workflow" in cats:
        lines += ["", "## Designer workflow", "- [Designer workflow](DESIGNER-WORKFLOW.md)"]
    if has_readiness:
        lines += ["", "## Still owed", "- [Readiness record](readiness.yaml) — eval sets, test inputs "
                  "and open decisions the build team is waiting on, with owners and due milestones"]
    if has_proto:
        lines += ["", "## Design", "- [Prototype](wireframes/prototype.html)"]
    if provenance:
        lines += _sources_table(provenance)
    lines.append("")
    return "\n".join(lines)


def _sources_table(provenance: list[dict]) -> list[str]:
    """Which approved revision of each source artifact this package was built
    from (backlog #71), so a reader never has to recompute a hash to know."""
    lines = [
        "",
        "## Sources",
        "",
        "| Artifact | Status | Version | Approved by | Approved at | Content hash |",
        "|---|---|---|---|---|---|",
    ]
    for rec in provenance:
        version = f"v{rec['version']}" if rec.get("version") else "—"
        digest = (rec.get("content_hash") or "")[:12] or "—"
        lines.append(
            f"| {rec['artifact']} | {rec.get('status') or '—'} | {version} | "
            f"{rec.get('approved_by') or '—'} | {rec.get('approved_at') or '—'} | {digest} |"
        )
    return lines


def _designer_workflow_doc(project_name: str, when: str) -> str:
    return (
        f"# {project_name} - Designer Workflow\n\n"
        f"> Generated {when}. This is the supported external-design workflow for a "
        "stage-04 design brief package.\n\n"
        "## Inputs\n\n"
        "- Read `reference/prd.md` for the approved product requirements.\n"
        "- Read `stories/` for per-story behavior, acceptance, and traceability.\n"
        "- Read `reference/nfrs.md` and `reference/user-journeys.md` before deriving screens.\n"
        "- Read `reference/design-brief.md` as the PM-owned work order. It is a draft, not an approved design spec.\n\n"
        "## Phase 1 - Inventory the design system\n\n"
        "Inspect the available Figma libraries, variables, components, and patterns. Do not create, move, rename, or delete frames during this phase.\n\n"
        "## Phase 2 - Derive the work order and pause\n\n"
        "Create a screen/state/field/component work-order table from the PRD stories, NFRs, journeys, and draft design brief. Stop and get designer approval before building anything.\n\n"
        "## Phase 3 - Agree the file convention and pause\n\n"
        "Agree the Figma page and frame naming convention, including `<Screen> / <state>` naming for state frames. Stop until the designer approves the convention.\n\n"
        "## Phase 4 - Build the scaffold\n\n"
        "Build a coverage-complete scaffold using approved design-system assets and approved vocabulary. The scaffold proves every required screen, state, field, and component location exists; it is not the finished design.\n\n"
        "## Phase 5 - Designer finishes the design\n\n"
        "The designer owns layout, hierarchy, density, emphasis, component fit, and defensible visual decisions. Do not treat the scaffold as final without designer review.\n\n"
        "## Phase 6 - Read-only export\n\n"
        "Run a separate export pass after the design is finished. That pass is read-only: it must not edit, move, rename, or create Figma objects. It writes both files under `design-in/`:\n\n"
        "- `design-in/ia.yaml`\n"
        "- `design-in/design-notes.md`\n\n"
        "Self-check before handoff: every PRD journey has a flow, every UI story has a screen or screenless rationale, every required state has a frame, every required field appears on a serving screen, every new component has a rationale, and `tokens.outside_system` is empty or justified.\n"
    )


def _write_hub_readme(handoff_root: Path, project_name: str, when: str) -> Path:
    """A small, always-rewritten top-level index (not marker-gated — it holds no
    unique content of its own). Lists whichever audience folders currently exist
    on disk — a plain `.exists()` check, not "built this run" — so a hub written
    after a single-audience `--audience dev` run still correctly links to
    `design/`/`qa/`/`business/` if those were populated by an earlier run and
    never removed."""
    lines = [
        f"# {project_name} — Handoff",
        "",
        f"> Generated {when}. Each subfolder below is a self-contained audience view;",
        "> regenerate one with `/pm-handoff --package --audience <name>`, or all four",
        "> with `/pm-handoff --package`.",
        "",
    ]
    present = [aud for aud in AUDIENCES if (handoff_root / aud).exists()]
    if present:
        for aud in present:
            lines.append(f"- [{aud}/]({aud}/README.md)")
    else:
        lines.append("- No audience folder has been built yet — run `/pm-handoff --package`.")
    jira_plan = handoff_root / "jira-plan.md"
    jira_csv = handoff_root / "jira-import.csv"
    if jira_plan.exists() or jira_csv.exists():
        lines += [
            "",
            "## Jira export artifacts",
            "These live at the `handoff/` root, separate from any audience folder:",
        ]
        if jira_plan.exists():
            lines.append("- [jira-plan.md](jira-plan.md)")
        if jira_csv.exists():
            lines.append("- [jira-import.csv](jira-import.csv)")
    lines.append("")
    path = handoff_root / "README.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _write_html_index(
    out_dir: Path, project_name: str, when: str, story_index, epic_index, cats: set[str]
) -> Path | None:
    """A minimal, self-contained HTML index for one audience folder. Reuses
    html_render's safe Markdown converter for the story links; no external assets."""
    try:
        sys.path.insert(0, os.environ.get("PM_OS_LIB_PATH") or str(Path.home() / ".pm-os" / "lib"))
        from html_render import _markdownish  # noqa: F401  (imported for parity with prior behavior)
    except Exception:
        return None
    items = "\n".join(
        f'<li><a href="stories/{story["filename"]}">{story["id"]} · {story["title"]}</a></li>'
        for story in story_index
    ) if "stories" in cats else ""
    epic_items = ""
    if "epics" in cats:
        epic_items = "\n".join(
            f'<li><a href="epics/{epic["filename"]}">{epic["id"]} · {epic["title"]}</a></li>'
            for epic in epic_index
        ) or "<li>Product epics not captured in source</li>"
    body_parts = [f"<h1>{project_name} — Handoff Package</h1>",
                  f"<p>Generated {when}. Read-only projection of the approved pipeline.</p>"]
    top_links = []
    if "overview" in cats:
        top_links.append('<li><a href="00-overview.md">Overview</a></li>')
    if epic_items:
        body_parts.append(f"<ul>{''.join(top_links)}{epic_items}</ul>")
    elif top_links:
        body_parts.append(f"<ul>{''.join(top_links)}</ul>")
    if "stories" in cats:
        body_parts.append(f"<h2>User stories</h2><ul>{items}</ul>")
    reference_links = {
        "prd_full": '<li><a href="reference/prd.md">Product requirements (PRD)</a></li>',
        "trd_full": '<li><a href="reference/trd.md">Technical requirements (TRD)</a></li>',
        "design_spec_full": '<li><a href="reference/design-spec.md">Design spec</a></li>',
        "prioritization": '<li><a href="reference/prioritization.md">Prioritization method</a></li>',
        "user_journeys": '<li><a href="reference/user-journeys.md">User journeys</a></li>',
        "screen_map": '<li><a href="reference/screen-map.md">Screen map</a></li>',
        "qa_scenarios": '<li><a href="reference/qa-scenarios.md">QA scenarios</a></li>',
        "impact_analysis": '<li><a href="reference/impact-analysis.md">Impact analysis</a></li>',
        "nfrs": '<li><a href="reference/nfrs.md">NFRs</a></li>',
    }
    present_reference = "".join(link for cat, link in reference_links.items() if cat in cats)
    if present_reference:
        body_parts.append(f"<h2>Reference</h2><ul>{present_reference}</ul>")
    body = "".join(body_parts)
    html_doc = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{project_name} — Handoff</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:52rem;margin:2rem auto;padding:0 1rem;line-height:1.5}</style>"
        f"</head><body>{body}</body></html>"
    )
    path = out_dir / "index.html"
    path.write_text(html_doc, encoding="utf-8")
    return path


# --- secret gate ------------------------------------------------------------------

# Stage artifacts the package reads (see build_package): brief, scope, PRD, design
# spec/brief, QA plan, TRD — plus the stage-05 prototype copied into wireframes/.
# Scanned whenever present, whatever their status: a secret sitting in a draft the
# package might pick up is still worth stopping on.
PACKAGE_SOURCE_STAGES = ("01", "02", "03", "04", "06", "08")
PROTOTYPE_FILENAME = "05-prototype-mockup.html"


def package_source_paths(root: Path) -> list[Path]:
    paths = [artifact_path(root, sid) for sid in PACKAGE_SOURCE_STAGES]
    paths.append(root / PROTOTYPE_FILENAME)
    paths.append(root / readiness.READINESS_FILE)  # copied into every audience folder
    return [p for p in paths if p.exists()]


# --- raw mode (original pm-share behavior, plus the secret gate) -----------------

def _raw_export(root: Path, stage_id: str | None, output: str | None,
                allow_secrets: bool = False, include_unapproved: bool = False) -> None:
    """Plain-text export. Only `approved` stages go out: an `edited` stage's body
    changed after approval, and a draft was never approved (backlog #71). The PM
    can include them with --include-unapproved, and the output then says so on
    each such stage."""
    meta = _load_live_meta(root)
    statuses = {s["id"]: s.get("status") for s in meta["stages"]}

    if stage_id:
        stage_id = stage_id.zfill(2)
        if stage_id not in STAGE_NAMES:
            print(f"Error: unknown stage '{stage_id}'")
            sys.exit(1)
        status = statuses.get(stage_id)
        if status != "approved" and not include_unapproved:
            fix = (f"It changed after approval: review it, then /pm-approve {stage_id} --reapprove"
                   if status == "edited" else f"Approve it first (/pm-approve {stage_id})")
            print(f"Error: stage {stage_id} is '{status or 'not present'}', not approved, so it "
                  f"is not exported. {fix}, or re-run with --include-unapproved to export it "
                  "marked as unapproved.")
            sys.exit(1)
        stages_to_share = [stage_id]
    else:
        wanted = ("approved", "edited", "draft", "stale") if include_unapproved else ("approved",)
        stages_to_share = [s["id"] for s in meta["stages"] if s["status"] in wanted]
        skipped = [f"{s['id']} ({s['status']})" for s in meta["stages"]
                   if s["status"] in ("edited", "draft", "stale") and s["id"] not in stages_to_share]
        if skipped:
            print(f"Note: not exported because not approved: {', '.join(skipped)}. "
                  "Approve them, or re-run with --include-unapproved.", file=sys.stderr)

    if not stages_to_share:
        print("No approved stages to share.")
        sys.exit(0)

    # Gate before printing/writing anything: raw mode echoes bodies verbatim.
    secret_scan.guard_export(
        root, [p for p in (artifact_path(root, sid) for sid in stages_to_share) if p.exists()],
        allow=allow_secrets, export="handoff_raw")

    lines = [f"# {meta['project_name']}", f"Project: {meta['project_slug']} | PM-OS {meta['pm_os_version']}", ""]

    for sid in stages_to_share:
        apath = artifact_path(root, sid)
        if not apath.exists():
            continue
        fm, body = fm_read(str(apath))
        stage = next((s for s in meta["stages"] if s["id"] == sid), {})
        status = stage.get("status") or fm.get("status", "?")
        h = stage.get("content_hash") or fm.get("content_hash")
        hash_short = h[:12] if h else "N/A"
        version = f"v{stage['version']}" if stage.get("version") else "none"
        header = (f"Status: {status} | Version: {version} | Approved by: "
                  f"{fm.get('approved_by') or 'n/a'} | Approved at: {stage.get('approved_at') or 'n/a'} "
                  f"| Hash: {hash_short}")
        lines += [
            "---",
            f"## Stage {sid}: {STAGE_NAMES[sid].replace('-', ' ').title()}",
            header,
        ]
        if status != "approved":
            lines.append(f"**NOT APPROVED ({status}): exported with --include-unapproved. "
                         "Do not treat this stage as a decision.**")
        lines += ["", body.strip(), ""]

    text = "\n".join(lines)

    if output:
        Path(output).write_text(text, encoding="utf-8")
        print(f"Exported to {output}")
    else:
        print(text)


# --- package publish (staged build -> release check -> publish) -----------------

def _add_release_files(root: Path, staged_root: Path, audiences: list[str], meta: dict,
                       release_note: str | None) -> dict:
    """Write CHANGES.md and manifest.json into each staged audience folder
    (backlog #73, #75) and return the snapshot a release record is made from.

    The change note compares the approved sources' stable ids and the outside
    inputs with the last recorded release. Plain rebuilds are drafts: they get
    a note but no release id.
    """
    project_name = meta.get("project_name") or meta.get("project_slug", "project")
    prov = _provenance(root, meta)
    stable_ids = release_record.stable_id_hashes(root, prov)
    inputs = release_record.outside_inputs(root)
    previous = release_record.latest(root)
    delta = release_record.diff(previous, stable_ids, inputs)
    stories = (release_record.affected_stories(root, [c["id"] for c in delta["ids"]])
               if previous else {})
    release_id = release_record.next_id(root) if release_note else None
    generated_at = release_record.now_iso()
    changes = release_record.render_changes(
        project_name=project_name, delta=delta, stories=stories, note=release_note,
        release_id=release_id, generated_at=generated_at)
    manifests: dict[str, dict] = {}
    for aud in audiences:
        aud_dir = staged_root / aud
        (aud_dir / release_record.CHANGES_FILE).write_text(changes, encoding="utf-8")
        readme = aud_dir / "README.md"
        if readme.is_file():
            text = readme.read_text(encoding="utf-8")
            link = ("- [What changed](CHANGES.md): ids added, removed or changed since the last "
                    "release, and the stories they affect. Files, roles and hashes: "
                    "[manifest.json](manifest.json)")
            text = text.replace("## Start here\n", f"## Start here\n{link}\n", 1)
            readme.write_text(text, encoding="utf-8")
        manifest = release_record.build_manifest(project_name, aud, aud_dir, release_id, generated_at)
        (aud_dir / release_record.MANIFEST_FILE).write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        manifests[aud] = manifest
    return {
        "release_id": release_id, "generated_at": generated_at, "provenance": prov,
        "stable_ids": stable_ids, "inputs": inputs, "delta": delta, "stories": stories,
        "manifests": manifests,
    }


def _record_release(root: Path, snapshot: dict, note: str, audiences: list[str],
                    overridden: list[str]) -> Path:
    """Write `.releases/REL-###.yaml` and log `handoff_released` (backlog #73)."""
    try:
        from config import load_config
        released_by = load_config().get("pm_user")
    except Exception:
        released_by = None
    delta = snapshot["delta"]
    record = {
        "id": snapshot["release_id"],
        "released_at": snapshot["generated_at"],
        "released_by": released_by,
        "note": note,
        "previous": delta.get("previous"),
        "audiences": audiences,
        "release_check_overridden": overridden,
        "sources": {sid: {k: rec.get(k) for k in ("artifact",) + APPROVAL_KEYS}
                    for sid, rec in sorted(snapshot["provenance"].items())},
        "stable_ids": snapshot["stable_ids"],
        "outside_inputs": snapshot["inputs"],
        "changes": delta["ids"],
        "files": {aud: [{"path": f["path"], "sha256": f["sha256"]} for f in m["files"]]
                  for aud, m in snapshot["manifests"].items()},
    }
    path = release_record.write_record(root, record)
    try:
        from telemetry import log
        log("handoff_released", root, None, {
            "release": record["id"], "previous": record["previous"], "audiences": audiences,
            "ids_changed": len(delta["ids"]), "stories_affected": len(snapshot["stories"]),
            "inputs_changed": len(delta["inputs"]), "release_check_overridden": overridden,
        })
    except Exception as e:  # telemetry must never break the workflow
        print(f"Warning: telemetry logging failed: {e}", file=sys.stderr)
    return path


def publish_package(root: Path, out_dir: Path, *, with_html: bool = False,
                    audience: str | None = None, allow_release_errors: bool = False,
                    release_note: str | None = None) -> list[Path]:
    """Build the package into a temporary folder, run the release check on each
    audience folder as it would ship, and only then replace `handoff/<audience>/`.

    Every refusal that can stop the export (unsafe output path, a non-PM-OS
    folder in the way, a release-check error) happens before anything under
    `out_dir` is created or deleted. Publishing removes only the files the
    previous build wrote (#68). With ``release_note`` the build is recorded as
    a release in `.releases/` (#73).
    """
    handoff_root = _validate_handoff_root(out_dir, root)
    audiences = [audience] if audience else list(AUDIENCES)
    for aud in audiences:
        _check_audience_dir(handoff_root, aud)
    if release_note is not None and not release_note.strip():
        raise SystemExit("Error: --release-note needs a one-line reason for this release.")

    kept: dict[str, list[str]] = {}
    with tempfile.TemporaryDirectory(prefix="pm-os-package-") as tmp:
        # Resolved: on Windows the temp dir can come back as an 8.3 short path
        # (MANDAL~1.KAR) while build_package resolves its output to the long one.
        staged_root = Path(tmp).resolve() / "handoff"
        staged = build_package(root, staged_root, with_html=with_html, audience=audience)
        meta = _load_live_meta(root)
        snapshot = _add_release_files(root, staged_root, audiences, meta, release_note)
        staged += [staged_root / aud / name for aud in audiences
                   for name in (release_record.CHANGES_FILE, release_record.MANIFEST_FILE)]
        reports = [
            (f"{_display(handoff_root / aud, root)}/",
             release_check.check_release(staged_root / aud, project_root=root))
            for aud in audiences
        ]
        release_check.guard_release(root, reports, allow=allow_release_errors,
                                    surface="handoff_package")
        overridden = sorted({f.code for _, r in reports for f in r.errors})

        handoff_root.mkdir(parents=True, exist_ok=True)
        for aud in audiences:
            target = handoff_root / aud
            kept[aud] = release_record.clear_generated(target)
            target.mkdir(parents=True, exist_ok=True)
            shutil.copytree(staged_root / aud, target, dirs_exist_ok=True)
        written = [handoff_root / Path(p).resolve().relative_to(staged_root) for p in staged]

    project_name = meta.get("project_name") or meta.get("project_slug", "project")
    _write_hub_readme(handoff_root, project_name, datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    for aud, files in kept.items():
        if files:
            print(f"Kept {len(files)} file(s) in handoff/{aud}/ that PM-OS did not write: "
                  + ", ".join(files[:10]) + (" …" if len(files) > 10 else ""))
    if release_note:
        path = _record_release(root, snapshot, release_note.strip(), audiences, overridden)
        print(f"Recorded release {snapshot['release_id']} in {_display(path, root)}.")
    return written


def _display(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


# --- entrypoint ----------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Share a PM-OS project or stage.")
    parser.add_argument("stage_id", nargs="?", help="Stage to share (e.g. '01'); omit for all approved. Ignored with --package.")
    parser.add_argument("--output", type=str, help="Output path: a file in raw mode (default: stdout), a directory in --package mode (default: ./handoff/)")
    parser.add_argument("--package", action="store_true", help="Build the readable handoff package (per-story files + reference docs) instead of a raw text export")
    parser.add_argument(
        "--audience", choices=list(AUDIENCES),
        help="With --package, rebuild only this audience's subfolder (handoff/<audience>/), "
             "leaving other audience subfolders untouched. Omit to (re)build all four.",
    )
    parser.add_argument("--html", action="store_true", help="With --package, also emit an index.html per built audience folder")
    parser.add_argument(
        "--allow-secrets", dest="allow_secrets", action="store_true",
        help="Export even though the scan found likely secrets (API keys, tokens, private "
             "keys) in the exported artifacts. Logged as secrets_allowed; rotate the credential.",
    )
    parser.add_argument(
        "--allow-release-errors", dest="allow_release_errors", action="store_true",
        help="With --package, publish even though the release check found errors "
             "(undefined ids, broken links, missing priorities…). Logged as "
             "release_check_overridden with the overridden codes.",
    )
    parser.add_argument(
        "--include-unapproved", dest="include_unapproved", action="store_true",
        help="Raw mode: also export stages that are edited, draft or stale. Each is "
             "marked NOT APPROVED in the output.",
    )
    parser.add_argument(
        "--release-note", dest="release_note", metavar="REASON",
        help="With --package, record this build as a release (.releases/REL-###.yaml) with a "
             "one-line reason. Every build writes CHANGES.md against the last release; only "
             "builds given a note are recorded.",
    )
    args = parser.parse_args()

    if args.audience and not args.package:
        raise SystemExit("Error: --audience only applies with --package.")
    if args.release_note is not None and not args.package:
        raise SystemExit("Error: --release-note only applies with --package.")

    try:
        root = resolve_project()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if args.package:
        out_dir = Path(args.output) if args.output else root / "handoff"
        # Before build_package touches handoff/: a blocked export writes nothing.
        secret_scan.guard_export(root, package_source_paths(root),
                                 allow=args.allow_secrets, export="handoff_package")
        written = publish_package(root, out_dir, with_html=args.html, audience=args.audience,
                                  allow_release_errors=args.allow_release_errors,
                                  release_note=args.release_note)
        base = _display(out_dir, root)
        scope = f"{base}/{args.audience}/" if args.audience else f"{base}/{{dev,design,qa,business}}/"
        print(f"Handoff package written to {scope} ({len(written)} files).")
        print("This package is read-only — regenerate with `/pm-handoff --package` after approving PRD/QA/design changes.")
        return

    _raw_export(root, args.stage_id, args.output, args.allow_secrets, args.include_unapproved)


if __name__ == "__main__":
    main()
