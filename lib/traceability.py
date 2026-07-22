"""Phase 3.5 traceability spine.

PM-OS keeps requirement and QA-scenario links in a flat ``.traceability.yaml``
sibling dotfile at the project root (same flavour as ``.meta.yaml`` — *not* a new
hidden directory). The file links requirement ids (``REQ-###`` / ``US-###`` /
``FR-###``) to QA test-case ids (``TC-###``), and reserves slots for the
ticket/bug/code references that later phases attach.

This module is the local resolver: it (re)builds the link file from the approved
PRD (stage 03) and QA plan (stage 06) artifact bodies, and answers questions like
"which scenarios cover requirement REQ-X" without any network or external system.

Format (``schema_version: 2``)::

    schema_version: 2
    generated_at: <iso8601>
    requirements:
      REQ-001:            # or US-001 / FR-001
        kind: requirement | user_story | functional_requirement
        source: 03-prd.md
        test_cases: [TC-001, TC-002]
        tasks: [TSK-001]  # TRD tasks that implement this requirement (reverse link)
        tickets: []       # populated by Phase 4b (/pm-handoff)
        bugs: []          # reserved for Phase 5a
        code_refs: []     # reserved for Phase 5b
    test_cases:
      TC-001:
        source: 06-qa-plan.md
        requirements: [REQ-001]
        bugs: []          # reserved for Phase 5a
    tasks:                # Phase 3.5b — TRD (stage 08) Work Breakdown
      TSK-001:
        source: 08-trd.md
        implements: [US-003, FR-012]
        tickets: []       # populated by Phase 4b (/pm-handoff)
    screens:              # design spec (stage 04) Information Architecture
      SCR-001:
        source: 04-design-spec.md
        serves: [US-003, UJ-002]
        design_refs: []   # reserved for a later Figma/design export

The file is a *derived* index: it is safe to delete and regenerate. The ``links``
inside test cases are extracted from each TC-### block in the QA plan (every
requirement id mentioned in the block is treated as a covering link).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from artifact_contracts import (
    REQUIREMENT_ID_RE,
    information_architecture_section,
    requirement_ids,
    screen_serves,
    split_screen_blocks,
    split_task_blocks,
    split_test_case_blocks,
    task_implements,
    work_breakdown_section,
)
from frontmatter import read as fm_read
from project import artifact_path

TRACEABILITY_FILENAME = ".traceability.yaml"
# v2 (Phase 3.5b) adds a `tasks:` map (TRD Work Breakdown, TSK-###) and a reverse
# `tasks: []` link on each requirement. The file is a *derived* index, so a v1 file
# on disk upgrades transparently on the next rebuild — reserved req/tc slots are
# still preserved; the tasks map is simply populated for the first time.
# v3 adds a `screens:` map (design-spec Information Architecture, SCR-###) and a
# reverse `screens: []` link on each requirement, so the handoff can answer "which
# screens does this story touch". Same upgrade story as v2: the file is derived, so a
# v1/v2 file on disk upgrades transparently on the next rebuild.
TRACEABILITY_SCHEMA_VERSION = 3

# Reserved cross-reference slots that later phases populate. Kept here so the
# generated file shape is stable and forward-compatible.
_REQ_REF_SLOTS = ("tickets", "bugs", "code_refs")
_TC_REF_SLOTS = ("bugs",)
_TASK_REF_SLOTS = ("tickets",)
_SCREEN_REF_SLOTS = ("design_refs",)


def traceability_path(project_root: Path | str) -> Path:
    return Path(project_root) / TRACEABILITY_FILENAME


def _id_kind(req_id: str) -> str:
    prefix = req_id.split("-", 1)[0].upper()
    return {
        "REQ": "requirement",
        "US": "user_story",
        "FR": "functional_requirement",
        "TSK": "task",
    }.get(prefix, "requirement")


def _read_body(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    try:
        _fm, body = fm_read(str(path))
    except Exception:
        return None
    return body


def _read_body_if_approved(path: Path) -> Optional[str]:
    """Return the artifact body only when its frontmatter status is ``approved``.

    Used for the TRD so a draft/stale/edited TRD's tasks never enter the derived
    index a handoff/export consumes. The stale cascade in post-approve.py demotes
    the TRD's frontmatter status (not just meta), so re-approving an upstream stage
    correctly drops its now-obsolete task links on the next rebuild."""
    if not path.exists():
        return None
    try:
        fm, body = fm_read(str(path))
    except Exception:
        return None
    return body if (fm or {}).get("status") == "approved" else None




def build_index(project_root: Path | str) -> dict:
    """Build the in-memory traceability index from the current PRD + QA artifacts.

    Pure function: reads artifact bodies, returns the dict that ``write_index``
    serialises. Missing artifacts simply contribute nothing.
    """
    project_root = Path(project_root)
    prd_body = _read_body(artifact_path(project_root, "03"))
    qa_body = _read_body(artifact_path(project_root, "06"))

    # Only an *approved* TRD's tasks are authoritative for the index a handoff
    # export consumes; a draft/stale/edited TRD contributes nothing. The design
    # spec's screens follow the same rule for the same reason.
    trd_body = _read_body_if_approved(artifact_path(project_root, "08"))
    design_body = _read_body_if_approved(artifact_path(project_root, "04"))

    requirements: dict[str, dict] = {}
    test_cases: dict[str, dict] = {}
    tasks: dict[str, dict] = {}
    screens: dict[str, dict] = {}

    def _new_requirement(req_id: str, source: Optional[str]) -> dict:
        return {
            "kind": _id_kind(req_id),
            "source": source,
            "test_cases": [],
            "tasks": [],
            "screens": [],
            **{slot: [] for slot in _REQ_REF_SLOTS},
        }

    # Requirements come from the PRD.
    if prd_body:
        for req_id in requirement_ids(prd_body):
            requirements[req_id] = _new_requirement(req_id, artifact_path(project_root, "03").name)

    # Test cases + their covering requirement links come from the QA plan.
    if qa_body:
        for tc_id, block in split_test_case_blocks(qa_body).items():
            linked = requirement_ids(block)
            test_cases[tc_id] = {
                "source": artifact_path(project_root, "06").name,
                "requirements": linked,
                **{slot: [] for slot in _TC_REF_SLOTS},
            }
            for req_id in linked:
                # A QA plan may reference a requirement the PRD did not stably id
                # (e.g. prose PRD). Record it so the link is not silently dropped.
                entry = requirements.setdefault(req_id, _new_requirement(req_id, None))
                if tc_id not in entry["test_cases"]:
                    entry["test_cases"].append(tc_id)

    # Tasks (TRD Work Breakdown) + the requirements they implement come from stage 08.
    # Scoped to the ## Work Breakdown section so a stray TSK-### elsewhere in the TRD
    # is not indexed as a delivery task.
    if trd_body:
        for tsk_id, block in split_task_blocks(work_breakdown_section(trd_body)).items():
            implemented = task_implements(block)
            tasks[tsk_id] = {
                "source": artifact_path(project_root, "08").name,
                "implements": implemented,
                **{slot: [] for slot in _TASK_REF_SLOTS},
            }
            for req_id in implemented:
                # As with QA links, a task may implement a requirement the PRD did
                # not stably id; record it so the reverse link is not dropped.
                entry = requirements.setdefault(req_id, _new_requirement(req_id, None))
                if tsk_id not in entry["tasks"]:
                    entry["tasks"].append(tsk_id)

    # Screens (design-spec Information Architecture) + the requirements they serve.
    # Scoped to the ## Information Architecture section so a SCR-### referenced under
    # Key User Flows is a reference, not a second screen declaration.
    if design_body:
        for scr_id, block in split_screen_blocks(information_architecture_section(design_body)).items():
            served = screen_serves(block)
            screens[scr_id] = {
                "source": artifact_path(project_root, "04").name,
                "serves": served,
                **{slot: [] for slot in _SCREEN_REF_SLOTS},
            }
            for req_id in served:
                if req_id.upper().startswith("UJ-"):
                    continue  # journeys are not requirement entries; the forward link suffices
                entry = requirements.setdefault(req_id, _new_requirement(req_id, None))
                if scr_id not in entry["screens"]:
                    entry["screens"].append(scr_id)

    return {
        "schema_version": TRACEABILITY_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "requirements": requirements,
        "test_cases": test_cases,
        "tasks": tasks,
        "screens": screens,
    }


def _merge_reserved(old: dict, new: dict) -> dict:
    """Preserve manually/externally populated reserved slots (tickets/bugs/code_refs)
    across a rebuild, since those don't come from the artifacts. Derived fields
    (test_cases / requirements / source / kind) are always taken from ``new``.
    """
    old_reqs = (old or {}).get("requirements") or {}
    for req_id, entry in new.get("requirements", {}).items():
        prior = old_reqs.get(req_id) or {}
        for slot in _REQ_REF_SLOTS:
            if prior.get(slot):
                entry[slot] = prior[slot]
    old_tcs = (old or {}).get("test_cases") or {}
    for tc_id, entry in new.get("test_cases", {}).items():
        prior = old_tcs.get(tc_id) or {}
        for slot in _TC_REF_SLOTS:
            if prior.get(slot):
                entry[slot] = prior[slot]
    old_tasks = (old or {}).get("tasks") or {}
    for tsk_id, entry in new.get("tasks", {}).items():
        prior = old_tasks.get(tsk_id) or {}
        for slot in _TASK_REF_SLOTS:
            if prior.get(slot):
                entry[slot] = prior[slot]
    old_screens = (old or {}).get("screens") or {}
    for scr_id, entry in new.get("screens", {}).items():
        prior = old_screens.get(scr_id) or {}
        for slot in _SCREEN_REF_SLOTS:
            if prior.get(slot):
                entry[slot] = prior[slot]
    return new


def load_index(project_root: Path | str) -> Optional[dict]:
    """Load the on-disk ``.traceability.yaml``, or ``None`` if absent/unreadable."""
    path = traceability_path(project_root)
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def write_index(project_root: Path | str, index: dict) -> Path:
    path = traceability_path(project_root)
    path.write_text(
        yaml.safe_dump(index, sort_keys=True, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def rebuild(project_root: Path | str) -> dict:
    """Rebuild the index from artifacts, preserving reserved external refs, and
    write it to ``.traceability.yaml``. Returns the written index."""
    project_root = Path(project_root)
    new_index = build_index(project_root)
    existing = load_index(project_root)
    if existing:
        new_index = _merge_reserved(existing, new_index)
    write_index(project_root, new_index)
    return new_index


# --- Resolver queries --------------------------------------------------------

def _index_for_query(project_root: Path | str) -> dict:
    """Use the on-disk index if present, else build fresh in memory."""
    return load_index(project_root) or build_index(project_root)


def scenarios_for_requirement(project_root: Path | str, req_id: str) -> list[str]:
    """Return the TC-### ids that cover ``req_id`` (case-insensitive)."""
    req_id = req_id.upper()
    index = _index_for_query(project_root)
    entry = (index.get("requirements") or {}).get(req_id)
    if entry:
        return list(entry.get("test_cases") or [])
    # Fall back to scanning test-case links (covers ids the PRD didn't declare).
    return sorted(
        tc_id
        for tc_id, tc in (index.get("test_cases") or {}).items()
        if req_id in (tc.get("requirements") or [])
    )


