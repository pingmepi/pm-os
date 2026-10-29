# PM-OS Sprint Mode Build Plan: changes, tests and verification

**Status:** 🔵 Plan only, nothing built. Recorded 2026-10-29 against v1.5.7.
**Author:** Karan (with Claude Code)
**Implements:** [`pm-os-sprint-mode-plan.md`](pm-os-sprint-mode-plan.md), the sprint mode design: what sprint mode is and why. This doc covers the build: what changes in the PM-OS engine, how each change is tested, and how it is verified before it reaches a PM. Read `pm-os-sprint-mode-plan.md` first; this doc doesn't repeat its rationale. Below, "sprint-mode plan §N" means a section of that doc.
**Builds on:** `pm-os-modes-delivery-and-handoff-plan.md` §8.7 (branch `docs/delivery-plan-part-b`, unmerged), which the sprint-mode plan revises. That section exists only on the remote branch; read it with `git show origin/docs/delivery-plan-part-b:docs/plans/pm-os-modes-delivery-and-handoff-plan.md` until S0 merges it. "§8.7.x" below always means that section.
**Backlog:** #28, #52, #63, #66, #22, #23, #76, #78.

---

## Start here (for the agent picking this up)

**Read, in order:**
1. `CLAUDE.md`: the repo rules. Most important: this repo is the source, not the running system. Never copy or edit files in `~/.pm-os`, `~/.claude/skills` or `~/.agents/skills`; changes reach the install only through commit → push → `python3 ~/.pm-os/scripts/pm_os_update.py`.
2. `docs/plans/pm-os-sprint-mode-plan.md`: the sprint mode design.
3. §8.7 of the modes plan, from the remote branch (command in the header above).
4. This doc.
5. `docs/guides/testing.md`: the test harness, the catalog convention, and how to add a test.
6. `docs/roadmap/backlog.md` entries #28, #52, #63, #66 before touching those areas.

**Existing code to reuse, not rebuild:**

| Need | Reuse |
|---|---|
| Ungated YAML record (load, validate, `check_project`, `/pm-check` section, `/pm-status` line) | `lib/readiness.py`, its wiring in `scripts/pm_check.py` and `scripts/pm_status.py`, and `tests/integration/test_readiness_record.py` as the ungated-test model |
| Stable-id blocks | `artifact_contracts.split_stable_id_blocks` (`lib/artifact_contracts.py`) |
| PRD epics → stories → requirements map | `lib/delivery_map.py` `build_prd_delivery_map` |
| Release record, `CHANGES.md`, manifest, safe clearing | `lib/release_record.py`, `lib/release_check.py` |
| Package build and Jira export | `scripts/pm_share.py`, `scripts/pm_handoff.py` |
| Finishing a stage written in parts | `scripts/pm_finish_stage.py` |
| Rebuild hook on approval | `hooks/post-approve.py`, the `.traceability.yaml` rebuild block |
| HTML render | `lib/html_render.py`; Jinja templates live in `templates/` |
| Project-owned paths | `lib/project_git.py` `OWNED_FILES`, `OWNED_DIRS` |
| Skill contract tests and Codex twins | `tests/contracts/test_skill_contracts.py` |
| Telemetry event list drift test | `tests/contracts/test_documentation_drift.py` |

**Working rules:**
- One branch and one PR per chunk (S0–S6), named `feat/sprint-mode-s<N>-<slug>`. Don't commit to `main`.
- A chunk is done only when its §7 gates are green. Don't start the next chunk on top of an unmerged one.
- If a decision in §2 hasn't been confirmed by Karan, stop and ask before building the chunk it blocks.
- Anything found that doesn't fit this plan goes into `docs/roadmap/backlog.md` after it's verified against the code.

---

## 0. Two kinds of work, kept apart

This plan has two parts, and they must not mix.

| | **Part 1: engine work** (§1–§9) | **Part 2: product usage** (§10–§12) |
|---|---|---|
| What | Changes to PM-OS itself: `lib/`, `scripts/`, `hooks/`, `skills/`, tests, docs | Running the finished PM-OS on a real product |
| Where | This repo, shipped through commit → push → `pm_os_update.py` | A product's project folder under `~/pm-projects/`, through `/pm-*` skills |
| Product-specific? | **Never.** No product name, domain term, Figma naming or Jira key appears in engine code, skill text, templates or test fixtures | Yes, by design |
| Done when | Its tests pass and the verification gates in §7 are green | That product's pilot outcomes in §11 are measured |
| Example | `lib/vision_deltas.py`, the `VD_*` checks, `/pm-sprint-plan` | Recording PRISM's sprints 1–3, settling its drift, running its sprint 4 |

