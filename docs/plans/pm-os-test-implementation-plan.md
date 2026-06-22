# PM-OS Test Implementation Plan

**Status:** Draft plan
**Scope:** Add a comprehensive automated test suite for PM-OS covering health, local-first lifecycle behavior, deliverable contracts, runtime parity, connection boundaries, and failure recovery.

PM-OS is not a service with one API boundary. It is a local filesystem state machine plus a skill/document contract. The test suite must therefore protect both halves:

- deterministic Python helpers, hooks, templates, and scripts
- the Markdown skill protocol that tells agents how to generate, approve, verify, share, and sync product artifacts

The suite should test the repo source tree directly. It must not hand-modify or depend on the installed `~/.pm-os`, `~/.agents/skills`, or `~/.claude/skills` directories.

---

## 1. Success definition

The suite is successful when a contributor can run one command from the repo and get meaningful confidence that:

1. PM-OS can create and operate a project in an isolated temp environment.
2. Stage gates block unsafe progression and allow valid progression.
3. Approval, hashing, telemetry, staleness, feedback, sharing, sync, and HTML companion rendering behave consistently.
4. Skill files, docs, scripts, and runtime instructions do not drift from each other.
5. Failure cases produce clear errors without corrupting local project state.
6. External side effects are isolated, mocked, or pointed at local temp repositories.

The default local verification command should eventually be:

```bash
python3 -m pytest
```

The first implementation may use markers to make slower coverage explicit:

```bash
python3 -m pytest -m unit
python3 -m pytest -m integration
python3 -m pytest -m contract
```

---

## 2. Test harness plan

### Implementation

- Add `pyproject.toml` with pytest configuration and markers:
  - `unit`
  - `integration`
  - `contract`
  - `connection`
  - `slow`
- Add `tests/` with:
  - `tests/conftest.py`
  - `tests/helpers.py`
  - `tests/unit/`
  - `tests/integration/`
  - `tests/contracts/`
  - `tests/fixtures/`
- Create fixtures for:
  - isolated HOME-like directory
  - temp PM-OS install tree copied from the repo source
  - temp Claude config dir
  - temp Codex skills dir
  - temp PM projects dir
  - sample `.meta.yaml` projects
  - sample stage artifacts with frontmatter
  - local bare git feedback repo
- Run scripts via subprocess with explicit environment:
  - `PM_OS_DIR=<tmp install>`
  - `CLAUDE_CONFIG_DIR=<tmp claude dir>`
  - `CODEX_SKILLS_DIR=<tmp codex skills dir>`
  - `PM_OS_PROJECTS_DIR=<tmp projects dir>`
  - `PYTHONPATH=<repo>/lib`

### Success criteria

- Tests never write to real user install paths.
- Fixtures can create a valid scratch PM-OS project in a temp directory.
- Scripts can run from the source tree without syncing uncommitted code into installed skill directories.
- Tests are deterministic and can run repeatedly in any order.

### Failure criteria

- Any test writes under real `~/.pm-os`, `~/.agents`, `~/.claude`, or `~/pm-projects`.
- Tests depend on local machine state outside the repo and temp dirs.
- Running tests twice produces different results without code changes.
- Tests require network access for default verification.

### Verification

```bash
python3 -m pytest tests/test_harness_smoke.py
python3 -m pytest --collect-only
```

Also inspect temporary paths in failures to confirm they point under pytest temp dirs, not user runtime dirs.

---

## 3. Unit test coverage

### Implementation

Add focused tests for shared modules:

- `lib/project.py`
  - `resolve_project`
  - `artifact_path`
  - `get_stage`
  - `upstream_stage_ids`
  - `downstream_stage_ids`
  - `migrate_meta`
  - `resolve_backfill`
- `lib/frontmatter.py`
  - `read`
  - `write`
  - `update_status`
- `lib/hashing.py`
  - body-only artifact hashing
  - event hash canonicalization
- `lib/config.py`
  - config loading
  - env migration
  - model tier defaults
  - deep-reasoning stage selection
- `lib/telemetry.py`
  - append event
  - last event lookup
  - verify hash chain
  - detect tampered/corrupt telemetry
- `lib/html_render.py`
  - section parsing
  - markdownish rendering
  - HTML escaping
  - design/prototype companion render
