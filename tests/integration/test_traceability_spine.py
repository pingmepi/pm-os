"""T2/Phase 3.5 — the traceability spine end to end through the real approval flow.

Approving the PRD (03) and QA plan (06) drives hooks/post-approve.py to (re)build
the flat `.traceability.yaml` sibling dotfile from the artifact bodies, and the
`pm_trace.py` resolver answers coverage queries against it — all locally, no network.
See docs/guides/testing.md §5 (T2, traceability spine)."""
import pytest

from helpers import run_script, make_draft

pytestmark = pytest.mark.integration


_PRD_BODY = """## Functional Requirements
- FR-001 — Complete the work.
- FR-002 — Audit the work.
## User Stories with Acceptance Criteria
### US-001 — Story
ok
"""

_QA_BODY = """## Functional Test Cases
### TC-001 — Primary (covers US-001, FR-001)
steps
### TC-002 — Audit (covers FR-002)
steps
"""


def _approve_prd_and_qa(pmos, proj):
    make_draft(proj, "03", body=_PRD_BODY)
    assert run_script(pmos, "pm_approve.py", "03", cwd=proj).returncode == 0
    make_draft(proj, "06", body=_QA_BODY)
    assert run_script(pmos, "pm_approve.py", "06", cwd=proj).returncode == 0


def test_approval_builds_traceability_dotfile(pmos, new_project):
    """Approving 03 then 06 writes a flat .traceability.yaml at the project root that
    links the PRD requirement ids to the QA TC-### scenarios."""
    proj = new_project("trace-e2e", "A problem")
    _approve_prd_and_qa(pmos, proj)
    path = proj / ".traceability.yaml"
    assert path.exists(), "approval should build .traceability.yaml"

    import yaml
    data = yaml.safe_load(path.read_text())
    assert set(data["requirements"]) == {"FR-001", "FR-002", "US-001"}
    assert set(data["test_cases"]) == {"TC-001", "TC-002"}
    assert data["requirements"]["FR-001"]["test_cases"] == ["TC-001"]


def test_bold_wrapped_bullet_tc_ids_still_populate_the_spine(pmos, new_project):
    """Backlog IMP-007: a QA plan that formats scenarios as bold-wrapped bullets
    (`- **TC-001:** ...`) must pass stage-06 validation AND populate
    .traceability.yaml — previously the loose validator regex accepted this style
    while the strict splitter (shared with build_index) returned nothing for it,
    so approval succeeded but the spine silently stayed empty."""
    proj = new_project("trace-bold", "A problem")
    make_draft(proj, "03", body=_PRD_BODY)
    assert run_script(pmos, "pm_approve.py", "03", cwd=proj).returncode == 0

    qa_body = """## Functional Test Cases
- **TC-001:** Primary scenario, covers US-001, FR-001.
- **TC-002:** Audit scenario, covers FR-002.
"""
    make_draft(proj, "06", body=qa_body)
    res = run_script(pmos, "pm_approve.py", "06", cwd=proj)
    assert res.returncode == 0, res.stderr

    import yaml
    data = yaml.safe_load((proj / ".traceability.yaml").read_text())
    assert set(data["test_cases"]) == {"TC-001", "TC-002"}, "spine must not be empty"


def test_resolver_answers_coverage_query(pmos, new_project):
    """pm_trace.py resolves which scenarios cover a requirement and which requirements
    are uncovered, locally from the approved artifacts."""
    proj = new_project("trace-query", "A problem")
    _approve_prd_and_qa(pmos, proj)

    res = run_script(pmos, "pm_trace.py", "requirement", "FR-001", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert "TC-001" in res.stdout

    res = run_script(pmos, "pm_trace.py", "scenario", "TC-002", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert "FR-002" in res.stdout


def test_rebuild_subcommand_regenerates_index(pmos, new_project):
    """pm_trace.py rebuild regenerates the dotfile on demand (it is a derived index,
    safe to delete and rebuild)."""
    proj = new_project("trace-rebuild", "A problem")
    _approve_prd_and_qa(pmos, proj)
    (proj / ".traceability.yaml").unlink()
    res = run_script(pmos, "pm_trace.py", "rebuild", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert (proj / ".traceability.yaml").exists()
    assert "requirement" in res.stdout.lower()