**PRISM appears only in Part 2**, and in one place in Part 1: §9.4, which uses PRISM's existing folders as a **read-only** acceptance input. Nothing in PRISM is written by an engine chunk, and no engine chunk's "done" depends on PRISM's sprint calendar. Another product could be the first user instead, and Part 1 wouldn't change.

---

# Part 1: Engine work

## 1. What changes and what doesn't

**Unchanged (and tested to stay unchanged):**
- `STAGE_ORDER`, `STAGE_NAMES`, stage statuses, the gate (`hooks/pre-stage.py`), approval (`scripts/pm_approve.py`), `lib/cascade.py`, `lib/hashing.py`.
- `.meta.yaml`, `config.yaml` and `.traceability.yaml` shapes. **No `schema_version` bump** in either. Every new file has its own `schema_version: 1`, as `readiness.yaml` does.
- Projects without `delivery.yaml` behave exactly as today. Every new flag (`--increment`) on such a project exits with one line pointing to the skill that creates it.

**New (all ungated, following the `readiness.yaml` pattern in `lib/readiness.py`):**

| File in a project | Kind | Built by |
|---|---|---|
| `delivery.yaml` | PM record, agent-edited | `lib/delivery.py` |
| `vision-deltas.md` | PM record, agent-edited | `lib/vision_deltas.py` |
| `vision.md` | Derived, overwritten | `lib/vision_summary.py` |
| `by-epic/` | Derived, overwritten | `lib/id_views.py` |
| `sprints/INC-###/` | PM records, agent-edited | `lib/sprint_workspace.py` |
| `readout/business-readout.md` (+ `.html`) | PM record, agent-edited | `lib/sprint_workspace.py`, `lib/html_render.py` |
| `handoff/INC-###/<audience>/` | Generated | `scripts/pm_share.py` |

`lib/project_git.py`: `OWNED_FILES` gains `delivery.yaml`, `vision-deltas.md`, `vision.md`; `OWNED_DIRS` gains `sprints`, `by-epic`, `readout`.

## 2. Decisions to confirm before building

The sprint-mode plan's §12 lists seven open decisions, each with a recommendation. This plan **assumes the recommended answer** for each. A chunk doesn't start until the decisions it depends on are confirmed.

