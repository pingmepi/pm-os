# PM-OS — Fix Pass 1 Specification

**Owner:** Karan
**Target executor:** Claude Code
**Status:** ✅ **Completed and shipped** (verified against the codebase 2026-06-17). All four phases landed: Phase A — mechanical skills refactored to script wrappers (`scripts/`); Phase B — `config.yaml` migration + config-driven install flow (`lib/config.py`, `install.sh`); Phase C — gate hooks (`hooks/pre-stage.py`, `hooks/post-approve.py`); Phase D — install verifier (`scripts/pm_os_verify.py` + the `pm-os-verify` skill). Retained as a historical record; this is the doc destined for `docs/archive/`.
**Context:** PM-OS first-run dogfooding surfaced 12 issues across install correctness, missing components, performance, and UX. This document specifies a single fix pass that resolves all of them in coordinated order.

**Read first:** the original `pm-os-spec.md`. (Note: `pm-os-feedback-spec.md` is referenced here and elsewhere but does **not** exist in this repo — treat that reference as historical.) This document assumes familiarity with the spec. References to "the spec" mean `pm-os-spec.md` unless stated otherwise.

---

## 1. Scope of this fix pass

12 issues total, grouped into 4 work phases. Phases must be executed in order. Each phase has independent acceptance criteria — do not advance to the next phase until current phase passes its acceptance check.

**Do not** introduce features beyond what is specified here. **Do not** refactor code beyond what each issue requires. **Do not** modify the original spec; this document is the delta.

If you encounter ambiguity, stop and ask. Do not guess.

---

## 2. Sequencing rationale

The order below is deliberate. Doing it in this order means each subsequent phase is faster and easier to test:

1. **Phase A — Script refactor first.** Makes every subsequent test faster (fixes the 2m 44s wait on `pm-new`).
2. **Phase B — Config file + install flow.** Foundation for everything else. Touches files Phase A also touched, so batched.
3. **Phase C — Missing hooks + registration.** Cannot be tested until config and scripts work.
4. **Phase D — Verifier + UX polish.** Verifier requires everything else to exist first. UX polish is low-priority cleanup.

---

## 3. Phase A — Refactor mechanical skills to script wrappers

### Background

`pm-new` was observed taking 2m 44s of model thinking before performing a simple project scaffold operation. Root cause: utility skills are written as prose-driven flows where the model interprets requests, plans steps, and mediates interactive prompts. For mechanical operations (file I/O, YAML writes, hash compute, telemetry append), this is pure overhead.

### Scope

Eight of the 15 PM-OS skills are mechanical. They must be refactored to thin SKILL.md wrappers over Python CLI scripts living at `~/.pm-os/scripts/`.

**Skills to refactor (mechanical):**
- `pm-new`
- `pm-approve`
- `pm-status`
- `pm-feedback`
- `pm-share`
- `pm-os-install`
- `pm-os-update`
- `pm-os-verify` (will be created in Phase D, but follow this pattern when built)

**Skills to leave as model-driven (generative):**
- `pm-stage-01-brief`
- `pm-stage-02-scope`
- `pm-stage-03-prd`
- `pm-stage-04-design-spec`
- `pm-stage-05-prototype-brief`
- `pm-stage-06-qa-plan`
- `pm-stage-07-metrics-plan`

### Implementation pattern

**Directory addition:** create `~/.pm-os/scripts/` for the CLI scripts. One script per mechanical skill: `pm_new.py`, `pm_approve.py`, etc.

**Scripts use existing `lib/` modules.** Do not duplicate logic from `lib/`. Scripts are CLI wrappers; lib/ remains the source of truth.

**Script-level interactive prompts.** When a script needs user input (e.g., GenAI flag, feedback rating), it prompts directly via `input()` or `argparse`-supplied flags. The model is never the mediator.

**Argument convention:**
- Required positional args first
- Optional flags with sensible defaults
- For booleans needing user input: accept `--genai` AND `--no-genai`; if neither is passed, script prompts directly

**Example — `pm_new.py`:**
- Required positional: `<slug>` and `<statement>`
- Optional: `--genai` / `--no-genai`
- If neither flag passed, script prints prompt and reads from stdin
- Validates slug format, checks no existing project, scaffolds files, writes `.meta.yaml`, logs `project_created` telemetry event, prints one-line confirmation

**SKILL.md content for mechanical skills must be ruthlessly minimal:**

