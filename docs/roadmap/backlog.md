# PM-OS Backlog

Tracked issues and fixes, surfaced during testing/rollout prep. Newest concerns first.
Status legend: 🔴 open (blocking/critical) · 🟠 open (lower urgency) · 🟡 partially fixed · 🟢 fixed (pending release).

---

## 1. 🟢 Edited-upstream re-approval gate is auto-answered by the agent (human-in-the-loop bypass)

**Severity:** P0 — undermines the core "PM approves every step" guarantee.
**Status:** **Fixed** (this change), pending release.

**Symptom:** A PM edits an already-approved upstream artifact (e.g. `00w` context wiki), then runs the next stage (`01`). The gate detects the edit and reports "edited after approval," but the stage **just runs** — the PM is never actually asked to re-approve.

**Root cause:** `hooks/pre-stage.py` correctly detects the drift and prints the `[1] Continue / [2] Re-approve / [3] Cancel` menu, then calls `read_edited_choice()`. That function only prompts a **human at a TTY**. Inside Claude Code/Codex the gate runs in a non-interactive shell (`stdin` is not a TTY), so instead of asking it exits with an error message that *literally tells the agent how to bypass it*: "Set `PM_OS_EDITED_UPSTREAM_CHOICE=continue` …". The agent reads that, sets the env var, re-runs, and the edit is **implicitly re-approved by the agent, not the PM**. Downstream stages cascade stale as a side effect.

**Evidence:** `hooks/pre-stage.py:25-57` (`read_edited_choice`, non-TTY branch) and `:151-199` (implicit-reapproval path). Confirmed live: `00w` edited → `01` run → telemetry shows `stage_edited_post_approval` immediately followed by `implicit_reapproval` with no human action.

**Proposed fix:** Decouple "genuinely unattended" runs from "interactive agent session." When an upstream is edited and there is no human TTY, the gate should **block** and the skill should **surface the choice to the PM in chat** ("`00w` changed since approval — re-approve it? `/pm-approve 00w`"), requiring an explicit human action. Reserve `PM_OS_EDITED_UPSTREAM_CHOICE` for true cron/CI use only; the gate's error message must stop instructing the agent to self-bypass.

**Fixed (this change):**
- `hooks/pre-stage.py` non-TTY branch no longer prints the `Set PM_OS_EDITED_UPSTREAM_CHOICE=continue` hint. It now **blocks** and routes the decision to the PM (`/pm-approve <NN>`), explicitly telling the agent to STOP and not re-approve on the PM's behalf. The env var is still honored *if already set* (CI/cron escape) but is no longer advertised to the agent.
- All 9 stage skills (`pm-stage-01…09/SKILL.md`) now carry an explicit instruction next to the gate: on an edited upstream, do **not** set the env var or self-approve — surface the changed stage to the PM and wait for `/pm-approve` or an explicit human go-ahead.
- Test renamed/updated: `tests/integration/test_stage_gates.py::test_non_tty_without_choice_routes_to_pm` asserts the block routes to `/pm-approve` and that `PM_OS_EDITED_UPSTREAM_CHOICE` is *not* present in stderr. `test_implicit_reapproval_continue` still verifies the CI escape works when the var is set. `docs/guides/testing.md` updated to match.

---

## 2. 🟡 Windows-friendly install + runtime

**Severity:** P1 — every Windows PM hits this; blocks Windows rollout.
**Status:** Partially fixed (see below); remainder open.

**Symptom (as observed):** On Windows, `python3` does not exist (Python installs as `python` / `py`). The `post-approve` hook failed with Windows error **9009 (command not recognized)** even though a `python3` shell alias was set up — because the alias does not propagate into Python `subprocess` calls. The failed hook left `.meta.yaml` upstream-hash bookkeeping inconsistent, producing false "edited"/"stale" flags on subsequent gate runs.

**Fixed now (this change):**
- The 3 internal `subprocess.run(["python3", …])` calls now use `sys.executable` so hooks run under the same interpreter that launched the script — fixes the 9009 cascade. `scripts/pm_approve.py:151`, `scripts/pm_context_import.py:247`, `scripts/pm_os_verify.py:157`.
- `install.sh` now resolves the interpreter (`python3` → `python` → `py -3`) and uses it throughout, so a Git-Bash install no longer hard-requires a literal `python3`.

