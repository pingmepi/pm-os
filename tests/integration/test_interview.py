"""T5 — context-import interview mechanics: PM-authored answers become sourced context."""
import pytest

import frontmatter
import yaml

from helpers import read_events, run_script, write_artifact

pytestmark = pytest.mark.integration


def test_record_interview_registers_pm_authored_source(pmos, new_project):
    """record-interview preserves answers as high-confidence PM-authored interview context."""
    proj = new_project("interview", "Prototype needs upstream reconstruction")
    answers = proj / "interview-answers.md"
    answers.write_text(
        "## Problem / why\n"
        "- The PM approved the prototype because it reduces handoff ambiguity.\n",
        encoding="utf-8",
    )

    res = run_script(
        pmos,
        "pm_context_import.py",
        "record-interview",
        str(answers),
        cwd=proj,
    )

    assert res.returncode == 0, res.stderr
    sources = yaml.safe_load((proj / ".sources.yaml").read_text(encoding="utf-8"))
    source = next(s for s in sources if s["uri"] == str(answers))
    assert source["type"] == "context"
    assert source["authorship"] == "pm"
    assert source["origin"] == "interview"
    assert source["confidence"] == "high"


def test_record_interview_records_skips_as_known_unknowns(pmos, new_project):
    """record-interview writes skipped PM questions as known unknowns, not assumptions."""
    proj = new_project("interview-skips", "Prototype needs upstream reconstruction")
    answers = proj / "interview-answers.md"
    answers.write_text(
        "## Interview answers\n"
        "- [x] ANSWERED: Why does this product matter?\n"
        "  It reduces prototype-to-dev ambiguity.\n"
        "- [ ] SKIPPED: Which user segment is explicitly out of scope?\n",
        encoding="utf-8",
    )

    res = run_script(pmos, "pm_context_import.py", "record-interview", str(answers), cwd=proj)

    assert res.returncode == 0, res.stderr
    known_unknowns = proj / "00-context" / "known-unknowns.md"
    assert known_unknowns.exists()
    text = known_unknowns.read_text(encoding="utf-8")
    assert "Which user segment is explicitly out of scope?" in text
    assert "Assumption I will use" not in text


def test_record_interview_emits_telemetry(pmos, new_project):
    """record-interview logs interview_conducted telemetry with asked/answered/skipped counts."""
    proj = new_project("interview-telemetry", "Prototype needs upstream reconstruction")
    answers = proj / "interview-answers.md"
    answers.write_text(
        "## Interview answers\n"
        "- [x] ANSWERED: Why does this product matter?\n"
        "  It reduces prototype-to-dev ambiguity.\n"
        "- [ ] SKIPPED: Which user segment is explicitly out of scope?\n",
        encoding="utf-8",
    )

    res = run_script(pmos, "pm_context_import.py", "record-interview", str(answers), cwd=proj)

    assert res.returncode == 0, res.stderr
    events = [e for e in read_events(proj) if e["event_type"] == "interview_conducted"]
    assert events
    assert events[-1]["payload"]["asked"] == 2
    assert events[-1]["payload"]["answered"] == 1
    assert events[-1]["payload"]["skipped"] == 1


def test_interview_answers_file_is_consumed_noninteractively(pmos, new_project):
    """--interview-answers registers answers without prompting in a non-tty subprocess."""
    proj = new_project("interview-file", "Prototype needs upstream reconstruction")
    answers = proj / "answers.md"
    answers.write_text(
        "## Interview answers\n"
        "- [x] ANSWERED: What success criterion matters most?\n"
        "  Dev handoff is unambiguous.\n",
        encoding="utf-8",
    )

    res = run_script(
        pmos,
        "pm_context_import.py",
        "record-interview",
        "--interview-answers",
        str(answers),
        cwd=proj,
    )

    assert res.returncode == 0, res.stderr
    sources = yaml.safe_load((proj / ".sources.yaml").read_text(encoding="utf-8"))
    assert any(s["uri"] == str(answers) and s["origin"] == "interview" for s in sources)


