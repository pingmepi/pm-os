# PM-OS — Whole-Product PDLC Definition Layer: Design & Decision Plan

**Date:** 2026-07-30 · **Participants:** Karan (PM, Indegene) + Claude.
**Status:** 🟢 **DECIDED & SPLIT (2026-07-30).** This remains the **design rationale + decision log**. The implementable work now lives in three sibling plans:
- [`pm-os-foundation-plan.md`](pm-os-foundation-plan.md) — shared primitives.
- [`pm-os-new-product-plan.md`](pm-os-new-product-plan.md) — **build first**.
- [`pm-os-enhancement-plan.md`](pm-os-enhancement-plan.md) — build second.

**Decisions locked:** **A1** (tier-tag, one project), **B1** (gated phased roadmap), **C2** (tagged+attributed provenance), **D2** (SOW-grade stub + `/pm-promote`), **G1** (one tiered scope artifact; tiers are filterable tags), **H1** (phased roadmap authored early, after `02`, before `03`). **Build order: new-product first, enhancement second.** The pros/cons/tradeoffs below are preserved as the reasoning behind these choices.

**Relationship to other docs:**
- **Extends / partially subsumes** `pm-os-modes-delivery-and-handoff-plan.md` (Part B = scope tiers + `/pm-promote` + delivery increments; Part A = enhancement mode, already shipped). Where this doc says "Part B," it means that plan.
- **Extends** `../roadmap/product-shape-and-flexibility-brainstorm.md` (the product-shape / linear-chain-ceiling thread; §1 regulatory gaps; §2 the three PM paths; §5 graduation/backfill feasibility; §5.6 context overlay).
- Roadmap home: Phase 4 in `../roadmap/current-state-review.md` §7; backlog #28.

---

## 0. The through-line (read first)

PM-OS was founded as an **MVP-definition tool** (CLAUDE.md: "v1 covers product definition, MVP-first"). This plan repositions it as a **whole-product PDLC definition layer**, driven by two facts Karan surfaced:

1. **Usage is ~60/40:** ~60% of real work is **enhancing products PM-OS never built** (externally developed); ~40% is **new product development**. Enhancement is the *majority*, not an edge case.
2. **Users want the *whole product*, not the MVP.** Indegene's buyers (SOW/RFP, client sign-off, regulated) want the entire product defined and phased up front — "MVP-first" reads as *under*-delivery to them.

**Scope of this plan = option (a): whole-product definition, left-of-build.** Explicitly **out of scope for now:** code development, and the *right-of-build* lifecycle (QA execution, release, live feedback → Phases 4–6, unbuilt). Those may return later; today's target is "define and govern the whole product," for both the 60% and the 40%.

**The golden rule (inherited, non-negotiable):** grow the *traceability spine* and add *read-only composition on top*; **never** modify the per-stage state machine (gate, hash, status, staleness). Options that respect this are cheap and safe; the one that violates it (per-capability status) is the only one that can break the system.

**The unifying insight (§4):** a new-product **phase** and an **enhancement cycle** are the same object — *an increment of scoped work against a known product-of-record*. Modeling them as one mechanism (two entry points) collapses the two capabilities into one and is the single biggest simplification in this plan.

---

## 1. Where new vs. enhancement actually forks (subphase breakdown)

Breaking the pipeline into subphases and asking "does this stage fork by mode?" yields a clean result: **only two stages fork structurally; everything else converges or carries an additive overlay.**

