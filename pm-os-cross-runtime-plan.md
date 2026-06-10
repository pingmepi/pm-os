# PM-OS Cross-Runtime Compatibility Plan

**Status:** Draft / proposal — not yet implemented.
**Author:** Karan (with Claude Code)
**Date:** 2026-06-10
**Scope:** Make PM-OS runnable under OpenAI Codex and Gemini CLI in addition to Claude Code, without forking the prompt content or the deterministic core.

> **Revision note (2026-06-10):** An earlier draft of this plan assumed only Claude Code had a skill-discovery system and that Codex/Gemini would need prompt-flattening or TOML translation. That was wrong. As of 2026, **Codex, Gemini CLI, and Claude Code have all converged on the Anthropic-style Agent Skills format** — a `SKILL.md` with `name`/`description` frontmatter in a skill directory, plus optional `scripts/`. Codex's skill spec even includes an optional `agents/openai.yaml`, which PM-OS already ships in every stage. The real work is therefore much smaller than first estimated: install targets and a few Claude-only idioms, **not** format translation. Sources are listed in §10.

---

## 1. The convergence that makes this easy

PM-OS already ships in the de-facto cross-runtime skill format. Each stage directory is:

```
skills/<stage>/
├── SKILL.md            (name + description frontmatter + body)   ← required by all three runtimes
├── agents/openai.yaml  (display_name, short_description, default_prompt)  ← Codex skill spec
```

That is **exactly** the structure Codex and Gemini CLI expect. The only required frontmatter on all three runtimes is `name` + `description`, both of which every PM-OS `SKILL.md` already has. PM-OS's extra frontmatter (`reads`, `writes`, `prompt_version`, `model`) is non-standard but should be ignored by runtimes that only read `name`/`description` (to be confirmed — see §5, Step 0).

### Skill format and location per runtime

| | Claude Code | OpenAI Codex | Gemini CLI |
|---|---|---|---|
| **Skill unit** | `SKILL.md` dir | `SKILL.md` dir | `SKILL.md` dir |
| **Required frontmatter** | name, description | name, description | name, description |
| **Scripts** | `scripts/` | `scripts/` | `scripts/` |
| **Interface descriptor** | — | `agents/openai.yaml` (optional) | — |
| **User install path** | `~/.claude/skills/` | `~/.codex/skills/` *or* `~/.agents/skills/` | `~/.gemini/skills/` *or* `~/.agents/skills/` |
| **Repo install path** | `.claude/skills/` | `.agents/skills/` | `.gemini/skills/` *or* `.agents/skills/` |
| **Invocation** | `/skill-name` | `/skills` picker, `$name` mention | `/skill-name`, `$name` |
| **Custom prompts** | n/a | **deprecated → use skills** | n/a |

**Key opportunity:** Both Codex and Gemini CLI honor a shared **`~/.agents/skills/`** alias. A single install to that path may cover both runtimes at once — to be verified in Step 0.

### Hooks per runtime — also broadly compatible

All three now have real lifecycle-hook systems with similar shapes (command hooks, JSON on stdin/stdout):

| | Claude Code | Codex | Gemini CLI |
|---|---|---|---|
| **Config** | `settings.json` hooks | `~/.codex/hooks.json` or `[hooks]` in `config.toml` | `hooks/hooks.json` in an extension |
| **Events** | SessionStart, PreToolUse, PostToolUse, Stop, … | SessionStart, PreToolUse, PermissionRequest, PostToolUse, PreCompact/PostCompact, UserPromptSubmit, SubagentStart/Stop, Stop | hook events via extension `hooks.json` |
| **I/O** | JSON stdin → JSON stdout | JSON stdin → JSON stdout (`continue`, `stopReason`, `systemMessage`) | intercept/customize via hooks |

**Important:** PM-OS does **not** currently use any runtime's native lifecycle hooks. Its `pre-stage.py` / `post-approve.py` are invoked **explicitly from the skill body** (`python3 ~/.pm-os/hooks/pre-stage.py` with `PM_OS_STAGE` set). That explicit pattern already works on every runtime that can run shell — so native hook wiring is an **optional enhancement**, not a prerequisite.

---

## 2. Target runtimes and verdicts

| Runtime | Verdict | Reason |
|---|---|---|
| **Claude Code** | ✅ Works today | Native skill suite. Baseline. |
| **OpenAI Codex** | ✅ Near-compatible | Same skill format (incl. `agents/openai.yaml`). Needs an install path + real `AGENTS.md` + de-interactive hook + model-block rewording. **No format translation.** |
| **Gemini CLI** | ✅ Near-compatible | Same skill format; `gemini skills install` from a local dir or git. Shares the `~/.agents/skills/` alias with Codex. Same small fixes as Codex. |
| **Gemini AI Studio** | ❌ Out of scope | Web playground — no filesystem, shell, git, or skill system. PM-OS is local-first by definition; its stateful guarantees cannot run here. **Target Gemini CLI instead.** |

---

## 3. Gap inventory (what actually blocks non-Claude runtimes)

