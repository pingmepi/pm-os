# PM-OS Cross-Runtime Compatibility Plan

**Status:** ✅ **Largely implemented (v0.4.4–0.4.6).** Claude + Codex runtime parity shipped: `install.sh --runtime claude|codex`, per-skill `agents/openai.yaml`, runtime-neutral `AGENTS.md` and model guidance, non-interactive-safe gates, and the `pm-os-verify` install verifier. **Only Gemini support remains** (deferred to a later phase). Verified against the codebase 2026-06-17.
**Author:** Karan (with Claude Code)
**Date:** 2026-06-11
**Scope:** Keep PM-OS fully compatible with Claude Code and OpenAI Codex without forking the skill content or the deterministic Python core.

> **Revision note (2026-06-11):** This document treats Claude Code and Codex as peer supported runtimes. The prior draft was right that PM-OS already uses the correct skill shape, but it understated several Codex blockers and used the wrong Codex install path in a few places. The work is still much smaller than a prompt-port, but it is broader than "add AGENTS.md and de-interactive `pre-stage.py`." All proposed changes below should preserve Claude behavior while removing provider-specific assumptions from shared config and skill metadata.

---

## 1. Runtime parity principle

Claude Code and OpenAI Codex are peer PM-OS runtimes:

- existing install and update flows must continue to work for Claude users
- install and update flows must work for Codex users without requiring Claude
- existing skill content remains the source of truth
- shared config and shared skill metadata must stay provider-neutral

That means the implementation rule for this plan is:

- prefer runtime-neutral wording where possible
- where behavior truly differs, add runtime-aware paths rather than replacing the Claude path
- do not regress the current Claude UX while making Codex first-class

---

## 2. What already aligns with Codex

PM-OS already ships in Codex's native skill format:

```text
skills/<skill-name>/
├── SKILL.md
└── agents/openai.yaml   # optional Codex descriptor, already present on stage skills
```

That matches the Codex skill model:

- A skill is a directory containing `SKILL.md` plus optional `scripts/`, `references/`, `assets/`, and `agents/`.
- `SKILL.md` requires `name` and `description`.
- `agents/openai.yaml` is optional, not a translation target.

This means PM-OS does **not** need:

- prompt flattening into deprecated custom prompts
- TOML command translation
- a parallel Codex-only skill tree

The current explicit-hook pattern is also portable enough for Codex:

- PM-OS invokes `~/.pm-os/hooks/pre-stage.py` directly from skill instructions.
- Codex hooks exist, but PM-OS does not need them for baseline correctness.
- Native Codex hooks are therefore an enhancement, not a prerequisite.

---

## 3. Runtime verdict

| Runtime | Verdict | Reason |
|---|---|---|
| **Claude Code** | ✅ Works today | Current baseline and must remain so. |
| **OpenAI Codex** | ⚠️ Not yet smooth | Skill format is compatible, but install/discovery, stdin assumptions, Claude-specific guidance, and updater/config behavior still need additive support. |

For this pass, Codex is the only new target. Gemini can be revisited later once the Claude + Codex path is implemented and verified.

---

## 4. What blocks Codex today

These are the concrete gaps in the current repo.

1. **`AGENTS.md` is effectively empty for Codex.**  
   The root [AGENTS.md](../../AGENTS.md) contains only the claude-mem wrapper. Codex reads `AGENTS.md` before work and walks from project root to cwd, so PM-OS is currently missing its main repository-level instruction surface in Codex.

2. **The prior plan used the wrong Codex skill install target.**  
   The Codex docs describe repo-local `.agents/skills/` and user-level `~/.agents/skills/` discovery. The earlier draft referred to `~/.codex/skills/`, which should not be treated as canonical unless verified separately.

3. **Codex-facing invocation guidance is still Claude-shaped.**  
   PM-OS docs and script output repeatedly tell the user to run slash commands such as `/pm-stage-01-brief` and `/pm-approve 01`. In Codex, the reliable skill entrypoints are the `/skills` picker and `$skill-name` mentions. The plan must update validation steps and user-facing copy accordingly.

4. **Interactive stdin is a repo-wide issue, not just a `pre-stage.py` issue.**  
   `input()` currently appears in:
   - `hooks/pre-stage.py`
   - `scripts/pm_new.py`
   - `scripts/pm_os_install.py`
   - `scripts/pm_feedback.py`
   - `lib/config.py`

   Codex can run interactively, but "as smooth as Claude" requires these flows to behave predictably in non-interactive and automation-oriented sessions too. Today some of them hang, and some silently fall back to defaults.

5. **Installer and updater logic are hard-coded to Claude paths and messaging.**  
   `install.sh` only installs to `~/.claude/skills/` and `~/.claude/hooks/`, requires the `claude` binary, and prints Claude-specific next steps. `scripts/pm_os_update.py` only re-syncs Claude directories and prints Claude restart instructions.

6. **Config defaults and model metadata are provider-specific.**  
   Older config wrote `default_stage_model: claude-sonnet-4-6` and `opus_stages`, which makes a shared PM-OS install assume Claude model names. Shared config should instead store runtime-neutral model tiers.

