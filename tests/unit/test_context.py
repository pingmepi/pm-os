"""Unit tests for the context overlay (lib/context.py).

These lock down the guarantees Codex flagged in review:
- unfilled / seed-identical pack is a perfect no-op (every stage),
- malformed manifest fails loud (never silent "no overlay"),
- partial project override LAYERS over base (never wipes it),
plus seeding and the lazy-bootstrap path.

The `pmos` fixture repoints context.CONTEXT_DIR / CONTEXT_SEED_DIR at the temp
install (which has context.example/ but no context/ yet).
"""
import pytest

import context

pytestmark = pytest.mark.unit

ALL_STAGES = ["01", "02", "03", "04", "05", "06", "07", "08", "09"]


def _seed(pmos):
    context.seed_context()
    return pmos.install / "context"


def test_unfilled_pack_is_noop_every_stage(pmos):
    _seed(pmos)
    for s in ALL_STAGES:
        assert context.render_context(s, None) == "", f"stage {s} not a no-op while unfilled"
        assert context.resolve_context(s, None)["has_content"] is False


def test_lazy_bootstrap_seeds_on_first_read(pmos):
    ctx = pmos.install / "context"
    assert not ctx.exists()  # not seeded yet
    assert context.render_context("04", None) == ""   # first read self-seeds
    assert (ctx / "context.yaml").exists()
    n_seed = sum(1 for p in (pmos.install / "context.example").rglob("*") if p.is_file())
    n_live = sum(1 for p in ctx.rglob("*") if p.is_file())
    assert n_live == n_seed


def test_seed_context_copies_missing_without_overwrite(pmos):
    ctx = _seed(pmos)
    n = sum(1 for p in ctx.rglob("*") if p.is_file())
    assert n > 0
    assert context.seed_context() == 0  # idempotent

    # An edited live file is preserved; a brand-new seed file is copied.
    company = ctx / "global" / "company.md"
    company.write_text("# Company\nEDITED BY PM.\n", encoding="utf-8")
    (pmos.install / "context.example" / "global" / "newfile.md").write_text("# New\nseed\n", encoding="utf-8")
    copied = context.seed_context()
    assert copied == 1
    assert "EDITED BY PM." in company.read_text()
    assert (ctx / "global" / "newfile.md").exists()


def test_malformed_manifest_fails_loud(pmos):
    ctx = _seed(pmos)
    (ctx / "context.yaml").write_text("global: [a, b\nstages: {{{\n", encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        context.render_context("04", None)
    assert "malformed" in str(exc.value).lower()


def test_filled_global_surfaces_and_strips_guidance(pmos):
    ctx = _seed(pmos)
    (ctx / "global" / "company.md").write_text(
        "# Company context\n> guidance to drop\n<!-- TODO -->\n"
        "Indegene is a life-sciences commercialization company.\n", encoding="utf-8")
    out = context.render_context("01", None)
    assert "life-sciences commercialization" in out
    assert "apply: augment" in out
    assert "guidance to drop" not in out, "blockquote guidance must be stripped"
    # The untouched glossary's empty table must NOT leak in.
    assert "Term / acronym" not in out


def test_apply_modes_emit_correct_directive(pmos):
    ctx = _seed(pmos)
    # Make stage 04 format substantive so the stage block renders.
    (ctx / "stages" / "04-design-spec" / "format.md").write_text(
        "# fmt\n## Required sections\nProblem, Flows, States.\n", encoding="utf-8")
    manifest = (ctx / "context.yaml").read_text()

    (ctx / "context.yaml").write_text(manifest.replace(
        'format:   stages/04-design-spec/format.md\n    examples: [stages/04-design-spec/example.md]\n    apply: augment',
        'format:   stages/04-design-spec/format.md\n    examples: [stages/04-design-spec/example.md]\n    apply: override'),
        encoding="utf-8")
    res = context.resolve_context("04", None)
    assert res["apply"] == "override"
    assert "REPLACE" in context.render_context("04", None)


def test_partial_project_override_layers_over_base(pmos, tmp_path):
    ctx = _seed(pmos)
    # Base: real company + guardrails + a real stage-04 example.
    (ctx / "global" / "company.md").write_text("# Company\nBASE company line.\n", encoding="utf-8")
    (ctx / "global" / "guardrails.md").write_text("# Guardrails\nBASE never expose PHI.\n", encoding="utf-8")
    (ctx / "stages" / "04-design-spec" / "example.md").write_text("# ex\nBASE design example.\n", encoding="utf-8")

    # Project override: adds ONE extra global file + overrides only stage-04 apply/format.
    proj = tmp_path / "proj"
    (proj / "context" / "global").mkdir(parents=True)
    (proj / "context" / "stages" / "04-design-spec").mkdir(parents=True)
    (proj / "context" / "context.yaml").write_text(
        "global: [global/project-extra.md]\n"
        'stages:\n  "04":\n    apply: override\n    format: stages/04-design-spec/format.md\n',
        encoding="utf-8")
    (proj / "context" / "global" / "project-extra.md").write_text("# Extra\nPROJECT-ONLY note.\n", encoding="utf-8")
    (proj / "context" / "stages" / "04-design-spec" / "format.md").write_text(
        "# fmt\n## Required sections\nPROJECT format X.\n", encoding="utf-8")

    out = context.render_context("04", str(proj))
    res = context.resolve_context("04", str(proj))
    assert "BASE company line." in out, "base global dropped by partial override"
    assert "BASE never expose PHI." in out, "base guardrails dropped"
    assert "PROJECT-ONLY note." in out, "project-only global missing"
    assert "BASE design example." in out, "base stage example dropped"
    assert res["apply"] == "override", "project apply mode must win"
    assert "PROJECT format X." in out, "project format must win"
