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

## 11. 🔴 Validator and traceability builder disagree on what counts as a `TC-###` declaration (IMP-007)

**Severity:** P1 — a QA plan that passes every contract check can still silently contribute nothing to `.traceability.yaml`. The failure is invisible: no error, no warning, just an empty spine.
**Status:** 🔴 Open. Verified against the current codebase (not just observed).

**Symptom:** `lib/artifact_contracts.py` has two different extractors for `TC-###` ids that disagree on what "declares" a test case:
- `test_case_ids()` — the **loose** extractor (`TEST_CASE_ID_RE = r"\bTC-\d{3,}\b"`), used by stage-06's `TEST_CASE_IDS_MISSING` check. It matches a `TC-###` anywhere in the text, including inside Markdown bold (`**TC-001**`), since `\b` word boundaries sit on either side regardless of the `*` characters.
- `split_test_case_blocks()` — the **strict**, line-anchored extractor (`_TC_BLOCK_START_RE`, requires the id to start the line after at most a heading/bullet/ordered-list marker). Used by stage-06's `TEST_CASE_TRACE_MISSING` check **and** by `lib/traceability.py`'s `build_index()` — the function that populates `.traceability.yaml`.

A QA plan that writes scenarios as `- **TC-001:** <description>` (bold-wrapped id after the bullet) passes both stage-06 checks — `test_case_ids()` finds `TC-001` (no `TEST_CASE_IDS_MISSING` error), and `split_test_case_blocks()` returns an **empty dict**, so `TEST_CASE_TRACE_MISSING`'s guard (`if tc_blocks and untraced`) short-circuits false and never fires either. The plan looks completely clean. But `build_index()` calls the same `split_test_case_blocks()`, gets the same empty dict, and writes `.traceability.yaml` with `test_cases: {}` — the whole spine is silently empty.

**Verified reproduction:**
```python
qa_text = "- **TC-001:** Verify ranked results exclude expired assets. Covers REQ-001."
test_case_ids(qa_text)          # -> ['TC-001']   (validator: looks fine)
split_test_case_blocks(qa_text) # -> {}            (traceability + trace-check: empty)
```

**Related, same root cause:** `_TC_SECTION_BREAK_RE` (the block-boundary stop condition) only breaks on `##`-level headings, not `###`. A non-TC `###` subsection interleaved between two test cases (e.g. an editorial `### Metrics and compliance evidence` heading with no TC- id) gets silently absorbed as trailing content of the *preceding* TC's block instead of ending it — confirmed live in `~/pm-projects/repassist/06-qa-plan.md:170`, between `TC-017` and `TC-018`. Harmless there only because the absorbed heading happened to be empty; a subsection with real content would bleed into the wrong TC's body.

**Evidence:** `lib/artifact_contracts.py` — `TEST_CASE_ID_RE` (loose), `_TC_BLOCK_START_RE`/`_TC_SECTION_BREAK_RE` (strict), `_validate_stage_06`; `lib/traceability.py:build_index()` (shares the strict extractor with the validator, not the loose one the "is this QA plan valid" gate actually uses).

**Proposed fix:** Make the strict, line-anchored extractor tolerant of a bold-wrapped id immediately after a bullet/heading marker (`[-*+]\s+\*{0,2}TC-\d{3,}` style), and make `TEST_CASE_IDS_MISSING` use the **same** extractor `split_test_case_blocks` uses — one extractor, not two, so "the contract says valid" and "the spine actually links it" can never disagree. Separately, make `_TC_SECTION_BREAK_RE` also stop at `###` headings so non-TC subsections never get absorbed into an adjacent TC's block.

---

## 12. 🔴 `pm_handoff.py` mis-renders contract-valid PRD/QA formats (IMP-008)

