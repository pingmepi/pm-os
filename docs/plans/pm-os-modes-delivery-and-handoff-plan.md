# PM-OS Modes, Delivery Model & Engineering Handoff Plan

**Status:** 🟡 **Part A's full E2 enhancement pathway shipped in v1.5.0 (PR #68); Part B partially built; Part C partly shipped (Jira; Linear/Figma unbuilt).** E2 adds same-project baseline cycles, a deterministic read-only inventory/affected-slice/impact-cone scan, decision boundary, multi-surface stage overlays 01–09, non-UI validation behavior, delta/consistency/status gates, delta-only package/Jira export, explicit refresh, completion, and two-cycle provenance. The pre-existing enhancement scaffold remains the first-intake route. **Part B — the delivery model (scope tiers + delivery increments) — is designed here (2026-07-27); B0 plus prerequisite priority/TRD contract work are shipped, while tiers and increments remain unbuilt. §8.7 (2026-10-21) adds the sprint path from the APEX feedback on PRISM: generated sprint PRDs, per-epic views, and the interim route. It awaits PM approval.** Part C (external engineering handoff) is partly shipped: `/pm-handoff jira` — both the Atlassian-MCP create route and the `--offline` CSV export — landed v1.2.0 (screen mapping v1.3.0); `/pm-handoff linear`, Figma pull/push, and design-token→React codegen remain unbuilt. Delivery-model and unbuilt-handoff work is tracked as Phase 4 in `docs/roadmap/current-state-review.md` §7 and as backlog #28.
>
> **Naming history — `/pm-share` ↔ `/pm-handoff` (canonical record; this file owns it).**
> Two moves, net result one skill: **(1) 2026-07-15** — a local handoff-package generator briefly
> shipped as its own `skills/pm-handoff/` (PR #30), colliding with the `/pm-handoff <target>` name Part B
> reserves; resolved by folding it into `/pm-share --package` (`scripts/pm_share.py`). **(2) 2026-07-28** —
> `/pm-share` (raw **and** `--package`) was then folded **into** `/pm-handoff`, now the single callable
> export skill for all shapes (raw text, the per-audience package split into `handoff/{dev,design,qa,business}/`,
> and Jira tickets). `scripts/pm_share.py` remains the mechanical engine for the raw/package modes; only the
> skill entrypoint changed. **`pm-share` is not reserved going forward — do not resurrect the name without
> re-reading this note.** (Other docs mention this fold-in tersely; the full history lives here.)

> **Reconciliation note (2026-06-17):** Phase 2 shipped a general **stage-00 understanding framework** — a gated context wiki (`00-context-wiki.md`) + understanding doc (`00-context-understanding.md`) synthesized from PM-provided sources, plus the business statement as gated stage `00`. The codebase understanding described below should be implemented as **one more evidence source feeding that same framework** (the code becomes another source the wiki absorbs and the understanding doc summarizes), not as a separate bespoke `00-codebase-understanding.md` pipeline. Reuse `lib/project.py`'s stage-00 group, `migrate_meta`, and `pm_context_import.py` rather than duplicating them.
**Author:** Karan (with Claude Code)
**Date:** 2026-06-10
**Scope:** Extend PM-OS from new-product-development-only to also support existing-product enhancements from a single install (Part A); define how a product's scope is tiered from MVP to full product and how approved work is sliced into deliverable increments (Part B); and lay out the external engineering-handoff capability that exports those increments to Figma / Jira / Linear via MCP (Part C).

> One install, two cases. A PM installs PM-OS once and runs either a greenfield product definition or an enhancement to an already-built product — selected per project, not per install. Engineering handoff (design + ticketing) is a later, additive phase layered on top of approved artifacts.

---

## 1. The core idea: mode as a propagating flag

PM-OS already has the exact pattern this needs: `genai_flag`. It is a project-level value set at `/pm-new`, written into `.meta.yaml` and every artifact's frontmatter, and each stage's single `SKILL.md` branches its output on it ("When `genai_flag=true`: add sections…") — **with no skill forking** (non-negotiable, spec §2).

Existing-product enhancement is the same shape: a second project-level dimension that propagates downstream and conditions each stage.

```yaml
# .meta.yaml
project_type: new_product | enhancement   # default: new_product
codebase_path: <abs path>                  # enhancement mode only
codebase_ref: <git SHA at understanding-doc generation>  # enhancement mode only
```

This preserves every non-negotiable:

- **One `SKILL.md` per stage** — mode is a conditional block in the existing body, not a new file.
- **Markdown is the source of truth** — the new artifact is markdown.
- **Distributable by config, not architecture** — mode is config, exactly like single-user mode and `genai_flag`.
- **Human-in-the-loop at every gate** — the new understanding stage is itself an approval gate.

The deterministic core (hashing, staleness cascade, telemetry, approval gates) is **mode-agnostic** and needs no changes. This is a purely additive flag following an established precedent, which keeps risk low.

---

## 2. Why enhancement mode reads the codebase

For an already-built product, a pinned codebase is the strongest source for **implemented structure and behavior**, but it is not the whole production truth: deployed release/configuration, feature flags, external services, data state, business intent, and compatibility promises may live elsewhere. Enhancement mode combines read-only code evidence, optional docs or a prior PM-OS project, and a narrow decision interview. It never treats scanned code as the enhancement scope by itself.

1. PM-OS **reads the existing codebase** (read-only), builds a cheap whole-repo inventory, then synthesizes an affected-slice + impact-cone **Codebase Understanding** document.
2. That document is surfaced to the PM as the **first approval gate** — they review, correct any misreading, and approve.
3. Only once the understanding and decision boundary are approved do downstream stages run, each **aligning the PM's request as a delta against that approved reality.**

This gives the PM a natural, early correction point: if PM-OS misunderstands the affected slice, it is caught at gate 0 rather than three stages later. PM-OS only ever **reads** the target codebase — it never writes files there, changes its checkout/index/worktree/ref, or runs a mutating build/install/format step. Generated outputs live in the PM-OS project.

---

## 3. Pipeline shape per mode

| Stage | File | new_product | enhancement |
|---|---|---|---|
| 00 input | `00-business-statement.md` | PM-authored ask | PM-authored ask |
| **00 understanding** | `00-codebase-understanding.md` | — (absent) | **generated + approved** |
| 01 Brief | `01-brief.md` | ✓ | ✓ (reads understanding) |
| 02 Scope | `02-scope.md` | ✓ | ✓ |
| 03 PRD | `03-prd.md` | ✓ | ✓ |
| 04 Design Spec | `04-design-spec.md` | ✓ | ✓ |
| 05 Prototype Brief | `05-prototype-brief.md` | ✓ | ✓ |
| 06 QA Plan | `06-qa-plan.md` | ✓ | ✓ |
| 07 Metrics Plan | `07-metrics-plan.md` | ✓ | ✓ |
| 08 TRD | `08-trd.md` | ✓ (optional) | ✓ (optional) |
| 09 Roadmap | `09-roadmap.md` | ✓ (optional) | ✓ (optional; follow-on enhancement horizons only) |

Numbering of stages 01–09 is unchanged, so existing projects and skills are unaffected. The business statement (the *ask*) and the codebase understanding (observed implementation evidence) are stage-00 grounding; the approved enhancement boundary supplies the binding delta. All stages remain present in both modes — **mode and affected surfaces change framing/content, not the linear approval architecture**.

---

## 4. New stage: `pm-stage-00-understand` (enhancement-only)

A new skill that runs only when `project_type=enhancement`.

**Pre-flight:** require `project_type=enhancement` and a resolvable `codebase_path` in `.meta.yaml`; otherwise stop with a clear message.

**How it reads the codebase:** read-only, slice-first exploration. First create a cheap repository inventory; then trace the approved ask through its change surface and impact cone (dependencies/dependents, shared components, interfaces/events, data/schema, permissions, configuration/flags, tests, observability, deployment, consumers). Marketplace skills may strengthen this scan only through reviewed, commit-pinned PM-OS adapters; the portable PM-OS skill remains authoritative. Large repositories stay tractable because the agent reads evidence-bearing excerpts and widens only when dependencies or uncertainty require it.

**Output — `00-codebase-understanding.md`** — E2 target sections:

- Baseline identity and scan coverage/exclusions/confidence
- Affected product slice: current behavior and evidence
- Affected surfaces (`ui | api | data | service | event | integration | operations`)
- Impact cone: dependencies, dependents, shared primitives, integrations, data and deployment
- Existing invariants and explicit non-touch candidates
- Relevant design/interface language and reusable primitives
- Relevant tests, observability, rollout mechanisms, constraints and tech debt
- Unknown/dynamic/unavailable boundaries that require interview or a widened scan

Frontmatter records repository identity, requested ref, resolved/scan SHA, optional monorepo subpath, and dirty/non-reproducible status. The scan verifies start SHA = end SHA and never silently replaces an approved baseline.

**Approval gate:** normal `draft → approve` flow. The PM reviews, edits to correct any misread, and approves. The stage-01 gate in enhancement mode requires stage 00 to be `approved`.

---

## 5. Per-stage conditional blocks (enhancement mode)

Added to each existing `SKILL.md` as a "When `project_type=enhancement`:" block, mirroring the existing `genai_flag` precedent. Grounded in the approved understanding doc.

| Stage | Required enhancement behavior |
|---|---|
| **00c Codebase understanding** | Record the pinned read-only baseline, scan coverage/exclusions/confidence, current affected behavior, multi-surface impact cone, relevant existing primitives/tests/constraints, and unknown boundaries. Do not reconstruct the whole product. |
| **00u Understanding** | Add a binding **Enhancement Boundary**: source-product/codebase baseline, current→target behavior, affected and explicit non-touch surfaces, regression invariants, compatibility/migration, success baseline/target, rollout/rollback constraints, blocking unknowns and accepted risks. |
| **01 Brief** | Frame the current-product gap, affected users, why this enhancement now, and the delta success hypothesis. Existing-product description is context, not scope. |
| **02 Scope** | Define change boundary, affected-surface matrix, impact/blast radius, explicit non-touch boundary, dependencies, and smallest coherent enhancement slice. |
| **03 PRD** | Class every story/requirement `new | modified | removed`; state current→target behavior; trace to affected surfaces; include backward compatibility, migration, mixed-version and rollout requirements. |
| **04 Design Spec** | Design only changed/new surfaces while preserving relevant existing context. UI: existing/modified/new screens and component reuse. API/data/service/event/integration/operations: interface contracts, schemas/migrations, service/event flows, integration/operational design. Never invent UI tokens or screens for a non-UI delta. |
| **05 Prototype/validation brief** | Validate the delta using artifacts appropriate to each affected surface: UI prototype; API examples/mock contract; data migration/sample validation; service/event harness or sequence; integration sandbox/webhook cases; operational drill/runbook. Generate HTML only when UI is affected. |
| **06 QA Plan** | Add delta acceptance tests plus an impact-based regression class tied to approved invariants; cover compatibility, migration/backfill, permissions, mixed versions, feature flags, rollback, and all affected surfaces. |
| **07 Metrics Plan** | Use **baseline-status → target** framing: cite the available baseline or say it is unavailable and define how to establish it. Add guardrails for existing outcomes and surface-specific operational/data/API/UI risks; define rollout/rollback triggers. |
| **08 TRD** | Produce a change-set against existing architecture: affected modules/interfaces/data/events/infra, integration and compatibility plan, migration/backfill, flags, observability, deployment/rollback, and delta-only tasks traced to requirements/tests. |
| **09 Roadmap** | Scope rollout and follow-on enhancement horizons only; do not reopen or roadmap the whole existing product. |
| **Handoff/check** | Export only delta work with change type, affected-surface/impact evidence, regression “must not break,” compatibility/migration/rollback notes, and baseline backlink; `/pm-check` warns on missing links or baseline mismatch. |

---

## 6. Codebase baseline and drift

The approved enhancement is pinned to the exact baseline captured in `00c`; later movement of a supplied checkout must not silently rewrite that baseline. `/pm-status` reports pinned vs current, while `/pm-check` compares repository identity/ref fields across metadata, `00c`, and the checkout. The PM chooses either (a) continue deliberately against the pinned baseline or (b) explicitly refresh/rebase. Refresh regenerates `00c`; its normal approval causes the existing downstream staleness cascade. Preparation alone must never overwrite `codebase_ref` and make an old `00c` appear current.

---

## 7. Plumbing changes (Part A)

Small and localized:

- `scripts/pm_new.py` — add `--mode {new_product|enhancement}` (+ interactive prompt) and `--codebase <path>`; write `project_type` and `codebase_path` to `.meta.yaml`.
- `templates/meta.yaml.j2` + spec §5.1 / §5.2 schemas — add `project_type` (and, in enhancement mode, `codebase_path` / `codebase_ref`).
- `scripts/pm_status.py` + spec §7.7 — show mode next to the GenAI flag and the codebase-drift indicator.
- New skill `skills/pm-stage-00-understand/SKILL.md` (+ `agents/openai.yaml`) for cross-runtime parity.
- Stage bodies read `00-codebase-understanding.md` when `project_type=enhancement` (handled in the body; `reads:` frontmatter is non-standard and ignored by runtimes anyway).
- Telemetry — add `project_type` to `project_created` and stage payloads so the feedback repo can segment new-product vs enhancement.
- Spec §2 / §8 / §13 updated to document the new dimension and stage.

**Risk:** the shipped flag/gate plumbing is low-risk, but the full pathway is not: slice completeness, same-project before/after provenance, baseline identity, stable-ID carry-forward, multi-surface contracts, regression scope, and handoff correctness are cross-cutting. E2 therefore ships in the dependency order and acceptance matrix in `pm-os-entry-pathways-plan.md`, while keeping the existing status/hash/gate state machine authoritative.

---

## 8. Part B — Delivery model: scope tiers & delivery increments

> **Provenance / abandoned attempt (2026-08-02).** A first implementation of the tiers / increments /
> `/pm-promote` work below was attempted on branch `feat/whole-product-foundation` and **abandoned as
> buggy per PM decision** — the *code* was discarded, but this *design* stands and may be picked up later.
> Before any rebuild, treat the §10 open decisions as **needing re-review**: some have likely been
> superseded by the 2026-08-01 entry-pathways / interview direction (`../plans/pm-os-entry-pathways-plan.md`)
> and the consistency-spine work. Do not resume from the old branch; rebuild from this design after that review.

**Designed 2026-07-27 (Karan + Claude); partially built.** B0 shipped 2026-07-28, resolving the synthetic-epic vs. per-story export mismatch into a Jira-native hierarchy with declared Product Epics (`EPIC-###`). Backlog #19 (priority) and #20 (TRD section contract) are now shipped prerequisites. The remaining Part B work resolves two gaps the current linear pipeline still has by design: PM-OS defines exactly one tier of work ("the MVP", as prose) and hands it off exactly once. It adds a *scope-tier* dimension upstream and a *delivery-increment* dimension downstream, both **additive to the traceability spine — no change to the gate, hash, status, or staleness machinery** (the product-shape golden rule: grow the spine, not the state machine).

### 8.1 The two gaps, verified

- **"MVP" is prose, and "the whole product" cannot produce stories.** Stage 02 writes one `## MVP Boundary` paragraph (`skills/pm-stage-02-scope/SKILL.md:155`); every downstream stage treats it as binding via LLM judgment, with no structured field, ID, or flag. Stage 09 has `V1`/`V2`/`Expansion` horizons but is explicitly forbidden from generating requirements, so roadmap horizons carry **no `US-###`/`FR-###`**. There is no path from "V1 horizon" to "user story" — the pipeline can only ever elaborate the single tier stage 02 named MVP.
- **Handoff is single-shot.** No delivery-increment / cycle object exists anywhere (`grep sprint` across `skills/`/`lib/`/`scripts/` returns nothing), so approved work cannot be sliced across multiple development cycles. The earlier export-mapping mismatch is now fixed: `pm_share.py --package` and `pm_handoff.py plan/export` both use Jira's native hierarchy (`EPIC-###` Epic → `US-###` Story / `FR-###` Task → `TSK-###` Subtask/Task as parentability allows).

### 8.2 Defining MVP vs. the whole product

The clarity gap is real and must be closed *before* tiers mean anything. Definitions this design commits to:

- **The whole product** = the full set of user stories/requirements the PM believes the product needs to be complete — enumerated across all tiers, at mixed fidelity (see 8.4).
- **A scope tier** = a named band of that set, ordered by delivery intent: `mvp` (smallest release that validates the core hypothesis — today's stage-02 boundary, now a *tag on requirements* rather than a prose paragraph), then `v1`, `v2`, `later`. The tier vocabulary reuses stage 09's existing horizon language so the roadmap and the requirement set finally share one axis.
- **The MVP boundary** stops being a paragraph and becomes *the set of requirements tagged `tier: mvp`*. Stage 02 still authors the rationale prose, but the boundary is now machine-readable and auditable.

### 8.3 Scope tier as a spine attribute

- Each `US-###`/`FR-###` carries an optional `Tier:` field (`mvp | v1 | v2 | later`), default `mvp` so existing projects are unchanged.
- Stage 02 declares the tiers and their intent (what "complete" means, what each band is for); stage 03 may generate stories across *all* declared tiers, each tagged.
- **Stages 04–07 filter to `tier: mvp` by default.** Design, prototype, QA, and metrics stay MVP-scoped exactly as today unless the PM explicitly widens them — so nothing downstream gets heavier, and the MVP pipeline behaves identically to the current one.
- `.traceability.yaml` indexes `tier` alongside the existing links; `/pm-check` can then warn if a `v1` story depends on a `later` story (tier inversion), reusing the read-only advisory pattern.

### 8.4 Tiered fidelity + the promote step (PM decision)

Non-MVP stories are **enumerated at lower fidelity** — title, value, `Tier`, and trace — not fully specified. Full per-story mini-specs (acceptance criteria, edge cases, happy path — the stage-03 v2 contract) would force specifying design that doesn't exist yet and balloon the PRD. So:

- **MVP tier:** full stage-03 v2 fidelity (unchanged).
- **v1/v2/later tiers:** lightweight stubs — the contract requires only title + value + tier + trace for these, and the v2 mini-spec checks apply *only* to `tier: mvp`.
- **`/pm-promote <US-###>`** (or a tier-change flag) elevates a stub to the next tier and triggers full-fidelity (re)generation of that story's mini-spec, at which point the v2 contract applies to it. Promotion is where the deferred rigor gets paid — deliberately not free, mirroring the graduation principle in `../roadmap/product-shape-and-flexibility-brainstorm.md` §5.

### 8.5 Delivery increments — the ungated layer (PM decision: option C)

Multiple development cycles need a *delivery increment* object. It is deliberately **not** a gated stage and **not** folded into stage 08/09, for four verified reasons: (1) a TRD in `edited` state contributes zero tasks to the export — `lib/traceability.py:142` and `scripts/pm_handoff.py:202` gate the index on status `approved` — so replanning inside 08 would silently empty the handoff; (2) stage 08 is an *optional dependency* of 09 (`lib/project.py:82`), so re-approving the TRD always cascades the roadmap to `stale` — parking the most fluid object downstream of the most stable one; (3) an increment change (a dev slips a task a cycle) carries no product-correctness signal, so firing the definition gate on it trains gate-fatigue; (4) a delivery plan is a *ledger* (what shipped, which keys came back), and hash-drift's "did this change, is it still valid?" is the wrong question for a ledger.

So the increment layer is:

- An **ungated, append-friendly** record — `delivery.yaml` (or `INC-###` entries) at project root, beside `.meta.yaml`, not a numbered stage artifact.
- Each increment: an id (`INC-###`), a goal, entry/exit conditions, and **membership by `TSK-###` when an approved TRD exists** (the TRD Work Breakdown is the right sequencing unit — tasks already carry `Implements:` traces). **Fallback for the TRD-less path:** stage 08 is optional, and the supported handoff already degrades to PRD-only stories/requirements when no TRD is present, so a project without a TRD has no `TSK-###` to group. In that case increment membership falls back to **`US-###`/`FR-###`** — the same units the PRD-only handoff exports — so an increment can always be formed. Prefer `TSK` granularity when tasks exist; fall back to `US`/`FR` otherwise. (An earlier draft said "group tasks, not stories"; that only holds when a TRD exists.)
- **Validated *against* 08/09, never gated *by* them:** `/pm-check` warns if an increment contains a `TSK` whose dependency sits in a later increment, or pulls a story from a horizon stage 09 placed later. Advisory, read-only — the existing `/pm-check` pattern.
- Sequencing (task→task dependency) stays in the **gated** stage-08 Work Breakdown; strategic horizons stay in **gated** stage 09; only *assignment to a cycle* and the *handoff ledger* live in the ungated layer. This is the "sort by rate of change, not by gated/ungated" split: stable facts stay gated and get *updated* (via `--reapprove`), the weekly-churn object stays out.

**Out of scope by decision:** story points, effort estimation, sprint dates, capacity, velocity — these belong to the tracker and to development, not PM-OS (backlog #22). PM-OS owns the increment *boundary* as a product decision; it does not estimate or schedule it.

### 8.6 Export mapping prerequisite — shipped

B0 is complete: Stage 03 declares Product Epics and `pm-share --package` / `pm_handoff.py` now agree on Jira's default hierarchy. `EPIC-###` entries export as Epic work items, `US-###` entries export as Story work items under their declared epic, `FR/REQ-###` entries export as Task work items under their declared epic, and approved `TSK-###` work-breakdown entries export as Subtasks when they implement exactly one exported item. Same-epic multi-ref tasks become Tasks under that epic; cross-epic or unresolved tasks stay unparented. `tests/integration/test_share_package.py` compares the package epic refs against the Jira handoff plan.

With that mapping in place, `/pm-handoff jira --increment INC-02` scopes the export to that increment — but **an increment export is the member set plus its required ancestor closure, not the members alone.** `scripts/pm_handoff.py` parents Subtasks to their owning requirement/story and standard Jira work items to their declared `EPIC-###`; the offline exporter resolves `Parent Id` only against issues present in the *same* CSV. So a subtask-only export orphans every subtask unless its Story/Task parent (and the epic ancestor for standard work items) is also present or represented by a previously-recorded Jira key. The export must therefore emit, for each member, the required ancestors it hangs from. And because those ancestors may have been created in an *earlier* increment, the export must **substitute the previously-recorded Jira keys** (from `.traceability.yaml`'s per-increment `tickets:` slots) for any parent already created, rather than re-creating it. `.traceability.yaml` records returned ticket keys per increment so cycle 2 never recreates cycle 1's tickets. This is a prerequisite-aware refinement of backlog #28. *(Revised in §8.7.5: the existing flat `tickets:` slot is enough, so no per-increment slot and no index shape change.)*

### 8.7 The sprint path (revision 2026-10-21, from APEX feedback on PRISM)

**Status:** designed, unbuilt, awaiting PM approval. It refines §8.5 and §8.6 where noted, and covers backlog #28 (increments), #66 (per-epic views), #63 (the interim route), and how #70–#75 and #68 plug in. The open decisions it raises are §10 items 8–14.

#### 8.7.1 What PRISM actually did

Read-only inspection of `~/pm-projects/prism-ai` on 2026-10-21:

- **The product artifacts are large.** The approved product PRD (`03-prd.md`, approved 2026-09-29) has a 451 KB body: 12 epics, 47 stories and 97 requirements. The QA plan is 270 KB with 177 test-case blocks.
- **Each sprint got its own hand-written PRD.** Sprint 1 (`sprint-1-r2/`, 7 Oct) and sprint 2 (`sprint-2/`, 21 Oct) each have one. `PRD-sprint-2.md` is 36 KB, v0.7, and has its own ids: stories `S2-US-01`…`16`, epics `S2-EP-01`…`06`, and requirements `FR-10`…`FR-17` with sub-items like `FR-12.3`, numbered on from sprint 1.
- **Neither sprint cites a single product PRD id.** There is no `EPIC-0xx`, `US-0xx` or `FR-0xx` anywhere in either folder.
- **Sprint 2's scope is not in the approved product artifacts.** "Page health", "crawler", "technical item" and "FAQPage" each appear 0 times in 03, 06 and 08. Sprint 2 brought in product scope that never went through stage 03.
- **Sprint 2 was re-cut six times in two days, r1 to r6, with no change note.** Each re-cut was a new dated zip. The crawler checks moved to sprint 3, the pharma checks were parked until the brand team supplies inputs, and the report output was dropped.
- **The sprint PRD has sections the product PRD lacks:**
  - plan and sizing (story points);
  - what we need from the business;
  - defaults and open items;
  - the expected result on the sample file;
  - done when.

**So the sprint path has two problems to solve, not one:**
1. Cutting a sprint-sized slice from the approved PRD, which is what §8.5 designed.
2. Getting scope that is found or decided during a sprint back into the product PRD, so there is something to cut it from.

Without (2), PMs will bypass (1) again, because the sprint's content isn't in the PRD.

#### 8.7.2 The design in one paragraph

The approved product artifacts (03, 06 and 08) remain the only source of truth. A sprint is an increment `INC-###` in the ungated `delivery.yaml`, which lists the approved ids it delivers. `/pm-handoff --package --increment INC-###` builds a sprint package whose sprint PRD is **generated**: it is cut verbatim, by id, from the approved PRD and is never written by hand. Scope that a sprint needs but the PRD lacks goes into stage 03 first, as new ids appended through normal approval. The same carving builds per-epic views of the PRD and QA plan (#66), so a stage that has to read a large PRD reads one epic at a time.

#### 8.7.3 `delivery.yaml`

```yaml
schema_version: 1
increments:
  - id: INC-002
    name: Sprint 2 - page health checks and technical items
    status: active                 # planned | active | released | closed
    builds_on: INC-001
    goal: >-
      PRISM checks the page itself and turns technical findings into approved work items.
    members:
      epics: [EPIC-013]            # shorthand: every story/requirement of the epic
      stories: [US-052, US-053]
      requirements: [FR-101]
      tasks: []                    # optional override; normally derived (below)
    deferred:
      - {id: FR-104, to: INC-003, reason: AI crawler checks need the crawler list, decision: OD-31}
      - {id: FR-109, to: parked, reason: brand team inputs not supplied, decision: OD-32}
    done_when:
      - Every sprint 1 done-when criterion passes on both test files.
    risks:
      - Spill-over from sprint 1 beyond 12 points.
    cut_from: {"03": 7, "06": 4, "08": 3}   # stage versions (#71) last checked; written by check
```

- **Ungated, like `readiness.yaml` (#74).** Editing it never changes stage state, starts no stale cascade and logs no approval event. The agent edits the YAML. `scripts/pm_delivery.py` gives `init` and `check [--json]`. There is no new skill: `/pm-check`, `/pm-status` and `/pm-handoff --increment` read the file.
- **Membership is by story and requirement (`US`/`FR`/`NFR`); tasks are derived.** This revises §8.5, which preferred `TSK`. PRISM cut both sprints by story, and APEX reads stories. A `TSK` belongs to the increment of every item it implements. A task whose items sit in two increments gets a warning. An explicit `tasks:` list overrides derivation for a PM who wants a task-level cut. *(Decision 9.)*
- **Whole ids only.** A requirement delivered in parts, like PRISM's `FR-12.3` (17 of the 38 checks), is split in stage 03 into separate ids. A member may carry a prose `note:`, which is shown in the sprint PRD but not checked.
- **`epics:` is a live shorthand.** It expands at check and build time. If an epic gains ids after the increment was released, `INC_EPIC_GREW` (a warning) says so.
- **`deferred:` keeps the reason.** It covers both "moved to sprint 3" and "parked" (`to: parked`), each with a reason and, where one exists, an `OD-##` from the readiness record. Spill-over is a member of INC-001 that INC-001 defers `to: INC-002`, and that is also a member of INC-002.
- **`cut_from` pins the stage versions.** It records the versions (#71) the membership was last checked against. `pm_delivery.py check` writes it when the check is clean, and that is its only write.
- **Not stored:** points, dates, capacity and velocity. #22 still holds: PRISM's "Plan and sizing" stays in the tracker. *(Decision 14 re-confirms this.)*

#### 8.7.4 Checks

These are read-only. `/pm-check` shows them in a Delivery section beside Readiness, and the release check adds them for an increment package.

| Code | Severity | Fires when |
|---|---|---|
| `INC_MEMBER_UNDEFINED` | error | A member id isn't declared in the approved 03 (or 08 for tasks). |
| `INC_MEMBER_DUPLICATE` | error | An id is a member of two open increments, and the earlier one doesn't defer it to the later one. |
| `INC_SOURCE_BEHIND` | warning | 03, 06 or 08 has been re-approved since `cut_from`, and a member's block changed. This uses the #73 stable-id diff, so the warning names the ids. |
| `INC_DEPENDENCY_LATER` | warning | A member depends on an id in a later increment, through a `TSK` dependency or a story's `Depends on`. |
| `INC_TASK_SPLIT` | warning | A derived task implements items in two increments. |
| `INC_EPIC_GREW` | warning | An `epics:` shorthand now covers ids added after the increment's last release. |
| `INC_MEMBER_UNTESTED` | warning, error at release | A member has no covering `TC-###`. This is the #72 `REQUIREMENT_UNTESTED` rule scoped to the increment, and it is an error only once 06 is approved. |
| `INC_UNASSIGNED` | info | The number of approved ids in no increment. It shows only once an increment exists. |
| `INC_HORIZON_LATER` | warning | A member sits in a later stage-09 horizon. Deferred until B1 tiers exist. |

The readiness record links to increments through `due`. Today `due` names a milestone; it may also name an `INC-###`, meaning "due at that increment's kick-off". When `delivery.yaml` exists, the active increment counts as the current milestone. Existing `readiness.yaml` files keep working unchanged. *(Decision 12.)*

#### 8.7.5 The sprint package: `/pm-handoff --package --increment INC-###`

- **Location:** `handoff/INC-002/{dev,design,qa,business}/`. The whole-product `handoff/{dev,…}` folders are untouched, and each increment folder is a sibling. *(Decision 11.)*
- **Contents:** today's package restricted to the members plus their ancestor closure. That is the owning epics, the journeys their stories serve, the screens serving them, the test cases covering them and the tasks implementing them. On top of that come:
  - **`PRD.md`, the generated sprint PRD.**
    - From `delivery.yaml`: the goal, what it builds on, done when, risks, and the deferred and parked lists with their reasons.
    - From 03: the core sections that apply, verbatim — the overview and any NFRs a member cites.
    - Each member epic, with its member stories and requirements verbatim from approved 03, plus a "Not in this increment" line listing the epic's other ids.
    - Frontmatter: the #71 approval stamps of 03, and `increment: INC-002`.
  - **A "Referenced, not in this increment" appendix.** For each id a member cites that sits outside the increment, it gives the title and a one-line summary. That closes APEX AL-21 (ids defined only outside the package) and turns the #72 `ID_NOT_IN_PACKAGE` warning into a deliberate reference.
  - **`readiness.yaml` items due for this increment (#74).**
  - **`manifest.json` (#75) and `CHANGES.md` (#73).**
- **Release check:** it runs on the staged folders exactly as now (#72), plus §8.7.4.
- **`--release-note` and change notes:** `--release-note` writes `.releases/REL-###.yaml` with `increment: INC-002`. `CHANGES.md` compares against the previous release *of the same increment*, so PRISM's r5 to r6 re-cut becomes a note. The first release of an increment compares against the last release of its `builds_on` increment for the ids both carry. Sprint 2's first note therefore says which sprint-1 stories' approved text changed since sprint 1 shipped, which is APEX's "re-plan only those".
- **Jira:** `/pm-handoff jira --increment INC-002` exports the members plus their ancestor closure. **This revises §8.6.** An ancestor whose `tickets:` slot already holds a key is referenced, not re-created. That flat slot is preserved across index rebuilds today, so it already means "created". No per-increment slot is needed, and `.traceability.yaml` keeps its shape. `record --increment` logs the increment in the telemetry payload.

#### 8.7.6 Per-epic views (#66)

- **One carving function, two uses.** `carve(body, ids)` returns the verbatim blocks for an id set plus their required ancestors, built on `split_stable_id_blocks` and `build_prd_delivery_map`. It is pure mechanics. Per-epic views and the sprint PRD both use it.
- **Written from the approved body only.** `post-approve.py` writes them on approval of 03, 06 or 08, next to the `.traceability.yaml` rebuild:
  - `by-epic/EPIC-###/prd.md`, `qa.md` and `trd.md`;
  - `by-epic/core.md`: the PRD sections outside any epic;
  - a short `by-epic/README.md` saying the files are derived and overwritten.

  The folder can't be called `views/`, because `00-context/views/` already belongs to the context pack. *(Decision 10.)*
- **Views are never part of stage state.** Each view's frontmatter carries `derived: true`, `epic`, and the source stage's `version` and `content_hash`. Views are never approved and never hashed into `.meta.yaml`. Editing one changes nothing, and the next approval overwrites it.
- **Measured on PRISM** (read-only, with the working-copy delivery map):

  | View | Size |
  |---|---|
  | Whole PRD / whole QA plan | 451 KB / 270 KB |
  | PRD view, per epic | 11–46 KB |
  | QA view, per epic | 15–64 KB |
  | PRD content outside any epic | 168 KB |

  The 168 KB outside any epic is:
  - journeys, 27 KB;
  - the epic list, 15 KB;
  - requirement disposition, 13 KB;
  - the GenAI architecture sections, about 36 KB (#77);
  - open decisions, 10 KB;
  - NFRs, 9 KB;
  - smaller sections.

  Moving journeys and epic declarations into their epic views, and the GenAI architecture into 08 (#77), leaves `core.md` at about 90 KB. That is still more than one comfortable read, so skills read `core.md` by heading, not whole.
- **The skills decide when to use views; this is judgment, so it goes in `SKILL.md`.** Stages 04, 06 and 08, and `/pm-feedback`, read `by-epic/` instead of the whole PRD once 03's body is past a size limit. The limit is a `lib` constant, not a `config.yaml` key, so there's no config schema change. They work one epic at a time, write a large output in parts, and finish it with `pm_finish_stage.py <NN>` (#63).
- **Known gap:** a test case that covers ids in two epics appears in both QA views, and the view header says so. Test cases in the QA plan's NFR table aren't indexed yet (#65), so they're missing from the views until #65 is fixed.

#### 8.7.7 The interim route for a hand-written sprint PRD, until §8.7.3–8.7.5 ship

**Why `pm_finish_stage.py` doesn't fit.** It finalises a stage listed in `STAGE_NAMES`: it stamps `generated_hash`, writes `.history/`, and sets stage `NN` to `draft`. A sprint PRD isn't a stage. Finishing it as `03` would replace the product PRD, and its approval would mark 04–09 stale. There is deliberately no slot for a second PRD.

**Why not a separate PM-OS project per sprint.** It forks the product's source of truth, and the ids drift apart. That is exactly PRISM's state today.

**So, until B3 ships:**

1. Keep the sprint folder hand-built, but run `/pm-check --release sprint-N/dev-handoff` before every send (chunk 1, built). It catches broken links, undefined ids, missing priorities and epics, placeholders and stale `source:` versions.
2. Track what the sprint is owed in the project's `readiness.yaml` (chunk 2, #74), with open decisions as `OD-##`. This retires `open-decisions.csv`.
3. Record each piece of scope a sprint adds that the product PRD lacks as an `OD-##` "fold into the PRD" item, so `/pm-status` shows the divergence instead of hiding it.
4. Before cutting the next sprint, fold the earlier sprints' scope into the product PRD. This is a stage 03 revision that appends new epics, stories and requirements with new ids, written in parts if it's large. That *is* a pipeline stage, so `pm_finish_stage.py 03` fits it. Approval bumps the version (#71) and runs the normal cascade.

**What the interim can't give a hand-built folder:** approval stamps (#71), a change note or manifest (#73, #75). All three are built from PM-OS stages.

#### 8.7.8 PRISM sprint 2 under this design

The ids below are illustrations.

1. **Fold the scope in.** A stage 03 revision appends EPIC-013 *Page health checks* and EPIC-014 *Technical work items*, with their stories (US-048 onward) and requirements (FR-094 onward). One requirement per check family replaces `FR-12.3`. The edit is append-only, written in parts and finished with `pm_finish_stage.py 03`. The #52 id diff runs on approval and confirms no existing id was renumbered. Approval makes 03 v7, and 04–09 go stale.
2. **Bring 06 and 08 up to date one epic at a time.** Stage 06 reads `by-epic/EPIC-013/prd.md` (about 30 KB) and `core.md` by heading, not 451 KB, and adds test cases for the new epics. Stage 08 does the same for tasks. Stages with nothing to add are rebound with `--reapprove`.
3. **Record the increment.** `delivery.yaml` gets INC-002 for sprint 2:
   - members EPIC-013, EPIC-014 and the sprint-1 regression stories;
   - deferred: the crawler checks to INC-003 with OD-31, and the pharma checks as parked with OD-32;
   - done when, copied from the sprint PRD.

   INC-001 is recorded as released (§8.7.10).
4. **Record what's owed.** `readiness.yaml` lists:
   - EVAL-001, the golden sentence list carried from sprint 1, due at INC-002, owner named;
   - TI-003 and TI-004, the brand inputs the pharma checks need;
   - the 45 open decisions from `open-decisions.csv` as `OD-##`.
5. **Build and release.** `/pm-handoff --package --increment INC-002 --release-note "Crawler checks moved to sprint 3"` builds `handoff/INC-002/dev/`. It contains a generated `PRD.md`, only the member stories with priorities and epics, their test cases and tasks, the owed items, `manifest.json` and `CHANGES.md`. The release check blocks anything like the 7 broken links, the undefined `R-01`–`R-09` and the 16 missing priorities found in the hand-built sprint-2 folder.
6. **Re-cut.** Each re-cut (r1 to r6) becomes `REL-0xx`. Its `CHANGES.md` lists the ids that moved out (the crawler-check FRs, to INC-003) and the reason, instead of a new dated zip.
7. **Export to Jira.** `/pm-handoff jira --increment INC-002` creates EPIC-013 and EPIC-014 once, and reuses earlier epics' keys for any ancestor already created in sprint 1.

#### 8.7.9 How chunks 1 and 2 plug in

| Built in | What the sprint path uses it for |
|---|---|
| #70 bold labeled fields | Members' priorities and epics parse cleanly into the sprint PRD, stories and the index. |
| #72 release check, `--allow-release-errors` | Runs unchanged on each `handoff/INC-###/<audience>` folder, plus §8.7.4. It is also the whole interim route for hand-built folders (§8.7.7). |
| #71 stage `version`, approval stamps, approved-only export | `cut_from` pins versions, `INC_SOURCE_BEHIND` compares them, and the generated `PRD.md` carries 03's stamps. |
| #74 `readiness.yaml` | Items take `due: INC-###`. The increment package carries the items due for it, and `OD-##` records deferrals and parked scope. |
| #73 `.releases/`, `CHANGES.md`; #75 `manifest.json` | A release record gains `increment:`. The change note compares within an increment, or against `builds_on` on a first release. Each increment folder has its own manifest. |
| #68 manifest-based clearing | Rebuilding an increment folder deletes only what its previous manifest lists. |

#### 8.7.10 Migration

- **No `.meta.yaml`, `config.yaml` or `.traceability.yaml` shape change, so no schema bump.** `delivery.yaml` is a new file with its own `schema_version: 1`, as `readiness.yaml` has. `by-epic/` is derived.
- **Projects without `delivery.yaml` behave exactly as today.** `--increment` on such a project exits with a message pointing to `pm_delivery.py init`.
- **Ownership:** `lib/project_git.py` `OWNED_FILES` gains `delivery.yaml`, and `OWNED_DIRS` gains `by-epic/`.
- **Existing projects pick up `by-epic/` on their next approval** of 03, 06 or 08, or on demand through a `pm_delivery.py views` rebuild.
- **PRISM: no retro-conversion of the sprint 1 and 2 folders,** because their ids don't map to product ids. Instead:
  - INC-001 and INC-002 are recorded as `status: released` with `external: sprint-N/`, so increment numbers match sprint numbers.
  - An `aliases:` map (for example `S2-US-03: US-061`) is written only for items still in flight, namely the crawler checks deferred to sprint 3 and the parked pharma checks. The release check then accepts the old ids in carried-over text.
  - *(Decision 13.)*

#### 8.7.11 Test plan

Every test has a docstring and is catalogued in `docs/guides/testing.md`.

- **Unit `test_delivery.py`:**
  - validation of the shape;
  - `epics:` expansion;
  - the deferred and duplicate rules, and spill-over;
  - task derivation and `INC_TASK_SPLIT`;
  - `cut_from` written only on a clean check;
  - `due: INC-###` accepted by readiness.
- **Unit `test_id_views.py`:**
  - carving is verbatim and includes ancestors;
  - per-epic split, with cross-epic test cases in both views;
  - views are built from the approved body only, never an `edited` one;
  - frontmatter stamps.
- **Unit `test_release_check.py`:** one case per `INC_*` code in §8.7.4.
- **Integration `test_delivery_ungated.py`:** editing `delivery.yaml` never touches stage state or telemetry, mirroring the readiness test.
- **Integration `test_increment_package.py`:**
  - two increments: each package carries only its members and ancestors;
  - the generated `PRD.md`, the "Referenced, not in this increment" appendix, and the filtered readiness items;
  - the per-increment manifest;
  - `CHANGES.md` for a re-cut and for a first release against `builds_on`;
  - the whole-product `handoff/` folders are left untouched.
- **Integration `test_increment_jira.py`:** cycle 2 references the epic key recorded in cycle 1 instead of re-creating it, in both the offline CSV and the plan.
- **Integration `test_epic_views.py`:**
  - post-approve writes the views;
  - editing a view changes no state;
  - a re-approval rewrites them;
  - a large generated PRD splits under the size limit.
- **Contracts:**
  - `pm-handoff` mentions `--increment`;
  - stages 04, 06 and 08 carry the large-artifact guidance;
  - every `SKILL.md` change has its `agents/openai.yaml` twin.
- **No new telemetry events:** `handoff_released` and `handoff_recorded` take an `increment` payload field, so the drift test only gains payload docs.
- **PRISM acceptance, read-only:** the view sizes in §8.7.6 and `/pm-check --release` on the sprint folders. Nothing under `prism-ai` is written, moved or re-zipped.
- **Full suite in a clean worktree before each chunk is called done.**

#### 8.7.12 Risks

- **Folding sprint scope into a 451 KB PRD is the hardest step** (#66), and a regeneration that renumbers ids breaks every link (#52). Mitigation: an append-only edit in parts, `pm_finish_stage.py 03`, and the #52 id diff on approval. #52 should land before the PRISM fold-in.
- **The cascade is coarse.** Approving 03 for one new epic marks 04–09 stale. Per-epic views and `--reapprove` keep the catch-up small. Per-epic staleness is deliberately **not** proposed, because the state machine stays as it is.
- **`delivery.yaml` could become a second PRD.** Its prose fields (`goal`, `done_when`, `risks`, `note`) are short, and anything that needs an id goes into 03. `/pm-check` warns when a prose field cites an id that 03 doesn't declare.
- **PMs may go back to hand-built sprint docs** if the generated `PRD.md` lacks the narrative they liked (PRISM's "What / Who / Why now" table) or the points they plan with. Mitigation: render `goal` and the deferred list at the top, and re-confirm #22 (decision 14).
- **Approved text can change after release.** A later 03 approval can change a released member's text. `INC_SOURCE_BEHIND` and the next `CHANGES.md` name the ids, but nothing stops it, by design.
- **APEX's read-set isn't agreed yet** (#75). Until it is, `manifest.json` roles are PM-OS's own guess.

---

## 9. Part C — External engineering handoff (Jira / Linear / Figma)

Engineering handoff is an **export/sync action, not new pipeline stages** — the same category as the existing `/pm-share`. It runs *after* approved artifacts exist and pushes them outward. Model it as a `pm-handoff` skill family gated on `approved` status, rather than stages 09/10. It consumes the Part B delivery increments: an increment is the natural unit of a single handoff.

**Status: partly shipped.** The Jira half of this part is built; Linear, Figma, and design-token→React codegen remain unbuilt.

- **`/pm-handoff jira` — ✅ shipped (v1.2.0, offline route + screen mapping v1.3.0; declared Product Epic hierarchy aligned in B0).** `scripts/pm_handoff.py plan` parses the approved PRD (+ approved TRD) into a Jira ticket map (`EPIC-###` → Epic, `US-###` → Story, `FR-###`/`REQ-###` → Task, approved `TSK-###` → Subtask/Task when parentable) and writes a PM-readable dry-run, fully offline. Two create routes:
  - *Connector route:* dry-run → PM confirms → create via the **Atlassian MCP** → `record` writes ticket keys back into `.traceability.yaml`. Needs an authorized connector.
  - *Offline route (`--offline`):* `pm_handoff.py export` writes `handoff/jira-import.csv` (+ import guide, descriptions converted to Jira wiki markup via `lib/jira_markup.py`, `Issue Id`/`Parent Id` parent linking) that the PM imports through Jira's own CSV importer — **no connector, no tokens** — then recovers the keys and runs the same `record` step. Ends in the same state as the connector route.
- **`/pm-handoff linear` — 🔴 unbuilt.** The plan builder is tracker-agnostic, so Linear is mostly a second create adapter over the same map. (Per the roadmap's one-tracker principle, Jira was chosen first, not both.)
- **`/pm-handoff figma` — 🔴 unbuilt.** Two directions:
  - *Pull* (do first): read an existing Figma file to extract real design tokens/components so stage 04 extends the actual system. **Complementary** to enhancement mode, which already extracts design language from code — most useful when the design source of truth lives in Figma rather than the codebase.
  - *Push* (later): generate frames from the prototype brief.
  - **Direction warning — read before spending this name.** Both bullets above are **outbound/PM-initiated**: the PM reaches into Figma. A separate design (`pm-os-external-design-authority-plan.md`, recorded 2026-08-13) covers the **inbound** case, where a *designer* authors the IA + Figma and it enters stage 04 as a gated upstream input carrying decision authority. That is a different capability, not this one's other half, and its §5 design deliberately mints **no** new command name (it re-runs `/pm-stage-04-design-spec` against a `design-in/` directory). Do not assume `figma` covers both.
- **`/pm-handoff react` (design-token → React codegen) — 🔴 unbuilt, blocked on partner.** A partner team is building a **design-token system mapped to React components**. Once it exists, PM-OS reads those tokens and generates **React code for the `SCR-###` screens it designs** — turning the stage-05 HTML prototype into design-system-conformant React rather than throwaway markup. Consumes the shipped screen spine (`SCR-###` `Serves:` trace + `reference/screen-map.md`) and the approved design spec / prototype brief; **emits code, not tickets** (an export/sync action like the rest of Part C, gated on `approved`). **External prerequisite:** the token system must be published and its token→component mapping stable — PM-OS is a *consumer* of that contract, so this cannot ship before it exists. Complementary to Figma *pull* above: pull grounds the design spec in real tokens; this grounds the generated code in them.

**Delivery-increment scoping (from Part B, unbuilt):** `--increment INC-##` should narrow any of the above to a single increment's members **plus their required ancestor closure** (owning epics/stories), substituting previously-recorded Jira keys for parents created in earlier increments so the hierarchy survives (see §8.6). `record` stamps returned keys per increment so later cycles never recreate earlier tickets. The shipped Jira export currently exports the whole approved pipeline; `--increment` lands with Part B's B3.

This part **revised current v1 non-goals.** Spec §13 listed "Figma integration" and "MCP integrations beyond optional `pm-share`" as out of scope, and the cross-runtime plan called a unified MCP server out of scope. The shipped Jira export already retired the MCP-integration non-goal; the Figma non-goal is retired when Figma lands. MCP is supported across Claude Code / Codex / Gemini, so connectors stay cross-runtime-portable.

---

## 10. Open decisions to resolve before build

*Part A (resolved, shipped):*
1. **Codebase access** — resolved: both local path and git URL are supported.
2. **Understanding-doc structure** — resolved: the `00c` section list shipped.
3. **Mode field naming** — resolved: `project_type: new_product | enhancement` (default `new_product`).

*Part B (open):*
4. **Tier vocabulary** — confirm `mvp | v1 | v2 | later` (reuses stage-09 horizon language), or a different band set?
5. **Increment record shape** — resolved by §8.7.3, pending approval of that section: a single ungated `delivery.yaml`, matching `readiness.yaml`.
6. **Promote fidelity trigger** — does `/pm-promote` regenerate the whole story mini-spec immediately, or mark it "promotion-pending" until the next stage-03 run? Leaning immediate, so the fidelity debt is paid at the moment of promotion.
7. **Decision-record coupling** — should a tier change or an increment replan write to the (undecided) product decision record (backlog #23)? Depends on #23's shape. In the meantime §8.7 records a deferral's reason and its `OD-##` in `delivery.yaml`, and `CHANGES.md` cites it.

*Sprint path, §8.7 (open, 2026-10-21):*

8. **Sprint scope missing from the PRD.**
   - The question: must scope enter stage 03 before an increment can include it, or may an increment carry sprint-local items with their own ids?
   - **Recommend:** stage 03 first. Sprint-local ids are how PRISM's sprints lost their link to the product.
9. **Membership unit.**
   - The question: stories and requirements with tasks derived, or `TSK` first as §8.5 said?
   - **Recommend:** stories and requirements with tasks derived. That is how PRISM cut both sprints and how APEX reads.
10. **Per-epic view folder.**
    - The question: what is it called, and is it committed? `views/` is taken by `00-context/views/`.
    - **Recommend:** `by-epic/`, committed. It is small and diffable, and teammates see the same views.
11. **Increment package layout.**
    - The question: `handoff/INC-002/<audience>/` or `handoff/<audience>/INC-002/`?
    - **Recommend:** the former. It keeps one increment self-contained for zipping and sending, and leaves the whole-product folders alone.
12. **Readiness timing.**
    - The question: should readiness `due` accept an `INC-###`, with the active increment as the current milestone?
    - **Recommend:** yes. Existing milestone lists keep working.
13. **PRISM migration.**
    - The options:
      - (a) record sprints 1 and 2 as external released increments, with aliases only for in-flight items;
      - (b) fully retro-convert both sprint folders;
      - (c) start at INC-001 with sprint 3.
    - **Recommend (a).**
14. **Re-confirm #22.** PRISM's sprint docs carry story points, and §8.7 still stores no points, dates or capacity.
    - **Recommend:** keep #22, and render `goal` and the deferred list prominently instead.

---

## 11. Sequencing

Independently shippable; ordered by dependency. Part A shipped (v0.5.9 / v0.6.0). Part B is the immediate open design; Part C's B1 shipped as `/pm-handoff jira` (v1.2.0).

| Phase | Work | Depends on | Status |
|---|---|---|---|
| **A0** | `00c` codebase-understanding + Explore-based reading + drift signal | mode flag | ✅ shipped |
| **A1** | Schema + `pm_new` (`--mode`, `--codebase`) + `pm_status` plumbing | — | ✅ shipped |
| **A2 / E2** | Read-only affected-slice enhancement pathway: one product/one project continuation, captured before/after baseline, `00c` inventory, marketplace-strengthened impact scan, decision boundary, scoped multi-surface updates across 01–09, regression/check/handoff, refresh and dogfood | A0, A1, entry-pathways E1/E3; Part-B interface contract | ✅ shipped v1.5.0 (PR #68) |
| **B0** | Resolve the synthetic-epic vs. per-story export mismatch to one declared-Product-Epic Jira mapping (backlog #28) | — | ✅ shipped |
| **B1** | Scope-tier attribute (`Tier:` on `US`/`FR`) + stage-02 tier declaration + stages 04–07 default-to-`mvp` filter | #19 shipped, B0 | 🔴 open |
| **B2** | Tiered-fidelity contract (v2 mini-spec checks apply to `tier: mvp` only) + `/pm-promote` | B1 | 🔴 open |
| **R** | Release check, approval version and stamps, readiness record, release record, change note and manifest (#70–#75, #68), the APEX chunks 1–2 | — | 🟢 built on branches, not released |
| **B3v** | Id carving and per-epic views `by-epic/` (#66, §8.7.6). There's no new state, so it can ship first | — | 🔴 open |
| **B3** | Delivery-increment layer: `delivery.yaml`, `INC-###` by `US`/`FR` with tasks derived, and the §8.7.4 checks (§8.7.3) | #20 shipped, R. B1 is **no longer a prerequisite**; only `INC_HORIZON_LATER` waits for it | 🔴 open |
| **B3p** | `--package --increment`, which generates the sprint `PRD.md` (§8.7.5) | B3, B3v, R | 🔴 open |
| **#52** | Stable-id diff on approval. Needed before any large PRD fold-in (§8.7.12) | — | 🔴 open |
| **C1** | `/pm-handoff jira` (export PRD/TRD → tickets); `--increment` scoping | A complete, B3 | 🟡 base shipped v1.2.0; `--increment` open |
| **C2** | Figma *pull* to ground enhancement-mode design spec | C1 | 🔴 open |
| **C3** | Figma *push* + spec §13 non-goal revision | C2 | 🔴 open |
| **C4** | Design-token → React codegen for `SCR-###` screens | C1, external token system | 🔴 open (blocked on partner) |

---

## 12. Acceptance criteria

**Part A infrastructure (met):**
- [x] `/pm-new --mode enhancement --codebase <path>` scaffolds a project with `project_type=enhancement` and `codebase_path` set.
- [x] `/pm-new` with no mode defaults to `new_product` and behaves exactly as today (no regression for greenfield).
- [x] The `00c` understanding doc passes the normal draft → approve gate; stage 01 is blocked until it is approved.
- [x] Stage 01 has enhancement framing; `/pm-status` shows mode and a status-only codebase drift warning; telemetry records `project_type`.
- [x] No change to new-product behavior, hashing, staleness, or telemetry semantics.

**Full enhancement pathway / E2 (target):**
- [x] Target repositories are read-only in practice and in tests; every output is written outside the target repo.
- [x] A lightweight repository inventory leads to an affected-slice/impact-cone `00c`, not a whole-product reconstruction; coverage/exclusions/confidence and widening decisions are explicit.
- [x] A product is represented by one PM-OS project: an external product initializes that project once, while a PM-OS-native or previously imported product handles every subsequent enhancement in place using captured approved hashes/code ref, normal history/reapproval/staleness, and stable unaffected IDs/content.
- [x] `project_type` remains the product's first-intake identity. A separate persisted in-project enhancement context supplies the active ask/baseline/affected-surface signal to conditional blocks without creating approval/status state; approved canonical artifacts become the updated product-of-record.
- [x] `/pm-promote` is not part of pathway activation; it remains the Part-B requirement-tier operation inside the same PRD. Fresh first-intake routing and established-project continuation use unambiguous terminology.
- [x] Repository identity/ref is bound to the cycle/`00c` evidence; preparation cannot mask drift; refresh/rebase is explicit and cascades ordinary staleness.
- [x] The decision-focused interview produces an approved enhancement boundary and blocks on unresolved baseline/scope/regression/compatibility decisions unless risk is explicitly accepted.
- [x] The behavior table above is implemented across 00c/00u and stages 01–09 for UI, API, data, service, event, integration, and operations without forcing frontend artifacts onto non-UI work.
- [x] Regression invariants, affected surfaces, requirements, tests, tasks, rollout/rollback and the delta-only handoff are traceable and checked.
- [x] The E2 acceptance matrix in `pm-os-entry-pathways-plan.md` passes for marketplace portability, greenfield/prototype regression, backward compatibility, drift, monorepo, external first intake, and PM-OS-built-product repeat cycles. The separately labeled E0 safe-route-correction follow-up is not part of E2.

**Part B (target):**
- [x] The synthetic-epic/per-story export mismatch is resolved to one declared-Product-Epic Jira mapping before any tier/increment work (B0).
- [ ] Each `US-###`/`FR-###` carries an optional `Tier:` (default `mvp`); existing projects are unchanged.
- [ ] Stages 04–07 stay MVP-scoped by default; the MVP pipeline behaves identically to today.
- [ ] Non-MVP stories may be stubs; the v2 mini-spec contract applies only to `tier: mvp`; `/pm-promote` elevates a stub and triggers full-fidelity regeneration.
- [ ] Delivery increments (`INC-###`) group approved `US`/`FR` ids, with `TSK-###` derived (revised §8.7.3). They are ungated and never mark any stage stale on replan.
- [ ] `/pm-check` warns on tier inversion and increment/dependency ordering, without gating.
- [ ] No change to the gate, hash, status, or staleness machinery.

**Sprint path (§8.7, target):**
- [ ] `/pm-handoff --package --increment INC-###` builds `handoff/INC-###/<audience>/`. Each folder contains a generated `PRD.md` cut verbatim from approved 03, only the members and their ancestors, a "Referenced, not in this increment" appendix, the readiness items due, `manifest.json` and `CHANGES.md`.
- [ ] A re-cut released with `--release-note` writes `REL-###` and a change note against the same increment's previous release. A first release compares with its `builds_on` increment.
- [ ] Approving 03, 06 or 08 writes `by-epic/` views from the approved body. On PRISM-sized input, no per-epic view exceeds about 64 KB, and editing a view changes no state.
- [ ] No `.meta.yaml`, `config.yaml` or `.traceability.yaml` shape change. A project without `delivery.yaml` behaves exactly as today.
- [ ] The interim route (§8.7.7) is documented in the SOP, and it works on PRISM's hand-built sprint folders without writing to them.

**Part C (target):**
- [ ] `/pm-handoff jira --increment INC-##` exports only that increment's tasks; returned ticket keys are recorded per increment so later cycles never recreate earlier tickets.

---

End of plan.