**Still open:**
- **24 skill-inline `python3 …` invocations** in `skills/**/SKILL.md` (e.g. `PM_OS_STAGE=03 python3 ~/.pm-os/hooks/pre-stage.py`) still assume `python3` resolves *and* use bash-only `VAR=val cmd` env-prefix syntax — which breaks under **PowerShell** (the shell Claude Code used on the test machine).
- **Shell standardization decision needed:** require Git Bash on Windows (then only `python3` resolution remains — solvable via an installer-created shim) **vs.** make skills shell-portable + ship an `install.ps1`. Recommendation: **standardize on Git Bash + installer shim** (lowest blast radius; CC already prefers Git Bash on Windows).
- No `install.ps1` exists; `install.sh` is bash-only.

**Note:** Must be tested on a real Windows box — cannot be verified from macOS.

---

## 3. 🟢 Recursive folder import for context folders

**Severity:** P2 — silent incompleteness; PM could believe a folder was fully ingested when subfolders were missed.
**Status:** **Fixed** (this change), pending release.

**Symptom:** `/pm-context-import <folder>` did not reliably ingest files in **subfolders**. The skill never specified recursion, and the script registered one file at a time, so coverage of nested folders was left to the agent's discretion — inconsistent and silent.

**Fix:** `scripts/pm_context_import.py register` now accepts a folder and walks it **recursively**, registering every document file (`.md/.txt/.pdf/.docx/.doc/.rtf/.csv/…`) across all subfolders, skipping engine/OS cruft and non-document files, and printing a coverage summary (`Registered N file(s) across M folder(s)…`) plus the skipped list. `skills/pm-context-import/SKILL.md` Inputs + Step 1 updated to use folder recursion and surface coverage/skips as FYIs.

---

---

## 4. 🔴 Downstream artifact edits are never checked against approved upstream content

**Severity:** P2 — silent correctness gap; a PM's direct edit can drift a downstream artifact out of sync with an approved upstream decision with no system signal, unlike the upstream→downstream direction, which *is* caught.
**Status:** 🔴 Open — no code path exists to close it; the `--note` conflict check is the only semantic check in the system, and it's scoped narrowly.

**Symptom:** Observed during a v1.0.8 `--upgrade-pack` re-run of the `repassist` project. PM-OS gating is purely hash/state-based and enforces one direction only — upstream edit → downstream stale. There is no check in the reverse direction: editing a downstream draft (e.g. `02-scope.md`) never validates that its content stays consistent with an approved upstream (`01-brief.md`). A PM can edit scope to contradict the brief's target user / success hypothesis and nothing surfaces it — not on save, not at `/pm-approve`, not at the next stage's `pre-stage.py` gate (which only recomputes upstream hashes for drift + approval state), and not in `/pm-check` (structural only).

**Evidence:**
- `scripts/pm_approve.py:71-169` — approval flow reads frontmatter status, computes/writes content hashes, and snapshots `upstream_hashes_at_approval`, but never reads an upstream artifact's body for meaning.
- `hooks/pre-stage.py:141-192` — the gate recomputes upstream body hashes and compares them for drift; pure hash comparison, no content diffing.
- `lib/consistency.py:90-97` (used by `/pm-check`) — runs exactly 7 structural checks (schema/stage shape, artifact presence, meta/frontmatter sync, body hash drift, upstream approval shape, telemetry chain, context YAML parsing); none open two artifact bodies and compare their meaning.
- `skills/pm-stage-02-scope/SKILL.md:59-89` (and the equivalent section in every other stage `SKILL.md`) — the only semantic reasoning anywhere in the system: an LLM-instruction-driven "upstream-conflict check," but it fires only when a `--note` is supplied at generation time, never for a direct hand-edit of a downstream artifact.
- `docs/reference/pm-os-spec.md:4,556-562` — self-documents that an embedding-based semantic-distance capability was designed but deliberately never built.

**Current partial cover:** The `--note` path does run an upstream-conflict check against the approved brief (or relevant upstream). A direct file edit bypasses it entirely.

**Proposed fix (for future consideration, not scoped now):** Extend the same agent-driven upstream-conflict-check pattern already used for `--note` handling to run generally at `/pm-approve` time (not just when a note was supplied) — consistent with the codebase's philosophy that judgment lives in `SKILL.md` prompts, not Python ("Skills carry instructions and prompts; Python carries mechanical state" — `CLAUDE.md`). Should remain a non-blocking advisory so the PM retains final call, mirroring the existing `--note` 3-way choice UX.

**Note:** Not a bug — consistent with the current hash-based model. Decision on whether to close this gap is deferred; this entry exists so it isn't lost. (Logged during a demo-project run as **IMP-002**; shares its root cause with entry #5 / **IMP-001** below — both stem from the same "no cross-artifact consistency checking" gap.)

---

## 5. 🔴 Design spec can silently diverge from the PRD, and from itself (IMP-001)

