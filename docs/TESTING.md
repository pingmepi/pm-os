# PM-OS Testing

The single reference for the PM-OS test apparatus. Read this top-to-bottom to
understand the whole suite; jump to a suite section to understand one test you're
reviewing. Every test also carries a docstring saying what it checks and why — this
doc and those docstrings are kept in lockstep (see [Conventions](#conventions-for-adding-tests)).

The implementation roadmap (which phases exist, exit criteria) lives in
[`docs/plans/pm-os-test-implementation-plan.md`](plans/pm-os-test-implementation-plan.md).
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

Dependencies (local/CI): `pytest`, plus the runtime deps `pyyaml`, `jinja2`, `gitpython`.
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
└── unit/                  # T1 — in-process lib/ tests
    ├── test_project.py     test_hashing.py     test_frontmatter.py
    ├── test_config.py      test_telemetry.py   test_text_metrics.py
    ├── test_context.py     test_git_sync.py    test_html_render.py
# (added as phases land:)
# ├── integration/         # T2,T4,T5,T7 — script+hook flows
# └── contracts/           # T3,T8 — skill/doc/spec drift
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
- `test_stage_tables_consistent` — STAGE_ORDER/NAMES/CORE align; stage-00 group leads the order.
- `test_artifact_path_special_and_formula` — `00w`/`00u` map to their fixed filenames; others follow `NN-name.md`.
- `test_get_stage_found_and_missing` — returns the stage dict; raises `KeyError` for unknown id.
- `test_upstream_linear_filtered_by_present_stages` — upstreams are prior present stages only.
- `test_stage_09_optional_dependency_on_08` — 09 gains 08 as upstream **only when 08 is approved**.
- `test_downstream_includes_dependents` — downstream = stages that depend on the given one.
- `test_resolve_backfill_verdicts` — faithful/lossy/infeasible classification; no-gap and empty cases.
- `test_migrate_meta_v1_to_v2` — adds `origin`, injects approved stage 00, sets `schema_version`; idempotent.
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
- `test_model_tier_for_stage` — 03/06/08 → `deep-reasoning`; others → `standard`.
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

### Planned suites (not yet built)
Tracked in the implementation plan; this catalog grows as each lands.

| Phase | Suite | Will cover |
|---|---|---|
| T2 | `integration/` lifecycle | pm_new→approve→gate→edited→stale→status→share; 04/05 HTML render; frontmatter↔meta sync |
| T3 | `contracts/` | skill frontmatter/gate/write-output contracts; stage section contracts; doc/spec drift |
| T4 | `integration/` runtime parity | install/update/verify for Claude+Codex; context seeding on install/update; verify checks |
| T5 | `integration/` | context-import (register/preflight/commit), **context-overlay skill integration** (§7A), feedback, telemetry, local bare-repo sync |
| T6 | `integration/` metrics | timing, edit-distance, model capture, regeneration, feedback, drift, sync-verify |
| T7 | `integration/` recovery | malformed/missing state, idempotency, non-tty escapes, schema migration |
| T8 | `contracts/` | local-first/network isolation, secret-free fixtures, documentation drift |
| T9 | CI | GitHub Actions running the default suite |

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
