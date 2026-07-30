# PM-OS — Shared Foundation: Implementation Plan

**Status:** 🟢 **F1–F2 implemented + verified** (branch `feat/whole-product-foundation`; full suite 342 passed). F3–F4 pending (built with the enhancement phase). **Build order: FIRST — new-product needs F1+F2; enhancement needs F3+F4.**
**Parent / rationale:** [`pm-os-whole-product-pdlc-plan.md`](pm-os-whole-product-pdlc-plan.md) (design + decision log).
**Sibling plans:** [`pm-os-new-product-plan.md`](pm-os-new-product-plan.md) (built first), [`pm-os-enhancement-plan.md`](pm-os-enhancement-plan.md) (built second).

This doc is the **shared primitives** both sibling plans depend on. Not every task is needed before new-product can start — see the **Needed-by** column. An executing agent should read the Guardrails section first, then work tasks in id order.

---

## Locked decisions (apply across all three plans)

| Id | Decision | Meaning |
|---|---|---|
| **A1** | phase = tier-*tag*, one project | no per-phase sub-pipelines; a "phase" is a tag on requirements |
| **B1** | phased roadmap is a **gated** artifact | it is a normal gated stage (draft→approved), not an ungated ledger |
| **C2** | baseline provenance **tagged + attributed** | every reconstructed fact carries `scanned \| asserted \| inferred` + who |
| **D2** | non-MVP tiers = **SOW-grade stubs** + `/pm-promote` | MVP full-fidelity; v1/v2/later = title+value+tier+size+rationale+deps+acceptance-intent |
| **G1** | one tiered scope artifact | tiers are tags models/tools filter on (mvp/v1/v2/…); no separate selection stage |
| **H1** | phased roadmap authored **early** | new gated stage after `02` scope, before `03` PRD |
| — | **Build order** | new-product first, enhancement second |

---

## Guardrails (READ FIRST — non-negotiable, from `CLAUDE.md`)

1. **Never touch the state machine.** Gate/hash/status/staleness live in `hooks/pre-stage.py`, `hooks/post-approve.py`, `scripts/pm_approve.py`, `lib/hashing.py`. Every task here is **additive to the traceability spine or read-only composition** — do not modify gate conditions, hashing, or the status lifecycle.
2. **Install discipline.** Edits in this working copy are **inert** until `commit → push → pm_os_update.py`. To test uncommitted logic, run against this repo in isolation (`PYTHONPATH=lib python3 …`) or a scratch project under `~/pm-projects/`. **Never** hand-copy into `~/.pm-os` or `~/.claude/skills`.
3. **Two synchronized sources of truth.** Stage state lives in **both** `.meta.yaml` (`stages[]`) and each artifact's frontmatter — keep them in lockstep. Any shape change bumps `schema_version` **and** ships a `migrate_meta` block that keeps existing on-disk projects working (never force re-approval).
4. **Runtime parity.** Every skill ships `SKILL.md` (Claude) **and** `agents/openai.yaml` (Codex). Add/patch both.
5. **Config-driven models.** Deep-reasoning stages come from `lib/config.py` `deep_reasoning_stages` — never hardcode a provider model id.
6. **Non-interactive safety.** Any `input()` needs an env-var/`--flag` escape **and** a non-tty branch.
7. **Tests carry docstrings and are cataloged** in `docs/guides/testing.md`. Every new test does both.

