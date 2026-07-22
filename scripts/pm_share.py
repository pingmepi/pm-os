#!/usr/bin/env python3
"""Export approved PM-OS artifacts in two modes.

Raw mode (default) — a single stage or every approved/edited stage,
concatenated verbatim, for a quick paste into email/Slack/a doc.

Package mode (--package) — a read-only, decomposed handoff package: one
self-contained file per user story (the team's house format), an overview,
and reference docs, assembled by walking the traceability spine
(US-### -> its FR-###s -> its UJ-### journey -> its covering TC-###s). It
never touches gate/hash/status — regenerate it after any PRD/QA re-approval.

Usage:
    python3 pm_share.py                    # raw text, all approved stages
    python3 pm_share.py 03                 # raw text, stage 03 only
    python3 pm_share.py --output out.md    # raw text to a file instead of stdout
    python3 pm_share.py --package                # write ./handoff/
    python3 pm_share.py --package --output DIR   # write to DIR instead
    python3 pm_share.py --package --html          # also emit handoff/index.html
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
    FUNCTIONAL_REQ_ID_RE,
    JOURNEY_ID_RE,
    _sections,
    information_architecture_section,
    split_screen_blocks,
    split_test_case_blocks,
    split_user_story_blocks,
)
from frontmatter import read as fm_read  # noqa: E402
from project import artifact_path, load_meta, resolve_project, STAGE_NAMES  # noqa: E402
import traceability  # noqa: E402

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:  # pragma: no cover - jinja2 is a declared runtime dep
    Environment = None  # type: ignore

NOT_CAPTURED = "— not captured in source —"
TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
# Dropped into every generated package so a regeneration can safely clear a prior
# one without risking arbitrary user directories (see _prepare_out_dir).
HANDOFF_MARKER = ".pm-os-handoff"


def _stage_status(meta: dict, stage_id: str) -> str | None:
    """Return the recorded status of a stage from .meta.yaml, or None if absent."""
    for stage in meta.get("stages", []):
        if stage.get("id") == stage_id:
            return stage.get("status")
    return None


def _prepare_out_dir(out_dir: Path, root: Path) -> Path:
    """Resolve, validate, and clear the package output directory.

    ``build_package`` recreates the directory from scratch, so a prior package
    must be removed first. To keep that ``rmtree`` from erasing project data or
    an arbitrary user directory, refuse to target the project root, any ancestor
    of it, or the current directory, and refuse an existing non-empty directory
    that this tool did not generate (identified by the ``.pm-os-handoff``
    marker). Returns the resolved, now-empty (or nonexistent) path.
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
    if out.exists():
        if out.is_file():
            raise SystemExit(f"Error: {out} is a file, not a directory.")
        others = [p for p in out.iterdir() if p.name != HANDOFF_MARKER]
        if others and not (out / HANDOFF_MARKER).exists():
            raise SystemExit(
                f"Error: {out} already exists and is not a PM-OS handoff folder "
                f"(no {HANDOFF_MARKER} marker). Refusing to delete it. Pick an "
                "empty or dedicated output directory."
            )
        shutil.rmtree(out)
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