```markdown
---
name: pm-new
description: Scaffold a new PM-OS project.
model: <haiku model identifier — see verification step below>
---

Run: python3 ~/.pm-os/scripts/pm_new.py "$@"

Pass through all arguments verbatim. Do not interpret, validate, or reformat them.
Report the script's output as-is. Do not summarize, restructure, or add commentary
beyond a one-line confirmation that the script ran.
```

Any prose beyond this introduces reasoning time. Be ruthless.

### Pre-implementation verification step

Before setting `model: haiku` in any SKILL.md frontmatter, verify two things:

1. Confirm that Claude Code's current SKILL.md frontmatter supports a `model` field. Check docs or test with a simple skill.
2. Confirm the exact model identifier string for the current Haiku version (likely something like `claude-haiku-4-5` but verify — do not guess).

If `model` field is not supported in frontmatter, document this and proceed without it. The script refactor is the primary win; the model swap is icing.

### Files affected (Phase A)

- New: `~/.pm-os/scripts/pm_new.py`, `pm_approve.py`, `pm_status.py`, `pm_feedback.py`, `pm_share.py`, `pm_os_install.py`, `pm_os_update.py`
- Modified: `~/.pm-os/skills/<each mechanical skill>/SKILL.md` (strip prose, replace with script invocation)
- Unchanged: all `pm-stage-*` skills, all `lib/` modules, all hooks

### Phase A acceptance criteria

- [ ] All 7 mechanical scripts exist in `~/.pm-os/scripts/` and are executable
- [ ] All 7 mechanical SKILL.md files are ≤15 lines including frontmatter
- [ ] `pm-new` completes in under 10 seconds end-to-end (down from 2m 44s)
- [ ] `pm-new --genai` and `pm-new --no-genai` both work without interactive prompt
- [ ] `pm-new` without either flag prompts via the script (not the model) and continues in the same turn
- [ ] `pm-approve 01` completes in under 10 seconds
- [ ] Generative stage skills (`pm-stage-*`) are untouched

---

## 4. Phase B — Config file migration and install flow correctness

### Background

Two related problems:

1. **Env-var propagation:** `PM_OS_FEEDBACK_REPO` is written to `.zshrc` by install, but Python subshells spawned by Claude Code skills don't reliably inherit it. Confirmed: `PM_OS_USER` propagates; `PM_OS_FEEDBACK_REPO` was never written by the installer for unknown reasons.
2. **Install silently skipped steps:** Only `PM_OS_USER` got persisted. Install completion message gave no indication of partial configuration.

### Scope

Migrate from environment variables to a config file. Make install verify each step's effect immediately after performing it.

### Config file design

**Path:** `~/.pm-os/config.yaml`

**Schema:**
```yaml
schema_version: 1
pm_user: <string>                    # was PM_OS_USER
feedback_repo: <git url>             # was PM_OS_FEEDBACK_REPO; e.g., git@github.com:pingmepi/pm-os-feedback.git
projects_dir: <absolute path>        # default: ~/pm-projects
pm_os_version: <semver>              # from VERSION file at install time
default_stage_model: <model id>      # default: sonnet
opus_stages: ["03", "06"]            # which stages use opus
```

### Implementation requirements

**New module: `lib/config.py`**
- `load_config() -> dict` reads `~/.pm-os/config.yaml`, returns parsed dict
- Caches result for the lifetime of the process
- Raises a clear, actionable error if config is missing (with command to run to create it)
- Raises a clear error if required keys are missing

**Migration logic in `lib/config.py`:**
- If `~/.pm-os/config.yaml` does not exist but legacy env vars (`PM_OS_USER`, `PM_OS_FEEDBACK_REPO`) are set, auto-create the config file from them on first read. Print a one-line notice that migration occurred.

**Replace all env-var reads:** every `os.environ.get("PM_OS_*")` across `lib/`, `hooks/`, and `scripts/` becomes `config.load_config()["<key>"]`.

**Install script must:**
1. Prompt for each required value
2. Write each value to `config.yaml` immediately
3. Verify the write succeeded by reading the file back
4. Confirm the value matches what was prompted
5. Print explicit confirmation per step: `✓ pm_user written: karan` or `✗ FAILED to write pm_user`
6. At end of install, run the verifier (Phase D) before declaring success
7. Refuse to declare success if any step failed

**Install must not modify `~/.zshrc` for PM-OS purposes.** Existing entries from prior runs may remain (harmless), but new installs do not write env vars.

### Backward compatibility

