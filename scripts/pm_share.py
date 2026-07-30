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
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.environ.get("PM_OS_LIB_PATH") or str(Path.home() / ".pm-os" / "lib"))

from artifact_contracts import (  # noqa: E402
    _sections,
    information_architecture_section,
    split_screen_blocks,
    split_task_blocks,
    split_test_case_blocks,
    split_user_story_blocks,
    work_breakdown_section,
)
from delivery_map import build_prd_delivery_map, title_of  # noqa: E402
from frontmatter import read as fm_read  # noqa: E402
from project import artifact_path, load_meta, resolve_project, STAGE_NAMES  # noqa: E402
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
    "stories": {"dev", "qa"},
    "epics": {"dev", "business"},
    "overview": {"business"},
    "prioritization": {"dev", "business"},
    "user_journeys": {"dev", "design", "qa", "business"},
    # qa included (not just dev/business) because the story template links every
    # story to impact analysis — without it, that link would dangle in qa/, the
    # only other audience folder that carries stories. QA also legitimately uses
    # impact analysis to scope regression coverage.
    "impact_analysis": {"dev", "qa", "business"},
    "nfrs": {"dev", "qa"},
    "qa_scenarios": {"qa"},
    "screen_map": {"design", "qa"},
    "wireframes": {"dev", "design", "qa"},
}


def _categories_for_audience(audience: str) -> set[str]:
    return {cat for cat, audiences in AUDIENCE_CATEGORIES.items() if audience in audiences}


def _stage_status(meta: dict, stage_id: str) -> str | None:
    """Return the recorded status of a stage from .meta.yaml, or None if absent."""
    for stage in meta.get("stages", []):
        if stage.get("id") == stage_id:
            return stage.get("status")
    return None


def _resolve_handoff_root(out_dir: Path, root: Path) -> Path:
    """Resolve and validate the top-level `handoff/` directory, non-destructively.

    Unlike a package audience subfolder (see `_prepare_audience_dir`), the root
    is never wiped: `pm_handoff.py` writes `jira-plan.*`/`jira-import.*` at this
    same level, and this function's job is only to refuse an unsafe target
    (project root/ancestor/cwd) and ensure the directory exists — never to
    inspect or clear its contents.
    """
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
    out.mkdir(parents=True, exist_ok=True)
    return out


def _prepare_audience_dir(handoff_root: Path, audience: str) -> Path:
    """Resolve, validate, and clear ONE audience subfolder (handoff/<audience>/),
    leaving sibling audience folders and any root-level files (jira-plan.*,
    jira-import.*, the hub README) untouched. Mirrors the old whole-package
    guard, just scoped one directory deeper: refuses to `rmtree` an existing
    non-empty folder that lacks this tool's marker.
    """
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
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
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

def _slug(text: str, fallback: str = "item") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
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
    return cleaned.strip().strip("*").strip() or story_id


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
    return env.get_template("handoff-story.md.j2").render(**ctx)


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