def build_package(root: Path, out_dir: Path, with_html: bool = False) -> list[Path]:
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

    # Reverse-declared requirement/journey links: a story is not required to
    # self-cite its FR/UJ ids (only journeys must cite a requirement id) — it
    # can be linked purely from the *other* direction, the FR's or journey's
    # own text naming the story. Build both directions once per project.
    fr_section = _section_of(prd_body, "functional requirements")
    uj_section = _section_of(prd_body, "user journeys")
    fr_blocks = _split_blocks(fr_section, _FR_BLOCK_START_RE)
    uj_blocks = _split_blocks(uj_section, _UJ_BLOCK_START_RE)

    # Clean out a stale package so removed stories don't linger — but only after
    # validating the target so this never erases project data or a user dir.
    out_dir = _prepare_out_dir(out_dir, root)
    (out_dir / "stories").mkdir(parents=True, exist_ok=True)
    (out_dir / "reference").mkdir(parents=True, exist_ok=True)
    (out_dir / "epics").mkdir(parents=True, exist_ok=True)
    (out_dir / HANDOFF_MARKER).write_text(
        "PM-OS handoff package — generated by /pm-share --package. "
        "Safe to delete; regenerated wholesale on each run.\n",
        encoding="utf-8",
    )

    prd_stamp = _stamp(root, "03")
    design_stamp = _stamp(root, "04")
    written: list[Path] = []

    # --- per-story files (the centrepiece) ---
    stories_section = _section_of(prd_body, "user stories with acceptance criteria")
    story_blocks = split_user_story_blocks(stories_section or prd_body)
    story_index: list[tuple[str, str, str]] = []  # (id, title, filename)

    for story_id, block in story_blocks.items():
        title = _story_title(story_id, block)

        # Forward: FR/REQ and UJ ids the story's own block cites.
        forward_reqs = [m.upper() for m in FUNCTIONAL_REQ_ID_RE.findall(block)]
        forward_journeys = [m.upper() for m in JOURNEY_ID_RE.findall(block)]
        # Reverse: FR/REQ or UJ blocks elsewhere in the PRD that name this story.
        reverse_reqs = [
            rid for rid, blk in fr_blocks.items()
            if re.search(rf"\b{re.escape(story_id)}\b", blk, re.IGNORECASE)
        ]
        reverse_journeys = [
            jid for jid, blk in uj_blocks.items()
            if re.search(rf"\b{re.escape(story_id)}\b", blk, re.IGNORECASE)
        ]

        reqs = list(dict.fromkeys([story_id] + forward_reqs + reverse_reqs))
        journeys = list(dict.fromkeys(forward_journeys + reverse_journeys))

        # Covering test cases via the traceability resolver, then fetch their text.
        tc_ids: list[str] = []
        for r in reqs:
            for tc in traceability.scenarios_for_requirement(root, r):
                if tc not in tc_ids:
                    tc_ids.append(tc)
        test_cases = [
            {"id": tc, "body": _strip_decl_line(tc_blocks.get(tc, ""), tc) or NOT_CAPTURED}
            for tc in tc_ids
        ]

        # Screens serving this story, resolved through the spine over both the story's
        # requirements and its journeys (a screen may cite either).
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
            }
            for scr in screen_ids
        ]

        generated_from = [s for s in (prd_stamp, _stamp(root, "06")) if s]
        if screens and design_stamp:
            generated_from.append(design_stamp)
        rendered = _render_story({
            "story_id": story_id,
            "title": title,
            "epic": "EPIC-01",
            "story_body": _strip_decl_line(block, story_id) or NOT_CAPTURED,
            "requirements": [r for r in reqs if r != story_id],
            "journeys": journeys,
            "test_cases": test_cases,
            "test_case_ids": tc_ids,
            "screens": screens,
            "screen_ids": screen_ids,
            "generated_from": generated_from,
            "canonical_source": "03-prd.md",
            "generated_at": now,
        })
        filename = f"{story_id}-{_slug(title, story_id.lower())}.md"
        path = out_dir / "stories" / filename
        path.write_text(rendered, encoding="utf-8")
        written.append(path)
        story_index.append((story_id, title, filename))

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
    overview = _stamped_doc(
        f"{project_name} — Handoff Overview",
        [s for s in (_stamp(root, "01"), _stamp(root, "02")) if s],
        now,
        f"## Who\n\n{who or NOT_CAPTURED}\n\n"
        f"## What & Why\n\n{what_why or NOT_CAPTURED}\n\n"
        f"## How\n\n{how or NOT_CAPTURED}\n",
    )
    (out_dir / "00-overview.md").write_text(overview, encoding="utf-8")
    written.append(out_dir / "00-overview.md")

    # --- epic index (single MVP epic; grouped story list) ---
    epic_lines = ["## Stories in this epic\n"]
    for sid, title, filename in story_index:
        epic_lines.append(f"- **{sid}** [{title}](../stories/{filename})")
    epic = _stamped_doc(
        f"EPIC-01 · {project_name} MVP",
        [prd_stamp] if prd_stamp else [],
        now,
        "\n".join(epic_lines) + "\n",
    )
    (out_dir / "epics" / "EPIC-01-mvp.md").write_text(epic, encoding="utf-8")
    written.append(out_dir / "epics" / "EPIC-01-mvp.md")

    # --- reference docs ---
    references = {
        "user-journeys.md": ("User Journeys", _section_of(prd_body, "user journeys"), prd_stamp),
        "impact-analysis.md": ("Impact Analysis", _section_of(prd_body, "impact analysis"), prd_stamp),
        "nfrs.md": ("Non-Functional Requirements", _section_of(prd_body, "non-functional requirements"), prd_stamp),
        "qa-scenarios.md": (
            "QA Scenarios",
            _section_of(qa_body, "functional test cases") or (qa_body or ""),
            _stamp(root, "06"),
        ),
    }
    for filename, (heading, content, stamp) in references.items():
        doc = _stamped_doc(
            heading, [stamp] if stamp else [], now, (content.strip() or NOT_CAPTURED) + "\n"
        )
        (out_dir / "reference" / filename).write_text(doc, encoding="utf-8")
        written.append(out_dir / "reference" / filename)

    # --- screen map (the reverse view: screen → the stories it serves) ---
    screen_map = _stamped_doc(
        "Screen Map",
        [design_stamp] if design_stamp else [],
        now,
        _screen_map_table(root, spine, screen_blocks, story_index),
    )
    (out_dir / "reference" / "screen-map.md").write_text(screen_map, encoding="utf-8")
    written.append(out_dir / "reference" / "screen-map.md")

    # --- wireframes: copy the approved prototype into the package if present ---
    proto = root / "05-prototype-mockup.html"
    if proto.exists():
        (out_dir / "wireframes").mkdir(exist_ok=True)
        shutil.copy2(proto, out_dir / "wireframes" / "prototype.html")
        written.append(out_dir / "wireframes" / "prototype.html")

    # --- README index ---
    readme = _readme(project_name, now, story_index, generated_sources(root), proto.exists())
    (out_dir / "README.md").write_text(readme, encoding="utf-8")
    written.append(out_dir / "README.md")

    if with_html:
        html_path = _write_html_index(out_dir, project_name, now, story_index)
        if html_path:
            written.append(html_path)

    return written


