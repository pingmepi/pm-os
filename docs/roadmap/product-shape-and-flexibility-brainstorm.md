# PM-OS — Product Shape & Flexibility: Brainstorm Notes

**Date:** 2026-07-06 · **Status:** OPEN DISCUSSION — not a decision, not a committed plan.
**Participants:** Karan (PM, Indegene) + Claude. Prompted by a conversation with another PM about working styles.
**Standing caveat:** Karan is **not yet convinced** of any direction here. This is a captured thinking thread, deliberately preserving open tensions rather than resolving them.

---

## 0. The through-line (read this first)

Almost every finding in this thread traces to one structural fact:

> **PM-OS models one product as one *linear artifact chain* — exactly one artifact per stage, one status per stage, one approval per stage.** This is simultaneously its greatest strength (standardization, gated rigor, traceability) and its ceiling (real product work is multi-shaped and multi-module).

And one **golden rule** recurred as the safe way to grow past the ceiling every single time:

> **Classify at intake → default to the native shape → add composition/orchestration *on top* → keep the per-stage state machine (gate, hash, status, staleness) sacred and untouched.**

Options that respect this rule are cheap and safe (they reuse tested mechanisms). The one option that violated it — rewriting the state machine for per-capability status — is the only one that can actually break the system, and was rejected each time it appeared.

A second recurring lens:

> **Product decomposition ≠ implementation decomposition.** "Platform of products" is a *definition-layer* question (how many gated pipelines). "Orchestrator of agents" is an *architecture-layer* question (stage 04 design + stage 08 TRD). Conflating them is how you make product-structure decisions on technical vibes (or vice versa).

---

## 1. Where PM-OS sits in a real PDLC (definition vs execution)

PM-OS covers the **entire left-of-build definition** of a V1 — not just "prototyping for an MVP":
`01 brief → 02 scope → 03 PRD → 04 design → 05 prototype → 06 QA plan → 07 metrics plan → 08 TRD → 09 roadmap`.

- The `05` prototype is an **HTML mockup**, not functional software. PM-OS never produces working code at any stage.
- Everything **right of the build boundary** — dev tracking, QA *execution*, release, live monitoring/feedback — is roadmap-planned (Phases 4–6) but unbuilt.
- Verdict: usable **today** to fully *define and govern* a V1; silent on *driving* build/QA/release. Once a team starts building, PM-OS becomes a static reference.

**Indegene-specific gaps flagged (not on the current roadmap):**
- **No regulatory/compliance gate** — MLR (Medical/Legal/Regulatory), 21 CFR Part 11 / GxP / CSV (GAMP 5) validation, HIPAA/GDPR privacy impact, WCAG accessibility. For a life-sciences org these are arguably *mandatory* gates, not optional.
- **No client/stakeholder model** — intake assumes a single internal PM with a one-line idea, not an SOW/RFP + multi-party sign-off (eng, design, legal/regulatory, *client*). The tech-lead review itself flags "no auth model."
- Ordering nits: **success metrics land too late** (should be seeded in brief/PRD, elaborated at 07); **technical feasibility lands too late** (TRD at 08 risks discovering infeasibility after scope is committed).

Bonus insight: a handoff packet + traceability spine extended through tickets/tests **is a Requirements Traceability Matrix** — a mandatory regulated-industry deliverable. That's a stronger justification for building the dev-handoff bridge than "nicer docs."

---

## 2. Working-style flexibility — the three PM "paths"

A PM described three working styles. Where PM-OS stands (verified in code):

| Path | Command today | Standing |
|---|---|---|
| **1. Discovery → features** (linear) | `/pm-new <slug> "<statement>"` → 01…09 | ✅ Fully supported — the happy path |
| **2. Existing product** (brownfield) | `/pm-new --mode enhancement --codebase <url>` → `/pm-context-import` | ✅ Fully supported — read-only scan → gated `00c` codebase-understanding; downstream reframes as the *delta* |
| **3. Skip to prototype** | `/pm-context-import` (adopt + backfill) | ⚠️ **Not really — by design** |