def requirements_for_scenario(project_root: Path | str, tc_id: str) -> list[str]:
    """Return the requirement ids that test case ``tc_id`` covers."""
    tc_id = tc_id.upper()
    index = _index_for_query(project_root)
    entry = (index.get("test_cases") or {}).get(tc_id)
    return list(entry.get("requirements") or []) if entry else []


def tasks_for_requirement(project_root: Path | str, req_id: str) -> list[str]:
    """Return the TSK-### ids that implement ``req_id`` (case-insensitive)."""
    req_id = req_id.upper()
    index = _index_for_query(project_root)
    entry = (index.get("requirements") or {}).get(req_id)
    if entry and entry.get("tasks"):
        return list(entry.get("tasks") or [])
    # Fall back to scanning task links (covers ids the PRD didn't declare).
    return sorted(
        tsk_id
        for tsk_id, tsk in (index.get("tasks") or {}).items()
        if req_id in (tsk.get("implements") or [])
    )


def screens_for_requirement(
    project_root: Path | str, req_id: str, index: dict | None = None
) -> list[str]:
    """Return the SCR-### ids that serve ``req_id`` (case-insensitive).

    Also answers for a journey id (``UJ-###``), which has no requirement entry of its
    own — those resolve through the fallback scan of each screen's ``serves`` list.

    Pass ``index`` to resolve against an already-built index instead of the on-disk
    one — callers exporting a package build it fresh so a stale or pre-screens
    ``.traceability.yaml`` cannot silently resolve every story to zero screens."""
    req_id = req_id.upper()
    index = index if index is not None else _index_for_query(project_root)
    entry = (index.get("requirements") or {}).get(req_id)
    if entry and entry.get("screens"):
        return list(entry.get("screens") or [])
    return sorted(
        scr_id
        for scr_id, screen in (index.get("screens") or {}).items()
        if req_id in (screen.get("serves") or [])
    )


def requirements_for_screen(
    project_root: Path | str, scr_id: str, index: dict | None = None
) -> list[str]:
    """Return the ids (requirements and journeys) that screen ``scr_id`` serves.

    ``index`` overrides the on-disk index, as in ``screens_for_requirement``."""
    scr_id = scr_id.upper()
    index = index if index is not None else _index_for_query(project_root)
    entry = (index.get("screens") or {}).get(scr_id)
    return list(entry.get("serves") or []) if entry else []


def requirements_for_task(project_root: Path | str, tsk_id: str) -> list[str]:
    """Return the requirement ids that task ``tsk_id`` implements."""
    tsk_id = tsk_id.upper()
    index = _index_for_query(project_root)
    entry = (index.get("tasks") or {}).get(tsk_id)
    return list(entry.get("implements") or []) if entry else []


def uncovered_requirements(project_root: Path | str) -> list[str]:
    """Requirement ids that have no covering TC-### (a coverage gap)."""
    index = _index_for_query(project_root)
    return sorted(
        req_id
        for req_id, entry in (index.get("requirements") or {}).items()
        if not (entry.get("test_cases") or [])
    )