Reduced from the original draft, because the skill format is shared:

1. **`AGENTS.md` is a stub.** It holds only claude-mem context, not PM-OS workflow instructions. Codex and Gemini CLI both read `AGENTS.md` as a primary instruction file (Codex walks root→leaf). Highest-leverage single fix.
2. **No install path for Codex/Gemini.** `install.sh` hard-requires the `claude` binary and copies only to `~/.claude/skills/` + `~/.claude/hooks/`. Needs per-runtime (or `~/.agents/skills/`) targets.
3. **Unverified frontmatter tolerance.** PM-OS `SKILL.md` carries non-standard fields (`reads`, `writes`, `prompt_version`, `model`). Must confirm Codex/Gemini ignore them rather than erroring.
4. **Interactive `input()` in `hooks/pre-stage.py`** (the implicit-reapproval prompt). Non-interactive Codex/Gemini runs will hang or hit EOF. Needs a TTY check + env/flag fallback.
5. **`/model opus` advisory blocks** (stages 03 PRD, 06 QA Plan) are Claude-only syntax. Codex/Gemini select models via config/flags. Needs runtime-neutral rewording.
6. **Telemetry `model` field** is phrased "the model id you are currently running as" (Claude-framed). Make it runtime-agnostic so Codex/Gemini populate it correctly.

Removed from the original draft (no longer real gaps): "flatten skills to `~/.codex/prompts/`" (custom prompts are deprecated; skills are the path) and "translate to `.gemini/commands/*.toml`" (Gemini CLI uses the same `SKILL.md` skill format).

---

## 4. Proposed design: one source, copy to runtime paths

Keep `skills/*/SKILL.md`, `lib/`, `scripts/`, `hooks/`, and `templates/` as the **single source of truth**. The installer **copies the same skill directories** to whichever runtime path is requested — no per-runtime content transformation.

```
skills/<stage>/  (single source, already in cross-runtime format)

install.sh --runtime claude  → copy skill dirs → ~/.claude/skills/
install.sh --runtime codex   → copy skill dirs → ~/.codex/skills/   (or ~/.agents/skills/)
install.sh --runtime gemini  → copy skill dirs → ~/.gemini/skills/  (or ~/.agents/skills/)
install.sh --runtime agents  → copy skill dirs → ~/.agents/skills/  (covers Codex + Gemini at once, if verified)
```

- **AGENTS.md** = the shared, runtime-neutral system instruction (pipeline overview, local-first state model, approval discipline, stage-invocation table). Claude Code ignores it harmlessly; Codex and Gemini CLI consume it.
- **Python core / hooks / templates** continue to live at the runtime-neutral `~/.pm-os/` and are invoked by absolute path from the prompts — already works, no per-runtime change.
- **Native lifecycle hooks** (Claude `settings.json`, Codex `hooks.json`, Gemini extension `hooks/hooks.json`) are an optional later enhancement; the explicit-invocation pattern is the portable baseline.

---

## 5. Implementation steps (proposed — not yet executed)

Independently shippable; ordered by leverage.

### Step 0 — Verify format tolerance (spike, ~1–2 hrs)
- Install one stage skill unchanged into `~/.codex/skills/` and `~/.gemini/skills/` (or `~/.agents/skills/`). Confirm: (a) the runtime discovers it, (b) the extra frontmatter fields don't cause errors, (c) `$pm-stage-01-brief` / `/skills` invocation works, (d) the explicitly-invoked Python hook runs.
- **Output:** a go/no-go on "copy unchanged" vs "needs a frontmatter shim." De-risks every later step.

### Step 1 — Write a real `AGENTS.md`
- **Files:** `AGENTS.md` (replace stub).
- **Content:** 7-stage pipeline overview, local-first state model (`.meta.yaml`, artifact files, `.history/`, telemetry/feedback JSONL), approval-gate discipline, and a stage-invocation table (`$pm-stage-NN-...`). Runtime-neutral wording.
- **Benefit:** improves Codex + Gemini CLI behavior immediately, before installer work lands.

### Step 2 — De-interactive `hooks/pre-stage.py`
- **Files:** `hooks/pre-stage.py`.
- **Change:** detect non-TTY (`sys.stdin.isatty()`); when non-interactive, honor `PM_OS_REAPPROVE=continue|halt` (default `halt` for safety) instead of `input()`. Keep current interactive behavior when a TTY is present.
- **Benefit:** unblocks non-interactive runs on all runtimes; no change under Claude Code.

### Step 3 — Neutralize model-selection idioms
- **Files:** `skills/pm-stage-03-prd/SKILL.md`, `skills/pm-stage-06-qa-plan/SKILL.md`, and the telemetry `model` instruction across all stage skills.
- **Change:** reword the "Model requirement" pre-flight from `/model opus` to runtime-neutral guidance ("this stage benefits from a top-tier model; select your runtime's strongest model before generating"). Make the telemetry `model` field read generically ("the model id of the current runtime/session").
- **Benefit:** prompts stop emitting Claude-only commands elsewhere.