For Karan's current installation:
- Migration logic in `lib/config.py` should auto-create `config.yaml` from his existing `PM_OS_USER` env var
- For `feedback_repo` (which was never set), the migration prompts once via stdin
- Provide a one-liner manual override: `python3 ~/.pm-os/scripts/pm_os_install.py --reconfigure` to rewrite config interactively

### Files affected (Phase B)

- New: `~/.pm-os/lib/config.py`
- New: `~/.pm-os/config.yaml` (created at install)
- Modified: every file under `lib/`, `hooks/`, `scripts/` that previously read env vars
- Modified: `~/.pm-os/scripts/pm_os_install.py` (built in Phase A, enhanced here for verification per step)

### Phase B acceptance criteria

- [ ] `~/.pm-os/config.yaml` exists and contains both `pm_user` and `feedback_repo`
- [ ] No PM-OS code reads from `os.environ` for PM-OS-specific values
- [ ] Running `pm-os-install --reconfigure` on Karan's machine produces a valid config file
- [ ] `git_sync.py` successfully pushes to `git@github.com:pingmepi/pm-os-feedback.git` (or HTTPS equivalent — confirm with Karan which auth method to use)
- [ ] Install completion message lists every step with explicit pass/fail
- [ ] Re-running install on a half-configured system completes the missing steps without redoing the successful ones

---

## 5. Phase C — Missing hooks and Claude Code registration

### Background

Two hooks were never built. Two hooks that were built are not registered with Claude Code's hook system.

### Missing hooks to build

**`post-tool-use.py`** (per spec section 9.3):
- Triggered after any Claude Code tool use; filter for file write operations on `~/pm-projects/**/*.md`
- Identify project and stage from path
- Recompute body hash
- Compare to frontmatter `content_hash`
- If status is `approved` and hashes differ: flip status to `edited`, log `stage_edited_post_approval` event
- Performance: must complete in under 200ms on small files; otherwise it makes every edit feel laggy
- Must early-return immediately for paths outside `~/pm-projects/`

**`session-end.py`** (per spec section 9.4):
- Triggered on Claude Code session end
- Flush pending telemetry events
- Push telemetry + feedback JSONL files to feedback repo
- Performance: must complete in under 5 seconds in the no-push case (e.g., no projects touched this session); under 30 seconds with a normal push
- Must early-return immediately if `feedback_repo` is not configured (do not error, do not block)
- Must not import slow dependencies (e.g., `sentence-transformers`) at module load — defer or skip entirely

### Registration in Claude Code

Hooks are registered declaratively in `~/.claude/settings.json`, not by file presence. Current settings.json shows the correct format under existing `PostToolUse` and `Stop` entries (a `continuous-learning` Stop hook exists from `claude-mem` plugin).

**Required additions to `~/.claude/settings.json`:**

Append entries — do not replace existing entries. The existing `continuous-learning/evaluate-session.sh` Stop hook stays unless explicitly told to remove it.

```json
{
  "hooks": {
    "PostToolUse": [
      // ...existing entries preserved...
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.pm-os/hooks/post-tool-use.py \"$CLAUDE_FILE_PATH\""
          }
        ]
      }
    ],
    "Stop": [
      // ...existing entries preserved...
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.pm-os/hooks/session-end.py"
          }
        ]
      }
    ]
  }
}
```

**Install script must update `settings.json` idempotently:**
- Read existing JSON
- Append PM-OS entries if not already present (detect by command-path match)
- Preserve all unrelated entries
- Write atomically (temp file + rename) to avoid corruption
- Verify the write parsed correctly as JSON before declaring success

**Both existing hooks (`pre-stage.py`, `post-approve.py`) remain as direct script invocations** called by skill scripts. They do not need Claude Code registration because they fire in response to explicit PM-OS commands. Only the two new hooks (which fire on events outside PM-OS commands) need registration.

### Files affected (Phase C)

- New: `~/.pm-os/hooks/post-tool-use.py`
- New: `~/.pm-os/hooks/session-end.py`
- Modified: `~/.claude/settings.json` (append entries)
- Modified: `~/.pm-os/scripts/pm_os_install.py` (add settings.json patching logic)

### Phase C acceptance criteria

- [ ] Both new hooks exist and are executable
- [ ] `~/.claude/settings.json` contains entries for both new hooks
- [ ] Existing `continuous-learning` Stop hook entry is preserved
- [ ] Editing an approved artifact outside Claude Code, then running any PM-OS command, shows the artifact as `edited` in `pm-status`
- [ ] `session-end.py` completes in under 5 seconds when no projects were touched
- [ ] `session-end.py` does not error when `feedback_repo` is not configured

---

## 6. Phase D — Verifier and UX cleanup

