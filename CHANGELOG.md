# Changelog

## 0.6.0 — 2026-06-24

### Added
- **Artifact quality contracts for Stages 03–05.** PRDs now require structured `UJ-###` user journeys; design specs map journeys to flows and declare a product interaction model; prototype briefs separate participant/reviewer modes and include a validation plan. A deterministic validator catches required-section errors, recommended-section gaps, journey drift, and high-signal prototype UX conflicts. Generation repairs required errors; approval/import remain warning-only and log `artifact_validation_warning` telemetry.
- **Research-safe interactive prototypes.** `pm-prototype-html` now follows the approved information architecture and interaction model instead of assuming every GenAI product needs generation/streaming/confidence UI. Participant mode is clean by default; reviewer controls and research questions are available through `?review=1`.

### Changed
- **Reorganized `docs/` into categorized folders** with lowercase filenames: `guides/` (`sop.md`, `testing.md`), `reference/` (`pm-os-spec.md`), `roadmap/` (`current-state-review.md`, `backlog.md`), `plans/` (now includes `context-intake-improvements.md` and `telemetry-fix-plan.md`), and `archive/`. Added a `docs/README.md` index. All inbound references (test docstrings, `CLAUDE.md`, `README.md`, `ARCHITECTURE.md`, the `test_documentation_drift` spec path, and intra-doc relative links) were updated in one pass.

### Fixed
- Documentation alignment sweep: corrected the `deep_reasoning_stages` value (the 7-stage set) in README / CLAUDE.md / AGENTS.md / ARCHITECTURE.md; bumped stale `v0.5.3` "current version" references; annotated the spec's aspirational sections (`edit_distance.py`/`embeddings.py`/`post-tool-use.py`/`session-end.py`/`session_end` event) and added `origin`/`generation_notes` to the spec frontmatter schema; fixed a dead `AGENTS.md` link and a duplicate row in `docs/guides/testing.md`.
- Removed the unused `gitpython` dependency (git operations shell out via `subprocess`).

### Added
- **Enhancement mode.** `/pm-new --mode enhancement --codebase <url-or-path>` (or `PM_OS_PROJECT_TYPE`) scaffolds a project that targets an existing product. `.meta.yaml` is now `schema_version: 3` with `project_type`, `codebase_path`, and `codebase_ref` (in-place `migrate_meta` upgrades v2 projects). A new conditional stage-00 doc, `00c` codebase-understanding, is produced by `/pm-context-import` via a read-only codebase scan and gates stage 01 when present. `pm_context_import.py prepare-codebase` clones (URL) or validates (local path) the codebase and records its git SHA; `/pm-status` shows the mode/codebase and warns on codebase drift. The business statement is now optional at `/pm-new`.
- **Reusable context-scan subagents.** Two standalone skills — `pm-context-scan-docs` (extract structured, wiki-ready knowledge from source documents) and `pm-context-scan-codebase` (read-only codebase scan) — that `/pm-context-import` orchestrates in parallel, and which can be invoked independently.
- **Richer context intake.** The context wiki and understanding doc gain new sections (non-goals/exclusions, success indicators, technical constraints, stakeholder authority, source-trust table, assumption register, conflict-resolution block), per-section confidence tiers, stage-affinity hints, a `> **PM:** …` annotation/override convention, lossy-vs-faithful backfill approval (lossy → `draft`), and six pre-commit self-lint rules. Stage skills `01–09` share a five-rule wiki-consumption block; stage `01` gains enhancement framing.
- Codex parity: the remaining utility skills (`pm-approve`, `pm-feedback`, `pm-new`, `pm-os-{install,update,verify}`, `pm-share`, `pm-status`) now ship `agents/openai.yaml` twins.

## 0.5.5 — 2026-06-18

### Added
- **Automated test suite.** A pytest suite under `tests/` (phases T0–T9) covering the `lib/` helpers, the full project lifecycle, the gate/approval/staleness machine, skill & documentation contracts, install/verify/update parity, context import, telemetry metrics, failure recovery, and local-first boundaries — fully isolated from the real `~/.pm-os` via temp-install fixtures. Config in `pyproject.toml`, central reference in `docs/guides/testing.md`, CI in `.github/workflows/tests.yml`.

## 0.5.4 — 2026-06-18

### Changed
- **Expanded the deep-reasoning model tier** to also cover the context-build docs (`00w`/`00u`), the design spec (`04`), and the roadmap (`09`); `deep_reasoning_stages` is now `["00w","00u","03","04","06","08","09"]`. Config merges in these policy stages even for older on-disk configs.

## 0.5.3 — 2026-06-18

