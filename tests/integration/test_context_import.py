"""T5 — context-import mechanical state (scripts/pm_context_import.py): register sources,
preflight backfill feasibility, and commit slots the skill wrote. See docs/guides/testing.md §5 (T5)."""
import pytest

import yaml

from helpers import run_script, write_artifact, read_events, stage_status

pytestmark = pytest.mark.integration


def _write_pack(proj):
    """Populate a minimal modular context pack (the bytes the SKILL would write)."""
    (proj / "00-context").mkdir(exist_ok=True)
    (proj / "00-context" / "views").mkdir(exist_ok=True)
    (proj / "00-context-wiki.md").write_text(
        "---\nstage: 00w-context-wiki\nstatus: draft\n---\n# Index\nNavigation.\n", encoding="utf-8")
    (proj / "00-context" / "sources.md").write_text(
        "---\nx: 1\n---\n# Sources\nsrc_001 market report.\n", encoding="utf-8")
    (proj / "00-context" / "evidence.yaml").write_text(
        "claims:\n- id: c1\n  text: alpha\n  confidence: medium\n", encoding="utf-8")
    (proj / "00-context" / "views" / "market-landscape.md").write_text(
        "---\nx: 1\n---\n# Market landscape\n| seg | note |\n|--|--|\n", encoding="utf-8")


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


# --- Adaptive context pack (v4) ----------------------------------------------

def test_register_classifies_new_formats_with_modality(pmos, new_project):
    """register ingests images, PPTX, and XLSX (not just text/PDF/DOCX/CSV), tagging each
    .sources.yaml entry with a deterministic modality and flagging lossy-by-default ones."""
    proj = _ctx_proj(pmos, new_project, slug="fmt")
    folder = proj / "drop"
    folder.mkdir()
    (folder / "notes.md").write_text("# notes\n", encoding="utf-8")
    (folder / "deck.pptx").write_bytes(b"PK\x03\x04 fake pptx")
    (folder / "data.xlsx").write_bytes(b"PK\x03\x04 fake xlsx")
    (folder / "screenshot.png").write_bytes(b"\x89PNG fake")
    res = run_script(pmos, "pm_context_import.py", "register", "drop", "--type", "research", cwd=proj)
    assert res.returncode == 0, res.stderr
    sources = yaml.safe_load((proj / ".sources.yaml").read_text())
    by_mod = {s["modality"] for s in sources}
    assert {"text", "slides", "spreadsheet", "image"} <= by_mod
    # lossy-by-default modalities are pre-flagged so they can't earn High confidence silently
    for s in sources:
        if s["modality"] in {"image", "slides", "spreadsheet"}:
            assert s["extraction_quality"] == "lossy"
            assert s["uncertainty"]


def test_pack_manifest_builds_fixed_order_and_records_meta(pmos, new_project):
    """pack-manifest writes a manifest in fixed canonical order (wiki index, evidence, sources,
    then views), records per-member hashes, and stamps context_pack into .meta.yaml."""
    proj = _ctx_proj(pmos, new_project, slug="pack")
    _write_pack(proj)
    res = run_script(pmos, "pm_context_import.py", "pack-manifest", cwd=proj)
    assert res.returncode == 0, res.stderr
    manifest = yaml.safe_load((proj / "00-context" / "manifest.yaml").read_text())
    paths = [m["path"] for m in manifest["members"]]
    assert paths == [
        "00-context-wiki.md",
        "00-context/evidence.yaml",
        "00-context/sources.md",
        "00-context/views/market-landscape.md",
    ]
    assert all(m.get("hash") for m in manifest["members"])
    meta = yaml.safe_load((proj / ".meta.yaml").read_text())
    assert meta["context_pack"]["manifest"] == "00-context/manifest.yaml"
    assert meta["context_pack"]["member_count"] == 4


def test_pack_validate_detects_post_build_edit(pmos, new_project):
    """pack-validate passes on a fresh manifest and reports a stale recorded hash once a member
    body is edited after the manifest was built."""
    proj = _ctx_proj(pmos, new_project, slug="pkv")
    _write_pack(proj)
    assert run_script(pmos, "pm_context_import.py", "pack-manifest", cwd=proj).returncode == 0
    assert run_script(pmos, "pm_context_import.py", "pack-validate", cwd=proj).returncode == 0
    (proj / "00-context" / "sources.md").write_text(
        "---\nx: 1\n---\n# Sources\nEDITED.\n", encoding="utf-8")
    res = run_script(pmos, "pm_context_import.py", "pack-validate", cwd=proj)
    assert res.returncode == 2
    assert "00-context/sources.md" in res.stdout


