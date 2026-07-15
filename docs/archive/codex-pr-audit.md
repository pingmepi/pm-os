# Codex PR Review Audit

Audit of all inline review comments left by `chatgpt-codex-connector[bot]` across the 14 PRs it reviewed (#5, #8, #9, #10, #11, #12, #14, #15, #18, #19, #20, #22, #24, #25). Each comment was cross-checked against the `main` branch codebase as of 2026-06-22.

**Result: 11 open · 10 resolved.**

> **Re-verified 2026-07-15, moved to `docs/archive/`.** Of the 11 originally-open items, **7 are now fixed** (#1 pre-stage.py re-checks blocking after cascade; #2 00c is in the approval handoff; #3 prepare-codebase validates the existing checkout's remote; #4/#5 pm-new/pm-feedback give non-interactive flag guidance; #6 install.sh fast-forwards via `merge --ff-only`; #7 the --note path leaves the edited upstream's hash unchanged so drift is caught downstream). **4 are still open** and have been migrated to `docs/roadmap/backlog.md` entries 14–17 (#8 advisory-only deep-reasoning gate, #9 `migrate_meta()` not backfilling missing stages, #10 backfilled-origin lost on approval telemetry, #11 `test_telemetry.py` not using the `pmos` isolation fixture) — track them there, not here. Retained for provenance/audit-trail only.

---

## Open Issues

### P0 — Fix immediately

#### #1 · PR #12 · `hooks/pre-stage.py`
**Gate exits 0 after cascading stale to intermediate stages**

When the PM chooses "continue" (implicit re-approval, choice `"1"`), `cascade_stale_for_edited()` marks intermediate approved stages (e.g. 02-scope, 03-prd) as `stale`, then `sys.exit(0)` is called — allowing the current stage to proceed with those stale intermediates. The blocking check only runs once, before the cascade.

**Issues caused:** Stage N is generated from unapproved intermediate artifacts. This is the most fundamental invariant of the pipeline and is violated silently.

**Suggested fix:** After the cascade, re-run the blocking check. If any upstream of `stage_id` is now stale, exit 1 and instruct the PM to re-approve the affected intermediates before retrying.

```python
# hooks/pre-stage.py — after cascade_stale_for_edited():
if stale_logged:
    stale_upstream = [s for s in stale_logged if s in upstream_ids]
    if stale_upstream:
        print(
            f"[pre-stage] BLOCKED: implicit re-approval staled intermediate stages "
            f"that are upstream of {stage_id}: {', '.join(stale_upstream)}.\n"
            "Re-approve them first, then retry this stage.",
            file=sys.stderr,
        )
        sys.exit(1)
```

---

### P1 — Fix in next release

#### #2 · PR #25 · `skills/pm-context-import/SKILL.md`
**00c omitted from approval handoff in enhancement imports**

The skill's approval handoff (around the "Tell the PM to approve" section) instructs the PM to `/pm-approve 00w` then `/pm-approve 00u` but omits `00c` (codebase-understanding). `lib/project.py` places `00c` in `PRE_STAGES` and it gates stage 01, so the pre-stage gate blocks until `00c` is approved.

**Issues caused:** Every codebase-backed import is stuck after the PM approves 00w + 00u with no clear path forward.

**Suggested fix:** Add `/pm-approve 00c` to the approval handoff step in `SKILL.md`, ordered before `00w` and `00u` (matching `STAGE_ORDER`).

---

#### #3 · PR #25 · `scripts/pm_context_import.py`
**`prepare-codebase` skips URL validation when `.codebase/` already exists**

In `cmd_prepare_codebase()`: if `.codebase/` exists, cloning and remote validation are skipped entirely. The existing checkout's HEAD is then recorded as `codebase_ref` regardless of what URL was requested.

**Issues caused:** Retrying with a corrected or different URL silently uses the old checkout; 00c and all enhancement artifacts describe the wrong product.

**Suggested fix:**
```python
# scripts/pm_context_import.py — cmd_prepare_codebase()
if target.exists():
    # Validate that the existing checkout matches the requested URL.
    remote_r = subprocess.run(
        ["git", "-C", str(target), "remote", "get-url", "origin"],
        capture_output=True, text=True,
    )
    existing_url = remote_r.stdout.strip()
    if remote_r.returncode != 0 or existing_url != raw:
        print(
            f"Warning: .codebase/ exists but its remote ({existing_url!r}) "
            f"differs from requested URL ({raw!r}).\n"
            "Remove .codebase/ manually to re-clone, or pass the same URL to reuse."
        )
        sys.exit(1)
```

---

#### #4 · PR #8 · `scripts/pm_new.py` + `skills/pm-new/SKILL.md`
**pm-new fails in agent sessions — no genai flag guidance**

`pm_new.py` exits in non-interactive mode if `--genai`/`--no-genai`/`PM_OS_GENAI_FLAG` is not supplied. `skills/pm-new/SKILL.md` passes only `"$@"` and gives no instruction to include a genai flag.

**Issues caused:** Agent-session `/pm-new` always fails before scaffolding. PMs must know to pass `--genai` explicitly, which is not documented in the skill.

**Suggested fix:** Update `skills/pm-new/SKILL.md` to instruct the agent to resolve the GenAI flag from the PM's intent and pass it explicitly:

```markdown
Before running pm_new, determine the genai flag:
- If the PM's statement or context makes clear this is an AI/agentic product, use `--genai`.
- If clearly non-AI, use `--no-genai`.
- If uncertain, ask the PM: "Is this a GenAI/agentic product? (yes/no)"

Run: python3 ~/.pm-os/scripts/pm_new.py "$SLUG" "$STATEMENT" --genai   # or --no-genai
```

---

#### #5 · PR #8 · `scripts/pm_feedback.py` + `skills/pm-feedback/SKILL.md`
**pm-feedback fails in agent sessions — no rating/note flag guidance**

`pm_feedback.py` exits in non-interactive mode without `--rating`/`--skip-rating` and `--note`/`--skip-note`. `skills/pm-feedback/SKILL.md` passes only `"$@"`.

**Issues caused:** Agent-session `/pm-feedback <NN>` always fails; feedback is never captured from agent sessions.

**Suggested fix:** Update `skills/pm-feedback/SKILL.md` to prompt the PM for rating + note before calling the script, then pass them as flags:

```markdown
Ask the PM:
1. "Rate this stage 1–5 (or skip)." → pass `--rating <N>` or `--skip-rating`
2. "Any notes on quality or gaps?" → pass `--note "..."` or `--skip-note`

Run: python3 ~/.pm-os/scripts/pm_feedback.py "$STAGE" --rating $R --note "..."
```

---

#### #6 · PR #14 · `install.sh`
**Existing installs not fast-forwarded after `git fetch`**

Lines 160–161: `git fetch origin main` followed by `git checkout main` only switches to the local `main` branch; it does not merge or reset to `origin/main`. The local checkout stays at the old commit.

**Issues caused:** Running the installer on an existing machine silently leaves stale code; skills/hooks are re-synced from the old checkout.

**Suggested fix:**
```bash
# install.sh — replace:
git -C "$INSTALL_DIR" fetch --tags origin main --quiet
git -C "$INSTALL_DIR" checkout main --quiet

# with:
git -C "$INSTALL_DIR" fetch --tags origin main --quiet
git -C "$INSTALL_DIR" checkout main --quiet
git -C "$INSTALL_DIR" merge --ff-only origin/main --quiet \
  || { echo "ERROR: could not fast-forward ~/.pm-os to origin/main. Run with --reset-main or resolve manually."; exit 1; }
```

---

### P2 — Fix soon

#### #7 · PR #5 · `skills/pm-stage-03-prd/SKILL.md`
**--note reconciliation edits upstream after the gate has already passed**

The --note path edits `01-brief.md` during stage-03 generation (after the pre-stage gate ran when 01 was still "approved"). 02-scope — approved against old 01 — is never marked stale during that cycle. This is the source scenario for the P0 bug (#1 above); the two issues compound.

**Issues caused:** 02-scope remains "approved" based on old 01 when 03 is generated from changed 01. The inconsistency is only caught later, at the pre-stage gate for stage 04+.

**Suggested fix:** After reconciling a note into an upstream artifact, the skill should explicitly call `pm_approve` for the edited upstream with `--reimport` semantics, or at minimum instruct the agent to warn the PM that 01 was edited and that 02 may need re-approval before proceeding.

---

#### #8 · PR #9 · `skills/pm-stage-03-prd/SKILL.md`, `06`, `08`
**Deep-reasoning gate is advisory, not a hard halt**

The model-tier check prints a warning and lets the PM override by re-running. It does not block generation on a lightweight model. Same wording is in stages 06 (QA plan) and 08 (TRD).

**Issues caused:** A PM can generate a binding PRD/QA/TRD on a lightweight model with one re-run; the model-tier quality gate is bypassed.

**Suggested fix:** Change the override path to require explicit PM confirmation in the same invocation (e.g. a `--confirm-lightweight-model` flag or an env var), rather than a silent re-run, so the bypass is intentional and auditable.

---

#### #9 · PR #14 · `lib/project.py`
**`migrate_meta()` doesn't backfill stages 01–09 for pre-v0.4 projects**

`migrate_meta()` handles schema v1→v2 and v2→v3 fields but never inserts missing pipeline stages. An old project that predates `pm_new.py`'s current scaffolding will hit `KeyError` in `pm_approve.py:97` when trying to approve stage 09.

**Issues caused:** Pre-v0.4 projects fail with `KeyError: 'Stage 09 not found in meta'` on the roadmap capstone. Low impact now (all new projects scaffold all stages), but upgrade correctness is broken for old installs.

**Suggested fix:** Add a migration pass in `migrate_meta()` that inserts any missing `STAGE_ORDER` stage with `status: pending` and default fields, guarded by a schema-version bump to v4.

---

#### #10 · PR #24 · `scripts/pm_context_import.py` + `scripts/pm_approve.py`
**Backfill provenance not preserved through draft → approved flow**

`stage_backfilled_draft` is logged correctly in `cmd_commit()`. But when the PM later calls `/pm-approve`, `pm_approve.py` emits a generic `stage_approved` event with no `backfilled` origin or `derived_from` reference.

**Issues caused:** Approved backfill artifacts are indistinguishable from generated ones in telemetry; provenance analytics can't trace which supplied artifact produced an approved backfill.

**Suggested fix:** `pm_approve.py` should check the stage's `origin` field in `.meta.yaml` and, when `origin == "backfilled"`, log a `stage_backfilled` event (or augment `stage_approved` with `{"origin": "backfilled", "derived_from": ...}`) instead of the plain approval event.

---

### P3 — Low priority

#### #11 · PR #20 · `tests/unit/test_telemetry.py`
**Telemetry unit tests read the real `~/.pm-os/config.yaml`**

Tests call `telemetry.log()` without the `pmos` fixture. `telemetry.log()` calls `load_config()` which reads the real install's `config.yaml`. No HOME or PM_OS_DIR monkeypatching.

**Issues caused:** Tests embed the developer's real `pm_user` in test telemetry. Tests fail on CI machines with no PM-OS install.

**Suggested fix:** Add the `pmos` fixture to each test class in `test_telemetry.py`, or add a lightweight `autouse` fixture in the unit test module that monkeypatches `telemetry.load_config` to return a minimal stub config.

---

## Resolved Issues

| # | PR | File | Resolution |
|---|----|----|-----------|
| R1 | #9 | `scripts/pm_new.py` | `projects_dir` now read from config (no longer hardcoded to `~/pm-projects`). |
| R2 | #10/#11 | `scripts/pm_os_verify.py` | `check_skills()` in `all` mode filters to installed runtime dirs; absent dirs are skipped, not failed. |
| R3 | #15 | `skills/pm-context-import/SKILL.md` | Heredoc uses `<<'PY'` but Python uses `Path.home()` — no shell-expansion issue. |
| R4 | #15 | All stage `SKILL.md` files | All 9 stage skills read `00-context-wiki.md` as grounding context when present. |
| R5 | #18 | `lib/git_sync.py` | `push_all` accumulates failures; `_result()` returns `ok: False` when any project fails to stage. |
| R6 | #18 | `scripts/pm_context_import.py` | `stage_generated`/`stage_backfilled_draft` events now include `prompt_version` and `notes`. |
| R7 | #19 | `lib/context.py` | YAML parse errors in `_load_manifest()` raise `ValueError` with a clear message instead of returning `{}`. |
| R8 | #19 | `lib/context.py` | Overlay merge uses `_union()` for lists and per-field merge for stages — no longer shallow-replaces. |
| R9 | #19 | `lib/context.py` | `resolve_context()` self-heals: seeds `context/` from `context.example/` on first read if absent. |
| R10 | #22 | `skills/pm-update-roadmap-tracking/` | Helper moved to `scripts/` and invoked via stable `~/.pm-os/scripts/` path (commit `0c8371c`). |
