# PM-OS Artifact Ingest & Mid-Pipeline Entry Plan

**Status:** ✅ **Implemented 2026-06-17** as `/pm-context-import` (command name chosen over `/pm-import` for readability). The realized design is broader than this plan's original per-stage file-import shape — see **§0 Implemented design** below. I0–I3 are delivered; I4 (dogfood a real Indegene enhancement) and `.docx`/`.pdf` conversion remain. Tracked as **Phase 2** in `docs/roadmap/current-state-review.md` §7.

---

## 0. Implemented design (what actually shipped)

The build went beyond per-stage file labels. The PM provides **all the context they have** (any mix), and PM-OS:

1. **Registers + preserves** every source (`.sources.yaml` registry + raw copies under `.history/`); logs `context_ingested`.
2. **Builds one gated context wiki** (`00-context-wiki.md`) — a normalized, provenance-tagged knowledge base the model reads as grounding for every downstream stage.
3. **Writes a gated understanding doc** (`00-context-understanding.md`) — human-facing synthesis: what it understood, how each source maps to the pipeline (adopt-as-stage vs. context-only), and a per-stage coverage map.
4. **Gate:** all three stage-00 docs — `00-business-statement.md` (now itself a normal gated stage), the wiki, and the understanding doc — must be `approved` before stage 01. The stage-01 gate names exactly which are still pending.
5. On approval, **adopts** the artifacts the PM authored (`origin: imported`) and **backfills** the upstream gaps below them (`origin: backfilled`), bottom-up, then hands back to the normal pipeline.

**Backfill feasibility map** (governs whether a missing upstream can be reconstructed; lives in `lib/project.py:resolve_backfill`, surfaced in the understanding doc):

| Gap | ✅ Faithful if provided | ⚠️ Lossy if best is | ⛔ Infeasible if best is |
|---|---|---|---|
| 01 Brief | 02 or 03 | 04 | 05 / 06 / 07 only |
| 02 Scope | 03 | 04 | 05 / 06 / 07 only |
| 03 PRD | — | 04 | 05 / 06 / 07 only |
| 04 Design | — | 05 | 06 / 07 only |
| 05 Prototype | — | 06 | 07 only |
| 06 QA plan | — | — | 07 only |

Only *provided* artifacts count as evidence — a reconstruction is never chained through another reconstructed artifact. An artifact whose chain has a ⛔ gap (e.g. a metrics plan alone) is **not adopted as a stage**; it stays in the wiki as context. This **overrides §10.4's recommendation to cap imports at stage 03** — any stage 01–07 may be provided.

Plumbing: `scripts/pm_context_import.py` (`register` / `preflight` / `commit`), `skills/pm-context-import/`, `lib/project.py` (schema_version 2 + `migrate_meta`, per-stage `origin`, stage-00 `00`/`00w`/`00u` group, `resolve_backfill`). `stage_imported` / `stage_backfilled` / `context_ingested` telemetry events.

---

### Original plan (per-stage file import — superseded shape, kept for history)

The remainder of this document describes the original `/pm-import NN <file>` shape. The mechanism that shipped generalizes it; the principles below (artifact-driven gate, write-to-approved precedent, gaps-backfilled-not-skipped, narrate-every-action) all still hold.
**Author:** Karan (with Claude Code)
**Date:** 2026-06-12
**Scope:** Let a PM plug *already-authored* artifacts (e.g. an existing scope and PRD) into a PM-OS project and continue the pipeline from that point, instead of regenerating every stage from scratch.

> You already did the work. PM-OS should adopt your existing scope/PRD as approved stage artifacts, fill any gaps in the chain, and let you run the remaining stages — without forking a single skill.

---

## 1. The gap this closes

The [modes & handoff plan](pm-os-modes-and-handoff-plan.md) added a *reality* axis (greenfield vs. existing-product, via reading the codebase). It still assumes **PM-OS authors every artifact** from stage 00 downward. That leaves a second, orthogonal axis unaddressed:

| Axis | Question | Status |
|---|---|---|
| Starting reality | greenfield vs. existing codebase | covered by modes plan |
| **Artifact origin** | **PM-OS generates upstream vs. PM already wrote it** | **this plan** |

Most enhancement work walks in holding a scope and PRD already. Forcing regeneration is wasteful and erodes trust ("it rewrote what I already approved with my stakeholders"). This plan adds an **ingest path** so existing documents become first-class stage artifacts.

---

## 2. Why this is low-risk: the architecture already does it

Two facts from the current code make ingest additive, not structural:

