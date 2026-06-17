# PM-OS Modes & Engineering Handoff Plan

**Status:** 🔲 **Not implemented** (verified against the codebase 2026-06-17 — no `pm-stage-00-understand` skill, no `project_type` or `codebase` fields in `.meta.yaml`, no MCP handoff). Tracked as **Phase 3** (enhancement mode / codebase understanding) and **Phase 4** (engineering handoff) in `docs/PM-OS-CURRENT-STATE-REVIEW.md` §7.

> **Reconciliation note (2026-06-17):** Phase 2 shipped a general **stage-00 understanding framework** — a gated context wiki (`00-context-wiki.md`) + understanding doc (`00-context-understanding.md`) synthesized from PM-provided sources, plus the business statement as gated stage `00`. The codebase understanding described below should be implemented as **one more evidence source feeding that same framework** (the code becomes another source the wiki absorbs and the understanding doc summarizes), not as a separate bespoke `00-codebase-understanding.md` pipeline. Reuse `lib/project.py`'s stage-00 group, `migrate_meta`, and `pm_context_import.py` rather than duplicating them.
**Author:** Karan (with Claude Code)
**Date:** 2026-06-10
**Scope:** Extend PM-OS from new-product-development-only to also support existing-product enhancements from a single install, and lay out a later-phase engineering-handoff capability (Figma / Jira / Linear via MCP).

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

## 8. Part B — Engineering handoff (later phase)

Engineering handoff is an **export/sync action, not new pipeline stages** — the same category as the existing `/pm-share`. It runs *after* approved artifacts exist and pushes them outward via MCP. Model it as a `pm-handoff` skill family gated on `approved` status, rather than stages 09/10.

The relevant MCP connectors are already available in the environment (Figma, Linear, Atlassian/Jira), which de-risks this phase.

- **`/pm-handoff jira` / `/pm-handoff linear`** — turn approved PRD (03) user stories + functional requirements (and TRD 08 tasks) into epics/tickets, pushed via the Jira/Linear MCP. Dry-run preview → confirm → create (outward-facing, so confirm before creating).
- **`/pm-handoff figma`** — two directions:
  - *Pull* (do first): read an existing Figma file to extract real design tokens/components so stage 04 extends the actual system. **Complementary** to enhancement mode, which already extracts design language from code — most useful when the design source of truth lives in Figma rather than the codebase.
  - *Push* (later): generate frames from the prototype brief.

This phase **revises current v1 non-goals.** Spec §13 lists "Figma integration" and "MCP integrations beyond optional `pm-share`" as out of scope, and the cross-runtime plan calls a unified MCP server out of scope. Part B formally retires those non-goals rather than silently contradicting them. MCP is supported across Claude Code / Codex / Gemini, so connectors stay cross-runtime-portable.

---

## 9. Open decisions to resolve before build

1. **Codebase access** — local path only for v1 (PM already has the repo checked out), or also support a git URL that PM-OS clones? **Recommendation: local path only** — simpler, no auth/clone concerns.
2. **Understanding-doc structure** — confirm or amend the §4 section list, including any Indegene-specific surfaces to always call out (e.g. compliance/PHI boundaries, integration points).
3. **Mode field naming** — `project_type: new_product | enhancement` (default `new_product`), or different naming/values?

---

## 10. Sequencing

Independently shippable; ordered by dependency.

| Phase | Work | Depends on |
|---|---|---|
| **A0** | `pm-stage-00-understand` skill + `00-codebase-understanding.md` + Explore-based reading + drift signal | mode flag |
| **A1** | Schema + `pm_new` (`--mode`, `--codebase`) + `pm_status` + meta/template plumbing | — |
| **A2** | Enhancement conditional blocks across stages 01–08; dogfood one real enhancement end-to-end | A0, A1 |
| **B1** | `/pm-handoff jira` / `linear` (export PRD/TRD → tickets) | A complete |
| **B2** | Figma *pull* to ground enhancement-mode design spec | B1 |
| **B3** | Figma *push* + spec §13 non-goal revision | B2 |

A0–A2 are the immediate ask; B is staged behind them and depends on `project_type` existing.

---

## 11. Acceptance criteria (Part A)

- [ ] `/pm-new --mode enhancement --codebase <path>` scaffolds a project with `project_type=enhancement` and `codebase_path` set.
- [ ] `/pm-new` with no mode defaults to `new_product` and behaves exactly as today (no regression for greenfield).
- [ ] `pm-stage-00-understand` reads the codebase read-only and writes `00-codebase-understanding.md` with a recorded `codebase_ref`.
- [ ] The understanding doc passes through the normal draft → approve gate; stage 01 is blocked until it is approved.
- [ ] Stage 01 brief in enhancement mode frames the request as a delta against the approved understanding.
- [ ] Enhancement conditional blocks activate correctly in stages 02–08.
- [ ] `/pm-status` shows mode and a codebase-drift indicator.
- [ ] Telemetry records `project_type` for segmentation.
- [ ] No change to new-product behavior, hashing, staleness, or telemetry semantics.

---

End of plan.