| Stage | New product | Enhancement | Verdict |
|---|---|---|---|
| **00 context** | outward: market, problem, user research | inward: codebase scan → `00c` understanding | **converge** (already handled — enhancement adds conditional `00-understand`, Part A shipped) |
| **01 brief** | problem framing + success *hypothesis* | problem framing + expected *impact / why-now* on a validated product | **converge** (same template; one field shifts) |
| **02 scope** | **funnel:** research whole product → tier it → *select* MVP slice | **bound:** take the given ask → frame vs existing system → change boundary + explicit non-touch + blast radius | **★ FORK #1** |
| **03 PRD** | requirements for the MVP slice | + "changes to existing behavior" refs | inherit + overlay |
| **04 design** | design the slice fresh | design *against* existing IA (changed screens only) | inherit + overlay |
| **05 prototype** | prototype the slice | prototype the delta in existing context | inherit + overlay |
| **06 QA** | fresh acceptance tests | **+ regression suite** (existing must not break) | inherit + *additive class* |
| **07 metrics** | adoption / hypothesis metrics | **+ guardrail metrics** (don't regress existing KPIs) | inherit + *additive class* |
| **08 TRD** | build contract for *the system* | change-set: baseline → blast radius → integration/compat → migration/backfill → regression | **★ FORK #2** |
| **09 roadmap** | tiers beyond MVP (v1/v2/later) | follow-on enhancements | converge (share the tier axis) |

**Findings:**
- Everything **upstream of scope converges** (context + brief are shared).
- **Scope (02)** and **TRD (08)** are the only *structural* forks.
- Stages **03–07 don't fork** — they carry a single cross-cutting **"existing-system overlay"** (blast radius, changed-behavior refs, regression, guardrail metrics, migration) that is *additive sections gated on mode*, exactly the `genai_flag` pattern. Part B §5 already sketches "per-stage conditional blocks (enhancement mode)."
- **Two axes are in play, not one:** the **mode axis** (new vs enhancement — *how* scope is produced: funnel vs bound) and the **tier axis** (whole product vs MVP slice — *how much* now). They are orthogonal and share the same tier machinery.

---

## 2. Current-state baseline: what is built vs designed vs unbuilt

**Built (demoable today):**
- New-product definition pipeline `01 → 09` (brief, scope, PRD, design, prototype, QA, metrics, TRD, roadmap).
- QA plan (stage 06): `TC-###` test cases each citing PRD requirement ids; machine-readable `REQ↔TC` spine (`.traceability.yaml`, schema v5) with **coverage-gap detection**.
- Jira handoff (`/pm-handoff jira`): create route (Atlassian MCP) + `--offline` CSV; **writes ticket keys back into the spine** (requirement → test → ticket linked).
- Handoff package (`/pm-handoff --package`, audience-scoped `handoff/{dev,design,qa,business}/`; PR #53): each dev/qa **story file** = a PRD requirement joined to its `SCR-###` screens, `TC-###` QA scenarios, and `TSK-###` backend tasks. Keyed purely off ids that exist in both modes, so it produces a valid package for enhancement input — but the shape is **mode-blind** (no slot for enhancement-specific payload; see §3.3).
- Enhancement mode **Part A**: `--mode enhancement`, `--codebase <url|path>`, `project_type`/`codebase_path`/`codebase_ref` in `.meta.yaml` (schema v3), conditional `00c` codebase-understanding stage, codebase-drift signal in `pm_status`.
- Context overlay (`lib/context.py`) + `pm-context-import` (adopt/backfill/source-registration).

**Designed, unbuilt (Part B):**
- Scope tiers (`Tier: mvp|v1|v2|later` on `US-###`/`FR-###`, default `mvp`); stages 04–07 filter to `tier: mvp` by default.
- Tiered fidelity (MVP full spec; v1/v2/later = stubs) + `/pm-promote` to elevate a stub and pay the fidelity debt.
- Delivery increments (`INC-###`, ungated ledger layer).
- Per-stage enhancement conditional blocks (Part B §5, partial).

**New in this conversation (no design anywhere yet):**
- **Program/umbrella object** (product spanning multiple phases/cycles). *Keystone.*
- **Product baseline** (persistent product-of-record reconstructed for external products).
- **Portable questionnaire** round-trip (emit → peer fills offline → import).
- **Increment-against-a-record** unification (§4).
- **MVP scope cost-preview** on mid-stream changes.
- **Provenance primitive** (scanned / asserted / inferred, with attribution).
- **Compliance-posture capture** + metrics/feasibility seeding up front.
- **Enhancement handoff payload** — carry the enhancement overlay end-to-end to dev/QA through the export templates (§3.3).

**Known limitations that this plan bumps into:**
- No program/roll-up: `resolve_project()` walks to the nearest `.meta.yaml`; nothing groups projects — cycles/phases are islands.
- Whole-stage staleness (not per-requirement): a one-requirement scope tweak restales the *entire* downstream stage.
- Stage 09 roadmap is forbidden from generating requirements → "the whole product" cannot produce stories today; it lives as prose.
- Context overlay fires every global block into every stage unfiltered (no stage-affinity — brainstorm §5.6 #1).

---

## 3. The two capabilities

### 3.1 New product (40%) — roadmap-first, phased

Today the roadmap is stage **09**: last, prose, forbidden from producing requirements. Karan wants the phased plan **early** — after scope, *driving* the PRD series:

```
brief → scope the WHOLE product → PHASED PLAN (V1, V2, V3…)   ← roadmap, up front
                                        ↓ then, per phase:
                                   PRD → design → prototype → QA → metrics → TRD
```

This moves the full-product view from the *end* (roadmap 09) to the *front* (scope), which also fixes the sequencing critique in brainstorm §1 ("you picked the MVP without seeing the whole"; "metrics/feasibility land too late").

### 3.2 External enhancement (60%) — the product baseline

For a product PM-OS didn't define, there is **no brief/scope/PRD/TRD to reason against** — the core reason enhancement felt trickier. So the first move on any external product is not "run an enhancement," it is **build a product baseline** (a reconstructed product-of-record):

- **Scan** the code (WHAT) — extends `pm-context-scan-codebase` / `00c`.
- **Ingest** existing docs (partial WHY) — reuses `pm-context-import` backfill.
- **Interview** humans for the un-scannable parts (WHY, don't-break surface, dependents, compliance) — via the portable questionnaire (§6).

The baseline is **persistent and shared** across every enhancement cycle on that product, so it also fixes cycle-islanding for external products (the baseline *is* the umbrella/spine).

**The WHAT-vs-WHY split is the whole problem:**

| Axis | Recoverable by scanning? | Example |
|---|---|---|
| **WHAT exists** | ✅ yes (code + walkthrough) | features, data model, architecture — today's `00c` |
| **WHY it exists** | ❌ no — code records decisions, not reasoning | why SSO-only, why this data shape, what was rejected |

`00c` today captures WHAT from one source (code): *features & flows, architecture & modules, data model, tech stack, design language, integration points, known constraints*. It captures **zero WHY**, no change-intent, no don't-break map, no dependents, no compliance posture. That gap is what the questionnaire fills.

**Three scenarios by context availability (richest → poorest):**
1. **PM-OS-native product** — enhancement reads the prior cycle's approved brief/PRD/TRD (full WHY). *Minority; needs cycle-linking.*
2. **External + docs** — scan + doc ingest → partial WHY.
3. **External, code-only legacy** — scan gives WHAT, WHY is gone → **must** interview. *(The 10-year product; the hardest case.)*

### 3.3 The enhancement overlay's last mile — carrying it to dev/QA

The enhancement overlay (blast radius, changed-behavior refs, regression, migration) is *authored* in stages 02–08, but it only creates value if it **reaches the people who build and test** — i.e. it must survive the export layer, not stop at the TRD. Today it doesn't: the `--package` handoff (post-PR #53) is keyed off ids (`US`/`FR`/`TSK`/`TC`/`SCR`) that exist in both modes, so an enhancement produces a *valid* package — but the story/task shape is **mode-blind** and the enhancement-specific payload has nowhere to ride. Four payload pieces are genuine and must be carried end-to-end:

1. **`change_type: new | modified`** on each story/task — so a dev knows whether they are building greenfield or *modifying live behavior* (the single most important fact for an enhancement; the template has no field for it).
2. **A "Regression — must not break" section** — the existing behaviors to protect, sourced from the stage-06 regression class, distinct from the delta's own `TC-###`. (Today "regression" appears only as a rationale for *which audience* gets the impact doc, not as generated content.)
3. **Baseline-derived blast-radius / impact** — real impact analysis against the product-of-record, not a PRD-section passthrough (`impact-analysis.md` is currently just `_section_of(prd, "impact analysis")`).
4. **A baseline backlink** — story → `00c` / baseline, so a dev modifying existing code has a pointer to how the existing thing works.

**Shape:** additive to `templates/handoff-story.md.j2` + the delivery-map in `scripts/pm_share.py` — **no state-machine touch** (golden rule). This is the export-layer twin of the stages 03–07 overlay, and lands with Phase 2 (§8). **Evidence-gated:** whether these four bite is itself a pilot measurement — give the generated package to a dev/QA on the enhancement and watch for exactly "is this new or a change?" and "what must I not break?" Build the fields when the pilot earns them, not before.

---

## 4. The unification: "increment against a product-of-record"

A new-product **V2 phase** and an **enhancement cycle** are both *"a scoped increment of work against a known product-of-record."* The only difference is where the record comes from:

- **New product:** the record is the **approved MVP** (PM-OS authored it).
- **External enhancement:** the record is the **baseline** (reconstructed).

**Consequence:** model them as one mechanism — *increment against the current product-of-record* — and Capability 3.1 and 3.2 collapse into **one system with two entry points.** The program object just holds `{ product-of-record, ordered list of increments }`. This naturally lands as Model A (below) and is banked as the spine of the plan.

**Corollary — the baseline should be backfilled stage artifacts, not a new schema.** The scan backfills the *faithful* parts into existing stage artifacts (features→scope, architecture/data→TRD-of-record); the **questionnaire fills exactly what backfill can't** (design→PRD reconstruction is forbidden as lossy — brainstorm §5). One artifact model, not two — and it explains *why* the questionnaire must exist.

---

## 5. Decisions to lock before any code (the forks — with tradeoffs)

Building before these are settled guarantees rework. Each is presented as an open decision.

### Decision A — Phase model: tag vs sub-pipeline

| | **A1: phase = tier-*tag*** (Part B) | **A2: phase = own PRD→…→TRD sub-pipeline** under a program umbrella |
|---|---|---|
| Shape | one project; `Tier:` on requirements | N pipelines under one program |
| Pros | reuses tested mechanisms; low artifact count; one spine; matches the §4 unification | maps to how SOW-phased delivery is contracted/sold ("V1 SOW, V2 SOW"); clean per-phase approval/ownership |
| Cons | one big project can feel monolithic; per-phase approval is softer | **cross-phase staleness** (phase-1 PRD change → does phase-2 stale? PM-OS has no cross-project staleness); artifact × staleness explosion; needs the program object to be robust |
| Cost | low | high |

**Lean:** start **A1** (aligned with §4 unification); design the program object so **A2** is a later add for genuine SOW-phased cases. Do **not** build A2 speculatively.

### Decision B — Is the phased roadmap gated?

| | **B1: gated/hashed artifact** | **B2: ungated planning *ledger*** |
|---|---|---|
| Pros | consistent with other stages | survives V1 learnings without cascading staleness; matches Part B's argument for ungated delivery increments |
| Cons | every V1 learning re-stales the whole plan → **gate fatigue**; wrong question for a plan ("did this change, still valid?") | one more object outside the gate to reason about |

**Lean:** **B2 (ungated ledger).**

### Decision C — Baseline provenance

| | **C1: present reconstructed intent as fact** | **C2: tag each claim `scanned / asserted / inferred` + attribution** |
|---|---|---|
| Pros | simpler | prevents building enhancements on fabricated WHY (the "hollow shell" risk, brainstorm §5); supports multiple contributors owning different subsystems; feeds the shared provenance primitive |
| Cons | **enhancements build on fiction** — the single most dangerous failure mode | small authoring overhead |

**Lean:** **C2 — non-negotiable.**

### Decision D — Non-MVP / later-phase fidelity

| | **D1: full spec up front** | **D2: stubs + `/pm-promote`** (Part B) |
|---|---|---|
| Pros | complete picture immediately | doesn't balloon the PRD; doesn't specify design that doesn't exist; deferred rigor paid at promotion, honestly |
| Cons | over-specification waste; fossilizes unvalidated futures | full picture only emerges as you promote |

**Lean:** **D2 — the core over-specification guard.**

### Decision E — How far right-of-build (scope boundary)

Confirmed for now: **left-of-build only.** But the QA-lead meeting may argue for QA *execution* support. Keep this explicitly parked, not silently expanding. **Lean:** hold the line; revisit after the QA meeting.

---

## 6. MVP scope adjustability & the portable enhancement questionnaire

### 6.1 Adjusting MVP scope (Karan's requirement)

- **At the start** (tiers tagged, nothing downstream generated): increase/decrease MVP = re-tag requirements `mvp ⇄ v1/later`. **Free — no cascade.** This is `/pm-promote` + its inverse (demote).
- **Mid-stream** (downstream already generated): a scope change triggers the existing **staleness cascade** → downstream rewrites. Native behavior; keep it.
- **Add: a cost preview.** Before committing a mid-stream change, PM-OS reports "this restales stages 03–07 and N requirements regenerate." Read-only; respects the state machine; makes the rewrite a conscious choice.
- **Catch:** staleness is *whole-stage*, not per-requirement — one requirement moving in/out of MVP mid-stream rewrites the entire downstream stage. Fixing that = per-requirement change tracking, which touches the sacred state machine. **Recommendation:** do **not** build per-requirement staleness in v1; just surface the cost via the preview.

### 6.2 Portable questionnaire (enhancement PM ≠ base-product PM)

The enhancement PM often isn't the person who built the base product. So the WHY-capture step must be **externalizable** — mirroring the existing `/pm-handoff --offline` round-trip (emit → human fills externally → import):

1. PM-OS scans the code, identifies **the gaps the scan can't fill**, and **emits a targeted questionnaire** — only the open questions (keeps it short → fixes interview-friction).
2. The enhancement PM sends it to the **peer(s)** who built the base product. They fill answers **in the same structured doc**, offline.
3. PM-OS **imports the answered doc directly** as baseline context, tagged `human-asserted` with **attribution** (who answered what) — feeding the provenance model (Decision C).
4. **Section-routable:** different peers own different subsystems, so questions can route by area — PM-OS's first step toward the multi-author/stakeholder model brainstorm §1 flagged as missing.

Reuses `pm-context-import` ingest + the `--offline` round-trip pattern → not new plumbing from scratch. Must follow the non-interactive-safety convention (the peer is not in the session; document-based, non-tty).

---

## 7. Additional efficiencies & consistencies to fold in

- **Build the provenance primitive once.** Needed in three places — baseline (`scanned/asserted/inferred`), questionnaire answers (attributed to a peer), tier/phase decisions (recorded as provenance). One mechanism, three consumers.
- **Seed success metrics + a lightweight feasibility flag per phase up front.** We're already reworking the front of the pipeline; fixes "metrics and feasibility land too late" (brainstorm §1) at near-zero marginal cost.
- **Capture compliance posture as a first-class baseline field** (MLR, 21 CFR Part 11, HIPAA). Piggybacks on intake we're building; starts closing the Indegene-critical regulatory gap (brainstorm §1).
- **Context-overlay stage-affinity fix first (Phase 0).** Baseline + questionnaire + phase context will all flow into stages; the overlay currently fires everything into every stage unfiltered. Fix the filter *before* piling on, or every enhancement stage gets a token dump.
- **RTM as a by-product** (for the QA thread): the `REQ↔TC`(→ticket) spine *is* the skeleton of a Requirements Traceability Matrix — a mandatory regulated deliverable. Lead with this for QA/regulated stakeholders.

---

## 8. Build sequence (dependency-ordered)

**Phase 0 — Prereq hygiene (cheap, do first):**
- Context-overlay **stage-affinity** fix (brainstorm §5.6 #1).

**Phase 1 — The program primitive (keystone):**
- `program.yaml` referencing children + roll-up in `/pm-status`. **Read-only, advisory** — never a second source of gate/status truth (Risk #1). Reuse the `/pm-check` read-only pattern.
- Traceability spine: add `tier`/`phase` attributes (additive) — Part B B1.
- **Provenance primitive** (shared, §7).

**Phase 2 — External baseline + enhancement deltas (60% — the majority; sequence before the 40%):**
- Product baseline intake: extend `pm-context-scan-codebase` (WHAT) + doc-ingest + **portable questionnaire** (WHY), producing a persistent, provenance-tagged product-of-record (backfilled stage artifacts, §4 corollary).
- Enhancement conditional overlays in stages 02–08 (blast radius, changed-behavior refs, regression, guardrail metrics, migration) — additive sections.
- Regression QA class tied to baseline-captured behaviors.
- **Enhancement handoff payload (§3.3):** extend the export templates + delivery-map so each story/task carries `change_type: new|modified`, a **Regression — must not break** section, baseline-derived **blast-radius/impact**, and a **baseline backlink**. Additive to `templates/` + `scripts/pm_share.py`; no state-machine touch. Evidence-gated on the pilot.
- Baseline drift/refresh (extends the codebase-drift signal).

**Phase 3 — New-product whole-product (40%):**
- Whole-product tiered scope + phased-plan artifact placed early.
- Tiered fidelity + `/pm-promote` — Part B B2.
- (If Decision A → A2) per-phase sub-pipeline orchestration under the program.

**Phase 4 — Migrations & validation:**
- `schema_version` bumps + migration for existing on-disk projects (both `.meta.yaml` and frontmatter — two synchronized sources of truth).
- Extend `pytest` suite + `pm_os_verify`.
- `/pm-check` advisories for new hazards (tier inversion, cross-phase staleness, baseline drift).

**Order (DECIDED — new-product first):** although the risk/value argument favored enhancement-first (the 60%, zero existing design), Karan chose **new-product first** — a new-product demo drives near-term momentum and there is runway to build enhancement after. The authoritative, split build sequence now lives in the three sibling plans; the phases below are preserved as the source they were split from (Phase 0/1 → foundation, Phase 3 → new-product, Phase 2 → enhancement). Consequence for the split: new-product needs only Foundation **F1+F2** (not the program object), so the first build stays lean and needs **no schema migration**.

---

## 9. Catches & risks (consolidated)

1. **The program object is where you can actually break PM-OS.** So much assumes single-project that an *authoritative* program layer forks the sacred state machine. Mitigation: read-only view over child `.meta.yaml`s; never a second source of truth.
2. **Cross-phase staleness (Decision A2).** No cross-project staleness exists today; A2 introduces the hazard. Strong reason to start A1.
3. **Fabricated WHY in the baseline.** Scan = confident WHAT; intent = lossy human input. Presenting reconstructed rationale as authoritative → enhancements build on fiction. Mitigation: Decision C2 + mandatory interview step.
4. **Regression is only as good as the baseline.** Can't generate "existing behavior must still hold" tests from prose "current features" — the baseline must capture behaviors as *testable assertions*, or enhancement QA is theater.
5. **Baseline goes stale.** The external product evolves under other teams; full re-scan each cycle is expensive. Need drift-aware incremental refresh.
6. **Prompt-branch explosion.** `mode=enhancement` × `genai_flag` → up to 4 combos per stage; prompts lengthen, two sources of truth harder to keep in lockstep. Mitigation: overlays as append-only sections, never rewrites.
7. **Install/update discipline.** Ships only via commit→push→`pm_os_update.py` with migrations for live projects. Broad change → staged, migration-safe rollout; no hand-modifying installs.

---

## 10. Where inefficiency creeps in

- **Over-specification:** full-fidelity V2/V3 up front → balloons PRD, specs non-existent design. Guard: stubs + promote (D2).
- **Context bloat:** baseline + phase + overlay compounding on the unfiltered overlay. Guard: Phase 0 stage-affinity fix first.
- **Redundant re-scans:** re-deriving the baseline cold each cycle. Guard: persistent baseline + incremental refresh.
- **Artifact/staleness explosion (A2):** N phases × 8 stages. Guard: start A1.
- **Interview friction:** heavy WHY-capture → PMs skip it → WHAT-only baselines → Risks #3/#4 bite. Guard: scan-driven *gap-only* questionnaire, short and provenance-visible so skipping is a visible gap.

---

## 11. Open decisions summary (what blocks the start)

| # | Decision | Options | **Decided** |
|---|---|---|---|
| A | Phase model | tag (A1) vs sub-pipeline (A2) | ✅ **A1** (A2 deferred for genuine SOW-phased cases) |
| B | Roadmap gated? | gated (B1) vs ledger (B2) | ✅ **B1** — gated stage; fits SOW auditability |
| C | Baseline provenance | fact (C1) vs tagged (C2) | ✅ **C2** |
| D | Non-MVP fidelity | full (D1) vs stubs (D2) | ✅ **D2** — SOW-grade stub (richer than Part B's minimal stub) |
| G | Scope artifact shape | one tiered (G1) vs scope-out+select (G2) | ✅ **G1** — tiers are filterable tags; adjust = re-tag |
| H | Phased-plan placement | early after 02 (H1) vs stage 09 (H2) | ✅ **H1** — new gated stage `02r`, before `03` |
| E | Right-of-build scope | hold vs expand | 🟠 **hold** — still parked pending the QA-lead meeting |

---

## Appendix — Stakeholder inputs that will resolve the open decisions

Three meetings (2026-07-30) map onto the three hardest unknowns; their answers feed the decisions above. All framed as **learn + scope a pilot**, not sell. Product names for the Indegene "Next Collaborator" line are placeholders pending Karan's confirmation.

**QA Lead — "how can PM-OS support QA?"** (→ Decision E, Risk #4)
- Lead with what's real: traceable QA plan (06) + `REQ↔TC`(→ticket) spine + coverage-gap detection = **RTM by-product** (mandatory regulated deliverable). Be upfront PM-OS does not execute tests / triage / gate releases.
- Ask: where is QA's pain (planning / execution / regression scoping / traceability / triage)? How is the RTM produced today? How is regression scope decided for enhancements? Which tools (Jira/Zephyr/Xray/qTest)? Would a PM-authored traceable plan in their tool reduce work, or do they need execution?

**NTG Product Owner — enhance primary product + research next-gen ("Next Collaborator").** (→ live pilot; tests Decisions A/D and the baseline)
- This stakeholder embodies the 60/40 in one. Recommend piloting the **next-gen research track first** (greenfield, low-risk, demoable today; needs no codebase access).
- Ask: which track is the real urgency? Appetite to scope the *whole* next-gen tiered (V1/V2)? For enhancement — codebase access + a named peer for the questionnaire + doc state? What is "experiment succeeded"? What's broken in their current definition process?

**10-year internal product (also client-sold) — enhancement.** (→ pure requirements-gathering for the baseline; the extreme legacy case, Scenario 3)
- Frame as design partnership; the baseline capability is designed, not built. Value prop: extract trapped institutional knowledge **once**, run every future enhancement against it.
- Ask: codebase size/language/monorepo (scannable?); doc state; **are original authors around / who to route the questionnaire to?**; enhancement cadence; **per-client variants/forks?** (multi-tenancy complicates the baseline); current enhancement pain (regression fear / knowledge loss / onboarding)?

**Cross-cutting takeaways to secure:** validate (or kill) the **baseline + portable questionnaire** (60% case, zero existing design — meetings 2 & 3 both test it); recruit the NTG PO and the 10-year-product team as design partners; demo only the greenfield pipeline (not enhancement/tiering/baseline — unbuilt).

---

## Grounding references

- `lib/project.py` — `STAGE_ORDER`, `STAGE_DEPENDENCIES`, `upstream_stage_ids()`, `resolve_project()`, backfill maps.
- `hooks/pre-stage.py` — the gate (blocks on `pending/draft/stale`).
- `lib/traceability.py` / `.traceability.yaml` — `REQ↔TC` spine (schema v5), coverage gaps, `tickets:` slots — the safe extension point.
- `skills/pm-stage-02-scope`, `skills/pm-stage-06-qa-plan`, `skills/pm-stage-08-trd` — the fork stages + QA/RTM story.
- `skills/pm-context-scan-codebase` / `00c`, `scripts/pm_context_import.py` — inbound brownfield understanding + adopt/backfill (the baseline's building blocks).
- `scripts/pm_handoff.py` — Jira export + ticket-key writeback (the `--offline` round-trip pattern the questionnaire reuses).
- `scripts/pm_share.py` / `templates/handoff-story.md.j2` — the `--package` handoff shape (story = requirement + screens + QA + backend tasks); mode-blind today, the last-mile target for the enhancement payload (§3.3).
- `lib/context.py` — context overlay (stage-affinity gap, §5.6 #1).
- `pm-os-modes-delivery-and-handoff-plan.md` — Part A (enhancement mode, shipped) + Part B (tiers, `/pm-promote`, increments — designed, unbuilt).
- `../roadmap/product-shape-and-flexibility-brainstorm.md` — linear-chain ceiling, three PM paths (§2), graduation/backfill feasibility (§5), regulatory gaps (§1).