def build_package(
    root: Path, out_dir: Path, with_html: bool = False, audience: str | None = None
) -> list[Path]:
    if audience is not None and audience not in AUDIENCES:
        raise SystemExit(f"Error: --audience must be one of {', '.join(AUDIENCES)}.")

    meta = load_meta(root)
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
            "Approve the PRD (/pm-approve 03) before packaging."
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
    if _stage_status(meta, "04") == "approved":
        _design_fm, design_body = _read_artifact(root, "04")
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
    # Product Epics. This is the same decomposition `pm_handoff.py` uses. The
    # handoff package is what to build now, so scope to the mvp band — deferred
    # (v1/v2/later) stubs are roadmap context, not per-audience build items.
    delivery = build_prd_delivery_map(prd_body, mvp_only=True)

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

    # --- compute all content ONCE in memory, keyed by output-fragment path ---
    # (render once, write into every audience folder a category belongs to —
    # this guarantees byte-identical duplicates across audiences, since `now`
    # and every rendered string are computed exactly once for the whole call.)
    stories: list[dict] = []  # {id, title, filename, content, epic, priority, requirements}
    story_index: list[dict] = []
    # Story ids that resolved to >=1 screen, captured from the same per-story
    # resolution the story files use (requirements *and* journeys). The screen map's
    # "Stories with no screen" list is derived from this set, not from each screen's
    # literal `serves` ids — otherwise a story covered only via a journey link
    # (a screen serves UJ-001, which serves US-001) would be reported uncovered in
    # the map while its own story file lists that screen.
    covered_story_ids: set[str] = set()

    for story_id, block in delivery.story_blocks.items():
        title = _story_title(story_id, block)
        epic_ref = delivery.story_to_epic.get(story_id)
        reqs = delivery.story_requirements.get(story_id, [story_id])
        journeys = delivery.story_journeys.get(story_id, [])

        tc_ids: list[str] = []
        for r in reqs:
            for tc in traceability.scenarios_for_requirement(root, r):
                if tc not in tc_ids:
                    tc_ids.append(tc)
        test_cases = [
            {"id": tc, "body": _strip_decl_line(tc_blocks.get(tc, ""), tc) or NOT_CAPTURED}
            for tc in tc_ids
        ]

        screen_ids: list[str] = []
        for ref in reqs + journeys:
            for scr in traceability.screens_for_requirement(root, ref, index=spine):
                if scr not in screen_ids:
                    screen_ids.append(scr)
        screens = [
            {
                "id": scr,
                "name": _story_title(scr, screen_blocks.get(scr, "")),
                "body": _strip_decl_line(screen_blocks.get(scr, ""), scr) or NOT_CAPTURED,
                "link": _screen_link(scr, has_proto, anchored_ids),
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
        if screens and design_stamp:
            generated_from.append(design_stamp)
        if tasks and trd_stamp:
            generated_from.append(trd_stamp)
        rendered = _render_story({
            "story_id": story_id,
            "title": title,
            "epic": epic_ref or NOT_CAPTURED,
            "priority": delivery.priorities.get(story_id) or NOT_CAPTURED,
            "story_body": _strip_decl_line(block, story_id) or NOT_CAPTURED,
            "requirements": [r for r in reqs if r != story_id],
            "journeys": journeys,
            "test_cases": test_cases,
            "test_case_ids": tc_ids,
            "screens": screens,
            "screen_ids": screen_ids,
            "tasks": tasks,
            "task_ids": tsk_ids,
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
    overview_content = _stamped_doc(
        f"{project_name} — Handoff Overview",
        [s for s in (_stamp(root, "01"), _stamp(root, "02")) if s],
        now,
        f"## Who\n\n{who or NOT_CAPTURED}\n\n"
        f"## What & Why\n\n{what_why or NOT_CAPTURED}\n\n"
        f"## How\n\n{how or NOT_CAPTURED}\n",
    )

    # --- epic indexes (one file per Product Epic declared in the PRD) ---
    epics: list[dict] = []  # {id, title, filename, content}
    epic_index: list[dict] = []
    for epic_ref, epic_rec in delivery.epics.items():
        epic_lines = [
            "## Outcome and scope",
            "",
            epic_rec.body.strip() or NOT_CAPTURED,
            "",
            "## Stories in this epic",
            "",
        ]
        epic_stories = [story for story in story_index if story.get("epic") == epic_ref]
        if epic_stories:
            for story in epic_stories:
                epic_lines.append(f"- **{story['id']}** [{story['title']}](../stories/{story['filename']})")
        else:
            epic_lines.append(NOT_CAPTURED)
        epic_lines += [
            "",
            "## Functional requirements in this epic",
            "",
        ]
        epic_requirements = [
            req_id for req_id, req_epic in delivery.requirement_to_epic.items()
            if req_epic == epic_ref
        ]
        if epic_requirements:
            epic_lines += [f"- {req}" for req in epic_requirements]
        else:
            epic_lines.append(NOT_CAPTURED)
        doc = _stamped_doc(
            f"{epic_ref} · {epic_rec.title}",
            [prd_stamp] if prd_stamp else [],
            now,
            "\n".join(epic_lines) + "\n",
        )
        filename = f"{epic_ref}-{_slug(epic_rec.title, epic_ref.lower())}.md"
        epics.append({"id": epic_ref, "title": epic_rec.title, "filename": filename, "content": doc})
        epic_index.append({"id": epic_ref, "title": epic_rec.title, "filename": filename})

    # --- reference docs ---
    reference_docs: dict[str, tuple[str, str]] = {}  # category -> (filename, content)
    plain_references = {
        "prioritization": ("prioritization.md", "Prioritization Method", _section_of(prd_body, "prioritization method"), prd_stamp),
        # Render from the mvp-only delivery map, not the raw PRD section, so a
        # deferred-only journey (serves only v1/v2/later requirements) doesn't ship
        # in the build package (AGENTS.md derived-tier rule).
        "user_journeys": ("user-journeys.md", "User Journeys", "\n".join(delivery.journey_blocks.values()), prd_stamp),
        "impact_analysis": ("impact-analysis.md", "Impact Analysis", _section_of(prd_body, "impact analysis"), prd_stamp),
        "nfrs": ("nfrs.md", "Non-Functional Requirements", _section_of(prd_body, "non-functional requirements"), prd_stamp),
        "qa_scenarios": (
            "qa-scenarios.md", "QA Scenarios",
            _section_of(qa_body, "functional test cases") or (qa_body or ""),
            _stamp(root, "06"),
        ),
    }
    for category, (filename, heading, content, stamp) in plain_references.items():
        doc = _stamped_doc(
            heading, [stamp] if stamp else [], now, (content.strip() or NOT_CAPTURED) + "\n"
        )
        reference_docs[category] = (filename, doc)

    # --- screen map (the reverse view: screen → the stories it serves) ---
    screen_map_content = _stamped_doc(
        "Screen Map",
        [design_stamp] if design_stamp else [],
        now,
        _screen_map_table(root, spine, screen_blocks, story_index, covered_story_ids, has_proto, anchored_ids),
    )
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
        (aud_dir / HANDOFF_MARKER).write_text(
            "PM-OS handoff package — generated by /pm-handoff --package. "
            "Safe to delete; this audience folder is regenerated wholesale on each run.\n",
            encoding="utf-8",
        )

        if "stories" in cats:
            (aud_dir / "stories").mkdir(parents=True, exist_ok=True)
            for story in stories:
                path = aud_dir / "stories" / story["filename"]
                path.write_text(story["content"], encoding="utf-8")
                written.append(path)

        if "epics" in cats:
            (aud_dir / "epics").mkdir(parents=True, exist_ok=True)
            for epic in epics:
                path = aud_dir / "epics" / epic["filename"]
                path.write_text(epic["content"], encoding="utf-8")
                written.append(path)

        if "overview" in cats:
            path = aud_dir / "00-overview.md"
            path.write_text(overview_content, encoding="utf-8")
            written.append(path)

        reference_cats = [c for c in reference_docs if c in cats]
        if reference_cats:
            (aud_dir / "reference").mkdir(parents=True, exist_ok=True)
            for cat in reference_cats:
                filename, content = reference_docs[cat]
                path = aud_dir / "reference" / filename
                path.write_text(content, encoding="utf-8")
                written.append(path)

        if "wireframes" in cats and has_proto:
            (aud_dir / "wireframes").mkdir(parents=True, exist_ok=True)
            path = aud_dir / "wireframes" / "prototype.html"
            path.write_bytes(proto_bytes)
            written.append(path)

        readme = _audience_readme(
            project_name, now, story_index, epic_index, generated_sources(root),
            has_proto and "wireframes" in cats, aud, cats,
        )
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

    lines = ["| Screen | Name | Serves | Prototype |", "|---|---|---|---|"]
    for scr_id, block in screen_blocks.items():
        served = traceability.requirements_for_screen(root, scr_id, index=spine)
        name = _story_title(scr_id, block)
        link = _screen_link(scr_id, has_proto, anchored_ids)
        link_cell = f"[Open]({link})" if link else NOT_CAPTURED
        lines.append(f"| {scr_id} | {name} | {', '.join(served) if served else NOT_CAPTURED} | {link_cell} |")

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


def _stamped_doc(heading: str, sources: list[str], when: str, body: str) -> str:
    src = ", ".join(sources) if sources else "the approved pipeline"
    return (
        f"<!-- GENERATED — DO NOT EDIT HERE. Read-only projection of {src}. "
        f"Edit the canonical artifact and regenerate with `/pm-handoff --package`. -->\n\n"
        f"# {heading}\n\n"
        f"> Generated from {src} on {when}. Do not edit here — edit the source and regenerate.\n\n"
        f"{body}"
    )


def generated_sources(root: Path) -> list[str]:
    return [s for s in (_stamp(root, sid) for sid in ("01", "02", "03", "04", "05", "06", "08")) if s]


def _audience_readme(
    project_name: str, when: str, story_index, epic_index, sources, has_proto: bool,
    audience: str, cats: set[str],
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
    reference_lines = {
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
    if has_proto:
        lines += ["", "## Design", "- [Prototype](wireframes/prototype.html)"]
    lines.append("")
    return "\n".join(lines)


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


# --- raw mode (original pm-share behavior, unchanged) -------------------------

def _raw_export(root: Path, stage_id: str | None, output: str | None) -> None:
    meta = load_meta(root)

    if stage_id:
        stage_id = stage_id.zfill(2)
        if stage_id not in STAGE_NAMES:
            print(f"Error: unknown stage '{stage_id}'")
            sys.exit(1)
        stages_to_share = [stage_id]
    else:
        stages_to_share = [s["id"] for s in meta["stages"] if s["status"] in ("approved", "edited")]

    if not stages_to_share:
        print("No approved stages to share.")
        sys.exit(0)

    lines = [f"# {meta['project_name']}", f"Project: {meta['project_slug']} | PM-OS {meta['pm_os_version']}", ""]

    for sid in stages_to_share:
        apath = artifact_path(root, sid)
        if not apath.exists():
            continue
        fm, body = fm_read(str(apath))
        h = fm.get("content_hash")
        hash_short = h[:12] if h else "N/A"
        lines += [
            "---",
            f"## Stage {sid}: {STAGE_NAMES[sid].replace('-', ' ').title()}",
            f"Status: {fm.get('status', '?')} | Hash: {hash_short}",
            "",
            body.strip(),
            "",
        ]

    text = "\n".join(lines)

    if output:
        Path(output).write_text(text)
        print(f"Exported to {output}")
    else:
        print(text)


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
    args = parser.parse_args()

    if args.audience and not args.package:
        raise SystemExit("Error: --audience only applies with --package.")

    try:
        root = resolve_project()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if args.package:
        out_dir = Path(args.output) if args.output else root / "handoff"
        written = build_package(root, out_dir, with_html=args.html, audience=args.audience)
        scope = f"handoff/{args.audience}/" if args.audience else "handoff/{dev,design,qa,business}/"
        print(f"Handoff package written to {scope} ({len(written)} files).")
        print("This package is read-only — regenerate with `/pm-handoff --package` after approving PRD/QA/design changes.")
        return

    _raw_export(root, args.stage_id, args.output)


if __name__ == "__main__":
    main()
