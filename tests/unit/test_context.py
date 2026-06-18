"""Unit tests for the context overlay (lib/context.py).

These lock down the guarantees Codex flagged in review of the overlay feature:
- an unfilled / seed-identical pack is a perfect no-op on every stage,
- a malformed manifest fails loud (never a silent "no overlay"),
- a partial project override LAYERS over base context (never wipes it),
plus seeding (copy-if-missing) and the lazy self-seed bootstrap.

The `pmos` fixture repoints context.CONTEXT_DIR / CONTEXT_SEED_DIR at the temp install
(which ships context.example/ but no live context/ until seeded). See docs/TESTING.md §5 (T1).
"""
import pytest

import context

pytestmark = pytest.mark.unit

ALL_STAGES = ["01", "02", "03", "04", "05", "06", "07", "08", "09"]


def _seed(pmos):
    context.seed_context()
    return pmos.install / "context"


def test_unfilled_pack_is_noop_every_stage(pmos):
    """A freshly-seeded (all-TODO) pack renders nothing and has no content for ALL 9
    stages — the contract that "no overlay configured ⇒ PM-OS behaves exactly as today.\""""
    _seed(pmos)
    for s in ALL_STAGES:
        assert context.render_context(s, None) == "", f"stage {s} not a no-op while unfilled"
        assert context.resolve_context(s, None)["has_content"] is False


def test_lazy_bootstrap_seeds_on_first_read(pmos):
    """When context/ is absent (e.g. the self-update that introduced seeding ran the OLD
    updater), the first render self-seeds it from context.example/ and is still a no-op.
    Regression guard for the self-update bootstrap gap."""
    ctx = pmos.install / "context"
    assert not ctx.exists()
    assert context.render_context("04", None) == ""
    assert (ctx / "context.yaml").exists()
    n_seed = sum(1 for p in (pmos.install / "context.example").rglob("*") if p.is_file())
    n_live = sum(1 for p in ctx.rglob("*") if p.is_file())
    assert n_live == n_seed


def test_seed_context_copies_missing_without_overwrite(pmos):
    """seed_context copies only files missing from context/, is idempotent, never overwrites
    a PM's edited file, and DOES pull in newly-added seed files."""
    ctx = _seed(pmos)
    assert sum(1 for p in ctx.rglob("*") if p.is_file()) > 0
    assert context.seed_context() == 0  # idempotent

    company = ctx / "global" / "company.md"
    company.write_text("# Company\nEDITED BY PM.\n", encoding="utf-8")
    (pmos.install / "context.example" / "global" / "newfile.md").write_text("# New\nseed\n", encoding="utf-8")
    assert context.seed_context() == 1
    assert "EDITED BY PM." in company.read_text()
    assert (ctx / "global" / "newfile.md").exists()


def test_malformed_manifest_fails_loud(pmos):
    """A YAML-broken context.yaml makes render_context RAISE — never silently degrade to
    "no overlay" and drop the PM's company/guardrail context. Codex P2 regression guard."""
    ctx = _seed(pmos)
    (ctx / "context.yaml").write_text("global: [a, b\nstages: {{{\n", encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        context.render_context("04", None)
    assert "malformed" in str(exc.value).lower()


def test_filled_global_surfaces_and_strips_guidance(pmos):
    """A real line in global/company.md surfaces on a stage with the apply directive, while
    seed scaffolding (guidance blockquotes, the empty glossary table) is stripped/ignored."""
    ctx = _seed(pmos)
    (ctx / "global" / "company.md").write_text(
        "# Company context\n> guidance to drop\n<!-- TODO -->\n"
        "Indegene is a life-sciences commercialization company.\n", encoding="utf-8")
    out = context.render_context("01", None)
    assert "life-sciences commercialization" in out
    assert "apply: augment" in out
    assert "guidance to drop" not in out, "blockquote guidance must be stripped"
    assert "Term / acronym" not in out, "untouched glossary table must not leak"


def test_apply_modes_emit_correct_directive(pmos):
    """The stage's apply mode (augment/override/reference-only) drives the directive in the
    rendered block; here override → 'REPLACE' guidance."""
    ctx = _seed(pmos)
    (ctx / "stages" / "04-design-spec" / "format.md").write_text(
        "# fmt\n## Required sections\nProblem, Flows, States.\n", encoding="utf-8")
    manifest = (ctx / "context.yaml").read_text()
    (ctx / "context.yaml").write_text(manifest.replace(
        'format:   stages/04-design-spec/format.md\n    examples: [stages/04-design-spec/example.md]\n    apply: augment',
        'format:   stages/04-design-spec/format.md\n    examples: [stages/04-design-spec/example.md]\n    apply: override'),
        encoding="utf-8")
    assert context.resolve_context("04", None)["apply"] == "override"
    assert "REPLACE" in context.render_context("04", None)


def test_partial_project_override_layers_over_base(pmos, tmp_path):
    """A PARTIAL project manifest (one extra global file + only stage-04 apply/format) layers
    over the base: base global files and base stage examples survive, project files win per
    duplicate field, and global lists union. Codex P2 regression guard for the shallow merge."""
    ctx = _seed(pmos)
    (ctx / "global" / "company.md").write_text("# Company\nBASE company line.\n", encoding="utf-8")
    (ctx / "global" / "guardrails.md").write_text("# Guardrails\nBASE never expose PHI.\n", encoding="utf-8")
    (ctx / "stages" / "04-design-spec" / "example.md").write_text("# ex\nBASE design example.\n", encoding="utf-8")

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