| # | Decision (sprint-mode plan §12) | Assumed | Blocks |
|---|---|---|---|
| 1 | Sprint id format | `S<n>-US-<nn>`, `S<n>-FR-<nn>`; `delivery.yaml` maps `S<n>` ↔ `INC-00n` | S4 |
| 2 | `vision.md` editable? | Derived only | S3 |
| 3 | Apply granularity | One revision per stage for all picked deltas | S2 |
| 4 | Drop/defer deltas | Edit both 03 (mark dropped) and 09 ("Not planned") | S2 |
| 5 | Business readout render | Markdown + HTML | S6 |
| 6 | Design kit | `--design-kit` flag on `/pm-sprint-spec`; design-return checks (#78) in S5 | S4, S5 |
| 7 | Docs branch | Merge `docs/delivery-plan-part-b` as is; mark §8.7 "revised by `pm-os-sprint-mode-plan.md`" | S0 |

## 3. Prerequisites already in the backlog

| Item | State today | Why sprint mode needs it | Handled in |
|---|---|---|---|
| **#52** stable-id diff on approval | 🟠 open | `/pm-vision-apply` is append-only for adds; without a diff, a regeneration that renumbers ids breaks every sprint story's `implements:` and every alias | **S0**, before any apply |
| **#63** `pm_finish_stage.py` | 🟡 script shipped v1.5.4 | Large stage revisions in `/pm-vision-apply` are written in parts and finished with it | Used as is |
| **#66** large artifacts | 🟠 open | `by-epic/` views are its fix for sprint use | S3 |
| **#65** NFR test-case table rows not indexed | 🟠 open | QA views miss NFR test cases | Known gap, stated in the view header; not fixed here |

## 4. Build chunks

Each chunk is a separate branch and PR, ships with its tests and docs, and passes the §7 gates before the next one starts. Every chunk leaves PM-OS releasable: a PM who never uses sprint mode sees no change.

### S0: groundwork

- Merge `docs/delivery-plan-part-b` (one commit, `4323a56`) and `pm-os-sprint-mode-plan.md`; add this plan. Update `docs/README.md` and the Part B status line.
- **#52 id diff.** On approval of 03, 06 or 08, compare the stable-id set of the new body against the last approved version (from `.history/`) with `artifact_contracts.split_stable_id_blocks`. A removed or renumbered id is reported in the approval output and logged in the `stage_approved` payload (`ids_removed`, `ids_added`). It warns; it doesn't block, matching how approval treats unapproved upstreams.
- Files: `lib/id_diff.py` (new), `scripts/pm_approve.py`.

### S1: the increment record

- `lib/delivery.py`: `path_for`, `load`, `validate`, `expand_members` (epic shorthand), `derive_tasks`, `check_project` returning issues in the `readiness.check_project` shape, so `/pm-check` and the release check consume it the same way.
- `scripts/pm_delivery.py init | check [--json]`. `check` writes `cut_from` only when clean; that is its only write.
- §8.7.4 `INC_*` checks, with the sprint-mode plan's revision (its §7): `INC_MEMBER_UNDEFINED` accepts a `sprint_items` id only if it names an existing VD (that half lands in S2; S1 rejects all `sprint_items`).
- `external: <folder>` increments: closed, no members required, never read.
- `readiness.yaml` `due:` accepts `INC-###` (`lib/readiness.py`).
- `/pm-check` gains a Delivery section beside Readiness; `/pm-status` shows the active increment.
- `lib/project_git.py` ownership entries for `delivery.yaml`.

### S2: vision deltas and `/pm-vision-apply`

- `lib/vision_deltas.py`: parse `### VD-### · title` blocks and their bold labeled fields (the #70 parser pattern already in `artifact_contracts`), validate status/kind values, allocate the next id, `settle(id, status)`.
- `VD_MISSING`, `VD_UNSETTLED`, `VD_ALIAS_MISSING`, `VD_PENDING_OLD` in `/pm-check`'s Delivery section.
- `delivery.yaml` `sprint_items` and `aliases` validation switches on.
- New skill **`skills/pm-vision-apply/`** (`SKILL.md` + `agents/openai.yaml`). The judgment (how to revise each stage) is in `SKILL.md`. Python only lists the deltas by affected stage, records `Applied in`, and writes `aliases`. Stage writes go through the existing stage flow: write in parts → `pm_finish_stage.py <NN>` → `/pm-approve <NN>`; untouched downstream stages → `/pm-approve <NN> --reapprove`.
- Script: `scripts/pm_vision.py deltas list | settle | applied`.

### S3: the derived summary and per-epic views

- `lib/id_views.py`: `carve(body, ids)` returning verbatim blocks plus required ancestors, built on `split_stable_id_blocks` and `delivery_map.build_prd_delivery_map`. Writes `by-epic/EPIC-###/{prd,qa,trd}.md`, `by-epic/core.md`, `by-epic/README.md`.
- `lib/vision_summary.py`: builds `vision.md` from **approved** bodies only (never an `edited` one, using `hashing.mark_edited_in_memory()`), plus delivery status per epic from `delivery.yaml` and open VD counts from `vision-deltas.md`. Frontmatter: `derived: true` and the source stage versions.
- `hooks/post-approve.py`: rebuild both next to the `.traceability.yaml` rebuild, inside the same try/warn wrapper so a failure never blocks approval.
- `scripts/pm_vision.py summary` and `pm_delivery.py views` for on-demand rebuilds.
- Skills 04, 06, 08 and `/pm-feedback`: large-artifact guidance (read `by-epic/` past a `lib` size constant).

### S4: sprint plan and spec

- `lib/sprint_workspace.py`: scaffold `sprints/INC-###/`, parse `sprint.md` version and change log, parse story frontmatter (`implements:`, `delta:`, `jira:`).
- Templates in `templates/sprint/` (`sprint.md`, `story.md`) with generic placeholders only.
- New skills **`pm-sprint-plan`** and **`pm-sprint-spec`** (`--design-kit`). The skill text ranks candidates, but the PM picks; the skill never picks.
- `SPRINT_STORY_UNTRACED`, `SPRINT_NO_CHANGELOG`.
- `sprint.md` "Pulled, not rewritten" sections are written by `carve`, never by the agent.

### S5: per-sprint handoff packages

- `scripts/pm_share.py --package --increment INC-###`: §8.7.5 layout, members plus ancestor closure, `sprint.md` and stories in dev and qa, `qa-readout.md` for qa, the business readout for business.
- Release record: `increment:` in `.releases/REL-###.yaml`; `CHANGES.md` compares within the increment, or against `builds_on` on a first release; the qa regression list comes from it.
- `scripts/pm_handoff.py jira --increment`: ancestor closure, reuse of recorded ticket keys.
- `INC_DESIGN_RETURN_MISSING` and the #78 design-return checks in the release check.
- `skills/pm-handoff/SKILL.md`: `--increment`, and the sentence "never write to Jira unless the PM asks in this turn".

### S6: review, close, Jira read, business readout

- New skills **`pm-sprint-review`** and **`pm-sprint-close`**. Jira reads happen in the skill through the Atlassian connector and land in `jira-snapshot.yaml`; **no script talks to Jira**.
- `/pm-sprint-close` refuses to set `status: closed` while any VD raised in the increment is `proposed` (`VD_UNSETTLED` as an error).
- `JIRA_SNAPSHOT_OLD`.
- Business readout: Markdown updated by plan and close, HTML through `lib/html_render.py`.
- Telemetry events (all chunks, listed here once): `sprint_planned`, `sprint_spec_revised`, `sprint_feedback_logged`, `sprint_closed`, `vision_delta_raised`, `vision_delta_settled`, `vision_delta_applied`; `handoff_released` gains `increment`.

## 5. Conventions every chunk follows

From `CLAUDE.md`; a contract test enforces most of them.

- **Skills carry judgment, Python carries state.** Ranking, writing narrative, disposing feedback and revising stages are in `SKILL.md`; parsing, validating, scaffolding and recording are in Python.
- **Every skill ships `SKILL.md` and `agents/openai.yaml`**, with `reads`/`writes`/`model_tier`. `/pm-vision-apply` is a deep-reasoning skill; it advises the strongest model, never a provider model id.
- **Windows:** `encoding="utf-8"` on every text read/write; `console.ensure_utf8_stdio()` at the top of each new script; `os.path.expanduser('~/.pm-os/lib')` in skill snippets.
- **Non-interactive:** any prompt has an env-var/flag escape and uses `console.stdin_is_interactive()`.
- **Telemetry** goes through `lib/telemetry.log`, wrapped so a failure warns.
- **Docs in the same PR:** `ARCHITECTURE.md` §3 rows, `docs/guides/sop.md` (PM-facing), `docs/guides/testing.md` catalog, `docs/reference/pm-os-spec.md` event list, `CHANGELOG.md` `## Unreleased`, backlog entries closed.

## 6. Tests per chunk

Every test has a docstring and is cataloged in `docs/guides/testing.md` §5. Fixtures are **synthetic** projects built by `tests/helpers.py`. No product's real artifacts are used as fixtures.

| Chunk | Unit (`tests/unit/`) | Integration (`tests/integration/`) | Contract (`tests/contracts/`) |
|---|---|---|---|
| S0 | `test_id_diff.py`: added, removed and renumbered ids; unchanged body is empty diff | `test_approval_id_diff.py`: approving a renumbered 03 warns and logs the diff; approval still succeeds | — |
| S1 | `test_delivery.py`: shape; epic expansion; deferred/duplicate/spill-over; task derivation and `INC_TASK_SPLIT`; `cut_from` only on clean check; `external` increments; `due: INC-###` | `test_delivery_ungated.py`: editing `delivery.yaml` changes no stage state, no hash, no telemetry (mirrors `test_readiness_record.py`) | — |
| S2 | `test_vision_deltas.py`: field parsing, status/kind values, id allocation, settlement rules, `VD_*` codes | `test_vision_apply_flow.py`: two deltas on 03 → one revision, one approval, one cascade; new ids appended, none renumbered (S0 diff empty of removals); `aliases` written; `Applied in` recorded | `pm-vision-apply` has its twin and declares deep reasoning |
| S3 | `test_id_views.py`: carving verbatim with ancestors; cross-epic test cases in both views; built from approved only; frontmatter stamps. `test_vision_summary.py`: approved-only, `edited` stage excluded, delivery status per epic | `test_epic_views.py`: post-approve writes views and `vision.md`; editing either changes no state; re-approval overwrites; a failure in the rebuild warns, approval completes | 04, 06, 08 carry large-artifact guidance |
| S4 | `test_sprint_workspace.py`: scaffold; version and change-log parsing; `SPRINT_STORY_UNTRACED`; `SPRINT_NO_CHANGELOG` | `test_sprint_spec_flow.py`: pulled sections equal `carve` output byte for byte; a sprint item without a VD fails `/pm-check` | `pm-sprint-plan`, `pm-sprint-spec` twins; plan skill says the PM picks |
| S5 | `test_release_check.py`: one case per `INC_*` and `INC_DESIGN_RETURN_MISSING` | `test_increment_package.py`: two increments, each package holds only members and ancestors; dev and qa stories identical; qa readout present; `CHANGES.md` re-cut and first-release-vs-`builds_on`; whole-product `handoff/` untouched. `test_increment_jira.py`: cycle 2 reuses cycle 1's epic key in CSV and plan | `pm-handoff` mentions `--increment` and the Jira write rule |
| S6 | `JIRA_SNAPSHOT_OLD`; close refuses with a `proposed` VD | `test_sprint_close_flow.py`: close auto-defers spill-over, settles VDs, updates the readout, logs `sprint_closed`; HTML render produced | `pm-sprint-review`, `pm-sprint-close` twins and Jira write rule; drift test covers the new events |

**Cross-cutting tests, added in S1 and extended per chunk:**
- **No-regression for non-sprint projects:** the existing lifecycle tests run unchanged; one new test runs the full 01–07 flow on a project with no `delivery.yaml` and asserts no new file appears and no new output line is printed.
- **Engine stays generic:** a contract test that fails if `lib/`, `scripts/`, `hooks/`, `skills/` or `templates/` contain a product name from a deny-list kept in the test (starting with `PRISM`, `APEX`). This keeps Part 2 out of Part 1 mechanically.
- **Windows portability:** `test_windows_portability_contracts.py` already scans new scripts and skills; nothing to add beyond running it.

## 7. Verification gates

A chunk is **done** only when all of these hold, in order:

| # | Gate | How | Pass |
|---|---|---|---|
| G1 | Fast suite | `python3 -m pytest -m "not slow"` | Green, same as CI |
| G2 | Full suite in a clean worktree | `git worktree add` from the PR branch, `python3 -m pytest` | Green, including slow tests; no reliance on local state |
| G3 | CI | `.github/workflows/tests.yml` on the PR | Green on Python 3.11 |
| G4 | Docs consistency | Drift contracts pass; `testing.md` catalogs every new test; SOP describes the PM-facing behavior | Reviewer confirms |
| G5 | Install health | After merge: `python3 ~/.pm-os/scripts/pm_os_update.py --runtime all`, then `pm_os_verify.py --runtime all` | All checks pass on both runtimes. **Only through the update path;** never by copying files into `~/.pm-os` or the skill dirs |
| G6 | Scratch end-to-end | A synthetic project under `~/pm-projects/sprint-mode-scratch/`: 01–07 approved, then the chunk's new skills run through Claude Code and through Codex | The flow completes on both runtimes; `/pm-check` clean |
| G7 | Release bookkeeping | `CHANGELOG.md` `## Unreleased` entries moved under the version the bump workflow assigns; backlog entries updated | Done in the merge follow-up |

G6 builds up across chunks. By S6 it covers the whole loop on the scratch project: plan → spec → handoff → review → close → apply, including one delta of each kind (add, change, drop, defer).

## 8. Usability check (before S6 is called done)

PM-OS is rolled out to PMs who are less technical. Before sprint mode is announced:

- A PM who didn't build it runs one scratch sprint using only the SOP and the skills, without being shown any CLI.
- Record where they got stuck. Any step that needed a script command or YAML editing by hand is a defect in the skill, not a training issue.
- Revisit whether five new skills is the right count. Merging review and close, or plan and spec, is allowed at this point without reopening `pm-os-sprint-mode-plan.md`.

## 9. Risks and rollback

1. **#52 slips.** Then `/pm-vision-apply` can't promise append-only ids. S2 doesn't merge without S0's diff.
2. **The cascade is coarse.** Applying one delta to 03 marks 04–09 stale. Per-stage batching (decision 3), `by-epic/` views and `--reapprove` keep the catch-up small. Per-epic staleness stays out of scope.
3. **The rebuilds in post-approve could slow approval.** They run inside the warn-only wrapper; G6 times approval of a large synthetic 03 before and after S3.
4. **Read-only acceptance on a real product (§9.4 below)** might surface a parser gap the synthetic fixtures missed. That becomes a new synthetic fixture and a fix in the engine, never a product-specific branch in code.
5. **Rollback.** Each chunk is one PR. Because no shared shape changes, reverting a chunk leaves existing projects working; the new files it created are inert without the code.

### 9.4 Read-only acceptance on a real product

After S3 and after S5, run the new read-only commands against PRISM's existing folders, from a copy, to confirm the parsers cope with real artifacts at real size:
- `by-epic/` view sizes compared with the measurements in §8.7.6;
- `/pm-check --release` on the existing hand-built sprint folders.

**Nothing under PRISM is written, moved or re-zipped.** Findings become engine fixes with synthetic fixtures (risk 4). This is the only place Part 1 touches PRISM.

---

# Part 2: Product usage

Everything below is project work done **with** the finished engine. None of it changes PM-OS code, and none of it is a gate for any engine chunk.

## 10. Pilot: PRISM

PRISM is the first product to use sprint mode (sprint-mode plan §10, decision D4, 28 Oct). It's run in PRISM's project folder (`~/pm-projects/prism-ai/` on Karan's machine, an approved 01–09 pipeline), by its PM, through the `/pm-*` skills. The sprint history and evidence are in `~/pm-projects/prism-ai/pmos-sprint-mode/`, starting with `01-process-as-practised.md`. An agent working on Part 1 doesn't need that folder except for the §9.4 read-only checks.

| Step | Needs engine chunks | What the PM does | Writes to |
|---|---|---|---|
| P1. Record history | S1 | `/pm-sprint-plan` records `INC-001`–`INC-003` as `external`, `closed`, pointing at `sprint-1-r2/`, `sprint-2/`, `sprint-3/` (S3 once it closes) | PRISM's `delivery.yaml` only |
| P2. Record the existing drift | S2 | Write each existing drift as a `proposed` VD: the sprint 1 reset; sprint 2's page health checks and technical items; dropped AI crawler checks and report output; parked pharma checks; sprint 3's structures, items, editing and manifest; the dropped Q&A module | PRISM's `vision-deltas.md` |
| P3. Settle and apply | S2, S3 | Settle every VD; apply the chosen ones with `/pm-vision-apply`; approve the revised stages; aliases for in-flight sprint ids | PRISM's 03/06/08/09 through normal approval |
| P4. Plan and spec sprint 4 | S4 | `/pm-sprint-plan`, `/pm-sprint-spec` against `vision.md` | `sprints/INC-004/` |
| P5. Hand off | S5 | `/pm-handoff --package --increment INC-004`; Jira read-only; Jira write only if the PM asks | `handoff/INC-004/` |
| P6. Review and close | S6 | `/pm-sprint-review` through the sprint; `/pm-sprint-close` at the end | `review.md`, `close.md`, readout |

The existing sprint 1–3 folders are never moved, renamed or re-zipped.

**Timing:** P1 can start as soon as S1 ships, without waiting for later chunks. If sprint 4 starts before S4–S6 are ready, PRISM uses the interim route in §8.7.7 for that sprint (`/pm-check --release` on the hand-built folder, `readiness.yaml` for what's owed) and adopts the skills from sprint 5. The engine schedule doesn't bend to the sprint calendar.

## 11. Pilot outcomes to measure

These measure whether sprint mode works for a product team. They are not engine tests and don't block any chunk.

| Measure | Baseline (sprints 1–3, outside PM-OS) | Target for sprint 4 or 5 |
|---|---|---|
| Time from sprint pick to a dev pack | From PRISM's sprint history | Shorter |
| Release-check errors caught before send | Errors found later in hand-built folders (§8.7.8: broken links, undefined ids, missing priorities) | Caught before send; zero sent |
| Re-cuts of a sprint pack | r4–r9 re-zips | Versioned `sprint.md` with change log and `CHANGES.md` |
| VDs raised and settled | 0 recorded | Every one settled at close |
| Sprint stories citing a vision id or VD | 0 | 100% (`SPRINT_STORY_UNTRACED` clean) |
| What dev, QA or APEX had to ask for outside the pack | From APEX feedback (#70–#79) | Logged in `review.md`; each becomes an engine backlog item or a project fix |

Pilot findings that need engine changes go into `docs/roadmap/backlog.md` as generic items, with PRISM named only as the source of the evidence.

## 12. Next steps

**Engine (this repo):**
1. Confirm the seven decisions in §2.
2. S0: merge the docs branch and both plans; build the #52 id diff.
3. S1 → S6 in order, each through the §7 gates.

**Usage (PRISM's project, run by its PM):**
1. After S1: record sprints 1–3 (P1).
2. After S2: record and settle the existing drift (P2–P3).
3. Choose whether sprint 4 runs on the interim route or waits for S4–S6.
