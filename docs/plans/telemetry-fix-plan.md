# Fix & complete PM-OS telemetry

> **Revalidation note (2026-06-17, after Phase 2 context-intake shipped).** Re-checked against the current codebase. **Still accurate and unaddressed:** central sync runs only from `post-approve` with no backfill and swallowed failures (Area 1); no `last_event` reader and no `lib/text_metrics.py` (Area 3); `scripts/pm_feedback.py` does not log `feedback_submitted` into the chain (Area 4); `pm_os_verify.py` has no telemetry self-test (Area 6). **Corrections forced by Phase 2:**
> - **Area 2 / Context #2 overstated.** `model_tier` is **not** a uniform `'standard'` constant across all 9 skills — it is already differentiated per stage (`'standard'` in 01/02/04/05/07/09, `'deep-reasoning'` in 03/06/08, matching `config.deep_reasoning_stages`). It is still a per-stage *baked literal* (not read from config), and the genuinely missing field is the **actual `model` id**. Scope Area 2 to adding `model`, not "fixing a useless constant."
> - **New events already exist.** Phase 2 added `context_ingested`, `stage_imported`, `stage_backfilled` (`scripts/pm_context_import.py`) and the gated stage-00 group (`00` / `00w` / `00u`). The `../reference/pm-os-spec.md` and `ARCHITECTURE.md` event lists were already updated for these, so Area 2's doc reconciliation there is partly done.
> - **Some metrics are correctly `None`.** The stage-00 group and any `imported` / `backfilled` stage have no `stage_generated` event and no `.history/*.generated.md` snapshot, so Area 3's `time_to_approve_seconds` and edit-distance fields legitimately stay `None` for them — expected, not breakage. Compute only when a generation snapshot exists.
> - **Model-capture gap extends to context-import.** The wiki / understanding docs and reverse-generated (`backfilled`) artifacts are model-produced but log no `model` / `model_tier`. Either extend Area 2 to `scripts/pm_context_import.py` + the `pm-context-import` skill, or explicitly scope it out.
> - **Backfill targets — re-verify at runtime.** As of this check: `bill-checker` / `image-generator` / `marketing-agent` are still stranded locally; `storyboard-demo` is synced. Phase-2 testing also left throwaway `phase2-*` entries in `~/.pm-os-feedback-cache` that should be pruned (and `push_all` should skip/ignore deleted projects gracefully).

## Context

The user reported telemetry "seems broken" and wants it to be a reliable basis for (a) diagnosing what went wrong if issues arise and (b) team performance tracking — capturing what the user did, what the system did, artifact quality, and time taken. Telemetry is meant to flow centrally to the approved `pm-os-feedback` repo across the team.

Investigation of the live system (4 local projects under `~/pm-projects/`, plus the central cache and the code) shows telemetry is **not dead** — `lib/telemetry.py` writes hash-chained events and the chains verify intact — but it is **unreliable and incomplete** in exactly the dimensions the user cares about:

1. **Central sync strands most projects.** `push_feedback_repo()` runs only from the `post-approve` hook (only on approval), with no backfill and failures swallowed by `try/except`. Only 2 of 4 local projects ever reached the central repo; `bill-checker` (21 events + real feedback) and others created pre-0.4 will never sync.
2. **No actual `model` id is recorded.** `stage_generated` emits `model_tier` only — already differentiated per stage (`'standard'` for 01/02/04/05/07/09, `'deep-reasoning'` for 03/06/08, matching `config.deep_reasoning_stages`), but as a per-stage *baked literal*, not read from config and not the model that actually ran. Older on-disk data used `"model": "<real-id>"`, so the real model id is missing entirely — defeating performance tracking. (The wiki/understanding/backfilled artifacts from `/pm-context-import` also record no model.)
3. **`feedback_submitted` never enters the telemetry stream** — `pm_feedback.py` only appends to a separate `feedback.jsonl`, decoupled from the chain, and rating is often null.
4. **Quality/timing metrics are stubbed `null`**: `time_to_approve_seconds`, `char_edit_distance`, `normalized_edit_distance`, `semantic_distance` — though the data to compute them already exists on disk.
5. **No read-back/validation**, and `pm_os_verify.py` never exercises telemetry or push, so breakage stays invisible.