**The invariant that decides path 3** (stated verbatim in the ingest plan): *"the gate is never weakened — gaps below where you start are backfilled, not skipped."* The gate (`hooks/pre-stage.py:176`) blocks any stage while any upstream is `pending/draft/stale`. There is **no `--skip`, no `--stop-after`, no not-applicable** for core stages 01–07 (only 08/09 are omittable). Backfill is a substitute for *generation*, not for *approval* — every backfilled stage must still be approved, and design-only→PRD backfill is **hard-blocked** (`BACKFILL_FAITHFUL_FROM["03"] = []`).

**Options brainstormed for accommodating "skip to prototype":**
- **A — Declared path templates.** PM picks a track (e.g. prototype-only = 01→03→04→05); gates enforce fully *within the chosen shape*. Standardization becomes "standard shapes." Architecture already ~90% supports this (`upstream_stage_ids()` filters to present stages).
- **B — Lower-friction backfill.** Keep the full chain; make backfill+approval fast (bulk-approve). Invariant untouched; but doesn't give a genuinely shorter shape.
- **C — True skip / not-applicable.** Mark core stages N/A, bypass gates. **Rejected** — this deletes the tool's reason to exist; breaks generation (stage prompts assume upstream exists) and the traceability spine.
- **D — Sanctioned exploration lane (sidecar).** `/pm-explore-prototype` generates a mockup from whatever's approved (even just a brief), written *outside* the gated chain, flagged non-canonical, later *promotable*. Reuses `pm-prototype-html`. Best fit for the real motive ("think by prototyping").

**Leaning (not decided):** **D + A**, with **B** as polish, and **not C**. D resolves the values tension instead of trading it off; A handles legitimately-shorter deliverables. All three respect the golden rule; C violates it.

---

## 3. Multi-capability products (the 4-accelerator case)

Scenario: one product with 4 accelerators — **content, translation, analysis, collateral-generation**.

**Verified finding:** PM-OS has **no first-class notion** of module / component / capability / epic / workstream anywhere. One project = one linear chain, one artifact per stage, flat requirement list (`FR-###`/`US-###`), whole-stage status, prose roadmap, **no program/multi-project roll-up** (`resolve_project()` walks to the nearest `.meta.yaml`; nothing groups projects). Today the 4 accelerators can only be represented as **sections inside single monolithic artifacts**.

**Key reframe:** the 4 accelerators are a **value chain** (content → translation → analysis → collateral), sharing a platform and feeding each other — so neither "one big blob" nor "four separate products" is right. The real object is **a platform with four semi-independent, interoperating capabilities**.

**Also key:** "platform of products" (product decomposition, definition layer) vs "orchestrator of agents" (architecture, stage 04/08) are *different questions at different layers*. You can have one product (platform), defined as one project, whose TRD describes an orchestrator of four agents.

**Decision heuristic** for the *product* decomposition (the only one that changes how you use PM-OS) — mostly "together" → one project; mostly "independent" → program of projects:
1. Release — ship/version together or separately?
2. Approval/ownership — one sign-off & owner, or distinct?
3. Users/data — shared or genuinely separate?
4. Standalone value — meaningful used/sold alone?
5. Lifecycle drift — different stages at the same time?

**Default bias: start as ONE product unless ≥2 signals scream independence.** For these 4: shared users, shared data, a value chain = mostly "together" → **one product**, with the agent-orchestrator design living in the TRD.

**Three models to represent them:**
| Model | How | Works today? | Cost | Loses |
|---|---|---|---|---|
| **1. One project, tagged** | accelerators as sections + `FR-CONTENT-001` namespacing + explicit "shared platform" & "integration" sections | ✅ zero code | discipline | independent maturity/approval; monolithic staleness |
| **2. Four projects + program** | each = own pipeline + a "platform" project; hand-rolled roll-up | ⚠️ mechanically yes, no program layer | manual coordination | cross-accelerator deps, shared context, roll-up |
| **3. First-class module/program layer** | per-capability sub-artifacts + per-capability status + program manifest | ❌ must be built | high — touches core state machine | nothing (the "right" model) |

