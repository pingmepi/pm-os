"""Read-only project consistency checks (T10 — the `/pm-check` toolkit).

Reuses the same invariants already enforced piecemeal by pm_approve.py,
pre-stage.py, and post-approve.py, and already asserted (on throwaway
fixtures) by the T0-T9 test suite, so the runtime check and the test
apparatus share one implementation instead of drifting apart. See
docs/plans/pm-os-test-implementation-plan.md §19 for the design.

check_project() never mutates project state — it only reads .meta.yaml,
artifact frontmatter, telemetry.jsonl, and optional context/sources YAML.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from project import STAGE_NAMES, artifact_path, load_meta, upstream_stage_ids
from hashing import CompositeHashError, stage_content_hash
from frontmatter import read as fm_read
from telemetry import verify_chain
from artifact_contracts import (
    JOURNEY_ID_RE,
    information_architecture_section,
    requirement_ids,
    screen_id_declarations,
    screen_serves,
    split_screen_blocks,
    split_task_blocks,
    task_id_declarations,
    task_implements,
    work_breakdown_section,
)


VALID_STATUSES = {"pending", "draft", "approved", "edited", "stale"}
VALID_ORIGINS = {"generated", "imported", "backfilled"}

CODE_META_MISSING = "META_MISSING"
CODE_META_UNREADABLE = "META_UNREADABLE"
CODE_SCHEMA_VERSION_MISSING = "SCHEMA_VERSION_MISSING"
CODE_STAGE_SHAPE_INVALID = "STAGE_SHAPE_INVALID"
CODE_ARTIFACT_MISSING = "ARTIFACT_MISSING"
CODE_ARTIFACT_UNREADABLE = "ARTIFACT_UNREADABLE"
CODE_META_FRONTMATTER_STATUS_MISMATCH = "META_FRONTMATTER_STATUS_MISMATCH"
CODE_META_FRONTMATTER_HASH_MISMATCH = "META_FRONTMATTER_HASH_MISMATCH"
CODE_BODY_HASH_DRIFT = "BODY_HASH_DRIFT"
CODE_CONTEXT_PACK_INVALID = "CONTEXT_PACK_INVALID"
CODE_APPROVED_UPSTREAM_NOT_READY = "APPROVED_UPSTREAM_NOT_READY"
CODE_TELEMETRY_CHAIN_BROKEN = "TELEMETRY_CHAIN_BROKEN"
CODE_CONTEXT_YAML_UNPARSEABLE = "CONTEXT_YAML_UNPARSEABLE"
CODE_SOURCES_YAML_UNPARSEABLE = "SOURCES_YAML_UNPARSEABLE"
CODE_CHECK_FAILED = "CHECK_FAILED"
CODE_TRD_TASK_DUPLICATE = "TRD_TASK_DUPLICATE"
CODE_TRD_TASK_ID_GAP = "TRD_TASK_ID_GAP"
CODE_TRD_TASK_ORPHAN = "TRD_TASK_ORPHAN"
CODE_TRD_TASK_UNKNOWN_REQ = "TRD_TASK_UNKNOWN_REQ"
CODE_TRD_WORK_BREAKDOWN_MISSING = "TRD_WORK_BREAKDOWN_MISSING"
CODE_TRD_REQ_NOT_IMPLEMENTED = "TRD_REQ_NOT_IMPLEMENTED"
CODE_SCREEN_DUPLICATE = "SCREEN_DUPLICATE"
CODE_SCREEN_ID_GAP = "SCREEN_ID_GAP"
CODE_SCREEN_ORPHAN = "SCREEN_ORPHAN"
CODE_SCREEN_UNKNOWN_REQ = "SCREEN_UNKNOWN_REQ"
CODE_SCREEN_IDS_MISSING = "SCREEN_IDS_MISSING"
CODE_STORY_HAS_NO_SCREEN = "STORY_HAS_NO_SCREEN"


@dataclass(frozen=True)
class Issue:
    code: str
    severity: str  # "error" | "warning"
    stage: str | None
    message: str
    remediation: str

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity,
            "stage": self.stage,
            "message": self.message,
            "remediation": self.remediation,
        }


def check_project(project_root) -> list[Issue]:
    """Audit a PM-OS project for internal consistency. Read-only; never mutates state."""
    project_root = Path(project_root)
    meta_path = project_root / ".meta.yaml"
    if not meta_path.exists():
        return [Issue(
            CODE_META_MISSING, "error", None,
            f"No .meta.yaml found at {project_root}",
            "Confirm this is a PM-OS project directory (or run /pm-new).",
        )]

    try:
        meta = load_meta(project_root)
    except Exception as e:  # noqa: BLE001 — a malformed meta is diagnostic, not a crash
        return [Issue(
            CODE_META_UNREADABLE, "error", None,
            f"Could not parse .meta.yaml: {e}",
            "Inspect .meta.yaml for YAML syntax errors.",
        )]

    stages = meta.get("stages") or []
    # Shared across invariants so each doesn't re-stat the filesystem.
    paths = {s["id"]: Path(artifact_path(project_root, s["id"]))
             for s in stages if s.get("id") in STAGE_NAMES}
    exists = {sid: p.exists() for sid, p in paths.items()}

    issues: list[Issue] = []
    checks = (
        lambda: _check_schema_and_stage_shape(meta),
        lambda: _check_artifacts_present(stages, paths, exists),
        lambda: _check_meta_frontmatter_sync(stages, paths, exists),
        lambda: _check_body_hash_drift(project_root, stages, paths, exists),
        lambda: _check_upstream_approval_shape(meta, stages),
        lambda: _check_telemetry_chain(project_root),
        lambda: _check_context_yaml_parses(project_root),
        lambda: _check_trd_task_ids(project_root, stages, paths, exists),
        lambda: _check_screen_ids(project_root, stages, paths, exists),
    )
    for check in checks:
        try:
            issues.extend(check())
        except Exception as e:  # noqa: BLE001 — one invariant's bug must not hide the rest
            issues.append(Issue(
                CODE_CHECK_FAILED, "error", None,
                f"An internal consistency check failed unexpectedly: {e}",
                "This is likely a bug in lib/consistency.py — report it.",
            ))
    return issues


def _check_schema_and_stage_shape(meta: dict) -> list[Issue]:
    issues: list[Issue] = []
    if not isinstance(meta.get("schema_version"), int):
        issues.append(Issue(
            CODE_SCHEMA_VERSION_MISSING, "error", None,
            "schema_version is missing or not an integer in .meta.yaml",
            "Run any /pm-* command — load_meta() auto-migrates the schema in place.",
        ))

    for stage in meta.get("stages") or []:
        sid = stage.get("id")
        missing_fields = [f for f in ("id", "status", "origin") if not stage.get(f)]
        if missing_fields:
            issues.append(Issue(
                CODE_STAGE_SHAPE_INVALID, "error", sid,
                f"Stage entry is missing required field(s): {', '.join(missing_fields)}",
                "Inspect .meta.yaml — this stage entry is malformed and needs manual repair.",
            ))
            continue
        if sid not in STAGE_NAMES:
            issues.append(Issue(
                CODE_STAGE_SHAPE_INVALID, "error", sid,
                f"Unknown stage id '{sid}' — not part of the PM-OS stage catalog",
                "Remove or correct this stage entry in .meta.yaml.",
            ))
        if stage["status"] not in VALID_STATUSES:
            issues.append(Issue(
                CODE_STAGE_SHAPE_INVALID, "error", sid,
                f"Invalid status '{stage['status']}' for stage {sid}",
                f"Valid statuses: {', '.join(sorted(VALID_STATUSES))}.",
            ))
        if stage["origin"] not in VALID_ORIGINS:
            issues.append(Issue(
                CODE_STAGE_SHAPE_INVALID, "error", sid,
                f"Invalid origin '{stage['origin']}' for stage {sid}",
                f"Valid origins: {', '.join(sorted(VALID_ORIGINS))}.",
            ))
    return issues


def _check_artifacts_present(stages, paths, exists) -> list[Issue]:
    issues: list[Issue] = []
    for stage in stages:
        sid = stage.get("id")
        if sid is None or stage.get("status") == "pending" or sid not in paths:
            continue
        if not exists.get(sid):
            issues.append(Issue(
                CODE_ARTIFACT_MISSING, "error", sid,
                f"Stage {sid} is '{stage.get('status')}' but its artifact file is missing ({paths[sid].name})",
                f"Regenerate stage {sid}, or reset its status to pending if the artifact was deleted intentionally.",
            ))
    return issues


def _check_meta_frontmatter_sync(stages, paths, exists) -> list[Issue]:
    issues: list[Issue] = []
    for stage in stages:
        sid = stage.get("id")
        if sid not in paths or not exists.get(sid):
            continue
        try:
            fm, _ = fm_read(str(paths[sid]))
        except Exception as e:  # noqa: BLE001
            issues.append(Issue(
                CODE_ARTIFACT_UNREADABLE, "error", sid,
                f"Could not read frontmatter for stage {sid}: {e}",
                f"Inspect {paths[sid].name} for a malformed frontmatter block.",
            ))
            continue

        meta_status = stage.get("status")
        fm_status = fm.get("status")
        if meta_status != fm_status:
            issues.append(Issue(
                CODE_META_FRONTMATTER_STATUS_MISMATCH, "error", sid,
                f"Stage {sid} status disagrees: .meta.yaml says '{meta_status}', frontmatter says '{fm_status}'",
                f"Re-run /pm-approve {sid} to resync — or check for a manual edit to the artifact frontmatter.",
            ))

        if meta_status in ("approved", "edited"):
            meta_hash = stage.get("content_hash")
            fm_hash = fm.get("content_hash")
            if meta_hash != fm_hash:
                issues.append(Issue(
                    CODE_META_FRONTMATTER_HASH_MISMATCH, "error", sid,
                    f"Stage {sid} content_hash disagrees between .meta.yaml and frontmatter",
                    f"Re-run /pm-approve {sid}.",
                ))
    return issues


def _check_body_hash_drift(project_root, stages, paths, exists) -> list[Issue]:
    issues: list[Issue] = []
    for stage in stages:
        sid = stage.get("id")
        if stage.get("status") != "approved" or sid not in paths or not exists.get(sid):
            continue
        try:
            current_hash = stage_content_hash(project_root, sid, paths[sid])
        except CompositeHashError as e:
            issues.append(Issue(
                CODE_CONTEXT_PACK_INVALID, "error", sid,
                f"Stage {sid}'s context pack could not be hashed: {e}",
                "Fix the 00-context/ pack (or re-run /pm-context-import --upgrade-pack).",
            ))
            continue

        recorded_hash = stage.get("content_hash")
        if current_hash != recorded_hash:
            issues.append(Issue(
                CODE_BODY_HASH_DRIFT, "warning", sid,
                f"Stage {sid} body has changed since approval "
                f"(recorded {str(recorded_hash)[:12]}, now {current_hash[:12]})",
                f"/pm-approve {sid} (or regenerate) — the gate will mark it 'edited' on next run.",
            ))
    return issues


def _check_upstream_approval_shape(meta, stages) -> list[Issue]:
    issues: list[Issue] = []
    stage_by_id = {s["id"]: s for s in stages if s.get("id")}
    for stage in stages:
        if stage.get("status") != "approved":
            continue
        sid = stage["id"]
        for uid in upstream_stage_ids(sid, meta):
            upstream = stage_by_id.get(uid)
            if upstream is None:
                continue
            ustatus = upstream.get("status")
            if ustatus in ("pending", "draft", "stale"):
                issues.append(Issue(
                    CODE_APPROVED_UPSTREAM_NOT_READY, "error", sid,
                    f"Stage {sid} is approved but upstream {uid} is '{ustatus}'",
                    f"Re-approve/regenerate {uid} first, or re-approve {sid} once {uid} is settled.",
                ))
    return issues


def _id_number(stable_id: str) -> int | None:
    """The numeric part of a stable id (`TSK-007` → 7), or None if unparseable.
    Shared by the TRD-task and screen sequence checks."""
    try:
        return int(stable_id.split("-", 1)[1])
    except (IndexError, ValueError):
        return None


def _check_trd_task_ids(project_root, stages, paths, exists) -> list[Issue]:
    """Validate the TRD (stage 08) Work Breakdown: TSK-### ids are unique and
    sequential, each task traces (`Implements:`) to a requirement that exists in the
    PRD, and every PRD requirement is implemented by at least one task.

    All findings are WARNING except a duplicate id (ERROR) — two tasks sharing a
    TSK-### would collide when the tracker export keys tickets off it. A TRD authored
    before the Work Breakdown contract simply has no tasks and yields one WARNING, so
    existing projects degrade gracefully rather than failing the check.
    """
    stage = next((s for s in stages if s.get("id") == "08"), None)
    if stage is None or stage.get("status") == "pending" or not exists.get("08"):
        return []
    try:
        _fm, trd_body = fm_read(str(paths["08"]))
    except Exception:
        return []  # unreadability is already reported by _check_meta_frontmatter_sync

    issues: list[Issue] = []
    # Only tasks declared inside the ## Work Breakdown section count — a stray TSK-###
    # elsewhere in the TRD is neither a delivery task nor a substitute for the section.
    work_breakdown = work_breakdown_section(trd_body)
    declarations = task_id_declarations(work_breakdown)
    if not declarations:
        return [Issue(
            CODE_TRD_WORK_BREAKDOWN_MISSING, "warning", "08",
            "TRD has no TSK-### tasks in a Work Breakdown section",
            "Regenerate stage 08 — the Work Breakdown (TSK-### tasks tracing to PRD requirements) is required for dev handoff.",
        )]

    # Duplicate ids (ERROR — collides on ticket keying).
    seen: set[str] = set()
    for tsk_id in declarations:
        if tsk_id in seen:
            issues.append(Issue(
                CODE_TRD_TASK_DUPLICATE, "error", "08",
                f"Task id {tsk_id} is declared more than once",
                "Give each TRD task a unique TSK-### id — reused ids collide when exported to the tracker.",
            ))
        seen.add(tsk_id)

    # Gaps / non-sequential numbering (WARNING).
    numbers = sorted({n for n in (_id_number(t) for t in seen) if n is not None})
    if numbers:
        missing = [n for n in range(1, numbers[-1] + 1) if n not in numbers]
        if missing:
            issues.append(Issue(
                CODE_TRD_TASK_ID_GAP, "warning", "08",
                f"TRD task ids are not sequential — missing: {', '.join(f'TSK-{n:03d}' for n in missing)}",
                "Number tasks sequentially from TSK-001 with no gaps so the set reads as a complete work breakdown.",
            ))

    # Per-task trace: implements a real PRD requirement.
    prd_body = _read_prd_body(project_root)
    prd_reqs = set(requirement_ids(prd_body)) if prd_body else set()
    implemented: set[str] = set()
    for tsk_id, block in split_task_blocks(work_breakdown).items():
        traced = task_implements(block)
        implemented.update(traced)
        if not traced:
            issues.append(Issue(
                CODE_TRD_TASK_ORPHAN, "warning", "08",
                f"Task {tsk_id} has no Implements: trace to a requirement",
                f"Add an `Implements:` line to {tsk_id} citing the PRD requirement (US-###/FR-###/REQ-###) it delivers.",
            ))
        elif prd_reqs:
            unknown = [r for r in traced if r not in prd_reqs]
            if unknown:
                issues.append(Issue(
                    CODE_TRD_TASK_UNKNOWN_REQ, "warning", "08",
                    f"Task {tsk_id} implements id(s) not in the PRD: {', '.join(unknown)}",
                    "Point the Implements: line at a requirement id that exists in the approved PRD (or add it there).",
                ))

    # Coverage: every PRD user story / functional requirement is implemented (WARNING).
    if prd_reqs:
        to_cover = {r for r in prd_reqs if r.split("-", 1)[0] in ("US", "FR")}
        uncovered = sorted(to_cover - implemented)
        if uncovered:
            issues.append(Issue(
                CODE_TRD_REQ_NOT_IMPLEMENTED, "warning", "08",
                f"PRD requirements with no implementing TRD task: {', '.join(uncovered)}",
                "Add a TSK-### task (or note a deliberate deferral) so the work breakdown covers the approved scope.",
            ))
    return issues


def _check_screen_ids(project_root, stages, paths, exists) -> list[Issue]:
    """Validate the design spec's (stage 04) screen inventory: SCR-### ids are unique
    and sequential, each screen traces (`Serves:`) to an id that exists in the PRD, and
    every PRD user story is served by at least one screen.

    Everything is WARNING except a duplicate id (ERROR — two screens sharing a SCR-###
    collide in the handoff's screen map). A design spec written before screen ids
    existed simply yields the one "no SCR-### screens" warning, so existing projects
    degrade gracefully instead of failing the check.
    """
    stage = next((s for s in stages if s.get("id") == "04"), None)
    if stage is None or stage.get("status") == "pending" or not exists.get("04"):
        return []
    try:
        _fm, design_body = fm_read(str(paths["04"]))
    except Exception:
        return []  # unreadability is already reported by _check_meta_frontmatter_sync

    issues: list[Issue] = []
    # Only screens declared inside ## Information Architecture count — a SCR-###
    # referenced under Key User Flows is a reference, not a second declaration.
    ia_section = information_architecture_section(design_body)
    declarations = screen_id_declarations(ia_section)
    if not declarations:
        return [Issue(
            CODE_SCREEN_IDS_MISSING, "warning", "04",
            "Design spec has no SCR-### screens in its Information Architecture",
            "Give each screen a SCR-### id and a `Serves:` line so the handoff package can map screens to user stories.",
        )]

    seen: set[str] = set()
    for scr_id in declarations:
        if scr_id in seen:
            issues.append(Issue(
                CODE_SCREEN_DUPLICATE, "error", "04",
                f"Screen id {scr_id} is declared more than once",
                "Give each screen a unique SCR-### id — reused ids collide in the handoff screen map.",
            ))
        seen.add(scr_id)

    numbers = sorted({n for n in (_id_number(s) for s in seen) if n is not None})
    if numbers:
        missing = [n for n in range(1, numbers[-1] + 1) if n not in numbers]
        if missing:
            issues.append(Issue(
                CODE_SCREEN_ID_GAP, "warning", "04",
                f"Screen ids are not sequential — missing: {', '.join(f'SCR-{n:03d}' for n in missing)}",
                "Number screens sequentially from SCR-001 with no gaps so the inventory reads as complete.",
            ))

    # Per-screen trace: serves a real PRD story/requirement/journey.
    prd_body = _read_prd_body(project_root)
    known_ids = set(requirement_ids(prd_body)) | set(_journey_ids(prd_body)) if prd_body else set()
    served: set[str] = set()
    for scr_id, block in split_screen_blocks(ia_section).items():
        traced = screen_serves(block)
        served.update(traced)
        if not traced:
            issues.append(Issue(
                CODE_SCREEN_ORPHAN, "warning", "04",
                f"Screen {scr_id} has no Serves: trace to a story, requirement, or journey",
                f"Add a `Serves:` line to {scr_id} citing the PRD ids (US-###/FR-###/UJ-###) it supports.",
            ))
        elif known_ids:
            unknown = [r for r in traced if r not in known_ids]
            if unknown:
                issues.append(Issue(
                    CODE_SCREEN_UNKNOWN_REQ, "warning", "04",
                    f"Screen {scr_id} serves id(s) not in the PRD: {', '.join(unknown)}",
                    "Point the Serves: line at ids that exist in the approved PRD (or add them there).",
                ))

    # Coverage: every PRD user story is served by some screen (WARNING).
    if known_ids:
        stories = {r for r in known_ids if r.startswith("US-")}
        unserved = sorted(stories - served)
        if unserved:
            issues.append(Issue(
                CODE_STORY_HAS_NO_SCREEN, "warning", "04",
                f"User stories no screen declares it serves: {', '.join(unserved)}",
                "Add the story to a screen's Serves: line (or note that it is deliberately screenless, e.g. a backend-only story).",
            ))
    return issues


def _journey_ids(body: str | None) -> list[str]:
    """Unique UJ-### ids in ``body`` — screens may serve a journey as well as a story."""
    seen: dict[str, None] = {}
    for match in JOURNEY_ID_RE.findall(body or ""):
        seen.setdefault(match.upper(), None)
    return list(seen)


def _read_prd_body(project_root) -> str | None:
    path = Path(artifact_path(project_root, "03"))
    if not path.exists():
        return None
    try:
        _fm, body = fm_read(str(path))
    except Exception:
        return None
    return body


def _check_telemetry_chain(project_root) -> list[Issue]:
    result = verify_chain(project_root)
    if result["ok"]:
        return []
    return [Issue(
        CODE_TELEMETRY_CHAIN_BROKEN, "error", None,
        f"Telemetry hash chain broken at line {result['break_at']}: {result['reason']}",
        "Investigate telemetry.jsonl for manual edits or corruption; the chain cannot be auto-repaired.",
    )]


def _check_context_yaml_parses(project_root) -> list[Issue]:
    issues: list[Issue] = []
    for rel, code in (
        ("context/context.yaml", CODE_CONTEXT_YAML_UNPARSEABLE),
        (".sources.yaml", CODE_SOURCES_YAML_UNPARSEABLE),
    ):
        path = Path(project_root) / rel
        if not path.exists():
            continue
        try:
            yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            issues.append(Issue(
                code, "error", None,
                f"{rel} does not parse as YAML: {e}",
                f"Fix the YAML syntax in {rel}.",
            ))
    return issues


def error_count(issues) -> int:
    return sum(1 for i in issues if i.severity == "error")


def format_report(issues) -> str:
    if not issues:
        return "No issues found. Project is internally consistent."

    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    lines: list[str] = []
    for label, group in (("Errors", errors), ("Warnings", warnings)):
        if not group:
            continue
        lines.append(f"{label} ({len(group)}):")
        for i in group:
            stage_tag = f"[stage {i.stage}] " if i.stage else ""
            lines.append(f"  {label[:-1].upper()} {stage_tag}[{i.code}] {i.message}")
            lines.append(f"    remediation: {i.remediation}")
    return "\n".join(lines)


def summary_line(issues) -> str:
    if not issues:
        return "Consistency: healthy"
    errors = error_count(issues)
    warnings = len(issues) - errors
    if errors:
        return f"Consistency: {errors} error(s), {warnings} warning(s) — run /pm-check"
    return f"Consistency: {warnings} warning(s) — run /pm-check"