### Added
- **Context overlay.** A pluggable company/team/product context layer (`lib/context.py`, seeded from `context.example/`) that loads into every stage prompt — apply modes `augment`/`override`/`reference-only`, precedence project > stage > global, with empty/TODO packs a silent no-op. The live `~/.pm-os/context/` is gitignored user data you edit in place; it's seeded on install/update and self-seeds on first read.
- **Telemetry you can measure with.** `stage_generated` now records the real `model` id and `model_tier`; `stage_approved` records real `time_to_approve_seconds` and PM edit distance (`char_edit_distance` + `normalized_edit_distance`), plus an optional agent-estimated `semantic_distance`.
- **Reliable central sync.** Feedback now enters the hash-chained telemetry stream, and a new `/pm-sync` catches up every project's telemetry/feedback to the team repo (`--verify` validates each hash chain). Sync failures are reported loudly instead of being swallowed.

## 0.5.0 — 2026-06-17

### Added
- **Start from the context you already have.** New `/pm-context-import` ingests your existing material — research, brief, scope, PRD, design notes — and builds two things: a single *context wiki* the model reads as grounding, and an *understanding doc* that shows what it understood and how your material maps onto the pipeline. Both are review-gated: you approve them before anything proceeds.
- PM-OS now **adopts the artifacts you authored** (your real PRD becomes the stage-03 artifact, marked `imported`) instead of regenerating them, and **faithfully backfills the upstream stages below them** (e.g. brief + scope from your PRD), so the pipeline chain stays intact.
- A feasibility check tells you up front which missing stages can be reconstructed faithfully, which only lossily, and which can't be rebuilt from what you provided (a metrics plan can't recreate a PRD) — surfaced in the understanding doc for your approval.
- `/pm-status` now marks each stage's origin (`imported` / `backfilled`) so it's always clear which artifacts you authored vs. which PM-OS generated.

### Changed
- The business statement is now a normal approval-gated stage (`/pm-approve 00`) like every other stage, and all three stage-00 documents (statement, context wiki, understanding) must be approved before stage 01 — if you try to move ahead, PM-OS tells you exactly what's still pending. Existing projects migrate automatically with no loss of approvals.

## 0.4.8 — 2026-06-16

### Added
- Data governance is now a required section in the PRD, QA Plan, and TRD — every product spec must state how data is collected, stored, and protected before it can be approved.

## 0.4.7 — 2026-06-15

### Added
- Share-ready materials for directors and BU heads (business overview, technical brief, walkthrough).
- As-built architecture diagram documenting how the pipeline actually runs end to end.

### Fixed
- Install verifier now defaults sensibly, resolves the projects directory correctly, and the stale-stage cascade behaves properly when upstream stages change.

## 0.4.6 — 2026-06-13

### Added
- `/pm-os-verify` — a one-command health check for your install (config, shared library, gate hooks, installed skills, and a live gate self-test).
- PM-OS now runs with full parity across the Claude and Codex runtimes.

## 0.4.5 — 2026-06-13

### Changed
- Product scope clarified as a PM-led layer over the full PDLC, with finalized runtime-neutral guidance for which model tier to use per stage.

## 0.4.4 — 2026-06-12

### Added
- Runtime-aware helpers so the same projects and commands work whether you drive PM-OS from Claude or Codex.

### Changed
- Skill metadata is now runtime-neutral; added cross-runtime usage guidance.

## 0.4.3 — 2026-06-10

### Added
- Stages 04 (Design Spec) and 05 (Prototype Brief) now generate polished HTML companion documents alongside the Markdown.

### Fixed
- `pm-status` now reports the installed PM-OS version instead of the version the project was created with.

## 0.4.2 — 2026-06-09

### Added
- Completed the product pipeline: Design Spec (04), Prototype Brief (05), QA Plan (06), and Metrics Plan (07).
- Optional Technical Requirements Document (08) as a technical capstone.

## 0.4.1 — 2026-06-09

### Added
- Scope (02) and PRD (03) stage skills.
- `--note` steering: pass notes to shape a stage's output. Notes that conflict with an approved upstream artifact are flagged for reconciliation, carry forward on regeneration, and surface in `pm-status`.
- Config-driven install and command flow.
- Cross-runtime interface (Codex) for every stage.

### Fixed
- Updater now tracks `main` explicitly and re-syncs skills and hooks into the runtime directories.
- Stages are set to `draft` on generation so status is accurate before approval.

## 0.1.0 — 2026-06-08

### Added
- Phase 1 engine skeleton
- `pm-new`, `pm-status`, `pm-approve` skills
- `pm-stage-01-brief` skill with minimal prompt
- `pre-stage` and `post-approve` hooks
- Core lib: hashing, frontmatter, project, telemetry, git_sync
