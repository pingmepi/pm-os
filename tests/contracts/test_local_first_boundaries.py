"""T8 — local-first & security boundaries: read-only commands stay local, source registration
can't escape the project, and the test fixtures embed no secrets or real user paths.
See docs/guides/testing.md §5 (T8)."""
import re

import pytest

from helpers import REPO_ROOT, run_script

pytestmark = pytest.mark.contract


def test_readonly_commands_do_not_sync():
    """pm_status and pm_share are pure local reads — they must not import git_sync or push
    anywhere (only approval/feedback/explicit sync touch the network)."""
    for script in ("pm_status.py", "pm_share.py"):
        src = (REPO_ROOT / "scripts" / script).read_text()
        assert "git_sync" not in src, f"{script} must not import git_sync"
        assert "push" not in src.lower(), f"{script} must not push"


@pytest.mark.integration
def test_source_registration_stays_inside_project(pmos, new_project):
    """A registered source is snapshotted under the project's .history/ — provenance never
    writes outside the project tree."""
    proj = new_project("boundary", "p")
    run_script(pmos, "pm_approve.py", "00", cwd=proj)
    (proj / "src.md").write_text("# Source\nbody\n", encoding="utf-8")
    res = run_script(pmos, "pm_context_import.py", "register", "src.md", "--type", "research", cwd=proj)
    assert res.returncode == 0, res.stderr
    snaps = list((proj / ".history").glob("source-*"))
    assert snaps, "source snapshot should exist under .history"
    for s in snaps:
        assert str(proj) in str(s.resolve()), "snapshot must live inside the project"


def test_fixtures_have_no_secrets_or_hardcoded_home():
    """The test sources embed no tokens and no hardcoded absolute home paths (isolation comes
    from fixtures/tmp_path). The home marker is built dynamically so this checker file doesn't
    trip on its own source."""
    secret = re.compile(r"ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}")
    home_marker = "/" + "Users" + "/"  # avoid embedding the literal here
    for py in (REPO_ROOT / "tests").rglob("*.py"):
        text = py.read_text()
        assert not secret.search(text), f"{py.name}: looks like an embedded secret"
        assert home_marker not in text, f"{py.name}: hardcoded absolute home path"
