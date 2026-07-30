# PM-OS — Enhancement Pathway (external products): Implementation Plan

**Status:** 🟡 **BUILD SECOND** (new-product first). **Depends on:** Foundation [`F3`](pm-os-foundation-plan.md) (provenance/C2) + [`F4`](pm-os-foundation-plan.md) (program object) — build those before starting here. Also assumes new-product's tier machinery (F2, NP1–NP3) exists, which enhancement deltas reuse.
**Parent / rationale:** [`pm-os-whole-product-pdlc-plan.md`](pm-os-whole-product-pdlc-plan.md).
**Decisions baked in:** C2 (tagged provenance), the §4 unification (an enhancement cycle = *an increment against a product-of-record*), §3.3 (handoff payload). Read the **Guardrails** section of the foundation plan first.

**Context:** this is the **60% majority workload** — enhancing products PM-OS never built. The core problem is that there is **no brief/scope/PRD/TRD to reason against**, so the pathway first **reconstructs a product-of-record (the baseline)**, then runs deltas against it. Today's `--mode enhancement` + `00c` codebase scan (Part A, shipped) is the starting point.

**⚠️ Evidence gate:** run the enhancement **pilot** on today's Part A machinery first and measure it (baseline fidelity via peer red-line, blast-radius recall, post-generation edit volume). **Build EN3/EN5 only where the pilot shows the gap bites** — see parent §3.3 and the anti-creep discipline. This plan is the full design; sequence it behind pilot evidence.

---

## Task graph

| Task | Summary | Touches |
|---|---|---|
| EN1 | Product baseline (scan + docs → backfilled, provenance-tagged product-of-record) | `pm-context-scan-codebase`, `pm_context_import`, `lib/provenance`, `lib/program` |
| EN2 | Portable questionnaire round-trip (emit → peer fills offline → import) | new script/skill, `pm_context_import` |
| EN3 | Enhancement conditional overlays in stages 02–08 | `skills/pm-stage-0{2,3,4,5,6,7,8}`, `artifact_contracts` |
| EN4 | Regression QA class tied to baseline behaviors | `skills/pm-stage-06-qa-plan`, `traceability` |
| EN5 | Enhancement handoff payload (§3.3) | `templates/handoff-story.md.j2`, `scripts/pm_share.py` |
| EN6 | Baseline drift / incremental refresh | `pm_status`, baseline store |
| EN7 | Migration + end-to-end validation | `pm_new`/`migrate_meta`, `pm_os_verify`, tests |

---

### EN1 — Product baseline (the product-of-record)

**Design (§4 corollary):** the baseline is **backfilled stage artifacts**, not a new schema — the scan backfills the *faithful* parts (features→scope, architecture/data→a TRD-of-record) via the existing `resolve_backfill` map; the questionnaire (EN2) fills what backfill can't. Persist it and attach it to the program object (F4) so N enhancement cycles share it.

**Change:**
- Extend `skills/pm-context-scan-codebase/SKILL.md` output → richer `00c` (already: features/flows, architecture, data model, tech stack, design language, integration points, constraints). Tag each claim with a **provenance** record (`lib/provenance`, kind `scanned`).
- `scripts/pm_context_import.py`: register the scan + ingested docs as **sources**; backfill faithful upstream stage artifacts (uses `lib/project.resolve_backfill` — note `BACKFILL_FAITHFUL_FROM["03"] = []`, so a PRD is **never** reconstructed from code alone; that gap is EN2's job).
- Attach the baseline to a `program.yaml` (F4) as the product-of-record; enhancement cycles are child increments.

**Verification:**
- New `tests/integration/test_baseline.py`: against a small fixture repo, the baseline builds; every reconstructed claim carries a provenance record with `kind`; `resolve_backfill` refuses design→PRD (asserts the PRD is not fabricated); the baseline persists and is discoverable from a child increment.

---

### EN2 — Portable questionnaire round-trip (enhancement PM ≠ base-product PM)

**Design:** scan-driven, **gap-only** questionnaire → peer fills offline → import with attribution. Mirrors the `/pm-handoff --offline` emit→fill→import pattern.

**Change:**
- New `scripts/pm_questionnaire.py` (or extend `pm_context_import.py`): `emit` writes a structured questions doc covering only what the scan couldn't determine (WHY, don't-break surface, dependents, compliance); **section-routable** (questions grouped by subsystem/owner). `import` ingests the answered doc as baseline context, each answer tagged `asserted` with **attribution** (who answered) via `lib/provenance` (C2).
- `skills/` entry (+ `agents/openai.yaml`). **Non-interactive safety:** the peer is not in the session — the exchange is document-based, non-tty, flag-driven.

**Verification:**
- `test_baseline.py` (extend): `emit` produces a doc with only scan-gap questions; importing a filled sample adds `asserted`+attributed provenance to the baseline; a skipped questionnaire leaves a **visible** gap (not silently filled); non-tty path works headless.