**Severity:** P1 — a spec contradiction reached the prototype stage before it was caught; it was only visible once built, not on paper.
**Status:** 🔴 Open.

**Symptom:** During a demo-project run, stage-04's design spec specified empty-submit → "blocked with hint," while the PRD's Edge Cases section specified empty → low-confidence recovery — two behaviors for the same event, unreconciled between stages. Separately, the same spec placed example text in an input's placeholder while its own accessibility rule stated inputs must be "not placeholder-only" for discoverability — an internal self-contradiction within stage 04 alone.

**Evidence:** PM-observed during a demo run; not yet traced to specific `skills/pm-stage-04-design-spec/SKILL.md` lines or `lib/artifact_contracts.py` checks in this session — needs a follow-up pass through the stage-04 skill and its cross-reference logic (see `lib/artifact_contracts.py`'s ID-matching checks, entry #4/IMP-002 evidence) to confirm whether this class of contradiction is checkable at all today.

**Proposed fix:** Stage-04's self-check should (a) explicitly reconcile input empty/invalid behavior against the PRD's Edge Cases section before the spec is presented as complete, and (b) require a first-use discoverability affordance for any input that isn't placeholder-only, checked against the spec's own accessibility rules. Shares its root cause with entry #4 (**IMP-002**: no cross-artifact/cross-section consistency checking) — a general upstream-conflict-style check at stage-04 generation/approval time would likely catch both the PRD-vs-spec and spec-vs-itself cases.

---

## 6. 🟠 `pm_approve` is slow and CPU-heavy (IMP-003)

**Severity:** P1 — UX; re-approvals took ~3 minutes at 99% CPU during a demo run.
**Status:** 🟠 Open.

**Symptom:** Re-approvals were dominated by the git + central-sync push step. When backgrounded, the process looked hung, and a partial-output read made it look like something had failed — even though the underlying approval state was actually correct by the time the sync finished.

**Evidence:** PM-observed during a demo run; the sync push is invoked from `hooks/post-approve.py` via `lib/git_sync.py` (per `CLAUDE.md`'s architecture notes on the gate flow) — the exact hot path (git operations vs. Python overhead) hasn't been profiled in this session.

**Proposed fix:** Make the telemetry/feedback sync push async or deferred relative to the approval itself, or surface progress output so a slow sync doesn't read as a hang. A network push should not gate the perceived completion of `/pm-approve`.

---

## 7. 🟠 Editing an already-approved artifact requires a clunky "drift dance" (IMP-004)

**Severity:** P1 — UX friction on a core, frequently-used workflow (revising an approved stage).
**Status:** 🟠 Open.

**Symptom:** `pm_approve` refuses to act on a stage that's already `approved`, so re-approving an intentional PM edit requires first running a *downstream* stage's `pre-stage.py` gate to flip the edited stage's status to `edited` before `/pm-approve` will accept it. Compounding this, the gate's non-interactive message (see entry #1's fix) tells the agent to "STOP — do not re-approve on the PM's behalf" — appropriate when the agent detects the edit unprompted, but the same wording fires even when the PM has explicitly and directly authorized the edit in the current conversation.

**Evidence:** `hooks/pre-stage.py` non-TTY STOP branch (per entry #1, `hooks/pre-stage.py:151-199` as of that fix); `scripts/pm_approve.py`'s status guard, which requires `draft`/`edited` and rejects `approved` (see `pm_approve.py:71-83` per entry #4's evidence).

**Proposed fix:** Add a direct `/pm-approve --reapprove` path that detects hash drift against the stage's own last-approved snapshot *within* `pm_approve.py` itself, without requiring a downstream stage's gate to run first. Also soften the STOP wording to distinguish "agent detected this unprompted, stop and ask the PM" from "the PM already sanctioned this edit in this session" — the latter shouldn't require the same friction.

---

## 8. 🟡 Telemetry stamps the project-pinned `pm_os_version`, not the runtime version (IMP-005)

**Severity:** P3 — provenance/observability nuance, not correctness-blocking.
**Status:** 🟡 Confirmed behavior this session; fix agreed but not yet implemented.

**Symptom:** Telemetry events for a demo-project run recorded `pm_os_version: 0.5.12` (the project's "created-with" version) while the installed runtime was actually `1.0.8`.

**Evidence:** `lib/telemetry.py:33` stamps every event from `meta.get("pm_os_version", "0.1.0")` — a value written once at `pm-new`/install time (`scripts/pm_new.py:89-90,157`) and never refreshed thereafter. Confirmed live drift on disk: `~/pm-projects/bill-checker/.meta.yaml` shows `pm_os_version: 0.3.0` against an installed `VERSION` of `1.0.8`. `scripts/pm_status.py:34-37` already computes a live-vs-pinned comparison, but only for human-facing display output — it's never wired into telemetry.

**Proposed fix (agreed this session, not yet implemented):** Add a second field, `pm_os_version_runtime`, to the telemetry payload — read from `~/.pm-os/VERSION` at log time — alongside the existing `pm_os_version` (kept as-is, as pinned "created-with" provenance). Additive, backward-compatible, no schema break.

---

## 9. 🟡 Whole context pack rides along every stage — unused per-stage routing (IMP-006)

**Severity:** P2 — token/cost inefficiency, not a correctness issue.
**Status:** 🟡 Partially built (the manifest field exists but is unused) — open.

**Symptom:** The context pack manifest's `stage_affinities` field is empty, and the adaptive `views/` mechanism is a deferred phase, so the full ~4.7k-token pack loads into all 6 stages with no per-stage filtering — every stage pays the token cost of the entire pack regardless of relevance.

**Evidence:** PM-observed during a demo run; the manifest schema location and `stage_affinities` field definition haven't been traced to specific file:line references in this session — needs a follow-up read of the context-pack manifest schema (likely under `lib/` or `context.example/`) to confirm the exact shape before implementing.

**Proposed fix:** The earlier-agreed views experiment — populate `stage_affinities` in the manifest and generate per-stage `views/`, so each stage loads only its relevant slice of the pack instead of the whole thing.

---

## 10. 🟠 Stage-05 prototype slice selection is not auditable (non-deterministic, judgment-only)

**Severity:** P2 — traceability/reproducibility gap. Not a correctness bug; the slice picked is always *valid*, just not *auditable* or repeatable.
**Status:** 🔴 Open.

**Symptom:** Stage 05 chooses *which* slice of the approved design to prototype by LLM judgment against a prose objective — "smallest slice that can answer the highest-risk product and design questions" (`skills/pm-stage-05-prototype-brief/SKILL.md:13,177`). "Highest-risk" is nowhere declared: there is no `risk`/`prototype-priority` field on `UJ-###` journeys, so the model *infers* risk from upstream prose each run. Two runs on the same inputs can pick different slices, and there is no recorded, rankable basis for why one journey made the slice and another didn't.

**Evidence:**
- `skills/pm-stage-05-prototype-brief/SKILL.md:13,177` — the selection objective is prose ("smallest useful slice" / "highest-risk questions"), no scoring input.
- `skills/pm-stage-05-prototype-brief/SKILL.md:132-134,158-160` — the brief must *justify* the slice ("state why this slice is the right one") and map questions to screens, but this is free-text rationale, not a machine-checkable link to a declared priority.
- `scripts/pm_validate_artifact.py 05` + self-check (`SKILL.md:303,317`) — validates the slice is **bounded** and **references `UJ-###`**, i.e. checks *shape, not correctness of the choice*. Nothing asserts the slice covers the highest-priority journeys.
- No `risk`/`priority` field exists on journeys in the PRD (03) or design-spec (04) contracts (`lib/artifact_contracts.py`).

**Proposed fix (spine, not state machine):** Make risk a *declared, upstream* attribute the slice selection can be audited against — additive to the traceability spine, no gate/hash/status change:
1. Add an optional `prototype_priority` (or `validation_risk`: high/med/low) tag to `UJ-###` journeys in the 03/04 contracts.
2. Stage 05 sorts the candidate pool by that tag and records, in "What to Prototype," the explicit inclusion/exclusion decision per journey (`UJ-003 included — high risk; UJ-007 excluded — low risk, deferred`).
3. Extend the 05 self-check / `pm_validate_artifact.py` to assert every high-priority journey is either in the slice or has a stated exclusion reason — turning "smallest slice answering highest-risk questions" from a judgment into a rankable, checkable selection.
4. PM `--note` remains the override lever; overrides get logged as provenance.

**Note:** Surfaced 2026-07-14 while reviewing how 05 decides the slice. Keeps PM authority (priority is a PM-set upstream signal); makes the slice decision reproducible and auditable. Consistent with the product-shape principle "grow the traceability spine, not the state machine."

---

_Recorded 2026-06-20 during v0.5.6 rollout testing (entries 1-3); entry 4 recorded 2026-07-09 (IMP-002); entries 5-9 recorded 2026-07-09 during a demo-project run (IMP-001, IMP-003 through IMP-006); entry 10 recorded 2026-07-14 while reviewing stage-05 slice selection. All documentation-only unless noted. Changes above land via the normal commit → push → `pm_os_update.py` path; they are inert until then._
