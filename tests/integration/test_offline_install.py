"""T_offline — offline install via --source and distribution packaging.
Exercises install.sh in offline mode (--source), verifies user-data preservation on
reinstall, and checks that git archive produces a clean zip (no dev files).
See docs/guides/testing.md §T_offline."""
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).parents[2]
INSTALL_SH = REPO_ROOT / "install.sh"

requires_bash = pytest.mark.skipif(
    shutil.which("bash") is None, reason="bash not available"
)
requires_git = pytest.mark.skipif(
    shutil.which("git") is None, reason="git not available"
)


def _run_install(fake_home, source_dir, pm_user, feedback_repo):
    """Run install.sh with --source in an isolated fake HOME and return the CompletedProcess."""
    import sys
    env = dict(os.environ)
    env["HOME"] = str(fake_home)
    # Ensure install.sh finds the same Python as the test runner (not a system 3.9)
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    return subprocess.run(
        [
            "bash", str(INSTALL_SH),
            "--runtime", "codex",
            "--source", str(source_dir),
            "--pm-user", pm_user,
            "--feedback-repo", feedback_repo,
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


@requires_bash
def test_offline_source_install_populates_and_autoverifies(tmp_path):
    """Offline --source install populates ~/.pm-os, syncs skills to ~/.agents/skills, auto-runs
    the verifier, and exits 0 with PASS in output — no git or network required."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()

    res = _run_install(fake_home, REPO_ROOT, "trial", "https://github.com/pingmepi/pm-os-feedback.git")
    assert res.returncode == 0, f"install failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "PASS" in res.stdout, f"verifier PASS not found in output:\n{res.stdout}"

    pm_os = fake_home / ".pm-os"
    assert (pm_os / "lib").is_dir()
    assert (pm_os / "scripts").is_dir()
    assert (pm_os / "hooks").is_dir()
    assert (pm_os / "skills").is_dir()
    assert (pm_os / "VERSION").exists()
    assert (fake_home / ".agents" / "skills").is_dir()


def _run_install_no_user(fake_home, source_dir, feedback_repo):
    """Run install.sh with --source but WITHOUT --pm-user, to test that existing config is reused."""
    import sys
    env = dict(os.environ)
    env["HOME"] = str(fake_home)
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    env.pop("PM_OS_USER", None)  # ensure no env-var override
    return subprocess.run(
        [
            "bash", str(INSTALL_SH),
            "--runtime", "codex",
            "--source", str(source_dir),
            "--feedback-repo", feedback_repo,
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


@requires_bash
def test_offline_reinstall_preserves_user_data(tmp_path):
    """Re-running the offline installer preserves context/ overlay files (rsync/cp exclude)
    and reuses the existing config.yaml pm_user without needing the flag on reinstall."""
    import yaml

    fake_home = tmp_path / "home"
    fake_home.mkdir()

    # First install — set pm_user explicitly
    res = _run_install(fake_home, REPO_ROOT, "trial-user", "https://github.com/pingmepi/pm-os-feedback.git")
    assert res.returncode == 0, res.stdout + res.stderr

    pm_os = fake_home / ".pm-os"

    # Plant a marker file in context/ to verify rsync/cp excludes it
    marker = pm_os / "context" / "my-marker.txt"
    marker.write_text("keep-me")

    # Second install — no --pm-user; pm_os_install.py must read it from existing config
    res2 = _run_install_no_user(fake_home, REPO_ROOT, "https://github.com/pingmepi/pm-os-feedback.git")
    assert res2.returncode == 0, res2.stdout + res2.stderr

    assert marker.read_text() == "keep-me", "context/ marker was overwritten by reinstall"
    cfg_after = yaml.safe_load((pm_os / "config.yaml").read_text())
    assert cfg_after.get("pm_user") == "trial-user", "config.yaml pm_user was not preserved on reinstall"


@requires_git
def test_package_excludes_dev_files(tmp_path):
    """git archive with .gitattributes export-ignore omits CLAUDE.md, AGENTS.md, tests/, and
    .github/ from the distribution zip while retaining install.sh, lib/, and skills/.
    Requires .gitattributes to be committed — this test acts as the contract that it stays wired."""
    zip_path = tmp_path / "pm-os-offline.zip"
    res = subprocess.run(
        ["git", "archive", "--worktree-attributes", "--format=zip", f"--output={zip_path}", "HEAD"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert res.returncode == 0, res.stderr

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()

    # Dev/repo-management files must be absent from the distribution zip
    assert not any("CLAUDE.md" in n for n in names), "CLAUDE.md found in zip"
    assert not any("AGENTS.md" in n for n in names), "AGENTS.md found in zip"
    assert not any(n.startswith("tests/") or "/tests/" in n for n in names), "tests/ found in zip"
    assert not any(n.startswith(".github/") or "/.github/" in n for n in names), ".github/ found in zip"

    # User-facing runtime files must be present
    assert any("install.sh" in n for n in names), "install.sh missing from zip"
    assert any("lib/" in n for n in names), "lib/ missing from zip"
    assert any("skills/" in n for n in names), "skills/ missing from zip"