**What to build to simplify without breaking:** a lightweight **intake/decomposition classifier** (extend `/pm-new` intake or `/pm-classify`) that asks the 5 questions, **defaults to one project**, records the decision as provenance; plus **composition as a read-only on-top layer** (a thin `program.yaml` referencing child projects + roll-up in `/pm-status`). Defer Model 3. Every recommendation maps onto already-tested mechanisms; the only new code is advisory + read-only. (This is exactly the "PM-led recommendation layer" the roadmap already calls for, §5.2.)

---

## 4. Value-chain modeling — the missing primitive is *edges*, not modules

For a value-chain product, the differentiated value ("the moat") lives in the **seams** — content born translation-ready, analysis feeding back into content, collateral auto-assembled from all three. If the seams aren't specified, you've defined four point tools, not a platform. Seams are what separate *prototype-grade* from *product-grade* definition.

PM-OS models requirements as **flat nodes** with exactly one edge type in the whole system: `REQ ↔ TC` (`.traceability.yaml`). There is **no `REQ→REQ` or capability→capability edge**. Four things the seams need that PM-OS doesn't structure:
1. **Dependency edges** — "collateral-gen consumes content + translation + analysis."
2. **Interface contracts** — data shape crossing each seam + failure behavior (translation fails → collateral blocks/degrades/skips?).
3. **Integration QA** — cross-capability failure scenarios (currently indistinguishable from unit tests).
4. **Dependency-driven sequencing** — the chain dictates release order, but roadmap (09) is prose disconnected from requirements.

**Do today (convention, zero code):** a "Capability Map & Interfaces" section in PRD + design; interface IDs (`IF-CONTENT→TRANS-001`) referenced from requirements on both sides; integration QA class (`TC-INT-###`) tied to `IF-` IDs; roadmap horizons ordered by the dependency edges.

**Worth building (safe):** grow the **traceability spine** with typed `REQ→REQ` / capability edges and `IF-` interface nodes — **purely additive to the link graph, never touches the state machine** (respects the golden rule). Then roadmap phasing can be *derived* from the dependency graph. Product interface lives in PRD/design; technical contract in TRD; **same `IF-` ID**, different layer.

---

## 5. The graduation / promotion problem

The hard case for "start light" flexibility: a PM explores a prototype, then wants to grow it into a full product.

**Why it's hard — it's an *information* problem, not plumbing.** Information flows downstream and gets more concrete; each stage *adds* info the previous lacked. Backfill can only recover upstream when the downstream artifact holds that info implicitly — hence the feasibility map: PRD→brief = faithful; design→PRD = lossy; prototype→PRD = **infeasible**. A prototype embodies decisions but records *no reasoning*, so "reconstruct a PRD from a prototype" = hollow shell or fabrication. **You can't recover abstract intent that was never authored.**

**The tractable split:**
- **Downstream graduation** (prototype-only track → add QA/metrics/TRD/roadmap): **trivial, native** — extending the chain forward from an approved PRD/design. No missing info.
- **Upstream graduation** (prototype → author the brief/scope/PRD *under* it): **the hard one** — the infeasible case.

**The reframe that resolves it: graduation ≠ backfill.** Don't *recover* the upstream from the prototype — **author it now, forward, with the exploration as a running start.** Run the normal pipeline (brief→scope→PRD→design), generating each stage fresh with full rigor (NFRs, acceptance criteria, priorities supplied *now*), injecting the prototype as strong context; PM approves each gate normally. The prototype *informs* generation; it never masquerades as reconstructed upstream — so the feasibility wall is never hit.

**Enabling move — capture intent *during* exploration.** The exploration lane should emit a **decision/assumption log** alongside the mockup ("chose tabs because…", "assuming SSO", "offline out of scope"). Then promotion is *structuring captured intent*, not reverse-engineering pixels. The fix is about *when* you capture, not *whether* you can reconstruct.

**Quality trap:** fossilizing sketch accidents as requirements (prototype used a dropdown → PRD mandates a dropdown). The decision log is what separates *decided* from *incidental*. Without it, graduation hardens throwaway choices into spec.

**Honesty principles:** (1) frictionless graduation is a *bug* — graduation is where deferred rigor gets paid; auto-deriving NFRs just rubber-stamps a skip. (2) Some explorations should **die, not graduate** — disposability is part of the exploration lane's value.

