# PM-OS Entry Pathways & Interview Plan

**Status:** E1 (pathway 2) and **E3 (standalone `/pm-interview` + known-unknowns surfacing)** shipped, pending PM review. **E2 is implemented on `feat/e2-affected-slice-enhancement`, pending final verification/review/merge:** read-only code evidence, `00c`-owned repository inventory, affected-slice generation, same-project product evolution, decision-focused interview, multi-surface stages, consistency, delta-only handoff, explicit refresh, and two-cycle provenance are built below.
**Author:** Karan (with Claude Code)
**Companion:** `pm-os-consistency-spine-plan.md` — the consistency-spine + v1.4.1 fixes half of the same next-development arc. This doc is the entry-pathways half.
**Realizes / supersedes:** the reserved **Phase 5 "thin-context discovery interview"** in `adaptive-context-intelligence-pack.md` (originally a ≤5-question nudge for thin inputs, skippable, answers registered as a PM-authored source, skips → known unknowns). This plan is the canonical replacement: it is pathway-aware and feasibility/coverage-driven, with a soft ~5 per topic round rather than a fixed total. E1/E3 implement the shared intake/re-run mechanics; E2 adds the decision-focused enhancement tuning.
**Provenance boundary:** do not resume or merge the abandoned `feat/whole-product-foundation` branch. E2 may reuse its useful design provenance — one-project product-of-record, tagged provenance, change boundary/blast-radius overlays, regression-class QA, and enhancement handoff payload — but must rebuild those ideas against current `main`. Do **not** carry forward its child-project/program-object shape for a PM-OS-native product. Its `/pm-promote` meant **promoting a deferred requirement to a higher-fidelity release tier inside the same project**; E2 does not use that command to convert a product or project into an enhancement.

---

## 1. The organizing principle

A PM does not always start from a one-line idea. They start from **the highest artifact the client/business has already approved** — and an approval means *adopt it, don't relitigate it*. That single fact determines three things for any project:

- what PM-OS **adopts** (the approved artifact becomes its stage, `origin: imported`),
- what PM-OS still **owes upstream** (the missing WHY/WHAT below the entry artifact — backfilled or interviewed),
- what is **fresh work** (the definition forward, or the enhancement delta).

This is the same propagating-flag shape PM-OS already uses (`genai_flag`, `project_type`): the entry point is a project-level fact set at intake that conditions every downstream stage — with **no skill forking**.

## 2. The three pathways

| Pathway | Client-approved entry | ≈ Stage | Built today | New work |
|---|---|---|---|---|
| **1 · Idea** | Business statement (+ context) | 00 | ✅ `/pm-new` (greenfield) | — |
| **2 · Prototype** | A prototype shown & approved; **no code yet** | ~04/05 | partial — `/pm-context-import` adopts + lossy-backfills | **Interview (broad)** carries the WHY/scope the prototype lost; then formalize-forward to dev/design handoff |
| **3 · Live product** | A shipped product + **read-only codebase**; optionally its prior PM-OS project | past 09 | Part A shipped — `--mode enhancement --codebase`, `00c` | Generate only the **affected product slice + impact cone**; a narrow decision interview supplies what code cannot; flow the scoped delta through stages 01–09 and handoff |

### The two-axis model (why 2 and 3 differ in kind, not just cost)

- **Extraction cost vs. elicitation cost move oppositely.** Prototype = cheap to read, expensive to interview (thin source, no WHY). Codebase = expensive to inspect and gives evidence for implemented WHAT/HOW, but cannot establish deployed configuration, business intent, success, non-goals, or compatibility promises; the interview is therefore narrow and **decision-focused**, not absent.
- **Complete-forward vs. scoped-delta.** Pathways 1 & 2 build one full definition forward. Pathway 3 strengthens `00c` with a lightweight repository inventory, traces an **impact cone** around the ask, and processes only that affected slice. For an external product's first PM-OS intake this populates its project pipeline; for a product already represented in PM-OS it updates that same project's canonical artifacts in place, preserving unaffected IDs/content and prior versions. It widens the cone when dependency evidence or uncertainty demands it; it does not reconstruct the whole product by default.

## 2b. The uniform front door (routing + guidance)

`/pm-new <slug> ["statement"]` is the **single entry when the product does not already have a PM-OS project** — it scaffolds one project, asks one routing question, and prints tailored next-step guidance, mirroring the existing GenAI prompt (interactive on a tty; a flag/env escape for unattended runs). A subsequent enhancement to a product already represented in PM-OS starts from inside that existing project; it must not scaffold a child project.

