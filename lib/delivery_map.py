"""Shared PRD delivery decomposition for readable and Jira handoff exports.

This module is deliberately mechanical: it reads stable ids and labeled ownership
from the approved PRD body, then returns one map that both export paths consume.
Product judgment stays in the stage artifacts; exporters must not invent epics.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from artifact_contracts import (
    FUNCTIONAL_REQ_ID_RE,
    JOURNEY_ID_RE,
    block_priority,
    block_epic_refs,
    split_epic_blocks,
    split_functional_requirement_blocks,
    split_user_story_blocks,
    _section,
    _sections,
)


@dataclass(frozen=True)
class Epic:
    ref: str
    title: str
    body: str


@dataclass
class PrdDeliveryMap:
    epics: dict[str, Epic] = field(default_factory=dict)
    story_blocks: dict[str, str] = field(default_factory=dict)
    requirement_blocks: dict[str, str] = field(default_factory=dict)
    journey_blocks: dict[str, str] = field(default_factory=dict)
    story_to_epic: dict[str, str] = field(default_factory=dict)
    requirement_to_epic: dict[str, str] = field(default_factory=dict)
    priorities: dict[str, str] = field(default_factory=dict)
    story_requirements: dict[str, list[str]] = field(default_factory=dict)
    story_journeys: dict[str, list[str]] = field(default_factory=dict)
    unassigned: list[str] = field(default_factory=list)


_UJ_BLOCK_START_RE = re.compile(
    r"^(?:#{1,6}\s+|[-*+]\s+|\d+\.\s+)?\*{0,2}(?P<id>UJ-\d{3,})\b",
    re.MULTILINE | re.IGNORECASE,
)


def _split_blocks(text: str, start_re: "re.Pattern[str]") -> dict[str, str]:
    matches = list(start_re.finditer(text or ""))
    blocks: dict[str, str] = {}
    for index, match in enumerate(matches):
        block_id = match.group("id").upper()
        if block_id in blocks:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text or "")
        blocks[block_id] = (text or "")[match.start():end]
    return blocks


def strip_decl(line: str, block_id: str) -> str:
    """Strip the leading markdown marker/id/priority from a declaration line."""
    t = re.sub(r"^(?:#{1,6}\s+|[-*+]\s+|\d+\.\s+)?", "", line or "")
    t = re.sub(
        rf"^\**\s*{re.escape(block_id)}\b\s*(?:\([^)]*\))?\s*[:—–-]*\s*\**\s*",
        "", t, flags=re.IGNORECASE,
    )
    return t.strip().strip("*").strip()


def title_of(block_id: str, block: str) -> str:
    """Best-effort human title from a stable-id block declaration."""
    first = block.strip().splitlines()[0] if block.strip() else ""
    return strip_decl(first, block_id) or block_id


def body_of(block: str, block_id: str) -> str:
    """Return a block body, preserving single-line declarations after id stripping."""
    lines = block.strip().splitlines()
    if not lines:
        return ""
    if len(lines) > 1:
        return "\n".join(lines[1:]).strip()
    return strip_decl(lines[0], block_id)


def single_epic_ref(block: str, declared_epics: set[str]) -> str | None:
    """Return the one valid labeled Epic ref for a block, or None.

    The Stage 03 validator reports missing/multiple/unknown refs once Product
    Epics are declared. Exporters use this conservative helper and leave unowned
    items unparented if they see a legacy or pre-validation artifact.
    """
    refs = block_epic_refs(block)
    if len(refs) != 1:
        return None
    return refs[0] if refs[0] in declared_epics else None


def build_prd_delivery_map(prd_body: str) -> PrdDeliveryMap:
    sections = _sections(prd_body or "")
    epic_blocks = split_epic_blocks(_section(sections, "Product Epics") or "")
    story_blocks = split_user_story_blocks(
        _section(sections, "User Stories with Acceptance Criteria") or prd_body or ""
    )
    requirement_blocks = split_functional_requirement_blocks(
        _section(sections, "Functional Requirements") or ""
    )
    journey_blocks = _split_blocks(_section(sections, "User Journeys") or "", _UJ_BLOCK_START_RE)

    epics = {
        epic_id: Epic(epic_id, title_of(epic_id, block), body_of(block, epic_id))
        for epic_id, block in epic_blocks.items()
    }
    declared_epics = set(epics)

    story_to_epic = {
        story_id: epic_id
        for story_id, block in story_blocks.items()
        if (epic_id := single_epic_ref(block, declared_epics))
    }
    requirement_to_epic = {
        req_id: epic_id
        for req_id, block in requirement_blocks.items()
        if (epic_id := single_epic_ref(block, declared_epics))
    }
    priorities = {
        block_id: priority
        for block_id, block in {**story_blocks, **requirement_blocks}.items()
        if (priority := block_priority(block))
    }

    story_requirements: dict[str, list[str]] = {}
    story_journeys: dict[str, list[str]] = {}
    unassigned: list[str] = []

    for story_id, block in story_blocks.items():
        forward_reqs = [m.upper() for m in FUNCTIONAL_REQ_ID_RE.findall(block)]
        forward_journeys = [m.upper() for m in JOURNEY_ID_RE.findall(block)]
        reverse_reqs = [
            rid for rid, req_block in requirement_blocks.items()
            if re.search(rf"\b{re.escape(story_id)}\b", req_block, re.IGNORECASE)
        ]
        reverse_journeys = [
            jid for jid, journey_block in journey_blocks.items()
            if re.search(rf"\b{re.escape(story_id)}\b", journey_block, re.IGNORECASE)
        ]
        story_requirements[story_id] = list(dict.fromkeys([story_id] + forward_reqs + reverse_reqs))
        story_journeys[story_id] = list(dict.fromkeys(forward_journeys + reverse_journeys))
        if declared_epics and story_id not in story_to_epic:
            unassigned.append(story_id)

    for req_id in requirement_blocks:
        if declared_epics and req_id not in requirement_to_epic:
            unassigned.append(req_id)

    return PrdDeliveryMap(
        epics=epics,
        story_blocks=story_blocks,
        requirement_blocks=requirement_blocks,
        journey_blocks=journey_blocks,
        story_to_epic=story_to_epic,
        requirement_to_epic=requirement_to_epic,
        priorities=priorities,
        story_requirements=story_requirements,
        story_journeys=story_journeys,
        unassigned=list(dict.fromkeys(unassigned)),
    )