**Safe design sketch:** exploration lane → `explore/mockup.html` + `explore/decisions.md` (non-canonical, ungated). `/pm-graduate` scaffolds deferred upstream as normal `pending` stages, registers the mockup + log as a *source* (reusing `pm_context_import` source registration), runs the normal forward gate. **Never invokes the backfill feasibility map; never touches gate/hash/status.** Only new code: decision-log capture + `/pm-graduate` orchestration — both additive.

**Bottom line:** graduation can be made cheap and honest, but **never free** — you always pay the deferred rigor eventually.

---

## 5.5 Design surface, Figma & the design system

Prompted by: where does Figma fit, and how do design spec / Figma screens / HTML prototype / Figma prototype avoid becoming four unsynced sources of truth? Same spine as everything else — **don't sync N things, derive N−1 from one source of truth.**

**The four artifacts collapse to two.** "Screens" and "prototype" are not separate artifacts — they are two *features of one surface* (Figma gives both; an HTML file gives both). So the real objects are: **the design spec (`04`) = design *intent* (source of truth)** + **one *surface* (derived)**. You never need four.

**`04` vs `05`, precisely (verified in the skills):**
- **`04` = the complete design contract.** Every screen, flow, component, token, a11y note; maps *every* PRD `UJ-###`. Source of truth for design.
- **`05` = a validation *plan* over a deliberate slice + the emitted artifact.** "Smallest useful prototype slice"; names only the slice's `UJ-###`. Contains **no new design** — it points at `04` as the source of truth. Its unique content is *research methodology* (participants, tasks, thresholds, bias controls) + participant/reviewer modes, and it auto-emits `05-prototype-mockup.html`.
- So **`05` bundles two different concerns**: (a) a *validation plan* (research; renderer-agnostic; closer to the QA/metrics family) and (b) *prototype production* (pick slice + fidelity, emit the surface — hard-wired to HTML today). **That fusion — not the `04`/`05` split, which is sound — is the seam worth questioning** for cleaner separation (`05a` surface / `05b` validation plan).
- Consequence: **`04` covers all journeys; the HTML prototype covers only a slice.** Want the *complete* screen set as a deliverable → generate from `04`. Want *cheap interactive validation* → the `05` HTML slice. Different scopes, by design.

**Division of labour (confirmed against Figma MCP capabilities):**
| Job | Tool | Status |
|---|---|---|
| Complete, DS-accurate **screens** | Figma MCP from **`04`** | ✅ generation + design-system resolution both supported |
| Cheap **interactive validation** (a slice) | **HTML** from **`05`** | ✅ already auto-wired |
| **Clickable Figma** prototype | **human** wires it natively in Figma | ⚠️ MCP can't — open feature request (Feb 2026) |

**Figma MCP is a screen generator + design-system resolver, not a prototyper** (sourced, July 2026): `use_figma` / `generate_figma_design` generate/capture screens; `search_design_system` / `get_libraries` / `get_variable_defs` resolve a real company library; but the MCP **cannot read or wire prototype interactions** (open feature request; current workaround = manual button annotations). Figma Make is the separate AI-prototyping surface the MCP mostly *reads*. So interactivity = the HTML prototype (already have it) or a human in Figma.

**Ownership boundary (the anti-drift rule):** `04` owns *intent / behavior / flows*; the surface owns *visuals / pixels*. Spec change → regenerate/refresh the surface (staleness handles it). Visual tweak → stays in the surface. **Behavior changed directly in Figma → must round-trip into `04`**, or it's silent drift. Figma generation is *seed-then-diverge*, not keep-in-sync; the spec→Figma link is a soft advisory trace (reference `UJ-###`), never a hard hash — don't over-promise prose↔pixel sync.

**Design system = context, not per-project output.** A standardized company DS is stable across every product, so it belongs in the **context overlay** (the rulebook + pointer) with the company **Figma library** as the asset source of truth. When a DS exists, **`04` shifts from token-*author* to token-*consumer*** — it references system components/tokens and specifies only composition + net-new/deviations. Figma MCP then resolves those references to the real library components. Same reference-don't-duplicate rule — and it *simplifies* `04`.