- `lib/git_sync.py`
  - no config skip
  - local feedback repo clone/copy/commit path
  - no-op when there are no changes

### Success criteria

- Every shared module has direct tests for normal and edge cases.
- Hash tests prove frontmatter edits do not change body hashes.
- Telemetry tests prove hash chains detect tampering.
- HTML render tests prove user content is escaped.
- Optional stage dependency tests cover stage 08 and stage 09 behavior.

### Failure criteria

- A malformed `.meta.yaml` or artifact crashes in an unclear way where a clearer failure is expected.
- Hashes change when only frontmatter changes.
- Telemetry tampering is not detected.
- HTML companion output can inject raw script tags from artifact content.
- Stage 09 ignores approved stage 08 when it should include it as optional context.

### Verification

```bash
python3 -m pytest tests/unit
```

Inspect coverage output once coverage is added:

```bash
python3 -m pytest tests/unit --cov=lib --cov=hooks --cov=scripts
```

---

## 4. Lifecycle integration tests

### Implementation

Add subprocess-based tests for the local project lifecycle:

1. `pm_new` creates a project with:
   - `.meta.yaml`
   - `00-business-statement.md`
   - `.history/`
   - `telemetry.jsonl`
   - `feedback.jsonl`
   - correct `genai_flag`
2. `pm_approve 00` approves the business statement and logs telemetry.
3. `pre-stage.py` blocks stage 02 when stage 01 is not approved.
4. `pre-stage.py` allows stage 01 after all present stage-00 docs are approved.
5. Editing an approved upstream artifact marks it `edited`.
6. `PM_OS_EDITED_UPSTREAM_CHOICE=continue` implicitly reapproves edited upstreams.
7. `post-approve.py` marks downstream approved stages stale.
8. Stage 04 approval renders `04-design-spec.html`.
9. Stage 05 approval renders `05-prototype-mockup.html`.
10. `pm_status` reports status, origin, feedback count, telemetry count, and recent events.
11. `pm_share` exports approved or edited stages only.

### Success criteria

- A scratch project can execute the core lifecycle without touching real install paths.
- Meta status and artifact frontmatter status stay synchronized.
- Approval computes and records content hashes.
- Downstream stale cascade updates both `.meta.yaml` and artifact frontmatter.
- HTML companion rendering failure warns without corrupting approval state.
- Share output includes approved content and excludes pending drafts.

### Failure criteria

- Downstream stages can be generated from unapproved upstreams.
- Approval succeeds for missing, pending, or unknown stages.
- Status in `.meta.yaml` disagrees with artifact frontmatter after a helper command.
- Stale cascade misses an approved downstream stage.
- `pm_status` reports misleading stage state after drift or stale propagation.

### Verification

```bash
python3 -m pytest tests/integration/test_project_lifecycle.py
python3 -m pytest tests/integration/test_stage_gates.py
python3 -m pytest tests/integration/test_approval_and_staleness.py
```

For manual spot verification, run the same flow in a temp project and inspect:

```bash
python3 scripts/pm_status.py
python3 scripts/pm_share.py
```

---

## 5. Deliverable and format contract tests

### Implementation

Add tests that inspect skill Markdown and expected artifact contracts. These tests should not judge LLM prose quality; they should validate the stable protocol the skill promises.

Check every `skills/*/SKILL.md` for:

- valid YAML frontmatter
- `name`
- `description`
- no provider-specific model IDs in shared frontmatter
- runtime-neutral model tier language
- Claude and Codex invocation examples where user-facing entrypoints are printed

Check every stage skill `01` through `09` for:

- correct pre-stage gate command with matching `PM_OS_STAGE`
- explicit input artifact list
- output filename
- required artifact frontmatter keys
- history snapshot instruction
- `.meta.yaml` update instruction
- `stage_generated` telemetry instruction
- quality/self-check section
- `generation_notes` carry-forward behavior where applicable

Check deliverable section contracts for:

- stage 01 product brief sections
- stage 02 scope sections
- stage 03 PRD sections
- stage 04 design spec sections
- stage 05 prototype brief sections
- stage 06 QA plan sections
- stage 07 metrics plan sections
- stage 08 TRD sections
- stage 09 roadmap sections

