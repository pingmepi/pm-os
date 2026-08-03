"""E3 — standalone /pm-interview mechanical state (pm_interview.py).

Covers the reader (`list-unknowns`), the resolver (`resolve` — mark-in-place +
rerun telemetry + provenance), non-interactive safety, and the end-to-end
re-run flow. The *questioning* judgment lives in skills/pm-interview/SKILL.md;
these tests only exercise the byte-moving script and its reuse of the E1
`record-interview` subcommand.
"""
import json
import re

import pytest
import yaml

from helpers import run_script

pytestmark = pytest.mark.integration


def _telemetry_events(proj):
    path = proj / "telemetry.jsonl"
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def _open_bullet_count(proj):
    text = (proj / KU_DIR / KU_FILE).read_text(encoding="utf-8")
    return sum(1 for line in text.splitlines() if line.strip().startswith("- "))

KU_DIR = "00-context"
KU_FILE = "known-unknowns.md"


def _header() -> str:
    return (
        "# Known unknowns\n\n"
        "Skipped or unanswered PM interview questions. These remain unresolved gaps, not assumptions.\n\n"
    )


def _write_known_unknowns(proj, body: str):
    ku = proj / KU_DIR
    ku.mkdir(exist_ok=True)
    (ku / KU_FILE).write_text(body, encoding="utf-8")
    return ku / KU_FILE


# --- Loop 1: list-unknowns reader ---------------------------------------------

def test_list_unknowns_returns_open_items(pmos, new_project):
    """list-unknowns --json returns only OPEN bullets (resolved ones excluded), each with question + source."""
    proj = new_project()
    _write_known_unknowns(proj, _header() + "\n".join([
        "- Who is the primary user? (source: src_003)",
        "- What is the success metric? (source: src_003)",
        "- What is out of scope? (source: src_001) [resolved: src_005 2026-01-01]",
    ]) + "\n")

    res = run_script(pmos, "pm_interview.py", "list-unknowns", "--json", cwd=proj)
    assert res.returncode == 0, f"{res.stdout}\n{res.stderr}"
    items = json.loads(res.stdout)
    questions = {i["question"] for i in items}
    assert questions == {"Who is the primary user?", "What is the success metric?"}
    assert all(i["source"] == "src_003" for i in items)
    assert "What is out of scope?" not in questions


def test_list_unknowns_empty_when_no_file(pmos, new_project):
    """No known-unknowns.md → exit 0 and an empty JSON list, never an error."""
    proj = new_project()
    res = run_script(pmos, "pm_interview.py", "list-unknowns", "--json", cwd=proj)
    assert res.returncode == 0, f"{res.stdout}\n{res.stderr}"
    assert json.loads(res.stdout) == []


# --- Loop 2: resolve — mark-in-place + rerun telemetry ------------------------

def _two_open(proj):
    return _write_known_unknowns(proj, _header() + "\n".join([
        "- Who is the primary user? (source: src_003)",
        "- What is the success metric? (source: src_003)",
    ]) + "\n")


def test_resolve_marks_matched_unknowns_in_place(pmos, new_project):
    """resolve marks an answered unknown [resolved: ...] in place, keeps its text, and leaves the other open."""
    proj = new_project()
    _two_open(proj)
    answers = proj / "answers.md"
    answers.write_text("- [x] ANSWERED: Who is the primary user?\n", encoding="utf-8")

    res = run_script(pmos, "pm_interview.py", "resolve", str(answers), cwd=proj)
    assert res.returncode == 0, f"{res.stdout}\n{res.stderr}"

    text = (proj / KU_DIR / KU_FILE).read_text(encoding="utf-8")
    lines = {}
    for line in text.splitlines():
        if line.strip().startswith("- "):
            lines[line] = line
    answered_line = next(l for l in lines if "Who is the primary user?" in l)
    open_line = next(l for l in lines if "What is the success metric?" in l)
    assert "[resolved:" in answered_line
    assert "Who is the primary user?" in answered_line  # audit trail intact
    assert "[resolved:" not in open_line


def test_resolve_never_deletes(pmos, new_project):
    """resolve marks, never removes — the bullet count is unchanged after resolution."""
    proj = new_project()
    _two_open(proj)
    before = _open_bullet_count(proj)
    answers = proj / "answers.md"
    answers.write_text("- [x] ANSWERED: Who is the primary user?\n", encoding="utf-8")
    run_script(pmos, "pm_interview.py", "resolve", str(answers), cwd=proj)
    assert _open_bullet_count(proj) == before


