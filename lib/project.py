import os
from pathlib import Path

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
        return yaml.safe_load(f)


def save_meta(meta_dict: dict, project_root=None) -> None:
    if project_root is None:
        project_root = resolve_project()
    with open(project_root / ".meta.yaml", "w", encoding="utf-8") as f:
        yaml.dump(meta_dict, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


STAGE_NAMES = {
    "01": "brief",
    "02": "scope",
    "03": "prd",
    "04": "design-spec",
    "05": "prototype-brief",
    "06": "qa-plan",
    "07": "metrics-plan",
}

STAGE_ORDER = ["01", "02", "03", "04", "05", "06", "07"]


def artifact_path(project_root: Path, stage_id: str) -> Path:
    name = STAGE_NAMES[stage_id]
    return project_root / f"{stage_id}-{name}.md"


def get_stage(meta: dict, stage_id: str) -> dict:
    for s in meta["stages"]:
        if s["id"] == stage_id:
            return s
    raise KeyError(f"Stage {stage_id} not found in meta")


def upstream_stage_ids(stage_id: str) -> list[str]:
    idx = STAGE_ORDER.index(stage_id)
    return STAGE_ORDER[:idx]
