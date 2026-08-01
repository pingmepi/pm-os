# PM-OS Entry Pathways & Interview Plan

**Status:** 🟡 Draft plan (2026-08-01). Design only — no code. **Build order decided 2026-08-01: pathway 2 (prototype → dev handoff) first; pathway 3 (codebase) later.** Remaining open decisions in §8.
**Author:** Karan (with Claude Code)
**Companion:** `pm-os-consistency-spine-plan.md` — the consistency-spine + v1.4.1 fixes half of the same next-development arc. This doc is the entry-pathways half.
**Realizes / supersedes:** the reserved **Phase 5 "thin-context discovery interview"** in `adaptive-context-intelligence-pack.md` (originally a ≤5-question nudge for thin inputs, skippable, answers registered as a PM-authored source, skips → known unknowns). This plan realizes that Phase 5 and makes it **pathway-aware** and **feasibility-map-driven** — and, for pathway 2's *reconstruction* case, **replaces the fixed ≤5 cap with a coverage-driven, batched model** (§4): Phase 5's small cap suits a thin-input nudge, not the fuller WHY/scope reconstruction a prototype needs. Fold Phase 5 into this plan (Open decision #5).
**Does not depend on:** the abandoned `feat/whole-product-foundation` branch (scope tiers / increments / promote).

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
| **3 · Live product** | A shipped product + **codebase** | past 09 | Part A shipped — `--mode enhancement --codebase`, `00c` | **Interview (narrow)** for intent the code can't express; the ask is a **scoped delta**, not a full redefinition |

### The two-axis model (why 2 and 3 differ in kind, not just cost)

- **Extraction cost vs. elicitation cost move oppositely.** Prototype = cheap to read, expensive to interview (thin source, no WHY). Codebase = expensive to read, but the code answers most WHAT/HOW, so the interview is narrow (intent only).
- **Complete-forward vs. scoped-delta.** Pathways 1 & 2 build one full definition forward. Pathway 3 **snapshots** the existing product as context (`00c` + context wiki) and runs a fresh, *scoped* mini-pipeline for just the change.

## 2b. The uniform front door (routing + guidance)

`/pm-new <slug> ["statement"]` is the **single entry for all three pathways** — it always scaffolds a new project, identically. Immediately after scaffolding it asks one routing question and prints tailored next-step guidance, mirroring the existing GenAI prompt (interactive on a tty; a flag/env escape for unattended runs):

```
Project "<slug>" created.
What are you starting from?
  [1] New idea — nothing built or approved yet
  [2] Approved prototype / design (no code yet)
  [3] Existing live product (codebase)
```

- **[1] New** → proceed greenfield: `/pm-stage-01-brief`.
- **[2] Prototype** (pathway 2) → `/pm-context-import <prototype + any supporting context you have>` (adopt everything provided + interview for the *residual* missing why/scope).
- **[3] Enhancement** (pathway 3) → prompt for the codebase, **promote** the project to enhancement, then `/pm-context-import --codebase <…>`.

Uniform to *use* (always `/pm-new`) and uniform to *consume* (always: created → pick type → told exactly what's next). It also removes the trap where a prototype PM silently lands in greenfield and skips context-import.

**Mechanics:** this gives `type` the same treatment `genai` already has — an interactive prompt plus a flag/env escape (`--entry {new,prototype,enhancement}`, with `--codebase` for enhancement; `--mode`/`PM_OS_PROJECT_TYPE` kept as back-compat aliases). Because the choice happens *after* scaffolding, `/pm-new` scaffolds a uniform `new_product` baseline and the routing step **promotes to enhancement** when [3] is chosen — a small post-scaffold setter that sets `project_type`, records `codebase_path`, and adds the `00c` stage. No schema change (`project_type` already exists). The chosen route is recorded in telemetry.

## 3. What already exists (build on, don't rebuild)

- **`/pm-context-import`** — adopts PM-authored artifacts as their stage and **reverse-generates** the missing upstream stages ("backfill"), gated by the understanding doc. The **feasibility map** (`skills/pm-context-import/SKILL.md` §"Feasibility map") already rates each missing upstream ✅ faithful / ⚠️ lossy / ⛔ infeasible, and the `preflight` subcommand (`scripts/pm_context_import.py`) prints those verdicts.
- **Stage-00 group** — `00` business statement, `00w` context-wiki pack, `00u` understanding doc, `00c` codebase-understanding (enhancement only). All gated.
- **Enhancement mode (Part A, shipped)** — `project_type: new_product | enhancement`, `codebase_path`/`codebase_ref`, `00c` via Explore-based scan, codebase-drift signal in `/pm-status`. **Per-stage delta-framing blocks (modes plan §5) are only partly built** (that plan's A2 dogfood is still open).
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
- **Pathway 3 (codebase, rich source):** narrow — the code answers WHAT/HOW, so the questions target *intent the code can't express*: why the product exists, what this change **is and isn't** (scope + regression boundary), the success bar, what must **not** change.

**Non-interactive safety (per repo convention):** an env/flag escape and a non-tty branch — e.g. `--interview-answers <file>` to supply answers unattended, and `PM_OS_INTERVIEW=skip` (or a non-tty session) records every question as a known unknown and proceeds without blocking. Mirrors `PM_OS_EDITED_UPSTREAM_CHOICE`.

**Where it lives:** a new step in `/pm-context-import` (after `preflight`, before the understanding doc is finalized), so it plugs into the existing approval gate. A thin standalone `/pm-interview` for re-running against remaining known-unknowns is a later add (E3) — name checked against `docs/plans/`, only the *concept* is reserved (Phase 5), not that skill name.

## 5. Pathway 2 — Approved prototype, no code

The prototype **is** the product definition; there is no code, no users, no back-compat. The job is to recover the WHY/scope beneath it and **formalize forward** to a dev/design-ready pipeline.

**Bring everything, not just the prototype.** `/pm-context-import` already ingests **any mix of sources** in one call — research, briefs, PRD fragments, notes, call transcripts, design docs, the prototype — as a folder or a file list (Step 1 registers them recursively; Step 2 classifies each as *adopt-as-stage* vs *context-only*; all feed the wiki/evidence). So additional context is a first-class input **today** — the prototype is simply the highest-fidelity *adoptable* artifact, and everything else grounds the backfill. Crucially, this is what **shrinks the interview**: the more the sources already answer, the fewer residual gaps remain, so the interview asks only what's *still* missing after all provided context is ingested.

Flow: `/pm-context-import <prototype + any supporting context you have>` → doc-scan (no `00c`) → `preflight` (expect ⚠️/⛔ on the upstream gaps the sources don't cover) → **interview (broad, decreasing-impact rounds)** over the *residual* gaps → backfill 01–03 at the raised fidelity → adopt the prototype/design as its stage → normal pipeline forward (06 QA, 07 metrics, 08 TRD) → `/pm-handoff`.

## 6. Pathway 3 — Live product + codebase

The product exists and runs; the client asks for a **change**. Snapshot the existing product as context, then run a **scoped delta** pipeline — do **not** faithfully reconstruct a full 01–07 for the whole existing product (expensive, lossy, mostly wasted).

Flow: `/pm-context-import --codebase <url|path> [+ docs]` → `00c` codebase scan (Explore) + wiki → **interview (narrow)** for intent/scope/regression boundary → run the pipeline **scoped to the delta**, using enhancement-mode per-stage delta-framing blocks (finish modes plan §5 / A2) → `/pm-handoff`. Reuses the existing codebase-drift staleness signal.

## 7. Phases

Independently shippable; ordered by dependency. Each ships with tests (`docs/guides/testing.md`) and both runtime entrypoints (`SKILL.md` + `agents/openai.yaml`).

| Phase | Work | Files | Depends on |
|---|---|---|---|
| **E0** | **Uniform front door + routing (§2b).** `/pm-new` always scaffolds identically, then an interactive routing prompt (new/prototype/enhancement, mirroring the GenAI prompt) sets the type and prints tailored next-step guidance; `--entry`/`--codebase`/env are the non-tty escape. Chosen route recorded in telemetry. **Pathway-2 milestone scope:** `[1]`/`[2]` fully wired; `[3]` presented but falls through to today's `--mode enhancement --codebase` behavior — the **promote-to-enhancement setter** (`project_type` + `codebase_path` + `00c`) lands with **E2 / pathway 3**. | `scripts/pm_new.py`, `skills/pm-new/SKILL.md` (+ `agents/openai.yaml`), telemetry | — |
| **E1** | **Interview primitive (realizes Phase 5), pathway-2 tuning.** New context-import Step (coverage-driven questions, batched by topic in decreasing-impact order, over residual gaps only), register answers as a PM source, re-run preflight, record skips as known unknowns; non-tty/flag escape | `skills/pm-context-import/SKILL.md`, `scripts/pm_context_import.py` (register-answers helper + preflight re-run) | E0 |
| **E2** | **Pathway-3 tuning (narrow) + scoped delta.** Finish enhancement-mode per-stage delta-framing blocks (modes plan §5 / A2 dogfood); scoped-delta handling; interview targets intent only | stage `SKILL.md` 01–08 enhancement blocks, `skills/pm-context-import/SKILL.md` | E1, modes Part A |
| **E3** | Standalone `/pm-interview` re-run against remaining known-unknowns; provenance + telemetry polish; surface known-unknowns in `/pm-status` | new `skills/pm-interview/` (+ `agents/openai.yaml`), `scripts/pm_status.py` | E1 |

> **Executable build plan for E0–E1 (pathway 2):** `pm-os-pathway-2-execution-runbook.md` — a loop-engineered, step-by-step runbook (aim → tests-first → code → verify → pass-if-green → update-tasks) an agent can run end-to-end.

### Acceptance criteria (targets)

- [ ] `/pm-new` always scaffolds identically, then routes: it asks new/prototype/enhancement, sets the type, and prints the correct next step for each (greenfield / context-import / context-import --codebase); non-interactively the `--entry`/`--codebase`/env escape preserves today's behavior. The chosen route is recorded in telemetry, and `[3]` promotes the project to enhancement (`project_type` + `codebase_path` + `00c`).
- [ ] On a pathway-2 import where `preflight` rates a gap ⚠️/⛔, the interview asks **coverage-driven** questions — batched by topic, in **strictly decreasing order of impact**, only for load-bearing gaps the provided sources don't already answer (soft ~5 per round, no hard total); answering raises the affected backfill's fidelity/confidence; skipping records a known unknown and never fabricates.
- [ ] Interview answers appear in `.sources.yaml` as a PM-authored source and feed the wiki/evidence ledger with high confidence.
- [ ] Non-interactively (`--interview-answers <file>` or non-tty), the flow completes without hanging; skipped questions become known unknowns.
- [ ] Pathway 3 runs a scoped-delta pipeline grounded in `00c`, with enhancement delta-framing active in stages 01–08; the interview is narrow (intent), not a full re-derivation.
- [ ] No change to the gate/hash/staleness/telemetry core; every stage-00 doc remains a human-approved gate; the interview never self-approves.

## 8. Open decisions (need PM input)

1. ~~**Build order — pathway 2 or 3 first?**~~ **DECIDED 2026-08-01: pathway 2 (prototype) first** — it's the case Karan is handing off to dev now; pathway 3 (codebase) comes later. E1 targets the pathway-2 (broad) interview; E2's pathway-3 tuning is deferred with it.
2. **Interview home** — a step inside `/pm-context-import` (recommended) with a standalone `/pm-interview` added later (E3), or a standalone skill from the start?
3. **Pathway 3 shape** — snapshot-as-context + scoped delta (recommended), or faithfully reconstruct full upstream 01–07 for the existing product?
4. ~~**Entry-profile in meta**~~ **Resolved by the front-door model (§2b):** the routing prompt sets the type at `/pm-new`. `new`/`enhancement` map to `project_type`; the `prototype` choice is `new_product` under the hood, recorded as a lightweight route hint (telemetry + optional meta field) so status/segmentation can tell it apart.
5. **Fold Phase 5** — confirm this plan supersedes `adaptive-context-intelligence-pack.md` Phase 5 (thin-context discovery interview), so there's one interview design, not two.

## 9. Non-goals

- Rebuilding the abandoned tiers/increments/promote work (that's a separate, deferred delivery-model effort).
- Any backend/service — everything stays local files + agent judgment.
- Weakening a gate: the interview informs generation; it never approves, and the three stage-00 docs remain human-approved.
- Interrogation: ask only load-bearing gaps the provided sources don't already answer, batched and skippable — never a fixed quota, and never converting a skipped question into a silent assumption.

---

End of plan.
