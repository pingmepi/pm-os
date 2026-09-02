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
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
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
        body = (stage_skill_dir(sid) / "SKILL.md").read_text(encoding="utf-8")
        assert "/pm-approve" in body and "$pm-approve" in body, f"stage {sid}: missing runtime entrypoints"


def test_product_artifact_skills_enforce_current_contracts():
    """Contracted artifact stages carry the required/recommended product/technical
    contracts and invoke strict deterministic validation before generation completes.
    Stage 06 adds the Phase 3.5 stable-id contract; stage 08 adds the warning-only
    TRD section contract."""
    expected = {
        "03": ("## Product Epics", "## Journey–Requirement Traceability", "artifact_contract_version: 7"),
        "04": ("## Journey-to-Flow Traceability", "## Product UX Guardrails", "Interaction model:", "artifact_contract_version: 7"),
        "05": ("## Prototype Audience & Modes", "## Validation Plan", "## Known Limitations"),
        "06": ("## Functional Test Cases", "## Requirement-Test Traceability", "artifact_contract_version: 7"),
        "08": ("## Work Breakdown", "## Open Technical Questions", "artifact_contract_version: 7"),
    }
    for stage_id, markers in expected.items():
        body = (stage_skill_dir(stage_id) / "SKILL.md").read_text(encoding="utf-8")
        for marker in markers:
            assert marker in body, f"stage {stage_id}: missing contract marker {marker!r}"
        assert f"pm_validate_artifact.py {stage_id} --mode strict" in body


def test_stage_skills_use_python_snapshot_helper():
    """Generated artifact history is owned by pm_snapshot.py, not by hand-written
    agent copies inside each stage skill."""
    for sid in STAGE_IDS:
        body = (stage_skill_dir(sid) / "SKILL.md").read_text(encoding="utf-8")
        assert f"pm_snapshot.py {sid}" in body, f"stage {sid}: missing snapshot helper call"
        assert "Save to history" not in body, f"stage {sid}: still asks the agent to hand-write history"


def test_context_import_skill_produces_modular_pack():
    """The context-import skill must instruct producing the modular pack the engine
    consumes (evidence ledger + source inventory + manifest assembly), and must NOT
    revert to the single-page-only wiki that left the pack infrastructure dormant.
    Guards the gap found in the end-to-end dogfood: composite hashing/dual-mode reads
    only engage when the producer actually writes the pack and builds the manifest."""
    body = (REPO_ROOT / "skills" / "pm-context-import" / "SKILL.md").read_text(encoding="utf-8")
    # Producer must write the pack members and assemble the manifest.
    for marker in ("00-context/evidence.yaml", "00-context/sources.md", "pack-manifest", "pack-validate"):
        assert marker in body, f"context-import skill missing pack marker {marker!r}"
    # Must not re-impose the single-page limitation the engine has outgrown.
    assert "Keep it a **single page**" not in body, "single-page wiki limitation reintroduced"
    # The writes: frontmatter must advertise the pack files it now produces.
    fm, _ = frontmatter.read(str(REPO_ROOT / "skills" / "pm-context-import" / "SKILL.md"))
    writes = fm.get("writes") or []
    assert "00-context/manifest.yaml" in writes and "00-context/evidence.yaml" in writes


def test_context_import_skill_has_interview_step():
    """pm-context-import must place the coverage-driven interview between preflight and 00u."""
    body = (REPO_ROOT / "skills" / "pm-context-import" / "SKILL.md").read_text(encoding="utf-8")
    assert "Step 4b" in body and "Interview" in body
    assert "preflight yields ⚠️/⛔" in body
    assert "coverage-driven" in body
    assert "batched by topic" in body
    assert "strictly decreasing order of impact" in body
    assert "provided sources don't already answer" in body
    assert "not a fixed count" in body or "not a fixed numeric total" in body
    assert "fixed numeric total" in body
    assert "record-interview" in body
    assert "PM_OS_INTERVIEW" in body
    assert "known unknown" in body
    assert "Do not self-approve" in body or "do not self-approve" in body
    assert "exactly 5" not in body
    assert "five-question maximum" not in body

    data = yaml.safe_load((REPO_ROOT / "skills" / "pm-context-import" / "agents" / "openai.yaml").read_text(encoding="utf-8"))
    interface = data.get("interface", {}) if isinstance(data, dict) else {}
    assert "interview" in interface.get("default_prompt", "").lower()
    assert "known unknown" in interface.get("default_prompt", "").lower()


def test_context_import_skill_has_e2_decision_interview():
    """E2 codebase intake asks unresolved decisions and records the binding boundary."""
    body = (REPO_ROOT / "skills" / "pm-context-import" / "SKILL.md").read_text(encoding="utf-8")
    for marker in (
        "Step 4c — Enhancement decision interview",
        "production baseline",
        "current→target behavior",
        "affected and explicit non-touch surfaces",
        "regression invariants",
        "compatibility/migration",
        "rollout/rollback",
        "decision authority",
        "Do not re-ask cited code facts",
        "blocking unknown",
        "pm_enhance.py set-boundary",
        "Do not self-approve",
    ):
        assert marker in body, f"context-import missing E2 interview marker {marker!r}"
    assert "repo-interview-prep" not in body

    data = yaml.safe_load((REPO_ROOT / "skills" / "pm-context-import" / "agents" / "openai.yaml").read_text(encoding="utf-8"))
    prompt = (data.get("interface") or {}).get("default_prompt", "")
    assert "enhancement decision interview" in prompt.lower()


