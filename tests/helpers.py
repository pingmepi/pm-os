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
