#!/usr/bin/env python3
"""Generate a human-readable handoff package from an approved PM-OS pipeline.

This is a *read-only projection* of the canonical stage artifacts — it never
touches the gate/hash/status state machine. Each user story is assembled into a
self-contained file (the boss house-format) by walking the existing traceability
spine (US-### -> its FR-###s -> its UJ-### journey -> its covering TC-###s), so the
handoff stays wired together instead of becoming disconnected lists.

Every generated file is stamped with the source artifact hashes and a
"DO NOT EDIT HERE" banner: the handoff is regenerable and non-canonical, so a
direct edit here is not a second source of truth (see backlog #4).

Usage:
    python3 pm_handoff.py                 # write ./handoff/ for the current project
    python3 pm_handoff.py --output DIR    # write to DIR instead of ./handoff
    python3 pm_handoff.py --html          # also emit handoff/index.html
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
    split_test_case_blocks,
    split_user_story_blocks,
)
from frontmatter import read as fm_read  # noqa: E402
from project import artifact_path, load_meta, resolve_project  # noqa: E402
import traceability  # noqa: E402

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:  # pragma: no cover - jinja2 is a declared runtime dep
    Environment = None  # type: ignore

NOT_CAPTURED = "— not captured in source —"
TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"


# --- helpers ----------------------------------------------------------------

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
    """Best-effort human title from the story's declaration line."""
    first = block.strip().splitlines()[0] if block.strip() else ""
    # Strip leading markers + the id, keep the rest of the heading.
    cleaned = re.sub(r"^(?:#{1,6}\s+|[-*+]\s+|\d+\.\s+)?", "", first)
    cleaned = re.sub(rf"^{re.escape(story_id)}\b[\s:—–-]*", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip() or story_id


def _strip_decl_line(block: str) -> str:
    """Return a block with its leading id-declaration line removed, so the
    template can supply a uniform heading regardless of how the source declared
    it (heading, bullet, or bare line)."""
    lines = block.strip().splitlines()
    return "\n".join(lines[1:]).strip() if lines else ""


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


# --- assembly ----------------------------------------------------------------

def build_package(root: Path, out_dir: Path, with_html: bool = False) -> list[Path]:
    meta = load_meta(root)
    project_name = meta.get("project_name") or meta.get("project_slug", "project")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    prd_fm, prd_body = _read_artifact(root, "03")
    _qa_fm, qa_body = _read_artifact(root, "06")
    _brief_fm, brief_body = _read_artifact(root, "01")
    _scope_fm, scope_body = _read_artifact(root, "02")

    if prd_body is None:
        raise SystemExit("Error: no approved PRD (03-prd.md) found — nothing to hand off.")

    tc_blocks = split_test_case_blocks(qa_body) if qa_body else {}

    # Clean out a stale package so removed stories don't linger.
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "stories").mkdir(parents=True, exist_ok=True)
    (out_dir / "reference").mkdir(parents=True, exist_ok=True)
    (out_dir / "epics").mkdir(parents=True, exist_ok=True)

    prd_stamp = _stamp(root, "03")
    written: list[Path] = []

    # --- per-story files (the centrepiece) ---
    stories_section = _section_of(prd_body, "user stories with acceptance criteria")
    story_blocks = split_user_story_blocks(stories_section or prd_body)
    story_index: list[tuple[str, str, str]] = []  # (id, title, filename)

    for story_id, block in story_blocks.items():
        title = _story_title(story_id, block)
        # Requirements this story exercises: itself + any FR/REQ ids in its block.
        reqs = [story_id] + [m.upper() for m in FUNCTIONAL_REQ_ID_RE.findall(block)]
        reqs = list(dict.fromkeys(reqs))
        journeys = list(dict.fromkeys(m.upper() for m in JOURNEY_ID_RE.findall(block)))

        # Covering test cases via the traceability resolver, then fetch their text.
        tc_ids: list[str] = []
        for r in reqs:
            for tc in traceability.scenarios_for_requirement(root, r):
                if tc not in tc_ids:
                    tc_ids.append(tc)
        test_cases = [
            {"id": tc, "body": _strip_decl_line(tc_blocks.get(tc, "")) or NOT_CAPTURED}
            for tc in tc_ids
        ]

        generated_from = [s for s in (prd_stamp, _stamp(root, "06")) if s]
        rendered = _render_story({
            "story_id": story_id,
            "title": title,
            "epic": "EPIC-01",
            "story_body": _strip_decl_line(block) or NOT_CAPTURED,
            "requirements": [r for r in reqs if r != story_id],
            "journeys": journeys,
            "test_cases": test_cases,
            "test_case_ids": tc_ids,
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
        f"Edit the canonical artifact and regenerate with /pm-handoff. -->\n\n"
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
        "> `/pm-handoff` — do not edit files here.",
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a readable handoff package.")
    parser.add_argument("--output", type=str, help="Output directory (default: ./handoff)")
    parser.add_argument("--html", action="store_true", help="Also emit handoff/index.html")
    args = parser.parse_args()

    try:
        root = resolve_project()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    out_dir = Path(args.output) if args.output else root / "handoff"
    written = build_package(root, out_dir, with_html=args.html)
    print(f"Handoff package written to {out_dir}/ ({len(written)} files).")
    print("This package is read-only — regenerate with /pm-handoff after approving PRD/QA changes.")


if __name__ == "__main__":
    main()