def _screen_map_table(root: Path, spine: dict, screen_blocks: dict, story_index) -> str:
    """The reverse of the per-story Screens section: one row per screen, listing the
    stories and journeys it serves, plus the stories no screen covers.

    Reads the served ids from the spine (``requirements_for_screen``) so this table and
    the per-story sections can never disagree."""
    if not screen_blocks:
        return (
            f"{NOT_CAPTURED}\n\n"
            "The approved design spec declares no `SCR-###` screens in its Information "
            "Architecture, so screens cannot be mapped to stories. Add screen ids with a "
            "`Serves:` line to `04-design-spec.md`, re-approve it, and regenerate.\n"
        )

    lines = ["| Screen | Name | Serves |", "|---|---|---|"]
    covered: set[str] = set()
    for scr_id, block in screen_blocks.items():
        served = traceability.requirements_for_screen(root, scr_id, index=spine)
        covered.update(served)
        name = _story_title(scr_id, block)
        lines.append(f"| {scr_id} | {name} | {', '.join(served) if served else NOT_CAPTURED} |")

    uncovered = [f"{sid} · {title}" for sid, title, _fn in story_index if sid not in covered]
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
        f"Edit the canonical artifact and regenerate with `/pm-share --package`. -->\n\n"
        f"# {heading}\n\n"
        f"> Generated from {src} on {when}. Do not edit here — edit the source and regenerate.\n\n"
        f"{body}"
    )


