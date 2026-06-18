"""T4 — install / verify / update runtime parity. Exercises the real scripts against the
isolated temp install. See docs/TESTING.md §5 (T4)."""
import importlib
import subprocess
import sys

import pytest

import yaml

pytestmark = pytest.mark.integration


def _run(pmos, script, *args, env=None, stdin=""):
    return subprocess.run(
        ["python3", str(pmos.install / "scripts" / script), *args],
        cwd=str(pmos.projects), env=env or pmos.env, input=stdin,
        capture_output=True, text=True, timeout=60,
    )


# --- pm_os_install ---

def test_install_writes_config_with_model_policy(pmos):
    """A non-interactive install writes config.yaml with the supplied values and the model
    policy fields (default tier + deep-reasoning stages)."""
    (pmos.install / "config.yaml").unlink()  # fresh install
    res = _run(pmos, "pm_os_install.py",
               "--pm-user", "alice", "--feedback-repo", str(pmos.feedback),
               "--projects-dir", str(pmos.projects))
    assert res.returncode == 0, res.stdout + res.stderr
    cfg = yaml.safe_load((pmos.install / "config.yaml").read_text())
    assert cfg["pm_user"] == "alice"
    assert cfg["default_model_tier"] == "standard"
    assert cfg["deep_reasoning_stages"] == ["00w", "00u", "03", "04", "06", "08", "09"]


def test_install_missing_pm_user_fails_non_interactive(pmos):
    """With no pm_user available (no arg, no env, no existing config) a non-interactive install
    fails clearly rather than hanging on a prompt."""
    (pmos.install / "config.yaml").unlink()
    env = dict(pmos.env)
    env.pop("PM_OS_USER", None)
    res = _run(pmos, "pm_os_install.py",
               "--feedback-repo", str(pmos.feedback), "--projects-dir", str(pmos.projects),
               env=env)
    assert res.returncode != 0


def test_install_seeds_context_overlay(pmos):
    """Install seeds the live context/ overlay from context.example/ (so the PM has an editable
    pack), without overwriting an existing one."""
    res = _run(pmos, "pm_os_install.py", "--reconfigure",
               "--pm-user", "tester", "--feedback-repo", str(pmos.feedback),
               "--projects-dir", str(pmos.projects))
    assert res.returncode == 0, res.stdout + res.stderr
    assert (pmos.install / "context" / "context.yaml").exists()


# --- pm_os_verify ---

def _sync_skills_to_claude(pmos):
    """Mirror install.sh's skill sync so the runtime looks fully installed for verify."""
    import shutil
    dest = pmos.claude / "skills"
    for sd in (pmos.install / "skills").iterdir():
        if sd.is_dir():
            shutil.copytree(sd, dest / sd.name, dirs_exist_ok=True)


def test_verify_passes_on_healthy_install(pmos):
    """The verifier passes against a complete install for claude (install built + skills synced
    to the runtime dir)."""
    _sync_skills_to_claude(pmos)
    res = _run(pmos, "pm_os_verify.py", "--runtime", "claude")
    assert res.returncode == 0, res.stdout + res.stderr
    assert "PASS" in res.stdout


def test_verify_fails_when_a_hook_is_missing(pmos):
    """Removing a gate hook makes the verifier fail — it actually checks install integrity."""
    (pmos.install / "hooks" / "pre-stage.py").unlink()
    res = _run(pmos, "pm_os_verify.py", "--runtime", "claude")
    assert res.returncode != 0
    assert "FAIL" in res.stdout


def test_verify_fails_on_missing_config(pmos):
    """A missing config.yaml fails verification."""
    (pmos.install / "config.yaml").unlink()
    res = _run(pmos, "pm_os_verify.py", "--runtime", "claude")
    assert res.returncode != 0


# --- pm_os_update (arg validation + sync parity; the git fast-forward needs a remote, out of scope) ---

def test_update_requires_runtime(pmos):
    """pm_os_update refuses to run without --runtime (it must know where to sync)."""
    res = _run(pmos, "pm_os_update.py")
    assert res.returncode != 0


def test_update_rejects_invalid_runtime(pmos):
    """An unsupported --runtime value is rejected."""
    res = _run(pmos, "pm_os_update.py", "--runtime", "emacs")
    assert res.returncode != 0


def test_sync_parity_claude_gets_hooks_codex_does_not(pmos):
    """Runtime sync parity: Claude receives skills AND hooks; Codex receives skills only
    (Codex has no native hooks). Tested via the updater's sync functions directly."""
    sys.path.insert(0, str(pmos.install / "scripts"))
    import pm_os_update as up
    importlib.reload(up)  # pick up the temp-install env constants

    up.sync_to_claude()
    assert (pmos.claude / "skills" / "pm-new").is_dir()
    assert (pmos.claude / "hooks" / "pre-stage.py").exists()

    up.sync_to_codex()
    assert (pmos.codex / "pm-new").is_dir(), "Codex should receive skills"
    assert not (pmos.codex / "hooks").exists(), "Codex must not receive hooks"
