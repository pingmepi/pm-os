# PM-OS Pathway 2 (Prototype Entry + Interview) — Execution Runbook

**Status:** Ready to execute (2026-08-01). Design source: `pm-os-entry-pathways-plan.md` (phases E0–E1, pathway-2 half). This runbook is the step-by-step, loop-engineered build plan for **an executing agent**. It builds *only* pathway 2 (approved-prototype entry + the broad interview). Pathway 3 (codebase) is out of scope here.

**Read before starting:** `pm-os-entry-pathways-plan.md` §§1–5, 7 (the why and the E0/E1 acceptance criteria); `skills/pm-context-import/SKILL.md` (the skill you extend); `docs/guides/testing.md` (test catalog + harness); `CLAUDE.md` (esp. "never hand-modify the install" and "judgment in SKILL.md, mechanical state in Python").

---

## 0. Operating protocol (the loop)

Execute the loops in order. **Each loop is a strict cycle — do not skip a phase, do not advance on red:**

1. **AIM** — restate the one outcome this loop delivers.
2. **TESTS (first)** — write the test(s) named in the loop. Run them; **confirm they FAIL** for the stated reason (a test that passes before you write code is not testing your change — fix the test).
3. **CODE** — make the minimal change to satisfy the tests. Touch only the files the loop lists.
4. **VERIFICATION** — run the loop's verify command(s).
5. **PASS-IF-GREEN** — if green, the loop is done; if red, fix the *code* (not the test's intent) and re-run. Never edit a test to pass unless the test itself was wrong. Do not start the next loop while this one is red.
6. **UPDATE TASKS** — mark this loop done (use your task tool: `TaskUpdate` → completed; set the next loop `in_progress`), and check the box in §2 below.

**Regression gate between loops:** after PASS-IF-GREEN, run the full suite (`python3 -m pytest -q`) at least at Loops 1, 3, 5, and 6. Baseline is **`main`'s suite count** (the v1.4.1 fixes — 341 passing — are merged to `main` before this work starts). The count must only ever go **up**. Any pre-existing test going red is a regression you caused — stop and fix before advancing.

### Global conventions (MUST follow)

- **Branch:** create a **new branch off `main`** for this work (the v1.4.1 consistency fixes are merged to `main` first — that's a separate, already-done step). Do not build on `fix/v1.4.1-consistency-defects`. **Do not commit or push** without the PM's OK — they review first. Engine changes reach the install only via commit → push → `pm_os_update.py`; **never** hand-edit `~/.pm-os` or runtime skill dirs.
- **Scope: pathway 2 only.** This runbook builds the prototype → dev-handoff path. Pathway 3 (codebase/enhancement) is deferred: the front door (Loop 5) *presents* the enhancement option and keeps today's `--mode enhancement --codebase` behavior, but does **not** build the promote-to-enhancement setter, the codebase interview, or the scoped-delta pipeline — those are E2.
- **TDD, isolated:** all tests use the harness in `tests/conftest.py`. Reuse fixtures `pmos`, `new_project`, and helpers `make_draft`, `run_script` (see `tests/helpers.py`). Never touch the real `~/.pm-os` or `~/pm-projects`.
- **Judgment vs. mechanics:** the *interview questioning/ranking* is agent judgment → lives in `SKILL.md` prose. Python only moves bytes (register answers, record known-unknowns, telemetry). Do not put question generation in Python.
- **Non-interactive safety:** any new interactive path needs an env/flag escape and a non-tty branch (mirror `PM_OS_EDITED_UPSTREAM_CHOICE`). New escape: `PM_OS_INTERVIEW=skip` and `--interview-answers <file>`.
- **Cross-runtime:** any skill change updates **both** `SKILL.md` and `agents/openai.yaml`.
- **Catalog:** every new test gets a one-line docstring and an entry in `docs/guides/testing.md` (Loop 6).
- **Contract cap:** the interview asks **≤5** questions; skipped questions become **known unknowns**, never silent assumptions. The interview **never self-approves** any stage-00 doc.

---

## 1. Definition of done (E1, pathway 2)

- A pathway-2 import (prototype/design provided, **no** `--codebase`) whose `preflight` rates an upstream gap ⚠️/⛔ triggers the interview; it asks ≤5 ranked questions; answering raises the affected backfill's fidelity/confidence; skipping records a known unknown and fabricates nothing.
- Interview answers are registered in `.sources.yaml` as a PM-authored source (high confidence) and flow into the wiki/evidence.
- Non-interactively (`--interview-answers <file>` or `PM_OS_INTERVIEW=skip`/non-tty) the flow completes without hanging; unanswered → known unknowns.
- `/pm-new` routes uniformly (new/prototype/enhancement) with tailored next-step guidance; `[1]`/`[2]` are fully wired; `[3]` is presented but falls through to today's enhancement behavior (its full promotion is E2); the chosen route is recorded in telemetry.
- Full suite green; new tests cataloged; `pm-os-entry-pathways-plan.md` E0/E1 boxes checked. Pathway 3 (E2) explicitly untouched.

---

## 2. Task checklist (update as you go)

- [ ] **Loop 0** — Baseline & orientation
- [ ] **Loop 1** — `record-interview` mechanical helper (register answers as PM source)
- [ ] **Loop 2** — Known-unknowns + telemetry
- [ ] **Loop 3** — Non-interactive safety (`--interview-answers`, `PM_OS_INTERVIEW=skip`, non-tty)
- [ ] **Loop 4** — SKILL.md interview step (+ `agents/openai.yaml`) [contract test]
- [ ] **Loop 5** — Uniform front door + routing (E0): `/pm-new` scaffolds → routes (new/proto/enhancement) → tailored guidance; `[1]`/`[2]` wired, `[3]` presented (existing behavior); route in telemetry
- [ ] **Loop 6** — End-to-end pathway-2 integration test + docs/catalog + finalize

---

## Loop 0 — Baseline & orientation

- **AIM:** confirm a green baseline and learn the exact shapes you'll extend, so later loops don't guess.
- **TESTS:** none (setup loop).
- **CODE:** none. **Read and note:**
  - `scripts/pm_context_import.py` — subcommand pattern (`cmd_register`, `cmd_preflight`, `cmd_commit`, argparse `sub.add_parser(...)` at the bottom). Note exactly how `cmd_register` writes a source into `.sources.yaml` (fields: type, authorship/origin, confidence, path). You will mirror it.
  - `.sources.yaml` shape (create a scratch import in a throwaway test project if needed, or read `cmd_register`).
  - `lib/telemetry.py` `log(event_type, project_root, stage, payload)` — the telemetry call convention.
  - `skills/pm-context-import/SKILL.md` — where Step 4 (preflight) and Step 5 (understanding doc) are, so the interview slots between them.
- **VERIFICATION:** `python3 -m pytest -q` → **341 passed**.
- **PASS-IF-GREEN:** baseline is 341. If not, stop — environment is wrong.
- **UPDATE TASKS:** check Loop 0.

---

## Loop 1 — `record-interview` mechanical helper

- **AIM:** a `pm_context_import.py record-interview <answers-file>` subcommand that registers an interview-answers Markdown file as a **PM-authored** source (type `context`, high confidence), so answers flow into the wiki/evidence with provenance — exactly like `register`, but flagged as interview-origin.
- **TESTS (first):** new file `tests/integration/test_interview.py` (marker `integration`):
  - `test_record_interview_registers_pm_authored_source`: `new_project`; write an answers file; `run_script(pmos, "pm_context_import.py", "record-interview", str(answers), cwd=proj)`; load `.sources.yaml`; assert the answers file is registered with type `context`, an authorship/origin marker identifying it as PM interview input, and confidence `high`.
  Run: `python3 -m pytest tests/integration/test_interview.py -q` → **must fail** (subcommand doesn't exist → nonzero exit / KeyError).
- **CODE:** add `cmd_record_interview(args)` + a `record-interview` subparser in `scripts/pm_context_import.py`. Reuse the existing `register` machinery; set the source's authorship/confidence to PM/high and tag origin as `interview`. Keep it byte-moving only.
- **VERIFICATION:** `python3 -m pytest tests/integration/test_interview.py -q`, then `python3 -m pytest -q`.
- **PASS-IF-GREEN:** targeted green + full suite ≥ 342.
- **UPDATE TASKS:** check Loop 1.

---

## Loop 2 — Known-unknowns + telemetry

- **AIM:** `record-interview` records **skipped/unanswered** questions as known-unknowns (never silent assumptions) and emits a telemetry event with counts.
- **TESTS (first):** add to `tests/integration/test_interview.py`:
  - `test_record_interview_records_skips_as_known_unknowns`: answers file marks some questions skipped (agree a simple machine format with the SKILL, e.g. a `- [ ] SKIPPED: <question>` line or a `## Skipped` section); after `record-interview`, assert the skips are captured in a machine-readable place (recommended: a `known_unknowns` list appended to the wiki's Open-questions data or a `00-context/known-unknowns.md` — confirm the target with `SKILL.md`), and are NOT turned into assumptions.
  - `test_record_interview_emits_telemetry`: assert a telemetry event (e.g. `interview_conducted`) exists in `telemetry.jsonl` with `{asked, answered, skipped}` counts. (Read `lib/telemetry.py` for how tests read events; see `tests/unit/test_telemetry.py` / `test_telemetry_metrics.py`.)
- **CODE:** extend `cmd_record_interview` to parse skips → write known-unknowns, and `telemetry.log("interview_conducted", ...)` wrapped so a telemetry failure warns but never breaks (existing convention).
- **VERIFICATION:** targeted + `python3 -m pytest -q`.
- **PASS-IF-GREEN:** green; full suite ≥ 344.
- **UPDATE TASKS:** check Loop 2.

---

## Loop 3 — Non-interactive safety

- **AIM:** the flow is safe unattended: `--interview-answers <file>` supplies answers non-interactively; `PM_OS_INTERVIEW=skip` (or a non-tty session) records every question as a known unknown and proceeds without blocking.
- **TESTS (first):** add to `tests/integration/test_interview.py`:
  - `test_interview_answers_file_is_consumed_noninteractively`: passing `--interview-answers <file>` registers the answers with no prompt (subprocess, no tty).
  - `test_interview_skip_env_records_all_as_known_unknowns`: with `PM_OS_INTERVIEW=skip` in env, `record-interview` (or the preflight step) records all questions as known unknowns and exits 0 without prompting.
- **CODE:** honor `--interview-answers` and `PM_OS_INTERVIEW` in the subcommand; ensure no `input()` without a non-tty branch. (The *asking* is the skill's job; Python must never block.)
- **VERIFICATION:** targeted + `python3 -m pytest -q`.
- **PASS-IF-GREEN:** green; full suite ≥ 346.
- **UPDATE TASKS:** check Loop 3.

---

## Loop 4 — SKILL.md interview step (+ openai.yaml)

- **AIM:** `/pm-context-import` gains a **Step 4b — Interview** between preflight (Step 4) and the understanding doc (Step 5), realizing Phase 5: fires when preflight yields ⚠️/⛔ (or the assumption register has high-impact `[inferred]` rows), asks **≤5 ranked** questions (broad for pathway 2 — problem/why, target user, success criteria, descope history, non-goals, decision authority), calls `record-interview` with the answers, records skips as known unknowns, honors the non-tty/`PM_OS_INTERVIEW` escape, and **never self-approves**.
- **TESTS (first):** contract test in `tests/contracts/` (see existing skill/doc contract tests for the pattern; marker `contract`). `test_context_import_skill_has_interview_step`: read `skills/pm-context-import/SKILL.md` and assert it contains: an interview step keyed to preflight ⚠️/⛔ verdicts, the literal ≤5 cap, a `record-interview` invocation, the `PM_OS_INTERVIEW` escape, the words "known unknown", and a "do not self-approve" instruction. (This is a drift/contract test — cheap, guards the prose contract.)
- **CODE:** edit `skills/pm-context-import/SKILL.md` (add Step 4b) and mirror the capability in `skills/pm-context-import/agents/openai.yaml`.
- **VERIFICATION:** `python3 -m pytest -m contract -q` (or the file), then `python3 -m pytest -q`.
- **PASS-IF-GREEN:** green; full suite ≥ 347.
- **UPDATE TASKS:** check Loop 4.

---

## Loop 5 — Uniform front door + routing (E0)

- **AIM:** `/pm-new` always scaffolds a project identically, then routes: it asks new/prototype/enhancement (interactive prompt mirroring the existing GenAI prompt) and prints tailored next-step guidance. Non-interactive escape: `--entry {new,prototype,enhancement}` (+ `--codebase` for enhancement). Focus is `[1]`/`[2]`; `[3]` is **presented** and falls through to today's `--mode enhancement --codebase` behavior unchanged (its full promote-to-enhancement setter is **E2, deferred**). The chosen route is recorded in telemetry.
- **TESTS (first):** drive them via the `--entry` flag so they're non-interactive (mirror how `--genai/--no-genai` are tested). New file `tests/integration/test_entry_routing.py` (marker `integration`):
  - `test_pm_new_new_route_prints_greenfield_guidance`: `--entry new` (or default) → `project_type=new_product`; stdout instructs `/pm-stage-01-brief`.
  - `test_pm_new_prototype_route_prints_import_guidance`: `--entry prototype` → `project_type=new_product`; a route hint recorded (telemetry/meta); stdout instructs `/pm-context-import` with the PM's prototype/design docs.
  - `test_pm_new_enhancement_route_prints_guidance_only`: `--entry enhancement --codebase <path>` behaves exactly as today's `--mode enhancement --codebase` (`project_type=enhancement`, `codebase_path` set — no *new* machinery) and stdout instructs `/pm-context-import --codebase`. (Pathway-3's promote setter is E2 — do not build or assert it here.)
  - `test_pm_new_route_recorded_in_telemetry`: the `project_created` (or a dedicated) event carries the chosen route.
  - `test_pm_new_noninteractive_defaults_to_new_without_entry`: no tty and no `--entry`/`--mode` → defaults to `new` and does not hang (preserves today's 341-baseline behavior — do not make this error).
  Run: `python3 -m pytest tests/integration/test_entry_routing.py -q` → **must fail**.
- **CODE:** in `scripts/pm_new.py`: add the `--entry` flag + an interactive routing prompt (tty only; non-tty without `--entry`/`--mode` defaults to `new`, no error); print tailored stdout guidance per route; record the route in telemetry. **`[3]` reuses the existing enhancement scaffold path as-is** — do not relocate `00c` or add a promote setter (that's E2). Update `skills/pm-new/SKILL.md` (the routing question + per-route guidance) and `agents/openai.yaml`. Keep `--mode`/`--codebase`/`PM_OS_PROJECT_TYPE` working as back-compat aliases.
- **VERIFICATION:** targeted + `python3 -m pytest -q` (watch for regressions in existing `pm_new`/lifecycle tests — the default-`new` non-tty behavior must be preserved).
- **PASS-IF-GREEN:** green; full suite count up from prior loop.
- **UPDATE TASKS:** check Loop 5. (This loop builds only the front door + `[1]`/`[2]` routing; pathway-3's promote setter, codebase interview, and scoped-delta pipeline stay deferred to E2.)

---

## Loop 6 — End-to-end pathway-2 integration + finalize

- **AIM:** prove the whole pathway-2 flow and close out docs.
- **TESTS (first):** `tests/integration/test_interview.py`:
  - `test_pathway2_import_with_interview_raises_backfill_fidelity`: simulate a pathway-2 import — register a downstream entry artifact (a design/prototype-level doc as the highest provided stage), run `preflight` (expect a ⚠️/⛔ on an upstream gap), supply `--interview-answers <file>` that fills the missing WHY/scope, and assert (a) the answers appear in `.sources.yaml` as a PM source, (b) known-unknowns are recorded for anything skipped, (c) the backfilled upstream artifact commit reflects the interview input (e.g. the answer text is present in the backfilled body or its provenance cites the interview source). Keep the assertion on mechanically-checkable outputs, not LLM phrasing.
- **CODE:** only what's needed to make the e2e assertions pass (wiring already built in Loops 1–5; this loop mostly integrates).
- **VERIFICATION:** `python3 -m pytest -q` → all green, count ≥ 350.
- **THEN (finalize, still this loop):**
  - Catalog every new test in `docs/guides/testing.md` (one line each, matching the existing format).
  - Tick the E0/E1 acceptance boxes in `pm-os-entry-pathways-plan.md` and set its status to "E1 shipped (pathway 2), pending PM review".
  - Do **not** commit. Report to the PM: what changed, the new test count, and that pathway 3 (E2) remains deferred.
- **PASS-IF-GREEN:** full suite green; docs updated.
- **UPDATE TASKS:** check Loop 6. E1 (pathway 2) done.

---

## Safety & rollback

- If a loop's regression gate goes red and the cause isn't obvious, revert that loop's code changes (`git checkout -- <files>` for tracked files; delete new untracked files) and re-approach — never advance on red.
- If any step tempts you to modify `~/.pm-os` or a runtime skill dir "to test," stop: run against the working copy via the test harness instead (`tests/conftest.py` builds an isolated temp install).
- Escalate to the PM (do not guess) if: the `.sources.yaml`/telemetry schema needs a breaking change; the interview would need to exceed 5 questions to be useful; or preflight verdicts turn out not to be a usable trigger signal (may need a small `preflight --json` addition — a new mini-loop, tested first).

---

End of runbook.
