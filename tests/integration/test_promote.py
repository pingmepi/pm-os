"""NP3 — `/pm-promote` cost preview + `pm_status` tier counts.

`pm_promote.py` is read-only: it previews the current→target tier and whether the
change is FREE (PRD unapproved), LOW (re-approve PRD only, no approved downstream),
or a CASCADE. The actual re-tag + regeneration is the skill's job, so the state
machine is never touched here. `pm_status` prints the whole-product tier breakdown.
See docs/guides/testing.md."""
import pytest

from helpers import run_script, make_draft

pytestmark = pytest.mark.integration

_TIERED_PRD = """## Functional Requirements
- FR-001 — Complete the work.
## User Stories with Acceptance Criteria
### US-001 — Core login
- **Tier:** mvp
Acceptance: works.
### US-002 — Reports
- **Tier:** v1
Acceptance: later phase.
"""


def test_promote_preview_free_on_draft_prd(pmos, new_project):
    """A tier change on a not-yet-approved PRD cascades nothing → FREE."""
    proj = new_project("promote-free", "A problem")
    make_draft(proj, "03", body=_TIERED_PRD)  # draft, not approved
    res = run_script(pmos, "pm_promote.py", "US-002", "--to", "mvp", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert "v1 → mvp" in res.stdout
    assert "FREE" in res.stdout


def test_promote_preview_low_on_approved_prd_no_downstream(pmos, new_project):
    """Approved PRD with no approved downstream → LOW (re-approve the PRD only)."""
    proj = new_project("promote-low", "A problem")
    make_draft(proj, "03", body=_TIERED_PRD)
    assert run_script(pmos, "pm_approve.py", "03", cwd=proj).returncode == 0
    res = run_script(pmos, "pm_promote.py", "US-002", "--to", "mvp", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert "v1 → mvp" in res.stdout
    assert "LOW" in res.stdout


def test_promote_preview_unknown_requirement_errors(pmos, new_project):
    """A requirement id absent from the PRD errors clearly (and writes nothing)."""
    proj = new_project("promote-unknown", "A problem")
    make_draft(proj, "03", body=_TIERED_PRD)
    res = run_script(pmos, "pm_promote.py", "US-999", "--to", "mvp", cwd=proj)
    assert res.returncode != 0
    assert "not a declared" in (res.stdout + res.stderr)


_PRD_REFERENCES_UNDECLARED_FR = """## Functional Requirements
- FR-001 — Complete the work.
## User Stories with Acceptance Criteria
### US-001 — Core login
- **Tier:** mvp
- **Traceability:** FR-999
Acceptance: works.
"""


def test_promote_preview_rejects_reference_only_id(pmos, new_project):
    """A requirement merely referenced in the PRD (no declaring block) is rejected —
    the traceability index would report a tier, but there is no block to re-tag."""
    proj = new_project("promote-refonly", "A problem")
    make_draft(proj, "03", body=_PRD_REFERENCES_UNDECLARED_FR)
    res = run_script(pmos, "pm_promote.py", "FR-999", "--to", "mvp", cwd=proj)
    assert res.returncode != 0
    assert "not a declared" in (res.stdout + res.stderr)


def test_status_shows_tier_counts(pmos, new_project):
    """pm_status prints a whole-product tier breakdown once a PRD carries tiers."""
    proj = new_project("status-tiers", "A problem")
    make_draft(proj, "03", body=_TIERED_PRD)
    assert run_script(pmos, "pm_approve.py", "03", cwd=proj).returncode == 0
    res = run_script(pmos, "pm_status.py", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert "Tiers:" in res.stdout
    assert "mvp:" in res.stdout and "v1:" in res.stdout