def generated_sources(root: Path) -> list[str]:
    return [s for s in (_stamp(root, sid) for sid in ("01", "02", "03", "04", "05", "06", "08")) if s]


def _readme(project_name: str, when: str, story_index, sources, has_proto: bool) -> str:
    lines = [
        f"# {project_name} — Handoff Package",
        "",
        f"> Generated {when} from: {', '.join(sources) if sources else 'the approved pipeline'}.",
        "> **This package is read-only.** It is a projection of the approved PM-OS",
        "> artifacts. To change anything, edit the canonical stage artifact and re-run",
        "> `/pm-share --package` — do not edit files here.",
        "",
        "## Start here",
        "- [Overview](00-overview.md) — who / what & why / how (for stakeholders)",
        "- [EPIC-01 · MVP](epics/EPIC-01-mvp.md) — the story index",
        "",
        "## User stories (dev/QA)",
    ]
    for sid, title, filename in story_index:
        lines.append(f"- [{sid} · {title}](stories/{filename})")
    lines += [
        "",
        "## Reference",
        "- [User journeys](reference/user-journeys.md)",
        "- [Screen map](reference/screen-map.md) — which screens serve which stories",
        "- [QA scenarios](reference/qa-scenarios.md)",
        "- [Impact analysis](reference/impact-analysis.md)",
        "- [Non-functional requirements](reference/nfrs.md)",
    ]
    if has_proto:
        lines.append("- [Prototype](wireframes/prototype.html)")
    lines.append("")
    return "\n".join(lines)


def _write_html_index(out_dir: Path, project_name: str, when: str, story_index) -> Path | None:
    """A minimal, self-contained HTML index. Reuses html_render's safe Markdown
    converter for the story links; no external assets."""
    try:
        sys.path.insert(0, os.environ.get("PM_OS_LIB_PATH") or str(Path.home() / ".pm-os" / "lib"))
        from html_render import _markdownish  # local, safe subset
    except Exception:
        return None
    items = "\n".join(
        f'<li><a href="stories/{fn}">{sid} · {title}</a></li>' for sid, title, fn in story_index
    )
    body = (
        f"<h1>{project_name} — Handoff Package</h1>"
        f"<p>Generated {when}. Read-only projection of the approved pipeline.</p>"
        f'<ul><li><a href="00-overview.md">Overview</a></li>'
        f'<li><a href="epics/EPIC-01-mvp.md">EPIC-01 · MVP</a></li></ul>'
        f"<h2>User stories</h2><ul>{items}</ul>"
        f"<h2>Reference</h2>"
        f'<ul><li><a href="reference/user-journeys.md">User journeys</a></li>'
        f'<li><a href="reference/screen-map.md">Screen map</a></li>'
        f'<li><a href="reference/qa-scenarios.md">QA scenarios</a></li>'
        f'<li><a href="reference/impact-analysis.md">Impact analysis</a></li>'
        f'<li><a href="reference/nfrs.md">NFRs</a></li></ul>'
    )
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
    parser.add_argument("--package", action="store_true", help="Build the full readable handoff package (per-story files + reference docs) instead of a raw text export")
    parser.add_argument("--html", action="store_true", help="With --package, also emit handoff/index.html")
    args = parser.parse_args()

    try:
        root = resolve_project()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if args.package:
        out_dir = Path(args.output) if args.output else root / "handoff"
        written = build_package(root, out_dir, with_html=args.html)
        print(f"Handoff package written to {out_dir}/ ({len(written)} files).")
        print("This package is read-only — regenerate with `/pm-share --package` after approving PRD/QA changes.")
        return

    _raw_export(root, args.stage_id, args.output)


if __name__ == "__main__":
    main()
