import pytest

import project

pytestmark = pytest.mark.unit


def test_stage_tables_consistent():
    # Every ordered stage has a name; core stages are a subset of the order.
    for sid in project.STAGE_ORDER:
        assert sid in project.STAGE_NAMES
    assert set(project.CORE_STAGE_ORDER) <= set(project.STAGE_ORDER)
    assert project.STAGE_ORDER[:3] == ["00", "00w", "00u"]


def test_artifact_path_special_and_formula(tmp_path):
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
    meta = _meta("00", "01")
    assert project.get_stage(meta, "01")["id"] == "01"
    with pytest.raises(KeyError):
        project.get_stage(meta, "99")


def test_upstream_linear_filtered_by_present_stages():
    meta = _meta("00", "00w", "00u", "01", "02", "03")
    up = project.upstream_stage_ids("03", meta)
    assert "01" in up and "02" in up and "00" in up
    assert "04" not in up


def test_stage_09_optional_dependency_on_08():
    # 08 present but not approved -> 09 must NOT depend on it.
    meta = _meta(*project.STAGE_ORDER)
    up = project.upstream_stage_ids("09", meta)
    assert "08" not in up
    # 08 approved -> 09 gains it as an upstream.
    meta_approved = _meta(*project.STAGE_ORDER, approved=("08",))
    assert "08" in project.upstream_stage_ids("09", meta_approved)


def test_downstream_includes_dependents():
    meta = _meta("00", "00w", "00u", "01", "02", "03")
    down = project.downstream_stage_ids("01", meta)
    assert "02" in down and "03" in down
    assert "00" not in down


def test_resolve_backfill_verdicts():
    # Provide only PRD (03): 01 faithful from 03, 02 faithful from 03.
    gaps = {g["stage"]: g for g in project.resolve_backfill(["03"])}
    assert gaps["01"]["verdict"] == "faithful"
    assert gaps["02"]["verdict"] == "faithful"
    # Provide only design (04): 03 is lossy-from-04 (no faithful source).
    gaps04 = {g["stage"]: g for g in project.resolve_backfill(["04"])}
    assert gaps04["03"]["verdict"] == "lossy"
    # Provide only metrics (07): everything below is infeasible.
    gaps07 = {g["stage"]: g for g in project.resolve_backfill(["07"])}
    assert all(g["verdict"] == "infeasible" for g in gaps07.values())
    # No gaps when only 01 provided.
    assert project.resolve_backfill(["01"]) == []
    # Empty provided -> no gaps.
    assert project.resolve_backfill([]) == []


def test_migrate_meta_v1_to_v2(tmp_path):
    (tmp_path / "00-business-statement.md").write_text(
        "---\nstatus: approved\n---\nThe statement body.\n", encoding="utf-8")
    meta = {"project_slug": "demo", "stages": [
        {"id": "01", "name": "brief", "status": "draft"},
    ]}
    changed = project.migrate_meta(meta, tmp_path)
    assert changed is True
    assert meta["schema_version"] == project.SCHEMA_VERSION
    # origin backfilled onto existing stages
    assert all("origin" in s for s in meta["stages"])
    # stage 00 injected as approved
    s00 = project.get_stage(meta, "00")
    assert s00["status"] == "approved"
    # idempotent second pass
    assert project.migrate_meta(meta, tmp_path) is False


def test_resolve_project_walks_up(tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    (proj / "sub").mkdir(parents=True)
    (proj / ".meta.yaml").write_text("project_slug: demo\nstages: []\n", encoding="utf-8")
    monkeypatch.chdir(proj / "sub")
    assert project.resolve_project() == proj.resolve()


def test_resolve_project_not_found(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        project.resolve_project()