### Success criteria

- Skill files parse cleanly as Markdown with YAML frontmatter.
- Stage skills contain all mechanical write/update/log instructions.
- GenAI and non-GenAI variants are described consistently.
- Runtime examples stay paired: Claude slash command and Codex `$skill` command.
- Stage names, file names, and IDs match `lib/project.py`.

### Failure criteria

- A skill writes a stage file name that does not match `artifact_path`.
- A stage skill omits the pre-stage gate.
- A stage skill instructs approval or telemetry differently from the deterministic helper scripts.
- Shared skills encode a concrete provider model ID.
- Docs say one runtime path and scripts use another.

### Verification

```bash
python3 -m pytest tests/contracts/test_skill_contracts.py
python3 -m pytest tests/contracts/test_stage_artifact_contracts.py
```

When a contract test fails, compare:

- `skills/<skill>/SKILL.md`
- `lib/project.py`
- `scripts/pm_approve.py`
- `hooks/pre-stage.py`
- `hooks/post-approve.py`
- README/AGENTS/CLAUDE guidance

---

## 6. Health and runtime parity tests

### Implementation

Test installer, updater, verifier, and runtime-specific sync behavior:

- `pm_os_install.py`
  - non-interactive success with required args/env
  - missing `pm_user` fails clearly
  - default feedback repo behavior
  - reconfigure behavior
  - model policy fields are written
- `pm_os_update.py`
  - `--runtime` is required
  - `claude`, `codex`, and `all` are accepted
  - unsupported runtime fails
  - Codex sync copies skills only
  - Claude sync copies skills and hooks
  - dirty/diverged git states are rejected unless explicitly reset
- `pm_os_verify.py`
  - complete temp install passes
  - missing config fails
  - missing lib module fails
  - missing hook fails
  - missing runtime skills fail for explicit runtime
  - gate self-test blocks and allows the expected stages

### Success criteria

- Claude and Codex install/update behavior remain intentionally different only where documented.
- Verifier catches incomplete installs.
- Runtime skill sync never requires copying into real user directories.
- `--runtime` remains explicit for install/update paths.

### Failure criteria

- Codex is treated as requiring Claude hook copies.
- Update sync silently skips missing skills.
- Verifier passes without required hooks or lib modules.
- Install/update writes provider-specific model IDs into shared config.

### Verification

```bash
python3 -m pytest tests/integration/test_install_verify_update.py
```

Manual verifier smoke test against an isolated temp install should run:

```bash
PM_OS_DIR=<tmp-pm-os> CODEX_SKILLS_DIR=<tmp-skills> python3 scripts/pm_os_verify.py --runtime codex
```

---

## 7. Context import and source provenance tests

### Implementation

Test `scripts/pm_context_import.py` mechanical behavior:

- `register`
  - preserves raw source under `.history/`
  - updates `.sources.yaml`
  - logs `context_ingested`
  - fails for missing source file
- `preflight`
  - reports no gaps when none exist
  - reports faithful backfill
  - reports lossy backfill
  - exits non-zero for infeasible gaps
- `commit`
  - refuses unknown stage IDs
  - refuses missing artifact slot
  - inserts context stages in canonical order
  - commits draft artifacts with origin
  - commits approved artifacts with hash, approval metadata, upstream hashes, telemetry
  - invokes post-approve when appropriate

### Success criteria

- Imported/backfilled/generated origins are preserved in meta and frontmatter.
- Raw source provenance is recorded and relative to the project where expected.
- Backfill feasibility matches `resolve_backfill`.
- Context stages `00w` and `00u` gate stage 01 when present.

### Failure criteria

- Source registration drops or mutates the original source.
- Infeasible backfill exits zero.
- Commit approves a missing artifact slot.
- Imported artifacts lose provenance fields.

### Verification

```bash
python3 -m pytest tests/integration/test_context_import.py
```

---

## 7A. Context overlay tests (`lib/context.py` + skill integration)

> Added after the context-overlay feature shipped. The overlay is the
> company/team/stage context layer seeded from `context.example/` into the
> gitignored `~/.pm-os/context/`. Its load path runs on **every** stage, so its
> guarantees (especially the no-op and fail-loud ones) are high-value to lock down.
> Tests live in `tests/unit/test_context.py` and `tests/integration/test_context_overlay.py`,
> using a temp `PM_OS_DIR` env override so nothing touches the real install.