Decisions confirmed with the user: fix all of the above; run a live end-to-end test during execution; compute `semantic_distance` via the **already-running agent** (Claude Code/Codex judges generated-vs-approved drift in the skill layer) rather than an embeddings API — no new dependency.

## Critical execution note (repo → runtime layering)

Per `CLAUDE.md`: edits in this working copy are **inert** until they reach `~/.pm-os`. All Python imports `lib` from `~/.pm-os/lib`; hooks run from `~/.pm-os/hooks`; skills run from `~/.claude/skills`. So after editing here, sync to `~/.pm-os` (copy files + re-sync skills) before any live test. Skills are dual-runtime: update **both** `SKILL.md` (Claude) and `agents/openai.yaml` (Codex) where the change is runtime-relevant.

## Changes

### Area 1 — Reliable central sync
- **`lib/git_sync.py`**: add `push_all(projects_dir)` that walks every dir containing `.meta.yaml`, copies `telemetry.jsonl` + `feedback.jsonl` into `telemetry/<pm>/<slug>/`, and does a single commit + push. Refactor the existing per-project copy into a shared helper. Make failures **loud**: catch `git` errors, print an explicit `FAILED — <reason>` line with remediation (auth/network), and return a status instead of silently raising into a swallowed `try/except`.
- **New `scripts/pm_sync.py`** (CLI) + **new skill `pm-sync`** (`skills/pm-sync/SKILL.md` + `agents/openai.yaml`): manual catch-up sync of all projects, callable as `/pm-sync` (Claude) / `$pm-sync` (Codex). Supports `--verify` to validate every project's hash chain and report breaks.
- **`hooks/post-approve.py`**: keep the per-project push but replace the silent warning with a clear success/failure line.
- **Backfill**: run `pm_sync.py` once during execution to push the still-stranded projects — as of 2026-06-17 `bill-checker`, `image-generator`, `marketing-agent` (re-verify the set at runtime; `storyboard-demo` is already synced). Also **prune** the throwaway `phase2-*` telemetry dirs left in `~/.pm-os-feedback-cache` by Phase-2 testing, and make `push_all` skip projects whose local dir was deleted.

### Area 2 — Capture actual model id (model_tier is already differentiated)
- Pattern change across all 9 stage skills (`skills/pm-stage-0{1..9}-*/SKILL.md`, and `agents/openai.yaml` where the telemetry bash is mirrored). The `stage_generated` payload already carries `model_tier` differentiated per stage (`'standard'` for 01/02/04/05/07/09, `'deep-reasoning'` for 03/06/08); add the missing real model id:
  - `model`: the **actual model id** the agent is running as (agent fills this in — it knows its own id), matching the historical field name.
  - `model_tier`: keep the per-stage value, but **derive it from `config.deep_reasoning_stages`** rather than baking the literal into each skill, so config and telemetry can't drift apart.
- **Extend to the context-intake generation path** (or explicitly scope out): `scripts/pm_context_import.py` `stage_backfilled` plus the wiki/understanding commits in the `pm-context-import` skill are model-produced and should carry `model` too.
- `../reference/pm-os-spec.md` and `ARCHITECTURE.md` event lists were already updated for the Phase-2 events; still need to document `model` + `model_tier` on `stage_generated` and reconcile the historical `model` field. (Global rule: grep all 9 skills first, change in one pass, summarize.)

### Area 3 — Timing & quality metrics (mechanical, in Python)
- **New `lib/text_metrics.py`** (pure stdlib, no deps): `char_edit_distance(a, b)` (Levenshtein) and `normalized_edit_distance(a, b)`.
- **`lib/telemetry.py`**: add a small reader `last_event(project_root, event_type, stage)` to find the most recent matching event.
- **`scripts/pm_approve.py`**: replace the `None` stubs:
  - `time_to_approve_seconds` = approval timestamp − the matching `stage_generated` timestamp (via `last_event`).
  - `char_edit_distance` / `normalized_edit_distance` = diff the retained generated snapshot in `.history/<stage>.*.generated.md` (most recent for the stage) against the approved body. If no snapshot, leave `None`.
- **Generation time**: derived at read time in the metrics/aggregation tool from each `stage_started`→`stage_generated` pair (both timestamps already exist) — no skill change needed, works retroactively.
- **Stage-00 group and imported/backfilled stages have no generation event/snapshot**, so leave `time_to_approve_seconds` and the edit-distance fields `None` for them — that is correct, not a gap. Only compute when a `stage_generated` event and a `.history/<stage>.*.generated.md` snapshot both exist.

