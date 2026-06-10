import html
import re
from pathlib import Path
from typing import Any, Union

from jinja2 import Environment, FileSystemLoader, select_autoescape

from frontmatter import read as read_frontmatter
from project import artifact_path, load_meta


def render_design_spec(project_root: Union[Path, str]) -> Path:
    """Render the approved stage 04 design spec into its HTML companion."""
    project_root = Path(project_root)
    meta, sections = _stage_context(project_root, "04")
    output_path = project_root / "04-design-spec.html"
    html_text = _render_template(
        "design-spec.html.j2",
        {
            "title": f"Design Spec: {meta.get('project_name', meta['project_slug'])}",
            "project_slug": meta["project_slug"],
            "stage_label": "Stage 04",
            "source_file": "04-design-spec.md",
            "sections": sections,
            "summary": _section_text(sections, "Information Architecture"),
        },
    )
    output_path.write_text(html_text, encoding="utf-8")
    return output_path


def render_prototype_mockup(project_root: Union[Path, str]) -> Path:
    """Render the approved stage 05 brief into a lo-fi HTML prototype."""
    project_root = Path(project_root)
    meta, prototype_sections = _stage_context(project_root, "05")
    _design_meta, design_sections = _stage_context(project_root, "04")
    screens = _list_items(_section_text(prototype_sections, "Screens to Include"))
    interactions = _list_items(_section_text(prototype_sections, "Interactions to Demonstrate"))
    output_path = project_root / "05-prototype-mockup.html"
    html_text = _render_template(
        "prototype-mockup.html.j2",
        {
            "title": f"Prototype Mockup: {meta.get('project_name', meta['project_slug'])}",
            "project_slug": meta["project_slug"],
            "stage_label": "Stage 05",
            "source_file": "04-design-spec.md + 05-prototype-brief.md",
            "prototype_sections": prototype_sections,
            "design_sections": design_sections,
            "screens": _prototype_screens(
                screens,
                interactions,
                _list_items(_section_text(design_sections, "Component Inventory")),
            ),
            "interactions": interactions,
            "questions": _list_items(_section_text(prototype_sections, "Questions the Prototype Should Answer")),
            "design_principles": _section_text(design_sections, "Design Principles"),
            "ia": _section_text(design_sections, "Information Architecture"),
            "tokens": {
                "typography": _section_text(design_sections, "Typography"),
                "colors": _section_text(design_sections, "Color Tokens"),
                "spacing": _section_text(design_sections, "Spacing Tokens"),
            },
        },
    )
    output_path.write_text(html_text, encoding="utf-8")
    return output_path


def _stage_context(project_root: Path, stage_id: str) -> tuple[dict[str, Any], list[dict[str, str]]]:
    meta = load_meta(project_root)
    stage_file = artifact_path(project_root, stage_id)
    if not stage_file.exists():
        raise FileNotFoundError(f"Cannot render HTML companion: missing {stage_file.name}")

    _frontmatter, body = read_frontmatter(str(stage_file))
    sections = _parse_sections(body)
    return meta, sections


def _render_template(template_name: str, context: dict[str, Any]) -> str:
    templates_dir = Path(__file__).resolve().parents[1] / "templates"
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html", "xml", "j2"]),
    )
    env.filters["markdownish"] = _markdownish
    template = env.get_template(template_name)
    return template.render(**context)


def _parse_sections(markdown: str) -> list[dict[str, str]]:
    sections: list[dict[str, str]] = []
    current_title = "Overview"
    current_lines: list[str] = []

    for line in markdown.splitlines():
        if line.startswith("# "):
            continue
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            if current_lines:
                sections.append(_section(current_title, current_lines))
            current_title = match.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines or not sections:
        sections.append(_section(current_title, current_lines))
    return sections


def _section(title: str, lines: list[str]) -> dict[str, str]:
    raw = "\n".join(lines).strip()
    return {
        "title": title,
        "raw": raw,
        "html": _markdownish(raw),
    }


def _section_text(sections: list[dict[str, str]], title: str) -> str:
    for section in sections:
        if section["title"].strip().lower() == title.strip().lower():
            return section["raw"]
    return ""


def _list_items(markdown: str) -> list[str]:
    items: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        match = re.match(r"^(?:[-*]|\d+[.])\s+(.+)$", stripped)
        if match:
            items.append(match.group(1).strip())
    if items:
        return items
    fallback = [line.strip() for line in markdown.splitlines() if line.strip()]
    return fallback[:6]


def _prototype_screens(screens: list[str], interactions: list[str], components: list[str]) -> list[dict[str, Any]]:
    if not screens:
        screens = ["Primary screen"]
    if not components:
        components = ["Primary content area", "Action controls", "Status or feedback area"]

    prototype = []
    for index, screen in enumerate(screens):
        prototype.append(
            {
                "title": screen,
                "eyebrow": "Start" if index == 0 else f"Step {index + 1}",
                "components": _rotate(components, index, 4),
                "interactions": _rotate(interactions, index, 3),
            }
        )
    return prototype


def _rotate(items: list[str], offset: int, limit: int) -> list[str]:
    if not items:
        return []
    rotated = items[offset:] + items[:offset]
    return rotated[:limit]


def _markdownish(markdown: str) -> str:
    """Convert a small, predictable subset of Markdown into safe HTML."""
    if not markdown.strip():
        return '<p class="muted">No content provided.</p>'

    blocks: list[str] = []
    list_items: list[str] = []

    def flush_list() -> None:
        if list_items:
            blocks.append("<ul>" + "".join(list_items) + "</ul>")
            list_items.clear()

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            flush_list()
            continue

        bullet = re.match(r"^(?:[-*]|\d+[.])\s+(.+)$", line)
        if bullet:
            list_items.append(f"<li>{_inline(bullet.group(1))}</li>")
            continue

        flush_list()
        if line.startswith("### "):
            blocks.append(f"<h3>{_inline(line[4:])}</h3>")
        else:
            blocks.append(f"<p>{_inline(line)}</p>")

    flush_list()
    return "\n".join(blocks)


def _inline(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return escaped
