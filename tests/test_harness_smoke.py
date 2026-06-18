"""T0 smoke tests — prove the harness builds an isolated install and runs in it.

If these pass, the fixtures work and nothing in the suite touches real user paths.
See docs/TESTING.md §5 (T0).
"""
from pathlib import Path

import pytest

from helpers import run_script  # noqa: F401  (kept for parity with other suites)


@pytest.mark.integration
def test_temp_install_is_isolated(pmos):
    """The temp install is a faithful copy under the pytest sandbox, not the real
    ~/.pm-os, and contains the dirs scripts/hooks/lib expect plus config.yaml."""
    assert pmos.install.is_dir()
    assert str(pmos.home) in str(pmos.install)
    assert "pytest-" in str(pmos.install)  # lives under the pytest tmp sandbox
    for d in ("lib", "scripts", "hooks", "skills", "context.example"):
        assert (pmos.install / d).is_dir(), f"missing {d} in temp install"
    assert (pmos.install / "config.yaml").exists()
    assert pmos.env["HOME"] == str(pmos.home)


@pytest.mark.integration
def test_pm_new_scaffolds_only_in_temp(pmos, new_project):
    """pm_new.py scaffolds a complete project (meta, statement, telemetry, .history)
    strictly inside the temp projects dir — the core isolation guarantee end to end."""
    proj = new_project("smoke-demo", "A smoke test problem")
    assert proj == pmos.projects / "smoke-demo"
    assert (proj / ".meta.yaml").exists()
    assert (proj / "00-business-statement.md").exists()
    assert (proj / "telemetry.jsonl").exists()
    assert (proj / ".history").is_dir()
    assert str(pmos.home) in str(pmos.projects)


@pytest.mark.unit
def test_lib_imports_resolve_to_repo():
    """lib/ modules import from the working copy and expose expected symbols."""
    import project
    import telemetry
    import context
    assert hasattr(project, "STAGE_ORDER")
    assert hasattr(telemetry, "verify_chain")
    assert hasattr(context, "render_context")


@pytest.mark.unit
def test_context_module_repointed_to_temp_install(pmos):
    """The fixture's in-process repoint aims context at the temp install (so unit
    tests of context never read the real ~/.pm-os/context)."""
    import context
    assert context.PM_OS_DIR == pmos.install
    assert context.CONTEXT_SEED_DIR == pmos.install / "context.example"
    assert str(pmos.home) in str(context.CONTEXT_DIR)
