"""E3 — /pm-status surfaces the count of open known-unknowns.

Resolved bullets (carrying a [resolved: ...] marker) are excluded from the count,
so the PM can see at a glance how many gaps a re-run interview could still close.
"""
import pytest

from helpers import run_script

pytestmark = pytest.mark.integration


def _write_known_unknowns(proj, body):
    ku = proj / "00-context"
    ku.mkdir(exist_ok=True)
    (ku / "known-unknowns.md").write_text(body, encoding="utf-8")


def test_status_shows_open_known_unknowns_count(pmos, new_project):
    """Two open + one resolved bullet → 'Known unknowns: 2 open'."""
    proj = new_project()
    _write_known_unknowns(proj, "\n".join([
        "# Known unknowns",
        "",
        "- Who is the primary user? (source: src_003)",
        "- What is the success metric? (source: src_003)",
        "- What is out of scope? (source: src_001) [resolved: src_005 2026-01-01]",
    ]) + "\n")
    res = run_script(pmos, "pm_status.py", cwd=proj)
    assert res.returncode == 0, f"{res.stdout}\n{res.stderr}"
    assert "Known unknowns: 2 open" in res.stdout


def test_status_no_known_unknowns_line_when_none(pmos, new_project):
    """No known-unknowns file → the line still prints, as 'Known unknowns: 0 open'."""
    proj = new_project()
    res = run_script(pmos, "pm_status.py", cwd=proj)
    assert res.returncode == 0, f"{res.stdout}\n{res.stderr}"
    assert "Known unknowns: 0 open" in res.stdout