def test_composite_00w_commit_and_approve_uses_composite_hash(pmos, new_project):
    """Committing 00w with a pack present approves it under the composite hash (spanning all
    members), not the wiki-index body hash alone."""
    proj = _ctx_proj(pmos, new_project, slug="cmp")
    _write_pack(proj)
    assert run_script(pmos, "pm_context_import.py", "pack-manifest", cwd=proj).returncode == 0
    res = run_script(pmos, "pm_context_import.py", "commit", "00w",
                     "--kind", "generated", "--status", "approved",
                     "--model", "claude-opus-4-8", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert stage_status(proj, "00w") == "approved"
    # The recorded hash must equal the composite hash, not the flat body hash.
    import sys
    sys.path.insert(0, str(pmos.install / "lib"))
    import hashing
    meta = yaml.safe_load((proj / ".meta.yaml").read_text())
    recorded = next(s for s in meta["stages"] if s["id"] == "00w")["content_hash"]
    assert recorded == hashing.hash_composite_artifact(proj)
    assert recorded != hashing.hash_artifact_body(str(proj / "00-context-wiki.md"))


def test_editing_pack_member_is_drift_through_gate(pmos, new_project):
    """Editing any pack member body after 00w is approved is detected as drift by the pre-stage
    gate (composite hash moves), routing the PM to re-approve — same as a flat-wiki edit."""
    from helpers import run_hook
    proj = _ctx_proj(pmos, new_project, slug="drift")
    _write_pack(proj)
    assert run_script(pmos, "pm_context_import.py", "pack-manifest", cwd=proj).returncode == 0
    assert run_script(pmos, "pm_context_import.py", "commit", "00w",
                      "--kind", "generated", "--status", "approved",
                      "--model", "m", cwd=proj).returncode == 0
    # also need 00u approved? gate for 01 checks all present stage-00 docs. Only 00 + 00w present.
    # Edit a non-index member -> composite drift.
    (proj / "00-context" / "evidence.yaml").write_text(
        "claims:\n- id: c1\n  text: CHANGED\n  confidence: medium\n", encoding="utf-8")
    res = run_hook(pmos, "pre-stage.py", "01", proj)
    # gate marks 00w edited then routes to PM (non-tty block) -> non-zero
    assert res.returncode != 0
    assert stage_status(proj, "00w") == "edited"


def test_invalid_pack_manifest_blocks_approval(pmos, new_project):
    """A structurally unsafe manifest (member missing on disk) blocks 00w approval rather than
    silently falling back to a partial hash."""
    proj = _ctx_proj(pmos, new_project, slug="bad")
    _write_pack(proj)
    (proj / "00-context" / "manifest.yaml").write_text(
        "members:\n- path: 00-context/ghost.md\n  kind: markdown\n", encoding="utf-8")
    res = run_script(pmos, "pm_context_import.py", "commit", "00w",
                     "--kind", "generated", "--status", "approved", "--model", "m", cwd=proj)
    assert res.returncode != 0
    assert "invalid" in res.stdout.lower() or "invalid" in res.stderr.lower()


def test_upgrade_pack_snapshots_flat_wiki_and_drafts(pmos, new_project):
    """upgrade-pack preserves the flat wiki in .history/, scaffolds 00-context/, and flips 00w
    back to draft (rebuild path) — without re-approving anything."""
    proj = _ctx_proj(pmos, new_project, slug="upg")
    # simulate an existing approved flat single-file wiki
    write_artifact(proj / "00-context-wiki.md", stage="00w-context-wiki", project=proj.name,
                   status="draft", body="## TL;DR\nLegacy flat wiki.\n")
    assert run_script(pmos, "pm_context_import.py", "commit", "00w",
                      "--kind", "generated", "--status", "approved", "--model", "m", cwd=proj).returncode == 0
    assert stage_status(proj, "00w") == "approved"
    res = run_script(pmos, "pm_context_import.py", "upgrade-pack", cwd=proj)
    assert res.returncode == 0, res.stderr
    assert stage_status(proj, "00w") == "draft"
    assert (proj / "00-context").is_dir()
    assert (proj / "00-context" / "views").is_dir()
    assert any("pre-upgrade" in p.name for p in (proj / ".history").iterdir())
    assert any(e["event_type"] == "context_pack_upgrade_started" for e in read_events(proj))