**Severity:** P1 — pre-merge (found dogfooding the branch behind [PR #30](https://github.com/pingmepi/pm-os/pull/30), not yet installed anywhere). Two distinct, verified bugs in the new handoff generator; both make a fully-traceable pipeline render `— not captured in source —` for content that genuinely exists upstream — exactly the honesty-signal the generator is supposed to preserve, now giving false negatives instead.
**Status:** 🔴 Open.

**Bug A — single-line TC bodies get stripped to empty.** `scripts/pm_handoff.py`'s `_strip_decl_line()` assumes every `split_test_case_blocks()` block has its declaration on its own line and body text on the lines that follow (`lines[1:]`) — true for a `### TC-001` heading block, false for the equally contract-valid single-line-bullet style QA plans commonly use (`- TC-001: <description>. Covers REQ-001.`), where the entire scenario is one line. `lines[1:]` on a one-line block is `[]` — the body vanishes.

**Verified reproduction:**
```python
qa_text = "- TC-001: Verify ranked results exclude expired assets. Covers REQ-001."
split_test_case_blocks(qa_text)          # -> {'TC-001': '- TC-001: Verify ranked results...\n'}  (correct)
pm_handoff._strip_decl_line(blocks['TC-001'])  # -> ''  (empty -> renders NOT_CAPTURED)
```

**Bug B — only forward references are walked, not the reverse graph.** `build_package()` collects a story's requirement/journey trace by regex-scanning **only the story's own block** (`FUNCTIONAL_REQ_ID_RE.findall(block)`, `JOURNEY_ID_RE.findall(block)`). Nothing in the stage-03 contract requires a story to self-cite its `FR-###`/`UJ-###` — only journeys are required to cite a requirement id (`lib/artifact_contracts.py` `_validate_stage_03`); a story can be linked purely from the *other* direction (the journey's or the FR's own Traceability field naming the story) and still pass validation. When that happens, `pm_handoff.py` finds zero FR/UJ ids for the story, so `traceability.scenarios_for_requirement()` is only ever asked about the story's own `US-###` id — any TC that traces solely to an FR/REQ the story never repeats is invisible to that story's handoff file.

**Verified reproduction:** a contract-valid `US-002` block with acceptance criteria but no embedded `FR-###`/`UJ-###` (relying on the journey/FR sections to declare the link the other way) yields `FUNCTIONAL_REQ_ID_RE.findall(block) == []`, `JOURNEY_ID_RE.findall(block) == []` — confirmed via `lib/artifact_contracts.py`'s own extractors.

**Note on the dogfood run:** neither bug surfaced during the `~/pm-projects/repassist` run because that PRD (regenerated under the new stage-03 skill) happens to repeat every story's full requirement/journey trace inline, and its QA plan uses heading-style (not single-line) TCs. Both bugs are real and contract-valid, just not triggered by that particular artifact shape — a genuinely fully-traceable pipeline can still hit either one depending on authoring style.

**Proposed fix:**
- Bug A: only strip a leading declaration line when the block actually has more than one line; for a single-line block, treat the whole line (minus the leading id/marker) as the body instead of discarding it.
- Bug B: resolve a story's requirements/journeys from the **traceability index** (`.traceability.yaml`, already reverse-built from the QA plan) rather than re-deriving them by re-scanning the story's own prose — the index already has the authoritative link graph; `pm_handoff.py` should consume it, not reimplement a weaker version of it.

---

## 13. 🟡 Telemetry does not capture per-stage token usage (IMP-009)

**Severity:** P2 — cost/routing visibility gap, not correctness-blocking. Also the one measurement that would make backlog #9's (IMP-006, whole-context-pack-per-stage) token savings provable rather than estimated.
**Status:** 🟡 Open — proposed, not yet scoped against runtime capability.

**Symptom:** `stage_generated` telemetry events (logged via `lib/telemetry.py:log()`, e.g. `skills/pm-stage-03-prd/SKILL.md`'s Write-outputs step) record `model`, `model_tier`, `prompt_version`, and `notes` — no `input_tokens`/`output_tokens`. Per-stage token consumption, the metric a PM would most want for cost or context-pack-routing decisions, can currently only be reconstructed by hand from file sizes.

**Evidence:** `lib/telemetry.py:log()` — `payload` is an arbitrary dict, so no schema change is needed to add fields, only a call-site change. Confirmed no skill or script currently passes any token-related field (`grep` across `skills/`, `lib/`, `scripts/` for `input_tokens`/`output_tokens`/`token_count`/`usage.` returns nothing).

**Open question before scoping a fix:** unlike the other entries here, this isn't purely a code change — it depends on whether the current agent runtime (Claude Code / Codex, mid-skill) can introspect its own exact API-level token usage for the turn that just generated the artifact. If the harness doesn't surface that number to the running skill, `input_tokens`/`output_tokens` would have to be an agent-estimated value (like the existing `semantic_distance` field already is) rather than a measured one — worth stating honestly in the telemetry payload (`_estimated: true` or similar) rather than presenting a guess as a hard count.

**Proposed fix:** Add `input_tokens`/`output_tokens` (or an `_estimated` variant, per the open question above) to the `stage_generated` payload in each stage skill's Write-outputs step, additive only — no schema version bump needed since `payload` is already free-form.

**Note:** Recorded 2026-07-15 from a RepAssist v1.0.8→v1.0.10 dogfooding pass, alongside entries 11-12 above (IMP-007, IMP-008). All three surfaced from the same review; IMP-001/IMP-007/IMP-008 share a common pattern worth naming: PM-OS's format *assumptions* (what a valid TC/story/journey looks like) keep drifting slightly ahead of or behind what the skills and PMs actually write — the fix in each case is to make the consuming code agree with itself (one parser, one source of truth) rather than adding more prose guidance that a second parser won't honor.

---

## 14. 🟠 Deep-reasoning model gate is advisory only, no enforced confirmation (from codex-pr-audit)

**Severity:** P2 — quality gate can be silently bypassed with a bare re-run; not data-destructive.
**Status:** 🟠 Open. Re-verified against current code 2026-07-15 (originally flagged in `docs/reference/codex-pr-audit.md` #8, PR #9, dated 2026-06-22).

**Symptom:** Stages 03 (PRD), 06 (QA plan), and 08 (TRD) print a model-tier warning when the session appears to be on a lightweight model, but the override path is just "re-run this stage and explicitly say to continue with the current model" — no flag, no distinct confirmation step, no record that the PM (rather than the agent, expedience-motivated) made that call.

**Evidence:** `skills/pm-stage-03-prd/SKILL.md` (Model guidance section) — "This check is advisory... If you want to proceed anyway, re-run this stage." Identical wording in stages 06 and 08.

**Proposed fix:** Require an explicit, auditable confirmation (e.g. `--confirm-lightweight-model` flag or an env var checked by the skill) before generating a deep-reasoning-tier stage on a lightweight model, rather than a silent re-run — so the bypass is intentional and visible in telemetry, not just possible.

---

## 15. 🟡 `migrate_meta()` does not backfill missing `STAGE_ORDER` stages (from codex-pr-audit)

**Severity:** P3 — low impact today (all new projects scaffold every stage), but upgrade correctness is broken for any project older than the current scaffolding.
**Status:** 🟡 Open, low priority. Re-verified against current code 2026-07-15 (originally flagged in `docs/reference/codex-pr-audit.md` #9, PR #14, dated 2026-06-22).

**Symptom:** `lib/project.py:migrate_meta()` handles schema v2→v4 field additions (`origin`, stage-00 injection, `project_type`/`codebase_path`/`codebase_ref`, `context_pack`) but never inserts a missing `STAGE_ORDER` entry generically. A pre-v0.4 project whose `stages[]` list predates later stages (e.g. 09) would still hit a `KeyError` in `pm_approve.py` trying to approve a stage `migrate_meta()` never backfilled.

**Evidence:** `lib/project.py:migrate_meta()` — confirmed no loop over `STAGE_ORDER` inserting missing entries with `status: pending`; only the one-off `00` injection exists.

**Proposed fix:** Add a migration pass that inserts any `STAGE_ORDER` id absent from `stages[]` with `status: pending` and default fields, guarded by the existing schema-version check so already-migrated projects are untouched.

---

## 16. 🟡 Approving a backfilled artifact logs a generic `stage_approved`, losing origin (from codex-pr-audit)

**Severity:** P3 — telemetry/provenance-analytics gap, not correctness-blocking.
**Status:** 🟡 Open. Re-verified against current code 2026-07-15 (originally flagged in `docs/reference/codex-pr-audit.md` #10, PR #24, dated 2026-06-22).

**Symptom:** `scripts/pm_context_import.py`'s `cmd_commit()` correctly logs `stage_backfilled_draft` with provenance, but once the PM later runs `/pm-approve`, `scripts/pm_approve.py` logs a plain `stage_approved` event with no `origin`/`derived_from` reference — an approved backfilled artifact becomes indistinguishable from a generated-then-approved one in telemetry.

**Evidence:** `scripts/pm_approve.py` — the only `log(...)` calls are `artifact_validation_warning` and `stage_approved`; neither branches on the stage's `origin` field in `.meta.yaml`.

**Proposed fix:** `pm_approve.py` should read the stage's `origin` from `.meta.yaml` at approval time and, when `origin == "backfilled"`, either log a distinct `stage_backfilled` (approved) event or augment `stage_approved`'s payload with `{"origin": "backfilled", "derived_from": [...]}` — additive, no schema change.

---

## 17. 🟢 `test_telemetry.py` reads the real installed `config.yaml` (from codex-pr-audit)

**Severity:** P3 — test-isolation gap; fails or leaks real data on machines with a real PM-OS install, not a product bug.
**Status:** 🟢 Re-verified against current code 2026-07-15 (originally flagged in `docs/reference/codex-pr-audit.md` #11, PR #20, dated 2026-06-22) — still present.

**Symptom:** `tests/unit/test_telemetry.py`'s four tests (`test_log_appends_chained_events`, `test_last_event_filters`, `test_verify_chain_ok_and_tamper`, `test_verify_chain_no_file`) take only `tmp_path`, never the `pmos` fixture. `telemetry.log()` calls `load_config()`, which reads the real `~/.pm-os/config.yaml` when the isolating fixture isn't requested — `pmos` (`tests/conftest.py`) monkeypatches `HOME`/`PM_OS_DIR` but is opt-in per test, not `autouse`.

**Evidence:** `tests/unit/test_telemetry.py` test signatures vs. `tests/conftest.py:pmos` fixture definition — confirmed the fixture is never requested in this file.

**Proposed fix:** Add the `pmos` fixture to each test in `test_telemetry.py` (matching the pattern already used across the rest of `tests/`), or add a lightweight `autouse` fixture scoped to this module that monkeypatches `telemetry.load_config` to a stub.

---

_Recorded 2026-06-20 during v0.5.6 rollout testing (entries 1-3); entry 4 recorded 2026-07-09 (IMP-002); entries 5-9 recorded 2026-07-09 during a demo-project run (IMP-001, IMP-003 through IMP-006); entry 10 recorded 2026-07-14 while reviewing stage-05 slice selection; entries 11-13 recorded 2026-07-15 during a RepAssist v1.0.8→v1.0.10 dogfooding pass (IMP-007 through IMP-009), each verified against the current codebase before being logged; entries 14-17 recorded 2026-07-15 during a docs cleanup pass, migrated from `docs/reference/codex-pr-audit.md` (dated 2026-06-22, since archived) — of that audit's 11 originally-open items, 7 were re-verified as already fixed (folded into the archived doc's resolution note) and these 4 were re-verified as still open. All documentation-only unless noted. Changes above land via the normal commit → push → `pm_os_update.py` path; they are inert until then._
