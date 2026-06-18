"""T9 — CI contract: the suite runs automatically. Guards that the workflow stays wired to
pytest so the suite can't quietly stop running in CI. See docs/TESTING.md §5 (T9)."""
import pytest

from helpers import REPO_ROOT

pytestmark = pytest.mark.contract


def test_ci_workflow_runs_pytest():
    """A GitHub Actions workflow exists and invokes pytest on push/PR."""
    wf = REPO_ROOT / ".github" / "workflows" / "tests.yml"
    assert wf.exists(), "missing .github/workflows/tests.yml"
    text = wf.read_text()
    assert "pytest" in text
    assert "pull_request" in text
    # runtime deps the suite needs are installed in CI
    for dep in ("pyyaml", "jinja2", "gitpython"):
        assert dep in text, f"CI must install {dep}"
