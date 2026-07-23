# PM-OS Testing

The single reference for the PM-OS test apparatus. Read this top-to-bottom to
understand the whole suite; jump to a suite section to understand one test you're
reviewing. Every test also carries a docstring saying what it checks and why — this
doc and those docstrings are kept in lockstep (see [Conventions](#conventions-for-adding-tests)).

The original implementation roadmap (which phases exist, exit criteria — now
fully shipped, T0–T10) lives in
[`docs/archive/pm-os-test-implementation-plan.md`](../archive/pm-os-test-implementation-plan.md).
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
│   ├── test_context.py     test_git_sync.py    test_html_render.py
│   ├── test_artifact_contracts.py     test_traceability.py
│   ├── test_jira_markup.py     # lib/jira_markup.py (offline Jira CSV export)
│   ├── test_consistency.py     # T10 — lib/consistency.py
├── integration/           # T2,T4,T5,T6,T7 — script + hook flows (subprocess, isolated)
│   ├── test_project_lifecycle.py      test_stage_gates.py     test_approval_and_staleness.py
│   ├── test_traceability_spine.py
│   ├── test_install_verify_update.py  test_context_import.py  test_feedback.py
│   ├── test_git_sync_local.py         test_telemetry_metrics.py
│   ├── test_artifact_contract_warnings.py
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
- `test_migrate_v3_to_v4_adds_context_pack` — adds optional `context_pack` (null) and bumps to schema v4; existing stages/hashes untouched; idempotent (flat wikis stay flat).
- `test_has_context_pack_and_is_composite_stage` — `has_context_pack`/`is_composite_stage` flip on only when a `00-context/manifest.yaml` exists, and only for 00w (dual-mode switch).
- `test_resolve_project_walks_up` / `test_resolve_project_not_found` — finds nearest `.meta.yaml`; raises when none.

**`test_hashing.py`** — content addressing
- `test_body_hash_ignores_frontmatter` — **key invariant:** editing frontmatter does not change the body hash.
- `test_body_hash_changes_with_body` — editing the body does change it.
- `test_body_hash_crlf_normalized` — CRLF and LF inputs hash equal.
- `test_hash_event_excludes_event_hash_and_chains` — `event_hash` field is excluded; `prev_hash` changes the link.
- `test_hash_event_deterministic_and_unicode` — key order doesn't matter; unicode is stable.
- `test_composite_hash_stable_and_member_order_fixed` — the adaptive-context-pack (00w) composite hash is reproducible and driven by the manifest's declared member order, not filesystem order.
- `test_composite_markdown_frontmatter_inert` — editing a markdown member's frontmatter is inert (members hashed body-only).
- `test_composite_yaml_cosmetic_reformat_inert` — reordering an id-keyed YAML list, reordering keys, and comments are inert (canonical YAML serialization).
- `test_composite_detects_member_body_change` / `test_composite_yaml_value_change_detected` — a semantic change to any member moves the composite hash.
- `test_composite_detects_stage_affinity_change` — editing the manifest's `stage_affinities` (downstream module routing) moves the composite hash, so a routing change after approval is drift; cosmetic reordering of the affinity map stays inert.
- `test_stage_content_hash_dispatch_dual_mode` — `stage_content_hash` returns the composite hash for a 00w with a manifest and the flat body hash once the manifest is gone (legacy fallback).
- `test_stage_content_hash_non_00w_always_body` — non-00w stages are body-hashed even when a pack exists.
- `test_manifest_safety_rejections` — `load_manifest_members` rejects missing manifest, path traversal, duplicates, self-listing, and members missing on disk.
- `test_validate_manifest_hashes_detects_stale` — recorded per-member hashes are validated against freshly computed ones; stale entries are reported.

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
- `test_log_stamps_runtime_version_distinct_from_pinned` — events carry both the project's pinned `pm_os_version` and the installed runtime's `pm_os_version_runtime`, so drift between them is visible.
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

**`test_jira_markup.py`** — Markdown → Jira wiki markup (`lib/jira_markup.py`), used by the offline CSV export
- `test_headings_emphasis_and_links` / `test_lists_preserve_nesting_depth` / `test_tables_mark_the_header_row_and_drop_the_separator` — the documented subset converts headings, `**bold**`→`*bold*`, `~~x~~`→`-x-`, links to `[text|url]`, bullets/ordered items with nesting depth, and tables to `||header||`/`|cell|`.
- `test_code_is_protected_from_every_other_rule` / `test_unterminated_fence_is_closed` — inline code (`{{…}}`) and fenced blocks (`{code:lang}`) keep their contents verbatim so Markdown syntax inside a code sample survives; a truncated fence is closed rather than swallowing the rest of the ticket.
- `test_quotes_rules_and_unknown_syntax_pass_through` — blockquotes/`----` convert, and unrecognized text is emitted unchanged (the safe failure mode for a ticket body).

**`test_artifact_contracts.py`** — Stage 03–06 artifact quality contracts (`lib/artifact_contracts.py`)
- `test_valid_prd_contract_has_no_errors` / `test_prd_without_journeys_is_an_error` — a PRD with `UJ-###` user journeys passes; one without fails strict mode with `USER_JOURNEY_MISSING`.
- `test_recommended_prd_sections_warn_without_blocking` — recommended sections warn instead of erroring; caller continues.
- `test_design_contract_checks_journey_mapping_and_interaction_model` — design spec must have Journey-to-flow traceability and a Product UX guardrails/interaction model declaration.
- `test_prototype_brief_requires_modes_validation_and_a_journey` — prototype brief must separate participant/reviewer modes and include a validation plan section.
- `test_retrieval_html_*` / `test_generative_html_*` — HTML validator flags generation patterns in retrieval-only participant UI, ignores reviewer-only subtrees, and allows them under a generative interaction model.
- **Phase 3.5 stable ids:** `test_valid_qa_plan_contract_has_no_errors` (TC-### scenarios tracing to PRD requirement ids pass); `test_qa_plan_without_tc_ids_is_an_error` (`TEST_CASE_IDS_MISSING`); `test_qa_plan_test_case_must_trace_to_a_requirement` (`TEST_CASE_TRACE_MISSING`); `test_qa_plan_per_test_case_trace_is_enforced` (each TC must cite a requirement id — an unlinked TC fails even when a traceability table carries ids; finding names the untraced scenario); `test_prd_functional_requirements_accept_req_only_ids` (a REQ-### only Functional Requirements section passes — the FR check accepts FR or REQ); `test_split_test_case_blocks_handles_ordered_list_items` (shared splitter parses `1. TC-001` ordered-list scenarios and bounds blocks at the next `##`); `test_qa_plan_uncovered_requirement_warns_not_errors` (`REQUIREMENT_COVERAGE_GAP` is a WARNING, never blocks); `test_requirement_and_test_case_id_extractors` (shared `requirement_ids`/`test_case_ids` return unique upper-cased ids, accept REQ/US/FR and TC).
- **Phase 3.5b TRD tasks:** `test_task_ids_and_split_task_blocks` (every `TSK-###` declared as heading/bullet/ordered-list is found, deduped, first-seen order); `test_task_block_does_not_absorb_trailing_section` (a bullet-declared final task ends at the next heading — the Work Breakdown's trailing sections are not swallowed); `test_task_implements_reads_only_the_implements_line` (`task_implements` trusts only the `Implements:` line — a requirement id mentioned in prose elsewhere in the block is not counted, so an orphan task returns `[]`); `test_task_id_declarations_keeps_duplicates` (`task_id_declarations` returns block-start ids including duplicates so `/pm-check` can flag a reused id, unlike `split_task_blocks` which collapses them); `test_work_breakdown_section_scopes_task_parsing` (`work_breakdown_section` returns only the text under `## Work Breakdown`, so a stray `TSK-###` under another heading is excluded from task parsing; `''` when the section is absent).
- **Contract v3 — design-spec screens (`SCR-###`):** `test_split_screen_blocks_and_serves` (every screen declared in the IA is found in first-seen order; `Serves:` reads requirement *and* journey ids from that line only, so a prose mention is not a trace); `test_information_architecture_section_scopes_screen_parsing` (a `SCR-###` under Key User Flows is a reference, not a declaration; `''` when the section is absent); `test_screen_id_declarations_keeps_duplicates` (declarations keep duplicates for `/pm-check`, unlike the collapsing splitter); `test_design_spec_without_screen_ids_warns_not_errors` (`SCREEN_IDS_MISSING` is WARNING-only so pre-v3 specs keep passing); `test_design_spec_screen_without_serves_warns` (`SCREEN_TRACE_MISSING` names the untraced screen); `test_fully_traced_screens_are_clean`.
- **Contract v3 — GenAI model availability/fallback (stages 03/08):** `test_genai_prd_model_rationale_without_availability_or_fallback_warns` (a GenAI PRD whose `Model Selection Rationale` names neither a deployment/availability path nor a fallback model gets `MODEL_SELECTION_INCOMPLETE` — WARNING, never blocking); `test_genai_prd_model_rationale_with_availability_and_fallback_is_clean` (naming the deployment path, region/quota and a named fallback with its switch trigger satisfies it); `test_non_genai_project_skips_the_model_selection_check` (`genai_flag: false` projects never see the check); `test_trd_model_serving_check_is_warning_only_and_version_exempt` (stage 08 is validated for `MODEL_SERVING_INCOMPLETE` only — it carries no required-section contract, so it is also exempt from `CONTRACT_VERSION_MISSING` and existing TRDs stay quiet); `test_missing_genai_sections_are_not_flagged` (an absent section is not a finding — the GenAI sections are appended conditionally).
- **IMP-007 fix — one TC extractor, not two:** `test_qa_plan_bold_wrapped_bullet_ids_are_declared` (a bold-wrapped bullet id `- **TC-001:** ...` is recognized by both `TEST_CASE_IDS_MISSING`'s check and the strict `split_test_case_blocks` splitter that feeds `traceability.build_index` — previously the loose validator regex accepted it while the strict splitter returned nothing, so a QA plan could pass validation while contributing nothing to `.traceability.yaml`); `test_split_test_case_blocks_stops_at_any_heading_level` (a non-TC `###` subsection interleaved between two test cases ends the preceding TC's block instead of being silently absorbed into it — previously the section-break regex only matched literal `##`); `test_split_test_case_blocks_preserves_nested_subheadings` (Codex PR #33 follow-up: a heading-style TC keeps its own nested `#### Coverage`/`#### Steps` detail — the level-aware splitter breaks only at a heading at or above the TC's own level, so requirement ids cited under a nested subsection are no longer dropped).

**`test_traceability.py`** — Phase 3.5 traceability spine (`lib/traceability.py`)
- `test_build_index_links_requirements_and_test_cases` — index extracts PRD requirement ids + QA TC-### ids and links each scenario to the requirement ids in its block.
- `test_build_index_parses_ordered_list_test_cases` — ordered-list scenarios (`1. TC-001 — covers FR-001`) are parsed, so a valid plan in that format is not reported all-uncovered.
- `test_last_tc_block_does_not_absorb_trailing_sections` — regression: the final TC block stops at the next `##` section, so a trailing Requirement-Test Traceability table / Acceptance Criteria section (naming every requirement id) is not swallowed into the last test case.
- `test_rebuild_writes_dotfile_at_project_root` — rebuild writes a flat `.traceability.yaml` sibling dotfile (not a hidden dir).
- `test_scenarios_for_requirement_both_directions` — resolver answers requirement→scenarios and scenario→requirements, case-insensitively.
- `test_uncovered_requirements_reports_gaps` — a requirement no scenario references is reported uncovered.
- `test_missing_artifacts_degrade_gracefully` — no PRD/QA → empty index, queries return empties (existing prose projects never break).
- `test_qa_referencing_undeclared_requirement_is_kept` — a QA-only requirement id is recorded (source=None), not dropped.
- `test_rebuild_preserves_reserved_external_refs` — reserved ticket/bug/code_ref slots survive a rebuild; derived links are re-derived.
- **Screens (schema v3):** `test_index_is_schema_v3_with_tasks_and_screens_maps` (the index declares v3 and always carries both maps); `test_build_index_links_screens_and_requirements` (screens from an approved design spec's IA are recorded with what they serve, and each requirement is back-linked; a `UJ-###` stays a forward link only — journeys are not requirement entries); `test_screen_resolver_both_directions` (`screens_for_requirement`/`requirements_for_screen` resolve both ways case-insensitively, and a journey id resolves through the fallback scan); `test_unapproved_design_spec_contributes_no_screens` (only an **approved** stage 04 contributes, so unapproved design decisions never reach the handoff); `test_screen_outside_information_architecture_is_not_indexed`; `test_rebuild_preserves_screen_design_refs` (the reserved `design_refs` slot survives a rebuild); `test_missing_design_spec_yields_empty_screens`.
- **Phase 3.5b TRD tasks (schema v2):** `test_index_is_schema_v2_with_tasks_map` (index declares `schema_version: 2` and always carries a `tasks` map); `test_build_index_links_tasks_and_requirements` (TRD `TSK-###` tasks recorded with what each implements, and each requirement back-linked to its implementing tasks); `test_task_resolver_both_directions` (`tasks_for_requirement`/`requirements_for_task` resolve both ways, case-insensitively); `test_task_implementing_undeclared_requirement_is_kept` (a task implementing a requirement the PRD didn't stably id keeps the reverse link, source=None); `test_rebuild_preserves_task_tickets_and_upgrades_v1` (a legacy v1 file upgrades to v2 on rebuild — schema bumps, an externally-set requirement ticket survives, and a Phase-4b task ticket is preserved across a later rebuild); `test_missing_trd_yields_empty_tasks` (no TRD → empty tasks map, task queries return empties — TRD is an optional capstone); `test_draft_or_stale_trd_tasks_excluded_from_index` (only an **approved** TRD's tasks are indexed — a draft/stale TRD contributes nothing, so re-approving an upstream stage that marks 08 stale drops its now-obsolete task links on rebuild); `test_task_outside_work_breakdown_is_not_indexed` (a `TSK-###` mentioned under a non-Work-Breakdown heading is not indexed as a delivery task).

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
- `test_reapprove_rejects_without_flag` — approving an already-approved stage without `--reapprove` is a no-op that points the PM at the flag.
- `test_reapprove_with_flag_reapproves_direct_edit` — `--reapprove` re-approves a stage the PM edited directly while still `approved` (no downstream gate needed first), cascades stale downstream, and logs `reapproved_from_approved: true`.
- `test_reapprove_noop_when_unchanged` — `--reapprove` on an approved stage with no body drift is a true no-op: no new telemetry, no downstream staleness.
- `test_stage_04_approval_renders_html` — approving 04 renders `04-design-spec.html` with escaped content.
- `test_stage_05_approval_renders_prototype_html` — approving 05 renders `05-prototype-mockup.html`.

**`test_traceability_spine.py`** — Phase 3.5 traceability spine end to end (`post-approve.py` + `pm_trace.py`)
- `test_approval_builds_traceability_dotfile` — approving 03 then 06 writes a flat `.traceability.yaml` at the project root linking PRD requirement ids to QA TC-### scenarios.
- `test_bold_wrapped_bullet_tc_ids_still_populate_the_spine` — IMP-007 end-to-end: a QA plan using bold-wrapped bullet TC ids passes stage-06 approval AND populates `.traceability.yaml` (previously approved silently with an empty spine).
- `test_resolver_answers_coverage_query` — `pm_trace.py requirement|scenario` resolves coverage in both directions, locally from approved artifacts.
- `test_rebuild_subcommand_regenerates_index` — `pm_trace.py rebuild` regenerates the derived dotfile on demand.

**`test_handoff.py`** — Phase 4b Jira handoff export (`scripts/pm_handoff.py`)
- `test_plan_blocks_when_prd_not_approved` — `plan` exits non-zero and writes nothing while the PRD is not approved (the export projects approved decisions only).
- `test_plan_maps_stories_requirements_and_tasks` — `plan` maps each `US-###`→epic, its `FR-###`→child story, each approved `TSK-###`→child task under the owning epic; unowned FR/TSK go to an Unassigned bucket; a `TSK-###` outside the Work Breakdown is excluded.
- `test_plan_without_trd_exports_prd_only` — with no approved TRD, `plan` still exports PRD stories + functional requirements and carries zero tasks (`source_stamps.trd` is null).
- `test_plan_excludes_tasks_when_trd_no_longer_approved` — Codex PR #36 P1 regression: when stage 08 is cascaded to stale (implicit re-approval of an edited PRD) *without* the derived `.traceability.yaml` being rebuilt, `plan` must not export the stale tasks — it rebuilds the index fresh and gates tasks on the live meta status.
- `test_record_writes_ticket_keys_and_logs_telemetry` — `record` writes created ticket keys into the matching requirement's/task's `tickets` slot, skips ids absent from the index, survives a later `pm_trace.py rebuild`, and logs a `handoff_exported` event carrying refs/counts/keys only.
- **Offline CSV route:** `test_export_csv_writes_importer_file_and_guide` (`export` writes `jira-import.csv` + the import guide with one row per exportable item, epics before their children, `Parent Id` pointing at the owning epic's `Issue Id`, unowned items parentless, the synthetic `UNASSIGNED` epic never emitted as a ticket, and the stable id carried as both a column and a `pm-os-<id>` label); `test_export_csv_descriptions_are_jira_markup_with_provenance` (descriptions are converted to wiki markup — no residual `**`/backticks — and carry a provenance footer naming the source artifact); `test_export_csv_blocks_when_prd_not_approved` (`export` reuses the plan builder's approval gate and writes nothing).

**`test_share_package.py`** — Phase 4a readable handoff package, `pm-share --package` (`scripts/pm_share.py`; merged from the former `scripts/pm_handoff.py` — the `pm-handoff` name is now reserved for a future external-tracker/design export, see `docs/plans/pm-os-modes-and-handoff-plan.md` Part B)
- `test_package_generates_per_story_files_with_traceability` — approving 01/02/03/06 then running `pm_share.py --package` assembles per-story files in the boss house-format by walking US-### → FR-### → UJ-### → covering TC-###; the story lists both covering test cases, carries the authored story body, and is stamped with source provenance + a "DO NOT EDIT HERE" banner.
- **Screens:** `test_package_maps_screens_to_each_story` (with an approved design spec, each story file lists the `SCR-###` screens it touches — resolved through the spine via its requirements *and* journeys — with the screen's own body and the design spec added to the story's provenance stamps); `test_package_screen_map_reference_lists_coverage_both_ways` (`reference/screen-map.md` is the reverse view: each screen with what it serves, plus a "Stories with no screen" section naming uncovered stories, linked from the README); `test_package_without_screen_ids_degrades_gracefully` (no approved design spec / no `SCR-###` ids → the not-captured marker and a screen map explaining what to add, never a crash or invention); `test_package_excludes_screens_from_an_unapproved_design_spec` (a stage 04 reopened as a draft contributes nothing to the story files or the screen map — unapproved design decisions must not ship as handoff material); `test_package_resolves_screens_from_a_stale_on_disk_index` (screens still resolve when `.traceability.yaml` predates the screens map, because the package builds the spine fresh rather than trusting the file). `test_screen_map_counts_journey_only_coverage_as_covered` (a story covered only through a journey link is not reported under "Stories with no screen" — the map derives coverage from the per-story resolution, not each screen's literal `serves` ids).
- `test_package_flags_unsourced_sections_instead_of_fabricating` — a story with no covering TC / no FR shows `— not captured in source —` rather than invented content (the blank doubles as a coverage checklist).
- `test_package_resolves_reverse_declared_fr_and_uj_links` — a story that never self-cites its own FR/UJ ids (only the FR/journey block names the story, the reverse direction) still resolves them and pulls in the TCs that trace only to that FR — regression test for backlog #12 (IMP-008) Bug B.
- `test_package_keeps_full_body_for_single_line_test_cases` — a single-line-bullet QA scenario (the whole TC on one line) still renders its full description instead of being stripped to empty — regression test for backlog #12 (IMP-008) Bug A.
- `test_package_overview_and_reference_docs` — `00-overview.md` carries Who/What&Why/How from the brief+scope; `reference/impact-analysis.md` and `nfrs.md` carry the PRD's Impact Analysis and NFR sections.
- `test_package_is_read_only_and_does_not_touch_state_machine` — generating the package leaves `.meta.yaml` and `03-prd.md` byte-identical (read-only projection, never gated/hashed).
- `test_package_requires_a_prd` — with no approved PRD the generator exits non-zero instead of emitting an empty package.
- `test_package_refuses_a_draft_prd` — a PRD that exists but is only `draft` is refused, so unreviewed product decisions can't be published as canonical handoff (Codex PR #31 finding).
- `test_package_refuses_an_edited_prd` — an `edited` PRD (body drifted after approval) is also refused: the changes are unreviewed and the traceability index is stale relative to the edited body, so re-approval is required before packaging (Codex PR #32 finding).
- `test_package_refuses_destructive_output_dir` — `--output .` (the project root/cwd) is rejected before any `rmtree`, so a stray target can never erase `.meta.yaml`/approved artifacts (Codex PR #30/#31 P1 finding).
- `test_package_refuses_existing_unmarked_dir` — an existing non-empty directory lacking the `.pm-os-handoff` marker is not deleted; only a prior package (which carries the marker) is regenerated in place.
- `test_raw_mode_unchanged_by_the_merge` — the pre-existing single-stage/all-approved raw text export is untouched by folding `--package` in alongside it, and raw mode never creates a `handoff/` package as a side effect.

The v2 PRD-contract enrichments that feed this package are covered in T1 (`test_split_user_story_blocks_bounds_by_declaration_and_section`, `test_user_story_without_acceptance_warns_not_errors`, `test_contract_version_1_is_still_supported`, `test_impact_analysis_is_a_recommended_prd_section`) — all WARNING-only, so existing `artifact_contract_version: 1` PRDs keep passing.

### T3 — Contracts (`tests/contracts/test_skill_contracts.py`, `test_documentation_drift.py`)
**Purpose:** skills/docs/spec can't silently drift from the code. **Pass:** structural facts hold (asserted from source-of-truth constants). **Fail:** a skill/doc diverges from the code.
- `test_skill_contracts`: every skill has frontmatter name/description **and a Codex `agents/openai.yaml` twin with well-formed interface metadata** (display name, short description, a `$skill` default prompt); no provider model ids in shared frontmatter; per-stage structure (dir/name/writes, gate command, `render_context` overlay load, model+`model_tier_for_stage` telemetry); deep-reasoning tier on the deep stages; both runtime entrypoints.
- `test_product_artifact_skills_enforce_current_contracts`: Stages 03–05 contain their required/recommended section templates, current artifact-contract marker, and strict validator invocation; the HTML skill uses the explicit interaction model and separates `?review=1` reviewer chrome.
- `test_context_import_skill_produces_modular_pack`: the context-import skill instructs writing the pack members (`evidence.yaml`, `sources.md`) and assembling the manifest (`pack-manifest`/`pack-validate`), does not re-impose the single-page wiki limitation, and advertises the pack files in its `writes:` frontmatter — guards the dormant-pack gap found in the dogfood.
- `test_documentation_drift`: stage-order shape; every pipeline stage has a skill; model-policy constant; spec documents every emitted event; ARCHITECTURE records the runtime paths.

### T4 — Install/verify/update parity (`tests/integration/test_install_verify_update.py`)
**Purpose:** the install lifecycle + runtime parity. **Pass:** install writes config & seeds context; verify passes on a healthy install and fails on tampering; update validates args and syncs per runtime.
- install: writes config + model policy; missing pm_user fails non-interactively; seeds the overlay.
- verify: passes on a complete install; fails on a missing hook, missing config key, missing `projects_dir` on disk, `git` not on PATH, missing templates, or a lib module that won't import.
- update: requires `--runtime`; rejects invalid runtime; **Claude gets skills+hooks, Codex skills only.**

### T5 — Context-import, feedback, local sync (`test_context_import.py`, `test_feedback.py`, `test_git_sync_local.py`)
**Purpose:** the intake path, feedback capture, and the real central-sync git path.
- context-import: register (preserve + `.sources.yaml` + `context_ingested`); preflight feasible/infeasible exit codes; commit (unknown stage / missing slot fail; generated wiki draft logs model+prompt_version; backfilled-approved records origin); imported Stage 03–05 artifacts preserve source content, approve with visible contract findings, and log `artifact_validation_warning`.
- adaptive context pack (v4): `register` ingests images/PPTX/XLSX with deterministic `modality` and lossy-by-default flags (`test_register_classifies_new_formats_with_modality`); `pack-manifest` builds a fixed-order manifest with per-member hashes and stamps `context_pack` into meta (`test_pack_manifest_builds_fixed_order_and_records_meta`); `pack-validate` detects a post-build member edit (`test_pack_validate_detects_post_build_edit`); committing/approving a 00w with a pack uses the composite hash, not the index body hash (`test_composite_00w_commit_and_approve_uses_composite_hash`); editing any pack member is drift through the real pre-stage gate (`test_editing_pack_member_is_drift_through_gate`); an unsafe manifest blocks approval (`test_invalid_pack_manifest_blocks_approval`); `upgrade-pack` snapshots the flat wiki, scaffolds `00-context/`, and drafts 00w without re-approving (`test_upgrade_pack_snapshots_flat_wiki_and_drafts`).
- feedback: rating/note → `feedback.jsonl` + `feedback_submitted`; skip flags; non-tty requires rating; unknown stage fails.
- `git_sync_local` *(connection)*: approval pushes to a **local bare** feedback repo (real git path, `PM_OS_SYNC_BLOCKING=1` inline mode the fixture defaults to); the deferred default backgrounds the push so approval returns immediately yet the detached push still lands centrally (`test_deferred_approval_sync_does_not_block`, backlog #6); two syncs racing on the single shared cache serialize via the mkdir cache lock so both projects' telemetry lands instead of colliding on clone/index-lock/non-fast-forward (`test_concurrent_syncs_serialize_via_cache_lock`, Codex PR #34 follow-up); `pm_sync` backfills all projects; `--verify` reports chains intact.

### T6 — Telemetry metrics (`tests/integration/test_telemetry_metrics.py`)
**Purpose:** the computed approval metrics. **Pass:** metrics populate from real data and stay null where no generation snapshot exists.
- time-to-approve recorded when generated; edit distance 0 unchanged / >0 edited / null without snapshot; `--semantic-distance` passthrough + out-of-range rejection; model id + config-derived tier captured; regeneration count surfaced.
- artifact-contract warnings carry stable severity/code/message entries, contract version, and artifact origin.

### T6b — Artifact contract warnings at PM entrypoints (`tests/integration/test_artifact_contract_warnings.py`)
**Purpose:** warning-only contract validation at every PM entrypoint — approval, import, status display, and the CLI validator. **Pass:** warnings surface and are recorded in telemetry; the workflow continues rather than blocking. **Fail:** warnings are silenced, block the workflow, or produce incorrect telemetry.
- `test_approval_warns_records_and_continues` — approving a Stage 03 artifact without `UJ-###` journeys prints findings, logs `artifact_validation_warning` (with `stage_approved` still recorded), exits 0.
- `test_import_approval_warns_and_continues` — `pm_context_import commit --kind imported` on an incomplete Stage 03 artifact warns, continues, records `origin: imported` in the warning payload.
- `test_status_surfaces_contract_warning_count` — `pm_status` shows a "contract warnings:" line for any Stage 03–05 artifact that carries `artifact_contract_version` and has findings.
- `test_validator_cli_strict_fails_and_warn_mode_succeeds` — `pm_validate_artifact.py 03 --mode strict` exits non-zero with `USER_JOURNEY_MISSING`; `--mode warn` exits 0 and prints findings.

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

### T10 — Consistency toolkit (`tests/unit/test_consistency.py` + `/pm-check`)
**Purpose:** a single read-only "is this project internally consistent right now?" check
(`lib/consistency.py` → `check_project`), reusing the invariant-style logic the T1/T2 suites
already assert on throwaway fixtures, so the runtime check and the test apparatus share one
implementation instead of drifting apart. Surfaced via the `/pm-check` skill (exit 1 on any
error), a non-blocking advisory in the pre-stage gate, and a one-line verdict in `/pm-status`
— never mutates state. See the test-implementation plan §19.
**Pass:** `check_project` returns `[]` for a healthy project and the exact expected issue code
for each corrupted-state fixture. **Fail:** an invariant misses real drift/corruption, or a
healthy project reports a false positive.

| Test | Checks |
|---|---|
| `test_missing_schema_version_is_an_error` | A `schema_version` that isn't an int is `SCHEMA_VERSION_MISSING`. |
| `test_stage_missing_required_field_is_an_error` | A stage entry missing `id`/`status`/`origin` is `STAGE_SHAPE_INVALID`. |
| `test_unknown_stage_id_is_an_error` | A stage id outside the STAGE_NAMES catalog is `STAGE_SHAPE_INVALID`. |
| `test_invalid_status_value_is_an_error` / `test_invalid_origin_value_is_an_error` | An out-of-enum `status`/`origin` is `STAGE_SHAPE_INVALID`. |
| `test_healthy_meta_has_no_shape_issues` | A fully valid meta produces zero shape issues. |
| `test_non_pending_stage_missing_artifact_is_an_error` | An approved/draft/edited/stale stage with no artifact file is `ARTIFACT_MISSING`. |
| `test_pending_stage_missing_artifact_is_not_an_error` | A `pending` stage with no file is not flagged. |
| `test_absent_context_and_sources_yaml_is_healthy` / `test_valid_context_and_sources_yaml_is_healthy` | Missing or well-formed `context/context.yaml`/`.sources.yaml` produce no issues. |
| `test_malformed_context_yaml_is_an_error` / `test_malformed_sources_yaml_is_an_error` | Broken YAML in either file is `CONTEXT_YAML_UNPARSEABLE`/`SOURCES_YAML_UNPARSEABLE`. |
| `test_healthy_project_returns_empty_list` | A fully consistent project (matching hashes, synced frontmatter, real files) returns `[]`. |
| `test_format_report_empty_is_healthy_message` / `test_format_report_groups_errors_and_warnings` | Report text is a healthy message when empty, and groups/labels errors vs. warnings otherwise. |
| `test_summary_line_variants` | The one-line verdict distinguishes healthy / warnings-only / has-errors. |
| `test_issue_as_dict_shape` | `Issue.as_dict()` carries exactly the 5 spec fields (`code`, `severity`, `stage`, `message`, `remediation`). |
| `test_trd_duplicate_task_id_is_error` | Two TRD tasks sharing a `TSK-###` id is `TRD_TASK_DUPLICATE` (ERROR — reused ids collide on ticket export). |
| `test_trd_task_gap_orphan_unknown_and_coverage_are_warnings` | A numbering gap (`TRD_TASK_ID_GAP`), an untraced task (`TRD_TASK_ORPHAN`), a task implementing an id absent from the PRD (`TRD_TASK_UNKNOWN_REQ`), and an uncovered PRD requirement (`TRD_REQ_NOT_IMPLEMENTED`) are all WARNINGs — a work-in-progress TRD still passes. |
| `test_trd_without_work_breakdown_warns_once` | A TRD with no `TSK-###` tasks yields exactly one `TRD_WORK_BREAKDOWN_MISSING` warning (pre-contract TRDs degrade gracefully). |
| `test_clean_trd_has_no_task_findings` | A TRD whose sequential tasks cover every PRD requirement produces zero TRD findings. |
| `test_design_spec_without_screen_ids_warns` | A design spec with no `SCR-###` ids yields exactly one `SCREEN_IDS_MISSING` warning (specs predating screen ids degrade gracefully). |
| `test_duplicate_screen_id_is_error` | Two screens sharing a `SCR-###` id is `SCREEN_DUPLICATE` (ERROR — reused ids collide in the handoff screen map). |
| `test_screen_gap_orphan_unknown_and_story_coverage_are_warnings` | A numbering gap (`SCREEN_ID_GAP`), a screen with no `Serves:` line (`SCREEN_ORPHAN`), a trace to an id absent from the PRD (`SCREEN_UNKNOWN_REQ`), and a user story no screen serves (`STORY_HAS_NO_SCREEN`) are all WARNINGs. |
| `test_fully_traced_screens_produce_no_screen_issues` / `test_screens_outside_information_architecture_are_ignored` | Sequential screens serving every story raise nothing; a `SCR-###` under another heading is a reference, not a declaration. |
| `test_trd_check_skipped_when_stage_pending` | No TRD findings while stage 08 is still `pending` (nothing generated yet). |
| `test_trd_task_outside_work_breakdown_does_not_count` | A `TSK-###` only under a non-Work-Breakdown heading is not a delivery task — the check reports `TRD_WORK_BREAKDOWN_MISSING` rather than counting it. |

The schema-shape tests call the private `_check_schema_and_stage_shape` helper directly rather
than the full `check_project` — `project.load_meta()` auto-migrates a missing/stale
`schema_version` in memory (and persists the fix) before `check_project` ever sees it, so that
invariant can't be exercised end-to-end through a disk fixture.

Also asserted (one `# T10:`-commented block apiece, reusing each test's own fixture rather than
duplicating it) in the suites that already encode these invariants at rest: `test_telemetry.py`
(`test_verify_chain_ok_and_tamper` — the shared checker flags the same tampered chain),
`test_hashing.py` (`test_stage_content_hash_dispatch_dual_mode` — a recorded hash matching the
current composite hash isn't flagged as drift), `test_project.py` (`test_migrate_meta_v1_to_v2`
— a freshly migrated, persisted meta has no shape issues), `test_approval_and_staleness.py`
(`test_approval_syncs_frontmatter_and_meta` — a freshly approved project has no sync-mismatch
issues), and `test_stage_gates.py` (`test_editing_approved_upstream_marks_edited` — once drift
flips a stage to `edited`, the checker stops flagging it as drifted, and no approved stage here
is flagged against it as an unready upstream).

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
