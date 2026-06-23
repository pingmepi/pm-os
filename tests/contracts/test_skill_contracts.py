"""T3 — skill contracts: structural facts that must not silently drift between the skill
Markdown, the scripts, and the code constants. These read the repo source directly (no temp
install). See docs/guides/testing.md §5 (T3)."""
import re

import pytest
import yaml

import project
import frontmatter
from helpers import REPO_ROOT, skill_dirs, stage_skill_dir

pytestmark = pytest.mark.contract

STAGE_IDS = project.CORE_STAGE_ORDER + ["08", "09"]
PROVIDER_TOKENS = ("claude-", "gpt-", "opus", "sonnet", "haiku", "o1", "o3")


def test_every_skill_has_frontmatter():
    """Every skill ships valid frontmatter with a name and description."""
    for sd in skill_dirs():
        fm, _ = frontmatter.read(str(sd / "SKILL.md"))
        assert fm.get("name"), f"{sd.name}: missing frontmatter name"
        assert fm.get("description"), f"{sd.name}: missing frontmatter description"


def test_codex_twin_parity_no_regression():
    """Every skill ships the Codex/OpenAI agents/openai.yaml UI metadata twin."""
    missing = {sd.name for sd in skill_dirs() if not (sd / "agents" / "openai.yaml").exists()}
    assert not missing, f"skill(s) missing the Codex twin: {sorted(missing)}"


def test_openai_yaml_interface_metadata_is_well_formed():
    """OpenAI skill descriptors expose stable UI metadata and an explicit $skill prompt."""
    for sd in skill_dirs():
        path = sd / "agents" / "openai.yaml"
        data = yaml.safe_load(path.read_text())
        interface = data.get("interface", {}) if isinstance(data, dict) else {}
        assert interface.get("display_name"), f"{sd.name}: missing display_name"
        short = interface.get("short_description")
        assert isinstance(short, str), f"{sd.name}: missing short_description"
        assert 25 <= len(short) <= 64, f"{sd.name}: short_description length {len(short)}"
        prompt = interface.get("default_prompt")
        assert isinstance(prompt, str), f"{sd.name}: missing default_prompt"
        assert f"${sd.name}" in prompt, f"{sd.name}: default_prompt must mention ${sd.name}"


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


def test_product_artifact_skills_enforce_current_contracts():
    """Stages 03–05 carry the required/recommended product contracts and invoke strict
    deterministic validation before generation completes."""
    expected = {
        "03": ("## User Journeys", "## Journey–Requirement Traceability", "artifact_contract_version: 1"),
        "04": ("## Journey-to-Flow Traceability", "## Product UX Guardrails", "Interaction model:"),
        "05": ("## Prototype Audience & Modes", "## Validation Plan", "## Known Limitations"),
    }
    for stage_id, markers in expected.items():
        body = (stage_skill_dir(stage_id) / "SKILL.md").read_text()
        for marker in markers:
            assert marker in body, f"stage {stage_id}: missing contract marker {marker!r}"
        assert f"pm_validate_artifact.py {stage_id} --mode strict" in body


def test_prototype_html_uses_interaction_model_not_genai_flag():
    body = (REPO_ROOT / "skills" / "pm-prototype-html" / "SKILL.md").read_text()
    assert "Interaction model" in body
    assert "?review=1" in body
    assert "review-only" in body
    assert "Never introduce an AI affordance solely because `genai_flag=true`" in body
    assert "pm_validate_artifact.py 05-html --mode strict" in body
