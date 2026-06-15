# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What PM-OS is

A local-first, PM-led PDLC operating layer, built as an **agent skill suite** (not an app). There is no frontend and no backend service. A PM drives a product idea through a gated pipeline of stages; each stage produces a Markdown artifact that a human reviews and explicitly approves before the next stage can run. All state is plain files (`.meta.yaml`, Markdown, JSONL) on the PM's machine. v1 covers product definition (stages 01–08); dev handoff / QA triage / release / feedback are planned later phases (see `docs/PM-OS-CURRENT-STATE-REVIEW.md`).

The agent (Claude Code or Codex) is the generation engine: stage `SKILL.md` files contain the prompt + the inline bash the agent runs. Python in `scripts/`, `lib/`, and `hooks/` only handles mechanical state (scaffold, hash, approve, gate, telemetry). Decision authority stays with the PM — nothing progresses autonomously.

## Critical: this repo is the source, not the running system

Editing files here does **not** change the running tool. There are two layers:

1. **This repo** → cloned/checked out to `~/.pm-os` (the canonical install: `lib/`, `scripts/`, `hooks/`, `skills/`).
2. `~/.pm-os` → **synced out** to the runtime's discovery dirs: skills to `~/.claude/skills` (or `~/.agents/skills` for Codex). The installer also copies hooks to `~/.claude/hooks`, but **nothing executes them from there** — the gates always run from `~/.pm-os/hooks` (see Gate flow). That copy is vestigial/reserved for future native-hook registration; don't mistake the Codex skip for a parity gap.

Consequences when developing:
- `scripts/*.py` import `lib` via a hardcoded `~/.pm-os/lib` path (`sys.path.insert(0, Path.home()/".pm-os"/"lib")`). The gate hooks are executed from `~/.pm-os/hooks` (the skill calls `python3 ~/.pm-os/hooks/pre-stage.py`; `pm_approve.py` invokes `~/.pm-os/hooks/post-approve.py`). So **your edits in this working copy are inert until they reach `~/.pm-os`.**
- `install.sh` clones `~/.pm-os` from the **GitHub remote**, not from this local directory. To test local changes, either work directly in `~/.pm-os`, or commit+push then run the updater, or manually copy files into `~/.pm-os` and re-sync.
- `pm_os_update.py` fast-forwards `~/.pm-os` to `origin/main`, then copies skills/hooks into the runtime dirs. It refuses to run on a non-`main` branch with a dirty tree, and refuses to overwrite a diverged local `main` without `--reset-main`.

## Commands

```bash
# Install for a runtime (--runtime is required)
./install.sh --runtime claude
./install.sh --runtime codex

# Update an existing install + re-sync skills/hooks to the runtime
python3 ~/.pm-os/scripts/pm_os_update.py --runtime claude   # or codex, or all
python3 ~/.pm-os/scripts/pm_os_update.py --runtime claude --reset-main  # realign diverged checkout

# Verify an install (config, lib imports, gate hooks, installed skills, gate self-test)
python3 ~/.pm-os/scripts/pm_os_verify.py --runtime claude   # or codex, or all (default)
```

`pm_os_verify.py` is the fastest way to confirm a change didn't break the install: it runs the real `pre-stage.py` gate in a throwaway project and asserts it blocks an unapproved upstream and allows the first stage. Run it after touching `lib/`, `hooks/`, or the installer (against `~/.pm-os`, so sync your changes there first).

Runtime dependencies (installed inline by `install.sh`, no `requirements.txt`): `pyyaml`, `jinja2`, `gitpython`. Python 3.11+.

PM-facing workflow runs through skills, not direct CLI — Claude uses `/pm-*`, Codex uses `$pm-*`:
`/pm-new <slug> "<statement>"` → `/pm-stage-01-brief` → `/pm-approve 01` → … → `/pm-status`, `/pm-feedback <NN>`, `/pm-share`.

**There is no unit-test suite, linter, or build step in this repo** (no `pytest`, `pyproject.toml`, `Makefile`, or CI beyond `.github/workflows/version-bump.yml`). The closest thing to a smoke test is `pm_os_verify.py` (above); beyond that, verify by running the skill/script flow against a scratch project under `~/pm-projects/`.