### Step 4 — Add per-runtime install targets
- **Files:** `install.sh` (add `--runtime {claude|codex|gemini|agents}`, default `claude`); optionally a small `scripts/sync_runtime.py` for path resolution.
- **Change:**
  - Resolve the destination skill dir per runtime (table in §4); copy skill dirs unchanged (pending Step 0).
  - Drop the hard `claude`-binary requirement when a non-Claude target is selected; check for `codex` / `gemini` instead.
  - All targets still install the Python core/hooks/templates to `~/.pm-os/` and write `~/.pm-os/config.yaml`.
  - For Gemini, optionally support `gemini skills install <repo-or-path>` as an alternative install route.
- **Benefit:** real, installable cross-runtime support.

### Step 5 — (Optional) Wire native lifecycle hooks
- **Files:** runtime hook configs (Claude `settings.json`, Codex `~/.codex/hooks.json`, Gemini extension `hooks/hooks.json`).
- **Change:** expose `pre-stage` as a `UserPromptSubmit`/`PreToolUse`-style gate and `post-approve` as a `Stop`/`PostToolUse` step, reading PM-OS state from the JSON stdin payload. Only worth doing after Steps 0–4 prove the explicit pattern; this is UX polish, not correctness.
- **Benefit:** tighter, more "native" feel per runtime.

### Step 6 — Verify end-to-end + document
- **Files:** `README.md` (add a "Runtimes" section), `pm-os-spec.md` (reconcile §300 cross-runtime notes with the implemented adapter).
- **Change:** run `/pm-new` → `/pm-stage-01-brief` → `/pm-approve 01` under Codex and Gemini CLI; capture drift. Document per-runtime install commands and known limits.
- **Benefit:** turns "should work" into "verified," and records the install UX.

---

## 6. Explicit non-goals

- **Gemini AI Studio** support (wrong product category — §2).
- **Mandatory native lifecycle hooks.** The explicit-invocation pattern is the portable baseline; native hooks are Step 5 polish only.
- **A unified MCP server.** All three runtimes support MCP, but PM-OS's local-file model doesn't need it. Out of scope absent a remote/multi-machine requirement.
- **Prompt content forking.** Single source of truth (`SKILL.md`) is a hard constraint; the installer copies, it does not transform content.

---

## 7. Effort and risk (revised down)

- **Estimated effort:** ~0.5–1 day for Steps 0–4 (was ~1–1.5 days). Step 0 spike + Step 1 (AGENTS.md) + Step 2 (hook) are hours each; Step 4 (installer) is the largest piece but is mostly path resolution + copy, not translation. Step 5 is optional and additive.
- **Primary risk:** Codex/Gemini reject or mis-handle PM-OS's non-standard frontmatter. **Mitigation:** Step 0 spike validates this before any broader work; if rejected, add a thin install-time frontmatter filter (strip to `name`/`description` for non-Claude targets) rather than forking content.
- **Secondary risk:** runtimes interpret prompt instructions differently (argument parsing, file-write conventions). **Mitigation:** Step 6 end-to-end verification per runtime before declaring support.

---

## 8. Suggested sequencing for approval

Independent; recommend landing incrementally:

0. Format-tolerance spike (Step 0) — de-risks everything; do first.
1. `AGENTS.md` (Step 1) — standalone, immediate benefit.
2. `pre-stage.py` de-interactive (Step 2) — small, safe, unblocks automation.
3. Model-idiom neutralization (Step 3) — prompt-only edits.
4. Installer runtime targets (Step 4) — the core feature.
5. (Optional) Native hooks (Step 5) — polish.
6. Verification + docs (Step 6) — closes the loop.

Awaiting approval before implementing any of the above.

---

## 9. Open questions to resolve during Step 0

- Does Claude Code also read `~/.agents/skills/`? If so, a single `--runtime agents` install could cover all three.
- Do Codex/Gemini error on, or silently ignore, the extra `SKILL.md` frontmatter (`reads`, `writes`, `prompt_version`, `model`)?
- Does the `$pm-stage-NN-...` mention syntax in `agents/openai.yaml`'s `default_prompt` resolve identically on Codex and Gemini?
- Is `~/.codex/skills/` or `~/.agents/skills/` the canonical Codex user path? (Docs reference both — confirm precedence.)

---

## 10. Sources (verified 2026-06-10)

- Codex — Agent Skills: https://developers.openai.com/codex/skills
- Codex — Hooks: https://developers.openai.com/codex/hooks
- Codex — Custom Prompts (deprecated → skills): https://developers.openai.com/codex/custom-prompts
- Codex — AGENTS.md: https://developers.openai.com/codex/guides/agents-md
- Codex — Configuration Reference: https://developers.openai.com/codex/config-reference
- Gemini CLI — Agent Skills: https://geminicli.com/docs/cli/skills/
- Gemini CLI — Creating Skills: https://geminicli.com/docs/cli/creating-skills/
- Gemini CLI — Extension reference (hooks): https://geminicli.com/docs/extensions/reference/
