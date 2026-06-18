"""T3 — skill contracts: structural facts that must not silently drift between the skill
Markdown, the scripts, and the code constants. These read the repo source directly (no temp
install). See docs/TESTING.md §5 (T3)."""
import re

import pytest

import project
import frontmatter
from helpers import skill_dirs, stage_skill_dir

pytestmark = pytest.mark.contract

STAGE_IDS = project.CORE_STAGE_ORDER + ["08", "09"]
PROVIDER_TOKENS = ("claude-", "gpt-", "opus", "sonnet", "haiku", "o1", "o3")


# KNOWN GAP (surfaced by this test): these utility skills currently ship no Codex
# agents/openai.yaml twin, contrary to the runtime-agnostic rule in CLAUDE.md. Tracked here
# so the suite stays green AND any *new* drop — or a fix — is noticed. Resolve separately,
# then delete entries from this set (the parity test will then require the twin).
KNOWN_MISSING_CODEX_TWIN = {
    "pm-approve", "pm-feedback", "pm-new", "pm-os-install",
    "pm-os-update", "pm-os-verify", "pm-share", "pm-status",
}


def test_every_skill_has_frontmatter():
    """Every skill ships valid frontmatter with a name and description."""
    for sd in skill_dirs():
        fm, _ = frontmatter.read(str(sd / "SKILL.md"))
        assert fm.get("name"), f"{sd.name}: missing frontmatter name"
        assert fm.get("description"), f"{sd.name}: missing frontmatter description"


def test_codex_twin_parity_no_regression():
    """Skills outside the documented known-gap set must ship a Codex agents/openai.yaml twin;
    and the set of skills missing it must match the allowlist exactly — so a NEW skill dropping
    its twin fails here, and fixing a known one (removing it from the allowlist) is required to
    keep this green. Locks the current state and prevents silent drift either way."""
    missing = {sd.name for sd in skill_dirs() if not (sd / "agents" / "openai.yaml").exists()}
    new_gaps = missing - KNOWN_MISSING_CODEX_TWIN
    assert not new_gaps, f"skill(s) dropped the Codex twin: {sorted(new_gaps)}"
    fixed = KNOWN_MISSING_CODEX_TWIN - missing
    assert not fixed, f"twin added for {sorted(fixed)} — remove them from KNOWN_MISSING_CODEX_TWIN"


def test_skill_frontmatter_has_no_provider_model_ids():
    """Shared skill frontmatter uses runtime-neutral tiers, never a provider model id."""
    for sd in skill_dirs():
        fm, _ = frontmatter.read(str(sd / "SKILL.md"))
        blob = " ".join(str(v) for v in fm.values()).lower()
        for tok in PROVIDER_TOKENS:
            assert tok not in blob, f"{sd.name}: provider token '{tok}' leaked into frontmatter"


@pytest.mark.parametrize("stage_id", STAGE_IDS)
def test_stage_skill_structure(stage_id):
    """Each stage skill matches the code: dir/name/writes follow STAGE_NAMES, and the body
    carries the gate command, the context-overlay load, and the stage_generated telemetry with
    the model id + config-derived tier — the mechanical contract the engine relies on."""
    sd = stage_skill_dir(stage_id)
    assert sd.is_dir(), f"missing skill dir for stage {stage_id}"
    fm, body = frontmatter.read(str(sd / "SKILL.md"))
    name = project.STAGE_NAMES[stage_id]
    assert fm["name"] == f"pm-stage-{stage_id}-{name}"
    assert fm["writes"] == f"{stage_id}-{name}.md" or f"{stage_id}-{name}.md" in str(fm["writes"])
    assert f"PM_OS_STAGE={stage_id} python3 ~/.pm-os/hooks/pre-stage.py" in body, "gate command"
    assert f"render_context('{stage_id}'" in body, "context-overlay load step"
    assert "stage_generated" in body and "'model'" in body, "model capture in telemetry"
    assert f"model_tier_for_stage('{stage_id}')" in body, "tier derived from config, not baked"


def test_deep_reasoning_stages_declare_tier():
    """Every deep-reasoning stage that has its own stage skill declares the tier in frontmatter,
    matching config.DEEP_REASONING_STAGES. The context-build stages (00w/00u) are deep too but
    are generated via pm-context-import (no per-stage skill), so they're checked via config."""
    import config
    for sid in config.DEEP_REASONING_STAGES:
        sd = stage_skill_dir(sid)
        if not sd.is_dir():
            continue  # 00w/00u have no pm-stage-* skill; verified below
        fm, _ = frontmatter.read(str(sd / "SKILL.md"))
        assert fm.get("model_tier") == "deep-reasoning", f"stage {sid} should declare deep-reasoning"
    for sid in ("00w", "00u"):
        assert sid in config.DEEP_REASONING_STAGES
        assert config.model_tier_for_stage(sid) == "deep-reasoning"


def test_stage_skills_print_both_runtime_entrypoints():
    """Stage skills surface both Claude (/pm-*) and Codex ($pm-*) entrypoints where they tell
    the PM what to run next."""
    for sid in STAGE_IDS:
        body = (stage_skill_dir(sid) / "SKILL.md").read_text()
        assert "/pm-approve" in body and "$pm-approve" in body, f"stage {sid}: missing runtime entrypoints"
