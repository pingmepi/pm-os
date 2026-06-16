# Changelog

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