## Architecture

### Stage pipeline and the state machine
Stages are fixed and linear, defined in `lib/project.py` (`STAGE_ORDER`, `STAGE_NAMES`): 01 brief → 02 scope → 03 prd → 04 design-spec → 05 prototype-brief → 06 qa-plan → 07 metrics-plan → 08 trd (optional). Each stage has a status: `pending → draft → approved`, plus two off-path states: `edited` (artifact body changed after approval — detected by hash drift) and `stale` (an upstream stage was re-approved).

### Two synchronized sources of truth
Stage state lives in **both** `.meta.yaml` (`stages[]` list) **and** each artifact's YAML frontmatter, and the code keeps them in lockstep (`pm_approve.py`, the hooks). When changing state logic, update both. `content_hash` is computed over the **body only** (everything after the closing `---`) so frontmatter edits never trigger false drift — see `lib/hashing.hash_artifact_body`.

### Gate flow (where approval is enforced)
1. Before generating, a stage `SKILL.md` runs `PM_OS_STAGE=<NN> python3 ~/.pm-os/hooks/pre-stage.py`. The gate (`hooks/pre-stage.py`) blocks if any upstream stage is `pending/draft/stale`, re-hashes upstream artifacts to catch post-approval edits (marking them `edited`), and prompts for implicit re-approval if upstreams were edited. On implicit re-approval it cascades `stale` to downstream approved stages (including intermediate ones), mirroring `post-approve.py`.
2. `scripts/pm_approve.py` validates status, writes the approval (frontmatter + meta + `stage_approved` telemetry), then shells out to `hooks/post-approve.py` with `PM_OS_STAGE` set.
3. `hooks/post-approve.py` renders HTML companions for stages 04/05 (`lib/html_render.py`), cascades `stale` to downstream approved stages, and pushes telemetry/feedback via `lib/git_sync.py`.

State flows between hooks and scripts via the `PM_OS_STAGE` environment variable, not arguments.

### Runtime agnosticism
Every skill ships `SKILL.md` (Claude, with YAML frontmatter) **and** `agents/openai.yaml` (Codex interface metadata). When adding or changing a skill, update both. `install.sh`/`pm_os_update.py` route to `~/.claude/{skills,hooks}` for Claude and `~/.agents/skills` for Codex (Codex skips hooks). Model choice is **config-driven, not hardcoded**: `lib/config.py` stores `default_model_tier` and `deep_reasoning_stages` (`["03","06","08"]`); skills/SOP advise running deep-reasoning stages on the strongest available model rather than naming a provider model id.

### Telemetry
`lib/telemetry.log(event_type, project_root, stage, payload)` appends a hash-chained JSONL line to the project's `telemetry.jsonl` (`prev_event_hash` → `event_hash`). Append-only by convention — never edit past events. Telemetry calls are wrapped so a failure warns but doesn't break the workflow.

### Config
`lib/config.load_config()` reads `~/.pm-os/config.yaml` (required keys: `pm_user`, `feedback_repo`, `projects_dir`), caches it, and applies model-policy defaults. It can migrate from `PM_OS_USER`/`PM_OS_FEEDBACK_REPO` env vars. `lib/project.resolve_project()` finds the active project by walking up from CWD to the nearest `.meta.yaml`, so PM commands must run from inside a project directory.

## Conventions when editing

- **Non-interactive safety:** code that prompts (`input()`) must have an env-var/`--flag` escape and a non-tty branch. Examples: `PM_OS_EDITED_UPSTREAM_CHOICE` for the edited-upstream gate; `config.py` defaults `feedback_repo` when stdin isn't a tty. Preserve this — these run unattended inside agents.
- **`schema_version`** exists in both `.meta.yaml` and `config.yaml`; bump it and provide migration when changing those shapes (existing projects on disk must keep working).
- Skills carry instructions and prompts; Python carries mechanical state. Keep generation/judgment in the `SKILL.md`, not in Python.
- The `pm-os-spec.md` repo/lib listing is partly aspirational (it references `edit_distance.py`, `embeddings.py`, `post-tool-use.py`, `session-end.py` that don't exist yet). Trust the actual files in `lib/` and `hooks/` over the spec.
