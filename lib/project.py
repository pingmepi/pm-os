import os
from pathlib import Path
from typing import Optional

import yaml


def resolve_project() -> Path:
    """Walk up from CWD to find a directory containing .meta.yaml."""
    current = Path(os.getcwd()).resolve()
    for directory in [current, *current.parents]:
        if (directory / ".meta.yaml").exists():
            return directory
    raise FileNotFoundError(
        "Not inside a PM-OS project. Run this command from inside ~/pm-projects/<slug>/."
    )


def load_meta(project_root=None) -> dict:
    if project_root is None:
        project_root = resolve_project()
    with open(project_root / ".meta.yaml", "r", encoding="utf-8") as f:
        meta = yaml.safe_load(f)
    # Migrate forward in place; persist only if something changed. Never let a
    # migration failure break a read — the unmigrated dict is still usable.
    try:
        if migrate_meta(meta, project_root):
            save_meta(meta, project_root)
    except Exception:
        pass
    return meta


def save_meta(meta_dict: dict, project_root=None) -> None:
    if project_root is None:
        project_root = resolve_project()
    with open(project_root / ".meta.yaml", "w", encoding="utf-8") as f:
        yaml.dump(meta_dict, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


# Current .meta.yaml shape. Bump (and extend migrate_meta) when the shape
# changes. Independent of config.yaml's own schema_version.
SCHEMA_VERSION = 3

STAGE_NAMES = {
    "00": "business-statement",
    "00c": "codebase-understanding",
    "00w": "context-wiki",
    "00u": "context-understanding",
    "01": "brief",
    "02": "scope",
    "03": "prd",
    "04": "design-spec",
    "05": "prototype-brief",
    "06": "qa-plan",
    "07": "metrics-plan",
    "08": "trd",
    "09": "roadmap",
}

# Stage-00 "understanding" group. The business statement is always present;
# the context wiki + understanding doc exist only when /pm-context-import is
# used. All three are normal gated stages (draft -> approved).
PRE_STAGES = ["00", "00c", "00w", "00u"]

# Stages whose artifact filename doesn't follow the f"{id}-{name}.md" formula.
STAGE_ARTIFACTS = {
    "00c": "00-codebase-understanding.md",
    "00w": "00-context-wiki.md",
    "00u": "00-context-understanding.md",
}

STAGE_ORDER = ["00", "00c", "00w", "00u", "01", "02", "03", "04", "05", "06", "07", "08", "09"]

CORE_STAGE_ORDER = ["01", "02", "03", "04", "05", "06", "07"]

STAGE_DEPENDENCIES = {
    "08": PRE_STAGES + CORE_STAGE_ORDER,
    "09": PRE_STAGES + CORE_STAGE_ORDER,
}

STAGE_OPTIONAL_DEPENDENCIES = {
    "09": ["08"],
}


def artifact_path(project_root: Path, stage_id: str) -> Path:
    if stage_id in STAGE_ARTIFACTS:
        return project_root / STAGE_ARTIFACTS[stage_id]
    name = STAGE_NAMES[stage_id]
    return project_root / f"{stage_id}-{name}.md"


def get_stage(meta: dict, stage_id: str) -> dict:
    for s in meta["stages"]:
        if s["id"] == stage_id:
            return s
    raise KeyError(f"Stage {stage_id} not found in meta")


def upstream_stage_ids(stage_id: str, meta: Optional[dict] = None) -> list[str]:
    if stage_id in STAGE_DEPENDENCIES:
        upstream = list(STAGE_DEPENDENCIES[stage_id])
    else:
        idx = STAGE_ORDER.index(stage_id)
        upstream = STAGE_ORDER[:idx]

    if meta is not None:
        # Only gate on stages this project actually has. The catalog includes the
        # optional context-wiki/understanding stages, but a greenfield project
        # (statement only) must not gate on stages it never created.
        present = {s["id"] for s in meta.get("stages", [])}
        upstream = [u for u in upstream if u in present]
        for optional_stage_id in STAGE_OPTIONAL_DEPENDENCIES.get(stage_id, []):
            try:
                optional_stage = get_stage(meta, optional_stage_id)
            except KeyError:
                continue
            if optional_stage.get("status") == "approved" and optional_stage_id not in upstream:
                upstream.append(optional_stage_id)

    return upstream


def downstream_stage_ids(stage_id: str, meta: Optional[dict] = None) -> list[str]:
    return [sid for sid in STAGE_ORDER if stage_id in upstream_stage_ids(sid, meta)]


def migrate_meta(meta: dict, project_root: Optional[Path] = None) -> bool:
    """Migrate a .meta.yaml dict forward in place. Returns True if it changed.

    Idempotent: a project already at SCHEMA_VERSION with all expected fields is
    left untouched and returns False. Must keep existing on-disk projects working
    (never force re-approval of work the PM already approved).
    """
    if not isinstance(meta, dict):
        return False
    changed = False

    stages = meta.setdefault("stages", [])

    # v2: every stage carries an explicit origin (generated | imported | backfilled).
    for s in stages:
        if "origin" not in s:
            s["origin"] = "generated"
            changed = True

    # v2: the business statement became a tracked, gated stage. Pre-v2 projects
    # wrote 00-business-statement.md straight to approved and never listed it in
    # stages[]; inject it as already-approved so the chain stays intact.
    ids = {s["id"] for s in stages}
    if "00" not in ids:
        content_hash = None
        if project_root is not None:
            bs_path = Path(project_root) / "00-business-statement.md"
            if bs_path.exists():
                try:
                    from hashing import hash_artifact_body
                    content_hash = hash_artifact_body(str(bs_path))
                except Exception:
                    content_hash = None
                # Keep frontmatter in lockstep with meta (two sources of truth).
                try:
                    from frontmatter import read as _fm_read, write as _fm_write
                    fm, body = _fm_read(str(bs_path))
                    if fm.get("content_hash") != content_hash or fm.get("origin") is None:
                        fm["content_hash"] = content_hash
                        fm.setdefault("status", "approved")
                        fm["origin"] = "generated"
                        _fm_write(str(bs_path), fm, body)
                except Exception:
                    pass
        stages.insert(0, {
            "id": "00",
            "name": "business-statement",
            "status": "approved",
            "approved_at": meta.get("created_at"),
            "content_hash": content_hash,
            "upstream_hashes_at_approval": {},
            "regeneration_count": 0,
            "optional": False,
            "origin": "generated",
        })
        changed = True

    # v3: project-level enhancement-mode fields (new_product by default for existing projects).
    if meta.get("schema_version", 1) < 3:
        meta.setdefault("project_type", "new_product")
        meta.setdefault("codebase_path", None)
        meta.setdefault("codebase_ref", None)
        changed = True

    if meta.get("schema_version", 1) < SCHEMA_VERSION:
        meta["schema_version"] = SCHEMA_VERSION
        changed = True

    return changed


# --- Backfill feasibility (the WHY -> WHAT -> HOW gradient) ---------------------
#
# Information flows downstream and gets more concrete, so a downstream artifact
# can only reconstruct an upstream one if it carries that upstream's substance.
# When the PM provides artifacts and PM-OS must reverse-generate the still-missing
# upstream stages below the highest provided one, these maps decide whether each
# gap can be filled faithfully, only lossily, or not at all.
#
#   faithful: the listed downstream stage genuinely carries this stage's content
#   lossy:    derivable but degraded (review carefully)
#   anything else below the gap -> infeasible (PM must supply more)

BACKFILL_FAITHFUL_FROM = {
    "01": ["02", "03"],   # brief: problem/goals live in scope or PRD
    "02": ["03"],         # scope: bounded by the PRD's in/out requirements
    "03": [],             # PRD: no downstream artifact reconstructs it faithfully
    "04": [],
    "05": [],
    "06": [],
}

BACKFILL_LOSSY_FROM = {
    "01": ["04"],
    "02": ["04"],
    "03": ["04"],         # PRD from design: behaviors implied, criteria/NFRs lost
    "04": ["05"],         # design from prototype brief
    "05": ["06"],         # prototype brief from QA plan (weak)
    "06": [],             # QA plan: nothing downstream reconstructs test cases
}


def resolve_backfill(provided_ids):
    """Classify each gap below the highest provided stage as faithful/lossy/infeasible.

    ``provided_ids`` is the set/list of core stage ids (01-07) the PM supplied as
    authored artifacts. Returns an ordered list of dicts: {"stage", "verdict",
    "derived_from"}, verdict in {"faithful", "lossy", "infeasible"}.

    Only artifacts the PM actually *provided* count as evidence — a reconstruction
    is never chained through another reconstructed (backfilled) artifact, because
    deriving a PRD from a design that was itself derived from a QA plan compounds
    invention at every hop. The faithful/lossy maps already give each gap a direct
    provided source wherever one is legitimately reachable.
    """
    provided = {sid for sid in provided_ids if sid in CORE_STAGE_ORDER}
    if not provided:
        return []
    highest_idx = max(CORE_STAGE_ORDER.index(s) for s in provided)
    gaps = [s for s in CORE_STAGE_ORDER[:highest_idx] if s not in provided]

    out = []
    for gap in gaps:
        faithful_src = [s for s in BACKFILL_FAITHFUL_FROM.get(gap, []) if s in provided]
        lossy_src = [s for s in BACKFILL_LOSSY_FROM.get(gap, []) if s in provided]
        if faithful_src:
            out.append({"stage": gap, "verdict": "faithful", "derived_from": faithful_src[0]})
        elif lossy_src:
            out.append({"stage": gap, "verdict": "lossy", "derived_from": lossy_src[0]})
        else:
            out.append({"stage": gap, "verdict": "infeasible", "derived_from": None})
    return out
