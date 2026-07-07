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