1. **The pipeline is artifact-driven, not session-driven.** The pre-stage gate (`hooks/pre-stage.py`, spec §6) only checks that each upstream artifact is `approved`/`edited` with a matching `content_hash`. It does **not** care *how* the file was produced. A generated `03-prd.md` and an imported one are indistinguishable to stage 04.
2. **"Write a file straight to approved" is an existing pattern.** `scripts/pm_new.py` already writes `00-business-statement.md` with `status: approved`, `content_hash: null`, `generated_hash: null` — PM-authored, never generated. Ingest generalizes that exact move from stage 00 to stages 01–03.

So nothing in the deterministic core (hashing, staleness cascade, telemetry, gates) changes. Downstream stages, staleness drift, and `/pm-status` keep working unmodified.

---

## 3. Where files come from and where they land

Ingest moves a document across two boundaries: your source location → the canonical stage slot, with the raw original preserved for provenance.

| | Source (yours) | Canonical slot | History snapshot |
|---|---|---|---|
| **Example path** | `~/Downloads/payments-prd.docx` | `~/pm-projects/<slug>/03-prd.md` | `.history/03-prd.<ts>.imported.md` |
| **Form** | your format, your structure | normalized to the stage's section template; `status: approved`; `content_hash` computed | raw original, untouched |
| **Lifecycle** | copied, never moved (your file stays put) | the file every downstream stage reads | provenance — what you actually handed in |

**Picked from:** anywhere on disk — you pass a path. The source is never assumed to live inside the project.
**Resides at:** the canonical `NN-name.md` slot inside `~/pm-projects/<slug>/`, exactly where a generated artifact would sit.

The `.history/...imported.md` snapshot mirrors the existing `.generated.md` convention, so the difference between "what I gave it" and "the normalized version it approved" is always recoverable.

---

## 4. The ingest steps (per file)

1. **Read + convert to markdown.** `.md` is verbatim. `.docx` / `.pdf` are converted to text first (this environment ships docx/pdf skills; pandoc is the fallback). Confluence/Notion → exported markdown or pasted text.
2. **Normalize** the content into that stage's section template (e.g. PRD → Overview / Goals & Non-Goals / User Stories w/ Acceptance Criteria / Functional / Non-Functional / Edge Cases / Risks). Map your headings onto PM-OS sections; never invent requirements that aren't in your source.
3. **Review gate.** Surface the normalized artifact for your confirmation that the reshaping didn't distort meaning. This *is* the approval gate — it keeps the human-in-the-loop guarantee intact.
4. **Write the slot:** `NN-name.md` with `status: approved`, computed `content_hash`, snapshotted `upstream_hashes_at_approval`. Copy the raw original to `.history/NN-name.<ts>.imported.md`.
5. **Update `.meta.yaml`** stage entry → `status: approved`; log a `stage_imported` telemetry event (see §7).

---

## 5. Two entry shapes

- **Per-file, into an existing project** — `cd` into the project, then run per stage:
  ```
  /pm-import 02 ~/Downloads/payments-scope.md
  /pm-import 03 ~/Downloads/payments-prd.docx
  ```
- **One-shot scaffold + seed** — create the project and ingest in a single call:
  ```
  /pm-new payments-enhancement "Improve checkout conversion" \
      --from-scope ~/Downloads/payments-scope.md \
      --from-prd   ~/Downloads/payments-prd.docx
  ```

`/pm-import` runs from the project root like every other stage skill. `--from-*` is sugar over the same code path inside `pm_new`.

---

## 6. The chain-gap problem (and the recommended fix)

Stage 04 reads 01 + 02 + 03. If you import only scope (02) and PRD (03), then `01-brief.md` is still `pending` and the gate blocks stage 04.

**Recommended: reverse-generate a thin `01-brief.md`** from the imported PRD/scope (problem framing, target user, why-now, success hypothesis — all derivable from a PRD), surfaced through the normal review gate. This keeps the dependency chain intact and the staleness model honest.

Rejected alternative: relaxing the gate to allow missing upstream. That punches a hole in the staleness guarantee for every project, not just imported ones — too high a cost for a one-off convenience.

Rule of thumb: **ingest may seed any stage, but the gate is never weakened — gaps below an imported stage are backfilled, not skipped.**

---

## 7. Telemetry: a new `stage_imported` event

Imported artifacts never went through `draft → approve`, so they have no edit-distance, time-to-approve, or regeneration metrics. Logging them as `stage_approved` would poison those signals in the feedback repo.

Add a distinct event so segmentation stays clean:

```
stage_imported: { source_format, source_filename, normalized: bool,
                  imported_hash, reverse_generated_upstream: [..] }
```

`/pm-status` shows imported stages with an `imported` marker rather than `approved`, so it's always visible which parts of the pipeline you authored vs. PM-OS generated.

---

## 8. User-facing messaging — narrate every non-obvious action (FYI requirement)

Ingest does things the PM can't see (format conversion, structural reshaping, gap-filling). Each must be surfaced as a plain **FYI** line so nothing happens silently. Minimum set:

