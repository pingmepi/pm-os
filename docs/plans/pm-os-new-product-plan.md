# PM-OS — New-Product Whole-Product Definition: Implementation Plan

**Status:** 🟢 **BUILD FIRST — NP1–NP3 implemented + verified** (branch `feat/whole-product-foundation`; full suite 342 passed). **Pending:** NP4 (the `02r` stage), NP5 (metrics/feasibility seeding), NP6 (wiring + e2e). **Depends on:** Foundation [`F1`](pm-os-foundation-plan.md) (overlay filter) + [`F2`](pm-os-foundation-plan.md) (tier attribute). Does **not** need the program object (F4) or provenance (F3) — A1 keeps this to one project.
**Parent / rationale:** [`pm-os-whole-product-pdlc-plan.md`](pm-os-whole-product-pdlc-plan.md).
**Decisions baked in:** A1, B1, D2 (SOW-grade stub), G1, H1. Read the **Guardrails** section of the foundation plan first — it applies here verbatim.

**Goal:** let a PM scope the **whole product**, tiered (`mvp|v1|v2|later`), author a **gated phased roadmap early**, then elaborate the MVP at full fidelity — promoting later tiers on demand. **Nice property: this whole plan needs no `.meta.yaml` schema migration** (tiers live in artifacts; the new stage is scaffolded for new projects and invisible to existing ones via the present-filter in `upstream_stage_ids`).

---

## Task graph (do in id order; NP4 is the biggest)

| Task | Summary | Touches |
|---|---|---|
| NP1 | Tiered scope (G1) | `skills/pm-stage-02-scope`, `artifact_contracts`, `traceability` |
| NP2 | Tiered fidelity + SOW-grade stub (D2) | `artifact_contracts`, `skills/pm-stage-03-prd` |
| NP3 | `/pm-promote` + demote + cost preview | `scripts/pm_promote.py`, `skills/pm-promote`, `pm_status` |
| NP4 | Early gated phased-roadmap stage `02r` (H1/B1) | `lib/project.py`, new skill, `artifact_contracts`, `pm_new`, `config` |
| NP5 | Seed metrics + feasibility per phase | `skills/pm-stage-02r-*`, `skills/pm-stage-07-metrics-plan` |
| NP6 | Wiring, migration-safety, end-to-end validation | `pm_new`, `pm_os_verify`, tests |

---

### NP1 — Tiered scope (G1) — ✅ IMPLEMENTED

**Change:**
- `skills/pm-stage-02-scope/SKILL.md` (+ `agents/openai.yaml`): instruct the model to **enumerate the whole product**, and tag each requirement it seeds with `- **Tier:** <mvp|v1|v2|later>` (default `mvp`). MVP boundary prose stays, but is now *"the set of requirements tagged `mvp`"* (machine-readable), not a standalone paragraph. Non-MVP items are enumerated at **SOW-grade stub** fidelity (see NP2).
- Consumes `block_tier` + `requirements_by_tier` from Foundation F2.
- Emit a short **Tier Summary** table in the artifact (counts per tier) so a reader sees the whole-product shape at a glance.

**Verification:**
- Run `/pm-stage-02-scope` on a scratch project (`~/pm-projects/np-test/`): requirements carry `Tier:`; unspecified → `mvp`; Tier Summary present.
- `tests/integration/test_project_lifecycle.py` (or a new `test_scope_tiers.py`): parsed scope yields tiers; `requirements_by_tier` returns non-empty `mvp` set; a legacy scope with no tiers → all `mvp` (back-compat).

---

### NP2 — Tiered fidelity + SOW-grade stub (D2) — ✅ IMPLEMENTED

**Change:**
- `lib/artifact_contracts.py`: make the stage-03 v2 mini-spec checks (acceptance criteria / edge cases / happy path) apply **only to `tier: mvp`** requirements. For `v1|v2|later`, require the **SOW-grade stub** fields: `Value`, `Tier`, rough `Size`/estimate, `Rationale`, `Depends on`, and one-line `Acceptance intent`. Missing stub field → `WARNING`; missing MVP full-fidelity field → `ERROR` (unchanged severity for MVP).
- `skills/pm-stage-03-prd/SKILL.md` (+ openai.yaml): elaborate `tier: mvp` fully; render non-MVP tiers as SOW-grade stubs; **do not** invent design for non-MVP tiers.

**Verification:**
- `tests/unit/test_artifact_contracts.py`: an MVP requirement missing acceptance criteria → `ERROR`; a `v1` stub missing `Size`/`Rationale` → `WARNING`; a `v1` stub is **not** required to carry full acceptance criteria.
- Manual: PRD on the NP1 scratch project shows full MVP specs + light v1/v2 stubs.

---

### NP3 — `/pm-promote` (+ demote) + cost preview (D2, scope adjustability) — ✅ IMPLEMENTED

**Change:**
- New `scripts/pm_promote.py`: `promote <REQ-ID> [--to <tier>]` raises a requirement's tier (e.g. `v1→mvp`) and flags its mini-spec for full-fidelity regeneration; `--demote` lowers it. Re-tag is the mechanical part; regeneration is the skill's job.
- **Cost preview (read-only):** before applying a mid-stream change, print which downstream stages will restale (`downstream_stage_ids` from `lib/project.py`) and how many requirements regenerate. At the **start** (no downstream generated) it reports "free — no cascade."
- New `skills/pm-promote/SKILL.md` (+ `agents/openai.yaml`): orchestrates re-tag → cost preview → (on confirm) regenerate the promoted requirement's mini-spec. Follow **non-interactive safety** (env/flag escape + non-tty branch).
- `scripts/pm_status.py`: show per-tier requirement counts.

