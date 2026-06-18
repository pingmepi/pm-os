"""Unit tests for lib/project.py — stage tables, dependency graph, backfill feasibility,
schema migration, and project resolution. This module encodes the pipeline's shape and the
state-machine dependencies, so its edges are high-value. See docs/TESTING.md §5 (T1)."""
import pytest

import project

pytestmark = pytest.mark.unit


def test_stage_tables_consistent():
    """Every ordered stage has a name, core stages are a subset of the full order, and the
    stage-00 understanding group (00/00w/00u) leads the pipeline."""
    for sid in project.STAGE_ORDER:
        assert sid in project.STAGE_NAMES
    assert set(project.CORE_STAGE_ORDER) <= set(project.STAGE_ORDER)
    assert project.STAGE_ORDER[:3] == ["00", "00w", "00u"]


def test_artifact_path_special_and_formula(tmp_path):
    """Special-cased artifacts (00w/00u) map to their fixed filenames; all others follow
    the NN-name.md formula."""
    assert project.artifact_path(tmp_path, "00w").name == "00-context-wiki.md"
    assert project.artifact_path(tmp_path, "00u").name == "00-context-understanding.md"
    assert project.artifact_path(tmp_path, "01").name == "01-brief.md"
    assert project.artifact_path(tmp_path, "03").name == "03-prd.md"


def _meta(*stage_ids, approved=()):
    return {"stages": [
        {"id": s, "name": project.STAGE_NAMES[s],
         "status": "approved" if s in approved else "pending"}
        for s in stage_ids
    ]}


def test_get_stage_found_and_missing():
    """get_stage returns the matching stage dict and raises KeyError for an unknown id."""
    meta = _meta("00", "01")
    assert project.get_stage(meta, "01")["id"] == "01"
    with pytest.raises(KeyError):
        project.get_stage(meta, "99")


def test_upstream_linear_filtered_by_present_stages():
    """Upstreams are the prior stages actually present in meta — not the full catalog —
    so a project gates only on stages it has."""
    meta = _meta("00", "00w", "00u", "01", "02", "03")
    up = project.upstream_stage_ids("03", meta)
    assert "01" in up and "02" in up and "00" in up
    assert "04" not in up


def test_stage_09_optional_dependency_on_08():
    """Stage 09 depends on the optional stage 08 ONLY when 08 is approved; an unapproved/
    absent 08 must not gate 09 (the optional-capstone rule)."""
    meta = _meta(*project.STAGE_ORDER)
    assert "08" not in project.upstream_stage_ids("09", meta)
    meta_approved = _meta(*project.STAGE_ORDER, approved=("08",))
    assert "08" in project.upstream_stage_ids("09", meta_approved)


def test_downstream_includes_dependents():
    """downstream_stage_ids returns the stages that depend on the given one (inverse of
    upstream) — used to cascade staleness."""
    meta = _meta("00", "00w", "00u", "01", "02", "03")
    down = project.downstream_stage_ids("01", meta)
    assert "02" in down and "03" in down
    assert "00" not in down


def test_resolve_backfill_verdicts():
    """Backfill feasibility classifies each gap below the highest provided artifact as
    faithful/lossy/infeasible — and chains only through PROVIDED artifacts. Covers PRD-only
    (faithful upstreams), design-only (lossy PRD), metrics-only (all infeasible), and no-gap."""
    gaps = {g["stage"]: g for g in project.resolve_backfill(["03"])}
    assert gaps["01"]["verdict"] == "faithful"
    assert gaps["02"]["verdict"] == "faithful"
    gaps04 = {g["stage"]: g for g in project.resolve_backfill(["04"])}
    assert gaps04["03"]["verdict"] == "lossy"
    gaps07 = {g["stage"]: g for g in project.resolve_backfill(["07"])}
    assert all(g["verdict"] == "infeasible" for g in gaps07.values())
    assert project.resolve_backfill(["01"]) == []
    assert project.resolve_backfill([]) == []


def test_migrate_meta_v1_to_v2(tmp_path):
    """v1→v2 migration adds `origin` to existing stages, injects the business statement as
    an approved stage 00, and stamps schema_version — and is idempotent on a second pass
    (so existing on-disk projects keep working without re-approval)."""
    (tmp_path / "00-business-statement.md").write_text(
        "---\nstatus: approved\n---\nThe statement body.\n", encoding="utf-8")
    meta = {"project_slug": "demo", "stages": [
        {"id": "01", "name": "brief", "status": "draft"},
    ]}
    changed = project.migrate_meta(meta, tmp_path)
    assert changed is True
    assert meta["schema_version"] == project.SCHEMA_VERSION
    assert all("origin" in s for s in meta["stages"])
    assert project.get_stage(meta, "00")["status"] == "approved"
    assert project.migrate_meta(meta, tmp_path) is False


def test_resolve_project_walks_up(tmp_path, monkeypatch):
    """resolve_project walks up from CWD to the nearest .meta.yaml (so commands work from a
    subdirectory of the project)."""
    proj = tmp_path / "proj"
    (proj / "sub").mkdir(parents=True)
    (proj / ".meta.yaml").write_text("project_slug: demo\nstages: []\n", encoding="utf-8")
    monkeypatch.chdir(proj / "sub")
    assert project.resolve_project() == proj.resolve()


def test_resolve_project_not_found(tmp_path, monkeypatch):
    """resolve_project raises FileNotFoundError when run outside any PM-OS project."""
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        project.resolve_project()