def test_interview_skip_env_records_all_as_known_unknowns(pmos, new_project):
    """PM_OS_INTERVIEW=skip records every pending question as a known unknown and exits 0."""
    proj = new_project("interview-skip-env", "Prototype needs upstream reconstruction")
    questions = proj / "interview-questions.md"
    questions.write_text(
        "## Interview questions\n"
        "- What user segment is out of scope?\n"
        "- What launch metric defines success?\n",
        encoding="utf-8",
    )

    res = run_script(
        pmos,
        "pm_context_import.py",
        "record-interview",
        str(questions),
        cwd=proj,
        extra_env={"PM_OS_INTERVIEW": "skip"},
    )

    assert res.returncode == 0, res.stderr
    text = (proj / "00-context" / "known-unknowns.md").read_text(encoding="utf-8")
    assert "What user segment is out of scope?" in text
    assert "What launch metric defines success?" in text
    event = [e for e in read_events(proj) if e["event_type"] == "interview_conducted"][-1]
    assert event["payload"]["asked"] == 2
    assert event["payload"]["answered"] == 0
    assert event["payload"]["skipped"] == 2


def test_interview_non_tty_questions_file_records_known_unknowns(pmos, new_project):
    """A non-tty pending-question file records every question as known unknowns without env."""
    proj = new_project("interview-nontty", "Prototype needs upstream reconstruction")
    questions = proj / "interview-questions.md"
    questions.write_text(
        "## Interview questions\n"
        "- What risk must QA prioritize?\n"
        "- Who approves scope tradeoffs?\n",
        encoding="utf-8",
    )

    res = run_script(pmos, "pm_context_import.py", "record-interview", str(questions), cwd=proj)

    assert res.returncode == 0, res.stderr
    text = (proj / "00-context" / "known-unknowns.md").read_text(encoding="utf-8")
    assert "What risk must QA prioritize?" in text
    assert "Who approves scope tradeoffs?" in text


def test_pathway2_import_with_interview_raises_backfill_fidelity(pmos, new_project):
    """Pathway-2 interview answers become PM source provenance on a backfilled upstream."""
    proj = new_project("pathway2-e2e", "Prototype approved; upstream why/scope missing")

    preflight = run_script(pmos, "pm_context_import.py", "preflight", "--provided", "04", cwd=proj)
    assert preflight.returncode == 0, preflight.stderr
    assert "lossy" in preflight.stdout.lower()

    answers = proj / "prototype-interview.md"
    answers.write_text(
        "## Interview answers\n"
        "- [x] ANSWERED: Why does this product matter?\n"
        "  It reduces prototype-to-dev handoff ambiguity.\n"
        "- [ ] SKIPPED: Which compliance constraints are binding?\n",
        encoding="utf-8",
    )
    recorded = run_script(
        pmos,
        "pm_context_import.py",
        "record-interview",
        "--interview-answers",
        str(answers),
        cwd=proj,
    )
    assert recorded.returncode == 0, recorded.stderr

    sources = yaml.safe_load((proj / ".sources.yaml").read_text(encoding="utf-8"))
    source = next(s for s in sources if s["uri"] == str(answers))
    assert source["origin"] == "interview"
    assert source["confidence"] == "high"
    assert "Which compliance constraints are binding?" in (
        proj / "00-context" / "known-unknowns.md"
    ).read_text(encoding="utf-8")

    write_artifact(
        proj / "01-brief.md",
        stage="01-brief",
        project=proj.name,
        status="draft",
        body="## Problem\nIt reduces prototype-to-dev handoff ambiguity.\n",
    )
    committed = run_script(
        pmos,
        "pm_context_import.py",
        "commit",
        "01",
        "--kind",
        "backfilled",
        "--status",
        "draft",
        "--derived-from",
        "04",
        "--model",
        "test",
        cwd=proj,
    )
    assert committed.returncode == 0, committed.stderr
    fm, body = frontmatter.read(str(proj / "01-brief.md"))
    assert source["id"] in fm["interview_sources"]
    assert "handoff ambiguity" in body