```
Project "<slug>" created.
What are you starting from?
  [1] New idea — nothing built or approved yet
  [2] Approved prototype / design (no code yet)
  [3] Existing live product (codebase)
```

- **[1] New** → proceed greenfield: `/pm-stage-01-brief`.
- **[2] Prototype** (pathway 2) → `/pm-context-import <prototype + any supporting context you have>` (adopt everything provided + interview for the *residual* missing why/scope).
- **[3] Enhancement** (pathway 3, external product's first PM-OS intake) → prompt for the read-only codebase, bind it to the new product project, then `/pm-context-import --codebase <…>`.

Uniform to *use for first intake* (`/pm-new`) and uniform to *consume* (created → pick type → told exactly what's next). It also removes the trap where a prototype PM silently lands in greenfield and skips context-import. Existing PM-OS projects use the E2 in-project continuation operation defined in E2.1 instead of returning to `/pm-new`.

**Mechanics:** this gives first-intake `type` the same treatment `genai` already has — an interactive prompt plus a flag/env escape (`--entry {new,prototype,enhancement}`, with `--codebase` for enhancement; `--mode`/`PM_OS_PROJECT_TYPE` kept as back-compat aliases). In the shipped pathway-2 slice, `[1]` and `[2]` are fully wired and `[3]` reuses today's external-product enhancement scaffold behavior (`project_type: enhancement`, `codebase_path` when provided). E2 adds the **same-project continuation** operation for an existing PM-OS product, baseline capture, strengthened `00c`, and scoped in-place regeneration. Do not call this product promotion: `/pm-promote` is reserved for the separate release-tier fidelity concept in the delivery-model plan.

### Product-project identity — three entry cases

1. **External product, never represented in PM-OS:** create its PM-OS product project once, bind the codebase snapshot as observed current-state evidence, and elicit the missing product decisions. Later enhancements to that product continue in this project rather than creating sibling projects.
2. **Product already represented in PM-OS:** continue in the existing project. Its approved artifacts are the product-of-record and its built codebase is current implementation evidence. Capture the pre-change artifact hashes plus pinned code ref, then update canonical stages in place for the affected IDs/sections; preserve unaffected IDs/content, use normal history/reapproval/staleness, and compute the handoff delta from the captured baseline. Do not create a child project or a second gate/status lineage.
3. **Wrong route selected during fresh scaffold:** before any stage 01+ artifact exists, an explicit route-correction operation may change `new`/`prototype` to `enhancement`, bind the codebase, and add `00c`. Once downstream work exists, route correction must refuse rather than silently reframe it.

The separate Part-B whole-product plan owns `mvp | v1 | v2 | later` tiers, `/pm-promote`, and delivery increments. E2 consumes that model when present but does not rebuild it: promoting an existing deferred requirement happens in the same PRD; a net-new enhancement receives stable IDs and the appropriate tier in that same project. Until Part B ships, existing requirements retain today's default-MVP behavior and E2 must not fabricate tier state.

**Project identity vs. active work:** `project_type` records how the product first entered PM-OS and must not be flipped from `new_product` merely because its next piece of work is an enhancement. E2.1 adds one persisted **in-project enhancement context** (exact file/schema and command frozen in E2.0) containing the PM-authored ask source, captured pre-change artifact hashes, pinned code ref, affected IDs/surfaces, and provenance. It conditions the E2 overlays but owns no approval/status values; the existing stage states remain authoritative. When the scoped change is approved and handed off, its context is retained as immutable provenance and the newly approved canonical artifacts become the next product-of-record. Part-B delivery increments remain a separate scheduling/handoff ledger.

## 3. What already exists (build on, don't rebuild)

- **`/pm-context-import`** — adopts PM-authored artifacts as their stage and **reverse-generates** the missing upstream stages ("backfill"), gated by the understanding doc. The **feasibility map** (`skills/pm-context-import/SKILL.md` §"Feasibility map") already rates each missing upstream ✅ faithful / ⚠️ lossy / ⛔ infeasible, and the `preflight` subcommand (`scripts/pm_context_import.py`) prints those verdicts.
- **Stage-00 group** — `00` business statement, `00w` context-wiki pack, `00u` understanding doc, `00c` codebase-understanding (enhancement only). All gated.
- **Enhancement pathway (Part A + E2 branch)** — the shipped first-intake identity/codebase plumbing is extended on the E2 branch with `/pm-enhance`, frozen baselines, deterministic inventory/slice/impact analysis, boundary interview, multi-surface stages, checks, scoped handoff, refresh, completion, and same-project repeat cycles.
- **The understanding doc** already has the six sections the interview feeds: *What I understood, Source trust table, Assumption register, Conflict resolution block, Coverage map, What happens on approval.*

The gap is not "start from a PRD/prototype" (that exists). The gap is: when the entry artifact is too far downstream, backfill is ⚠️/⛔ and the missing WHY/scope can only come from the PM's head — and **nothing interviews them for it**. Today the skill commits a lossy backfill as `draft` and waits for async `> **PM:**` edits.

## 4. The interview primitive (the one genuinely new capability)

An interactive elicitation step that **converts feasibility verdicts from ⚠️/⛔ to ✅** by asking the PM for the information the downstream entry artifact threw away — realizing the reserved Phase 5 discovery interview and wiring it to the feasibility map.

**Contract (inherited from Phase 5, non-negotiable):**
- **As many questions as the missing coverage requires — not a fixed count.** Ask only **load-bearing gaps**: ones the feasibility map flags as blocking a faithful backfill or driving a downstream stage, and that the **provided sources don't already answer**. Batch by topic and ask in **strictly decreasing order of impact** (highest-impact topic first), with a **soft cap of ~5 per topic round** to stay digestible. The PM may skip any question or stop early; skipped/unanswered → known unknowns. (A thin prototype is typically several rounds; a well-documented one, a short round or none.)
- Answers are **registered as a PM-authored source** (traceable, high-confidence, reusable) — via `pm_context_import.py register … --type context` so provenance flows into the wiki/evidence ledger.
- **Skips → known unknowns**, recorded in the wiki's `## Open questions & uncertainties` and the understanding doc's assumption register — **never converted into silent assumptions.**
- Judgment lives in `SKILL.md`; Python only moves bytes (register the answers, re-run preflight).

**How questions are chosen (feasibility-driven):** rank the gaps by (a) preflight verdict severity (⛔ > ⚠️), (b) how many downstream stages the gap blocks, and (c) high-impact `[inferred]` rows in the assumption register / unresolved conflicts. Ask about the *substance the entry artifact cannot carry* — in decreasing-impact topic order: problem/why → target users & pains → success criteria → scope boundary → non-goals/descope history → hard constraints → decision authority. Each topic is a short round (soft ~5), highest-impact topic first, and any topic the provided sources already cover is skipped entirely.

**Pathway-aware tuning (same primitive, opposite weight):**
- **Pathway 2 (prototype, thin source):** the interview carries the bulk — a guided brief/scope reconstruction, typically several topic rounds. It shrinks by exactly however much supporting context the PM also brought (see §5) — anything the sources answer isn't asked.
- **Pathway 3 (codebase, observed implementation):** narrow and decision-focused — confirm which release/ref represents reality; why this change matters; the current→target behavior; affected users; scope and explicit non-touch boundary; compatibility/migration promises; success baseline/target; rollout/rollback constraints; and what must not regress. Do not ask for architecture or behavior already supported by cited code evidence.

**Non-interactive safety (per repo convention):** an env/flag escape and a non-tty branch — e.g. `--interview-answers <file>` to supply answers unattended, and `PM_OS_INTERVIEW=skip` (or a non-tty session) records every question as a known unknown. Pathway 3 classifies unknowns as `blocking` or `non-blocking`: missing baseline identity, change boundary, regression invariants, or required compatibility/migration decisions block stage 01 unless the PM explicitly records an accepted risk; lower-impact unknowns may proceed visibly. Mirrors `PM_OS_EDITED_UPSTREAM_CHOICE` without turning skips into safe defaults.

**Where it lives:** pathway intake interviewing is a step in `/pm-context-import` (after `preflight`, before the understanding doc is finalized), so it plugs into the existing approval gate. E3 adds the standalone `/pm-interview` re-run against remaining known unknowns without replacing the intake step.

## 5. Pathway 2 — Approved prototype, no code

The prototype **is** the product definition; there is no code, no users, no back-compat. The job is to recover the WHY/scope beneath it and **formalize forward** to a dev/design-ready pipeline.

**Bring everything, not just the prototype.** `/pm-context-import` already ingests **any mix of sources** in one call — research, briefs, PRD fragments, notes, call transcripts, design docs, the prototype — as a folder or a file list (Step 1 registers them recursively; Step 2 classifies each as *adopt-as-stage* vs *context-only*; all feed the wiki/evidence). So additional context is a first-class input **today** — the prototype is simply the highest-fidelity *adoptable* artifact, and everything else grounds the backfill. Crucially, this is what **shrinks the interview**: the more the sources already answer, the fewer residual gaps remain, so the interview asks only what's *still* missing after all provided context is ingested.

Flow: `/pm-context-import <prototype + any supporting context you have>` → doc-scan (no `00c`) → `preflight` (expect ⚠️/⛔ on the upstream gaps the sources don't cover) → **interview (broad, decreasing-impact rounds)** over the *residual* gaps → backfill 01–03 at the raised fidelity → adopt the prototype/design as its stage → normal pipeline forward (06 QA, 07 metrics, 08 TRD) → `/pm-handoff`.

## 6. Pathway 3 — Live product + codebase

The product exists and runs; the client asks for a **change**. PM-OS receives read-only access: it may list/read/search files and run non-mutating inspection commands, but it must never edit the target repository, write generated files into it, change its index/worktree/ref, or run a formatter/build/test that writes there. Remote URLs may be cloned into the PM-OS project using read credentials; supplied local repositories remain untouched. All generated material lives in the PM-OS project.

### Slice-first feasibility: generate the affected product surface, not the whole product

This is feasible and is the E2 default. The scan has three bounded rings:

1. **Inventory ring:** a cheap whole-repository map of manifests, workspaces, entry points, routes/interfaces, data stores, tests, CI/deployment, shared libraries, and ownership boundaries. This is an internal scan substrate summarized in `00-codebase-understanding.md` (`00c`) with coverage/exclusion/confidence evidence — not a second wiki or a new product artifact. It prevents a narrowly worded ask from hiding an obvious cross-cutting dependency; it is context, not a reconstructed whole-product artifact.
2. **Change-surface ring:** locate the user/system surfaces named or implied by the approved ask and trace their current behavior with repository-relative file/line evidence.
3. **Impact-cone ring:** follow inbound/outbound dependencies, shared components, APIs/events, data/schema paths, permissions, configuration/feature flags, tests, observability, deployment, and known consumers. Record explicit non-touch surfaces and coverage gaps.

Generate or refresh `00c`, then generate/regenerate only the affected portions of stages 01–09 and handoff. Existing unaffected behavior is carried forward unchanged and appears in delta outputs only where needed as an invariant, dependency, or regression boundary. If the cone reaches a shared primitive, an unknown dynamic boundary, multiple packages/services, or conflicting evidence, widen the scan and explain why; never silently claim the original slice is complete.

Static reading cannot prove every runtime relationship, especially with reflection, dynamic imports, feature flags, environment-specific configuration, generated code, or services outside the granted repository. The approval gate must therefore show scan coverage, exclusions, evidence, and confidence rather than promise perfect blast-radius detection.

### Full product-surface support

E2 supports the whole **kind** of enhancement, not only frontend changes. Capture a multi-valued affected-surface set such as `ui`, `api`, `data`, `service`, `event`, `integration`, and `operations`. Stage 04/05 behavior branches by the surfaces actually affected: UI work uses screens/components and an interactive prototype; API/data/service/event/integration/operations work uses interface contracts, schemas/migrations, service flows, event contracts, sandbox/mock/sample payloads, or operational validation artifacts. Do not invent screens or force HTML for a non-UI enhancement. The exact non-UI traceability primitive is decided in E2.0; existing `SCR-###` remains valid for UI and must not be broken.

### Stronger codebase understanding by borrowing, not depending blindly

E2 starts with a short marketplace evaluation and then vendors/adapts the selected read-only patterns into PM-OS's portable scan skill:

- GitHub Awesome Copilot's [`acquire-codebase-knowledge`](https://github.com/github/awesome-copilot/tree/main/skills/acquire-codebase-knowledge) is the primary candidate: deterministic stack/structure/integration/testing inventory, focus-area mode, evidence-only claims, explicit `[TODO]`/`[ASK USER]`, monorepo handling, and generated-output exclusions. Its helper must write output to the PM-OS project, never `docs/codebase/` inside the target repo.
- Awesome Copilot's [`arch` documentation workflow](https://awesome-copilot.github.com/plugin/arch/) is a secondary pattern for cited architecture, contradiction handling, and deep-diving complex subsystems. Reuse the pattern or run it only in an isolated PM-OS-owned snapshot because its normal workflow authors documents in the repository.
- A regression-scope skill may inform QA impact analysis after its license/security/portability review; it is enrichment, not the sole source of the regression boundary.

Marketplace/runtime-specific skills never become a required gate dependency. The PM-OS-owned `pm-context-scan-codebase` contract remains authoritative and works in Claude and Codex. Every adopted skill/script is pinned to a reviewed commit, license-attributed, inspected for writes/network/subprocess behavior, and wrapped so read-only access is mechanically testable.

Flow for a product's first PM-OS intake: create its project → `/pm-context-import --codebase <url|path> [+ docs]`. Flow for an existing PM-OS product: start the E2 continuation operation inside that project → capture approved artifact hashes + code ref → refresh/add `00c` without creating a child. Both then converge: read-only inventory + affected-slice/impact-cone scan → `00c` + context → **narrow decision interview** → approve the stage-00 boundary → scoped in-place generation/regeneration across affected portions of stages 01–09 → `/pm-check` → `/pm-handoff` with computed delta, invariants, regression, baseline reference, and affected-surface evidence.

## 7. Phases

Independently shippable; ordered by dependency. Each ships with tests (`docs/guides/testing.md`) and both runtime entrypoints (`SKILL.md` + `agents/openai.yaml`).

| Phase | Work | Files | Depends on |
|---|---|---|---|
| **E0** | **Uniform first-intake front door + routing (§2b).** `/pm-new` scaffolds a product not already represented in PM-OS, then an interactive routing prompt (new/prototype/external-product enhancement, mirroring the GenAI prompt) sets the type and prints tailored next-step guidance; `--entry`/`--codebase`/env are the non-tty escape. Chosen route recorded in telemetry. **Pathway-2 milestone scope:** `[1]`/`[2]` fully wired; `[3]` presented and reuses today's external-product enhancement scaffold behavior; same-project continuation lands with E2. | `scripts/pm_new.py`, `skills/pm-new/SKILL.md` (+ `agents/openai.yaml`), telemetry | — |
| **E1** | **Interview primitive (realizes Phase 5), pathway-2 tuning.** New context-import Step (coverage-driven questions, batched by topic in decreasing-impact order, over residual gaps only), register answers as a PM source, re-run preflight, record skips as known unknowns; non-tty/flag escape | `skills/pm-context-import/SKILL.md`, `scripts/pm_context_import.py` (register-answers helper + preflight re-run) | E0 |
| **E2** | **Pathway 3: read-only affected-slice enhancement in one product project.** Create a project only for a product not yet represented in PM-OS; otherwise continue in place. Strengthen `00c` with repository inventory, map only the affected slice/impact cone, run a decision-focused interview, and propagate the delta across UI/API/data/service/event/integration/operations through scoped stage updates, consistency checks, regression traceability, and handoff. See the dependency order below. | intake/scanner, stages 01–09, contracts/traceability/check/status/handoff | E1, E3, modes Part A; Part-B interface contract |
| **E3** | **✅ Shipped (pending PM review).** Standalone `/pm-interview` re-run against remaining known-unknowns; provenance + telemetry polish; surface known-unknowns in `/pm-status` | new `skills/pm-interview/` (+ `agents/openai.yaml`), new `scripts/pm_interview.py` (`list-unknowns`/`resolve`), `scripts/pm_status.py` | E1 |

> **Executable build plans:** E0–E1 (pathway 2) → `pm-os-pathway-2-execution-runbook.md`; **E2 → `pm-os-e2-execution-runbook.md`; E3 → `pm-os-e3-execution-runbook.md`**. The E2 dependency order below defines *what* must land; its execution runbook defines *how to build it* through strict, tests-first loops (aim → confirm red → minimal code → verify → pass-if-green → update tasks), scheduled full-suite regression gates, stop conditions, read-only proofs, and two-cycle dogfood. Do not execute E2 directly from the dependency table.

### E2 development order — dependency locked

| Order | Increment | Deliverable | Depends on |
|---:|---|---|---|
| 1 | **E2.0 — Contract + marketplace spike** | Freeze the read-only boundary and **one product = one PM-OS project** invariant; confirm `00c` is the only user-facing codebase-inventory artifact; prove slice-first scan on representative UI and non-UI fixtures; evaluate/pin/license-review `acquire-codebase-knowledge`, `arch`, and regression-scope candidates; decide the smallest multi-surface traceability extension and exact in-project continuation interface. No production implementation until the spike shows coverage/exclusion output and no target-repo writes. | E1/E3 |
| 2 | **E2.1 — Product-project continuation + baseline capture** | Implement one-time external-product initialization, same-project continuation for every later enhancement, and safe pre-stage route correction. Persist the ask source, affected IDs/surfaces, approved artifact hashes and pinned code ref in an in-project enhancement context so delta/handoff and rollback provenance are reproducible. Keep `project_type` as origin identity; do not flip it to activate overlays. The context adds no approval/status values, child project, program-level gate, or competing state machine. Reserve `/pm-promote` for Part-B tier fidelity. | E2.0 |
| 3 | **E2.2 — Read-only baseline integrity + `00c` inventory** | Separate repository identity, supplied checkout path, requested ref, resolved SHA, scan SHA, optional monorepo subpath, and dirty/non-reproducible status; strengthen `pm-context-scan-codebase` so the whole-repo inventory, coverage, exclusions and confidence populate `00c`; prevent silent baseline replacement; compare metadata↔`00c`↔current checkout in `/pm-check`. Do not create a parallel repository wiki. | E2.1 |
| 4 | **E2.3 — Slice/impact-cone scanner** | Adapt the reviewed marketplace patterns into `pm-context-scan-codebase`; inventory whole repo cheaply, then scan the affected slice and dependency cone; emit coverage/exclusions/confidence and affected surfaces; widen on evidence. All outputs stay in the PM-OS project. | E2.2 |
| 5 | **E2.4 — Decision interview + approved enhancement boundary** | Pathway-3 question selection, blocking/non-blocking unknowns, current→target behavior, affected/non-touch surfaces, invariants, compatibility/migration, success, rollout/rollback; write the binding enhancement boundary into stage-00 understanding. | E2.3 |
| 6 | **E2.5 — Scoped in-place stages 01–09** | Add conditional delta overlays and contracts across UI/API/data/service/event/integration/operations; update an established project's canonical artifacts only at affected stable IDs/sections while carrying unaffected content forward; make stage 04/05 surface-aware; use normal stage-level reapproval/staleness without per-requirement status; avoid forced screens/HTML for non-UI work. Honor Part-B tiers when present: promoted/deferred and net-new requirements remain in the same PRD. | E2.4 |
| 7 | **E2.6 — Regression, consistency, and handoff** | Baseline-behavior regression class, affected-surface↔requirement↔test↔task traces, delta-only package/Jira export, compatibility/migration/rollback checks, and status guidance. Compute delta and baseline references from the captured in-project before/after state, not a child-project backlink. | E2.5 |
| 8 | **E2.7 — Refresh, migration, and dogfood** | Explicit rebase/refresh with staleness cascade; schema migration/back-compat; full external-product and PM-OS-built-product runs; **two consecutive enhancements in one project** to prove baseline rollover, immutable prior provenance, and stable unaffected IDs; UI, API/data/service, cross-cutting, monorepo, drift, and read-only-permission fixtures; broad regression and isolated smoke. | E2.6 |

### Acceptance criteria (targets)

- [x] `/pm-new` scaffolds and routes a product's first PM-OS intake: it asks new/prototype/enhancement, sets the type for new/external-product enhancement, records the prototype route hint, and prints the correct next step (greenfield / context-import / context-import --codebase); non-interactively the `--entry`/`--codebase`/env escape preserves today's behavior. The chosen route is recorded in telemetry; established products do not call `/pm-new` again and their in-project continuation remains E2 work.
- [x] On a pathway-2 import where `preflight` rates a gap ⚠️/⛔, the interview asks **coverage-driven** questions — batched by topic, in **strictly decreasing order of impact**, only for load-bearing gaps the provided sources don't already answer (soft ~5 per round, no hard total); answering raises the affected backfill's fidelity/confidence; skipping records a known unknown and never fabricates.
- [x] Interview answers appear in `.sources.yaml` as a PM-authored source and feed the wiki/evidence ledger with high confidence.
- [x] Non-interactively (`--interview-answers <file>` or non-tty), the flow completes without hanging; skipped questions become known unknowns.
- [x] **Read-only guarantee:** a local target repo passes E2 with write permissions removed. PM-OS performs no target-repo file writes, checkout/ref/index/worktree changes, formatting, dependency installation, build output, or generated documentation; every scan/interview/artifact output lands in the PM-OS project. A URL uses read credentials to clone only into the PM-OS project.
- [x] **Marketplace safety/portability:** reviewed marketplace patterns are commit-pinned and license/security/write/network assessed; PM-OS ships owned portable helpers with no marketplace runtime dependency, so absence of those sources never blocks the gated path.
- [x] **`00c` owns repository inventory:** the scanner's lightweight whole-repo inventory, coverage, exclusions and confidence feed `00-codebase-understanding.md`; `00w` only cross-references relevant technical evidence and no parallel repository wiki/inventory artifact is created.
- [x] **Slice-first output:** the scanner derives an evidence-cited affected slice and impact cone from the `00c` inventory; generation/regeneration and handoff contain only new/modified/removed behavior plus required invariants/dependencies. Unaffected capabilities retain their stable IDs/content and never become new scope or tickets.
- [x] **Impact-cone safety:** shared dependencies, consumers, interfaces/events, data/schema, permissions, flags/config, tests, observability, deployment, and cross-package/service boundaries are considered. Dynamic/unavailable boundaries appear as coverage gaps; evidence of wider impact expands the slice visibly.
- [x] **External-product initialization:** a product never represented in PM-OS can create one product project from its codebase and optional docs without fabricating missing intent; every later enhancement reuses that project.
- [x] **Same-project continuation:** a PM-OS-native or previously imported product starts every subsequent enhancement inside its existing project. No child/sibling project or program-level gate is created; pre-change approved hashes and code ref are captured, canonical artifacts evolve through ordinary history/reapproval/staleness, and unaffected IDs/content remain stable.
- [x] **Identity/work separation:** starting a later enhancement does not change the established project's `project_type`. A persisted in-project enhancement context activates overlays and records ask/baseline/affected-surface provenance without defining approval/status; after completion it remains immutable evidence and the approved canonical stages are the new product-of-record.
- [x] **Part-B compatibility and promotion boundary:** E2 does not implement or overload `/pm-promote`; it preserves existing requirement/tier content when present and current default-MVP semantics when Part B is absent. The separate Part-B plan owns future `mvp | v1 | v2 | later` behavior.
- [ ] **Separate E0 follow-up — safe route correction:** changing a mistaken fresh-project intake route before stage 01 remains an E0 front-door operation, not `/pm-enhance` and not product promotion. It is deliberately outside this E2 branch; established products already use same-project continuation.
- [x] **Baseline integrity:** repository identity, requested ref, resolved SHA, scan start/end SHA, dirty/non-reproducible state, and optional monorepo subpath are recorded and bound to the cycle/`00c` evidence. Preparation cannot overwrite an approved baseline and make old evidence appear current; `/pm-check` detects frozen-baseline and checkout mismatch.
- [x] **Decision-focused interview:** pathway 3 asks only unresolved decisions — production baseline, why/change outcome, current→target behavior, affected/non-touch surfaces, regression invariants, success, compatibility/migration, rollout/rollback, and authority. Cited code facts are not re-asked.
- [x] **Unknown severity:** unresolved baseline identity, delta boundary, regression invariants, or required compatibility/migration are blocking unless the PM records an accepted risk; lower-impact skips remain visible known unknowns. No skip becomes a silent default.
- [x] **Multi-surface pipeline:** an enhancement may affect any combination of UI, API, data, service, event, integration, and operations. Stage 04/05 generate appropriate design/validation artifacts for those surfaces; non-UI work is never forced into fake screens or HTML, while existing `SCR-###` behavior remains backward-compatible for UI.
- [x] **End-to-end delta propagation:** stages 01–09 implement the enhancement behavior table in the modes plan. Every changed requirement is classed `new | modified | removed`, grounded in current→target behavior, and tied to affected surfaces or explicitly marked cross-cutting.
- [x] **Canonical-product integrity:** after approval, stages 01–09 still describe the current product definition, not a set of detached delta-only documents. Unaffected blocks are carried forward; the enhancement delta is a derived baseline-vs-current view used by checks and handoff.
- [x] **Regression and migration traceability:** every declared non-touch/regression invariant maps to explicit QA wording; every changed requirement maps to tests/tasks; compatibility/migration requires migration, rollout observability, and rollback coverage; `/pm-check` reports gaps.
- [x] **Delta-only handoff:** package/Jira outputs carry change type, affected-surface/blast-radius evidence, “must not break” regression coverage, compatibility/migration notes, and the captured in-project baseline reference. They export no unaffected baseline work.
- [x] **Refresh semantics:** checkout drift never silently changes the approved baseline. Explicit refresh records prior evidence, repins a clean checkout, invalidates the boundary, and causes ordinary staleness while preserving frozen artifacts.
- [x] **Compatibility and repeatability:** greenfield/prototype suites stay unchanged; projects without `.enhancements/` remain backward-compatible; a second enhancement uses the first enhancement's approved result as its baseline without losing earlier provenance; focused E2 and full regression gates pass.
- [x] No new stage status or parallel approval state machine: existing gate/hash/staleness/telemetry primitives remain authoritative; E2 may add validated inputs, mismatch checks, and ordinary downstream staleness cascades. Every stage-00 doc remains a human-approved gate; the interview never self-approves.
- [x] **(E3)** `/pm-interview` re-runs against the still-open known-unknowns only: `pm_interview.py list-unknowns` reads them, the answers register via the unchanged `record-interview`, and `pm_interview.py resolve` marks each answered gap `[resolved: <source> <date>]` **in place** (never deleted) with a `mode: rerun` `interview_conducted` event. Non-tty/`PM_OS_INTERVIEW=skip` leaves unknowns open; the skill never self-approves.
- [x] **(E3)** `/pm-status` surfaces `Known unknowns: N open` (resolved excluded, deduped by question) so the PM can see remaining gaps at a glance.

## 8. Open decisions (need PM input)

1. ~~**Build order — pathway 2 or 3 first?**~~ **DECIDED 2026-08-01: pathway 2 (prototype) first** — it's the case Karan is handing off to dev now; pathway 3 (codebase) comes later. E1 targets the pathway-2 (broad) interview; E2's pathway-3 tuning is deferred with it.
2. ~~**Interview home**~~ — **resolved:** pathway intake interview lives in `/pm-context-import`; E3 adds standalone `/pm-interview` for remaining known unknowns.
3. ~~**Pathway 3 shape**~~ — **resolved 2026-08-03:** lightweight repository inventory + affected-slice/impact-cone context + scoped delta through stages 01–09; do not reconstruct the full existing product. Widen only when dependency evidence/uncertainty requires it.
4. ~~**Entry-profile in meta**~~ **Resolved by the front-door model (§2b):** the routing prompt sets the type at `/pm-new`. `new`/`enhancement` map to `project_type`; the `prototype` choice is `new_product` under the hood, recorded as a lightweight route hint (telemetry + optional meta field) so status/segmentation can tell it apart.
5. ~~**Fold Phase 5**~~ — **resolved:** this plan supersedes `adaptive-context-intelligence-pack.md` Phase 5; there is one interview primitive with pathway-specific tuning.
6. ~~**Promotion meaning**~~ — **resolved 2026-08-03:** E2 initializes an external product once or continues an established product in its existing project; it does not promote a project. `/pm-promote` remains the separate Part-B command for moving an individual requirement between `mvp|v1|v2|later` fidelity bands inside the same PRD.
7. ~~**Product surfaces**~~ — **resolved 2026-08-03:** build E2 for UI, API, data, service, event, integration, and operations, including surface-aware 04/05 outputs. E2.0 decides the smallest backward-compatible non-UI traceability primitive.
8. ~~**PM-OS-native project lifetime**~~ — **resolved 2026-08-03:** subsequent enhancements remain in the product's existing PM-OS project. E2 uses captured baselines plus scoped in-place regeneration; no child enhancement project or `program.yaml` roll-up is part of this pathway.

## 9. Non-goals

- Rebuilding the abandoned tiers/increments `/pm-promote` implementation (that remains a separate delivery-model effort); design provenance may be reused selectively as stated above.
- Writing to or executing mutating workflows in the target product codebase. E2 reads it and writes only PM-OS project artifacts.
- Reconstructing the entire existing product when a bounded slice/impact cone is sufficient.
- Weakening a gate: the interview informs generation; it never approves, and every present stage-00 document remains human-approved.
- Interrogation: ask only load-bearing gaps the provided sources don't already answer, batched and skippable — never a fixed quota, and never converting a skipped question into a silent assumption.

---

End of plan.
