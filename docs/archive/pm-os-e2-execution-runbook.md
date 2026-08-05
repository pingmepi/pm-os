# PM-OS E2 (Read-only, Affected-slice Enhancement) — Execution Runbook

**Status:** ✅ Shipped — merged to `main` in **v1.5.0** (PR #68, 2026-08-05), including two Codex-review rounds and the zip-codebase-source + mandatory-boundary-gate follow-ups. Design source: `pm-os-entry-pathways-plan.md` phase **E2** and `pm-os-modes-delivery-and-handoff-plan.md` Part A behavior table. E2 now provides one-product-project continuation, a read-only repository inventory in `00c`, affected-slice/impact-cone discovery, a decision interview, scoped in-place stage evolution, regression traceability, delta-only handoff, explicit refresh/completion, and immutable two-cycle provenance.

**Execution branch:** `feat/e2-affected-slice-enhancement`, created from refreshed `main` at `0296e0f` after E3 landed. Execute all loops without a PM-review pause. Do not commit, push, publish, or update the installed runtime unless separately requested.

**Read before starting:** `pm-os-entry-pathways-plan.md` §§2b, 5–9; `pm-os-modes-delivery-and-handoff-plan.md` §§5–8, especially the enhancement behavior table and the Part-B boundary; `docs/reference/codebase-wiki-format.md`; `skills/pm-context-import/SKILL.md`; `skills/pm-context-scan-codebase/SKILL.md`; stage skills 01–09; `lib/project.py`; `lib/artifact_contracts.py`; `lib/traceability.py`; `lib/consistency.py`; `scripts/pm_context_import.py`; `scripts/pm_check.py`; `scripts/pm_handoff.py`; `docs/guides/testing.md`; and `CLAUDE.md`/`AGENTS.md`.

---

## 0. Operating protocol — the building loop

Execute the loops in order. Every loop is a strict cycle:

1. **AIM** — restate the single observable outcome.
2. **TESTS (first)** — add the named tests and run them. Confirm red for the intended missing behavior, not because of a broken fixture or environment.
3. **CODE** — make the smallest production change that satisfies the tests. Stay inside the loop's file boundary.
4. **VERIFICATION** — run the targeted test set and the named contract/integration checks.
5. **PASS-IF-GREEN** — fix implementation defects and rerun. Do not weaken the acceptance intent or advance while red.
6. **UPDATE TASKS** — check off the loop, record evidence and test counts, and mark the next loop in progress.

### Regression cadence

- Loop 0 records the current `main` collection count and full-suite result. Never hard-code an old count.
- Run `python3 -m pytest -q` after Loops 2, 4, 6, 8, 10, and 12, and before any PM review handoff.
- The collected test count may increase but must not decrease. A previously green test turning red is a regression and blocks the next loop.
- At every full-suite gate also run `git diff --check` and inspect `git status --short` so unrelated work is never absorbed.
- Tests must use the isolated harness in `tests/conftest.py`; no test may read from or write to the real `~/.pm-os`, runtime skill directories, or a real PM project.

### Global invariants — enforce in every loop

- **Target repository is read-only.** E2 may read files and Git metadata. It may not write, format, install dependencies, run generators, switch refs, modify the index/worktree, create build output, or write its own wiki into the product repository. A remote repository is cloned into storage owned by the PM-OS project.
- **One product, one PM-OS project.** An external product creates one PM-OS project on first intake. PM-OS-native and previously imported products run later enhancements in that same project. Never create an enhancement child/sibling project or a second approval lineage.
- **Identity is not work state.** `project_type` remains first-intake identity. The E2 continuation context activates scoped enhancement behavior but adds no competing approval/status state machine.
- **`00c` is the repository-inventory artifact.** The lightweight whole-repository inventory, affected slice, impact cone, coverage, exclusions, evidence, and confidence are written into `00-codebase-understanding.md`. Do not create a parallel codebase wiki.
- **Slice first, widen on evidence.** Begin from the approved ask, but follow shared dependencies, consumers, APIs/events, data/schema, permissions, configuration, tests, observability, deployment, and package/service boundaries. Uncertainty is recorded; it is never silently treated as coverage.
- **Canonical artifacts remain the product-of-record.** Update only affected stable-ID blocks/sections in stages 01–09 and carry unaffected content forward. The delta is computed from the captured baseline; it is not a detached replacement document.
- **All product surfaces are valid.** UI, API, data, service, event, integration, and operations are first-class. Stages 04/05 must not invent screens or HTML for non-UI enhancements.
- **Promotion is out of scope.** `/pm-promote` remains the separate Part-B operation for moving requirements among `mvp | v1 | v2 | later`. E2 consumes tier data when present and preserves current default-MVP behavior when absent.
- **Judgment stays in skills; mechanics stay in Python.** Question prioritization, impact interpretation, and stage synthesis belong in skill instructions. Python owns deterministic state, parsing, hashing, diffs, checks, and exports.
- **Cross-runtime parity.** Every new or changed skill updates both `SKILL.md` and `agents/openai.yaml`; provider-specific model IDs never enter shared configuration or artifacts.
- **Marketplace code is optional.** PM-OS-owned contracts and fallbacks remain authoritative. Any borrowed code is commit-pinned, license-attributed, security/read-only reviewed, and accessed through a PM-OS adapter. Absence of a marketplace tool must not block E2.

### Frozen E2 contract (Loop 1)

- **Entrypoint:** new cross-runtime skill `/pm-enhance`, backed by `scripts/pm_enhance.py`. Mechanical subcommands are `start`, `show`, `set-boundary`, `delta`, `refresh`, and `complete`.
- **Storage:** `.enhancements/index.yaml` stores `schema_version`, `active_cycle`, `next_sequence`, and ordered cycle IDs. Each cycle lives at `.enhancements/EH-NNN/context.yaml`; its captured approved artifacts live under `.enhancements/EH-NNN/baseline/`.
- **Lifecycle without a second status model:** `active_cycle` is either one cycle ID or null. A cycle carries `started_at` and an optional `completed_at`, never a stage-like `status` or approval value. `start` refuses a second active cycle; `complete` clears the pointer after normal PM-OS gate/check prerequisites pass. A completed context and its baseline are immutable.
- **Context shape:** cycle ID, previous cycle ID, PM-authored ask path/hash, captured approved artifact paths/body hashes, repository source/path/requested ref/resolved SHA/scan start+end SHA/dirty flag/subpath, affected stable IDs, affected surfaces, explicit non-touch surfaces, regression invariants, compatibility/migration notes, rollout/rollback notes, coverage/exclusions/confidence, and timestamps.
- **Identity:** `project_type` and `entry_route` are never changed by `/pm-enhance`. External first intake may already carry `project_type: enhancement`; PM-OS-native products retain `new_product`.
- **Vocabulary:** change type is exactly `new | modified | removed`; affected surface is one or more of `ui | api | data | service | event | integration | operations | cross-cutting`.
- **Baseline/delta:** `start` copies every currently approved artifact into the cycle baseline and records its authoritative body hash. `delta` compares that frozen baseline with the current canonical artifacts and emits only changed stable-ID blocks plus required context; it never treats the delta as the canonical product definition.
- **Repository safety:** local targets are opened read-only; only read-only Git commands are permitted. Remote sources clone under the PM-OS project. Before/after SHA, dirty state, porcelain status, and a deterministic repository fingerprint prove that the target was not mutated.
- **Inventory:** `00c` remains the only user-facing repository inventory. Its contract adds Repository identity, Inventory & ownership boundaries, Enhancement ask, Affected slice, Impact cone, Explicit non-touch surfaces, Coverage/exclusions/confidence, and the existing product/architecture/data/stack/design/integration/debt sections.
- **Marketplace boundary:** external repositories supply reviewed patterns only. E2 ships PM-OS-owned instructions/helpers and has no runtime dependency on those repositories.

### Stop conditions

Stop and escalate instead of guessing if a loop would:

- change approval/status semantics or introduce a second state machine;
- require target-repository writes or command execution beyond explicitly approved read-only Git inspection;
- silently replace an approved baseline or an immutable prior enhancement record;
- require a breaking artifact/schema change without migration and backward-compatibility tests;
- proceed with unknown repository identity, unresolved scan drift, no approved change boundary, or missing regression invariants;
- overload `/pm-promote`, `project_type`, or Part-B delivery increments to mean “start enhancement.”

---

## 1. Definition of done

E2 is done only when all of the following are demonstrated:

- Both first-time external-product intake and later same-project enhancement reach the same read-only scan → boundary → scoped stages → check → handoff path.
- Two consecutive enhancements in one project prove baseline rollover, immutable provenance, stable unaffected IDs/content, and no child project.
- `00c` contains a lightweight whole-repository inventory and an evidence-cited affected slice/impact cone, with explicit coverage, exclusions, confidence, repository identity, requested/resolved refs, scan start/end SHAs, dirty state, and optional monorepo subpath.
- The target repository passes with write permissions removed and remains byte-for-byte/Git-state unchanged.
- The decision interview asks unresolved product decisions, not code facts, and blocking unknowns prevent boundary approval unless an accepted risk is recorded.
- The modes-plan behavior table is implemented across `00c`/`00u`, stages 01–09, checks, and handoff for UI and non-UI surfaces.
- Every `new | modified | removed` requirement traces to affected surfaces, validation, implementation tasks, rollout/rollback where applicable, and the captured baseline.
- Every non-touch/regression invariant maps to QA coverage; every compatibility/migration requirement maps to tasks, tests, observability, and rollback criteria.
- Handoff/Jira export includes only delta work plus the minimum ancestor/context closure, never unaffected baseline work.
- Existing greenfield, prototype, installed-runtime, handoff, and traceability behavior stays green; migrations preserve old projects.
- Focused E2 tests, the full suite, contract tests, and isolated end-to-end smokes are green and cataloged in `docs/guides/testing.md`.

---

## 2. Task checklist

- [x] **Loop 0** — Baseline, branch, and architecture orientation
- [x] **Loop 1** — E2.0 contract freeze + marketplace/adaptation spike
- [x] **Loop 2** — Enhancement context, same-project continuation, and baseline capture
- [x] **Loop 3** — Read-only repository identity and `00c` inventory
- [x] **Loop 4** — Affected-slice and impact-cone scanner
- [x] **Loop 5** — Decision interview and approved enhancement boundary
- [x] **Loop 6** — Scoped canonical stages 01–03
- [x] **Loop 7** — Surface-aware stages 04–05
- [x] **Loop 8** — Regression/operations stages 06–09
- [x] **Loop 9** — Traceability, consistency, and status guidance
- [x] **Loop 10** — Delta-only package and Jira handoff
- [x] **Loop 11** — Refresh, migration, and backward compatibility
- [x] **Loop 12** — Two-path, two-cycle end-to-end dogfood and finalization

---

## Loop 0 — Baseline, branch, and architecture orientation

- **AIM:** establish a reproducible green baseline and an evidence map of the code paths E2 will extend.
- **TESTS:** none; this is an orientation loop.
- **CODE:** none.
- **ORIENT:** from a clean branch based on current `main`, record `git rev-parse HEAD`, `python3 -m pytest --collect-only -q`, `python3 -m pytest -q`, and `git status --short`. Read the files listed at the top of this runbook. Trace current `.meta.yaml` migration, stage hashing/history/staleness, `00c` creation, stage skill preflights, traceability indexing, consistency checks, status, share/handoff, and the existing read-only boundary tests.
- **VERIFICATION:** baseline full suite green; no unexplained worktree changes; current main commit and collected count recorded in the task log.
- **PASS-IF-GREEN:** the executing agent can point to the authoritative implementation locations for each E2 concern and no implementation has started from the E3 branch.
- **UPDATE TASKS:** check Loop 0; start Loop 1.

## Loop 1 — E2.0 contract freeze + marketplace/adaptation spike

- **AIM:** remove architectural ambiguity before production code: freeze the in-project command/context contract, `00c` schema additions, affected-surface/change-type vocabulary, read-only threat model, and marketplace adaptation boundary.
- **TESTS (first):** add contract fixtures that describe, without implementing, these observable cases:
  - first enhancement for an external product and later enhancement for the same project converge without a child project;
  - a PM-OS-native project keeps `project_type` unchanged;
  - one active enhancement has a unique immutable identifier, ask source, baseline artifact hashes, pinned code ref, affected IDs/surfaces, timestamps, and prior-cycle linkage;
  - lifecycle operations are explicit and idempotent; an active or completed context cannot be silently overwritten;
  - scan output has inventory/slice/impact-cone/coverage/exclusions/confidence sections in `00c`;
  - the target fixture is unwritable and no repo state changes;
  - UI-only, API/data-only, cross-cutting, monorepo, and unresolved-dynamic-boundary fixtures produce inclusion and exclusion evidence.
  Confirm these contract tests fail because the E2 contract is absent.
- **SPIKE:** evaluate patterns from the PM-provided `affaan-m/ecc`, `obra/superpowers`, and `ComposioHQ/awesome-claude-skills` sources. Record commit, license, useful behavior, filesystem/network/subprocess behavior, Claude/Codex portability, and adopt/adapt/reject reasoning. Use them as inspiration for PM-OS-owned inventory/focus, dependency-impact, TDD, systematic-debugging, and verification skills; do not install them into the protected runtime or make them required dependencies.
- **CODE:** no production feature code. Add a short E2 contract decision section to this runbook or a linked ADR that fixes exact command names, persisted paths/schema, lifecycle, vocabulary, adapters, and rollback rules. Replace every downstream ambiguity with that decision before continuing.
- **VERIFICATION:** fixture spike shows useful coverage/exclusion output and proves no target-repository writes. The contract above resolves every interface needed by later loops; run the new contract tests only to preserve the expected red baseline.
- **PASS-IF-GREEN:** “green” here means the contract and spike evidence satisfy the global invariants. Production implementation remains red and has not begun.
- **UPDATE TASKS:** check Loop 1 after the contract/spike evidence is recorded; start Loop 2 without a PM-review pause.

## Loop 2 — Enhancement context, same-project continuation, and baseline capture

- **AIM:** start enhancement work inside the existing product project and capture an immutable, reproducible pre-change baseline without changing product identity.
- **TESTS (first):** add integration tests covering external first intake, PM-OS-native continuation, previously imported continuation, stable `project_type`, exact approved stage hashes, pinned code ref, one active context, idempotent retry, refusal to overwrite/parallel-start, retained completed context, and telemetry without approval/status duplication. Add schema-migration red tests before adding any `.meta.yaml` field.
- **CODE:** implement the Loop-1 command/context contract; centralize migration in `migrate_meta()` if meta changes; capture hashes using existing artifact hashing and locks; use normal telemetry primitives; do not create child projects or a new gate.
- **VERIFICATION:** targeted lifecycle/migration tests; `tests/integration/test_approval_and_staleness.py`; project lifecycle and telemetry tests; full suite.
- **PASS-IF-GREEN:** the captured baseline is reproducible and immutable, retry-safe, and independent of `project_type`; all existing projects still load.
- **UPDATE TASKS:** check Loop 2; start Loop 3.

## Loop 3 — Read-only repository identity and `00c` inventory

- **AIM:** bind a repository snapshot unambiguously and place a lightweight whole-repository inventory in `00c` without writing to the target.
- **TESTS (first):** add integration tests for local clean/dirty repos, detached/requested refs, ref drift, scan start/end SHA mismatch, remote clone into PM-OS-owned storage, optional monorepo subpath, missing/unavailable evidence, write permissions removed, unchanged file hashes, unchanged `git status`, and forbidden subprocesses that could mutate the target.
- **CODE:** strengthen the PM-OS-owned codebase scanner and context import mechanics. Record repository identity, supplied source, requested ref, resolved SHA, scan start/end SHA, dirty/non-reproducible status, subpath, coverage, exclusions, and confidence in the enhancement context and `00c`. A refresh must be explicit; preparation must not disguise an old `00c` as current.
- **VERIFICATION:** targeted scanner/local-first tests; `tests/contracts/test_local_first_boundaries.py`; context-import integration tests. Inspect target fixture hashes and Git state before/after.
- **PASS-IF-GREEN:** `00c` owns the inventory, no parallel wiki exists, every baseline mismatch is visible, and the unwritable repository passes.
- **UPDATE TASKS:** check Loop 3; start Loop 4.

## Loop 4 — Affected-slice and impact-cone scanner

- **AIM:** turn the approved ask plus whole-repository inventory into a bounded, evidence-cited change surface and dependency cone that widens when evidence demands it.
- **TESTS (first):** add scanner tests for UI-only, API/data-only, service/event, integration, operations, shared-library expansion, upstream consumers, schema/config/permission/test/observability/deployment edges, monorepo cross-package edges, dynamic/reflection uncertainty, generated/ignored files, and explicit non-touch surfaces. Assert stable machine-readable output plus rendered `00c` content, coverage, exclusions, confidence, and widen reasons.
- **CODE:** implement PM-OS-owned inventory/focus/dependency adapters selected in Loop 1. Keep deterministic discovery in Python and impact judgment in the skill. Never execute target builds or dependency installation. Preserve a portable fallback that uses repository files and read-only Git inspection only.
- **VERIFICATION:** targeted slice fixtures; read-only boundary tests; context scan skill contract tests; full suite. Manually inspect one UI and one non-UI `00c` output for usefulness and evidence quality.
- **PASS-IF-GREEN:** a narrow ask does not miss obvious cross-cutting dependencies, uncertainty is visible, and unrelated repository areas are excluded with reasons rather than absorbed as product scope.
- **UPDATE TASKS:** check Loop 4; start Loop 5.

## Loop 5 — Decision interview and approved enhancement boundary

- **AIM:** convert code facts and PM answers into one binding stage-00 enhancement boundary before downstream generation.
- **TESTS (first):** add contract/integration tests that questions cover only unresolved production baseline, why/outcome, current→target behavior, affected/non-touch surfaces, regression invariants, success, compatibility/migration, rollout/rollback, and authority. Cited code facts are not re-asked. Unresolved baseline/delta/invariants/required migration are blocking unless an accepted risk is explicit; lower-impact skips remain known unknowns. The interview never self-approves.
- **CODE:** extend the appropriate existing context-import/interview skill, not `repo-interview-prep`. Reuse the current answer provenance and known-unknown mechanisms. Render the approved boundary into `00-context-understanding.md` and reference the `00c` evidence; use existing stage-00 approval/hash/staleness behavior.
- **VERIFICATION:** interview and known-unknown tests; stage-00 gate tests; skill contract tests; a non-tty run with answers file and a skip run that never hangs.
- **PASS-IF-GREEN:** downstream stages cannot run without an approved, evidence-backed boundary or explicit accepted-risk handling; no code fact is turned into intent.
- **UPDATE TASKS:** check Loop 5; start Loop 6.

## Loop 6 — Scoped canonical stages 01–03

- **AIM:** evolve the product brief, scope, and PRD in place for the approved slice while preserving unaffected canonical content and stable IDs.
- **TESTS (first):** add stage contract tests for affected-block replacement/addition/removal, byte-stable unaffected blocks where mechanically possible, collision-free stable IDs, `new | modified | removed`, current→target behavior, affected surfaces, non-touch invariants, compatibility/migration, and Part-B tier preservation when present. Assert legacy projects without tiers remain valid.
- **CODE:** add enhancement overlays to stage skills 01–03 and deterministic merge/diff helpers where needed. The generated canonical artifact must remain a complete current product definition; a separate computed delta view identifies only changes. Use normal history snapshots, hashes, approval, regeneration count, and downstream staleness.
- **VERIFICATION:** focused stage/artifact contract tests; approval/history/idempotency tests; full suite. Compare before/current artifacts and verify unaffected IDs/content.
- **PASS-IF-GREEN:** stages 01–03 satisfy the corresponding rows of the modes-plan enhancement behavior table and no detached delta-only PRD replaces the product definition.
- **UPDATE TASKS:** check Loop 6; start Loop 7.

## Loop 7 — Surface-aware stages 04–05

- **AIM:** design and validate the enhancement using artifacts appropriate to every affected surface, without forcing frontend output.
- **TESTS (first):** add contract tests for UI, API, data, service/event, integration, operations, and mixed-surface enhancements. UI retains `SCR-###` compatibility; non-UI work emits appropriate contract/example/migration/harness/sandbox/runbook validation and does not require screens or HTML. Mixed-surface outputs trace to the same affected requirement IDs.
- **CODE:** update stage 04/05 skills, artifact contracts, prototype-brief behavior, and prototype routing. Generate HTML only when UI is affected; reuse existing prototype tooling unchanged for UI paths.
- **VERIFICATION:** stage 04/05 contracts; prototype and HTML tests; representative UI and API/data artifacts reviewed against the behavior table.
- **PASS-IF-GREEN:** every affected surface has an actionable design/validation representation and no fake frontend artifact appears for non-UI work.
- **UPDATE TASKS:** check Loop 7; start Loop 8.

## Loop 8 — Regression/operations stages 06–09

- **AIM:** complete QA, metrics, technical delivery, and roadmap consequences for the slice, including regressions, compatibility, rollout, and rollback.
- **TESTS (first):** add contracts asserting: each invariant has QA coverage; each changed requirement has delta acceptance cases; migration/compatibility/permissions/mixed-version/flag/rollback cases exist when declared; metrics include change, guardrail, data-quality, and rollback thresholds; TRD tasks implement affected requirements and operational work; roadmap changes only when timing/dependency consequences exist and respects Part-B tiers.
- **CODE:** add scoped enhancement behavior to stage skills 06–09 and the relevant artifact contracts. Preserve unaffected cases/tasks/roadmap items; remove or revise only entries justified by the approved boundary.
- **VERIFICATION:** stage 06–09 contracts; traceability and TRD consistency tests; full suite; one cross-cutting artifact set reviewed end-to-end.
- **PASS-IF-GREEN:** stages 06–09 implement their behavior-table rows and all regression/migration/operations obligations are explicit and traceable.
- **UPDATE TASKS:** check Loop 8; start Loop 9.

## Loop 9 — Traceability, consistency, and status guidance

- **AIM:** make missing, stale, or contradictory E2 links mechanically visible and tell the PM the next safe action.
- **TESTS (first):** add checks for context↔`00c` repository mismatch, current checkout drift, missing affected-surface/change-type links, changed requirements without tests/tasks, invariants without regression cases, migration without rollout/rollback/observability, baseline hash mismatch, unstable unaffected IDs, and stale downstream artifacts. Add status tests for no-active/active/blocked/completed enhancement guidance without creating a new stage status.
- **CODE:** extend traceability indexes, artifact contracts, `/pm-check`, and `/pm-status`. Derive lifecycle display from the frozen context plus existing stage approvals/staleness. Use actionable finding codes and remediation text.
- **VERIFICATION:** unit/integration consistency tests; traceability spine; status tests; deliberate-corruption fixtures for every new finding.
- **PASS-IF-GREEN:** each acceptance gap yields a deterministic finding and safe next action; valid projects remain quiet; legacy projects do not gain false errors.
- **UPDATE TASKS:** check Loop 9; start Loop 10.

## Loop 10 — Delta-only package and Jira handoff

- **AIM:** export only implementation work caused by the enhancement, with enough baseline, impact, regression, compatibility, and rollback context to execute safely.
- **TESTS (first):** add package/Jira tests for `new | modified | removed`, affected surfaces, impact evidence, baseline reference, non-touch/regression coverage, compatibility/migration, observability, rollout/rollback, and exclusion of unaffected baseline stories/requirements/tasks. Preserve the minimum ancestor closure and existing recorded Jira keys. Assert handoff refuses stale/unapproved/mismatched baselines.
- **CODE:** extend `/pm-handoff` and shared export mechanics using the computed baseline-vs-current delta. Keep Part-B `--increment` semantics separate; if tiers/increments are absent, E2 still exports correctly.
- **VERIFICATION:** handoff/share/Jira integration tests; inspect package manifest and representative ticket payloads; full suite.
- **PASS-IF-GREEN:** every exported item is justified by the delta or required ancestor closure; no unaffected baseline work becomes a ticket.
- **UPDATE TASKS:** check Loop 10; start Loop 11.

## Loop 11 — Refresh, migration, and backward compatibility

- **AIM:** handle repository drift and old PM-OS projects explicitly without corrupting baselines or prior enhancement provenance.
- **TESTS (first):** add tests for continue-on-pinned-baseline, explicit refresh/rebase, regenerated `00c`, normal downstream staleness cascade, dirty/ref mismatch refusal, migration from every supported schema shape, repeated migration, interrupted write recovery, and completed-context immutability.
- **CODE:** implement explicit refresh semantics and migration/backfill through existing project/meta locks and `migrate_meta()`. Never silently update the baseline because the checkout moved. Preserve hashes/history and older enhancement records.
- **VERIFICATION:** migration, locking, failure-recovery, history, approval/staleness, and project-versioning tests.
- **PASS-IF-GREEN:** refresh is explicit and auditable; migrated projects remain readable; repeated migration/refresh is idempotent; prior cycle provenance cannot change.
- **UPDATE TASKS:** check Loop 11; start Loop 12.

## Loop 12 — Two-path, two-cycle end-to-end dogfood and finalization

- **AIM:** prove the real operating pathway, not only its components, and reconcile all planning/testing documentation.
- **TESTS (first):** add isolated end-to-end smokes for:

  1. an external product's first PM-OS intake through read-only scan, boundary approval, scoped stages, check, and handoff;
  2. a PM-OS-native product completing enhancement A and then enhancement B in the same project, where B uses A's approved result as baseline;
  3. UI-only, API/data/service, and cross-cutting enhancements;
  4. monorepo, scan drift, dynamic-boundary uncertainty, and write-permissions-removed cases.
  Assert no child project, stable unaffected IDs/content, immutable A provenance, correct B delta, unchanged target repo, and no unaffected handoff work.
- **CODE:** integration wiring only. Do not add a new abstraction merely to make the smoke pass; fix the owning earlier loop and rerun its targeted tests when a defect is found.
- **VERIFICATION:** focused E2 suite; contract/integration/unit suites; full `python3 -m pytest -q`; isolated direct skill/script smokes for Claude/Codex packaging; `git diff --check`; review target-repo before/after hashes and Git state.
- **FINALIZE:** catalog every new test in `docs/guides/testing.md`; update the E2 acceptance boxes only where test/e2e evidence exists; reconcile the modes behavior table, entry-pathways plan, current-state review, backlog, skill catalog, and generated-format reference. Do not mark E2 shipped from code presence alone.
- **PASS-IF-GREEN:** all Definition-of-done items have evidence, the full suite is green with a non-decreasing count, target repositories are unchanged, and the PM has a reviewable diff.
- **UPDATE TASKS:** check Loop 12; report changed files, test evidence, and any remaining risks. Do not commit or push unless separately requested.

---

## 3. Execution evidence (2026-08-03)

- Branch base: refreshed `main` at `0296e0f`; implementation branch `feat/e2-affected-slice-enhancement`.
- Fresh-main baseline: 373 tests passed. Intermediate full gates: 378, 383, 391, and 400 passed as loops landed.
- Final focused E2/contract/handoff/lifecycle gate: 69 passed.
- Final repository gate after lifecycle recovery hardening: **403 passed in 199.73s**; collection count never decreased.
- Static gates: `git diff --check` and Python compilation of every changed/new helper passed.
- Read-only proof covers clean, dirty, write-permissions-removed, drift, and deterministic fingerprint fixtures; no test or implementation writes to the target checkout.
- The installed `~/.pm-os` and runtime skill directories were not modified. No commit, push, or publish was performed.

---

## 4. Failure handling and rollback

- If a loop fails, keep its task in progress, identify whether the defect belongs to the fixture, contract, or production code, and rerun from the first red test. Never advance with an expected-failure marker for required behavior.
- Preserve unrelated worktree changes. Before reverting anything, inspect the exact diff and use a narrow explicit patch limited to files changed in the active loop; do not use broad or destructive reset/checkout commands.
- If a new schema field is required, stop production work until a failing migration/backfill test exists. Preserve stage hashes and end at the authoritative schema version.
- If marketplace code violates the read-only/network/license/portability boundary, reject it and continue with the PM-OS-owned fallback. Do not weaken the invariant to keep the dependency.
- If dogfood reveals an earlier architectural defect, reopen the owning loop, add a reproducing test there, make the minimal fix, then rerun every later regression gate.
- The only supported route to an installed-runtime change remains commit → push → `pm_os_update.py`; test uncommitted work solely through the repository harness.

---

End of runbook.
