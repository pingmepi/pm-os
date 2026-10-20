"""T2 — Windows bundle (backlog #59–#63): console output that survives a cp1252
pipe, handoff filenames short enough for every filesystem, finishing a stage
written outside its skill, and central-sync health in /pm-status.
See docs/guides/testing.md §5 (T2)."""
import json
import subprocess
import sys

import pytest

from helpers import run_script, make_draft, stage_status, read_events

pytestmark = pytest.mark.integration


def test_verify_output_survives_a_cp1252_pipe(pmos):
    """Backlog #60. With output piped and no UTF-8 override (an agent on stock
    Windows Python, where the pipe defaults to cp1252), pm_os_verify prints its ✓
    marks instead of dying with UnicodeEncodeError. Off Windows this always held."""
    env = {k: v for k, v in pmos.env.items()
           if k not in ("PYTHONIOENCODING", "PYTHONUTF8", "PYTHONLEGACYWINDOWSSTDIO")}
    res = subprocess.run([sys.executable, str(pmos.install / "scripts" / "pm_os_verify.py"),
                          "--runtime", "claude"],
                         cwd=str(pmos.projects), env=env, capture_output=True, timeout=180)
    out = res.stdout.decode("utf-8", errors="strict")
    err = res.stderr.decode("utf-8", errors="replace")
    assert "UnicodeEncodeError" not in err, err
    assert "✓" in out


_LONG_TITLE = ("The traceability gate verifies that every generated statement in the brief, "
               "the scope and the PRD cites at least one approved source claim and blocks "
               "approval when any statement is unsupported or contradicts the evidence ledger")

_PRD = f"""## Product Epics
### EPIC-001 — Traceability
**Outcome:** Every statement is sourced.
**Scope:** Gate.
**Success signal:** No unsupported statements at approval.
## User Journeys
### UJ-001 — Approve a sourced brief
Traceability: US-001.
## User Stories with Acceptance Criteria
### US-001 — {_LONG_TITLE}
Priority: Must
Epic: EPIC-001
As a PM, I want unsupported statements blocked, so that approvals are trustworthy.
Traceability: UJ-001, FR-001.
## Functional Requirements
FR-001 — {_LONG_TITLE}
Priority: Must
Epic: EPIC-001
## Non-Functional Requirements
Performance: the gate runs in under a second.
"""


def test_package_filenames_are_capped_and_links_still_resolve(pmos, new_project):
    """Backlog #59. A sentence-length story/requirement title used to become a ~250+
    character filename, beyond Windows' path limit and the 255-byte filename limit
    elsewhere, so the package build crashed. Slugs are now capped at a word boundary;
    filenames stay id-first and every story link to a requirement still resolves."""
    proj = new_project("long-titles", "A problem")
    run_script(pmos, "pm_approve.py", "00", cwd=proj)
    for stage, body in (("01", "## Target User\nPMs.\n"), ("02", "## MVP Boundary\nGate only.\n"),
                        ("03", _PRD)):
        make_draft(proj, stage, body=body)
        assert run_script(pmos, "pm_approve.py", stage, cwd=proj).returncode == 0

    res = run_script(pmos, "pm_share.py", "--package", cwd=proj)
    assert res.returncode == 0, res.stdout + res.stderr
    dev = proj / "handoff" / "dev"
    stories = list((dev / "stories").glob("US-001-*.md"))
    reqs = list((dev / "requirements").glob("FR-001-*.md"))
    assert len(stories) == 1 and len(reqs) == 1
    for path in stories + reqs:
        assert len(path.name) <= len("US-001-") + 60 + len(".md"), path.name
        assert path.stem.startswith(("US-001-the-traceability-gate", "FR-001-the-traceability-gate"))
        assert not path.stem.endswith("-")
    epic = (dev / "epics").glob("EPIC-001-*.md").__next__().read_text(encoding="utf-8")
    assert f"../stories/{stories[0].name}" in epic


