"""Shared test helpers — subprocess runners and small artifact builders.

Everything here operates against the *isolated temp install* built by the
`pmos` fixture (see conftest.py). Nothing reaches the real ~/.pm-os.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def run_script(pmos, script: str, *args: str, cwd: Path | None = None, stdin: str | None = None):
    """Run scripts/<script> from the temp install with the isolated env.

    Returns the CompletedProcess (capture_output, text). `cwd` defaults to the
    projects dir; pass a project path for commands that resolve_project().
    """
    script_path = pmos.install / "scripts" / script
    return subprocess.run(
        ["python3", str(script_path), *args],
        cwd=str(cwd or pmos.projects),
        env=pmos.env,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=60,
    )


def run_hook(pmos, hook: str, stage: str, cwd: Path, *, extra_env: dict | None = None, stdin: str | None = ""):
    """Run hooks/<hook> the way a skill does: PM_OS_STAGE=NN python3 ~/.pm-os/hooks/<hook>."""
    env = dict(pmos.env)
    env["PM_OS_STAGE"] = stage
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["python3", str(pmos.install / "hooks" / hook)],
        cwd=str(cwd),
        env=env,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=60,
    )


def write_artifact(path: Path, *, stage: str, project: str, status: str = "draft",
                   body: str = "Body line.\n", **frontmatter) -> Path:
    """Write a minimal stage artifact (frontmatter + body) for tests."""
    fm = {
        "stage": stage, "project": project, "status": status,
        "approved_at": None, "approved_by": None, "content_hash": None,
        "generated_hash": "test", "pm_os_version": "0.0.0-test",
        "genai_flag": False, "generation_notes": [],
    }
    fm.update(frontmatter)
    lines = "\n".join(f"{k}: {v if v is not None else 'null'}" for k, v in fm.items())
    path.write_text(f"---\n{lines}\n---\n{body}", encoding="utf-8")
    return path


# --- in-process state helpers (lib is importable; these touch only the project tree) ---

def make_draft(proj: Path, stage_id: str, body: str = "Draft body.\n") -> Path:
    """Simulate a skill generating a stage: write a draft artifact and set BOTH the meta
    stage entry and frontmatter to 'draft', so it can then be approved by pm_approve.py."""
    import project
    import frontmatter as fm_mod

    apath = project.artifact_path(proj, stage_id)
    fm_mod.write(str(apath), {
        "stage": f"{stage_id}-{project.STAGE_NAMES[stage_id]}", "project": proj.name,
        "status": "draft", "approved_at": None, "approved_by": None,
        "content_hash": None, "generated_hash": "gen", "pm_os_version": "0.0.0-test",
        "genai_flag": False, "generation_notes": [],
    }, body)
    meta = project.load_meta(proj)
    project.get_stage(meta, stage_id)["status"] = "draft"
    project.save_meta(meta, proj)
    return apath


def stage_status(proj: Path, stage_id: str) -> str:
    """Read a stage's status from .meta.yaml."""
    import project
    return project.get_stage(project.load_meta(proj), stage_id)["status"]


def read_events(proj: Path) -> list:
    """Parse a project's telemetry.jsonl into a list of event dicts."""
    import json
    p = proj / "telemetry.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def event_types(proj: Path) -> list:
    """The ordered list of telemetry event_type values for a project."""
    return [e["event_type"] for e in read_events(proj)]
