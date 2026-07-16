# Changelog

## 1.1.0 — 2026-07-16

### Fixed
- **Approval no longer waits on the central sync ([PR #34](https://github.com/pingmepi/pm-os/pull/34), backlog #6/IMP-003).** `/pm-approve` used to print its confirmation only after `post-approve.py` finished a synchronous feedback-repo `git push`, so approval could appear to hang for minutes even though the state was already saved locally. The central push now defers to a detached background process by default; approval returns immediately and `/pm-sync` remains the catch-up/retry path. `PM_OS_SYNC_BLOCKING=1` forces the old inline push (CI/tests use it).
- **Concurrent syncs serialize via a portable cache lock (Codex review on #34).** Because the deferred push is backgrounded, two approvals seconds apart could collide on the single shared `~/.pm-os-feedback-cache`. `lib/git_sync.py` now guards the cache with an atomic `mkdir` lock (portable — holds under Git Bash on Windows, no `fcntl`) that waits for the holder and steals a crashed process's stale lock.
- **`TC-###`/`US-###` block splitting is level-aware (Codex review on #33).** The `#{2,6}`-heading break introduced in 1.0.14 truncated a heading-style test case (`### TC-001`) at its own nested `#### Coverage`/`#### Steps` subsection, dropping requirement ids cited below it. The shared splitter (`_split_id_blocks`) now breaks only at a heading at or above the declaration's own level, preserving nested detail while still ending at a sibling/interleaved heading.

## 1.0.14 — 2026-07-16

### Fixed
- **Reliability + traceability hardening batch ([PR #33](https://github.com/pingmepi/pm-os/pull/33)).**
  - **Unified `TC-###` extractors (backlog #11/IMP-007).** The stage-06 validator and `traceability.build_index()` used two different extractors that disagreed on what "declares" a test case, so a bold-wrapped-bullet QA plan (`- **TC-001:** …`) could pass every contract check while contributing nothing to `.traceability.yaml`. Both now share one line-anchored, bold-tolerant extractor.
  - **`/pm-approve <NN> --reapprove` (backlog #7).** Re-approve a stage the PM edited directly while it was still `approved`, without first running a downstream stage's gate to demote it to `edited`. No-ops if the body is unchanged.
  - **Telemetry stamps the runtime version (backlog #8).** Events now record `pm_os_version_runtime` (the installed `~/.pm-os/VERSION`) alongside the project's pinned "created-with" `pm_os_version`, so drift is visible.
  - **Telemetry test isolation (backlog #17).** `test_telemetry.py` no longer reads the real installed `config.yaml`.

## 1.0.10 – 1.0.13 — 2026-07-14 … 2026-07-15

### Added
- **Readable handoff package via `/pm-share --package` ([PR #30](https://github.com/pingmepi/pm-os/pull/30) → [#31](https://github.com/pingmepi/pm-os/pull/31)).** Generates a decomposed per-story handoff package (`scripts/pm_share.py --package`) — per-story files plus reference docs — from the approved pipeline. Merged into `/pm-share` rather than a standalone skill; the `pm-handoff` name is reserved for a later external-tracker/design export.
- **Stage-03 PRD contract v2.** Per-story mini-specs and impact analysis, with an explicit happy path + edge cases required per user story (`lib/artifact_contracts.py`).

### Fixed
- **`--package` safety guards ([PR #32](https://github.com/pingmepi/pm-os/pull/32)).** Requires an *approved* (not merely `edited`) PRD and guards against overwriting existing handoff output.

## 1.0.7 — 2026-07-07

### Added
- **`/pm-check` — read-only project consistency toolkit (T10).** A single "is this
  project internally consistent right now?" check (`lib/consistency.py` →
  `check_project`), reusing the invariant logic already enforced piecemeal by
  approval/gating/telemetry. Checks meta↔frontmatter sync, approved-stage body
  drift, upstream approval shape, the telemetry hash chain, `.meta.yaml`
  schema/stage shape, missing artifacts, and `context.yaml`/`.sources.yaml`
  parseability. Surfaced via the new `/pm-check` skill (exit 1 on any error),
  a non-blocking advisory in the pre-stage gate, and a one-line verdict in
  `/pm-status`. Never mutates state — points to the remediation command
  (e.g. `/pm-approve <NN>`) instead.

## 1.0.6 — 2026-06-30

### Added
- **Adaptive context pack.** Context intake now produces a modular pack that stages 01–09 and the import flow read directly, instead of one flat wiki document — richer per-source metadata and pack operations in `pm_context_import.py`, dual-mode reads wired into every stage skill, and a `--upgrade-pack` flag for migrating existing projects.
- **Composite hashing + schema v4.** `.meta.yaml` composite-hashes the context pack so drift on any pack section is caught; the pre-stage gate and approval path both dispatch stage `00w` through the new composite hash.

### Fixed
- Traceability: bounded `TC` blocks at the next `##` section instead of running to end-of-document; addressed Codex review — `REQ`-only `FR`, per-`TC` trace, ordered lists; hash-affinity and three smoke-test fixes found during an end-to-end run ([PR #28](https://github.com/pingmepi/pm-os/pull/28)).

## 1.0.5 — 2026-06-25/30

### Added
- **Traceability spine (Phase 3.5).** Stable `REQ-###`/`US-###`/`FR-###` IDs formalized in the PRD contract and `TC-###` IDs in the QA plan contract (`lib/artifact_contracts.py`), so requirements and test cases survive regeneration. A new `.traceability.yaml` local link file wires `REQ` ↔ `TC`, with a resolver (`lib/traceability.py`) that answers "which scenarios cover requirement REQ-X" entirely locally. The link table rebuilds automatically on stage approval. Test coverage: stable-id contracts, resolver behavior, end-to-end spine ([PR #29](https://github.com/pingmepi/pm-os/pull/29)).

## 1.0.2 – 1.0.4 — 2026-06-25

### Fixed
- **Install verifier false negatives.** `pm_os_verify.py` closed gaps where health checks could report success despite being silently skipped.

### Changed
- Verifier description updated to reflect the new checks; SOP docs (§4.1) gained a prerequisites block for one-time setup.

## 1.0.1 — 2026-06-25

Version renumbering only (0.6.x → 1.0.x); no functional change beyond the 0.6.0 content below.

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