**Current state (verified):** PM-OS has **no first-class design-system reference.** `04` authors tokens from scratch (`lib/artifact_contracts.py` requires "Color Tokens", "Spacing Tokens", "Component Inventory" as things to *define*). The only DS awareness is *inbound* brownfield scanning (`skills/pm-context-scan-codebase` → `00c`). The context overlay is the only injection point today, and it's **unstructured prose — advisory, no component IDs, no library resolution.** A real reference convention (component/token IDs the overlay defines and Figma MCP resolves) is **net-new plumbing** that the whole Figma workflow depends on.

---

## 5.6 Context overlay review

Review of `lib/context.py` + `context.example/` — how the pluggable company/team/stage knowledge layer works, whether it's efficient, and what to change.

**How it works.** A manifest (`context.yaml`) declares `global` files (`company/team/glossary/guardrails`) applied to *every* stage, plus per-stage `format` + `examples` + an `apply` mode (`augment` default / `override` / `reference-only`). Layering (`resolve_context`, `lib/context.py:101`): project `<project>/context/` overrides the base install, merged *on top* (globals union, stage fields project-wins). A strong **no-op guarantee**: `_clean` strips comment/guidance scaffolding, `_has_substance` drops heading-only files, and a **seed-equality check** (`context.py:94`) drops any file still identical to the pristine seed — so an all-TODO pack injects nothing. Injected once per stage via a bash one-liner (`render_context`) the agent reads as authoritative background.

**Efficiency — three lenses:**
- **Compute/IO — fine.** Runs once per stage over a few small files; only waste is re-reading + re-cleaning the seed on every `_read_overlay_file` call (`context.py:94-96`) — negligible. Don't optimize.
- **Token/relevance — the real gap.** Every global block goes into **every stage, unfiltered** — no stage-affinity/relevance selection. Notable because the sibling `00-context` wiki/adaptive pack *did* get `stage_affinities` in schema v4; **the overlay never did.** The two context systems are inconsistent, and the overlay is the blunt one. Full example artifacts injected "for tone" on every generation compound the cost.
- **Maintainability — two latent bugs.**
  1. **Seed-drift leak (low-med):** "unfilled" is inferred by equality to the *current* seed (`context.py:94`), but `seed_context` is copy-*if-missing* and never overwrites. When a release changes a seed file, an unfilled file keeps the **old** seed → no longer matches the new one → **stale never-filled scaffolding leaks into every prompt as real content.** Bites exactly the substantive-scaffolding files the check was added for (e.g. the glossary rows). Root cause: unfilled-ness defined by content-equality to a moving target.
  2. **Blockquote stripping (low):** `_clean` removes *all* `>` lines (`context.py:35`) — deletes legitimate PM blockquotes, including the `> **PM:**` annotation convention the wiki treats as highest-priority override. Inconsistent with the wiki.

