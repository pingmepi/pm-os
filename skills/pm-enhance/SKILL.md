---
name: pm-enhance
description: Start and manage a read-only affected-slice enhancement inside an existing PM-OS product project while preserving baseline lineage and normal stage gates.
reads: [".meta.yaml", "00-*.md", "01-*.md", "02-*.md", "03-*.md", "04-*.md", "05-*.md", "06-*.md", "07-*.md", "08-*.md", "09-*.md", ".enhancements/**", "<codebase_path>/**"]
writes: [".enhancements/**", "00-codebase-understanding.md", "00-context-understanding.md", ".meta.yaml", "telemetry.jsonl"]
prompt_version: 0.2.0
---

# Start or continue an enhancement in the same project

Use this skill for a new enhancement to a product that already has a PM-OS project, or immediately after first-intake scaffolding for an external product. Every later enhancement stays in the **same project**. Never create a child project, sibling enhancement project, program-level gate, or parallel approval state machine.

`project_type` and `entry_route` record how the product first entered PM-OS. Do not change them to start enhancement work. `/pm-promote` is unrelated: it changes a requirement's Part-B release tier and is never an enhancement entrypoint.

## Hard safety boundary

The target product codebase is **read-only**. You may read files and use read-only Git inspection. Do not edit files, switch refs, alter the index/worktree, install dependencies, run formatters/generators/builds, create caches/output, or write documentation into the target. All `.enhancements/`, scan, interview, stage, and handoff output belongs in the PM-OS project.

Do not self-approve any stage. Existing stage approval, hashing, history, staleness, and telemetry remain authoritative.

## 1. Start the cycle

Run from inside the existing PM-OS project:

```bash
python3 ~/.pm-os/scripts/pm_enhance.py start --ask-file <pm-authored-ask.md> [--codebase <prepared-codebase-dir>] [--ref <git-ref>] [--subpath <monorepo-subpath>]
```

This captures approved canonical artifacts into an immutable cycle baseline and creates `.enhancements/EH-NNN/context.yaml`. It refuses a second active cycle and never changes `project_type`.

`start` consumes an **already-prepared local codebase** — it never clones or extracts. Preparation is `/pm-context-import`'s job: a git URL (GitHub/GitLab) is cloned, and a `.zip` is extracted, read-only, into the project's PM-OS-owned `.codebase/`, with `codebase_path` recorded in `.meta.yaml`. So for a git URL or a zip, run `/pm-context-import --codebase <url | code.zip>` **first**; then run `start` with no `--codebase` (it picks up the prepared `.codebase/` from `.meta.yaml`), or point `--codebase` at that local directory. For a repository already checked out on disk, pass its directory directly. The start/scan path records before-state evidence and must leave the codebase unchanged.

**The boundary is a hard gate.** Product stages 01–09 will not generate in an enhancement project until this cycle is started **and** `set-boundary` (step 4) has recorded the affected slice — `pre-stage.py` blocks them otherwise. So run `start` and `set-boundary` before any stage skill; approve `00c`/`00u` first, since `set-boundary` requires them.

## 2. Build `00c`: inventory, slice, then impact cone

Read `skills/pm-context-scan-codebase/SKILL.md` and execute its read-only workflow. `00-codebase-understanding.md` is the only user-facing repository inventory. Do not create a second codebase wiki.

Start with a lightweight whole-repository inventory, focus on the enhancement ask, and widen the impact cone when dependency or uncertainty evidence requires it. Capture UI, API, data, service, event, integration, operations, and cross-cutting surfaces without forcing frontend artifacts.

## 3. Run the decision interview

Ask only unresolved product decisions: production baseline, why/outcome, current→target behavior, affected and explicit non-touch surfaces, regression invariants, success, compatibility/migration, rollout/rollback, and decision authority. Do not re-ask cited code facts. Persist skips as known unknowns; unresolved baseline, boundary, invariants, or required migration block downstream generation unless an explicit accepted risk is recorded.

Write the binding boundary to `00-context-understanding.md`. The interview informs generation and must **Do not self-approve** stage 00 documents.

## 4. Record the approved boundary mechanically

After the stage-00 boundary is written, record its deterministic fields:

```bash
python3 ~/.pm-os/scripts/pm_enhance.py set-boundary \
  --current-behavior "<observed production behavior>" \
  --target-behavior "<approved target behavior>" \
  --surface ui --surface api \
  --affected-id FR-012 \
  --non-touch "existing authentication flow" \
  --invariant "existing sessions remain valid" \
  --authority "<decision owner>"
```

Allowed surfaces are `ui | api | data | service | event | integration | operations | cross-cutting`. Requirement change type in stages and handoff is exactly `new | modified | removed`.

## 5. Regenerate affected canonical content

Run normal pre-stage gates and stage skills in order. Update affected stable-ID blocks/sections only; carry unaffected canonical content forward. Stages remain the current product definition, while the enhancement delta is a derived baseline-vs-current view.

- Stages 01–03: current→target behavior, stable IDs, affected surfaces, and `new | modified | removed`.
- Stages 04–05: UI screens/prototype only when UI is affected; otherwise interface examples, schemas/migrations, service/event harnesses, integration sandboxes, or operational drills.
- Stages 06–09: regression invariants, compatibility/migration, metrics/guardrails, tasks, rollout/rollback, and roadmap consequences.

## 6. Check and derive the delta

```bash
python3 ~/.pm-os/scripts/pm_enhance.py delta
python3 ~/.pm-os/scripts/pm_check.py
```

The delta contains only new/modified/removed stable-ID blocks plus required context. `/pm-check` blocks baseline corruption, checkout drift, out-of-bound changes, change-type/surface gaps, changed requirements without tests/tasks, invariant gaps, and incomplete migration/rollback/observability coverage. It never replaces the canonical artifacts and never turns unaffected baseline work into handoff scope.

## 7. Handoff and complete

Run `/pm-handoff` only after ordinary approvals and `/pm-check` are green. While a cycle is active, package and Jira modes automatically emit delta work plus minimum ancestor closure; they refuse stale/unapproved changes and include baseline, impact, regression, compatibility, rollout, and rollback context. Then:

```bash
python3 ~/.pm-os/scripts/pm_enhance.py complete
```

Completion stamps `completed_at`, clears the active pointer, and makes the cycle context/baseline immutable. The approved current artifacts become the next product-of-record and the next enhancement captures them as its new baseline.

## Refresh semantics

Repository drift never silently changes the baseline. Continue against the pinned ref or explicitly run:

```bash
python3 ~/.pm-os/scripts/pm_enhance.py refresh --ref <git-ref>
```

Refresh records the new snapshot and makes `00c` plus normal downstream stages stale. It refuses completed cycles and any target-repository mutation.