### Area 4 — Feedback + missing events
- **`scripts/pm_feedback.py`**: after writing `feedback.jsonl`, also `telemetry.log("feedback_submitted", root, stage_id, {scope, rating, tags, free_text})` so feedback joins the hash-chained stream, and trigger a sync so feedback reaches central without needing a later approval.
- **`stage_edited_via_note`**: add the inline telemetry emit (same bash pattern as `stage_started`) to the steering-note reconciliation path in skills that support it (stages 02–09), so the event the skills already *instruct* actually fires.
- **`session_end`**: deferred unless trivial — there is no session boundary in the skill model and no session hook exists. Noted as a follow-up rather than forced in.

### Area 5 — Agent-computed semantic distance (no embeddings)
- **`scripts/pm_approve.py`**: accept optional `--semantic-distance <0..1>`; put it in the `stage_approved` payload (defaults to `None` when absent).
- **`skills/pm-approve/SKILL.md`** (+ `agents/openai.yaml`): when edit-distance indicates drift, instruct the agent to read the `.history` generated snapshot and the approved body and emit a `0..1` semantic-distance estimate, passed via `--semantic-distance`. Clearly labeled as an agent judgment (subjective, non-deterministic). Degrades to `None` when not supplied.

### Area 6 — Make breakage visible
- **`scripts/pm_os_verify.py`**: add a telemetry self-test — log an event into a throwaway project, assert it appended and the hash chain validates; assert `push_all` reports a clear status (skipping actual network push). Optionally add a lightweight `pm_metrics.py` / `/pm-metrics` summarizer (per-stage timings, edit distances, ratings) so telemetry is actually readable for diagnosis.

## Files to modify (summary)
- `lib/git_sync.py` (add `push_all`, loud failures), `lib/telemetry.py` (add `last_event`), **new** `lib/text_metrics.py`
- `scripts/pm_approve.py` (real metrics + `--semantic-distance`), `scripts/pm_feedback.py` (`feedback_submitted` + sync), `scripts/pm_os_verify.py` (telemetry self-test), **new** `scripts/pm_sync.py`
- `hooks/post-approve.py` (clear push status)
- All 9 `skills/pm-stage-0*-*/SKILL.md` (add `model` id, derive `model_tier` from config; `stage_edited_via_note`), `skills/pm-approve/SKILL.md`, **new** `skills/pm-sync/` — plus matching `agents/openai.yaml` for each
- `scripts/pm_context_import.py` + `skills/pm-context-import/SKILL.md` — add `model` to `stage_backfilled` and the wiki/understanding commits (Area 2 extension), or scope out
- Docs: `../reference/pm-os-spec.md`, `ARCHITECTURE.md` — event lists already carry the Phase-2 events (`context_ingested` / `stage_imported` / `stage_backfilled`); still add `model` + `model_tier` to the `stage_generated` payload doc

## Verification

1. **Sync changes to `~/.pm-os`** first (copy `lib/`, `scripts/`, `hooks/`, then re-sync skills to `~/.claude/skills`), since the working copy is inert until then.
2. Run `python3 ~/.pm-os/scripts/pm_os_verify.py --runtime claude` — must pass, including the new telemetry self-test.
3. **Live end-to-end test** on a throwaway project under `~/pm-projects/` (note: the project is now `schema_version: 2` and the business statement is gated stage `00`, so approve it first): `/pm-new telemetry-test "..."` → `/pm-approve 00` → `/pm-stage-01-brief` → `/pm-approve 01` → `/pm-feedback 01`. Then inspect its `telemetry.jsonl` and assert:
   - `stage_generated` carries a real `model` id and correct `model_tier`.
   - `stage_approved` has non-null `time_to_approve_seconds` and edit-distance fields.
   - a `feedback_submitted` event exists with the rating.
   - hash chain still validates (including any Phase-2 `context_ingested` / `stage_imported` / `stage_backfilled` events if context-import was exercised).
4. Run `/pm-sync` (or `pm_sync.py`) and confirm the previously stranded projects (`bill-checker`, `image-generator`, `marketing-agent`) now appear under `~/.pm-os-feedback-cache/telemetry/karan/` and the commit pushes (or fails *loudly* with a clear reason).
5. Delete the throwaway test project afterward.
