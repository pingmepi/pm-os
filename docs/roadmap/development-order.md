# PM-OS Development Order

**Date:** 2026-07-28 · **Status:** Living sequencing plan.

This is the single home for **build sequencing** across all open work. It does not re-describe items — it orders them. Item detail lives in the trackers:

- Verified defects/gaps → `backlog.md` (referenced as `#N`)
- Delivery-model & handoff design → `../plans/pm-os-modes-delivery-and-handoff-plan.md` (phases `B0`–`C4`)
- Lifecycle/roadmap gaps & phase plan → `current-state-review.md` (§3 "Roadmap-level lifecycle gaps", §7 phases)

## The dividing line

- **Necessary to the current state** — a defect or missing guarantee in something PM-OS *already ships and claims to do*. Fixing it makes the current product (a local-first product-definition + traceability + Jira-handoff tool) correct, trustworthy, and operable. **No new scope.**
- **Roadmap** — adds capability or lifecycle coverage PM-OS *does not currently claim*.

**Sequencing principle: finish the current product first, then expand.** Conveniently, the necessary P1 work (`B0`, `#19`, `#20`, `#27`) *is also* the foundation the roadmap's delivery model depends on — so closing out the current thing tees up the expansion rather than competing with it.

---

## Part 1 — Necessary to the current state (do first)

### Recommended order

| # | Item | Why necessary | Depends on |
|---|---|---|---|
| 1 | **#18 (local half)** — `git init` per project ✅ **shipped** | Every approved decision lives on one laptop with no version history; the local half needs nothing external. `lib/project_git.py` — init+commit at scaffold, commit on approval. | — |
| 2 | **B0** — reconcile epic/story/task export mapping ✅ **shipped** | Stage 03 now declares Product Epics (`EPIC-###`) and both shipped exports use the same Jira-native mapping: `EPIC-###` items are Epics, `US-###` items are Stories, `FR/REQ-###` items are Tasks, and `TSK-###` items become Subtasks when they implement exactly one exported item. This unblocks the roadmap's tier/increment work. | — |
| 3 | **#19** — prioritization value + method block | Stage-03 already *claims* "stories in priority order" with nothing to back it. Makes a current claim honest; unblocks #10; foundation for tiers. | — |
| 4 | **#20** — stage-08 TRD required-section contract | The TRD is now load-bearing (TSK ids, Jira export) yet the least-validated artifact. WARNING-only + `CONTRACT_VERSION` bump. Unblocks increments. | — |
| 5 | **#27** — labeled-field contracts | Contracts match vocabulary, not meaning — the root cause behind #11/#12/#5. Retires the bug class; generalizes the labeled-field pattern #19/#20 use. Larger change. | (best after #19/#20 so their fields ride the same bump) |
| 6 | **#5** — design-spec ↔ PRD divergence | A spec contradiction reached the prototype uncaught. #27's structural fields make this class checkable. | #27 (shrinks its surface) |
| 7 | **#10** — stage-05 slice auditability | The current prototype-slice choice isn't auditable or repeatable. | #19 (declared priority) |
| 8 | **#25** — deterministic / validated `.history` | Agent-written lineage is never checked, silently corrupting current approval-quality metrics. Touches all 9 stage skills; warn-not-fail. | — |

### Lower-priority integrity/operability (slot in opportunistically)

- **#2** — Windows install/runtime remainder (**necessary only if Windows is a current target**; needs a real Windows box + a shell-standardization decision: Git Bash + shim vs `install.ps1`).
- **#4** — downstream-vs-upstream consistency check (backlog defers this — "consistent with the current hash-based model").
- **#14** — deep-reasoning model gate is bypassable with a bare re-run.
- **#15 / #16 / #24** — migration backfill of missing stages, backfilled-approve provenance, `.meta.yaml` concurrency lock. P3 robustness.

---

## Part 2 — Roadmap (expansion, after the current product is closed out)

### 2a. Delivery model (#28 build-out — the headline new capability)
Unblocked by the Part 1 foundation (`#19`, `#20`, `B0`).

`B1` scope tiers → `B2` tiered fidelity + `/pm-promote` → `B3` delivery increments → `C1` `--increment` Jira scoping.

### 2b. Design & external handoff
- `C2` Figma *pull* (ground the design spec in real tokens) → `C3` Figma *push* (frames from the prototype brief).
- `C4` **design-token → React codegen** — blocked on the partner token system; slots in whenever that contract is published.
- `/pm-handoff linear` — a second create adapter over the existing tracker-agnostic map.

### 2c. Self-improvement loop & observability
Tied to the *unbuilt* self-improvement loop (`current-state-review.md` §10 item 10).
- **#23** product decision record → **#26** relabel "quality" metrics (activity/satisfaction, not correctness). #26 depends on #23.
- **#13** per-stage token telemetry (depends on runtime token introspection).
- **#9** context-pack per-stage views — an optimization, not a correctness fix.

### 2d. New lifecycle phases
- Phase 5 — QA bug triage + dev fix guidance.
- Phase 6 — release readiness + feedback intake.

### 2e. Lifecycle-coverage gaps (`current-state-review.md` §3)
Discovery/research stage · regulatory/MLR gate · commercial/services layer · localization/UX-writing · metrics-late/feasibility-late ordering. Several need a product decision before code. **#21** (multi-approver) becomes real work only if the regulatory gate forces it.

---

## Not on the build path (explicit boundary)

- **#22** — time/effort/capacity/velocity: deliberately owned by development and the tracker, not PM-OS.
- **#21** — single approver: by design for the single-PM v1; listed under 2e only as a regulatory-gate dependency.

---

## Blocked / needs a decision before build

| Item | Blocked on |
|---|---|
| #18 off-machine half | Indegene-owned git hosting (one IT request; reuse the telemetry-sink namespace) |
| #23 → #26 | A decision on *what* a product-decision record captures at approval time without adding gate friction |
| C4 | Partner team publishing a stable design-token → React-component mapping |
| Regulatory/MLR gate + #21 | Product decision on multi-party sign-off model |
| #13 | Whether the agent runtime can introspect its own token usage mid-skill |
| #2 | A real Windows box + shell-standardization decision |
