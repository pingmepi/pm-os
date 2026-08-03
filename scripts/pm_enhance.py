#!/usr/bin/env python3
"""Deterministic lifecycle and baseline mechanics for PM-OS E2 enhancements."""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import yaml

sys.path.insert(0, os.environ.get("PM_OS_LIB_PATH") or str(Path.home() / ".pm-os" / "lib"))

from hashing import CompositeHashError, stage_content_hash  # noqa: E402
from frontmatter import read as fm_read, update_status  # noqa: E402
from project import artifact_path, get_stage, load_meta, resolve_project  # noqa: E402
from consistency import check_project  # noqa: E402
from enhancement import EnhancementDeltaError, active_enhancement_delta  # noqa: E402
from telemetry import log  # noqa: E402


ENHANCEMENT_SCHEMA_VERSION = 1
SURFACES = (
    "ui", "api", "data", "service", "event", "integration", "operations", "cross-cutting",
)
REQUIREMENT_PREFIXES = ("US-", "FR-", "REQ-", "NFR-")


class EnhancementError(Exception):
    """A user-actionable E2 lifecycle error."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_yaml(path: Path, default):
    if not path.exists():
        return default
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if data is not None else default


def _write_yaml_atomic(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temp.write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    os.replace(str(temp), str(path))


def _enhancements_dir(root: Path) -> Path:
    return root / ".enhancements"


def _index_path(root: Path) -> Path:
    return _enhancements_dir(root) / "index.yaml"


def _context_path(root: Path, cycle_id: str) -> Path:
    return _enhancements_dir(root) / cycle_id / "context.yaml"


def _default_index():
    return {
        "schema_version": ENHANCEMENT_SCHEMA_VERSION,
        "active_cycle": None,
        "next_sequence": 1,
        "cycles": [],
    }


def _load_index(root: Path):
    index = _read_yaml(_index_path(root), _default_index())
    if not isinstance(index, dict):
        raise EnhancementError(".enhancements/index.yaml must contain a mapping")
    index.setdefault("schema_version", ENHANCEMENT_SCHEMA_VERSION)
    index.setdefault("active_cycle", None)
    index.setdefault("next_sequence", 1)
    index.setdefault("cycles", [])
    return index


@contextmanager
def _enhancement_lock(root: Path):
    directory = _enhancements_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / ".lock"
    try:
        lock.mkdir()
    except FileExistsError:
        raise EnhancementError("another enhancement lifecycle operation is already running")
    try:
        yield
    finally:
        try:
            lock.rmdir()
        except OSError:
            pass


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _capture_approved_artifacts(
    root: Path, meta: dict, baseline_dir: Path, logical_baseline_dir: Optional[Path] = None,
):
    logical_baseline_dir = logical_baseline_dir or baseline_dir
    captured = {}
    for stage in meta.get("stages", []):
        stage_id = str(stage.get("id", ""))
        if stage.get("status") != "approved" or not stage_id:
            continue
        source = artifact_path(root, stage_id)
        if not source.exists():
            raise EnhancementError(f"approved stage {stage_id} is missing {source.name}")
        try:
            computed = stage_content_hash(root, stage_id, source)
        except CompositeHashError as exc:
            raise EnhancementError(f"cannot capture stage {stage_id}: {exc}")
        recorded = stage.get("content_hash")
        if recorded != computed:
            raise EnhancementError(
                f"approved stage {stage_id} has hash drift; run /pm-check and reapprove before enhancement"
            )
        destination = baseline_dir / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source), str(destination))
        captured[stage_id] = {
            "path": source.name,
            "snapshot_path": _relative(root, logical_baseline_dir / source.name),
            "status": "approved",
            "content_hash": computed,
            "approved_at": stage.get("approved_at"),
        }
        if stage_id == "00w" and (root / "00-context" / "manifest.yaml").exists():
            pack_dest = baseline_dir / "00-context"
            shutil.copytree(str(root / "00-context"), str(pack_dest))
            captured[stage_id]["context_pack_snapshot"] = _relative(
                root, logical_baseline_dir / "00-context"
            )
    if not captured:
        raise EnhancementError("no approved artifacts to capture; approve stage 00 first")
    return captured


def _git_value(path: Optional[Path], *args: str) -> Optional[str]:
    if path is None:
        return None
    result = subprocess.run(
        ["git", "-C", str(path), *args], capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _git_visible_paths(path: Path):
    result = subprocess.run(
        [
            "git", "-C", str(path), "ls-files", "-z", "--cached", "--others",
            "--exclude-standard",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    decoded = result.stdout.decode("utf-8", errors="surrogateescape")
    return sorted(item for item in decoded.split("\0") if item)


def _repository_fingerprint(path: Path) -> str:
    """Hash Git-visible worktree bytes without following links or reading .git."""
    relative_paths = _git_visible_paths(path)
    if relative_paths is None:
        relative_paths = []
        for current, directories, files in os.walk(path, followlinks=False):
            directories[:] = sorted(name for name in directories if name != ".git")
            current_path = Path(current)
            for name in sorted(files):
                relative_paths.append((current_path / name).relative_to(path).as_posix())
        relative_paths.sort()

    digest = hashlib.sha256()
    for relative in relative_paths:
        candidate = path / relative
        digest.update(relative.encode("utf-8", errors="surrogateescape"))
        digest.update(b"\0")
        if candidate.is_symlink():
            digest.update(b"L\0")
            digest.update(os.readlink(str(candidate)).encode("utf-8", errors="surrogateescape"))
        elif candidate.is_file():
            digest.update(b"F\0")
            with candidate.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        else:
            digest.update(b"M\0")
        digest.update(b"\0")
    return digest.hexdigest()


def _local_codebase(raw: Optional[str]) -> Optional[Path]:
    if not raw or raw.startswith(("https://", "http://", "git@")):
        return None
    candidate = Path(raw).expanduser().resolve()
    return candidate if candidate.is_dir() else None


def _repository_seed(meta: dict, args) -> dict:
    source = args.codebase or meta.get("codebase_path")
    local = _local_codebase(source)
    if source and not source.startswith(("https://", "http://", "git@")) and local is None:
        raise EnhancementError(f"codebase path is not a readable directory: {source}")
    resolved = _git_value(local, "rev-parse", "HEAD") or meta.get("codebase_ref")
    if local is not None and args.ref:
        requested_sha = _git_value(local, "rev-parse", args.ref)
        if requested_sha is None:
            raise EnhancementError(f"requested ref cannot be resolved read-only: {args.ref}")
        if resolved != requested_sha:
            raise EnhancementError(
                f"requested ref {args.ref} resolves to {requested_sha}, but checkout HEAD is {resolved}; "
                "provide a checkout already pinned to the requested ref"
            )
    porcelain = _git_value(local, "status", "--porcelain", "--untracked-files=all") if local else None
    dirty = bool(porcelain) if porcelain is not None else None
    fingerprint = _repository_fingerprint(local) if local else None
    return {
        "source": source,
        "path": str(local) if local else meta.get("codebase_path"),
        "requested_ref": args.ref,
        "resolved_sha": resolved,
        "scan_start_sha": resolved,
        "scan_end_sha": None,
        "dirty": dirty,
        "non_reproducible_reason": (
            "checkout has uncommitted or untracked files" if dirty else None
        ),
        "porcelain_before": porcelain,
        "porcelain_after": None,
        "fingerprint_algorithm": "sha256(git-visible-path+kind+bytes)",
        "fingerprint_before": fingerprint,
        "fingerprint_after": None,
        "subpath": args.subpath,
    }


def cmd_start(args) -> None:
    root = resolve_project()
    ask = Path(args.ask_file).expanduser().resolve()
    if not ask.is_file():
        raise EnhancementError(f"ask file not found: {ask}")
    ask_hash = _sha256_file(ask)

    with _enhancement_lock(root):
        index = _load_index(root)
        active = index.get("active_cycle")
        if active:
            active_context = _read_yaml(_context_path(root, active), {})
            if active_context.get("ask", {}).get("sha256") == ask_hash:
                print(f"Enhancement {active} is already active for this ask; no action taken.")
                return
            raise EnhancementError(
                f"active enhancement {active} already exists; complete it before starting different work"
            )

        sequence = int(index.get("next_sequence", 1))
        cycle_id = f"EH-{sequence:03d}"
        cycle_dir = _enhancements_dir(root) / cycle_id
        if cycle_dir.exists():
            raise EnhancementError(f"cycle directory already exists: {cycle_id}")
        temp_dir = _enhancements_dir(root) / f".{cycle_id}.tmp-{os.getpid()}"
        temp_dir.mkdir()
        try:
            ask_snapshot = temp_dir / "ask.md"
            shutil.copy2(str(ask), str(ask_snapshot))
            meta = load_meta(root)
            captured = _capture_approved_artifacts(
                root,
                meta,
                temp_dir / "baseline",
                cycle_dir / "baseline",
            )
            prior = index.get("cycles", [])[-1] if index.get("cycles") else None
            started_at = _now()
            context = {
                "schema_version": ENHANCEMENT_SCHEMA_VERSION,
                "id": cycle_id,
                "previous_cycle_id": prior,
                "started_at": started_at,
                "completed_at": None,
                "ask": {
                    "source_path": str(ask),
                    "snapshot_path": f".enhancements/{cycle_id}/ask.md",
                    "sha256": ask_hash,
                },
                "baseline": {
                    "captured_at": started_at,
                    "artifacts": captured,
                },
                "repository": _repository_seed(meta, args),
                "boundary": {
                    "affected_ids": [],
                    "affected_surfaces": [],
                    "non_touch_surfaces": [],
                    "regression_invariants": [],
                    "compatibility_migration": [],
                    "rollout_rollback": [],
                },
                "scan": {
                    "coverage": [],
                    "exclusions": [],
                    "confidence": None,
                },
            }
            _write_yaml_atomic(temp_dir / "context.yaml", context)
            os.replace(str(temp_dir), str(cycle_dir))
        except Exception:
            if temp_dir.exists():
                shutil.rmtree(str(temp_dir))
            raise

        index["active_cycle"] = cycle_id
        index["next_sequence"] = sequence + 1
        index.setdefault("cycles", []).append(cycle_id)
        _write_yaml_atomic(_index_path(root), index)

    try:
        log("enhancement_started", root, None, {
            "cycle_id": cycle_id,
            "previous_cycle_id": prior,
            "ask_sha256": ask_hash,
            "baseline_artifact_ids": list(captured.keys()),
        })
    except Exception as exc:
        print(f"Warning: telemetry logging failed: {exc}")
    print(f"Enhancement {cycle_id} started in the same PM-OS project.")
    print(f"Captured approved baseline stages: {', '.join(captured.keys())}")


def cmd_show(args) -> None:
    root = resolve_project()
    index = _load_index(root)
    active = index.get("active_cycle")
    if not active:
        print("No active enhancement.")
        return
    context = _read_yaml(_context_path(root, active), {})
    if args.json:
        import json
        print(json.dumps(context, ensure_ascii=False, sort_keys=True))
        return
    print(f"Active enhancement: {active}")
    print(f"Started: {context.get('started_at')}")
    print(f"Affected surfaces: {', '.join(context.get('boundary', {}).get('affected_surfaces', [])) or '(not set)'}")


def _active_context(root: Path):
    index = _load_index(root)
    cycle_id = index.get("active_cycle")
    if not cycle_id:
        raise EnhancementError("no active enhancement; run /pm-enhance start first")
    path = _context_path(root, cycle_id)
    context = _read_yaml(path, {})
    if not isinstance(context, dict) or context.get("id") != cycle_id:
        raise EnhancementError(f"active enhancement context is missing or invalid: {cycle_id}")
    if context.get("completed_at"):
        raise EnhancementError(f"enhancement {cycle_id} is already complete and immutable")
    return index, cycle_id, path, context


def _approved_stage_hash(root: Path, meta: dict, stage_id: str) -> str:
    try:
        stage = get_stage(meta, stage_id)
    except KeyError:
        raise EnhancementError(f"required stage {stage_id} is missing")
    if stage.get("status") != "approved":
        raise EnhancementError(f"required stage {stage_id} must be approved")
    path = artifact_path(root, stage_id)
    if not path.exists():
        raise EnhancementError(f"required stage {stage_id} artifact is missing")
    try:
        computed = stage_content_hash(root, stage_id, path)
    except CompositeHashError as exc:
        raise EnhancementError(f"cannot validate stage {stage_id}: {exc}")
    if computed != stage.get("content_hash"):
        raise EnhancementError(f"required stage {stage_id} has hash drift; reapprove it first")
    return computed


def _repository_after(context: dict) -> dict:
    repository = context.get("repository") or {}
    raw_path = repository.get("path")
    local = _local_codebase(raw_path)
    if local is None:
        raise EnhancementError("active enhancement has no prepared readable local codebase")
    current_sha = _git_value(local, "rev-parse", "HEAD")
    current_porcelain = _git_value(local, "status", "--porcelain", "--untracked-files=all")
    current_fingerprint = _repository_fingerprint(local)
    mismatches = []
    if current_sha != repository.get("scan_start_sha"):
        mismatches.append("HEAD SHA")
    if current_porcelain != repository.get("porcelain_before"):
        mismatches.append("Git porcelain state")
    if current_fingerprint != repository.get("fingerprint_before"):
        mismatches.append("worktree fingerprint")
    if mismatches:
        raise EnhancementError(
            "repository changed during the scan (" + ", ".join(mismatches) + "); "
            "explicitly refresh before recording the boundary"
        )
    return {
        "scan_end_sha": current_sha,
        "porcelain_after": current_porcelain,
        "fingerprint_after": current_fingerprint,
    }


def _unique(values: List[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def _build_delta(root: Path, cycle_id: str, context: dict) -> dict:
    try:
        derived = active_enhancement_delta(root, require_approved=False)
    except EnhancementDeltaError as exc:
        raise EnhancementError(str(exc))
    if not derived or derived.get("cycle_id") != cycle_id:
        raise EnhancementError(f"cannot derive active enhancement delta for {cycle_id}")
    changes = derived["changes"]
    declaration_mismatches = [
        {
            "stage": item["stage"], "id": item["id"],
            "computed": item["change_type"], "declared": item.get("declared_change_type"),
        }
        for item in changes
        if item.get("after") is not None
        and not item["id"].startswith("STAGE-")
        and item.get("declared_change_type") != item["change_type"]
    ]

    approved_ids = set((context.get("boundary") or {}).get("affected_ids") or [])
    unexpected = sorted({
        item["id"] for item in changes
        if item["id"].startswith(REQUIREMENT_PREFIXES) and item["id"] not in approved_ids
    })
    return {
        "schema_version": 1,
        "baseline_cycle": cycle_id,
        "baseline_captured_at": (context.get("baseline") or {}).get("captured_at"),
        "changes": changes,
        "unexpected_changed_ids": unexpected,
        "declaration_mismatches": declaration_mismatches,
    }


def cmd_delta(args) -> None:
    root = resolve_project()
    _index, cycle_id, _path, context = _active_context(root)
    data = _build_delta(root, cycle_id, context)
    if args.json:
        import json
        print(json.dumps(data, ensure_ascii=False, sort_keys=True))
        return
    print(f"Enhancement delta: {cycle_id}")
    if not data["changes"]:
        print("No canonical artifact changes detected.")
        return
    for item in data["changes"]:
        print(f"- {item['stage']} {item['id']}: {item['change_type']}")
    if data["unexpected_changed_ids"]:
        print("Unexpected changed requirement IDs: " + ", ".join(data["unexpected_changed_ids"]))
    if data["declaration_mismatches"]:
        print(f"Change-type declaration mismatches: {len(data['declaration_mismatches'])}")


def cmd_set_boundary(args) -> None:
    root = resolve_project()
    with _enhancement_lock(root):
        _index, cycle_id, context_path, context = _active_context(root)
        meta = load_meta(root)
        _approved_stage_hash(root, meta, "00c")
        understanding_hash = _approved_stage_hash(root, meta, "00u")

        blocking_unknowns = _unique(args.blocking_unknown)
        accepted_risks = _unique(args.accepted_risk)
        unaccepted = [unknown for unknown in blocking_unknowns if unknown not in accepted_risks]
        if unaccepted:
            raise EnhancementError(
                "blocking unknown requires an explicit matching --accepted-risk: "
                + "; ".join(unaccepted)
            )
        repository_after = _repository_after(context)

        surfaces = _unique(args.surface)
        invalid = [surface for surface in surfaces if surface not in SURFACES]
        if invalid:
            raise EnhancementError(
                f"invalid affected surface(s): {', '.join(invalid)}; valid: {', '.join(SURFACES)}"
            )
        if not surfaces:
            raise EnhancementError("at least one --surface is required")

        context["boundary"] = {
            "recorded_at": _now(),
            "source_artifact": "00-context-understanding.md",
            "source_hash": understanding_hash,
            "current_behavior": args.current_behavior.strip(),
            "target_behavior": args.target_behavior.strip(),
            "affected_ids": _unique(args.affected_id),
            "affected_surfaces": surfaces,
            "non_touch_surfaces": _unique(args.non_touch),
            "regression_invariants": _unique(args.invariant),
            "success_criteria": _unique(args.success),
            "compatibility_migration": _unique(args.compatibility),
            "rollout": _unique(args.rollout),
            "rollback": _unique(args.rollback),
            "decision_authority": args.authority.strip(),
            "blocking_unknowns": blocking_unknowns,
            "known_unknowns": _unique(args.known_unknown),
            "accepted_risks": accepted_risks,
        }
        context.setdefault("repository", {}).update(repository_after)
        context["scan"] = {
            "coverage": _unique(args.coverage),
            "exclusions": _unique(args.exclusion),
            "confidence": args.confidence,
        }
        _write_yaml_atomic(context_path, context)

    try:
        log("enhancement_boundary_recorded", root, None, {
            "cycle_id": cycle_id,
            "affected_ids": context["boundary"]["affected_ids"],
            "affected_surfaces": context["boundary"]["affected_surfaces"],
            "blocking_unknowns": len(blocking_unknowns),
            "accepted_risks": len(accepted_risks),
        })
    except Exception as exc:
        print(f"Warning: telemetry logging failed: {exc}")
    print(f"Enhancement boundary recorded for {cycle_id}.")


def cmd_refresh(args) -> None:
    """Explicitly repin code evidence and invalidate the old decision boundary."""
    root = resolve_project()
    stale_ids = []
    with _enhancement_lock(root):
        _index, cycle_id, context_path, context = _active_context(root)
        previous_repository = dict(context.get("repository") or {})
        raw_path = previous_repository.get("path")
        if not raw_path:
            raise EnhancementError("active enhancement has no local codebase to refresh")
        seed_args = SimpleNamespace(
            codebase=raw_path,
            ref=args.ref,
            subpath=previous_repository.get("subpath"),
        )
        refreshed = _repository_seed({}, seed_args)
        if refreshed.get("dirty"):
            raise EnhancementError(
                "refusing to refresh from a dirty checkout; commit/stash changes or provide a clean checkout"
            )
        if not refreshed.get("resolved_sha"):
            raise EnhancementError("refreshed checkout does not resolve to a Git commit")

        # Preserve every superseded decision/evidence object inside the active
        # cycle. Frozen artifact baselines are deliberately never replaced.
        context.setdefault("repository_refreshes", []).append({
            "refreshed_at": _now(),
            "previous_repository": previous_repository,
        })
        old_boundary = context.get("boundary") or {}
        if old_boundary.get("recorded_at"):
            context.setdefault("boundary_history", []).append(dict(old_boundary))
        context["repository"] = refreshed
        context["boundary"] = {
            "invalidated_at": _now(),
            "affected_ids": [], "affected_surfaces": [], "non_touch_surfaces": [],
            "regression_invariants": [], "compatibility_migration": [],
            "rollout_rollback": [],
        }
        context["scan"] = {"coverage": [], "exclusions": [], "confidence": None}

        meta = load_meta(root)
        for stage in meta.get("stages", []):
            if stage.get("id") == "00" or stage.get("status") != "approved":
                continue
            stage["status"] = "stale"
            path = artifact_path(root, stage["id"])
            if path.exists():
                update_status(str(path), "stale")
            stale_ids.append(stage["id"])
        _write_yaml_atomic(root / ".meta.yaml", meta)
        _write_yaml_atomic(context_path, context)

    try:
        log("enhancement_repository_refreshed", root, None, {
            "cycle_id": cycle_id,
            "previous_sha": previous_repository.get("scan_start_sha"),
            "refreshed_sha": refreshed.get("scan_start_sha"),
            "stale_stages": stale_ids,
        })
    except Exception as exc:
        print(f"Warning: telemetry logging failed: {exc}")
    print(f"Enhancement {cycle_id} refreshed to {refreshed['scan_start_sha']}.")
    print("Frozen artifact baseline preserved; decision boundary must be rebuilt.")
    if stale_ids:
        print("Stages now stale: " + ", ".join(stale_ids))


def cmd_complete(_args) -> None:
    """Close an active cycle only after the product-of-record is coherent."""
    root = resolve_project()
    with _enhancement_lock(root):
        recovery_index = _load_index(root)
        recovery_cycle = recovery_index.get("active_cycle")
        if recovery_cycle:
            recovery_context = _read_yaml(_context_path(root, recovery_cycle), {})
            if (
                isinstance(recovery_context, dict)
                and recovery_context.get("completed_at")
                and isinstance(recovery_context.get("completion"), dict)
            ):
                # Atomic context write succeeded but the following index write
                # was interrupted. Completed provenance is immutable; retry
                # repairs only its derived active pointer.
                recovery_index["active_cycle"] = None
                _write_yaml_atomic(_index_path(root), recovery_index)
                try:
                    log("enhancement_completion_recovered", root, None, {
                        "cycle_id": recovery_cycle,
                    })
                except Exception as exc:
                    print(f"Warning: telemetry logging failed: {exc}")
                print(f"Enhancement {recovery_cycle} completion recovered; active pointer cleared.")
                return
        index, cycle_id, context_path, context = _active_context(root)
        boundary = context.get("boundary") or {}
        required_boundary = ("recorded_at", "current_behavior", "target_behavior", "affected_surfaces")
        if any(not boundary.get(field) for field in required_boundary):
            raise EnhancementError("cannot complete without a recorded enhancement boundary")

        meta = load_meta(root)
        # E2 updates the entire definition/implementation spine. Stage 09 remains
        # optional, but a present non-pending roadmap must also be approved.
        for stage_id in ("01", "02", "03", "04", "05", "06", "07", "08"):
            _approved_stage_hash(root, meta, stage_id)
        try:
            roadmap = get_stage(meta, "09")
        except KeyError:
            roadmap = None
        if roadmap and roadmap.get("status") != "pending":
            _approved_stage_hash(root, meta, "09")

        delta = _build_delta(root, cycle_id, context)
        if delta["unexpected_changed_ids"]:
            raise EnhancementError(
                "changed requirement IDs fall outside the recorded boundary: "
                + ", ".join(delta["unexpected_changed_ids"])
            )
        if delta["declaration_mismatches"]:
            refs = ", ".join(item["id"] for item in delta["declaration_mismatches"])
            raise EnhancementError("computed and declared change types disagree for: " + refs)
        if (context.get("repository") or {}).get("path"):
            _repository_after(context)

        errors = [issue for issue in check_project(root) if issue.severity == "error"]
        if errors:
            raise EnhancementError(
                "project consistency errors block completion: "
                + ", ".join(sorted({issue.code for issue in errors}))
            )

        completed_at = _now()
        context["completed_at"] = completed_at
        context["completion"] = {
            "delta_change_count": len(delta["changes"]),
            "approved_product_stages": [
                stage["id"] for stage in meta.get("stages", [])
                if stage.get("status") == "approved"
            ],
        }
        index["active_cycle"] = None
        _write_yaml_atomic(context_path, context)
        _write_yaml_atomic(_index_path(root), index)

    try:
        log("enhancement_completed", root, None, {
            "cycle_id": cycle_id,
            "delta_change_count": len(delta["changes"]),
        })
    except Exception as exc:
        print(f"Warning: telemetry logging failed: {exc}")
    print(f"Enhancement {cycle_id} completed; the canonical artifacts remain the product-of-record.")


def main() -> None:
    parser = argparse.ArgumentParser(description="PM-OS E2 enhancement lifecycle mechanics.")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="Start a same-project enhancement and capture baseline.")
    start.add_argument("--ask-file", required=True)
    start.add_argument("--codebase", default=None)
    start.add_argument("--ref", default=None)
    start.add_argument("--subpath", default=None)
    start.set_defaults(func=cmd_start)

    show = sub.add_parser("show", help="Show the active enhancement context.")
    show.add_argument("--json", action="store_true")
    show.set_defaults(func=cmd_show)

    boundary = sub.add_parser("set-boundary", help="Record the approved enhancement boundary.")
    boundary.add_argument("--current-behavior", required=True)
    boundary.add_argument("--target-behavior", required=True)
    boundary.add_argument("--surface", action="append", default=[])
    boundary.add_argument("--affected-id", action="append", default=[])
    boundary.add_argument("--non-touch", action="append", default=[])
    boundary.add_argument("--invariant", action="append", default=[])
    boundary.add_argument("--success", action="append", default=[])
    boundary.add_argument("--compatibility", action="append", default=[])
    boundary.add_argument("--rollout", action="append", default=[])
    boundary.add_argument("--rollback", action="append", default=[])
    boundary.add_argument("--authority", required=True)
    boundary.add_argument("--blocking-unknown", action="append", default=[])
    boundary.add_argument("--known-unknown", action="append", default=[])
    boundary.add_argument("--accepted-risk", action="append", default=[])
    boundary.add_argument("--coverage", action="append", default=[])
    boundary.add_argument("--exclusion", action="append", default=[])
    boundary.add_argument("--confidence", choices=["high", "medium", "low"], default=None)
    boundary.set_defaults(func=cmd_set_boundary)

    delta = sub.add_parser("delta", help="Compute the frozen-baseline versus canonical delta.")
    delta.add_argument("--json", action="store_true")
    delta.set_defaults(func=cmd_delta)

    refresh = sub.add_parser("refresh", help="Explicitly repin repository evidence and stale the pipeline.")
    refresh.add_argument("--ref", required=True)
    refresh.set_defaults(func=cmd_refresh)

    complete = sub.add_parser("complete", help="Close the active same-project enhancement cycle.")
    complete.set_defaults(func=cmd_complete)

    args = parser.parse_args()
    try:
        args.func(args)
    except EnhancementError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
