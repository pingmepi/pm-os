# PM-OS Modes, Delivery Model & Engineering Handoff Plan

**Status:** 🟡 **Part A implemented (v0.5.9 / v0.6.0); Part B designed but unbuilt; Part C partly shipped.** Enhancement mode shipped: `--mode enhancement`, `--codebase <url-or-path>`, `project_type`/`codebase_path`/`codebase_ref` in `.meta.yaml` (schema v3), conditional `00c` codebase-understanding stage, `prepare-codebase` subcommand in `pm_context_import.py`, codebase drift signal in `pm_status.py`. **Part B — the delivery model (scope tiers + delivery increments) — is designed here (2026-07-27) but unbuilt.** Part C (external engineering handoff) is partly shipped: `/pm-handoff jira` — both the Atlassian-MCP create route and the `--offline` CSV export — landed v1.2.0 (screen mapping v1.3.0); `/pm-handoff linear` and Figma pull/push remain unbuilt. Delivery-model and unbuilt-handoff work is tracked as Phase 4 in `docs/roadmap/current-state-review.md` §7 and as backlog #28.
>
> **Naming note, resolved 2026-07-15.** A local, human-readable handoff-package generator briefly shipped under `skills/pm-handoff/` (PR #30), colliding with the `/pm-handoff <target>` name this plan reserves for Part B below. **Resolved by merging that local generator into `/pm-share --package`** (`scripts/pm_share.py`) instead — `pm-share` now covers both a raw text export and the decomposed per-story package, and the `pm-handoff` name is fully free again for Part B's external-tracker/design export when it gets built, exactly as this plan originally intended.

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

For an already-built product, the most reliable source of current-state truth is the **code itself**, not a document the PM writes from memory. So enhancement mode does not ask the PM to author a context file. Instead:

1. PM-OS **reads the existing codebase** (read-only) and synthesizes a **Codebase Understanding** document.
2. That document is surfaced to the PM as the **first approval gate** — they review, correct any misreading, and approve.
3. Only once the understanding is approved do downstream stages run, each **aligning the PM's request as a delta against that approved reality.**

This gives the PM a natural, early correction point: if PM-OS misunderstands the product, it is caught and fixed at gate 0 rather than surfacing three stages later. PM-OS only ever **reads** the codebase — it never modifies it, staying true to "not a replacement for the dev team."

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

Numbering of stages 01–08 is unchanged, so existing projects and skills are unaffected. The business statement (the *ask*) and the codebase understanding (the *reality*) are both stage-00 grounding; the brief stays stage 01 and simply gains a second upstream input in enhancement mode. All stages remain present in both modes — **mode changes framing and depth, not stage presence** — which preserves the single-architecture guarantee.

---

## 4. New stage: `pm-stage-00-understand` (enhancement-only)

A new skill that runs only when `project_type=enhancement`.

**Pre-flight:** require `project_type=enhancement` and a resolvable `codebase_path` in `.meta.yaml`; otherwise stop with a clear message.

**How it reads the codebase:** fan-out exploration via a read-only sub-agent (the **Explore** agent is purpose-built for this — broad codebase sweep, returns a digest, keeps the main session context clean). Large repositories stay tractable because the sub-agent reads excerpts and reports conclusions rather than loading whole trees. Cross-runtime note: Codex and Gemini CLI both have file/shell access and sub-agents, so this step is portable.

**Output — `00-codebase-understanding.md`** — proposed default sections (to be confirmed, see §9):

- Current functionality & user-facing flows
- Architecture & key modules
- Data model
- Tech stack & notable dependencies
- Existing design language (tokens / components extracted from code)
- Integration points & external surfaces
- Known constraints & tech debt

Frontmatter records the **git SHA** the document was generated against (`codebase_ref`).

**Approval gate:** normal `draft → approve` flow. The PM reviews, edits to correct any misread, and approves. The stage-01 gate in enhancement mode requires stage 00 to be `approved`.

---

## 5. Per-stage conditional blocks (enhancement mode)

Added to each existing `SKILL.md` as a "When `project_type=enhancement`:" block, mirroring the existing `genai_flag` precedent. Grounded in the approved understanding doc.

| Stage | When `project_type=enhancement` |
|---|---|
| 01 Brief | "Why now" → "Why this enhancement"; problem framed against the current-product gap; reads `00-codebase-understanding.md` |
| 02 Scope | Add **Impact on existing features** + **Regression boundary** (what must not change); scope bounded by the current system |
| 03 PRD | User stories as **deltas** (changed vs net-new); backward-compatibility & migration requirements |
| 04 Design Spec | **Extend** the existing design system (from the understanding doc); reuse the existing component inventory rather than inventing tokens |
| 05 Prototype Brief | Prototype the delta against existing screens, not a greenfield flow |
| 06 QA Plan | Heavy **regression suite** for existing behavior + migration testing, alongside new-feature tests |
| 07 Metrics Plan | **Baseline → target** framing (current numbers exist) + guardrails that existing metrics do not regress |
| 08 TRD | Brownfield: integration with the existing architecture, migration path, tech-debt constraints |

---

## 6. Codebase drift (new staleness signal)

The understanding doc is generated against a git SHA. If the code moves, the doc — and everything downstream — can be stale. `/pm-status` shows "understanding generated against `abc123`; current HEAD is `def456`," and re-running stage 00 regenerates and cascades staleness through the existing hash machinery. This is a softer signal than artifact-hash drift (the "upstream" here is external code rather than another PM-OS artifact), but it reuses the same plumbing.

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

**Risk:** low. Additive flag + one new gate; the deterministic core is untouched.

---

## 8. Part B — Delivery model: scope tiers & delivery increments

**Designed 2026-07-27 (Karan + Claude); unbuilt.** This part resolves two gaps the current linear pipeline has by design: PM-OS defines exactly one tier of work ("the MVP", as prose) and hands it off exactly once. It adds a *scope-tier* dimension upstream and a *delivery-increment* dimension downstream, both **additive to the traceability spine — no change to the gate, hash, status, or staleness machinery** (the product-shape golden rule: grow the spine, not the state machine). Depends on backlog #19 (priority) and #20 (TRD section contract).

### 8.1 The two gaps, verified

- **"MVP" is prose, and "the whole product" cannot produce stories.** Stage 02 writes one `## MVP Boundary` paragraph (`skills/pm-stage-02-scope/SKILL.md:155`); every downstream stage treats it as binding via LLM judgment, with no structured field, ID, or flag. Stage 09 has `V1`/`V2`/`Expansion` horizons but is explicitly forbidden from generating requirements, so roadmap horizons carry **no `US-###`/`FR-###`**. There is no path from "V1 horizon" to "user story" — the pipeline can only ever elaborate the single tier stage 02 named MVP.
- **Handoff is single-shot, and the two exports disagree.** `scripts/pm_share.py:352` stamps every story with a literal `"EPIC-01"` and writes one `epics/EPIC-01-mvp.md`; `scripts/pm_handoff.py:160` uses a *different* mapping (one epic per `US-###`). Neither models "which slice ships this cycle" — a grep for `sprint` across `skills/`/`lib/`/`scripts/` returns nothing.

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

### 8.6 Resolve the export mismatch first

Before tiers or increments land, the `EPIC-01`-hardcode (`pm_share.py:352`) vs. one-epic-per-story (`pm_handoff.py:160`) disagreement must be reconciled to a single epic/story/task mapping — otherwise the inconsistency multiplies across every tier and increment.

Once unified, `/pm-handoff jira --increment INC-02` scopes the export to that increment — but **an increment export is the member set plus its required ancestor closure, not the members alone.** `scripts/pm_handoff.py:255-264` parents each task to its owning `US-###` epic, and the offline exporter (`:359-365`, `:399-410`) resolves `Parent Id` only against issues present in the *same* CSV. So a task-only export orphans every task (its parent epic isn't in the file). The export must therefore emit, for each member, the epic/story ancestors it hangs from. And because those ancestors may have been created in an *earlier* increment, the export must **substitute the previously-recorded Jira keys** (from `.traceability.yaml`'s per-increment `tickets:` slots) for any parent already created, rather than re-creating it. `.traceability.yaml` records returned ticket keys per increment so cycle 2 never recreates cycle 1's tickets. This is a prerequisite-aware refinement of backlog #28.

---

## 9. Part C — External engineering handoff (Jira / Linear / Figma)

Engineering handoff is an **export/sync action, not new pipeline stages** — the same category as the existing `/pm-share`. It runs *after* approved artifacts exist and pushes them outward. Model it as a `pm-handoff` skill family gated on `approved` status, rather than stages 09/10. It consumes the Part B delivery increments: an increment is the natural unit of a single handoff.

**Status: partly shipped.** The Jira half of this part is built; Linear and Figma remain unbuilt.

- **`/pm-handoff jira` — ✅ shipped (v1.2.0, offline route + screen mapping v1.3.0).** `scripts/pm_handoff.py plan` parses the approved PRD (+ approved TRD) into a tracker-agnostic ticket map (`US-###` → epic, `FR-###`/`REQ-###` → child story, approved `TSK-###` → child task) and writes a PM-readable dry-run, fully offline. Two create routes:
  - *Connector route:* dry-run → PM confirms → create via the **Atlassian MCP** → `record` writes ticket keys back into `.traceability.yaml`. Needs an authorized connector.
  - *Offline route (`--offline`):* `pm_handoff.py export` writes `handoff/jira-import.csv` (+ import guide, descriptions converted to Jira wiki markup via `lib/jira_markup.py`, `Issue Id`/`Parent Id` parent linking) that the PM imports through Jira's own CSV importer — **no connector, no tokens** — then recovers the keys and runs the same `record` step. Ends in the same state as the connector route.
- **`/pm-handoff linear` — 🔴 unbuilt.** The plan builder is tracker-agnostic, so Linear is mostly a second create adapter over the same map. (Per the roadmap's one-tracker principle, Jira was chosen first, not both.)
- **`/pm-handoff figma` — 🔴 unbuilt.** Two directions:
  - *Pull* (do first): read an existing Figma file to extract real design tokens/components so stage 04 extends the actual system. **Complementary** to enhancement mode, which already extracts design language from code — most useful when the design source of truth lives in Figma rather than the codebase.
  - *Push* (later): generate frames from the prototype brief.

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
| **A2** | Enhancement conditional blocks across stages 01–08; dogfood one real enhancement | A0, A1 | 🟡 dogfood open |
| **B0** | Resolve the `EPIC-01` vs. per-story export mismatch to one mapping (backlog #28) | — | 🔴 prerequisite |
| **B1** | Scope-tier attribute (`Tier:` on `US`/`FR`) + stage-02 tier declaration + stages 04–07 default-to-`mvp` filter | #19, B0 | 🔴 open |
| **B2** | Tiered-fidelity contract (v2 mini-spec checks apply to `tier: mvp` only) + `/pm-promote` | B1 | 🔴 open |
| **B3** | Delivery-increment layer (`delivery.yaml`, `INC-###` by `TSK`) + `/pm-check` cross-validation | #20, B1 | 🔴 open |
| **C1** | `/pm-handoff jira` (export PRD/TRD → tickets); `--increment` scoping | A complete, B3 | 🟡 base shipped v1.2.0; `--increment` open |
| **C2** | Figma *pull* to ground enhancement-mode design spec | C1 | 🔴 open |
| **C3** | Figma *push* + spec §13 non-goal revision | C2 | 🔴 open |

---

## 12. Acceptance criteria

**Part A (met):**
- [x] `/pm-new --mode enhancement --codebase <path>` scaffolds a project with `project_type=enhancement` and `codebase_path` set.
- [x] `/pm-new` with no mode defaults to `new_product` and behaves exactly as today (no regression for greenfield).
- [x] The `00c` understanding doc passes the normal draft → approve gate; stage 01 is blocked until it is approved.
- [x] Enhancement conditional blocks activate in stages 01–08; `/pm-status` shows mode and codebase drift; telemetry records `project_type`.
- [x] No change to new-product behavior, hashing, staleness, or telemetry semantics.

**Part B (target):**
- [ ] The `EPIC-01`/per-story export mismatch is resolved to one mapping before any tier/increment work (B0).
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