7. **Claude-only model-switch instructions existed in more places than the prior plan captured.**  
   The earlier draft mentioned stages 03 and 06, but stage 08 also contained the same `/model opus` advisory block. This has since been cleaned up: stages 03, 06, and 08 now use runtime-neutral advisory `model_tier: deep-reasoning` guidance.

8. **Skill frontmatter tolerance should still be verified.**  
   PM-OS `SKILL.md` files include non-standard frontmatter keys such as `reads`, `writes`, `prompt_version`, and `model_tier`. Codex likely ignores unknown keys, but support should not be declared until that is verified in a real install.

9. **Codex may prefer skill-local `scripts/`, while PM-OS uses a shared top-level `scripts/` directory.**  
   Codex documents `scripts/` as an optional folder inside the skill directory, but PM-OS currently calls shared scripts from outside individual skill folders. That may still work if paths are referenced correctly, but it should be treated as a compatibility question to verify, not an assumption. The intended solution is **not** duplicating script logic. If Codex needs a more self-contained skill layout, use thin wrappers or symlinks from each skill directory back to the shared implementation.

---

## 5. Target cross-runtime design

Keep the existing PM-OS repository structure as the single source of truth:

```text
skills/*/SKILL.md
skills/*/agents/openai.yaml
hooks/*.py
scripts/*.py
lib/*.py
templates/*
```

Adopt these runtime behaviors:

- **Repository instructions:** write a real root `AGENTS.md` that explains the PM-OS workflow, state model, approval discipline, and both Claude/Codex invocation expectations.
- **Claude install path:** keep Claude installs targeting `~/.claude/skills/` and the existing Claude hooks location.
- **Codex install path:** add installation into `~/.agents/skills/` for user-level Codex discovery.
- **Optional repo-local development path:** support `.agents/skills/` inside the repo for local testing if useful.
- **Skill invocation guidance:** document Claude usage with existing slash commands, and Codex usage via `/skills` and `$pm-...` mentions.
- **Portable helpers:** keep the Python core in `~/.pm-os/` and make all helper scripts safe when stdin is unavailable.
- **Single script implementation:** keep the shared top-level `scripts/` directory as the source of truth. If Codex needs skill-local script packaging for better portability, add thin wrappers or symlinked `scripts/` directories inside skills rather than duplicating implementation.

Native Codex lifecycle hooks remain optional. Baseline PM-OS compatibility should come from explicit shell invocation inside each skill, not from Codex hook configuration.

---

## 6. Implementation steps

### Step 0 — Verify unchanged skill discovery in Codex

- Install one PM-OS skill unchanged into `~/.agents/skills/`.
- Confirm Codex discovers it in `/skills`.
- Confirm Codex can invoke it via `$skill-name`.
- Confirm the existing `agents/openai.yaml` is accepted.
- Confirm extra `SKILL.md` frontmatter keys are ignored rather than rejected.
- Confirm an explicit shell call such as `python3 ~/.pm-os/hooks/pre-stage.py` runs successfully from a skill.
- Confirm whether Codex is happy with PM-OS skills referencing shared scripts outside the individual skill directory.

**Output:** go/no-go on "copy unchanged" as the Codex install model, including whether external shared-script references are acceptable as-is.

### Step 1 — Replace the root `AGENTS.md` stub with real PM-OS guidance

**Files:** `AGENTS.md`

Add repo instructions that preserve Claude as the baseline while teaching Codex how to behave:

- 7-stage pipeline overview
- local-first project state (`.meta.yaml`, artifacts, `.history/`, telemetry, feedback)
- approval and regeneration rules
- expectations for running helper scripts from inside a PM-OS project
- Claude invocation guidance: existing PM-OS slash commands remain valid in Claude
- Codex skill invocation guidance: use `/skills` or `$pm-...`
- explicit note that PM-OS shell commands may write local files and should be allowed when the user requested PM-OS work

This is the highest-leverage single improvement for Codex behavior.

### Step 2 — Remove stdin dependence from helper flows

**Files:** `hooks/pre-stage.py`, `scripts/pm_new.py`, `scripts/pm_os_install.py`, `scripts/pm_feedback.py`, `lib/config.py`

Changes:

- Detect non-TTY sessions before calling `input()`.
- Add explicit flags and/or env vars for decisions that currently require prompts.
- Default to safe failure where silent fallback would be dangerous.
- Avoid quietly forcing `genai_flag=false` on EOF in `pm_new.py`.
- Keep the interactive UX intact when a TTY is available.

This step matters more than hooks alone because Codex users will hit project creation, install/reconfigure, and feedback capture too.

### Step 3 — Make wording runtime-aware without breaking Claude

**Status:** Implemented for model guidance in stages 03, 06, and 08. Keep this checklist for future prompt copy that introduces runtime-specific commands.

**Files:** covered:

- `skills/pm-stage-03-prd/SKILL.md`
- `skills/pm-stage-06-qa-plan/SKILL.md`
- `skills/pm-stage-08-trd/SKILL.md`
- any skill or script output that tells the user to run `/pm-*` or a runtime-specific model command

Changes:

