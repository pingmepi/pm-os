"""T5 — context-import mechanical state (scripts/pm_context_import.py): register sources,
preflight backfill feasibility, and commit slots the skill wrote. See docs/TESTING.md §5 (T5)."""
import pytest

from helpers import run_script, write_artifact, read_events, stage_status

pytestmark = pytest.mark.integration


def _ctx_proj(pmos, new_project, slug="ctx"):
    proj = new_project(slug, "Existing context to import")
    run_script(pmos, "pm_approve.py", "00", cwd=proj)  # business statement gated first
    return proj


def test_register_preserves_source_and_logs(pmos, new_project):
    """register preserves the raw source under .history/, records it in .sources.yaml, and logs
    a context_ingested event."""
    proj = _ctx_proj(pmos, new_project)
    (proj / "research.md").write_text("# Market research\nFindings.\n", encoding="utf-8")
    res = run_script(pmos, "pm_context_import.py", "register", "research.md", "--type", "research", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert (proj / ".sources.yaml").exists()
    assert any(p.name.startswith("source-") for p in (proj / ".history").iterdir())
    assert any(e["event_type"] == "context_ingested" for e in read_events(proj))


def test_register_missing_file_fails(pmos, new_project):
    """Registering a non-existent source fails clearly."""
    proj = _ctx_proj(pmos, new_project)
    res = run_script(pmos, "pm_context_import.py", "register", "nope.md", cwd=proj)
    assert res.returncode != 0


def test_preflight_feasible_and_infeasible(pmos, new_project):
    """preflight exits 0 when gaps are faithful/lossy (e.g. provided PRD 03) and non-zero when
    a gap is infeasible (e.g. only a metrics plan 07)."""
    proj = _ctx_proj(pmos, new_project)
    assert run_script(pmos, "pm_context_import.py", "preflight", "--provided", "03", cwd=proj).returncode == 0
    assert run_script(pmos, "pm_context_import.py", "preflight", "--provided", "07", cwd=proj).returncode != 0


def test_commit_unknown_stage_and_missing_slot_fail(pmos, new_project):
    """commit refuses an unknown stage id, and refuses a stage whose artifact slot the skill
    has not written yet."""
    proj = _ctx_proj(pmos, new_project)
    assert run_script(pmos, "pm_context_import.py", "commit", "99",
                      "--kind", "generated", "--status", "draft", cwd=proj).returncode != 0
    # 00w slot not written -> commit must fail
    assert run_script(pmos, "pm_context_import.py", "commit", "00w",
                      "--kind", "generated", "--status", "draft", cwd=proj).returncode != 0


def test_commit_generated_wiki_draft(pmos, new_project):
    """Committing the context-wiki slot as a generated draft creates the 00w stage entry and
    logs a stage_generated event carrying the model + prompt_version."""
    proj = _ctx_proj(pmos, new_project)
    write_artifact(proj / "00-context-wiki.md", stage="00w-context-wiki", project=proj.name,
                   status="draft", body="## TL;DR\nNormalized context.\n")
    res = run_script(pmos, "pm_context_import.py", "commit", "00w",
                     "--kind", "generated", "--status", "draft",
                     "--model", "claude-opus-4-8", "--prompt-version", "0.2.0", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert stage_status(proj, "00w") == "draft"
    gen = [e for e in read_events(proj) if e["event_type"] == "stage_generated" and e["stage"] == "00w"]
    assert gen and gen[-1]["payload"]["model"] == "claude-opus-4-8"
    assert gen[-1]["payload"]["prompt_version"] == "0.2.0"


def test_commit_backfilled_approved_records_origin(pmos, new_project):
    """Committing a reverse-generated upstream as backfilled+approved records origin and logs a
    stage_backfilled event with the model."""
    proj = _ctx_proj(pmos, new_project)
    write_artifact(proj / "01-brief.md", stage="01-brief", project=proj.name,
                   status="draft", body="Reverse-generated brief.\n")
    res = run_script(pmos, "pm_context_import.py", "commit", "01",
                     "--kind", "backfilled", "--status", "approved",
                     "--derived-from", "03", "--model", "claude-opus-4-8", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert stage_status(proj, "01") == "approved"
    bf = [e for e in read_events(proj) if e["event_type"] == "stage_backfilled" and e["stage"] == "01"]
    assert bf and bf[-1]["payload"]["origin"] == "backfilled"


def test_commit_backfilled_draft(pmos, new_project):
    """Committing a lossy/conflicted backfill as backfilled+draft keeps the stage in draft and
    logs a stage_backfilled_draft event (PM must /pm-approve explicitly)."""
    proj = _ctx_proj(pmos, new_project)
    write_artifact(proj / "01-brief.md", stage="01-brief", project=proj.name,
                   status="draft", body="Lossy reverse-generated brief.\n")
    res = run_script(pmos, "pm_context_import.py", "commit", "01",
                     "--kind", "backfilled", "--status", "draft",
                     "--derived-from", "03", "--model", "claude-opus-4-8", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert stage_status(proj, "01") == "draft"
    bf = [e for e in read_events(proj) if e["event_type"] == "stage_backfilled_draft" and e["stage"] == "01"]
    assert bf and bf[-1]["payload"]["origin"] == "backfilled"