**Verification:**
- New `tests/integration/test_promote.py`: `promote v1→mvp` re-tags in the artifact + spine; cost preview lists the correct restaled stages when downstream exists and "free" when it doesn't; `--demote` reverses it; **staleness is produced by the existing cascade, not by pm_promote** (assert pm_promote never writes status directly — Guardrail #1).
- Runtime parity: `skills/pm-promote/agents/openai.yaml` present and consistent with `SKILL.md`.

---

### NP4 — Early gated phased-roadmap stage `02r` (H1 + B1) — **the core change**

**Design:** a new **gated** stage `02r` ("phase-roadmap") sits **after `02` scope, before `03` PRD**. Authored from the tiered scope, it maps tiers→phases (V1/V2/…), sequences by dependency, and is the SOW-signable whole-product view. Being a normal gated stage satisfies **B1** (gated), and its early position satisfies **H1**.

**Change (declarative — no state-machine edits):**
- `lib/project.py`:
  - `STAGE_ORDER`: insert `"02r"` immediately after `"02"`.
  - `STAGE_NAMES["02r"] = "phase-roadmap"`.
  - Add `"02r"` to `STAGE_DEPENDENCIES["08"]` and `["09"]` lists (so the capstones gate on it when present).
  - Because `upstream_stage_ids` is **index-based + present-filtered**, `03`–`07` automatically gate on `02r` **only when the project has it** — so existing projects (no `02r`) are unaffected. Add a test asserting exactly this.
- `skills/pm-stage-02r-phase-roadmap/SKILL.md` (+ `agents/openai.yaml`): pre-stage gate → read approved `02` (tiers) → produce the phased roadmap; **forbidden from inventing new requirements** (it references tiered `US/FR` ids, mirroring today's stage-09 rule). Gate line: `PM_OS_STAGE=02r python3 ~/.pm-os/hooks/pre-stage.py`.
- `lib/artifact_contracts.py`: `REQUIRED_SECTIONS["02r"]` = e.g. *Phasing Overview*, *Phase Definitions (V1/V2/…)* (each = tier→requirement mapping + sequencing rationale + per-phase success signal + feasibility flag — see NP5), *Dependencies & Sequencing*, *Out-of-Horizon*. Bump `CONTRACT_VERSION` if a new artifact contract is registered.
- `lib/config.py`: add `"02r"` to `deep_reasoning_stages` (phasing is a reasoning task).
- **Stage 09 relationship (ONE sub-decision to confirm during build):** with `02r` owning phasing, stage `09` narrows to an *optional detailed release roadmap* or is retired. **Recommended:** keep `09` as-is for migration safety (existing projects have it) and note the future consolidation; do **not** delete it in this task. Flag this explicitly in the PR description.

**Verification:**
- New `tests/integration/test_phase_roadmap_stage.py`:
  - a **new** project scaffolds `02r`; `03`'s gate **blocks** until `02r` is approved; approving `02` alone is insufficient.
  - an **existing** project fixture *without* `02r` still runs `03` (present-filter path) — proves back-compat.
  - `08`/`09` gates include `02r` when present.
  - `02r` artifact validates against its contract.
- `tests/unit/test_project.py`: `upstream_stage_ids("03", meta_with_02r)` contains `02r`; `upstream_stage_ids("03", meta_without_02r)` does not.
- Re-run `test_stage_gates.py` — no regressions.

---

### NP5 — Seed success metrics + feasibility per phase (efficiency fix)

**Why:** fixes brainstorm §1 "metrics/feasibility land too late" at near-zero cost, since `02r` already enumerates phases.

**Change:**
- `skills/pm-stage-02r-phase-roadmap`: each phase carries a one-line **success signal** and a **feasibility flag** (`clear|risky|unknown`).
- `skills/pm-stage-07-metrics-plan/SKILL.md`: reference the per-phase success signals from `02r` when building MVP metrics (don't re-derive).

**Verification:**
- `test_phase_roadmap_stage.py`: each phase block carries a success signal + feasibility flag; stage-07 output references them.

---

### NP6 — Wiring, migration-safety, end-to-end validation

**Change:**
- `scripts/pm_new.py` (project scaffold): add `02r` to the scaffolded `stages[]` for **new** projects (status `pending`). **No `schema_version` bump** — `stages[]` is a list; existing projects simply lack `02r` and are handled by the present-filter.
- `scripts/pm_os_verify.py`: include `pm-stage-02r-phase-roadmap` and `pm-promote` in the installed-skills check.
- `docs/guides/sop.md`, `README.md`, `CLAUDE.md` stage list: document the new `02r` stage + `/pm-promote` + tiers.

**Verification (acceptance for the whole plan):**
- **End-to-end scratch run** (`~/pm-projects/np-e2e/`): `/pm-new` → `/pm-stage-01-brief` → approve → `/pm-stage-02-scope` (tiered) → approve → `/pm-stage-02r-phase-roadmap` → approve → `/pm-stage-03-prd` (MVP full, v1/v2 stubs) → … → `/pm-promote <v1 story> --to mvp` (regenerates its spec) → `/pm-handoff --package`. All gates behave; roadmap is gated; promotion pays fidelity.
- Full `pytest` green; `pm_os_verify.py --runtime claude` green (after sync).
- Every new test docstring'd + cataloged in `docs/guides/testing.md`.

---

## Definition of done
- NP1–NP6 merged; end-to-end scratch run passes; no schema migration required; state machine provably untouched (existing gate/staleness tests unchanged).