### Implementation

Unit (`tests/unit/test_context.py`):
- **No-op guarantee:** an all-TODO/seed-identical pack → `render_context()` returns `""`
  and `resolve_context()["has_content"] is False`, for every stage `01`–`09`. This is
  the contract that "no overlay configured ⇒ behaves exactly as today."
- **Substance detection:** `_clean` strips HTML comments + blockquote guidance; a file
  that is only headings/comments is dropped; a file unchanged from its `context.example/`
  seed is treated as unfilled (covers seed scaffolding that survives `_clean`, e.g. an
  empty glossary table).
- **Fail loud on malformed manifest:** a `context.yaml` with a YAML error makes
  `resolve_context`/`render_context` raise `ValueError` (NOT silently return `{}`/`""`).
  Regression guard for the silent-no-overlay bug.
- **Filled content surfaces:** one real line in `global/company.md` → appears in the
  rendered block for every stage, with the `apply: augment` directive; guidance
  blockquotes are stripped from output.
- **Apply modes:** `augment` / `override` / `reference-only` each emit their correct
  directive text.
- **Layering precedence (project > stage > global):** a *partial* project manifest
  (one extra `global:` file, or only a stage's `format`/`apply`) **layers over** the base
  — base global files and base stage `examples` survive; project files win for duplicate
  paths/fields; global lists union. Regression guard for the shallow-merge bug.
- **`seed_context()`:** empty `context/` → all `context.example/` files copied; a
  pre-existing edited file is **not** overwritten; a newly-added seed file IS copied;
  returns the count.
- **Lazy bootstrap:** with `context.example/` present but `context/` absent, the first
  `render_context()` self-seeds `context/` and is still a no-op. Regression guard for the
  self-update bootstrap gap.

Integration (`tests/integration/test_context_overlay.py`):
- The "Load context overlay" step contract: every `skills/pm-stage-*/SKILL.md` contains a
  `render_context('NN', …)` invocation with the stage's own id, and the surrounding
  instruction (use per `apply` directive; empty ⇒ no overlay; **error ⇒ stop, malformed
  manifest, not "no overlay"**).
- `pm_os_install.py` / `pm_os_update.py` seed `context/` from `context.example/` on a temp
  install; existing edited files are preserved.
- `pm_os_verify.py` context-pack check: passes when manifest parses; warns (does not fail)
  on a dangling referenced file; reports "not configured" when absent.

### Success criteria

- Overlay is provably a no-op until filled in, on every stage.
- Malformed manifest fails loud; partial project override never drops base context.
- Seeding never overwrites PM edits; bootstrap covers the absent-`context/` case.

### Failure criteria

- An unfilled or seed-identical pack injects anything into a stage prompt.
- A YAML typo silently degrades to "no overlay."
- A partial project manifest wipes base global/stage content.
- Any overlay test reads or writes the real `~/.pm-os/context/`.

### Verification

`python3 -m pytest tests/unit/test_context.py tests/integration/test_context_overlay.py`

---

## 8. Feedback, telemetry, and connection boundary tests

### Implementation

Test local feedback and optional git sync without network access:

- `pm_feedback.py`
  - rating and note write JSONL
  - skip rating/note behavior
  - non-interactive failure when required values are missing
  - unknown stage failure
- `telemetry.py`
  - hash chain remains intact across lifecycle events
  - corruption is detected with line number and reason
- `git_sync.py`
  - no config means skip
  - missing feedback repo means skip
  - local bare repo can receive copied telemetry and feedback
  - no commit is made when there are no changes

### Success criteria

- Default tests do not perform network operations.
- Feedback JSONL and telemetry JSONL remain parseable after repeated writes.
- Local git sync test proves the integration path without pushing to a remote service.

### Failure criteria

- Any default test contacts GitHub or another remote.
- Feedback capture writes invalid JSON.
- Telemetry chain can be modified without detection.
- Git sync crashes when config is absent.

### Verification

```bash
python3 -m pytest tests/integration/test_feedback.py
python3 -m pytest tests/unit/test_telemetry.py
python3 -m pytest tests/integration/test_git_sync_local.py
```

---

## 9. Telemetry metrics tests

### Implementation

Add tests for the metrics that PM-OS derives from the telemetry stream, artifact snapshots, approval payloads, and feedback events. These should use small deterministic fixtures rather than real model output.

- Generation duration
  - create a stage with `stage_started` and `stage_generated` timestamps
  - assert the aggregation/helper layer can derive elapsed generation time
  - verify repeated generations use the correct stage-specific event pair
- Approval duration
  - create a generated draft with a matching `stage_generated` event
  - approve it
  - assert `stage_approved.payload.time_to_approve_seconds` is non-null and positive
  - assert imported/backfilled/stage-00 artifacts without generated snapshots keep this metric `null`
- Edit-distance metrics
  - create `.history/<stage>.<timestamp>.generated.md`
  - approve an unchanged artifact and assert `char_edit_distance == 0` and `normalized_edit_distance == 0`
  - approve an edited artifact and assert both edit metrics increase
  - assert missing history snapshots leave edit metrics `null`
- Semantic-distance passthrough
  - approve with `--semantic-distance 0.25` and assert the payload records `0.25`
  - approve without the flag and assert `semantic_distance` is `null`
  - invalid values below `0` or above `1` fail without approving
- Model telemetry
  - contract-test every stage skill logs `stage_generated.payload.model`
  - assert `model_tier` is produced through `model_tier_for_stage(stage_id)`
  - assert the deep-reasoning stages (`00w`, `00u`, `03`, `04`, `06`, `08`, `09`) resolve to `deep-reasoning`; other stages resolve to the configured default
- Regeneration metrics
  - generate a stage twice
  - assert `.meta.yaml.stages[].regeneration_count` increments
  - assert approval payload includes the final `regeneration_count`
- Feedback metrics
  - run `pm_feedback.py --rating <n> --note <text>`
  - assert `feedback.jsonl` contains the rating/note
  - assert `telemetry.jsonl` contains a matching `feedback_submitted` event
  - assert the telemetry chain remains valid after feedback submission
- Drift and stale metrics
  - edit an approved upstream artifact
  - run the pre-stage gate and assert `stage_edited_post_approval`
  - continue with implicit reapproval and assert `implicit_reapproval` plus downstream `stage_marked_stale`
- Sync/readiness metrics
  - run `pm_sync.py --verify` on intact and corrupted chains
  - assert it reports project-level pass/fail status and line-level break information

### Success criteria

- Metric tests prove timing, edit distance, model metadata, feedback, regeneration, drift, and sync-readiness signals are actually populated where expected.
- Tests distinguish direct facts from derived metrics.
- Metrics that are intentionally unavailable stay `null` rather than being faked.
- Hash-chain validation passes after metric-bearing events and fails after tampering.
- Metric fixtures are deterministic and do not require real model calls or network access.

### Failure criteria

- `stage_approved` emits `None` for timing/edit metrics when generated snapshots and events exist.
- Imported, backfilled, or stage-00 artifacts receive misleading generated-draft metrics.
- Invalid semantic-distance values are accepted.
- Stage skills omit the actual model field or bypass `model_tier_for_stage`.
- Feedback is captured only in `feedback.jsonl` and not in the telemetry chain.
- Metric events break the telemetry hash chain.

### Verification

```bash
python3 -m pytest tests/integration/test_telemetry_metrics.py
python3 -m pytest tests/contracts/test_telemetry_metric_contracts.py
python3 -m pytest tests/unit/test_text_metrics.py
```

---

## 10. Negative, resilience, and recovery tests

### Implementation

Add tests for hostile or broken local state:

- malformed `.meta.yaml`
- missing `.meta.yaml`
- duplicate stage entries
- unknown stage IDs
- missing artifact files
- artifact without frontmatter
- invalid YAML frontmatter
- missing `.history`
- empty business statement
- corrupt telemetry lines
- stale meta/frontmatter disagreement
- partial HTML render failure
- hook failure after approval

### Success criteria

- Commands fail fast with actionable messages when state is unusable.
- Commands do not silently repair ambiguous corruption unless migration logic explicitly owns that repair.
- Partial failures do not leave approved artifacts with pending meta or the inverse.
- Idempotent commands stay idempotent:
  - approve already-approved stage
  - verifier twice
  - status twice
  - share twice
  - render HTML twice

### Failure criteria

- A helper crashes with an unhelpful traceback for expected user-facing mistakes.
- A failed command leaves mixed approval state.
- Running an idempotent command twice changes hashes or telemetry unexpectedly.
- Corrupt telemetry is treated as valid.

### Verification

```bash
python3 -m pytest tests/integration/test_failure_recovery.py
python3 -m pytest tests/integration/test_idempotency.py
```

---

## 11. Security, privacy, and local-first tests

### Implementation

Add tests that guard PM-OS's local-first promise:

- commands operate only inside configured project/temp dirs
- source registration cannot write outside project `.history`
- share output path behavior is explicit and tested
- HTML companion output escapes untrusted Markdown content
- no default command attempts network access
- feedback sync is isolated behind explicit config and local test repos
- generated tests do not embed secrets, tokens, or real user paths in fixtures

### Success criteria

- Local project data stays local by default.
- HTML render escapes unsafe content.
- Tests can prove external connection points are opt-in and mockable.
- Path handling is explicit enough to prevent accidental writes into unrelated directories.

### Failure criteria

- Normal lifecycle commands contact external services.
- Artifact content is emitted as unsafe raw HTML in companion files.
- A malicious source filename can escape `.history` or overwrite project files.
- Tests require credentials.

### Verification

```bash
python3 -m pytest tests/contracts/test_local_first_boundaries.py
python3 -m pytest tests/unit/test_html_render.py
```

---

## 12. Documentation drift tests

### Implementation

Add contract tests that compare docs, scripts, and skills for stable facts:

- supported runtimes: Claude and Codex
- install/update require explicit runtime argument
- Codex skill path: `~/.agents/skills`
- Claude skill path: `~/.claude/skills`
- gate execution path: `~/.pm-os/hooks`
- stage list and filenames
- optional stage semantics for 08 and 09
- model tier policy:
  - default `standard`
  - deep-reasoning stages `00w`, `00u`, `03`, `04`, `06`, `08`, `09`
- no shared config/provider-specific model IDs

### Success criteria

- README, AGENTS, CLAUDE, skills, and scripts agree on runtime paths and commands.
- Stage IDs and filenames in docs match `lib/project.py`.
- Model policy is runtime-neutral in shared docs and skill frontmatter.

### Failure criteria

- Docs instruct `/pm-stage-*` only without Codex `$pm-stage-*` guidance where both should appear.
- Docs mention an obsolete Codex path.
- A stage is documented but missing from `STAGE_NAMES`, or vice versa.
- Deep-reasoning stage policy differs between docs and config defaults.

### Verification

```bash
python3 -m pytest tests/contracts/test_documentation_drift.py
```

---

## 13. Performance and scale tests

### Implementation

Add a small number of non-default or marked tests for larger local inputs:

- large markdown artifacts
- large telemetry files
- many feedback entries
- many registered sources
- full stage list status rendering

These should be marked `slow` only if they materially increase runtime.

### Success criteria

- Status, share, telemetry verification, and source registration remain usable for realistic project sizes.
- Large-file behavior does not time out under normal local execution.

### Failure criteria

- Status or share becomes noticeably slow with normal project history.
- Telemetry chain verification cannot handle a project-length event log.
- Source registration degrades sharply with many sources.

### Verification

```bash
python3 -m pytest -m slow
```

---

## 14. CI plan

### Implementation

Add a GitHub Actions workflow after the local suite exists:

- checkout repo
- set up Python 3.11
- install test dependencies
- run `python3 -m pytest`

Optional later additions:

- coverage report
- separate slow job
- contract-only job for docs/skills changes

### Success criteria

- CI runs on pull requests and main branch pushes.
- CI has no network dependency except installing test dependencies.
- CI artifacts show clear failing test names and assertion messages.

### Failure criteria

- CI depends on a developer's local PM-OS install.
- CI writes to real home runtime dirs.
- CI requires real feedback repo credentials.

### Verification

```bash
python3 -m pytest
```

Then confirm the workflow passes in GitHub Actions.

---

## 15. Implementation sequence

| Phase | Work | Exit criteria |
|---|---|---|
| T0 | Add pytest config, fixtures, helpers, and harness smoke test | Tests collect and run in isolation |
| T1 | Add unit tests for `lib/` modules (incl. `context.py`, `text_metrics.py`) | Core helpers covered for normal and edge cases |
| T2 | Add lifecycle integration tests for project create, approve, gates, stale cascade, status, share | Scratch project flow verified |
| T3 | Add skill and artifact contract tests | Skills/docs/scripts cannot silently drift |
| T4 | Add install/update/verify runtime parity tests | Claude/Codex sync and verifier behavior covered |
| T5 | Add context import, context **overlay** (§7A), feedback, telemetry, local git sync tests | Provenance, overlay no-op/fail-loud/layering, and connection boundaries covered |
| T6 | Add telemetry metrics tests | Timing, edit-distance, model, feedback, regeneration, drift, and sync-readiness metrics are verified |
| T7 | Add negative/idempotency/recovery tests | Broken local state fails clearly and safely |
| T8 | Add local-first/security/documentation drift tests | Trust and privacy guarantees covered |
| T9 | Add CI workflow and optional coverage | Suite runs automatically |
| T10 | **PM consistency toolkit (final phase, §19)** — built **after T9 is green** | `lib/consistency.py` shared by tests + `/pm-check`; live project audits against the at-rest invariants |

---

## 16. Initial acceptance criteria for the test project

- [ ] `python3 -m pytest --collect-only` succeeds.
- [ ] Unit tests cover `project`, `frontmatter`, `hashing`, `config`, `telemetry`, `text_metrics`, `context`, and `html_render`.
- [ ] Context-overlay tests cover the no-op-when-unfilled guarantee, fail-loud on malformed manifest, project>stage>global layering, apply modes, `seed_context`, and the lazy-bootstrap path (§7A).
- [ ] Optional-stage tests cover 09 gaining 08 as an upstream only when 08 is approved, and approving 08 after 09 marking 09 stale.
- [ ] Integration tests create and operate a scratch PM-OS project without touching user install paths.
- [ ] Gate tests cover approved, pending, stale, edited, and implicitly reapproved upstream states.
- [ ] Approval tests validate frontmatter/meta/hash/telemetry synchronization.
- [ ] Telemetry metrics tests validate generation duration, approval duration, edit distance, semantic-distance passthrough, model/model-tier capture, regeneration count, feedback events, drift events, and sync verification.
- [ ] Contract tests validate skill frontmatter, pre-stage gates, write-output instructions, runtime examples, and provider-neutral model policy.
- [ ] Context import tests cover register, preflight, commit draft, and commit approved paths.
- [ ] Runtime tests cover install/update/verify for Claude and Codex temp dirs.
- [ ] Local-first tests prove default commands do not require network or credentials.
- [ ] Documentation drift tests compare stage lists, runtime paths, and model tier policy.
- [ ] CI runs the default suite successfully.

---

## 17. Out of scope for the first pass

- Evaluating LLM-generated prose quality beyond stable section/frontmatter contracts.
- Running real Claude or Codex skill invocation in CI.
- Pushing telemetry to a real remote feedback repository.
- Installing PM-OS into real user runtime directories as part of tests.
- Full mutation testing.
- Browser visual regression for generated HTML companions.

These can be added later once the deterministic suite is reliable.

---

## 18. Extensibility for future phases

The suite must absorb planned phases (enhancement/codebase-understanding mode, Jira/Linear/Figma
handoff, stable REQ-/TC- IDs + traceability, QA bug triage, release readiness, feedback intake —
see `docs/plans/pm-os-modes-and-handoff-plan.md` and `docs/roadmap/current-state-review.md`) without
restructuring. Conventions that make that cheap:

- **Data-driven contracts, not hardcoded lists.** Stage contract tests iterate over
  `project.STAGE_ORDER` / `STAGE_NAMES` / `CORE_STAGE_ORDER` and the `context.yaml` `stages:` map,
  so adding a stage (or a new stage-00-style gated doc) auto-extends coverage. New event types are
  asserted against a single `EVENT_TYPES` table mirrored from the spec, so adding one is a one-line
  table edit.
- **Phase markers.** Register pytest markers per phase (`phase1` … current; `phase3_enhancement`,
  `phase4_handoff`, `phase5_triage`, `phase6_release` reserved). Future-phase test files are added
  under the existing `tests/{unit,integration,contracts}/` dirs and tagged with their marker; CI can
  run `-m "not phase3_enhancement"` until a phase lands. No new top-level layout.
- **Capability gating.** A `requires_feature(name)` helper skips (not fails) a test when the
  capability isn't built yet (e.g. `project_type=enhancement`, `pm-handoff`, `.traceability.yaml`),
  so reserved tests can be committed ahead of the feature and flip live when it ships.
- **Shared fixtures stay generic.** The scratch-project and temp-install fixtures take parameters
  (stage set, `project_type`, mounted context pack) rather than baking in the v1 pipeline, so an
  enhancement-mode project or a handoff target is a fixture arg, not a new harness.
- **One source of truth per contract.** Runtime paths, stage list, model policy, and event list are
  asserted from the code/spec constants the implementation also reads — never re-typed in tests — so
  a future phase that changes a constant updates code, test expectation, and docs in lockstep.

---

## 19. T10 — PM consistency toolkit (final phase)

> **Built last — only after T0–T9 are complete and verified.** It leans on the matured harness
> and the T7 negative fixtures, and it reuses the invariant logic the earlier phases assert.

A **read-only toolkit the PM reaches for when something feels wrong** with their project. The
test suite asserts PM-OS invariants on throwaway projects; the same invariants matter for a PM's
*live* project mid-work, but today they're scattered across `pm_approve.py`/`pre-stage.py`/
`post-approve.py` and enforced only at the moment of an operation — there is no single
"is this project internally consistent right now?" check.

### Design

- **`lib/consistency.py` → `check_project(project_root) -> list[Issue]`** — the single source of
  truth, reusing existing lib (`project`, `hashing`, `frontmatter`, `telemetry.verify_chain`).
  `Issue = {code, severity (error|warning), stage, message, remediation}`; empty list == healthy.
  Plus `format_report(issues)` and `summary_line(issues)`.
- **Shared with the tests:** the correlated suites are refactored to assert `check_project`
  against healthy + corrupted fixtures, so the "testing apparatus" and the runtime check are one
  piece of logic. Correlated: `test_telemetry` (chain), `test_hashing` (body-hash drift),
  `test_project` (ordering + schema shape), `test_approval_and_staleness` (meta↔frontmatter sync),
  `test_stage_gates` (no approval over an unapproved upstream). Behavior-only suites
  (`text_metrics`, `html_render`, `config` model-tier, `git_sync` stubs, context apply-mode/
  no-op/layering) do **not** correlate and stay as-is.
- **Read-only:** diagnoses and prints the remediation command (e.g. "stage 03 body drifted — run
  /pm-approve 03 or regenerate"); never mutates state. Fixes still flow through the normal gated
  commands.

### Invariants checked (at rest)

- meta↔frontmatter status sync; for approved/edited, `content_hash` matches between them (error)
- approved stage body still hashes to its recorded `content_hash` — drift (warning; the gate
  marks it `edited` on the next run)
- no `approved` stage has an upstream in {pending, draft, stale} (error; `edited` allowed)
- telemetry hash chain intact via `verify_chain` (error, with break line/reason)
- schema/stage shape: `schema_version` present; valid stage `id`/`status`/`origin`; required
  fields present (error)
- every non-`pending` stage has its artifact file (error)
- project `<project>/context/context.yaml` and `.sources.yaml` parse if present (error)

### Surfaces

- **`/pm-check`** (new `skills/pm-check/` + `scripts/pm_check.py`) — on-demand audit; exit 1 on
  any error (warnings listed, exit 0).
- **pre-stage gate** — a non-blocking advisory summary (read-only) before generation; the
  existing gate stays the authoritative blocker.
- **`/pm-status`** — a one-line consistency verdict.

### Out of scope
Auto-fix/reconciliation (read-only); cross-project auditing (that's `/pm-sync --verify`); install
health (that's `pm_os_verify`); changing the gate's blocking behavior.

---

End of plan.
