"""T0 smoke tests — prove the harness builds an isolated install and runs in it.

If these pass, fixtures work and nothing touches the real user paths.
"""
import os
from pathlib import Path

import pytest

from helpers import run_script


@pytest.mark.integration
def test_temp_install_is_isolated(pmos):
    # The install is a faithful copy under the pytest tmp tree, not the real ~/.pm-os.
    assert pmos.install.is_dir()
    assert str(pmos.home) in str(pmos.install)
    assert "pytest-" in str(pmos.install)  # lives under the pytest tmp sandbox
    for d in ("lib", "scripts", "hooks", "skills", "context.example"):
        assert (pmos.install / d).is_dir(), f"missing {d} in temp install"
    assert (pmos.install / "config.yaml").exists()
    # env points home into the sandbox
    assert pmos.env["HOME"] == str(pmos.home)


@pytest.mark.integration
def test_pm_new_scaffolds_only_in_temp(pmos, new_project):
    proj = new_project("smoke-demo", "A smoke test problem")
    # Project landed in the temp projects dir...
    assert proj == pmos.projects / "smoke-demo"
    assert (proj / ".meta.yaml").exists()
    assert (proj / "00-business-statement.md").exists()
    assert (proj / "telemetry.jsonl").exists()
    assert (proj / ".history").is_dir()
    # ...and the temp projects dir is inside the sandbox, never the real ~/pm-projects.
    assert str(pmos.home) in str(pmos.projects)


@pytest.mark.unit
def test_lib_imports_resolve_to_repo():
    import project
    import telemetry
    import context
    assert hasattr(project, "STAGE_ORDER")
    assert hasattr(telemetry, "verify_chain")
    assert hasattr(context, "render_context")


@pytest.mark.unit
def test_context_module_repointed_to_temp_install(pmos):
    import context
    # The repoint fixture must aim context at the temp install, not real home.
    assert context.PM_OS_DIR == pmos.install
    assert context.CONTEXT_SEED_DIR == pmos.install / "context.example"
    assert str(pmos.home) in str(context.CONTEXT_DIR)
