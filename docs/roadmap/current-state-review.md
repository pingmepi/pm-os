# PM-OS Current State Review and Roadmap

**Date:** 2026-06-12 · **Updated:** 2026-07-16 (v1.1.0; see CHANGELOG for full history)

> **Version summary:** Phase 1 runtime parity and Phase 2 flexible intake shipped in v0.4–v0.5.2; context overlay + telemetry metrics in v0.5.3; deep-reasoning tier expansion in v0.5.4; automated test suite in v0.5.5; telemetry/gate hardening in v0.5.6–v0.5.7; richer context intake in v0.5.8; **enhancement mode + `00c` codebase-understanding + offline install** in v0.5.9–v0.5.10; `pm-prototype-html` skill in v0.5.11; **artifact quality contracts (Stages 03–05) + research-safe prototypes** in v0.6.0; **Phase 3.5 traceability spine** (stable `REQ`/`TC` IDs, `.traceability.yaml` resolver) and **adaptive context pack** (composite hashing, schema v4, modular pack across stages 01–09) in v1.0.5–v1.0.6; **`/pm-check` consistency toolkit** in v1.0.7; **PRD contract v2 + readable handoff package (`/pm-share --package`)** in v1.0.10–v1.0.12; **reliability + traceability hardening** (unified `TC` extractors, `--reapprove`, runtime-version telemetry) in v1.0.14; **deferred non-blocking central sync + portable cache lock** (#6) in v1.1.0. §2/§3 below reflect v1.1.0.
**Purpose:** Review the current PM-OS codebase against the expanded product ask: an end-to-end, PM-led, agent-agnostic PDLC operating layer.
**Status:** Working product/architecture review. This document distinguishes implemented behavior from draft plans already present in the repo.

---

## 1. Product Aim

PM-OS should reduce end-to-end Product Development Life Cycle (PDLC) time from idea to shipped learning by helping the PM and cross-functional team maintain one coherent thread across:

- intake and discovery
- product definition
- design and solution planning
- development handoff and development-phase support
- QA planning, QA execution support, and bug triage
- release readiness
- feedback, learnings, and iteration

PM-OS is not the final decision-maker and is not the executor.

- The **PM decides**: scope, trade-offs, approvals, priority, release calls, and whether to proceed.
- PM-OS **suggests, prepares, validates, maps, and coordinates**.
- Developers and QAs **execute** development and testing.
- PM-OS supports dev/QA phases by connecting requirements, QA scenarios, codebase state, bugs, tickets, PRs, and release decisions.

The long-term product should be a cohesive lifecycle intelligence layer that consumes artifacts from where work actually happens: Markdown docs, PRDs, repos, Jira/Linear tickets, QA bugs, PRs, design files, release notes, analytics, support feedback, and stakeholder conversations.

It should be **agent/runtime agnostic**. Claude Code, Codex, Gemini CLI, or future agents are execution surfaces. PM-OS owns the lifecycle model, artifacts, approvals, traceability, and orchestration rules.

---

## 2. Current State Summary

The current codebase (v1.1.0) is a strong **local-first product-definition MVP** with flexible intake, enhancement mode, a pluggable company/team context overlay, deterministic artifact quality contracts, a requirements-to-test-case traceability spine, a read-only consistency check (`/pm-check`), and a decomposed per-story handoff package (`/pm-share --package`).

It can scaffold a project from a business statement **or from existing PM-authored context** (research, brief, scope, PRD, design notes) via `/pm-context-import`; generate staged product artifacts; require human approval between stages; track status/hashes/origin in local files; check project consistency (`/pm-check`); record telemetry/feedback; and export approved artifacts — as raw text or a decomposed per-story handoff package (`/pm-share --package`).

It is not yet the full PDLC operating system described above (no brownfield codebase awareness, external integrations, or dev/QA/release/feedback workflows).

### Implemented Today

| Area | Status | Evidence |
|---|---:|---|
| Local project scaffold | Implemented | `scripts/pm_new.py` creates `~/pm-projects/<slug>`, `.meta.yaml`, `00-business-statement.md`, `.history/`, telemetry, feedback |
| Linear stage pipeline | Implemented | `lib/project.py` defines `STAGE_ORDER` = `00`, `00c`, `00w`, `00u`, `01`–`09`: stage-00 understanding group (`00` business-statement always present; `00c` codebase-understanding only in enhancement mode; `00w` context-wiki + `00u` context-understanding only after `/pm-context-import`), `CORE_STAGE_ORDER` 01-07, plus optional 08 (TRD) and 09 (roadmap) capstones |
| Human approval gates | Implemented | `scripts/pm_approve.py`, `hooks/pre-stage.py`, `hooks/post-approve.py` |
| Artifact status model | Implemented | `pending`, `draft`, `approved`, `edited`, `stale` in `.meta.yaml` and frontmatter |
| Hash-based drift detection | Implemented | `hooks/pre-stage.py` recomputes upstream hashes and marks edits |
| Downstream staleness cascade | Implemented | `hooks/post-approve.py` marks approved downstream stages stale |
| Telemetry | Implemented | `lib/telemetry.py` appends hash-chained JSONL events |
| Telemetry: approval metrics | Implemented | `pm_approve.py` records real `time_to_approve_seconds`, PM edit distance (`char_edit_distance` + `normalized_edit_distance`, Levenshtein via `lib/text_metrics.py`), optional agent-estimated `semantic_distance`, and `regeneration_count` — null for stage-00/imported/backfilled artifacts that were never generated |
| Telemetry: model capture | Implemented | generated/backfilled artifacts record the real `model` id + `model_tier` (`config.model_tier_for_stage`); imported (PM-authored) artifacts carry no model |
| Feedback capture | Implemented, basic | `scripts/pm_feedback.py` writes simple feedback JSONL entries |
| Share/export | Implemented, basic | `scripts/pm_share.py` exports approved/edited artifacts |
| GenAI-specific sections | Implemented in prompts | `genai_flag` exists and stage prompts branch on it |
| Optional TRD | Implemented | `pm-stage-08-trd` exists and is marked optional in metadata |
| Optional Roadmap | Implemented | `pm-stage-09-roadmap` — optional product-strategy capstone that runs after the 01-07 MVP pipeline; depends on the core stages and uses the TRD (08) as delivery context if approved |
| HTML companions | Implemented | post-approval renders stage 04 and 05 HTML companions |
| Cross-runtime install (Claude + Codex) | Implemented | `install.sh --runtime claude\|codex` routes Codex skills to `~/.agents/skills`, skips Claude hooks on Codex |
| Runtime-neutral skill interface | Implemented | each stage skill ships `agents/openai.yaml` alongside `SKILL.md` |
| Gate parity across runtimes | Implemented | gates run via skill bash (`python3 ~/.pm-os/hooks/pre-stage.py`) + `pm_approve.py` subprocess, not native hooks — identical on Claude and Codex (verified) |
| Runtime-neutral `AGENTS.md` | Implemented | full agents file; `claude-mem` stub removed |
| Runtime-neutral model wording | Implemented | deep-reasoning stages 03/04/06/08/09 (and the context-build docs 00w/00u) use advisory deep-reasoning guidance instead of `/model opus` |
| Non-interactive gate safety | Implemented | `pre-stage.py` has `isatty()` branch + `PM_OS_EDITED_UPSTREAM_CHOICE`; never hangs unattended |
| Catch-up telemetry sync | Implemented | `/pm-sync` + `scripts/pm_sync.py` walk every project under `projects_dir`, copy telemetry/feedback to the central repo, and push in one commit; `--verify` validates each project's hash chain. Failures are surfaced loudly, not swallowed |
| Automated test suite | Implemented (in progress) | `tests/` pytest harness (T0–T9: unit/integration/contract), isolated from the real `~/.pm-os` via temp-install fixtures; `pyproject.toml` config, `docs/guides/testing.md` reference, `.github/workflows/tests.yml` CI |
| Install verifier | Implemented | `scripts/pm_os_verify.py` + `pm-os-verify` skill: install-integrity checks + deterministic gate self-test, per runtime |
| Flexible context intake | Implemented | `/pm-context-import` (`scripts/pm_context_import.py` + `skills/pm-context-import/`): ingest existing research/brief/scope/PRD/design, register sources in `.sources.yaml`, preserve raw in `.history/` |
| Gated stage-00 understanding | Implemented | context wiki (`00-context-wiki.md`) + understanding doc (`00-context-understanding.md`); the business statement is now a normal gated stage `00`. All three must be approved before stage 01 |
| Adopt + backfill | Implemented | PM-authored artifacts adopted as stage artifacts (`origin: imported`); upstream gaps reverse-generated (`origin: backfilled`) per the feasibility map in `lib/project.resolve_backfill` |
| Schema versioning + migration | Implemented | `.meta.yaml` `schema_version: 4`; `lib/project.migrate_meta` upgrades older projects in place (v2 added `00` stage + per-stage `origin`; v3 added `project_type`/`codebase_path`/`codebase_ref`; v4 added the composite-hash adaptive context pack) without disturbing approvals |
| Telemetry: intake events | Implemented | `context_ingested`, `stage_imported`, `stage_backfilled` kept distinct from `stage_approved` so quality signals are not polluted |
| Context overlay | Implemented (v0.5.3) | `lib/context.py` (resolve/render/seed) injects a pluggable company/team/product knowledge layer into every stage prompt. Three apply modes — `augment`, `override`, `reference-only`; layering precedence project > stage > global; empty/TODO packs are a silent no-op. Seed lives in `context.example/` (global `company`/`team`/`glossary`/`guardrails.md` + per-stage `format.md`/`example.md` packs); all stage skills load it; seeded on install/update and self-seeds on first read |
| Context overlay as user data | Implemented (v0.5.3) | live `~/.pm-os/context/` is **gitignored** and edited in place by the PM — the one engine-dir exception to the never-hand-modify rule; never diverges `main` or blocks `pm_os_update.py` |
| Enhancement mode | Implemented (v0.5.9) | `/pm-new --mode enhancement --codebase <url-or-path>` scaffolds a project with `project_type: enhancement`, `codebase_path`, `codebase_ref` (schema v3). `pm_context_import.py prepare-codebase` clones or validates the codebase and records its git SHA. `/pm-status` shows mode and warns on codebase drift. Stage-01 brief in enhancement mode frames the request as a delta against the existing product |
| Codebase-understanding stage (`00c`) | Implemented (v0.5.9) | Conditional pre-stage doc produced by `/pm-context-import` via a read-only codebase scan. Gates stage 01 when present. Contains TL;DR, current features & flows, architecture & modules, data model, tech stack, design language, integration points, known constraints — each section tagged with `<!-- stage-affinity -->` hints |
| Richer context intake | Implemented (v0.5.8) | Context wiki gained 4 new sections (non-goals, success indicators, technical constraints, stakeholder authority), per-section confidence tiers, stage-affinity hints, and a PM annotation override convention. Understanding doc gained a source-trust table, assumption register, and conflict-resolution block. All 9 stage skills use a 5-rule wiki consumption block |
| Offline / GitLab install | Implemented (v0.5.9) | `install.sh --source <zip-or-dir>` for air-gapped/offline installs; `--repo <url>` to clone from a GitLab mirror instead of GitHub. Auto-runs `pm_os_verify.py` after install. Documented in `docs/guides/offline-install.md` |
| Standalone HTML prototype skill | Implemented (v0.5.11) | `pm-prototype-html` generates or regenerates `05-prototype-mockup.html` from approved prototype brief + design spec without re-running the full stage 05 brief. Auto-invoked by `pm-stage-05-prototype-brief`; also callable standalone. Prototype follows the approved interaction model — participant mode is clean by default; reviewer controls appear only via `?review=1` |
| Artifact quality contracts (Stages 03–05) | Implemented (v0.6.0) | `lib/artifact_contracts.py` (CONTRACT_VERSION=1) + `scripts/pm_validate_artifact.py`. PRDs require `UJ-###` user journeys; design specs require journey-to-flow traceability and an interaction model declaration; prototype briefs require audience/mode separation and a validation plan. Strict mode blocks generation on required-section errors; warn mode at approval/import logs `artifact_validation_warning` telemetry and continues |
| Traceability spine | Implemented (v1.0.5) | `lib/traceability.py` + stable `REQ-###`/`US-###`/`FR-###` IDs in the PRD contract and `TC-###` IDs in the QA plan contract; `.traceability.yaml` records the `REQ` ↔ `TC` link table and a resolver answers "which scenarios cover requirement REQ-X" locally; links rebuild automatically on stage approval |
| Adaptive context pack | Implemented (v1.0.6) | `lib/hashing.py` composite hashing + `.meta.yaml` `schema_version: 4`; `/pm-context-import` produces a modular context pack (per-source hash + stage-affinity tags) consumed dual-mode across stages 01–09 and import; `--upgrade-pack` flag migrates older single-blob context wikis in place |
| Project consistency check (`/pm-check`) | Implemented (v1.0.7) | `lib/consistency.py` → `check_project` — a read-only "is this project internally consistent right now?" check reusing the invariant logic enforced piecemeal by approval/gating/telemetry (meta↔frontmatter sync, approved-body drift, upstream approval shape, telemetry hash chain, schema/stage shape, missing artifacts, `context.yaml`/`.sources.yaml` parseability). Surfaced via `/pm-check`, a non-blocking pre-stage advisory, and a one-line `/pm-status` verdict; never mutates state |
| PRD contract v2 + per-story mini-specs | Implemented (v1.0.10) | Stage-03 PRD contract enriched to v2: per-story mini-specs and impact analysis, with an explicit happy path + edge cases required per user story (`lib/artifact_contracts.py`) |
| Readable handoff package (`/pm-share --package`) | Implemented (v1.0.10–1.0.12) | `scripts/pm_share.py --package` generates a decomposed per-story handoff package (per-story files + reference docs) from the approved pipeline. Merged into `/pm-share`; requires an *approved* (not `edited`) PRD and guards against overwriting existing output. The `pm-handoff` name is reserved for a later external-tracker/design export |
| Reliability + traceability hardening | Implemented (v1.0.14–v1.1.0) | Unified `TC-###` extractors so the QA validator and traceability builder can't disagree (backlog #11); `/pm-approve --reapprove` for direct edits to an approved stage (#7); telemetry stamps `pm_os_version_runtime` alongside the pinned version (#8); telemetry test isolation (#17) — all v1.0.14. In v1.1.0: deferred (non-blocking) central sync on approval with a portable cache lock (#6) |

### Planned but Not Implemented

| Area | Status | Source |
|---|---:|---|
| Gemini runtime support | Planned | `../plans/pm-os-cross-runtime-plan.md` (Claude + Codex already shipped) |
| Jira/Linear handoff | Planned | `../plans/pm-os-modes-and-handoff-plan.md` Part B |
| Figma/design-system integration | Planned later | `../plans/pm-os-modes-and-handoff-plan.md` |
| QA bug analysis against codebase | Missing | part of expanded ask |
| Dev-phase support and fix-plan suggestion | Missing | part of expanded ask |
| Release readiness workflow | Missing | part of expanded ask |
| Feedback artifact ingestion | Missing | part of expanded ask |
| External artifact graph | Missing | part of expanded ask |

---

## 3. Fit Against the Expanded Ask

### Where PM-OS Fits Well Today

The current architecture already has several foundations that should survive:

- **PM approval remains explicit.** The state machine already prevents autonomous downstream progression.
- **Artifacts are portable.** Markdown/YAML/JSONL are a good neutral base.
- **The pipeline is artifact-driven.** Downstream stages care about approved files and hashes, not session state.
- **Hash/staleness machinery is valuable.** This is the beginning of lifecycle traceability.
- **Skill-based workflow is a good portable wrapper.** The same idea can work across Claude/Codex if runtime-specific assumptions are removed.
- **The context overlay is an early context-layer foundation.** Per-PM/company knowledge (company, team, glossary, guardrails, per-stage packs) now flows into every stage's generation without any code change, and lives as gitignored user data. This is the seed of the wider PDLC context graph the target product needs.

### Where It Falls Short

The product now generates from a business statement **or** adopts existing PM-authored context, but it remains a product-definition tool: it has no brownfield codebase awareness, no external integrations, and no dev/QA/release/feedback workflows.

Major gaps:

1. **Scope mismatch (largely closed):** README, spec, and SOP were reframed (Phase 0) from "doc generator" to PM-led PDLC layer; the *implementation* still covers only product definition (stages 00–09), while the ask extends to dev, QA, release, and feedback.
2. **Entry point (largely addressed):** PM-OS can start from a business statement, from existing PM-authored docs via `/pm-context-import`, or from an existing codebase (`--mode enhancement --codebase <url-or-path>`). It still cannot start from a Jira bug, QA report, or existing ticket.
3. **Linear dependency model:** stages are hard-coded (stage-00 understanding group + core 01-07 + optional 08/09 capstones); no explicit lifecycle graph for optional/nonlinear paths.
4. **Context-sufficiency layer (partly built):** for ingest, PM-OS now assesses whether provided inputs can faithfully reconstruct the missing upstream stages (the `resolve_backfill` feasibility map, surfaced in the understanding doc for approval). There is still no general recommendation layer across the wider PDLC.
5. **Brownfield support is now live (Phase 3):** enhancement mode + `00c` codebase-understanding shipped in v0.5.9. No external integrations yet (Jira/Linear/Figma handoff is Phase 4, not built).
6. **No external artifact consumption:** Jira/Linear/GitHub/Figma/QA/analytics/support systems are not integrated.
7. **No dev/QA execution support:** PM-OS can draft a QA plan and TRD, but cannot yet analyze a QA bug, map it to requirements/code, classify it, and suggest a developer fix plan.
8. **Runtime agnosticism is complete (Claude + Codex).** Install, skill interfaces, advisory model guidance, a real `AGENTS.md`, non-interactive-safe gates, and an install verifier are all shipped. Gate parity was confirmed: the gates run from `~/.pm-os/hooks` via skill bash and `pm_approve.py`, not native Claude hooks, so they behave identically on both runtimes. (Gemini remains a later runtime target.)

---

## 4. How Much Needs to Change

This is **not a full rewrite**.

The deterministic core can remain:

- local project state
- artifact files
- frontmatter
- status machine
- approval commands
- hashing
- stale cascade
- telemetry/feedback append logs
- stage skills

But the product needs a **significant expansion around the core**.

Approximate change profile:

| Layer | Change level | Notes |
|---|---:|---|
| Current artifact/status core | Low to medium | Extend statuses/metadata, avoid breaking current projects |
| Stage prompts 01-09 | Medium | Add modes, external context, lifecycle trace IDs |
| Installer/runtime support | Medium | Needed for true Claude/Codex agnosticism |
| Intake/orchestration | High | New layer: classify ask, identify available artifacts, recommend path, request PM approval |
| Artifact ingest | Medium | Mostly additive because current gate is artifact-driven |
| Brownfield/codebase awareness | High | New stage/tooling, code snapshot tracking, drift checks |
| External integrations | High | Jira/Linear/GitHub/Figma/etc. require connectors, auth, provenance, sync rules |
| Dev/QA support | High | Requires traceability graph across requirements, tests, bugs, code, PRs |
| Release/feedback loop | High | New workflows and external artifact consumers |

Best framing: the current PM-OS is the **product-definition kernel**. The target product is a **PDLC context graph and recommendation layer** wrapped around that kernel.

---

## 5. Target Product Scope

### Core Capabilities

PM-OS should eventually support:

1. **Flexible intake**
   - Start from a business statement, PRD, scope, repo, ticket, bug, feedback item, design file, or partial artifact set.
   - Classify the work as new product, existing product change, greenfield, brownfield, bug fix, feature enhancement, release readiness, or feedback iteration.

2. **PM-led recommendations**
   - PM-OS suggests the next best PDLC action and explains why.
   - PM-OS does not autonomously decide or proceed across meaningful gates.
   - PM approves whether to generate, ingest, backfill, hand off, triage, defer, or stop.

3. **Artifact and decision traceability**
   - Maintain links from product intent to requirements, design decisions, dev tickets, QA scenarios, bugs, fixes, releases, and feedback.
   - Preserve provenance: which source artifact produced which PM-OS artifact or recommendation.

4. **External artifact consumption**
   - Consume Jira/Linear tickets, GitHub PRs/issues, codebase snapshots, QA results, design files, release notes, analytics, and feedback.
   - Store references and summaries, not necessarily copies of everything.

5. **Dev-phase support**
   - Produce dev-ready handoff packets.
   - Map implementation questions back to approved requirements.
   - Detect likely scope drift or requirement ambiguity.
   - Suggest developer action plans when issues arise.

6. **QA-phase support**
   - Produce QA scenarios and acceptance checks.
   - Map bugs to requirements, QA scenarios, code areas, tickets, and PRs.
   - Classify QA findings as implementation bug, unclear requirement, product gap, test mismatch, regression, or out-of-scope request.
   - Recommend next action and whether PM clarification is needed.

7. **Release and feedback loop**
   - Assess release readiness against QA, acceptance criteria, metrics instrumentation, known bugs, rollout risks, and open decisions.
   - Ingest post-launch feedback and outcomes.
   - Recommend iteration paths and artifact/ticket updates.

---

## 6. Lifecycle Checks

These are the checks PM-OS should enforce or recommend at each lifecycle phase.

| Phase | PM-OS check | Output |
|---|---|---|
| Intake | What is the user asking? What artifacts are present? Is this new/existing, greenfield/brownfield, feature/bug/release/feedback? | Intake summary and recommended path |
| Discovery | Is the problem, target user, urgency, and success hypothesis clear enough? | Brief or missing-info prompt |
| Scope | Is MVP boundary explicit? Are exclusions, assumptions, dependencies, and risks clear? | Scope artifact and approval prompt |
| PRD | Are requirements testable, scoped, prioritized, and traceable to goals? | PRD with acceptance criteria |
| Design | Do flows, states, UX behavior, accessibility, and design constraints match the PRD? | Design spec/prototype brief |
| Dev readiness | Can devs execute without guessing product intent? Are tickets/tasks traceable to requirements? | Dev handoff packet or Jira/Linear tickets |
| Development support | Does implementation work still map to approved requirements? Are dev questions product decisions or technical choices? | Clarification recommendation, scope drift warning, or updated handoff |
| QA planning | Do QA scenarios cover requirements, edge cases, regressions, and release blockers? | QA plan and test scenario set |
| QA bug triage | Which requirement/test scenario does the bug relate to? Is it product gap, implementation bug, unclear requirement, test mismatch, regression, or out-of-scope? | Bug analysis and suggested dev plan |
| Release readiness | Are must-pass tests complete? Are blockers known? Are metrics/release notes/rollout and rollback plans ready? | Release readiness report |
| Feedback | What did users/data/support reveal? Does this require doc, ticket, scope, or roadmap changes? | Feedback analysis and iteration recommendation |

---

## 7. Phased Implementation Plan

### Phase 0: Align the Product Contract

Goal: make the repo describe the same product we now want to build.

Work:

- Update README/spec language from "doc generator" to "PM-led PDLC operating layer."
- Reconcile seven-stage versus optional stage 08 wording.
- Add the decision authority model: PM decides, PM-OS recommends, dev/QA execute.
- Define lifecycle phases and terms: new product, existing product, greenfield, brownfield, artifact ingest, handoff, bug triage, release readiness, feedback loop.

Checks:

- README, spec, SOP, and this review use the same scope.
- No claim says PM-OS autonomously decides or replaces dev/QA execution.

Dependencies:

- PM approval of the product aim and boundaries.

Blockers:

- Need final naming for "PDLC operating layer" versus "lifecycle intelligence layer" if branding matters.

### Phase 1: Runtime Agnosticism — COMPLETE

When this phase was scoped it listed a gate-parity gap as the substantive item. Investigation showed that premise was **incorrect**: the gates were never Claude-native hooks. They run from `~/.pm-os/hooks` — `pre-stage.py` is invoked by inline bash in every stage `SKILL.md`, and `post-approve.py` is invoked by `pm_approve.py` via subprocess. Both paths are plain shell/Python the agent runs identically on Claude and Codex. There is no `settings.json` registering native hooks anywhere. The `~/.claude/hooks` copy that `install.sh` writes is **not on the execution path** (reserved for any future native-hook registration); skipping it on Codex is harmless.

What shipped to close the phase:

1. **Gate parity — verified, not just argued.** A deterministic self-test runs `pre-stage.py` exactly as the skills do, in a throwaway project, asserting it blocks an unapproved upstream and allows the first stage. Identical behavior on both runtimes.
2. **Runtime-neutral model guidance.** The deep-reasoning stages (03/04/06/08/09, plus context-build 00w/00u) give advisory deep-reasoning guidance; no `/model opus` hard-stop.
3. **Real `AGENTS.md`.** Full runtime-neutral agents file; the `claude-mem` stub was removed.
4. **Non-interactive gate safety.** `pre-stage.py` already had an `isatty()` branch plus `PM_OS_EDITED_UPSTREAM_CHOICE`; it errors with guidance instead of hanging. Covered by the verifier's timeout-guarded self-test.
5. **Install verifier.** `scripts/pm_os_verify.py` + the `pm-os-verify` skill check config, shared-lib imports, gate hooks, installed skills per runtime, and run the gate self-test. This is the verifier `pm_os_update.py` already pointed users to.

Remaining under "runtime": only **Gemini** support, deferred to a later phase.

Docs corrected in this phase: README / CLAUDE.md / AGENTS.md now make `~/.pm-os/hooks` the unambiguous execution path so the `~/.claude/hooks` copy is not mistaken for a parity gap.

### Phase 2: Flexible Intake and Artifact Ingest — COMPLETE (core)

Shipped 2026-06-17 as `/pm-context-import` (see `../archive/pm-os-ingest-plan.md` §0). The realized design is broader than the original per-stage import below: the PM provides **all the context they have**; PM-OS builds a **gated context wiki** (`00-context-wiki.md`) + **gated understanding doc** (`00-context-understanding.md`), then adopts the artifacts the PM authored (`origin: imported`) and faithfully backfills the upstream gaps below them (`origin: backfilled`), governed by a feasibility map. The business statement became a normal gated stage (`00`), and all present stage-00 docs must be approved before stage 01 (the gate lists exactly what's pending). `.meta.yaml` is now `schema_version: 3` with an in-place `migrate_meta` so existing projects keep working. Codebase-understanding has since been unified into the same stage-00 framework: enhancement projects (`/pm-new --mode enhancement --codebase <url-or-path>`, `schema_version: 3`) get a conditional gated `00c` codebase-understanding doc, produced by `/pm-context-import` via a read-only codebase scan, alongside the wiki/understanding docs. `.docx`/`.pdf` conversion is resolved (registered as document types in `pm_context_import.py`, extended to images/PPTX/XLSX by the adaptive-context-pack's Phase 1). Remaining: dogfooding a real Indegene enhancement end-to-end (I4).

Shipped in the same Phase 2 push (v0.5.3, PR #19): the **context overlay** (`lib/context.py` + `context.example/`) — a pluggable company/team/product knowledge layer loaded into every stage prompt (apply modes `augment`/`override`/`reference-only`; precedence project > stage > global). It is seeded on install/update (self-seeding on first read) and the live `~/.pm-os/context/` is gitignored user data the PM edits in place, so it never diverges `main`. Alongside it, the approval path gained real **telemetry metrics** (time-to-approve, edit distance, semantic distance, model id/tier) so generation quality can be measured rather than guessed.

Original Phase 2 sketch (superseded shape):

Goal: PM can start from partial existing context instead of a one-line statement only.

Work:

- Add `/pm-import`.
- Ingest existing scope/PRD as approved canonical artifacts.
- Preserve raw sources in `.history/`.
- Add `stage_imported` telemetry.
- Add visible imported marker in status.
- Backfill missing upstream artifacts through PM review, not silent generation.

Checks:

- Import PRD into stage 03 and run stage 04 without weakening upstream gates.
- Source provenance is visible.
- Imported artifacts do not pollute stage approval metrics.

Dependencies:

- Markdown import first.
- DOCX/PDF conversion can follow.

Blockers:

- Need decide normalization versus verbatim default.
- Need decide whether imported stages use status `approved` plus metadata marker, or a new status.

### Phase 3: Product Mode and Brownfield Understanding — ✅ COMPLETE (v0.5.9)

`/pm-new --mode enhancement --codebase <url-or-path>` scaffolds a project with `project_type: enhancement`, `codebase_path`, and `codebase_ref`. `pm_context_import.py prepare-codebase` clones (URL) or validates (local path) the codebase and records its git SHA. A conditional `00c` codebase-understanding doc is generated by `/pm-context-import` and gates stage 01 when present. `/pm-status` shows mode and warns on codebase SHA drift. Enhancement-aware conditional blocks land in the wiki consumption rules and stage-01 brief framing; downstream stages pick them up via the approved `00c` and context wiki. Both local-path and git URL are supported. See `docs/plans/pm-os-modes-and-handoff-plan.md` for the original plan and current status (Part B — handoff to Jira/Linear/Figma — remains unbuilt).

**Sequencing principle for Phases 4–6.** Every phase ships a **connector-free, local-first version first**; each external integration is a separate, opt-in, **read-before-write, dry-run -> confirm** unit. This keeps the per-PM, local, file-based flavour intact and stops the hardest/riskiest pieces (live code analysis, tracker writes) from blocking the simple, high-value ones. The `a` sub-phases need zero integrations and ship real PDLC coverage on their own; the `b` sub-phases are independently shippable and skippable.

### Phase 3.5: Traceability Spine — ✅ COMPLETE (v1.0.5)

Goal: give requirements and QA scenarios machine-stable IDs and local links, so everything downstream can reference them. No integrations.

Shipped: stable `REQ-###`/`US-###`/`FR-###` IDs in the PRD contract and `TC-###` IDs in the QA plan contract, formalized in `lib/artifact_contracts.py`; a local `.traceability.yaml` link file connecting `REQ` ↔ `TC`; a resolver (`lib/traceability.py`) that answers "which scenarios cover requirement REQ-X" locally; and automatic link-table rebuild on stage approval. Landed alongside the adaptive context pack (schema v4) — see [PR #29](https://github.com/pingmepi/pm-os/pull/29).

Checks (met):

- Each requirement and QA scenario has a stable ID that survives regeneration.
- PM-OS can resolve "which scenarios cover requirement REQ-X" locally.

### Phase 3.5b: TRD Task IDs — ✅ COMPLETE

Goal: extend the traceability spine down into the TRD so engineering work is machine-addressable — the prerequisite for exporting tickets in Phase 4b. No integrations.

Shipped: a mandatory **Work Breakdown** section in the stage-08 TRD contract that enumerates discrete tasks with stable `TSK-###` ids, each declaring `Implements:` the PRD requirement(s) it delivers; a `TSK-###` parser (`split_task_blocks`, `task_implements`, `task_id_declarations`) in `lib/artifact_contracts.py`; a `tasks:` map in `.traceability.yaml` (schema **v2**) with reverse requirement↔task links and a reserved `tickets: []` slot, rebuilt on stage-08 approval; resolver queries (`tasks_for_requirement`, `requirements_for_task`) + a `pm_trace.py task` subcommand; and `/pm-check` validation (unique/sequential ids as error/warning, orphan/unknown-requirement/coverage as warnings). The traceability schema is a derived index, so a v1 file on disk upgrades transparently on the next rebuild.

Checks (met):

- Every TRD task has a stable `TSK-###` id that traces to an approved PRD requirement.
- `.traceability.yaml` resolves "which tasks implement requirement REQ-X" (and back) locally.
- `/pm-check` flags duplicate/gap/orphan task ids and PRD requirements no task implements.

### Phase 3.6: Automated Test Suite (foundational — infra alongside Phase 3.5)

Goal (met — see status above): give a contributor **one repo-level command** that yields real confidence in both halves of PM-OS — the deterministic Python state machine *and* the Markdown skill/doc contract — without ever touching the installed `~/.pm-os`, `~/.agents/skills`, or `~/.claude/skills`. Originally the only smoke test was `pm_os_verify.py` against the install, with no `pytest`, linter, or CI beyond version-bump. Design was captured in `docs/archive/pm-os-test-implementation-plan.md` (drafted 2026-06-18, now archived); the live reference is `docs/guides/testing.md`.

Work:

- Add `pyproject.toml` with pytest config and markers: `unit`, `integration`, `contract`, `connection`, `slow`.
- Add `tests/` (`conftest.py`, `helpers.py`, `unit/`, `integration/`, `contracts/`, `fixtures/`) with fixtures for isolated HOME-like temp dirs and throwaway PM-OS installs.
- Cover: `lib/` modules (`project`, `frontmatter`, `hashing`, `config`, `telemetry`, `text_metrics`, `html_render`, `git_sync`, `context`); the full lifecycle (`pm_new` → approve → gates → stale → status → share); deliverable/format contracts (skill frontmatter, stage artifact sections, runtime examples); runtime parity (install/update/verify for Claude and Codex); context import + provenance; telemetry metrics; negative/resilience (malformed meta, corrupt telemetry, idempotent recovery); local-first boundaries (no default network, HTML escaping); and doc-drift (stage lists, runtime paths, model-tier policy).

Checks:

- `python3 -m pytest` is green from a clean checkout; markers run subsets (`-m unit` / `-m integration` / `-m contract`).
- Gates block unsafe progression and allow valid progression inside isolated temp projects.
- No test writes to real user dirs or hits the network; external side effects point at local temp repos.

Dependencies:

- Tests target the repo source tree directly — never the installed runtime dirs.
- Runs before the handoff/triage/release phases so their ID-linked behavior is regression-protected.

Out of scope (this phase): LLM prose-quality evaluation, real Claude/Codex skill invocation, pushing to the real feedback repo, mutation/visual-regression testing.

### Phase 4: Handoff and External Work Artifacts

Goal: connect approved product intent to the systems dev/QA actually use — value first, connectors second.

**Phase 4a — Local handoff packet (zero integrations).**

- Generate a dev-ready handoff doc from approved PRD/TRD/QA using the Phase 3.5 stable IDs.
- Pure local Markdown; no auth, no network. This is most of Phase 4's value with none of the connector risk.

Checks:
- Handoff packet lists each requirement with its acceptance criteria and covering `TC` IDs.
- Generated entirely offline from approved artifacts.

**Phase 4b — One tracker, export-only (opt-in, dry-run -> confirm -> create).**

- Pick the single tracker the PM actually uses (Linear *or* Jira, not both).
- Export tickets in dry-run -> PM confirm -> create flow; read ticket IDs back into local state.
- GitHub/GitLab PR/commit refs and Figma source links are **separate, later, read-only "reference capture" units** — not bundled here.

Checks:
- Tickets map to requirements and acceptance criteria via stable IDs.
- PM confirms before any external object is created or updated.
- Only references/IDs/summaries are stored locally — never bulk copies of external data.

Dependencies:
- Phase 3.5 stable IDs.
- Local CLI/token access for the one chosen tracker.

Blockers:
- Need connector/auth policy (tokens from env/local config; see Section 8 and Risks).

### Phase 5: QA Bug Triage and Dev Fix Guidance

Goal: support the dev/QA phase without replacing devs or QAs. Split the reliable part from the error-prone part so the latter cannot taint the former.

**Phase 5a — Bug intake + classification (no code analysis).**

- Manual/Markdown bug intake.
- Link bug to QA scenario, acceptance criteria, requirement, and (if present) ticket via stable IDs.
- Classify bug type: implementation bug, product gap, unclear requirement, test mismatch, regression, out-of-scope request.
- Recommend next action; flag when PM clarification is needed.
- Deterministic-ish, genuinely useful, needs no repo access.

Checks:
- Given a QA bug tied to a `TC`, PM-OS produces a traceable triage report locally.
- PM-OS flags product-decision bugs instead of pretending they are pure dev fixes.

**Phase 5b — Code-area suggestion (the hard, error-prone part — quarantined).**

- Repo snapshot + recent-changes heuristic -> candidate files -> suggested fix plan and tests.
- Explicit opt-in; always cites evidence; never auto-acts; output is clearly labelled "suggestion."
- Isolated from 5a so its uncertainty cannot contaminate 5a's reliable triage output.

Checks:
- Developer can execute the suggested plan directly, while still owning implementation and verification.
- Every suggested code area cites the evidence it was derived from.

Dependencies:
- Phase 3.5 stable IDs; Phase 5a triage record.
- Codebase understanding and codebase refs (Phase 3); read-only repo access.

Blockers:
- No codebase mapping capability implemented yet.

### Phase 6: Release Readiness and Feedback Loop

Goal: close the lifecycle after development and QA — local rollups first.

**Phase 6a — Release-readiness report (local rollup).**

- Aggregate already-local state: QA status, open bugs (from 5a), acceptance-criteria coverage, metrics-plan instrumentation, known blockers, rollout/rollback note, unresolved PM decisions.
- No new integration.

Checks:
- PM-OS produces a release-readiness report grounded in approved artifacts and local bug/triage state.
- PM approves any change to scope, requirements, or roadmap.

**Phase 6b — Feedback intake + iteration recommendation (local).**

- Manual/Markdown feedback intake.
- Classify feedback; link to requirements, bugs, releases, and backlog candidates via stable IDs.
- Recommend iteration actions to the PM.
- Analytics/support connectors are optional add-ons later, using the same read-only, opt-in pattern as Phase 4b.

Checks:
- Feedback items are classified and linked to product decisions or backlog candidates locally.
- PM approves any resulting scope/requirement/roadmap change.

Dependencies:
- Phase 3.5 stable IDs; Phase 5a bug records.

Blockers:
- No release artifact model yet (introduced in 6a).

---

## 8. Proposed Data Model Additions

**Preserve the existing flavour.** PM-OS runs per-PM on the PM's own machine: state is flat files at the project root (`.meta.yaml`, `.history/`, `telemetry.jsonl`, `feedback.jsonl`, numbered `NN-*.md` artifacts). The additions below keep that convention — **no new hidden `.pm-os/` subdirectory**, no server, no shared service. Small structured state folds into `.meta.yaml`; append-logs sit beside the existing ones at the root; larger structured records become sibling dotfiles.

**Add a `schema_version` first.** Every new field must land without breaking existing projects, so introduce a version marker that migrations key off:

```yaml
schema_version: 2          # existing projects default to 1 and migrate on next command
project_type: new_product | enhancement
codebase:
  path: <absolute-path-or-null>
  ref: <git-sha-or-null>
lifecycle:
  current_phase: intake | discovery | design | dev | qa | release | feedback
  recommended_next_actions: []
```

`schema_version`, `project_type`, `codebase`, and `lifecycle` live in `.meta.yaml` (small, frequently read).

Larger structured records, as flat files at the project root — matching the existing naming convention, **not** under a new directory:

- `.sources.yaml` — external artifact registry (dotfile, like `.meta.yaml`). Each entry:
  ```yaml
  - id: src_...
    type: prd | scope | repo | jira_ticket | jira_bug | github_pr | figma | feedback
    uri: <path-or-url>
    captured_at: <iso8601>
    summary_hash: <sha256-or-null>
  ```
- `.traceability.yaml` — requirement/test/ticket/bug/code links keyed by the Phase 3.5 stable IDs (`REQ-…`, `TC-…`).
- `recommendations.jsonl` — PM-OS suggestions and PM decisions (append-log, beside `telemetry.jsonl`).
- `imports.jsonl` — ingest provenance (append-log, beside `feedback.jsonl`).

Principles:

- Store enough canonical state to preserve decisions and traceability, but **reference** external systems — store IDs, URIs, and summaries locally, never bulk copies of external data.
- Connectors read credentials from env / local config; secrets are never written into project files or telemetry.
- All state stays local to the PM's machine, file-based and human-gated — the same model PM-OS has today.

---

## 9. Key Risks

| Risk | Why it matters | Mitigation |
|---|---|---|
| PM-OS becomes another competing source of truth | Teams already use Jira, GitHub, Figma, docs | Reference and consume external artifacts; do not copy blindly |
| Too much automation undermines PM authority | The ask explicitly keeps decisions with the PM | Recommendation-first UX with approval gates |
| Linear stages do not match real PDLC | Teams enter from PRDs, bugs, repos, tickets | Add intake and artifact graph around the stage pipeline |
| External integrations create data/security exposure | Tickets/repos/design files may contain sensitive data | Connector policy, provenance, user confirmation, sanitization guidance |
| Bug/code analysis produces false confidence | Code mapping can be wrong | Classify as suggestions, cite evidence, require dev execution/verification |
| Cross-runtime support drifts | Claude/Codex skill behavior differs | One source of truth, adapter/install tests per runtime |
| Telemetry schema gets polluted | Imported/external artifacts differ from generated drafts | Separate event types: imported, linked, triaged, recommended, decided |

---

## 10. Immediate Next Steps

Recommended order:

1. ~~Approve the product aim and scope in this document.~~ (done)
2. ~~Update README/spec/SOP to reflect the expanded PDLC scope and PM/dev/QA authority model.~~ (done — Phase 0)
3. ~~Finish runtime parity (Phase 1): model wording, real `AGENTS.md`, non-interactive gate, install verifier. Gate parity confirmed (gates run from `~/.pm-os/hooks`, not native hooks).~~ (done — Phase 1)
4. ~~Add `schema_version` and the migration path so existing projects survive new fields.~~ (done — `.meta.yaml` is `schema_version: 2` with in-place `migrate_meta`)
5. ~~Implement artifact ingest for existing scope/PRD (Phase 2).~~ (done — shipped as `/pm-context-import`: gated context wiki + understanding doc, adopt + feasibility-governed backfill; see `../archive/pm-os-ingest-plan.md` §0)
6. ~~Ship the context overlay so company/team knowledge flows into every stage.~~ (done — v0.5.3, `lib/context.py` + `context.example/`, gitignored user data)
7. ~~Implement enhancement mode and codebase understanding (Phase 3).~~ — **DONE** (`/pm-new --mode enhancement --codebase`, `00c` stage, `prepare-codebase`, schema v3, codebase drift signal in `/pm-status`; shipped v0.5.9). Standalone HTML prototype (`pm-prototype-html`) and artifact quality contracts also shipped (v0.5.11 / v0.6.0).
8. ~~Add stable IDs to requirements and QA scenarios (Phase 3.5)~~ — **DONE** (`REQ-`/`US-`/`FR-` IDs in the PRD, `TC-` IDs in the QA plan, `.traceability.yaml` link file + resolver, shipped v1.0.5). Foundational before the handoff, triage, and release phases that link by ID. Shipped alongside the **adaptive context pack** (composite hashing, schema v4, modular pack across stages 01–09; v1.0.6).
9. ~~Stand up the automated test suite (Phase 3.6)~~ — **DONE** (pytest suite T0–T10 under `tests/`, CI at `.github/workflows/tests.yml`, reference in `docs/guides/testing.md`). Locks current behavior before the ID-linked phases land. **T10 — `/pm-check` consistency toolkit** (a PM-facing reuse of the suite's invariants) has also shipped; its original design lives in `../archive/pm-os-test-implementation-plan.md` §19.
10. Add the PM-OS quality, operations, usage, and self-improvement loop so telemetry/feedback turn into readable metrics, suggestions, PM decisions, and implementation plans without automatic source changes. See `../plans/pm-os-self-improvement-loop-plan.md`.
11. Ship local handoff packet (4a), then one opt-in tracker export (4b).
12. Ship bug intake + classification (5a), then quarantined code-area suggestion (5b).
13. Ship local release-readiness report (6a), then feedback intake (6b).

---

## 11. Current Verdict

PM-OS today is a useful and coherent **stage-gated product-definition tool with flexible intake**.

It already has the right instincts: local-first state, explicit approvals, artifact hashes, staleness checks, PM-visible review points, and — as of Phase 2 — the ability to adopt existing PM-authored context through a gated understanding step instead of regenerating it. The v0.5.3 **context overlay** adds a second instinct worth keeping: company/team/product knowledge flows into every stage's generation as gitignored, edit-in-place user data. The v1.0.5 **traceability spine** adds a third: requirements and QA scenarios now carry stable IDs with a local, resolvable link table — the first concrete thread of the PDLC context graph the target product needs.

To meet the expanded ask, it needs to evolve into a **PM-led PDLC context graph and recommendation system**. The current codebase is the kernel, and flexible intake (from PM-authored documents) and requirements traceability now exist; the next major work is not simply "add more stages." The larger remaining move is to add external artifact ingestion (repos/trackers/design files), dev/QA support workflows, release readiness, and feedback loops — extending the traceability spine to link bug/ticket/code refs — while preserving PM authority and human execution.