### Background

No way to confirm install correctness exists. Several issues in this fix pass (#3, #4, #5, #9) would have been caught immediately by a post-install verifier. Building one prevents recurrence in future installs (especially during multi-PM rollout).

Two minor UX issues are also addressed here.

### `pm-os-verify` skill and script

**Pattern:** script wrapper, same as Phase A.

**Checks to perform** (each check is independent — one failure does not stop subsequent checks):

**File system layout**
- `~/.pm-os/` exists with: `VERSION`, `lib/`, `hooks/`, `skills/`, `scripts/`, `templates/`, `config.yaml`
- `lib/` contains all expected modules: `hashing`, `frontmatter`, `telemetry`, `project`, `edit_distance`, `embeddings`, `git_sync`, `html_render`, `config`
- `hooks/` contains all 4 hooks: `pre-stage`, `post-approve`, `post-tool-use`, `session-end`
- `scripts/` contains all 7+ CLI scripts from Phase A
- `skills/` contains all 15 skills, each with a `SKILL.md`
- `~/pm-projects/` directory exists and is writable

**Skill registration**
- All 15 skills are visible to Claude Code (check `~/.claude/skills/` or equivalent path)
- Each skill's SKILL.md parses correctly

**Hook registration**
- `~/.claude/settings.json` parses as valid JSON
- Contains entries for both PM-OS hooks at correct events
- Command paths in entries match actual file locations
- All 4 hook files are executable (`os.access(path, os.X_OK)`)

**Config**
- `config.yaml` exists and parses
- Contains all required keys per Phase B schema
- `feedback_repo` URL is reachable via `git ls-remote` (confirms auth works)
- `projects_dir` exists and is writable

**Dependencies**
- Python ≥ 3.11
- All required packages importable: `yaml`, `jinja2`, `sentence_transformers`, `Levenshtein` (or fast equivalent), git library
- Sentence-transformers embedding model is cached locally (do not require network at runtime)

**Hash chain library consistency**
- Run a fixed known input through `lib/hashing.py`, confirm output matches expected SHA-256
- This catches divergence from the `pm-os-feedback` repo's verifier

**End-to-end smoke test**
- Create throwaway project at `/tmp/pm-os-verify-<timestamp>/`
- Run `pm-new`
- Verify `.meta.yaml` and `00-business-statement.md` exist with correct structure
- Run `pm-stage-01-brief`
- Verify `01-brief.md` exists with valid frontmatter and non-empty body
- Run `pm-approve 01`
- Verify status flipped, hash computed, telemetry event written
- Verify telemetry hash chain valid (single event, `prev_event_hash: null`)
- Clean up throwaway project

### Verifier output format

```
PM-OS Installation Verification (v0.1.0)
==========================================

File system:
  ✓ ~/.pm-os/ exists
  ✓ lib/ complete (9/9 modules)
  ✓ hooks/ complete (4/4 hooks)
  ✓ scripts/ complete (7/7 scripts)
  ✓ skills/ complete (15/15 skills)
  ✓ ~/pm-projects/ writable
  ✓ config.yaml present and valid

Skill registration:
  ✓ All 15 skills visible to Claude Code

Hook registration:
  ✓ post-tool-use.py registered (PostToolUse)
  ✓ session-end.py registered (Stop)
  ✓ continuous-learning Stop hook preserved
  ✓ All hook files executable

Config:
  ✓ pm_user set: karan
  ✓ feedback_repo set: git@github.com:pingmepi/pm-os-feedback.git
  ✓ feedback_repo reachable
  ✓ projects_dir writable

Dependencies:
  ✓ Python 3.11.5
  ✓ All packages importable
  ✓ Embedding model cached locally

Hash chain:
  ✓ lib/hashing.py output matches expected

Smoke test:
  ✓ Project scaffolded
  ✓ Stage 01 generated
  ✓ Stage 01 approved
  ✓ Telemetry hash chain valid

==========================================
All checks passed. PM-OS is healthy.
```

On failure, the relevant line shows `✗` with a one-line remediation hint.

**Behavior:**
- Single command, runnable as `pm-os-verify` skill or `python3 ~/.pm-os/scripts/pm_os_verify.py` directly
- Exit code 0 if all checks pass, non-zero otherwise
- `--verbose` flag for detailed output, default is summary
- Auto-invoked at end of `pm-os-install` and `pm-os-update`. Install does not declare success unless verifier passes.

### UX fixes

**Issue 6 — Inline y/n feedback prompt:**
After approval, do not prompt for feedback via the model. Replace the prompt with a one-line suggestion in the script's stdout:

```
Stage 01 approved. Run /pm-feedback 01 to capture notes on this stage.
```

This is a single line printed by `pm_approve.py`. No turn break, no queued input, no model mediation.

**Issue 1 — Stop hook hang (claude-mem):**

Not a PM-OS bug. Document in `pm-os-verify` output a warning if `continuous-learning/evaluate-session.sh` is registered as a Stop hook and is observed taking > 30 seconds:

```
Warnings:
  ⚠ claude-mem's Stop hook (evaluate-session.sh) detected.
    Observed runtime: 155s on last session.
    Consider disabling in ~/.claude/settings.json if you don't actively use claude-mem.
```

PM-OS itself does not modify this hook. The verifier just surfaces the issue.

### Files affected (Phase D)

- New: `~/.pm-os/scripts/pm_os_verify.py`
- New: `~/.pm-os/skills/pm-os-verify/SKILL.md`
- Modified: `pm_approve.py` (remove model-mediated feedback prompt, print one-liner instead)
- Modified: `pm_os_install.py` (auto-invoke verifier at end)
- Modified: `pm_os_update.py` (auto-invoke verifier at end)

### Phase D acceptance criteria

- [ ] `pm-os-verify` skill exists and works
- [ ] Verifier produces clear pass/fail per check
- [ ] Verifier exits non-zero on any failure
- [ ] `pm-os-install` automatically runs verifier at end
- [ ] Approval no longer prompts for feedback via the model; just prints suggestion line
- [ ] If Karan disables claude-mem's Stop hook, verifier shows no warning; if not disabled, verifier shows the warning with current observed runtime

---

## 7. Cross-phase coordination notes

- **Phase A and B touch the same files** (install script, all utility skills). Implement A first because it makes B's testing faster. But hold off committing A until B's config-file pattern is ready — otherwise the scripts will need to be patched twice.
- **Phase C cannot be tested fully until Phase B is complete.** Hook registration in `settings.json` depends on the install script being able to patch JSON correctly.
- **Phase D depends on everything.** Verifier validates the work of Phases A, B, and C. Build it last.

---

## 8. Testing protocol after each phase

After each phase, run this sequence on a clean state:

1. Re-run install: `pm-os-install` (or `--reconfigure` if config already exists)
2. Run `pm-os-verify` (after Phase D exists)
3. Create a throwaway project: `pm-new test-<timestamp> "test statement" --genai`
4. Run all stages 01–07 to approval
5. Edit an approved artifact externally, verify it's flagged
6. Confirm telemetry pushes to feedback repo

If any step fails or hangs unexpectedly, halt and report. Do not proceed to the next phase.

---

## 9. The full issues list (mapped to phases)

| # | Issue | Phase | Status |
|---|---|---|---|
| 1 | Stop hook hang (claude-mem) | D (warning only) | open |
| 2 | PM_OS_FEEDBACK_REPO env var | B (resolved by config migration) | open |
| 3 | post-tool-use.py never built | C | open |
| 4 | session-end.py never built | C | open |
| 5 | PM-OS hooks not registered | C | open |
| 6 | Inline y/n feedback prompt | D | open |
| 7 | Migrate env vars to config | B | open |
| 8 | Build post-install verifier | D | open |
| 9 | Install skill skipped step | B | open |
| 10 | Install summary didn't surface skipped steps | B | open |
| 11 | Mechanical skills using full model reasoning | A | open |
| 12 | Queued input across turns | A (resolved by script refactor) | open |

---

## 10. What success looks like

When this fix pass is complete:

- `pm-new` and `pm-approve` complete in under 10 seconds each
- A fresh install on a clean machine produces a verifiably-healthy PM-OS
- All telemetry and feedback pushes succeed to `pingmepi/pm-os-feedback`
- External edits to approved artifacts are detected automatically
- Session-end is fast (or, if slow, the cause is identified and surfaced)
- Karan can begin dogfooding in earnest without install issues recurring

---

## 11. Questions to escalate, not resolve unilaterally

1. Confirmation of correct Haiku model identifier (Phase A pre-implementation step)
2. Whether to use SSH or HTTPS form of feedback repo URL (Phase B — Karan to confirm based on his GitHub auth setup)
3. Whether to remove or keep the `continuous-learning` Stop hook from settings.json (Phase D — current spec preserves it, Karan to decide separately)
4. Any apparent contradiction between this document and `pm-os-spec.md`

---

End of fix-pass specification.