def test_resolve_emits_rerun_telemetry(pmos, new_project):
    """resolve emits an interview_conducted event with mode='rerun' and integer counts."""
    proj = new_project()
    _two_open(proj)
    answers = proj / "answers.md"
    answers.write_text("- [x] ANSWERED: Who is the primary user?\n", encoding="utf-8")
    run_script(pmos, "pm_interview.py", "resolve", str(answers), cwd=proj)

    reruns = [e for e in _telemetry_events(proj)
              if e["event_type"] == "interview_conducted" and e["payload"].get("mode") == "rerun"]
    assert len(reruns) == 1
    payload = reruns[0]["payload"]
    for key in ("asked", "answered", "skipped"):
        assert isinstance(payload[key], int)
    assert payload["answered"] == 1


def test_rerun_flow_emits_single_event(pmos, new_project):
    """record-interview --mode rerun stays silent so the rerun logs exactly one
    interview_conducted event (mode=rerun), not a double-counted intake + rerun (Codex P2)."""
    proj = new_project()
    _two_open(proj)
    answers = proj / "answers.md"
    answers.write_text("- [x] ANSWERED: Who is the primary user?\n", encoding="utf-8")

    reg = run_script(pmos, "pm_context_import.py", "record-interview",
                     "--interview-answers", str(answers), "--mode", "rerun", cwd=proj)
    assert reg.returncode == 0, f"{reg.stdout}\n{reg.stderr}"
    resv = run_script(pmos, "pm_interview.py", "resolve", str(answers), cwd=proj)
    assert resv.returncode == 0, f"{resv.stdout}\n{resv.stderr}"

    events = [e for e in _telemetry_events(proj) if e["event_type"] == "interview_conducted"]
    assert len(events) == 1, f"expected one interview_conducted event, got {len(events)}"
    assert events[0]["payload"].get("mode") == "rerun"


def test_resolve_leaves_unanswered_open(pmos, new_project):
    """A skipped question stays open — never rewritten as an assumption."""
    proj = new_project()
    _two_open(proj)
    answers = proj / "answers.md"
    answers.write_text(
        "- [x] ANSWERED: Who is the primary user?\n"
        "- [ ] SKIPPED: What is the success metric?\n",
        encoding="utf-8",
    )
    run_script(pmos, "pm_interview.py", "resolve", str(answers), cwd=proj)

    res = run_script(pmos, "pm_interview.py", "list-unknowns", "--json", cwd=proj)
    open_qs = {i["question"] for i in json.loads(res.stdout)}
    assert open_qs == {"What is the success metric?"}


# --- Loop 3: provenance + non-interactive safety ------------------------------

def test_resolved_bullet_carries_provenance(pmos, new_project):
    """The resolved marker credits the newest PM interview source id and an ISO date."""
    proj = new_project()
    _write_known_unknowns(proj, _header()
                          + "- Who is the primary user? (source: src_seed)\n")
    answers = proj / "answers.md"
    answers.write_text("- [x] ANSWERED: Who is the primary user?\n", encoding="utf-8")

    # Register the answers as a PM interview source (E1 machinery, reused unchanged).
    reg = run_script(pmos, "pm_context_import.py", "record-interview",
                     "--interview-answers", str(answers), cwd=proj)
    assert reg.returncode == 0, f"{reg.stdout}\n{reg.stderr}"
    sources = yaml.safe_load((proj / ".sources.yaml").read_text()) or []
    interview_ids = [s["id"] for s in sources
                     if s.get("origin") == "interview" and s.get("confidence") == "high"]
    assert interview_ids, "record-interview should have created an interview source"
    expected = interview_ids[-1]

    res = run_script(pmos, "pm_interview.py", "resolve", str(answers), cwd=proj)
    assert res.returncode == 0, f"{res.stdout}\n{res.stderr}"
    text = (proj / KU_DIR / KU_FILE).read_text(encoding="utf-8")
    marked = next(l for l in text.splitlines() if "Who is the primary user?" in l)
    assert re.search(rf"\[resolved: {re.escape(expected)} \d{{4}}-\d{{2}}-\d{{2}}\]", marked), marked