def test_pm_interview_skill_contract():
    """E3: the standalone /pm-interview skill drives list-unknowns → record-interview → resolve,
    keeps the coverage-driven interview contract, and never self-approves."""
    sd = REPO_ROOT / "skills" / "pm-interview"
    assert (sd / "SKILL.md").exists(), "pm-interview SKILL.md missing"
    body = (sd / "SKILL.md").read_text(encoding="utf-8")
    # reads the open unknowns from the mechanical helper
    assert "list-unknowns" in body
    # reuses E1 answer-registration, then marks the addressed unknowns resolved
    assert "record-interview" in body
    assert "resolve" in body
    # rerun answers are recorded once (no double-counted intake event) — Codex P2
    assert "--mode rerun" in body
    # reconciles answers against the context understanding rather than silently absorbing them,
    # and recommends regenerating the context pack so answers reach downstream generation — Codex P1
    assert "00-context-understanding.md" in body
    assert "contradict" in body
    assert "regenerat" in body
    # coverage-driven interview contract (mirrors the E1 Step 4b contract)
    assert "coverage-driven" in body
    assert "strictly decreasing order of impact" in body
    assert "not a fixed count" in body or "not a fixed numeric total" in body
    assert "known unknown" in body
    # non-interactive escape + gate discipline
    assert "PM_OS_INTERVIEW" in body
    assert "Do not self-approve" in body or "do not self-approve" in body

    data = yaml.safe_load((sd / "agents" / "openai.yaml").read_text(encoding="utf-8"))
    interface = data.get("interface", {}) if isinstance(data, dict) else {}
    assert "$pm-interview" in interface.get("default_prompt", "")
    assert "known unknown" in interface.get("default_prompt", "").lower()


def test_pm_enhance_skill_contract():
    """E2: /pm-enhance owns same-project lifecycle while preserving normal gates."""
    sd = REPO_ROOT / "skills" / "pm-enhance"
    assert (sd / "SKILL.md").exists(), "pm-enhance SKILL.md missing"
    body = (sd / "SKILL.md").read_text(encoding="utf-8")
    for marker in (
        "same project",
        "pm_enhance.py start",
        "pm_enhance.py set-boundary",
        "pm_enhance.py delta",
        "pm_enhance.py complete",
        "read-only",
        "00-codebase-understanding.md",
        "new | modified | removed",
        "ui | api | data | service | event | integration | operations",
        "project_type",
        "Do not self-approve",
    ):
        assert marker in body, f"pm-enhance missing contract marker {marker!r}"
    assert "child project" in body
    assert "repo-interview-prep" not in body

    data = yaml.safe_load((sd / "agents" / "openai.yaml").read_text(encoding="utf-8"))
    interface = data.get("interface", {}) if isinstance(data, dict) else {}
    assert "$pm-enhance" in interface.get("default_prompt", "")
    assert "same project" in interface.get("default_prompt", "").lower()


def test_codebase_scan_skill_has_e2_inventory_and_impact_contract():
    """E2: the portable scanner owns inventory, bounded focus, and widening evidence."""
    body = (REPO_ROOT / "skills" / "pm-context-scan-codebase" / "SKILL.md").read_text(encoding="utf-8")
    for marker in (
        "Repository identity",
        "Inventory & ownership boundaries",
        "Enhancement ask",
        "Affected slice",
        "Impact cone",
        "Explicit non-touch surfaces",
        "Coverage, exclusions & confidence",
        "scan start SHA",
        "scan end SHA",
        "read-only",
        "widen",
        "pm_codebase_inventory.py",
    ):
        assert marker in body, f"codebase scan missing E2 marker {marker!r}"
    assert "repo-interview-prep" not in body


def test_stage_skills_implement_e2_behavior_table():
    """E2: every canonical stage carries its surface-aware affected-slice obligation."""
    required = {
        "01": (
            "active enhancement context", "current-product gap", "delta success hypothesis",
            "carry unaffected content forward",
        ),
        "02": (
            "Change Boundary", "Affected-surface matrix", "Explicit non-touch boundary",
            "smallest coherent enhancement slice", "carry unaffected content forward",
        ),
        "03": (
            "new | modified | removed", "current→target behavior", "Affected surfaces:",
            "backward compatibility", "mixed-version", "carry unaffected content forward",
        ),
        "04": (
            "Surface-aware enhancement design", "API/data/service/event/integration/operations",
            "Never invent UI", "carry unaffected content forward",
        ),
        "05": (
            "Surface-aware enhancement validation", "API examples/mock contract",
            "operational drill/runbook", "Generate HTML only when UI is affected",
            "carry unaffected content forward",
        ),
        "06": (
            "impact-based regression class", "approved regression invariants",
            "migration/backfill", "mixed versions", "carry unaffected content forward",
        ),
        "07": (
            "baseline-status → target", "guardrails for existing outcomes",
            "rollout/rollback triggers", "carry unaffected content forward",
        ),
        "08": (
            "change-set against existing architecture", "delta-only tasks",
            "migration/backfill", "deployment/rollback", "carry unaffected content forward",
        ),
        "09": (
            "enhancement rollout and follow-on horizons only", "do not roadmap the whole product",
            "carry unaffected content forward",
        ),
    }
    for stage_id, markers in required.items():
        body = (stage_skill_dir(stage_id) / "SKILL.md").read_text(encoding="utf-8")
        for marker in markers:
            assert marker in body, f"stage {stage_id} missing E2 marker {marker!r}"


def test_prototype_html_uses_interaction_model_not_genai_flag():
    body = (REPO_ROOT / "skills" / "pm-prototype-html" / "SKILL.md").read_text(encoding="utf-8")
    assert "Interaction model" in body
    assert "?review=1" in body
    assert "review-only" in body
    assert "Never introduce an AI affordance solely because `genai_flag=true`" in body
    assert "pm_validate_artifact.py 05-html --mode strict" in body
