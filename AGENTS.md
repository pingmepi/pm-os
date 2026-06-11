# PM-OS Agent Instructions

PM-OS is a local-first product management workflow. It turns a short business
statement into reviewed Markdown artifacts, with deterministic Python helpers for
project creation, gates, approvals, telemetry, and sharing.

## Runtime Expectations

- Treat Claude Code and OpenAI Codex as supported runtimes. Do not encode a
  concrete provider model id into shared PM-OS config, shared skill frontmatter,
  or generated artifacts.
- In Claude, invoke PM-OS skills with slash commands such as `/pm-new`,
  `/pm-stage-01-brief`, `/pm-approve 01`, `/pm-status`, and `/pm-feedback 03`.
- In Codex, invoke PM-OS skills through the `/skills` picker or by mentioning the
  skill name directly, for example `$pm-new`, `$pm-stage-01-brief`,
  `$pm-approve`, `$pm-status`, and `$pm-feedback`.
- Codex user-level skills belong in `~/.agents/skills/`. Repo-local development
  skills may live in `.agents/skills/`.
- Claude skills install into `~/.claude/skills/`; Claude hooks install into
  `~/.claude/hooks/`.
- The install and update commands require an explicit runtime argument:
  `--runtime claude` or `--runtime codex`.
- Native Codex hooks are optional. Baseline correctness comes from the explicit
  shell commands already listed inside each skill.
- Model policy is expressed in runtime-neutral tiers. The default tier is
  `standard`; stages `03`, `06`, and `08` require `deep-reasoning`. Claude users
  should map `deep-reasoning` to Opus or the strongest available reasoning model.
  Codex users should map it to a high/deep reasoning model.

## Product Pipeline

The core product pipeline has seven approved stages:

1. `01-brief.md` - product brief
2. `02-scope.md` - MVP scope
3. `03-prd.md` - product requirements document
4. `04-design-spec.md` - design specification
5. `05-prototype-brief.md` - prototype brief
6. `06-qa-plan.md` - QA plan
7. `07-metrics-plan.md` - metrics plan

Stage 08, `08-trd.md`, is an optional technical capstone generated after stages
01-07 are approved. It translates the approved product definition into a
technical requirements document without reopening product decisions.

## Project State

- PM-OS projects are plain local directories, usually under the configured
  `projects_dir`.
- `.meta.yaml` is the source of truth for project slug, PM-OS version,
  `genai_flag`, stage status, approval state, hashes, and regeneration counts.
- `00-business-statement.md` is the seed input for the whole pipeline.
- Stage artifacts are Markdown files with YAML frontmatter and a generated body.
- `.history/` stores timestamped generated snapshots before the current artifact
  is written.
- `telemetry.jsonl` records local stage events. `feedback.jsonl` records PM
  feedback captured through PM-OS.

## Stage Discipline

- Run PM-OS helper commands from inside a PM-OS project directory unless the
  helper explicitly says otherwise.
- Before generating a stage, follow the skill's pre-flight instructions and run
  the listed pre-stage gate, such as
  `PM_OS_STAGE=01 python3 ~/.pm-os/hooks/pre-stage.py`.
- If a pre-stage gate exits non-zero, stop and surface its error. Do not write
  the artifact.
- Do not generate downstream stages from unapproved upstream artifacts.
- Keep approved upstream artifacts as the binding source of truth. If a new note
  conflicts with an approved upstream artifact, surface the conflict instead of
  silently changing the product decision.
- On regeneration, honor the skill's carry-forward note behavior. Existing
  `generation_notes` should be surfaced before deciding whether to reuse them.
- When writing a stage artifact, update the artifact, `.history/`, `.meta.yaml`,
  generated hash, and telemetry exactly as the skill specifies.
- Approval is explicit. A draft is not approved until the PM runs the approval
  entrypoint for that stage.

## Helper Scripts And Local Writes

- The shared Python implementation under `~/.pm-os/` is the runtime source of
  truth for installed PM-OS helpers.
- The repository `scripts/`, `lib/`, `hooks/`, `templates/`, and `skills/`
  directories are the source tree for PM-OS development.
- Keep shared script logic centralized. If a runtime needs skill-local wrappers
  or symlinks later, make them thin and point back to the shared implementation.
- PM-OS shell commands may write local project files, local history, telemetry,
  feedback, and PM-OS config. When the user asks for PM-OS work, expect these
  local writes and allow them when the active tool policy permits.
- Do not send project data to external services unless the user explicitly asks
  for sharing, installation from a remote source, or another networked action.

## Quality Bar

- Generated artifacts should be concrete, PM-native, and free of placeholders.
- Respect `genai_flag` when a skill asks for GenAI-specific sections or
  rationale.
- Prefer deterministic helper scripts for mechanical state changes. Use the
  agent for product reasoning, synthesis, and careful editing.
- Keep runtime-specific guidance valid for both Claude and Codex. Runtime
  parity is the goal; provider-specific details belong only in runtime-specific
  install paths, invocation examples, or model-tier mapping instructions.


<claude-mem-context>
# Memory Context

# [pm-os] recent context, 2026-06-11 2:56pm GMT+5:30

No previous sessions found.
</claude-mem-context>