def test_resolve_answers_file_consumed_noninteractively(pmos, new_project):
    """--interview-answers runs with no tty/prompt and resolves the matched unknown."""
    proj = new_project()
    _two_open(proj)
    answers = proj / "answers.md"
    answers.write_text("- [x] ANSWERED: Who is the primary user?\n", encoding="utf-8")
    res = run_script(pmos, "pm_interview.py", "resolve",
                     "--interview-answers", str(answers), cwd=proj)
    assert res.returncode == 0, f"{res.stdout}\n{res.stderr}"
    listed = run_script(pmos, "pm_interview.py", "list-unknowns", "--json", cwd=proj)
    open_qs = {i["question"] for i in json.loads(listed.stdout)}
    assert open_qs == {"What is the success metric?"}


def test_resolve_skip_env_leaves_all_open(pmos, new_project):
    """PM_OS_INTERVIEW=skip resolves nothing, exits 0, and says the unknowns remain open."""
    proj = new_project()
    _two_open(proj)
    answers = proj / "answers.md"
    answers.write_text("- [x] ANSWERED: Who is the primary user?\n", encoding="utf-8")
    res = run_script(pmos, "pm_interview.py", "resolve", str(answers), cwd=proj,
                     extra_env={"PM_OS_INTERVIEW": "skip"})
    assert res.returncode == 0, f"{res.stdout}\n{res.stderr}"
    assert "remain open" in res.stdout.lower()
    listed = run_script(pmos, "pm_interview.py", "list-unknowns", "--json", cwd=proj)
    open_qs = {i["question"] for i in json.loads(listed.stdout)}
    assert open_qs == {"Who is the primary user?", "What is the success metric?"}


# --- Loop 6: end-to-end standalone re-run -------------------------------------

def test_pm_interview_end_to_end_resolves_and_records(pmos, new_project):
    """The full re-run (record-interview → resolve) closes answered unknowns with provenance,
    leaves skips open, registers the interview source, logs mode=rerun, and updates /pm-status."""
    proj = new_project()
    _write_known_unknowns(proj, _header() + "\n".join([
        "- Who is the primary user? (source: src_seed)",
        "- What is the success metric? (source: src_seed)",
        "- What is out of scope? (source: src_seed)",
    ]) + "\n")
    answers = proj / "answers.md"
    answers.write_text(
        "- [x] ANSWERED: Who is the primary user? :: Enterprise admins\n"
        "- [x] ANSWERED: What is the success metric? :: Weekly active admins\n"
        "- [ ] SKIPPED: What is out of scope?\n",
        encoding="utf-8",
    )

    reg = run_script(pmos, "pm_context_import.py", "record-interview",
                     "--interview-answers", str(answers), "--mode", "rerun", cwd=proj)
    assert reg.returncode == 0, f"{reg.stdout}\n{reg.stderr}"
    resv = run_script(pmos, "pm_interview.py", "resolve", str(answers), cwd=proj)
    assert resv.returncode == 0, f"{resv.stdout}\n{resv.stderr}"

    # (a) both answered unknowns marked resolved & still present (audit trail)
    text = (proj / KU_DIR / KU_FILE).read_text(encoding="utf-8")
    lines = [l for l in text.splitlines() if l.strip().startswith("- ")]
    user_line = next(l for l in lines if "Who is the primary user?" in l)
    metric_line = next(l for l in lines if "What is the success metric?" in l)
    scope_line = next(l for l in lines if "What is out of scope?" in l)
    assert "[resolved:" in user_line and "[resolved:" in metric_line
    # (b) the skipped unknown stays open
    assert "[resolved:" not in scope_line

    # (c) .sources.yaml gained the PM interview source
    sources = yaml.safe_load((proj / ".sources.yaml").read_text()) or []
    assert any(s.get("origin") == "interview" and s.get("confidence") == "high" for s in sources)

    # (d) exactly one interview_conducted event, correctly classified rerun (no double-counted intake)
    events = [e for e in _telemetry_events(proj) if e["event_type"] == "interview_conducted"]
    assert len(events) == 1, f"expected one interview_conducted event, got {len(events)}"
    assert events[0]["payload"].get("mode") == "rerun"
    assert events[0]["payload"]["answered"] == 2

    # (e) /pm-status now reports one open known unknown
    status = run_script(pmos, "pm_status.py", cwd=proj)
    assert "Known unknowns: 1 open" in status.stdout