---

### EN3 — Enhancement conditional overlays in stages 02–08

**Design:** the `genai_flag` pattern — **append-only** sections gated on `project_type == "enhancement"` (Risk #6: never rewrite existing sections, only add). Overlay per stage:
- `02` scope: **Change boundary + blast radius + explicit non-touch**.
- `03` PRD: **changes-to-existing-behavior** refs.
- `04/05` design/prototype: design **against existing IA** (changed screens only).
- `06` QA: **regression class** (→ EN4).
- `07` metrics: **guardrail metrics** (don't regress existing KPIs).
- `08` TRD: **baseline → blast radius → integration/compat → migration/backfill → regression**.

**Change:** conditional blocks in each `skills/pm-stage-0{2,3,4,5,6,7,8}/SKILL.md` (+ openai.yaml) reading `project_type` from `.meta.yaml`; matching optional sections in `lib/artifact_contracts.py` (enhancement-only, warning-level).

**Verification:**
- New `tests/integration/test_enhancement_overlays.py`: an enhancement-mode project's artifacts carry the overlay sections; a `new_product` project is **byte-for-byte unaffected** (no overlays); the contract validator accepts both; the 4-combo matrix (`new|enh` × `genai true|false`) each validate.

---

### EN4 — Regression QA class tied to baseline behaviors

**Why (Risk #4):** you cannot generate "existing behavior must still hold" tests from prose — the baseline must carry behaviors as **testable assertions**.

**Change:**
- `skills/pm-stage-06-qa-plan/SKILL.md`: in enhancement mode, emit a **regression** test-case class (`TC-REG-###`) sourced from baseline behaviors, distinct from the delta's `TC-###`.
- `lib/traceability.py`: index regression cases (additive; derived) so the handoff can carry them (EN5).

**Verification:**
- `test_enhancement_overlays.py` (extend): enhancement QA plan contains `TC-REG-###` traced to baseline behaviors; new-product QA plan contains none; regression cases are distinguishable in the spine.

---

### EN5 — Enhancement handoff payload (§3.3)

**Design:** carry the overlay's *last mile* to dev/QA. Additive to templates + delivery-map; **no state-machine touch**. Evidence-gated (build when the pilot's dev/QA usability check earns it).

**Change (`templates/handoff-story.md.j2` + `scripts/pm_share.py`):**
1. `change_type: new | modified` on each story/task (from the EN3 changed-behavior refs).
2. A **"Regression — must not break"** section (from EN4's `TC-REG-###`).
3. Baseline-derived **blast-radius/impact** (replace the current `_section_of(prd,"impact analysis")` passthrough with a baseline-aware impact view when in enhancement mode).
4. A **baseline backlink** (story → `00c`/baseline).

**Verification:**
- Extend `tests/integration/test_share_package.py`: an enhancement package's story files carry all four payload pieces; a new-product package is unchanged; `test_handoff_share_interop.py` still green (no collision regressions).

---

### EN6 — Baseline drift / incremental refresh

**Why (Risk #5 / efficiency):** the external product evolves under other teams; full re-scan each cycle is expensive.

**Change:** extend the existing codebase-drift signal (`scripts/pm_status.py`, Part A) so the baseline knows it's stale; refresh **only changed modules** rather than a cold re-scan.

**Verification:**
- `test_baseline.py` (extend): mutate the fixture repo → drift flagged; incremental refresh updates only the changed module's baseline section and re-stamps its provenance; unaffected sections keep their prior provenance.

---

### EN7 — Migration + end-to-end validation

**Change:** any `.meta.yaml` field added for the baseline/program backref goes through a `migrate_meta` block + `schema_version` bump (coordinate with Foundation F4's v5). Update `pm_os_verify` installed-skills check for the questionnaire skill. Document enhancement flow in `docs/guides/sop.md`.

**Verification (acceptance for the whole plan):**
- **End-to-end scratch run** against a fixture external repo: `/pm-new --mode enhancement --codebase <fixture>` → baseline (EN1) → questionnaire emit/import (EN2) → delta `02` scope with blast radius (EN3) → `03` PRD delta → `06` with `TC-REG` (EN4) → `08` TRD change-set → `/pm-handoff --package` carrying the payload (EN5). All gates behave; provenance visible throughout.
- Full `pytest` green; `pm_os_verify.py` green after sync; new tests docstring'd + cataloged in `docs/guides/testing.md`.
- **State machine untouched:** `test_stage_gates.py` + `test_approval_and_staleness.py` unchanged.

---

## Definition of done
- EN1–EN7 merged (EN3/EN5 gated on pilot evidence); end-to-end enhancement scratch run passes; new-product path byte-for-byte unaffected; provenance (C2) present on every reconstructed fact.
