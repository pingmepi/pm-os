# PM-OS Consistency Spine & v1.4.1 Fixes Plan

**Status:** 🟡 In progress (2026-08-01). **The seven v1.4.1 defect fixes (A.0, backlog #30–#36) are implemented and green** on branch `fix/v1.4.1-consistency-defects` — full suite **341 passing**; #31 shipped the *detector* (`DOWNSTREAM_UPSTREAM_STALE`), its atomicity refactor half deferred. A.1–A.4 (the general consistency spine) are designed here, not yet built.
**Author:** Karan (with Claude Code)
**Entry-pathways work** (formerly bundled here as "Thrust B") now lives in its own plan: `pm-os-entry-pathways-plan.md`. This doc is the consistency-spine + fixes half only.
**Supersedes / ignores:** the `feat/whole-product-foundation` branch (scope-tier / increment / promote work) — abandoned as buggy per PM decision. Its Part B *design* still lives in `pm-os-modes-delivery-and-handoff-plan.md`; this plan does **not** depend on that branch's code.

**Why this exists:** cross-cutting requirements introduced in skill prose (e.g. "add TRD tasks to each story file") were enforced only by LLM diligence, not a hard check — so they silently missed stages. This plan makes the checks structural, and fixes the v1.4.1 defect cluster that pain produced.

---

## A.0 — The v1.4.1 defect cluster (done, TDD)

Seven defects verified against the shipped v1.4.1 code, logged as backlog #30–#36, each fixed test-first with a regression test cataloged in `docs/guides/testing.md`:

| Backlog | Defect | Fix |
|---|---|---|
| #30 | `/pm-check` reports every generated snapshot "unreadable" — `hash_artifact_body` called but never imported (`lib/consistency.py`) | add the missing import |
| #31 | Partial-approval invalid state — approve→cascade not atomic; `upstream_hashes_at_approval` written but read nowhere | **detector shipped** (`DOWNSTREAM_UPSTREAM_STALE` in `/pm-check`, consuming the field); atomicity refactor deferred |
| #32 | Traceability drops `NFR-###` ids — `REQUIREMENT_ID_RE` had no NFR arm and `\d{3,}` rejected short forms | NFR arm + flexible digits (existing arms unchanged) |
| #33 | Invalid YAML frontmatter in generated story files — unquoted title/priority | serialize frontmatter with `yaml.safe_dump` |
| #34 | Business epic files link to a `stories/` folder that audience never gets | plain-text story refs for audiences without stories |
| #35 | Global IA prose leaks into story screen slices — loose block boundary | render-time screen-body trim in `pm_share.py` |
| #36 | Per-story screen scope journey-inflated | prefer-direct attribution; journey fallback only for journey-only screens (QA half was unconfirmed — not changed) |

**Remaining from #31:** the atomicity refactor (make approve+cascade atomic / `post-approve.py` idempotent) so the invalid state can't be *created*, not only detected. Deferred as a core-state-machine change; the detector already makes it visible and repairable.

## A.1 — Declarative invariant registry (designed)

A cross-cutting requirement lives in two places that drift apart — skill prose and the validator (`lib/artifact_contracts.py`). Nothing binds them. Today's cross-cutting checks (`_check_trd_task_ids`, `_check_screen_ids`, `_validate_journey_references`) are each hand-written for one relationship. **Proposal:** one declarative registry (`lib/generation_invariants.py` or YAML) listing each cross-cutting rule as data — *"`TSK-###` backend refs must appear in every `US-###` story block in the dev handoff"* — that the checker reads and reports **exactly which stages/blocks are missing it**. #31's invariant is the flagship first entry.

## A.2 — Propagation / coverage matrix (designed)

For every ID relationship meant to flow (US→TSK, journey→SCR, requirement→test, requirement includes `NFR-###`), verify **full bidirectional coverage** and report orphans + gaps in one matrix. Builds on `lib/traceability.py`. #32 (NFR) and #36 (screen attribution) are coverage-matrix cases.

## A.3 — Contract-lint meta-check (designed)

A suite test that scans skill prose for declared cross-cutting requirements and **fails if any lacks a registry entry** — closing the prose↔checker drift permanently. Would have caught #30 (an invariant referencing an unimported symbol) at test time.

## A.4 — Generation self-check as a gate (designed)

`scripts/pm_validate_artifact.py --strict` already runs at generation for stages 03–05. Extend it to run the A.1/A.2 checks at generation for every stage that produces or consumes a cross-cutting element, so a miss is caught immediately. Read-only/advisory; no gate/hash/staleness change.

---

## Entry pathways (separate plan)

The three entry pathways (idea / prototype / live-product) and the interview primitive are a distinct thread. Full, buildable design: **`pm-os-entry-pathways-plan.md`** (pathway 2 first, per PM decision 2026-08-01). Sequencing note: the consistency spine (A.1–A.4) is the guardrail that makes the entry work's interview-driven backfill trustworthy — three of the v1.4.1 defects (#30/#32/#31) are the "no hard cross-artifact check" problem in miniature — so A before B where they overlap, but the pathway-2 interview does not hard-depend on A.1–A.4 and can proceed in parallel.

## Sequencing (this plan)

1. **A.0** — v1.4.1 defect fixes (#30–#36). ✅ **done** (341 passing; #31 atomicity deferred).
2. **A.1 + A.2** — invariant registry + coverage matrix (seeded by #31/#32/#36).
3. **A.3** — contract-lint meta-check (locks the drift shut).
4. **A.4** — generation self-check gate.
5. **#31 atomicity refactor** — slot in when the core-state-machine change is worth it.

All engine changes land via commit → push → `pm_os_update.py`; never hand-modify the install.

---

End of plan.