**Run-all verification (used by every task's Verification):**
```bash
cd <repo> && python3 -m pytest -q            # full suite must stay green
# health-check the installed tool (after sync): 
python3 ~/.pm-os/scripts/pm_os_verify.py --runtime claude
```

---

## Tasks

### F1 — Context-overlay stage-affinity filter — ✅ IMPLEMENTED — **Needed-by: new-product (do first)**

**Why:** `lib/context.py` currently injects every `global` overlay block into **every** stage unfiltered (brainstorm §5.6 #1). Both sibling plans push more context (tiers, baseline, questionnaire) into stages; fix the filter *before* piling on or every stage gets a token dump.

**Change:**
- `lib/context.py`: let a `global` manifest entry declare an optional `stages: [<ids>]`; default = all stages (unchanged behavior when absent). Filter globals by the current `stage_id` in `render_context`/`resolve_context`.
- `context.example/context.yaml`: document the new optional `stages:` key on globals (seed only — do not fill).
- Preserve the existing **no-op guarantee** (`_clean`, `_has_substance`, seed-equality check) untouched.

**Verification:**
- Extend `tests/unit/test_context.py`: a global with `stages: ["03"]` renders into stage 03 and **not** into 02; a global with no `stages` renders into all (regression); an all-unfilled pack still injects nothing.
- Manual: `python3 -c "import sys; sys.path.insert(0,'lib'); from context import render_context; print(render_context('02','<scratch-proj>'))"` shows only stage-02-relevant globals.

---

### F2 — Tier attribute on the spine + fast filter — ✅ IMPLEMENTED — **Needed-by: new-product (do first)**

**Why:** G1/D2 need every `US-###`/`FR-###` to carry a machine-readable tier so tools/models can filter `mvp|v1|v2|later` instantly.

**Change:**
- `lib/artifact_contracts.py`: add `block_tier(block) -> str` (reads `- **Tier:** <val>` inside a US/FR block via existing `labeled_field`; default `"mvp"`; validate value ∈ `{mvp,v1,v2,later}`, else a `WARNING` Finding `TIER_INVALID`). Reuse the `block_priority` pattern.
- `lib/traceability.py`: in `build_index`, record `tier` on each requirement entry (derived — no schema migration for on-disk data). Bump `TRACEABILITY_SCHEMA_VERSION` 5→6 (derived index upgrades transparently on next rebuild). Add helper `requirements_by_tier(index) -> {tier: [req_id,...]}` and `mvp_requirements(index)`.
- **No `.meta.yaml` schema bump** — tier lives in artifact bodies + the derived index. Existing projects with no `Tier:` default every requirement to `mvp`, so behavior is unchanged.

**Verification:**
- `tests/unit/test_artifact_contracts.py`: `block_tier` default = `mvp`; explicit `v1` parsed; invalid tier → `TIER_INVALID` warning.
- `tests/integration/test_traceability_spine.py`: index carries `tier` per requirement; `requirements_by_tier` groups correctly; a PRD with no tiers → all `mvp` (back-compat).

---

### F3 — Provenance primitive (C2) — **Needed-by: enhancement**

**Why:** C2 requires reconstructed facts to be tagged `scanned|asserted|inferred` with attribution. Needed in three places (baseline, questionnaire answers, tier decisions) → build once.

**Change:**
- New `lib/provenance.py`: a small value type / helpers — `record(claim, kind, source, author=None) -> dict`, `validate(record)`, `KINDS = {"scanned","asserted","inferred"}`. Storage convention: a `provenance:` list in the relevant artifact's frontmatter and/or a sidecar `.provenance.yaml` (derived-safe, append-only by convention).
- Document the convention in `docs/reference/` (one short section).

**Verification:**
- New `tests/unit/test_provenance.py`: record round-trips through YAML; invalid `kind` rejected; attribution preserved; missing attribution allowed for `scanned`.

---

### F4 — Program object (read-only roll-up) — **Needed-by: enhancement (defer until then)**

**Why:** enhancement needs a product-of-record + multiple cycles grouped (§4 unification). New-product (A1, one project) does **not** need it — so this is the one keystone that stays deferred until the enhancement build, keeping the first build lean.

**Change (keep it a READ-ONLY VIEW — Risk #1):**
- New `lib/program.py`: `program.yaml` (parent object) lists child project paths + increment order; `load_program`, `resolve_program` (walk up like `resolve_project` but for `program.yaml`), `rollup_status(program)` aggregating child `.meta.yaml` statuses. **Never** a second source of gate/status truth.
- `scripts/pm_status.py`: when a `program.yaml` is present, print the roll-up **in addition to** the normal per-project view.
- `.meta.yaml` schema **v5**: add optional `program: null` backref on children; add a `migrate_meta` v5 block (default `null`, idempotent). Bump `SCHEMA_VERSION` 4→5.
- `/pm-check` (advisory, read-only): warn on cross-child hazards (e.g., an increment whose dependency sits in a later increment).

**Verification:**
- New `tests/integration/test_program_rollup.py`: a `program.yaml` with two child projects → `pm_status` shows roll-up; **each child gate still resolves independently** (import and run `hooks/pre-stage.py` per child — behavior identical to no-program); `resolve_project()` from inside a child is unchanged (program layer never shadows it).
- Re-run `tests/integration/test_stage_gates.py` + `test_approval_and_staleness.py` unchanged — **the state machine must be provably untouched.**
- `tests/unit/test_project.py`: `migrate_meta` adds `program: null`, is idempotent, and leaves a v4 project's stages/approvals intact.

---

## Definition of done (foundation)
- F1, F2 green and merged **before** new-product work begins.
- F3, F4 green and merged **before** enhancement work begins.
- Full `pytest` green; `pm_os_verify.py` green after sync.
- Every new test docstring'd and cataloged in `docs/guides/testing.md`.
