"""PM-OS test harness.

Builds a fully isolated PM-OS install in a temp directory and points every
home-derived path at it, so the suite never reads or writes the real
``~/.pm-os``, ``~/.claude``, ``~/.agents``, ``~/pm-projects``, or the real
feedback repo.

Two isolation mechanisms, because PM-OS code resolves home two ways:
- **Subprocess (integration):** scripts/hooks do ``Path.home()/".pm-os"`` at
  runtime, so we run them with ``env`` where ``HOME`` points into the temp tree.
- **In-process (unit):** lib modules bake some paths at import (``config.CONFIG_PATH``,
  ``git_sync.CACHE_DIR``, ``context.PM_OS_DIR``). The ``pmos`` fixture monkeypatches
  those module constants to the temp install for any already/loaded module.
"""
from __future__ import annotations

import importlib
import os
import shutil
import site
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
LIB_DIR = REPO_ROOT / "lib"
# Captured against the REAL home, before any HOME monkeypatch. We re-add this to
# the subprocess PYTHONPATH so relocating HOME doesn't hide runtime deps
# (pyyaml/jinja2) that may live in the user site-packages.
_REAL_USER_SITE = site.getusersitepackages()
# Copied verbatim into the temp install so subprocess runs exercise the working copy.
# `templates/` is required by html_render (resolved as ~/.pm-os/templates).
INSTALL_DIRS = ["lib", "scripts", "hooks", "skills", "context.example", "templates"]

# Make lib importable for in-process unit tests.
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))


def _build_install(home: Path) -> SimpleNamespace:
    install = home / ".pm-os"
    install.mkdir(parents=True)
    for d in INSTALL_DIRS:
        src = REPO_ROOT / d
        if src.is_dir():
            shutil.copytree(src, install / d)
    version = REPO_ROOT / "VERSION"
    (install / "VERSION").write_text(version.read_text() if version.exists() else "0.0.0-test")

    projects = home / "pm-projects"
    projects.mkdir()
    claude = home / ".claude"
    (claude / "skills").mkdir(parents=True)
    codex = home / ".agents" / "skills"
    codex.mkdir(parents=True)

    feedback = home / "feedback.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(feedback)],
                   check=True, capture_output=True)

    (install / "config.yaml").write_text(
        "schema_version: 1\n"
        "pm_user: tester\n"
        f"feedback_repo: {feedback}\n"
        f"projects_dir: {projects}\n"
        "pm_os_version: 0.0.0-test\n"
        "default_model_tier: standard\n"
        "deep_reasoning_stages: ['00w', '00u', '03', '04', '06', '08', '09']\n",
        encoding="utf-8",
    )
    return SimpleNamespace(
        home=home, install=install, projects=projects,
        claude=claude, codex=codex, feedback=feedback,
    )


@pytest.fixture
def pmos(tmp_path, monkeypatch):
    """Isolated PM-OS install + environment. The backbone fixture for the suite."""
    home = tmp_path / "home"
    h = _build_install(home)

    # Inherit the parent env (keeps PATH + interpreter site config), then override
    # only the isolation keys. PYTHONPATH gets the temp install's lib first, plus
    # the real user site-packages so relocating HOME doesn't hide runtime deps.
    pythonpath = os.pathsep.join(
        p for p in [str(h.install / "lib"), _REAL_USER_SITE, os.environ.get("PYTHONPATH", "")] if p
    )
    env = dict(os.environ)
    env.update({
        "HOME": str(home),
        "PM_OS_DIR": str(h.install),
        "CLAUDE_CONFIG_DIR": str(h.claude),
        "CODEX_SKILLS_DIR": str(h.codex),
        "PM_OS_PROJECTS_DIR": str(h.projects),
        "PM_OS_USER": "tester",
        "PM_OS_FEEDBACK_REPO": str(h.feedback),
        "PYTHONPATH": pythonpath,
        "GIT_AUTHOR_NAME": "tester", "GIT_AUTHOR_EMAIL": "tester@example.com",
        "GIT_COMMITTER_NAME": "tester", "GIT_COMMITTER_EMAIL": "tester@example.com",
    })
    h.env = env
    for key in ("HOME", "PM_OS_DIR", "CLAUDE_CONFIG_DIR", "CODEX_SKILLS_DIR",
                "PM_OS_PROJECTS_DIR", "PM_OS_USER", "PM_OS_FEEDBACK_REPO"):
        monkeypatch.setenv(key, env[key])

    # Repoint in-process lib module constants at the temp install (for unit tests).
    _repoint_lib_modules(h, monkeypatch)
    return h


def _repoint_lib_modules(h: SimpleNamespace, monkeypatch):
    """Monkeypatch home-derived constants in already-importable lib modules."""
    import config
    import git_sync
    importlib.reload(config)
    importlib.reload(git_sync)
    monkeypatch.setattr(config, "CONFIG_PATH", h.install / "config.yaml", raising=False)
    config._config_cache = None  # drop any cached config
    monkeypatch.setattr(git_sync, "CACHE_DIR", h.home / ".pm-os-feedback-cache", raising=False)

    import context
    importlib.reload(context)
    monkeypatch.setattr(context, "PM_OS_DIR", h.install, raising=False)
    monkeypatch.setattr(context, "CONTEXT_DIR", h.install / "context", raising=False)
    monkeypatch.setattr(context, "CONTEXT_SEED_DIR", h.install / "context.example", raising=False)


@pytest.fixture
def new_project(pmos):
    """Factory: scaffold a scratch project via the real pm_new.py, return its path."""
    from helpers import run_script

    def _make(slug: str = "demo", statement: str = "Test problem", genai: bool = False):
        flag = "--genai" if genai else "--no-genai"
        res = run_script(pmos, "pm_new.py", slug, statement, flag)
        assert res.returncode == 0, f"pm_new failed: {res.stdout}\n{res.stderr}"
        return pmos.projects / slug

    return _make


def requires_feature(name: str):
    """Skip-marker for planned-but-unbuilt capabilities (see test-plan §18).

    Lets reserved future-phase tests be committed now and flip live when the
    capability ships. Extend FEATURES as phases land.
    """
    FEATURES = {
        # "enhancement_mode": (REPO_ROOT / "skills" / "pm-stage-00-understand").exists(),
    }
    return pytest.mark.skipif(not FEATURES.get(name, False),
                              reason=f"feature '{name}' not built yet")
