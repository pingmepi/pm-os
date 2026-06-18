"""T5 — feedback capture (scripts/pm_feedback.py): writes feedback.jsonl AND joins the
hash-chained telemetry stream; non-interactive safety. See docs/TESTING.md §5 (T5)."""
import json

import pytest

from helpers import run_script, read_events

pytestmark = pytest.mark.integration


def test_feedback_writes_jsonl_and_telemetry_event(pmos, new_project):
    """A rating+note writes a feedback.jsonl entry and logs a matching feedback_submitted
    telemetry event (so feedback is diagnosable and syncs)."""
    proj = new_project("fb", "A problem")
    run_script(pmos, "pm_approve.py", "00", cwd=proj)
    res = run_script(pmos, "pm_feedback.py", "00", "--rating", "4", "--note", "useful", cwd=proj)
    assert res.returncode == 0, res.stderr
    entries = [json.loads(l) for l in (proj / "feedback.jsonl").read_text().splitlines() if l.strip()]
    assert entries[-1]["rating"] == 4 and entries[-1]["note"] == "useful"
    ev = [e for e in read_events(proj) if e["event_type"] == "feedback_submitted"]
    assert ev and ev[-1]["payload"]["rating"] == 4


def test_feedback_skip_flags_no_hang(pmos, new_project):
    """--skip-rating/--skip-note capture an entry without prompting (safe in non-interactive)."""
    proj = new_project("fb2", "A problem")
    res = run_script(pmos, "pm_feedback.py", "00", "--skip-rating", "--skip-note", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert (proj / "feedback.jsonl").read_text().strip()


def test_feedback_non_interactive_requires_rating(pmos, new_project):
    """With no rating and no skip flag in non-interactive mode, it errors rather than hanging."""
    proj = new_project("fb3", "A problem")
    res = run_script(pmos, "pm_feedback.py", "00", cwd=proj)  # stdin is empty/non-tty
    assert res.returncode != 0


def test_feedback_unknown_stage_fails(pmos, new_project):
    """Feedback on an unknown stage id fails clearly."""
    proj = new_project("fb4", "A problem")
    res = run_script(pmos, "pm_feedback.py", "99", "--rating", "3", "--skip-note", cwd=proj)
    assert res.returncode != 0
