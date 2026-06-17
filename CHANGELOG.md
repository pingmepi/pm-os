# Changelog

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