def test_finish_stage_records_a_hand_written_artifact_as_a_draft(pmos, new_project):
    """Backlog #63. A stage written outside its skill (in parts, by hand) becomes an
    approvable draft in one call: generated_hash stamped, .history snapshot written,
    meta + frontmatter set to draft, stage_generated logged with the model. Approval
    then works and computes the edit distance against that snapshot."""
    import frontmatter as fm
    proj = new_project("finish-stage", "A problem")
    run_script(pmos, "pm_approve.py", "00", cwd=proj)
    (proj / "01-brief.md").write_text("---\nstage: 01-brief\nstatus: pending\n---\n## Target User\nPMs.\n",
                                      encoding="utf-8")

    res = run_script(pmos, "pm_finish_stage.py", "01", "--model", "claude-test-model",
                     "--note", "written in two parts", cwd=proj)
    assert res.returncode == 0, res.stdout + res.stderr
    assert stage_status(proj, "01") == "draft"
    fmd, _ = fm.read(str(proj / "01-brief.md"))
    assert fmd["status"] == "draft" and fmd["generated_hash"]
    assert fmd["generation_notes"] == ["written in two parts"]
    assert list((proj / ".history").glob("01-brief.*.generated.md"))
    generated = [e for e in read_events(proj) if e["event_type"] == "stage_generated"]
    assert generated[-1]["stage"] == "01"
    assert generated[-1]["payload"]["model"] == "claude-test-model"
    assert generated[-1]["payload"]["generated_hash"] == fmd["generated_hash"]
    assert generated[-1]["payload"]["prompt_version"] not in (None, "", "unknown")

    path = proj / "01-brief.md"
    path.write_text(path.read_text(encoding="utf-8") + "PM edit.\n", encoding="utf-8")
    res = run_script(pmos, "pm_approve.py", "01", cwd=proj)
    assert res.returncode == 0, res.stdout + res.stderr
    approved = [e for e in read_events(proj) if e["event_type"] == "stage_approved"][-1]
    assert approved["payload"]["char_edit_distance"] == len("PM edit.\n")


def test_finish_stage_refuses_a_missing_or_empty_artifact(pmos, new_project):
    """Backlog #63. Nothing to finish means a clear error, and no state change."""
    proj = new_project("finish-missing", "A problem")
    res = run_script(pmos, "pm_finish_stage.py", "01", "--model", "m", cwd=proj)
    assert res.returncode != 0 and "does not exist" in res.stdout
    (proj / "01-brief.md").write_text("---\nstatus: pending\n---\n\n", encoding="utf-8")
    res = run_script(pmos, "pm_finish_stage.py", "01", "--model", "m", cwd=proj)
    assert res.returncode != 0 and "no body" in res.stdout
    assert stage_status(proj, "01") == "pending"


def test_status_shows_a_successful_sync(pmos, new_project):
    """Backlog #62. An approval whose central sync succeeded records it, and
    /pm-status reports the sync as OK."""
    proj = new_project("sync-ok", "A problem")
    assert run_script(pmos, "pm_approve.py", "00", cwd=proj).returncode == 0
    status = json.loads((proj / ".pm-os-sync.json").read_text(encoding="utf-8"))
    assert status["ok"] is True and status["last_success_at"]
    res = run_script(pmos, "pm_status.py", cwd=proj)
    assert "Central sync:      OK" in res.stdout, res.stdout


def test_status_explains_a_credential_failure_and_counts_unsynced_approvals(pmos, new_project):
    """Backlog #62. When pushes fail for lack of credentials (GH #77-16: ~30 silent
    failures), /pm-status says so, names the feedback repo and the fix, and counts the
    approvals that have not reached the central repo."""
    proj = new_project("sync-auth", "A problem")
    assert run_script(pmos, "pm_approve.py", "00", cwd=proj).returncode == 0
    (proj / ".pm-os-sync.json").write_text(json.dumps({
        "last_attempt_at": "2099-01-01T00:00:00+00:00", "ok": False,
        "reason": "commit/push: fatal: could not read Username for 'https://github.com': "
                  "terminal prompts disabled",
    }), encoding="utf-8")
    res = run_script(pmos, "pm_status.py", cwd=proj)
    assert "Central sync:      FAILED" in res.stdout, res.stdout
    assert "No git credentials" in res.stdout
    assert str(pmos.feedback) in res.stdout
    assert "Approvals not yet synced: 1" in res.stdout


def test_sync_status_file_is_never_committed(pmos, new_project):
    """Backlog #61/#62. The per-project sync record is machine-local state: it is
    gitignored (older projects get the entry added) and never appears in a commit."""
    proj = new_project("sync-ignored", "A problem")
    run_script(pmos, "pm_approve.py", "00", cwd=proj)
    tracked = subprocess.run(["git", "-C", str(proj), "ls-files"], capture_output=True,
                             text=True).stdout.split()
    assert ".pm-os-sync.json" not in tracked
    assert ".pm-os-sync.json" in (proj / ".gitignore").read_text(encoding="utf-8")