- Replace runtime-specific model-switch instructions with wording that still helps Claude users but is not wrong in Codex.
- Reword "the model you are currently running as" to "the current session model id" or equivalent.
- Update user-facing next-step strings so Claude users still see Claude-friendly guidance and Codex users are not told to use Claude-only command forms.

The goal is not to erase Claude support; it is to remove text that is wrong in Codex while keeping Claude guidance intact.

### Step 4 — Add Codex-aware install and sync targets without regressing Claude

**Files:** `install.sh`, `scripts/pm_os_update.py`, possibly a shared sync helper

Changes:

- Add a runtime selector, at least `claude` and `codex`.
- Keep the current Claude install/update path working as it does today.
- For Codex, install skills to `~/.agents/skills/`.
- Do not require the `claude` binary when the selected runtime is Codex.
- Keep installing the runtime-neutral PM-OS core to `~/.pm-os/`.
- Add Codex-aware re-sync logic to `pm_os_update.py` alongside the existing Claude sync logic.
- Print runtime-specific post-install instructions.
- If Step 0 shows Codex wants a more self-contained skill layout, install skill-local wrappers or symlinked `scripts/` directories that point at the shared top-level implementation. Do not duplicate business logic across skills.

Without this step, Codex support remains manual and brittle even if the skills themselves are compatible.

### Step 5 — Make config/runtime metadata additive

**Files:** `scripts/pm_os_install.py`, `lib/config.py`, any docs that describe default model policy

Changes:

- Remove concrete provider model ids from shared config and shared skill frontmatter.
- Store runtime-neutral policy metadata:
  - `default_model_tier: standard`
  - `deep_reasoning_stages: ["00w", "00u", "03", "04", "06", "08", "09"]`
- Keep the deep-reasoning model-tier semantics for those stages without making shared config assume any provider.
- Keep Claude pathways working through runtime-specific instructions only: Claude users map `deep-reasoning` to Opus or the strongest available reasoning model; Codex users map it to a high/deep reasoning model.

### Step 6 — Verify end-to-end in Codex and document the exact UX

**Files:** `README.md`, `../reference/pm-os-spec.md`, this plan if needed

Validation flow should use Codex-native invocation, for example:

1. Install skills into `~/.agents/skills/`
2. Start Codex in a PM-OS workspace
3. Invoke `pm-new` through `/skills` or `$pm-new`
4. Generate stage 01 via `/skills` or `$pm-stage-01-brief`
5. Approve stage 01 using the Codex-supported PM-OS entrypoint
6. Confirm helper scripts, writes, and approval gates behave correctly

Document:

- that Claude and Codex are both supported runtimes
- supported install path
- supported invocation patterns
- known limitations
- whether Codex hooks were needed or not

### Step 7 — Optional native Codex hook integration

**Files:** `~/.codex/hooks.json` examples or documented `config.toml` snippets

Only consider this after Steps 0–6 work. If implemented, use it for polish:

- session reminders
- extra safety messaging
- workflow nudges

Do **not** make Codex hooks a baseline dependency for PM-OS.

---

## 7. Suggested landing order

1. Step 0 — verify Codex skill discovery and frontmatter tolerance
2. Step 1 — write real `AGENTS.md`
3. Step 2 — remove stdin dependence from helper flows
4. Step 3 — clean up Claude-only wording
5. Step 4 — ship Codex install/sync support
6. Step 5 — neutralize config/runtime metadata
7. Step 6 — verify end-to-end and document
8. Step 7 — optional hooks polish

This order front-loads the pieces that most affect whether Codex feels reliable and predictable while keeping Claude stable.

---

## 8. Non-goals for this pass

- Gemini CLI / AI Studio support — **deferred to a later pass, not abandoned.** Gemini remains a planned runtime target (see `docs/roadmap/current-state-review.md`); it is out of scope only for *this* Claude + Codex pass.
- a mandatory Codex hooks integration
- prompt forking or skill duplication
- replacing the local-file PM-OS architecture with MCP or a service backend

---

## 9. Open questions to answer during implementation

- Does Codex accept the current PM-OS `SKILL.md` frontmatter unchanged?
- Does `agents/openai.yaml` add meaningful UX for PM-OS skills in Codex, or is it merely tolerated?
- Should Codex support rely only on user-level `~/.agents/skills/`, or should repo-local `.agents/skills/` be part of the documented dev workflow too?
- Are direct references from a skill to shared parent-level scripts fully reliable in Codex, or should PM-OS install wrappers/symlinks inside each skill directory?
- What is the right non-interactive behavior for `pm_new.py` when `--genai/--no-genai` is omitted?
- Should PM-OS add runtime-specific examples for additional model providers, while keeping config provider-neutral?
- Which guidance should remain explicitly runtime-specific because it only applies to one runtime?

---

## 10. Sources (verified 2026-06-11)

- Codex — Agent Skills: https://developers.openai.com/codex/skills
- Codex — AGENTS.md: https://developers.openai.com/codex/guides/agents-md
- Codex — Hooks: https://developers.openai.com/codex/hooks
- Codex — Configuration Reference: https://developers.openai.com/codex/config-reference