**Changes — prioritized:**
1. **Stage-affinity for globals** (biggest efficiency win) — let a `global` entry declare `stages: [...]`, default all. Aligns overlay with the adaptive pack; cuts per-stage token noise. Additive schema change.
2. **Fix the seed-drift leak with an explicit marker** — replace "unfilled = equals current seed" with a sentinel the PM removes when filling (`<!-- pm-os:unfilled -->` or manifest `filled: false`). Robust to seed evolution.
3. **Blockquote-safe `_clean`** — strip only the leading guidance block, not every `>` line, so PMs can use quotes + the `> **PM:**` convention.
4. **(Architecture) Coordinate overlay vs `00-context` wiki/pack** — two independent injections can double-inject company facts. Boundary: overlay = stable cross-project company/team/**design-system** knowledge; wiki = per-project sourced context. This is also where the **structured design-system pack** from §5.5 (component/token IDs) would live.
5. **(Nice-to-have)** a `pm-context` diagnostic that renders what each stage receives (active blocks + rough token count) so the overlay is visible/budgetable; `lru_cache` the seed compare.

**Verdict.** For a local, occasionally-run, single-PM tool it's **functionally efficient and unusually well-designed** on the no-op guarantee and layering. The genuine gaps are **relevance, not compute** (globals fire into every stage unfiltered — the overlay never got the adaptive treatment the wiki did) plus two cheap-to-fix latent bugs. If you do one thing: **#1 (stage-affinity)**; two: add **#2 (drift fix)**.

---

## 6. Recurring principles distilled

1. **Keep the state machine sacred.** Gate/hash/status/staleness is load-bearing. Grow *around* it (advisory + read-only composition), never *into* it.
2. **Product decomposition ≠ implementation decomposition.** Definition layer vs architecture layer (TRD). Don't let one drive the other.
3. **Start native, split when forced.** Default to one linear project; split into templates/programs only when a concrete pain (divergent release, independent approval, distinct owners) proves the seam.
4. **Grow the traceability spine, not the state machine.** Edges, interfaces, program roll-ups are all additive link-graph extensions — safe.
5. **Stable-ID discipline is the connective tissue.** REQ/TC today; IF-/capability edges are the natural next IDs.

---

## 7. Unresolved / points of skepticism (Karan not convinced)

Deliberately left open:
- Is the exploration-lane + graduation machinery **worth the complexity**, or does it just re-introduce, in a side door, the rigor-skipping the gate exists to prevent?
- Does a program/manifest layer make PM-OS a **portfolio tool it was never meant to be** — scope creep away from "one PM, one product, local-first"?
- For Indegene specifically: is the higher-priority gap actually the **regulatory/compliance gate + multi-approver model** (§1), which no option here addresses, rather than shape flexibility at all?
- Where's the line between "product interface (PRD)" and "technical contract (TRD)" in practice — will PMs actually keep them separate, or will `IF-` IDs blur the layers?
- Is any of this needed *now*, or is single-project Model 1 + convention genuinely sufficient until a real multi-accelerator product forces the issue?
- Design-system reference is **net-new plumbing** (no first-class support today) — is overlay-as-prose enough, or is a component/token-ID convention worth building? And is splitting `05` into surface + validation-plan worth it while the pipeline is still pre-build?

---

## 8. Not decided / possible next steps (none committed)

- Detail the **intake classifier + `program.yaml`** as a concrete, buildable design.
- Prototype the **edge-aware `.traceability.yaml`** + derived roadmap sequencing.
- Spec the **exploration lane + `/pm-graduate`** flow end to end.
- Step back and weigh **regulatory gate / multi-approver** against all of the above for Indegene priority.
- Sketch a **design-system reference convention in `04`** (component/token IDs the overlay defines and Figma MCP resolves) — the plumbing the Figma workflow depends on — and consider splitting `05` into **surface** (HTML|Figma renderer) + **validation plan**.
- **Context overlay** (§5.6): add stage-affinity to globals (#1), fix the seed-drift leak (#2), make `_clean` blockquote-safe (#3); later, coordinate overlay vs `00-context` pack and host the design-system pack there.

## 9. Grounding references (anchors for re-entry)

- `lib/project.py` — `STAGE_ORDER`, `STAGE_DEPENDENCIES`, `upstream_stage_ids()`, `resolve_backfill`, `BACKFILL_FAITHFUL_FROM`/`BACKFILL_LOSSY_FROM`, `resolve_project()`.
- `hooks/pre-stage.py` — the gate condition (blocks on `pending/draft/stale`).
- `lib/artifact_contracts.py` — flat requirement IDs; no grouping dimension.
- `lib/traceability.py` / `.traceability.yaml` — REQ↔TC link graph (the safe extension point).
- `lib/context.py` — context overlay (per-project only; no cross-project inheritance). `context.example/` (global guardrails + per-stage packs) is the only lever to inject a company design system today — as prose.
- `scripts/pm_context_import.py` + `skills/pm-context-import/` — adopt/backfill/source-registration.
- `skills/pm-stage-04-design-spec` vs `skills/pm-stage-05-prototype-brief` — complete design contract (all `UJ-###`) vs deliberate validation slice; `04` authors tokens (no DS reference). `skills/pm-prototype-html` renders only the brief's slice into HTML. `skills/pm-context-scan-codebase` — the only (inbound, brownfield) design-system awareness.
- Figma MCP (external): Dev Mode server is design-to-code + design-system resolution; prototype-interaction read/wiring is unsupported (open Figma Forum feature request, Feb 2026). Figma Make is the separate AI-prototyping surface.
- `docs/roadmap/current-state-review.md` — the canonical roadmap (Phases 0–6); this brainstorm extends its §3/§5/§7.