- **Format conversion:** `FYI: converted payments-prd.docx → markdown (via docx skill).`
- **Normalization/reshaping:** `FYI: reshaped your 6 headings into the PM-OS PRD template. Your "Requirements" section was split into Functional + Non-Functional — review before approving.`
- **Reverse-generated upstream:** `FYI: you imported scope + PRD but no brief. I generated a thin 01-brief.md from your PRD to keep the chain intact — review it too.`
- **What was imported vs. left alone:** `FYI: imported 02-scope.md and 03-prd.md as approved. Stages 04–08 are still pending and will read these.`
- **Provenance:** `FYI: your original file is preserved at .history/03-prd.<ts>.imported.md.`

The review gate (§4 step 3) is where these land — the PM sees the FYIs, then explicitly approves. No silent rewrites, no silent conversions.

---

## 9. Composability with enhancement mode

This axis stacks on the modes plan cleanly. An enhancement where you also already have a PRD is just `project_type=enhancement` (codebase-understanding at stage 00) **plus** imported 02/03. The understanding doc grounds *reality*; the imported artifacts supply *decisions already made*. Downstream stages read both. No interaction beyond "more approved upstream inputs exist."

---

## 10. Open decisions to resolve before build

1. **Normalize vs. verbatim default.** Reshape to the PM-OS template (better for downstream stages, slight distortion risk) vs. ingest verbatim (faithful, but downstream stages may not find expected sections). **Recommendation: normalize, gated by the §4 review.**
2. **Status value for imports.** Reuse `approved`, or add a distinct `imported` status that behaves like `approved` at the gate but is visibly different in `/pm-status`? **Recommendation: keep `approved` on the artifact, mark `imported` only in `.meta.yaml` + telemetry** — avoids touching the state machine in spec §6.
3. **Source formats for v1.** `.md` only, or `.md` + `.docx` + `.pdf` from day one? **Recommendation: `.md` + `.docx` + `.pdf`** — those cover real PM artifacts and the skills already exist.
4. **Highest importable stage.** Cap at 03 (PRD) for v1, or allow seeding 04–07 too? **Recommendation: cap at 03 for v1** — the common case, and it bounds the backfill logic.

---

## 11. Plumbing changes

- New skill `skills/pm-import/SKILL.md` (+ `agents/openai.yaml` for cross-runtime parity).
- `scripts/pm_import.py` — read/convert/normalize/write one artifact to an approved slot; backfill missing upstream; log `stage_imported`.
- `scripts/pm_new.py` — add `--from-scope` / `--from-prd` (call into `pm_import` after scaffolding).
- `lib/telemetry.py` + spec §6 event list — register `stage_imported`.
- `scripts/pm_status.py` + spec §7.7 — render the `imported` marker.
- Spec §2 / §6 / §13 — document the ingest path and the "gaps backfilled, gate never weakened" rule.

**Risk:** low. Reuses the `00-business-statement.md` write-to-approved precedent and the artifact-driven gate; the deterministic core is untouched.

---

## 12. Sequencing

| Phase | Work | Depends on |
|---|---|---|
| **I0** | `pm_import.py` core: ingest `.md` → normalize → review gate → approved slot + `.history` snapshot; `stage_imported` event | — |
| **I1** | `/pm-import NN <file>` skill; FYI messaging (§8); `/pm-status` `imported` marker | I0 |
| **I2** | Backfill: reverse-generate missing upstream (the brief gap, §6) | I1 |
| **I3** | `.docx` / `.pdf` conversion; `/pm-new --from-scope/--from-prd` one-shot | I1 |
| **I4** | Dogfood one real Indegene enhancement: import an existing scope+PRD, run 04→08 | I2, I3 |

---

## 13. Acceptance criteria

- [ ] `/pm-import 03 <file.md>` writes `03-prd.md` with `status: approved`, a computed `content_hash`, and a `.history/03-prd.<ts>.imported.md` snapshot of the raw original.
- [ ] Importing scope + PRD without a brief reverse-generates a `01-brief.md` through the review gate; the chain to stage 04 is unbroken.
- [ ] Every non-obvious action (conversion, reshaping, reverse-generation, provenance path) is surfaced as an FYI before approval; nothing happens silently.
- [ ] `stage_imported` is logged (not `stage_approved`); edit-distance/time-to-approve signals are not polluted.
- [ ] `/pm-status` visibly distinguishes imported stages from generated-then-approved ones.
- [ ] Downstream stages (04–08) read imported artifacts identically to generated ones — no skill forking, no gate changes.
- [ ] `.docx` and `.pdf` sources convert correctly; `/pm-new --from-scope/--from-prd` scaffolds and seeds in one call.
- [ ] No regression to greenfield generate-from-scratch behavior, hashing, staleness, or telemetry semantics.

---

End of plan.
