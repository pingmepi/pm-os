# PM-OS Testing

The single reference for the PM-OS test apparatus. Read this top-to-bottom to
understand the whole suite; jump to a suite section to understand one test you're
reviewing. Every test also carries a docstring saying what it checks and why — this
doc and those docstrings are kept in lockstep (see [Conventions](#conventions-for-adding-tests)).

The implementation roadmap (which phases exist, exit criteria) lives in
[`docs/plans/pm-os-test-implementation-plan.md`](../plans/pm-os-test-implementation-plan.md).
This doc describes what is **built**.

---

## 1. What we're testing and why

PM-OS is not a service with one API boundary — it's a **local filesystem state machine
plus a skill/document contract**. So the suite protects two halves:

- the deterministic **Python** (`lib/`, `scripts/`, `hooks/`) that scaffolds, hashes,
  approves, gates, records telemetry, syncs, and renders;
- the **Markdown skill protocol** (`skills/*/SKILL.md`) + docs/spec that tell the agent how
  to generate/approve/verify — checked for *contract stability*, not prose quality.

Guiding properties every test upholds:

- **Isolation** — tests never read or write the real `~/.pm-os`, `~/.claude`, `~/.agents`,
  `~/pm-projects`, or the real feedback repo. Everything runs in a temp install.
- **Determinism** — no network, no real model calls, no clock/order dependence.
- **Safety** — broken/hostile local state must fail with a clear error, never corrupt a project.

## 2. Running the suite

```bash
python3 -m pytest                 # full suite
python3 -m pytest tests/unit      # one layer
python3 -m pytest -m unit         # by marker
python3 -m pytest -m "not slow"   # skip perf cases (the default fast run)
python3 -m pytest tests/unit/test_context.py -k layering -v   # one test
```

Dependencies (local/CI): `pytest`, plus the runtime deps `pyyaml` and `jinja2`.
Config + markers live in `pyproject.toml` (`[tool.pytest.ini_options]`).

## 3. The harness (`tests/conftest.py`, `tests/helpers.py`)

PM-OS code resolves its home two ways, so the harness isolates both:

- **Subprocess (integration):** scripts/hooks do `Path.home()/".pm-os"` at runtime, so they
  run with an `env` whose `HOME` points into the temp tree.
- **In-process (unit):** some lib modules bake paths at import (`config.CONFIG_PATH`,
  `git_sync.CACHE_DIR`, `context.PM_OS_DIR`), so the fixture monkeypatches those constants.

### Fixtures

| Fixture | Purpose |
|---|---|
| `pmos` | The backbone. Builds a faithful PM-OS install in a temp `HOME` (copies `lib/`, `scripts/`, `hooks/`, `skills/`, `context.example/`, `VERSION`), writes a test `config.yaml`, creates temp Claude/Codex/projects dirs and a **local bare git feedback repo**, sets the isolation env, and repoints in-process lib constants. Exposes `.install/.projects/.claude/.codex/.feedback/.home/.env`. |
| `new_project` | Factory — scaffolds a scratch project via the real `pm_new.py` and returns its path. |
| `requires_feature(name)` | Skip-marker for planned-but-unbuilt capabilities, so reserved future-phase tests can be committed now and flip live when the feature ships (test-plan §18). |

### Helpers (`tests/helpers.py`)

- `run_script(pmos, "pm_x.py", *args, cwd=…, stdin=…)` — run a script from the temp install with the isolated env.
- `run_hook(pmos, "pre-stage.py", stage, cwd=…, extra_env=…)` — run a gate hook the way a skill does (`PM_OS_STAGE=NN`).
- `write_artifact(path, stage=…, project=…, status=…, body=…, **frontmatter)` — build a minimal stage artifact.

### Markers

`unit` · `integration` · `contract` · `connection` · `slow` · reserved phase markers
`phase3_enhancement` · `phase4_handoff` · `phase5_triage` · `phase6_release`.

## 4. Layout

```
tests/
├── conftest.py            # harness: fixtures + isolation
├── helpers.py             # run_script / run_hook / write_artifact
├── test_harness_smoke.py  # T0 — proves the harness itself works
├── unit/                  # T1 — in-process lib/ tests
│   ├── test_project.py     test_hashing.py     test_frontmatter.py
│   ├── test_config.py      test_telemetry.py   test_text_metrics.py
│   └── test_context.py     test_git_sync.py    test_html_render.py
├── integration/           # T2,T4,T5,T6,T7 — script + hook flows (subprocess, isolated)
│   ├── test_project_lifecycle.py      test_stage_gates.py     test_approval_and_staleness.py
│   ├── test_install_verify_update.py  test_context_import.py  test_feedback.py
│   ├── test_git_sync_local.py         test_telemetry_metrics.py
│   ├── test_failure_recovery.py       test_idempotency.py
│   └── test_offline_install.py
└── contracts/             # T3,T8,T9 — skill/doc/spec drift, local-first, CI
    ├── test_skill_contracts.py    test_documentation_drift.py
    └── test_local_first_boundaries.py    test_ci.py
```

---

## 5. Test catalog

Each suite below lists its **purpose**, **pass/fail criteria**, and **every test** with a
one-line description. The matching docstring in code carries the same intent for in-place review.

### T0 — Harness smoke (`tests/test_harness_smoke.py`)
**Purpose:** prove the apparatus builds an isolated install and runs in it before any real test relies on it.
**Pass:** a temp install is created under the pytest tmp tree and a scratch project is scaffolded there.
**Fail:** anything resolves to a real user path, or lib can't import from the working copy.

| Test | Checks |
|---|---|
| `test_temp_install_is_isolated` | The temp install lives under the pytest sandbox (not real `~/.pm-os`) and contains `lib/scripts/hooks/skills/context.example` + `config.yaml`. |
| `test_pm_new_scaffolds_only_in_temp` | `pm_new.py` creates `.meta.yaml`, business statement, telemetry, `.history/` **inside the temp projects dir** only. |
| `test_lib_imports_resolve_to_repo` | `project`/`telemetry`/`context` import from the working copy with expected symbols. |
| `test_context_module_repointed_to_temp_install` | The fixture repoints `context.PM_OS_DIR`/`CONTEXT_SEED_DIR` at the temp install (in-process isolation works). |

### T1 — Unit: `lib/` modules (`tests/unit/`)
**Purpose:** cover each shared helper's normal paths, branches, and edge cases in-process.
**Pass:** documented behavior holds for normal + edge inputs; invariants (body-only hash, chain integrity, no-op overlay) are upheld.
**Fail:** an invariant breaks, or a regression reappears in a guarded area.

**`test_project.py`** — stage/state helpers
- `test_stage_tables_consistent` — STAGE_ORDER/NAMES/CORE align; stage-00 group (`00`, `00c`, `00w`, `00u`) leads the order.
- `test_artifact_path_special_and_formula` — `00c`/`00w`/`00u` map to their fixed filenames; others follow `NN-name.md`.
- `test_get_stage_found_and_missing` — returns the stage dict; raises `KeyError` for unknown id.
- `test_upstream_linear_filtered_by_present_stages` — upstreams are prior present stages only.
- `test_stage_09_optional_dependency_on_08` — 09 gains 08 as upstream **only when 08 is approved**.
- `test_downstream_includes_dependents` — downstream = stages that depend on the given one.
- `test_resolve_backfill_verdicts` — faithful/lossy/infeasible classification; no-gap and empty cases.
- `test_migrate_meta_v1_to_v2` — adds `origin`, injects approved stage 00, sets `schema_version`; idempotent.
- `test_00c_in_stage_tables` — `00c` is in STAGE_NAMES, STAGE_ARTIFACTS, PRE_STAGES, STAGE_ORDER; positioned between `00` and `00w`.
- `test_migrate_v2_to_v3` — adds `project_type`, `codebase_path`, `codebase_ref` to existing meta; bumps to schema v3; idempotent.
- `test_resolve_project_walks_up` / `test_resolve_project_not_found` — finds nearest `.meta.yaml`; raises when none.

**`test_hashing.py`** — content addressing
- `test_body_hash_ignores_frontmatter` — **key invariant:** editing frontmatter does not change the body hash.
- `test_body_hash_changes_with_body` — editing the body does change it.
- `test_body_hash_crlf_normalized` — CRLF and LF inputs hash equal.
- `test_hash_event_excludes_event_hash_and_chains` — `event_hash` field is excluded; `prev_hash` changes the link.
- `test_hash_event_deterministic_and_unicode` — key order doesn't matter; unicode is stable.

**`test_frontmatter.py`** — frontmatter I/O
- `test_read_write_roundtrip` / `test_empty_frontmatter_roundtrip` — values survive a write→read cycle.
- `test_read_no_frontmatter_returns_empty_dict` / `test_bare_dashes_treated_as_no_frontmatter` — non-frontmatter docs return verbatim body.
- `test_read_crlf_normalized` — CRLF normalized on read.
- `test_update_status_flips_and_sets_kwargs` — flips status + extra fields, leaves body untouched.

**`test_config.py`** — config + model policy
- `test_load_config_reads_temp_install` — reads the isolated config; applies model-policy defaults.
- `test_model_tier_for_stage` — deep-reasoning stages (00w/00u/03/04/06/08/09) → `deep-reasoning`; others → `standard`.
- `test_model_tier_falls_back_without_config` — returns a sane tier even if config load fails.

**`test_telemetry.py`** — hash-chained log
- `test_log_appends_chained_events` — events append and link `prev_event_hash`→`event_hash`.
- `test_last_event_filters` — most-recent event by type/stage filter.
- `test_verify_chain_ok_and_tamper` — intact chain passes; a tampered line is caught with line number + reason.
- `test_verify_chain_no_file` — absent telemetry is `ok` with 0 events.

**`test_text_metrics.py`** — edit distance
- `test_char_edit_distance_known` — Levenshtein on known pairs + empties.
- `test_normalized_edit_distance_range` — 0.0 identical … 1.0 fully different.

**`test_context.py`** — context overlay (Codex regression guards)
- `test_unfilled_pack_is_noop_every_stage` — an unfilled/seed-identical pack renders nothing for all 9 stages.
- `test_lazy_bootstrap_seeds_on_first_read` — first read self-seeds `context/` when absent (self-update bootstrap).
- `test_seed_context_copies_missing_without_overwrite` — seeds missing files, preserves PM edits, copies new seed files.
- `test_malformed_manifest_fails_loud` — a YAML-broken manifest **raises** (never silent "no overlay").
- `test_filled_global_surfaces_and_strips_guidance` — real content surfaces with `apply` directive; guidance/empty-table scaffolding stripped.
- `test_apply_modes_emit_correct_directive` — `augment`/`override`/`reference-only` produce the right directive.
- `test_partial_project_override_layers_over_base` — partial project manifest layers over base (base files survive; project wins per field; examples union).

**`test_git_sync.py`** — sync skip/failure paths (stubbed, no network)
- `test_push_all_empty_dir_is_clean_noop` — empty/missing projects dir returns a clean `ok` no-op.
- `test_unconfigured_feedback_repo_skips` — no `feedback_repo` → `ok:false` with "not configured".
- `test_partial_staging_failure_flips_ok_false` — a project that can't be staged flips `ok:false` and lands in `failed`, while good ones still sync.
- `test_deleted_project_dir_is_skipped_not_failed` — a root without `.meta.yaml` is skipped, not counted as a failure.

**`test_html_render.py`** — companion rendering (escaping + parsing)
- `test_markdownish_escapes_untrusted_html` / `test_inline_escapes_and_formats` — untrusted Markdown is HTML-escaped (XSS guard); bold/code still render.
- `test_parse_sections_splits_on_h2` / `test_parse_sections_no_headings_defaults_overview` — sections split on `##`; no-heading body becomes one "Overview" section.

### T2 — Lifecycle integration (`tests/integration/`)
**Purpose:** exercise the real scripts + hooks end to end against the isolated temp install — the state machine as a PM drives it.
**Pass:** scaffolding, gating, approval, staleness, and HTML rendering behave per spec and keep meta↔frontmatter in sync.
**Fail:** a gate lets unsafe progression through (or blocks valid), state desyncs, or a side effect corrupts the project.

**`test_project_lifecycle.py`** — scaffold → approve → status → share
- `test_pm_new_creates_full_scaffold` — `pm_new` writes meta/statement/telemetry/feedback/.history, records genai flag, logs `project_created`.
- `test_approve_business_statement_logs_telemetry` — approving 00 syncs meta+frontmatter, records a hash, logs `stage_approved`.
- `test_pm_status_reports_state` — `pm_status` surfaces stage statuses, feedback count, recent telemetry.
- `test_pm_share_includes_approved_excludes_pending` — share exports approved bodies, omits pending stages.

**`test_stage_gates.py`** — the gate (`pre-stage.py`)
- `test_gate_blocks_when_upstream_unapproved` — stage 02 blocked while 01 is pending; blocker named.
- `test_gate_allows_first_stage_after_00_approved` — stage 01 gate passes once 00 is approved.
- `test_editing_approved_upstream_marks_edited` — body drift on an approved upstream → marked `edited` + `stage_edited_post_approval` logged.
- `test_non_tty_without_choice_routes_to_pm` — edited upstream + no `PM_OS_EDITED_UPSTREAM_CHOICE` blocks and routes the re-approval to the PM (`/pm-approve`), and does NOT advertise the env-var bypass (so an agent can't self-approve); never hangs.
- `test_enhancement_project_scaffolds` — `pm_new --mode enhancement` writes `project_type=enhancement`, `schema_version=3`, and `codebase_path` to meta.
- `test_brief_gates_on_00c_when_present` — when `00c` exists in meta as `draft`, stage-01 gate blocks; approving `00c` unblocks it.
- `test_implicit_reapproval_continue` — `…CHOICE=continue` re-approves the edited upstream and logs `implicit_reapproval`, then allows the run.

**`test_approval_and_staleness.py`** — `post-approve.py` side effects
- `test_approval_syncs_frontmatter_and_meta` — approval records identical hash/status in both sources of truth.
- `test_reapproving_upstream_cascades_downstream_stale` — re-approving 01 marks approved 02 stale + logs `stage_marked_stale`.
- `test_stage_04_approval_renders_html` — approving 04 renders `04-design-spec.html` with escaped content.
- `test_stage_05_approval_renders_prototype_html` — approving 05 renders `05-prototype-mockup.html`.

### T3 — Contracts (`tests/contracts/test_skill_contracts.py`, `test_documentation_drift.py`)
**Purpose:** skills/docs/spec can't silently drift from the code. **Pass:** structural facts hold (asserted from source-of-truth constants). **Fail:** a skill/doc diverges from the code.
- `test_skill_contracts`: every skill has frontmatter name/description **and a Codex `agents/openai.yaml` twin with well-formed interface metadata** (display name, short description, a `$skill` default prompt); no provider model ids in shared frontmatter; per-stage structure (dir/name/writes, gate command, `render_context` overlay load, model+`model_tier_for_stage` telemetry); deep-reasoning tier on the deep stages; both runtime entrypoints.
- `test_product_artifact_skills_enforce_current_contracts`: Stages 03–05 contain their required/recommended section templates, current artifact-contract marker, and strict validator invocation; the HTML skill uses the explicit interaction model and separates `?review=1` reviewer chrome.
- `test_documentation_drift`: stage-order shape; every pipeline stage has a skill; model-policy constant; spec documents every emitted event; ARCHITECTURE records the runtime paths.

### T4 — Install/verify/update parity (`tests/integration/test_install_verify_update.py`)
**Purpose:** the install lifecycle + runtime parity. **Pass:** install writes config & seeds context; verify passes on a healthy install and fails on tampering; update validates args and syncs per runtime.
- install: writes config + model policy; missing pm_user fails non-interactively; seeds the overlay.
- verify: passes on a complete install; fails on a missing hook / missing config.
- update: requires `--runtime`; rejects invalid runtime; **Claude gets skills+hooks, Codex skills only.**

### T5 — Context-import, feedback, local sync (`test_context_import.py`, `test_feedback.py`, `test_git_sync_local.py`)
**Purpose:** the intake path, feedback capture, and the real central-sync git path.
- context-import: register (preserve + `.sources.yaml` + `context_ingested`); preflight feasible/infeasible exit codes; commit (unknown stage / missing slot fail; generated wiki draft logs model+prompt_version; backfilled-approved records origin); imported Stage 03–05 artifacts preserve source content, approve with visible contract findings, and log `artifact_validation_warning`.
- feedback: rating/note → `feedback.jsonl` + `feedback_submitted`; skip flags; non-tty requires rating; unknown stage fails.
- `git_sync_local` *(connection)*: approval pushes to a **local bare** feedback repo (real git path); `pm_sync` backfills all projects; `--verify` reports chains intact.

### T6 — Telemetry metrics (`tests/integration/test_telemetry_metrics.py`)
**Purpose:** the computed approval metrics. **Pass:** metrics populate from real data and stay null where no generation snapshot exists.
- time-to-approve recorded when generated; edit distance 0 unchanged / >0 edited / null without snapshot; `--semantic-distance` passthrough + out-of-range rejection; model id + config-derived tier captured; regeneration count surfaced.
- artifact-contract warnings carry stable severity/code/message entries, contract version, and artifact origin.

### T7 — Negative/resilience + idempotency (`test_failure_recovery.py`, `test_idempotency.py`)
**Purpose:** broken/hostile state fails safely; safe ops repeat cleanly.
- malformed/missing `.meta.yaml`, not-in-project, no-frontmatter artifact, tampered telemetry, non-tty genai decision → clear failures.
- approve-already-approved no-op; `pm_status` stable; HTML render deterministic.

### T8 — Local-first & security (`tests/contracts/test_local_first_boundaries.py`)
**Purpose:** trust/privacy boundaries. **Pass:** read-only commands don't sync; provenance stays in-project; fixtures carry no secrets.
- `pm_status`/`pm_share` don't import `git_sync` or push; source registration stays inside `.history`; no secrets/hardcoded home in `tests/`.

### T9 — CI (`tests/contracts/test_ci.py` + `.github/workflows/tests.yml`)
**Purpose:** the suite runs automatically. The workflow runs `pytest -m "not slow"` on push/PR; a contract test guards it stays wired (and installs the runtime deps).

### T_offline — Offline install (`tests/integration/test_offline_install.py`)
**Purpose:** verify that `install.sh --source` works without git or network, that reinstall
preserves user data, and that `git archive` produces a clean distribution zip.
**Pass:** exit 0 with verifier PASS; context/config survive reinstall; zip omits dev files.
**Fail:** offline install breaks, user data is overwritten, or dev files ship in the zip.
**Requires:** `bash` (tests 1–2), `git` (test 3); skipped automatically when unavailable.

| Test | Checks |
|---|---|
| `test_offline_source_install_populates_and_autoverifies` | `--source` install populates `~/.pm-os`, syncs skills to `~/.agents/skills`, auto-runs verifier, exits 0 with PASS. |
| `test_offline_reinstall_preserves_user_data` | `context/` marker file and `config.yaml` sentinel key survive a second `--source` install (rsync/cp excludes work). |
| `test_package_excludes_dev_files` | `git archive HEAD` omits `CLAUDE.md`, `AGENTS.md`, `tests/`, `.github/` but includes `install.sh`, `lib/`, `skills/`. |

### Planned suites (not yet built)
Tracked in the implementation plan; this catalog grows as each lands.

| Phase | Suite | Will cover |
|---|---|---|
| T10 | `lib/consistency.py` + `/pm-check` | **Final phase, built after T9** — reusable live consistency checker (see "Reused as a live consistency check" below + test-plan §19). |

### Reused as a live consistency check (planned — final phase, T10)

The invariant-style suites here aren't just tests — once T0–T9 are done, their checks get lifted
into a single shared `lib/consistency.py` → `check_project(project_root)` so a PM can audit a
**live** project ("something feels wrong") with the exact logic the tests assert. The tests then
assert that shared function against healthy + corrupted fixtures, and it's surfaced to the PM via
`/pm-check`, a non-blocking advisory in the pre-stage gate, and a one-line verdict in `/pm-status`
— read-only (diagnose + point to the fix, never mutate). See the test-implementation plan §19.

The suites that **correlate** (encode at-rest invariants → feed the checker): `test_telemetry`,
`test_hashing`, `test_project`, `test_approval_and_staleness`, `test_stage_gates`. The rest are
behavior-only and stay as they are.

---

## 6. Conventions for adding tests

So this doc stays the single source of truth and any reviewer can read one test in isolation:

1. **Every test has a docstring** — one or two lines: what it checks and, when non-obvious, why
   it matters (the invariant/regression it guards).
2. **Every suite is cataloged here** — add a row when you add a test; add a suite section when you
   add a file. A test that isn't in this doc is incomplete.
3. **Assert from source-of-truth constants** — iterate `project.STAGE_ORDER`/`STAGE_NAMES`, the
   `context.yaml` `stages:` map, and a single event-types table; never re-type the stage list or
   runtime paths in a test (see test-plan §18).
4. **Mark correctly** — pick `unit`/`integration`/`contract`/`connection`; tag future-phase tests
   with their `phaseN_*` marker and gate with `requires_feature` so CI can exclude them until live.
5. **Stay isolated** — use the `pmos`/`new_project` fixtures; never reference a real user path.
