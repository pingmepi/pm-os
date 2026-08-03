# PM-OS Modes, Delivery Model & Engineering Handoff Plan

**Status:** 🟡 **Part A infrastructure implemented; its full enhancement pathway is E2 planned. Part B partially built; Part C partly shipped.** Enhancement plumbing shipped: `--mode enhancement`, `--codebase <url-or-path>`, `project_type`/`codebase_path`/`codebase_ref` in `.meta.yaml` (schema v3), conditional `00c`, `prepare-codebase`, and a status-only drift signal. Stage 01 has delta framing; the affected-slice scanner, cycle lineage, baseline integrity, decision interview, multi-surface overlays for stages 02–09, regression/consistency, and delta-only handoff remain unbuilt and are now sequenced in `pm-os-entry-pathways-plan.md` E2. **Part B — the delivery model (scope tiers + delivery increments) — is designed here (2026-07-27); B0 plus prerequisite priority/TRD contract work are shipped, while tiers and increments remain unbuilt.** Part C (external engineering handoff) is partly shipped: `/pm-handoff jira` — both the Atlassian-MCP create route and the `--offline` CSV export — landed v1.2.0 (screen mapping v1.3.0); `/pm-handoff linear`, Figma pull/push, and design-token→React codegen remain unbuilt. Delivery-model and unbuilt-handoff work is tracked as Phase 4 in `docs/roadmap/current-state-review.md` §7 and as backlog #28.
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

**Risk:** the shipped flag/gate plumbing is low-risk, but the full pathway is not: slice completeness, source-project lineage, baseline identity, multi-surface contracts, regression scope, and handoff correctness are cross-cutting. E2 therefore ships in the dependency order and acceptance matrix in `pm-os-entry-pathways-plan.md`, while keeping the existing status/hash/gate state machine authoritative.

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

With that mapping in place, `/pm-handoff jira --increment INC-02` scopes the export to that increment — but **an increment export is the member set plus its required ancestor closure, not the members alone.** `scripts/pm_handoff.py` parents Subtasks to their owning requirement/story and standard Jira work items to their declared `EPIC-###`; the offline exporter resolves `Parent Id` only against issues present in the *same* CSV. So a subtask-only export orphans every subtask unless its Story/Task parent (and the epic ancestor for standard work items) is also present or represented by a previously-recorded Jira key. The export must therefore emit, for each member, the required ancestors it hangs from. And because those ancestors may have been created in an *earlier* increment, the export must **substitute the previously-recorded Jira keys** (from `.traceability.yaml`'s per-increment `tickets:` slots) for any parent already created, rather than re-creating it. `.traceability.yaml` records returned ticket keys per increment so cycle 2 never recreates cycle 1's tickets. This is a prerequisite-aware refinement of backlog #28.

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
5. **Increment record shape** — a single `delivery.yaml`, or per-increment `INC-###` entries folded into `.meta.yaml`? Leaning `delivery.yaml` (append-friendly, sits beside `.meta.yaml` like the other root dotfiles).
6. **Promote fidelity trigger** — does `/pm-promote` regenerate the whole story mini-spec immediately, or mark it "promotion-pending" until the next stage-03 run? Leaning immediate, so the fidelity debt is paid at the moment of promotion.
7. **Decision-record coupling** — should a tier change or an increment replan write to the (undecided) product decision record (backlog #23)? Depends on #23's shape.

---

## 11. Sequencing

Independently shippable; ordered by dependency. Part A shipped (v0.5.9 / v0.6.0). Part B is the immediate open design; Part C's B1 shipped as `/pm-handoff jira` (v1.2.0).

| Phase | Work | Depends on | Status |
|---|---|---|---|
| **A0** | `00c` codebase-understanding + Explore-based reading + drift signal | mode flag | ✅ shipped |
| **A1** | Schema + `pm_new` (`--mode`, `--codebase`) + `pm_status` plumbing | — | ✅ shipped |
| **A2 / E2** | Read-only affected-slice enhancement pathway: cycle lineage, baseline integrity, marketplace-strengthened impact scan, decision boundary, multi-surface conditional blocks across 01–09, regression/check/handoff, refresh and dogfood | A0, A1, entry-pathways E1/E3 | 🔴 unbuilt; development order in entry-pathways E2.0–E2.7 |
| **B0** | Resolve the synthetic-epic vs. per-story export mismatch to one declared-Product-Epic Jira mapping (backlog #28) | — | ✅ shipped |
| **B1** | Scope-tier attribute (`Tier:` on `US`/`FR`) + stage-02 tier declaration + stages 04–07 default-to-`mvp` filter | #19 shipped, B0 | 🔴 open |
| **B2** | Tiered-fidelity contract (v2 mini-spec checks apply to `tier: mvp` only) + `/pm-promote` | B1 | 🔴 open |
| **B3** | Delivery-increment layer (`delivery.yaml`, `INC-###` by `TSK`) + `/pm-check` cross-validation | #20 shipped, B1 | 🔴 open |
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
- [ ] Target repositories are read-only in practice and in tests; every output is written outside the target repo.
- [ ] A lightweight repository inventory leads to an affected-slice/impact-cone `00c`, not a whole-product reconstruction; coverage/exclusions/confidence and widening decisions are explicit.
- [ ] External products and products originally built with PM-OS both create separate enhancement cycles with correct baseline/source lineage; original PM-OS product artifacts remain unchanged.
- [ ] `/pm-promote` is not part of pathway activation; fresh route correction and enhancement-cycle binding use unambiguous terminology and refuse unsafe late conversion.
- [ ] Repository identity/ref is bound to `00c`; preparation cannot mask drift; refresh/rebase is explicit and cascades ordinary staleness.
- [ ] The decision-focused interview produces an approved enhancement boundary and blocks on unresolved baseline/scope/regression/compatibility decisions unless risk is explicitly accepted.
- [ ] The behavior table above is implemented across 00c/00u and stages 01–09 for UI, API, data, service, event, integration, and operations without forcing frontend artifacts onto non-UI work.
- [ ] Regression invariants, affected surfaces, requirements, tests, tasks, rollout/rollback and the delta-only handoff are traceable and checked.
- [ ] The full E2 acceptance matrix in `pm-os-entry-pathways-plan.md` passes, including marketplace-adapter safety, greenfield/prototype regression, migration, drift, monorepo, external-product and PM-OS-built-product dogfood.

**Part B (target):**
- [x] The synthetic-epic/per-story export mismatch is resolved to one declared-Product-Epic Jira mapping before any tier/increment work (B0).
- [ ] Each `US-###`/`FR-###` carries an optional `Tier:` (default `mvp`); existing projects are unchanged.
- [ ] Stages 04–07 stay MVP-scoped by default; the MVP pipeline behaves identically to today.
- [ ] Non-MVP stories may be stubs; the v2 mini-spec contract applies only to `tier: mvp`; `/pm-promote` elevates a stub and triggers full-fidelity regeneration.
- [ ] Delivery increments (`INC-###`) group `TSK-###`, are ungated, and never mark stage 08/09 stale on replan.
- [ ] `/pm-check` warns on tier inversion and increment/dependency ordering, without gating.
- [ ] No change to the gate, hash, status, or staleness machinery.

**Part C (target):**
- [ ] `/pm-handoff jira --increment INC-##` exports only that increment's tasks; returned ticket keys are recorded per increment so later cycles never recreate earlier tickets.

---

End of plan.
