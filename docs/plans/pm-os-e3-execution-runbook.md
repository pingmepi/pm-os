# PM-OS E3 (Standalone `/pm-interview` + Known-Unknowns Surfacing) — Execution Runbook

**Status:** Ready to execute (2026-08-03). Design source: `pm-os-entry-pathways-plan.md` §7 (phase **E3**) and §8 open-decision #2. This runbook is the step-by-step, loop-engineered build plan for **an executing agent**. It builds *only* E3 (standalone re-run interview + provenance/telemetry polish + `/pm-status` surfacing). Pathway 3 / E2 (codebase interview, promote-to-enhancement setter, scoped-delta pipeline) is **out of scope** and must not be touched.

**Read before starting:** `pm-os-entry-pathways-plan.md` §§4–5, 7, 8 (the interview contract, the E3 row, and open decision #2); `skills/pm-context-import/SKILL.md` Step 4b (the E1 interview the re-run mirrors); `scripts/pm_context_import.py` (`cmd_record_interview`, `_write_known_unknowns`, `_parse_interview_markdown`, `_register_one` — the E1 machinery you reuse); `scripts/pm_status.py` (where the surfacing line lands); `docs/guides/testing.md` (test catalog + harness); `CLAUDE.md` (esp. "never hand-modify the install" and "judgment in SKILL.md, mechanical state in Python").

**Recommended defaults baked into this runbook (from the E3 scope review, 2026-08-03):**
1. **Helper home** — a **new, self-contained `scripts/pm_interview.py`**. It reuses E1's answer-registration by shelling out to `pm_context_import.py record-interview` (zero edits to that script), and owns only the *read* + *resolve* of `known-unknowns.md`. No `lib/` refactor; E1's `_write_known_unknowns` stays the single writer of new skips.
2. **Resolution model** — resolved items are **marked in place** (`[resolved: <source> <YYYY-MM-DD>]`) and kept as an audit trail. **Never delete a known unknown**, never convert a skip into a silent assumption.
3. **Telemetry** — reuse the existing `interview_conducted` event with a `mode: "rerun"` field. No new event type; the hash chain stays simple.
4. **`/pm-status` depth** — a `Known unknowns: N open` line plus the first few open questions (compact, matching the existing status style).
5. **Re-run scope** — strictly the recorded known-unknowns in `00-context/known-unknowns.md`. E3 does **not** re-run `preflight` or discover *new* gaps — that stays in `/pm-context-import`.

---

## 0. Operating protocol (the loop)

Execute the loops in order. **Each loop is a strict cycle — do not skip a phase, do not advance on red:**

1. **AIM** — restate the one outcome this loop delivers.
2. **TESTS (first)** — write the test(s) named in the loop. Run them; **confirm they FAIL** for the stated reason (a test that passes before you write code is not testing your change — fix the test).
3. **CODE** — make the minimal change to satisfy the tests. Touch only the files the loop lists.
4. **VERIFICATION** — run the loop's verify command(s).
5. **PASS-IF-GREEN** — if green, the loop is done; if red, fix the *code* (not the test's intent) and re-run. Never edit a test to pass unless the test itself was wrong. Do not start the next loop while this one is red.
6. **UPDATE TASKS** — mark this loop done (use your task tool: `TaskUpdate` → completed; set the next loop `in_progress`), and check the box in §2 below.

**Regression gate between loops:** after PASS-IF-GREEN, run the full suite (`python3 -m pytest -q`) at least at Loops 1, 3, 5, and 6. Baseline is **`main`'s suite count = 359 collected** (confirm in Loop 0). The count must only ever go **up**. Any pre-existing test going red is a regression you caused — stop and fix before advancing.

### Global conventions (MUST follow)

- **Branch:** create a **new branch off `main`** for this work. **Do not commit or push** without the PM's OK — they review first. Engine changes reach the install only via commit → push → `pm_os_update.py`; **never** hand-edit `~/.pm-os` or runtime skill dirs.
- **Scope: E3 only.** Standalone re-run interview against **already-recorded** known-unknowns, provenance/telemetry polish, and `/pm-status` surfacing. Do **not** build or touch: pathway-3 codebase interview, the promote-to-enhancement setter, scoped-delta stage blocks, or any stage `SKILL.md` 01–08. Do **not** edit `skills/pm-context-import/SKILL.md` (that file is E2's territory; E3 reuses `record-interview` as-is via subprocess).
- **TDD, isolated:** all tests use the harness in `tests/conftest.py`. Reuse fixtures `pmos`, `new_project`, and helpers `make_draft`, `run_script` (see `tests/helpers.py`). Never touch the real `~/.pm-os` or `~/pm-projects`.
- **Judgment vs. mechanics:** the *re-run questioning/ranking* is agent judgment → lives in `skills/pm-interview/SKILL.md` prose. Python (`pm_interview.py`) only moves bytes: list open unknowns, mark them resolved with provenance, log telemetry. Do not put question generation in Python.
- **Non-interactive safety:** the new interactive path needs an env/flag escape and a non-tty branch (mirror E1). Escapes are the **same names** as E1 so PMs learn one vocabulary: `--interview-answers <file>` and `PM_OS_INTERVIEW=skip` (and non-tty ⇒ never prompt, never hang; open unknowns simply stay open).
- **Cross-runtime:** the new skill ships **both** `skills/pm-interview/SKILL.md` and `skills/pm-interview/agents/openai.yaml`.
- **Catalog:** every new test gets a one-line docstring and an entry in `docs/guides/testing.md` (Loop 6).
- **Interview contract (unchanged from E1):** **coverage-driven, not a fixed count** — batched by topic in **strictly decreasing order of impact**, soft ~5 per round, PM may skip/stop anytime. Skipped/unanswered → the unknown **stays open** (never a silent assumption). The interview **never self-approves** any stage-00 doc; it informs regeneration only.
- **Name check:** `skills/pm-interview/` does not exist today and the name is reserved for exactly this (only the *concept* was reserved as Phase 5 — the skill name is free). Confirm with `ls skills/ | grep interview` before creating it.

---

## 1. Definition of done (E3)

- Inside an existing project that has a `00-context/known-unknowns.md` with open items, `/pm-interview` presents **only the still-open** unknowns (resolved ones are skipped), batched by decreasing impact, and lets the PM answer or skip.
- Answers are registered as a PM-authored, high-confidence source **via the existing `record-interview` machinery** (unchanged), so provenance flows into `.sources.yaml`/evidence exactly as in E1.
- Each answered unknown is **marked resolved in place** with provenance (`[resolved: <source-id> <YYYY-MM-DD>]`); skipped/unanswered unknowns stay open; nothing is deleted and nothing becomes a silent assumption.
- Non-interactively (`--interview-answers <file>` or `PM_OS_INTERVIEW=skip`/non-tty) the flow completes without hanging.
- A re-run emits `interview_conducted` telemetry with `mode: "rerun"` and `{asked, answered, skipped}` counts.
- `/pm-status` shows `Known unknowns: N open` plus the first few open questions.
- Full suite green (count only up); new tests cataloged; `pm-os-entry-pathways-plan.md` E3 box checked and its status line updated. E2 explicitly untouched.

---

## 2. Task checklist (update as you go)

- [ ] **Loop 0** — Baseline & orientation
- [ ] **Loop 1** — Known-unknowns reader (`pm_interview.py list-unknowns` → open items as JSON)
- [ ] **Loop 2** — Known-unknowns resolver (`pm_interview.py resolve` → mark-in-place + `mode:rerun` telemetry)
- [ ] **Loop 3** — Provenance + non-interactive safety (`--interview-answers`, `PM_OS_INTERVIEW=skip`, non-tty)
- [ ] **Loop 4** — `/pm-interview` skill (`SKILL.md` + `agents/openai.yaml`) [contract test]
- [ ] **Loop 5** — `/pm-status` surfacing (`Known unknowns: N open` + first few)
- [ ] **Loop 6** — End-to-end re-run integration test + docs/catalog + finalize

---

## Loop 0 — Baseline & orientation

- **AIM:** confirm a green baseline and learn the exact shapes you'll extend, so later loops don't guess.
- **TESTS:** none (setup loop).
- **CODE:** none. **Read and note:**
  - `scripts/pm_context_import.py` — `_write_known_unknowns` (the exact on-disk format: `- <question> (source: <id>)`, the header block, append-only dedupe), `_parse_interview_markdown` (how answered/skipped are counted), `cmd_record_interview` (the subcommand you will reuse **unchanged** via subprocess), and the argparse `sub.add_parser(...)` pattern at the bottom (you'll mirror it in the new script).
  - `00-context/known-unknowns.md` shape — create a scratch project + `record-interview` a pending-questions file in a throwaway test to see the real output, or read the writer.
  - `lib/telemetry.py` `log(event_type, project_root, stage, payload)` and how tests read events (`tests/unit/test_telemetry*.py`).
  - `scripts/pm_status.py` — the print order (Stages → Recent events → Feedback/Telemetry counts → Consistency). The known-unknowns line will slot in near the feedback/telemetry summary. Find the existing status test file: `grep -rl pm_status tests/`.
  - `scripts/pm_new.py` / `lib/project.py` `resolve_project()` — how a script finds the active project (the new script needs the same).
- **VERIFICATION:** `python3 -m pytest -q` → **359 passed** (or the current `main` count). Record the number.
- **PASS-IF-GREEN:** baseline matches the recorded `main` count. If not, stop — environment is wrong.
- **UPDATE TASKS:** check Loop 0.

---

## Loop 1 — Known-unknowns reader (`list-unknowns`)

- **AIM:** a new, self-contained `scripts/pm_interview.py` with a `list-unknowns` subcommand that parses `00-context/known-unknowns.md` and emits the **open** items (question + originating source) as machine-readable JSON, so the skill can drive the re-run from a stable contract. Resolved items (those carrying a `[resolved: ...]` marker) are excluded.
- **TESTS (first):** new file `tests/integration/test_pm_interview.py` (marker `integration`):
  - `test_list_unknowns_returns_open_items`: `new_project`; write a `00-context/known-unknowns.md` with two open `- <q> (source: <id>)` bullets and one bullet already carrying `[resolved: <src> 2026-01-01]`; run `run_script(pmos, "pm_interview.py", "list-unknowns", "--json", cwd=proj)`; assert stdout parses as JSON listing exactly the two open questions (each with its `question` and `source`), and the resolved one is absent.
  - `test_list_unknowns_empty_when_no_file`: no `known-unknowns.md` → exits 0, emits `[]` (never errors).
  Run: `python3 -m pytest tests/integration/test_pm_interview.py -q` → **must fail** (script/subcommand doesn't exist → nonzero exit).
- **CODE:** create `scripts/pm_interview.py` with the standard shebang/`sys.path.insert(0, ~/.pm-os/lib)` header, `resolve_project()` usage, and a `list-unknowns` subparser (`--json`). Parse the bullet format written by `_write_known_unknowns`; treat any bullet containing `[resolved:` as closed. Byte-moving only — no question generation.
- **VERIFICATION:** `python3 -m pytest tests/integration/test_pm_interview.py -q`, then `python3 -m pytest -q`.
- **PASS-IF-GREEN:** targeted green + full suite ≥ 361.
- **UPDATE TASKS:** check Loop 1.

---

## Loop 2 — Known-unknowns resolver (`resolve`) + telemetry

- **AIM:** a `pm_interview.py resolve <answers-file>` subcommand that (a) marks each previously-open unknown the answers address as **resolved in place** — appending `[resolved: <source-id> <YYYY-MM-DD>]` to the bullet, never deleting it — and (b) emits an `interview_conducted` telemetry event with `mode: "rerun"` and `{asked, answered, skipped}` counts. Unmatched unknowns stay open verbatim.
- **TESTS (first):** add to `tests/integration/test_pm_interview.py`:
  - `test_resolve_marks_matched_unknowns_in_place`: seed two open unknowns; supply an answers file that answers one (agree the machine-matching key with the SKILL — recommended: the answers file echoes the exact question text under an `## Answered` section, or a `- <question> :: <answer>` line); after `resolve`, assert the answered bullet now contains `[resolved:` **and still contains the original question text** (audit trail intact), and the other bullet is unchanged/open.
  - `test_resolve_never_deletes`: assert the total bullet count in `known-unknowns.md` is unchanged after resolve (marked, not removed).
  - `test_resolve_emits_rerun_telemetry`: assert a `telemetry.jsonl` event `interview_conducted` exists with `payload.mode == "rerun"` and integer `asked/answered/skipped` counts.
  - `test_resolve_leaves_unanswered_open`: a skipped question stays open, is **not** rewritten as an assumption.
- **CODE:** add `cmd_resolve` + a `resolve` subparser to `scripts/pm_interview.py`. Reuse the file format from Loop 1; use `lib.telemetry.log("interview_conducted", root, None, {"mode": "rerun", ...})` wrapped so a telemetry failure warns but never breaks (existing convention). **Do not** re-register the answers here — that's the reused `record-interview` step, invoked separately by the skill (Loop 4). `resolve` only mutates `known-unknowns.md` + logs.
- **VERIFICATION:** targeted + `python3 -m pytest -q`.
- **PASS-IF-GREEN:** green; full suite ≥ 365.
- **UPDATE TASKS:** check Loop 2.

---

## Loop 3 — Provenance + non-interactive safety

- **AIM:** the re-run is safe unattended and carries provenance. `resolve` records **who/when/which-source** on each resolved bullet; `--interview-answers <file>` drives it non-interactively; `PM_OS_INTERVIEW=skip` or a non-tty session never prompts and never hangs (open unknowns simply remain open).
- **TESTS (first):** add to `tests/integration/test_pm_interview.py`:
  - `test_resolved_bullet_carries_provenance`: after `resolve`, the marked bullet's `[resolved: <source-id> <date>]` names the interview source id and an ISO date. (Source id = the id `record-interview` produced; in the resolve-only test, pass it via a `--source <id>` arg or read the latest interview source from `.sources.yaml` — pick one and assert it.)
  - `test_resolve_answers_file_consumed_noninteractively`: `--interview-answers <file>` runs with no tty and no prompt.
  - `test_resolve_skip_env_leaves_all_open`: with `PM_OS_INTERVIEW=skip`, `resolve` marks nothing, exits 0, prints a clear "no answers; N unknowns remain open" line, and does not block.
- **CODE:** in `scripts/pm_interview.py`: honor `--interview-answers`/`PM_OS_INTERVIEW`/non-tty exactly as `pm_context_import.py` does (copy the `skip_all` idiom); thread the interview source id onto the resolved marker (accept `--source <id>`, else resolve the newest `origin: interview, confidence: high` id from `.sources.yaml` via the same predicate as `_interview_source_ids`). No `input()` without a non-tty branch.
- **VERIFICATION:** targeted + `python3 -m pytest -q`.
- **PASS-IF-GREEN:** green; full suite ≥ 368.
- **UPDATE TASKS:** check Loop 3.

---

## Loop 4 — `/pm-interview` skill (+ openai.yaml)

- **AIM:** a new standalone skill `/pm-interview` that: reads open unknowns via `pm_interview.py list-unknowns --json`; if none, says so and exits; otherwise conducts a **coverage-driven** re-run — batched by topic in **strictly decreasing order of impact**, soft ~5 per round, only the still-open gaps — then registers answers with the **existing** `pm_context_import.py record-interview --interview-answers <file>` (provenance into `.sources.yaml`), then calls `pm_interview.py resolve <answers-file>` to mark the addressed unknowns resolved and log `mode: rerun`. Honors the `PM_OS_INTERVIEW`/non-tty escape; **never self-approves** any stage-00 doc; notes that answering may warrant re-running the affected stage(s), but does not do so automatically.
- **TESTS (first):** contract test in `tests/contracts/` (marker `contract`; follow the existing skill-contract pattern, e.g. the E1 `test_context_import_skill_has_interview_step`). `test_pm_interview_skill_contract`: read `skills/pm-interview/SKILL.md` and assert it contains: a `list-unknowns` read step, the coverage-driven contract phrases ("decreasing order of impact", ask only still-open gaps, **no** fixed numeric total), a `record-interview` invocation, a `resolve` invocation, the `PM_OS_INTERVIEW` escape, the words "known unknown", and a "do not self-approve" instruction. Also assert `skills/pm-interview/agents/openai.yaml` exists and declares the skill.
- **CODE:** create `skills/pm-interview/SKILL.md` (with YAML frontmatter, mirroring an existing skill's shape) and `skills/pm-interview/agents/openai.yaml`. Prose carries all judgment; the only mechanics are the three script calls above. Do **not** edit `skills/pm-context-import/SKILL.md`.
- **VERIFICATION:** `python3 -m pytest -m contract -q` (or the file), then `python3 -m pytest -q`.
- **PASS-IF-GREEN:** green; full suite ≥ 369.
- **UPDATE TASKS:** check Loop 4.

---

## Loop 5 — `/pm-status` surfacing

- **AIM:** `/pm-status` shows `Known unknowns: N open` (N = open bullets in `00-context/known-unknowns.md`) and, when N > 0, lists the first few open questions — compact, matching the existing status style. Resolved bullets are not counted.
- **TESTS (first):** in the existing status test file (from Loop 0's `grep -rl pm_status tests/`; create `tests/integration/test_status_known_unknowns.py` if there's no natural home):
  - `test_status_shows_open_known_unknowns_count`: seed `known-unknowns.md` with 2 open + 1 resolved; run `pm_status.py`; assert stdout contains `Known unknowns: 2 open`.
  - `test_status_no_known_unknowns_line_when_none`: no file (or all resolved) → shows `Known unknowns: 0 open` (or omits — pick one and assert it consistently; recommended: always print the line so absence is legible).
- **CODE:** in `scripts/pm_status.py`, after the feedback/telemetry summary block, read `00-context/known-unknowns.md` (reuse the open/resolved parse — factor a tiny shared parser into `pm_interview.py` and import it, or duplicate the one-line "contains `[resolved:`" check; keep it trivial), print the count and up to ~3 open questions. Read-only; never mutates.
- **VERIFICATION:** targeted + `python3 -m pytest -q`.
- **PASS-IF-GREEN:** green; full suite ≥ 371.
- **UPDATE TASKS:** check Loop 5.

---

## Loop 6 — End-to-end re-run integration + finalize

- **AIM:** prove the whole standalone re-run flow end to end and close out docs.
- **TESTS (first):** `tests/integration/test_pm_interview.py`:
  - `test_pm_interview_end_to_end_resolves_and_records`: start from a project with 3 open known-unknowns; supply `--interview-answers <file>` answering 2 and skipping 1; run the sequence the skill runs (`record-interview` → `resolve`); assert (a) the 2 answered unknowns are marked `[resolved: <interview-source-id> <date>]` and still present (audit trail), (b) the 1 skipped stays open, (c) `.sources.yaml` gained the interview source, (d) a `interview_conducted` `mode:rerun` event exists, and (e) `pm_status.py` now reports `Known unknowns: 1 open`. Keep assertions on mechanically-checkable outputs, not LLM phrasing.
- **CODE:** only what's needed to make the e2e assertions pass (wiring built in Loops 1–5; this loop mostly integrates).
- **VERIFICATION:** `python3 -m pytest -q` → all green, count ≥ 372.
- **THEN (finalize, still this loop):**
  - Catalog every new test in `docs/guides/testing.md` (one line each, matching the existing format).
  - In `pm-os-entry-pathways-plan.md`: tick the **E3** acceptance and set the plan's status line to note "E3 shipped (standalone `/pm-interview` + known-unknowns surfacing), pending PM review".
  - In `docs/roadmap/current-state-review.md`: add E3 to the entry-pathways row when the PM approves (leave a note; do not pre-claim a version).
  - Do **not** commit. Report to the PM: what changed, the new test count, and that E2 (pathway 3) remains deferred.
- **PASS-IF-GREEN:** full suite green; docs updated.
- **UPDATE TASKS:** check Loop 6. E3 done.

---

## Safety & rollback

- If a loop's regression gate goes red and the cause isn't obvious, revert that loop's code changes (`git checkout -- <files>` for tracked files; delete new untracked files) and re-approach — never advance on red.
- If any step tempts you to modify `~/.pm-os` or a runtime skill dir "to test," stop: run against the working copy via the test harness instead (`tests/conftest.py` builds an isolated temp install).
- **Do not touch E2 surfaces.** If a change seems to require editing `skills/pm-context-import/SKILL.md`, a stage `SKILL.md` (01–08), or the enhancement/scoped-delta machinery, stop and escalate — that's a scope breach, not an E3 task.
- Escalate to the PM (do not guess) if: the `known-unknowns.md` format needs a breaking change to carry provenance (Loop 2/3 assume an in-line `[resolved: ...]` marker is sufficient — if it isn't, propose a small format bump as its own tested mini-loop); the answers-file ↔ open-question matching can't be made deterministic from the current bullet text (may need a stable per-unknown id — a schema touch, PM call); or `record-interview` turns out to need changes to support re-run (it should not — if it does, that's a shared-surface decision).

---

End of runbook.
