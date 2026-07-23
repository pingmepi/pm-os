# PM-OS — Build Specification

**Owner:** Karan (PM, Indegene)
**Status:** ✅ **Kernel implemented as of v0.4.8** — stages 01–08, approval gates (`hooks/pre-stage.py`, `hooks/post-approve.py`), the status/hash state machine, config, telemetry/feedback logs, HTML companions, and cross-runtime install (Claude + Codex) are all live. ⚠️ Parts of this spec are **aspirational and were never built** — `lib/edit_distance.py` and `lib/embeddings.py` (edit distance actually lives in `lib/text_metrics.py`; embedding-based semantic distance was never built), the `hooks/post-tool-use.py` and `hooks/session-end.py` hooks (§9.3/§9.4), the `session_end` telemetry event, and the "Sonnet default; Opus for 03/06" line in §6 step 9 (superseded by the runtime-neutral tier policy in §7). When this spec and the code disagree, trust the code and `ARCHITECTURE.md`.
**Purpose:** Build the product-definition kernel of a PM-led PDLC operating layer. v1 takes a business statement through a gated artifact pipeline (brief → scope → PRD → design spec → prototype brief → QA plan → metrics plan, plus optional TRD and roadmap capstones) with explicit PM approval at every stage. Later phases extend this kernel into dev handoff, QA bug triage, release readiness, and feedback ingestion.
**Target executor:** Claude Code and OpenAI Codex, working from this spec.

---

## Contents

1. [Context and intent](#1-context-and-intent)
2. [Non-negotiables](#2-non-negotiables)
3. [Repos and structure](#3-repos-and-structure)
4. [Project structure (on PM's machine)](#4-project-structure-on-pms-machine)
5. [Data schemas](#5-data-schemas)
6. [State machine](#6-state-machine)
7. [Skills — specifications](#7-skills--specifications)
8. [Per-stage prompt guidelines](#8-per-stage-prompt-guidelines)
9. [Hooks — specifications](#9-hooks--specifications)
10. [Library specifications](#10-library-specifications)
11. [Build phasing (for executor)](#11-build-phasing-for-executor)
12. [Technical defaults](#12-technical-defaults)
13. [Out of scope for v1](#13-out-of-scope-for-v1)
14. [Questions to escalate to Karan, not resolve unilaterally](#14-questions-to-escalate-to-karan-not-resolve-unilaterally)
15. [Acceptance criteria](#15-acceptance-criteria)
16. [Notes on building this system *using* Claude Code](#16-notes-on-building-this-system-using-claude-code)

---

## 1. Context and intent

PM-OS is an internal tool that expedites PM work at Indegene across the full PDLC. It is not a replacement for the dev team, design team, or QA — it is a recommendation and coordination layer that keeps one coherent thread from idea to ship.

**Decision authority:** The PM decides scope, trade-offs, approvals, priority, and release calls. PM-OS suggests, prepares, and validates. Developers and QAs execute. No lifecycle phase progresses without explicit PM approval.

**v1 scope (this spec):** The product-definition kernel. PMs go from a one-line business statement to a full set of approved product artifacts: brief, scope, PRD, design spec, prototype brief, QA plan, metrics plan, and an optional TRD. This kernel is the foundation; later phases add dev handoff, QA bug triage, release readiness, and feedback ingestion without replacing it.

The system is built as an agent skill suite for Claude Code and OpenAI Codex, with shared Python libraries and hooks. There is no frontend. There is no backend service. Everything runs locally on each PM's machine, with shared state via two GitHub repos.

**Build target:** single-user MVP (Karan only) for the first iteration. Architecture must be ready to distribute to other PMs without rewrite — only configuration and onboarding.

---

## 2. Non-negotiables

These constraints shape every design decision. Do not deviate without explicit confirmation:

- **No frontend.** Pure Claude Code skills + shared libraries + hooks.
- **No backend service.** State lives in files; aggregation lives in a git repo.
- **Markdown is the source of truth** for every artifact. HTML companions for design/prototype stages are generated, not authoritative.
- **Human-in-the-loop at every stage boundary.** No autonomous progression.
- **Append-only telemetry.** No edits to telemetry files post-write.
- **Distributable by design.** Single-user mode is a configuration, not a different architecture.
- **No PHI/PII handling required** for v1. Inputs are assumed sanitized.
- **No audit/compliance features.** This is internal prototyping assistance.
- **Pharma GenAI bias:** stages 03, 06, 07 must support GenAI-specific branching.

---

## 3. Repos and structure

Two GitHub repos. Both private.

### `pm-os` — the system itself

```
pm-os/
  VERSION                          # semver, e.g. "0.1.0"
  README.md                        # install + usage
  CHANGELOG.md
  skills/
    pm-os-install/SKILL.md         # bootstrap installer
    pm-os-update/SKILL.md          # pull latest tagged release
    pm-new/SKILL.md                # scaffold new project
    pm-status/SKILL.md             # show project state
    pm-approve/SKILL.md            # approve current stage
    pm-feedback/SKILL.md           # manual feedback capture
    pm-share/SKILL.md              # push artifacts to leadership share
    pm-context-import/SKILL.md     # context-intake: wiki + understanding doc + backfill
    pm-context-scan-docs/SKILL.md  # subagent: extract structured knowledge from source docs
    pm-context-scan-codebase/SKILL.md  # subagent: read-only codebase scan (enhancement mode)
    pm-stage-01-brief/SKILL.md
    pm-stage-02-scope/SKILL.md
    pm-stage-03-prd/SKILL.md
    pm-stage-04-design-spec/SKILL.md
    pm-stage-05-prototype-brief/SKILL.md
    pm-stage-06-qa-plan/SKILL.md
    pm-stage-07-metrics-plan/SKILL.md
    pm-stage-08-trd/SKILL.md
  lib/
    hashing.py                     # SHA-256 of artifact content excluding status
    frontmatter.py                 # YAML frontmatter read/write
    telemetry.py                   # append JSONL event with hash chain
    project.py                     # resolve project root from CWD, load .meta.yaml
    text_metrics.py                # Levenshtein char + normalized edit distance (implemented)
    # NOTE: embedding-based semantic distance (embeddings.py) was never built; semantic_distance
    #       is an optional agent estimate passed to pm-approve, not computed locally.
    config.py                      # config load + model-tier policy (model_tier_for_stage)
    context.py                     # context-overlay loader (resolve/render/seed)
    git_sync.py                    # push telemetry/feedback to feedback repo (push_feedback_repo + push_all)
    html_render.py                 # render design-spec.html and prototype-mockup.html
  hooks/
    pre-stage.py                   # gate: upstream approved + staleness check
    post-approve.py                # hash + telemetry push + companion HTML regen
    post-tool-use.py               # detect out-of-band artifact edits
    session-end.py                 # flush pending telemetry, push to feedback repo
  templates/
    meta.yaml.j2                   # project metadata template
    artifact-frontmatter.yaml.j2   # stage artifact frontmatter template
    design-spec.html.j2            # Tailwind-based design language preview
    prototype-mockup.html.j2       # Tailwind-based mockup template
  install.sh                       # one-line installer (curl | bash)
```

### `pm-os-feedback` — shared aggregation repo

```
pm-os-feedback/
  README.md
  telemetry/
    <pm-identifier>/
      <project-slug>/
        telemetry.jsonl
        feedback.jsonl
  inferred/                        # auto-generated weekly summaries (post-MVP)
```

For single-user MVP, `<pm-identifier>` = `karan`. Folder structure exists from day one to support multi-PM without restructuring.

---

## 4. Project structure (on PM's machine)

```
~/pm-projects/
  <project-slug>/
    .meta.yaml                     # project metadata (see schema below)
    00-business-statement.md       # raw input, PM-authored
    01-brief.md                    # generated
    02-scope.md
    03-prd.md
    04-design-spec.md
    04-design-spec.html            # generated on approval of 04
    05-prototype-brief.md
    05-prototype-mockup.html       # generated on approval of 05
    06-qa-plan.md
    07-metrics-plan.md
    08-trd.md                      # optional technical capstone
    telemetry.jsonl                # local, append-only, hash-chained
    feedback.jsonl                 # local, append-only
    .history/
      <NN>-<name>.<timestamp>.generated.md   # all initial generations
```

---

## 5. Data schemas

### 5.1 `.meta.yaml`

```yaml
schema_version: 3                     # v2 added stage 00 + origin; v3 added project_type + codebase fields; lib/project.py:migrate_meta upgrades older projects
project_slug: <kebab-case-slug>
project_name: <human readable>
created_at: <ISO 8601>
created_by: <pm identifier from $PM_OS_USER>
genai_flag: true | false              # set at /pm-new, propagates downstream
project_type: new_product | enhancement     # v3; set at /pm-new --mode (default new_product)
codebase_path: <url-or-local-path or null>  # v3; enhancement codebase, set via /pm-new --codebase or prepare-codebase
codebase_ref: <git sha or null>             # v3; codebase HEAD recorded at scan time (for drift detection)
pm_os_version: <semver from VERSION file at scaffold time>
stages:
  # Stage-00 understanding group. "00" (business statement) is always present and
  # gated; the conditional "00c" codebase-understanding, "00w" context-wiki, and
  # "00u" context-understanding exist only when /pm-context-import is used ("00c"
  # only in enhancement mode). All present stage-00 docs must be approved before stage 01.
  - id: "00"
    name: business-statement
    status: pending | draft | approved | edited | stale
    approved_at: <ISO 8601 or null>
    content_hash: <sha256 or null>
    upstream_hashes_at_approval: {}   # map of stage id -> hash at this stage's approval
    regeneration_count: 0
    optional: false
    origin: generated | imported | backfilled   # how the artifact got here
  - id: "01"
    name: brief
    ...
```

### 5.2 Artifact frontmatter

Every generated artifact starts with:

```yaml
---
stage: <NN-name>
project: <project-slug>
status: draft | approved | edited | stale
approved_at: <ISO 8601 or null>
approved_by: <pm identifier or null>
content_hash: <sha256 of body, computed at approval>
generated_hash: <sha256 of initial generation>
pm_os_version: <semver>
genai_flag: true | false
artifact_contract_version: 3   # present on contract-validated Stage 03–06 generations
origin: generated | imported | backfilled
generation_notes: [<verbatim --note values, or empty>]
---

# <Artifact Title>

<body in markdown>
```

`content_hash` is computed over the body only (everything after the closing `---`), so frontmatter changes don't trigger false positives.

### 5.3 Telemetry event (JSONL line)

```json
{
  "event_id": "<uuid4>",
  "prev_event_hash": "<sha256 of previous event in this file, or null for first>",
  "event_hash": "<sha256 of this event excluding event_hash field>",
  "timestamp": "<ISO 8601>",
  "pm": "<pm identifier>",
  "project": "<project-slug>",
  "pm_os_version": "<semver>",
  "event_type": "stage_started | stage_generated | stage_approved | stage_imported | stage_backfilled | context_ingested | stage_edited_post_approval | stage_edited_via_note | artifact_validation_warning | stage_marked_stale | implicit_reapproval | feedback_submitted | handoff_exported | session_end",
  "stage": "<NN or null>",
  "payload": { ... event-specific fields }
}
```

Hash chain provides tamper-evidence. Append-only by convention.

**Event-specific payloads:**

- `stage_started`: `{}`
- `stage_generated`: `{ generated_hash, model, model_tier, prompt_version, notes }` — `model` is the actual model id the agent ran as (it fills in its own id); `model_tier` is derived from `config.deep_reasoning_stages` (not baked per-skill) so policy and telemetry can't drift
- `stage_approved`: `{ generated_hash, approved_hash, char_edit_distance, normalized_edit_distance, semantic_distance, time_to_approve_seconds, regeneration_count, implicit_reapproval: bool }` — `char_edit_distance`/`normalized_edit_distance` diff the retained `.history/<stage>.*.generated.md` snapshot against the approved body; `time_to_approve_seconds` is the approval timestamp minus the matching `stage_generated` timestamp; `semantic_distance` is an optional 0..1 agent judgment via `--semantic-distance`. All stay `null` when no generation snapshot/event exists (stage-00 group, imported/backfilled).
- `context_ingested`: `{ source_id, source_type, source_filename, snapshot }` — a PM-provided source registered via `/pm-context-import` (original design in `../archive/pm-os-ingest-plan.md`, §0 for the shipped shape). Raw original preserved under `.history/`; registry in `.sources.yaml`.
- `stage_imported`: `{ origin: "imported", approved_hash, source_format, source_filename, derived_from }` — a PM-authored artifact adopted as this stage's artifact (not generated). Kept distinct from `stage_approved` so edit-distance/time-to-approve signals are not polluted.
- `stage_backfilled`: `{ origin: "backfilled", approved_hash, derived_from, model, model_tier }` — an upstream gap reverse-generated to keep the chain intact below an adopted artifact (feasibility per `lib/project.resolve_backfill`). Model-produced, so it carries `model`/`model_tier` like `stage_generated`.
- `stage_edited_post_approval`: `{ old_hash, new_hash, detected_via: "pre_stage_hook" }` — emitted by `hooks/pre-stage.py` when it re-hashes an approved upstream and finds drift
- `stage_edited_via_note`: `{ note, edited_sections }` — logged on an upstream stage when a later stage's `--note` is reconciled into that upstream artifact (see §7 Steering notes)
- `artifact_validation_warning`: `{ contract_version, origin, findings: [{ severity, code, message }] }` — logged when approval or imported/backfilled approval continues despite Stage 03–06 (or the stage-08 GenAI model check) artifact-contract findings
- `stage_marked_stale`: `{ reason, triggering_upstream_stage }`
- `implicit_reapproval`: `{ stage, old_hash, new_hash }`
- `feedback_submitted`: `{ stage, scope: "stage" | "cross_stage", rating: 1-5, tags: [], free_text }`
- `handoff_exported`: `{ tracker, created_count, tickets: { <stable-id>: <ticket-key> } }` — logged by `scripts/pm_handoff.py record` (Phase 4b) after tickets are created in the external tracker and their keys written back into `.traceability.yaml`. Stores only refs/ids/keys, never bulk copies of external data. Logged identically whether the tickets were created through the Atlassian connector or imported from the offline `pm_handoff.py export` CSV
- `session_end`: `{ session_duration_seconds, events_in_session }` — **aspirational; not emitted** (no session boundary in the skill model; `telemetry.flush_pending()` is a no-op)

### 5.4 Feedback entry (JSONL line)

```json
{
  "feedback_id": "<uuid4>",
  "timestamp": "<ISO 8601>",
  "pm": "<pm identifier>",
  "project": "<project-slug>",
  "scope": "stage" | "cross_stage",
  "stage": "<NN or null>",
  "rating": 1-5,
  "tags": ["prompt_weak", "missing_section", "hallucination", "tone_off", "format_broken", "other"],
  "free_text": "...",
  "trigger": "manual" | "post_approval_prompt"
}
```

---

## 6. State machine

Each stage has a status, transitioned by explicit commands and hooks.

```
pending  →  (run /pm-stage-NN)              →  draft
draft    →  (run /pm-approve NN)            →  approved
approved →  (PM edits file outside CC)      →  edited
approved →  (upstream edited, hash drift)   →  stale
edited   →  (run /pm-approve NN)            →  approved
edited   →  (run downstream /pm-stage NN+1) →  approved (implicit reapproval, logged)
stale    →  (run /pm-stage-NN again)        →  draft
stale    →  (run /pm-approve NN)            →  approved (PM attests "still valid")
```

**Hash-based detection rules:**

- On any stage skill invocation, recompute hashes of all upstream artifacts marked `approved`. Any mismatch with `content_hash` in frontmatter → mark that artifact `edited`.
- On stage N invocation, if any upstream stage is `edited`, present the implicit-reapproval prompt described below.
- On stage approval, snapshot all upstream `content_hash` values into the artifact's `upstream_hashes_at_approval`.

**Implicit reapproval prompt** (when downstream stage runs with `edited` upstream):

```
Upstream stage <NN> was edited after approval.
  - Approved hash: <abc123>
  - Current hash:  <def456>

Options:
  [1] Continue — generate stage <NN+1> using current upstream content
      (this implicitly re-approves stage <NN>)
  [2] Re-approve stage <NN> explicitly first (recommended for significant edits)
  [3] Cancel

Choice [1/2/3]:
```

Option 1 → log `implicit_reapproval` event, flip upstream status to `approved` with new hash, proceed.
Option 2 → halt with instruction to run `/pm-approve <NN>` first.
Option 3 → exit cleanly, no state change.

---

## 7. Skills — specifications

For every stage skill, the SKILL.md follows this structure:

```markdown
---
name: pm-stage-NN-<name>
description: <one-line>
reads: [<list of upstream artifact filenames>]
writes: <output filename>
prompt_version: <semver>
---

# Role and goal
<who Claude is and what this stage produces>

# Inputs
<for each input file, what to extract>

# Output specification
<exact markdown structure with required sections>
<if the stage has GenAI-specific requirements: condition them on the project's genai_flag>

# Quality bar
<what good looks like, what to avoid, common failure modes>

# Self-check before writing
<3-5 checks the model runs on its own draft before emitting>
```

GenAI architecture: PM-OS uses one `SKILL.md` per stage. Do not create separate GenAI and non-GenAI skill files, and do not encode branch capability in frontmatter. Every generative stage reads `genai_flag` from `.meta.yaml`; the skill body states exactly how output changes when `genai_flag=true` or `genai_flag=false`.

Cross-runtime interface: each stage directory also ships an `agents/openai.yaml` describing how the stage is surfaced in OpenAI/Codex-style runtimes. It carries an `interface:` block with `display_name`, `short_description`, and `default_prompt` (the `default_prompt` invokes the stage via `$<skill-name>`). Every stage directory includes one.

Model selection: shared skill metadata uses runtime-neutral model tiers, not provider model ids. Skills that need extra reasoning declare `model_tier: deep-reasoning`; utility skills may declare `model_tier: utility`. Stages 03 (PRD), 04 (Design Spec), 06 (QA Plan), 08 (TRD), and 09 (Roadmap) recommend the `deep-reasoning` tier and include a "Model guidance" block; the context-build docs (`00w`/`00u`, generated via `/pm-context-import`) are deep-reasoning too. The guidance tells the runtime to continue when the current model appears suitable, continue with a note when the model is unknown, and pause only when the current model is clearly lightweight or low-reasoning. Claude users map `deep-reasoning` to Opus or the strongest available reasoning model; Codex users map it to a high/deep reasoning model. There is no env var a hook can read for the active model, so this guidance lives in the skill body and is advisory, not runtime-enforced.

Steering notes: generative stages accept repeatable `--note "<text>"` arguments (read from `$ARGUMENTS`) that steer a generation — e.g. excluding a feature or dropping a target segment. Notes apply **forward only** by default: they shape the current artifact and downstream stages, and are recorded verbatim in the artifact's `generation_notes` frontmatter (excluded from the body-only `content_hash`), in `.history`, and in the `stage_generated` telemetry payload. When a note contradicts a binding decision in an upstream artifact (e.g. a stage-02 note drops a target user the brief named), the stage stops and offers the PM three choices: (1) reconcile into the upstream artifact — edits it, appends the note to its `generation_notes`, logs `stage_edited_via_note`, and lets the existing pre-stage hash-drift cascade mark downstream stages stale for re-approval; (2) apply forward only and let the documents diverge; or (3) cancel. The system never silently rewrites an upstream artifact.

### 7.1 `pm-os-install`

Bootstrap installer. Performs:

1. Verify Claude Code version >= required (check `claude --version`).
2. Clone `pm-os` repo to `~/.pm-os/`.
3. Symlink or copy all `skills/*` to `~/.claude/skills/`.
4. Symlink or copy all `hooks/*` to `~/.claude/hooks/` (or whatever Claude Code's hook directory is).
5. Set up `~/pm-projects/` directory.
6. Prompt for `PM_OS_USER` value and write to shell rc (`~/.zshrc` or `~/.bashrc`).
7. Prompt for `pm-os-feedback` repo SSH/HTTPS URL, configure as remote.
8. Run smoke test: create a throwaway project, run stage 1, approve, verify telemetry was written and pushed.
9. Print instructions to restart Claude Code session for skills to load.

### 7.2 `pm-os-update`

1. `cd ~/.pm-os && git fetch --tags`
2. Compare latest tag to local `VERSION`.
3. If newer: checkout latest tag, re-sync skills and hooks to Claude Code directories.
4. Print changelog diff.
5. Prompt user to restart session.

### 7.3 `pm-new <slug> ["<business statement>"] [--genai|--no-genai] [--mode new_product|enhancement] [--codebase <url-or-path>]`

1. Validate slug is kebab-case and unique under `~/pm-projects/`.
2. Create `~/pm-projects/<slug>/`.
3. Write `00-business-statement.md` with frontmatter and the statement as body. The statement is optional — if omitted, a placeholder body is written for the PM to fill before approving `00`.
4. Prompt user: "Is this a GenAI/agentic product? [y/n]" (or take `--genai`/`--no-genai`/`PM_OS_GENAI_FLAG`). Set `genai_flag` in `.meta.yaml`.
5. Resolve `project_type` from `--mode` → `PM_OS_PROJECT_TYPE` → default `new_product`; record `project_type`, `codebase_path` (from `--codebase`, enhancement only), and `codebase_ref: null` in `.meta.yaml` (`schema_version: 3`).
6. Initialize `.meta.yaml` with stage `00` as `draft` and stages `01–09` in `pending` status.
7. Initialize empty `telemetry.jsonl` and `feedback.jsonl`.
8. Log `project_created` event (with `project_type`) to telemetry.

### 7.4 `pm-stage-NN-<name>` (per stage)

Common flow:

1. Resolve project from CWD (must be a `~/pm-projects/<slug>/` directory).
2. Load `.meta.yaml`.
3. Run pre-stage hook: verify upstream stages are `approved` or `edited` (not `pending`, `draft`, or `stale`).
4. If any upstream is `edited`: present implicit-reapproval prompt (section 6).
5. Recompute upstream hashes; if drift detected on `approved` artifacts, mark as `edited` and re-evaluate gate.
6. Log `stage_started` event.
7. Read upstream artifacts per the skill's `reads` declaration.
8. Render the stage prompt with upstream content injected.
9. Generate output (model choice is **runtime-neutral**: the `deep-reasoning` tier for stages in `deep_reasoning_stages`, `standard` otherwise — see §7; no hardcoded provider model).
10. Write generated content to `.history/<NN>-<name>.<timestamp>.generated.md`.
11. Write same content to `<NN>-<name>.md` with frontmatter status=`draft`, `generated_hash` set.
12. Log `stage_generated` event with `generated_hash` and `prompt_version`.
13. Increment `regeneration_count` in `.meta.yaml`.
14. Print summary to PM: "Stage <NN> draft written to <path>. Review and run `/pm-approve <NN>` when ready, or re-run `/pm-stage-<NN>` to regenerate, or run `/pm-feedback <NN>` to capture notes."

**Per-stage prompts:** see section 8 for content guidelines. Initial prompts will be sparse; iteration happens during Phase 4 dogfooding.

### 7.5 `pm-approve <NN>`

1. Resolve project from CWD.
2. Load `<NN>-<name>.md`.
3. Verify status is `draft` or `edited` or `stale`. If `approved` already, no-op with message.
4. Read latest `.history/<NN>-<name>.*.generated.md` for distance comparison.
5. Compute:
   - `content_hash` of current body
   - `char_edit_distance` = Levenshtein(generated, current)
   - `normalized_edit_distance` = char_edit_distance / max(len(generated), len(current))
   - `semantic_distance` = 1 - cosine_similarity(embed(generated), embed(current))
   - `time_to_approve_seconds` = now - last `stage_generated` event timestamp
6. Update artifact frontmatter: status=`approved`, `approved_at`, `approved_by`, `content_hash`.
7. Update `.meta.yaml` stage entry: status=`approved`, snapshot upstream hashes into `upstream_hashes_at_approval`.
8. For stages 04 and 05: invoke `lib/html_render.py` to regenerate companion HTML.
9. Log `stage_approved` event with full distance metrics.
10. Run post-approve hook: push telemetry + feedback JSONL to feedback repo.
11. Mark downstream stages: if any downstream had status `approved`, flip to `stale` (their upstream changed). Log `stage_marked_stale` events.
12. Optionally prompt PM: "Capture feedback for stage <NN>? [y/n]" — if yes, invoke `pm-feedback NN`.

### 7.6 `pm-feedback [NN]`

1. Resolve project from CWD.
2. If `NN` provided, scope=`stage`. Otherwise prompt for scope (`stage` or `cross_stage`).
3. Prompt: rating (1-5).
4. Prompt: tags (multi-select from fixed list + "other").
5. Prompt: free text.
6. Append entry to `feedback.jsonl`.
7. Log `feedback_submitted` event to telemetry.
8. Push to feedback repo immediately.

### 7.7 `pm-status`

Print project state:

```
Project: <slug>
Created: <timestamp>  GenAI: <y/n>  PM-OS version: <semver>

Stages:
  01 Brief              [approved]  edit distance: 0.12  approved 2h ago
  02 Scope              [approved]  edit distance: 0.08  approved 1h ago
  03 PRD                [edited]    last approved 30m ago, edited since
  04 Design Spec        [stale]     upstream 03 changed after approval
  05 Prototype Brief    [pending]
  06 QA Plan            [pending]
  07 Metrics Plan       [pending]
  08 TRD                [pending]  (optional)

Recent events:
  <last 5 telemetry events, human-formatted>

Feedback captured: <count> entries
Telemetry events:  <count>
```

### 7.8 `pm-share <NN>` (or `all`)

1. Resolve project from CWD.
2. If `NN`: target one artifact. If `all`: target all `approved` artifacts.
3. Verify status is `approved`.
4. Push to configured share destination (MCP connector for Confluence/Drive/SharePoint). MVP can simply copy artifact paths to clipboard or print a summary block PM pastes manually — full MCP integration is post-demo.

---

## 8. Per-stage prompt guidelines

**Important:** initial prompts should be minimal and conventional. Real prompt quality comes from Phase 4 iteration. Do not overengineer prompts in the initial build.

### Stage 01 — Brief
Output sections: Problem, Target user, Why now, Success hypothesis, Out of scope, GenAI flag rationale.

### Stage 02 — Scope
Output sections: In scope, Out of scope, Constraints, Assumptions, Dependencies, MVP boundary, Open questions.

### Stage 03 — PRD (use Opus)
Required output sections: Overview, Goals and non-goals, **User journeys**, User stories with acceptance criteria, Functional requirements, Non-functional requirements, Data & governance, Edge cases, Risks. Journeys use stable `UJ-###` identifiers and trace to stable `US-###` / `FR-###` identifiers.
Recommended sections: Journey–requirement traceability; Assumptions & open decisions.
**When `genai_flag=true`:** add sections — Model selection rationale, Prompt/agent architecture, Tool/function inventory, Context window strategy, Fallback behavior, Output validation strategy.

### Stage 04 — Design Spec
Required output sections: Information architecture, **Journey-to-flow traceability**, Key user flows, **Product UX guardrails**, Design principles, Component inventory, Typography, Color tokens, Spacing tokens, Iconography, Accessibility notes. Product UX guardrails declare `Interaction model: retrieval-only | generative | mixed | non-AI`.
Recommended sections: Responsive & platform behavior; UX content rules.
**Companion HTML:** rendered from these tokens.

### Stage 05 — Prototype Brief
Required output sections: What to prototype, Fidelity level, **Prototype audience & modes**, Screens to include, Interactions to demonstrate, Questions the prototype should answer, **Validation plan**, Non-goals for prototype.
Recommended sections: Prototype data & scenarios; Known limitations.
**Companion HTML:** interactive participant mode by default; reviewer navigation/questions/metadata appear only with `?review=1`. UI behavior follows the design's interaction model, not `genai_flag` alone.

### Artifact contracts (Stages 03–05)

`scripts/pm_validate_artifact.py <03|04|05|05-html|06|08> --mode strict|warn` validates required sections, recommended sections, journey traceability, screen ids (`SCR-###` + `Serves:`), prototype modes, and high-signal HTML guardrails. Stage 08 has no required-section contract and is validated only for the GenAI model availability/fallback check. Stage skills run strict mode before generation telemetry; required-section errors must be repaired. Approval and context-import use warning mode: they surface and record findings but continue. Imported PM-authored documents are preserved rather than silently augmented with invented content. `pm-status` shows a warning count for any contract-validated artifact that has findings.

### Stage 06 — QA Plan (use Opus)
Output sections: Test strategy, Functional test cases, Non-functional tests, Edge cases, Acceptance criteria.
**When `genai_flag=true`:** add sections — Eval dataset spec, Golden set construction, LLM-as-judge rubric, Hallucination test plan, Latency/cost SLOs, Red-team scenarios, Prompt regression suite.

### Stage 07 — Metrics Plan
Output sections: North star metric, Input metrics, Output metrics, Guardrail metrics, Instrumentation plan, Dashboard sketch, Review cadence.
**When `genai_flag=true`:** add sections — Quality metrics (accuracy, faithfulness), Cost per invocation, Token usage, Model performance drift detection.

### Stage 08 — TRD (optional, use Opus)
Optional technical capstone. Always scaffolded (`optional: true` in `.meta.yaml`) but only runnable once stages 01–07 are approved; it reads the full pipeline and details how the product is built. Owned conceptually by engineering, not the PM. Separation of concerns: the PRD says **what/why**, the TRD says **how**.
Output sections: System context, Architecture, Data model, API/interface contracts, Key technical flows, Tech stack & rationale, Non-functional implementation, Dependencies & integrations, Trade-offs & alternatives considered, Technical risks & mitigations, Rollout/migration/deployment, **Work Breakdown**, Open technical questions.
The **Work Breakdown** enumerates discrete engineering tasks with stable `TSK-###` ids, each tracing (`Implements:`) to the PRD requirement(s) it delivers (Phase 3.5b). These are the handoff spine: `.traceability.yaml` indexes them under a `tasks:` map (schema v3, which also carries the design spec's `screens:` map) with a reserved `tickets: []` slot — only when the TRD is **approved**, and only tasks inside the `## Work Breakdown` section — and the tracker export (`/pm-handoff`, Phase 4b) keys tickets off them. `/pm-check` validates that `TSK-###` ids are unique, sequential, and each traces to a real PRD requirement.
**When `genai_flag=true`:** add sections — Model serving & selection, Prompt/agent architecture (implementation), Tool/function implementation, Context & retrieval engineering, Evaluation & guardrail implementation, Inference cost & latency engineering. (The PRD keeps its product-level GenAI sections; the TRD goes deeper into implementation.)

---

## 9. Hooks — specifications

### 9.1 `pre-stage.py`

Triggered before any `pm-stage-NN` skill runs.

1. Resolve project from CWD.
2. Recompute hashes of all upstream artifacts marked `approved`.
3. For each mismatch: update frontmatter status to `edited`, log `stage_edited_post_approval` event.
4. If any upstream stage is `pending`, `draft`, or `stale`: block with clear error message.
5. If any upstream is `edited`: trigger implicit-reapproval prompt (see section 6).
6. Allow stage skill to proceed.

### 9.2 `post-approve.py`

Triggered after `pm-approve` completes successfully.

1. Push `telemetry.jsonl` and `feedback.jsonl` to feedback repo at appropriate path.
2. For stages 04 and 05: invoke HTML companion regeneration.
3. Cascade staleness: any downstream stage previously `approved` → flip to `stale`, log events.

### 9.3 `post-tool-use.py`

Triggered after any Claude Code tool use. Filters for file write operations on `~/pm-projects/**/*.md` paths.

1. Identify which project and which stage artifact was written.
2. Recompute body hash.
3. Compare to frontmatter `content_hash`.
4. If artifact status is `approved` and hashes differ: flip status to `edited`, log `stage_edited_post_approval` event.

### 9.4 `session-end.py`

Triggered on Claude Code session end.

1. For each project touched this session: ensure all pending telemetry events are flushed.
2. Push to feedback repo.
3. Log `session_end` event with session duration.

---

## 10. Library specifications

### `lib/hashing.py`
- `hash_artifact_body(file_path) -> str`: SHA-256 of content after frontmatter close marker.
- `hash_event(event_dict, prev_hash) -> str`: SHA-256 of canonicalized JSON with `event_hash` field excluded, prefixed with `prev_hash`.

### `lib/frontmatter.py`
- `read(file_path) -> (frontmatter_dict, body_str)`
- `write(file_path, frontmatter_dict, body_str)`
- `update_status(file_path, new_status, **kwargs)`: convenience to flip status and update related fields atomically.

### `lib/telemetry.py`
- `log(event_type, project, stage, payload)`: append-only write to `<project>/telemetry.jsonl` with hash chaining. Reads last line to get `prev_event_hash`.
- `flush_pending()`: no-op for MVP (writes are synchronous); placeholder for future async batching.

### `lib/project.py`
- `resolve_project() -> Path`: walk up from CWD to find directory containing `.meta.yaml`. Raise if not found.
- `load_meta() -> dict`
- `save_meta(meta_dict)`

### `lib/edit_distance.py`
- `levenshtein(a, b) -> int`
- `normalized(a, b) -> float`
- `semantic(a, b) -> float`: via `embeddings.py`

### `lib/embeddings.py`
- Wraps `sentence-transformers` with `all-MiniLM-L6-v2` (small, fast, local). Cache embeddings keyed by content hash to avoid recomputation.

### `lib/git_sync.py`
- `push_feedback_repo()`: clone-or-fetch feedback repo to `~/.pm-os-feedback-cache/`, copy local telemetry/feedback JSONL files to appropriate paths, commit with message `telemetry: <pm> <project> <timestamp>`, push.
- Idempotent. Safe to call repeatedly.

### `lib/html_render.py`
- `render_design_spec(project_slug) -> writes 04-design-spec.html`
- `render_prototype_mockup(project_slug) -> writes 05-prototype-mockup.html`
- Uses Jinja2 templates from `templates/`.

---

## 11. Build phasing (for executor)

Build in this order. Do not skip ahead.

### Phase 1 — Engine skeleton (target: 1 day)
1. Set up `pm-os` repo with directory structure from section 3.
2. Implement `lib/` modules: `hashing`, `frontmatter`, `project`, `telemetry`, `git_sync`. Skip `edit_distance` and `embeddings` for now.
3. Implement `pm-new`, `pm-status`, `pm-approve` skills (without distance metrics).
4. Implement `pm-stage-01-brief` with a minimal prompt.
5. Wire hooks: `pre-stage`, `post-approve`.
6. Smoke test: create project, run stage 1, approve, verify telemetry written and pushed to local feedback repo.

**Phase 1 done = the loop closes on one stage end-to-end.**

### Phase 2 — Remaining stages (target: 3 days)
Build stages 02, 07, 06, 04, 05, 03 in that order (easiest to hardest). For each:
1. Write SKILL.md with minimal prompt per section 8 guidelines.
2. Verify `genai_flag` activation works for stages 03, 06, 07.
3. Run end-to-end on a throwaway project.

For stages 04 and 05: also implement `html_render.py` and the Jinja templates. HTML companions are basic Tailwind, single-file, no JS framework.

**Phase 2 done = full 7-stage pipeline runs on one real-feel project.**

### Phase 3 — Hardening (target: 1.5 days)
1. Implement `lib/edit_distance.py` and `lib/embeddings.py`. Add distance computation to `pm-approve`.
2. Implement `post-tool-use.py` hook for out-of-band edit detection.
3. Implement `session-end.py` hook for telemetry flushing.
4. Implement implicit-reapproval prompt flow.
5. Implement `pm-feedback` skill.
6. Implement `pm-status` with full state display.
7. Implement `pm-os-install` and `pm-os-update` skills.
8. Write `install.sh` and `README.md`.

**Phase 3 done = Karan can reliably use this on real Indegene projects.**

### Phase 4 — Dogfood (Karan-driven, not Claude Code work)
Karan runs 2-3 real projects through the system. Captures feedback aggressively. Iterates prompts in `skills/pm-stage-*/SKILL.md`. No new features.

### Phase 5 — Demo prep (target: 2 days)
1. One polished sample project with all 7 artifacts approved.
2. Pitch deck (5-7 slides).
3. Optional `pm-share` MCP integration if a target system is decided.

### Phase 6 — Distribution (target: 2 days, contingent on approval)
1. Real `pm-os-install` flow for onboarding new PMs.
2. Per-PM feedback repo folders.
3. Weekly prompt-update cadence documented.

---

## 12. Technical defaults

- **Language:** Python 3.11+ for all `lib/` and hooks. No other runtime.
- **Dependencies:** keep minimal. Allowed: `pyyaml`, `jinja2`, `sentence-transformers`, `python-Levenshtein`, `gitpython` (or shell out to `git`). Avoid heavy frameworks.
- **Model selection:**
  - Shared config stores `default_model_tier: standard`.
  - Shared config stores `deep_reasoning_stages: ["00w", "00u", "03", "04", "06", "08", "09"]`.
  - Skills run inline on the current session model; `model_tier:` frontmatter is advisory, not runtime-enforced.
  - Deep-reasoning stages prompt the PM to switch to the runtime's strongest appropriate reasoning model and re-invoke (see §7).
- **Embeddings model:** `sentence-transformers/all-MiniLM-L6-v2` — small, local, no API cost.
- **Timestamps:** ISO 8601 UTC throughout.
- **UUIDs:** uuid4.
- **Hash algorithm:** SHA-256.
- **Line endings:** LF only. Normalize on read for hash stability.

---

## 13. Out of scope for v1

> ⚠️ **Superseded for later phases.** This list defined the boundary of the *original v1 kernel*. The canonical roadmap is now `docs/roadmap/current-state-review.md`, which deliberately brings several of these items **back into scope** in later phases — notably engineering handoff and MCP integrations beyond `pm-share` (Jira/Linear/Figma, Phase 4), and data-governance/compliance content (now required in PRD/QA/TRD as of v0.4.8). Treat the items below as out of scope **only for the v1 kernel**; where this list and the Current State Review disagree, the review wins.

Do not build these in the v1 kernel. If a design decision seems to require one, flag and stop.

- Frontend / web UI
- Backend service / API
- Cross-project memory or knowledge base
- Audit logging beyond telemetry
- PHI/PII handling, compliance features
- Real-time collaboration (multiple PMs on one project)
- Cloud-hosted aggregation
- Dashboards (telemetry is for analysis via scripts only in v1)
- Automatic prompt iteration / RLHF / self-improvement loops
- MCP integrations beyond optional `pm-share`
- Code generation (real prototype generation deferred to v2)
- Figma integration

---

## 14. Questions to escalate to Karan, not resolve unilaterally

If during build you encounter:

1. Ambiguity in stage prompt content beyond what section 8 specifies → write minimal version, flag for Phase 4 iteration.
2. Choice between two viable architectures within these constraints → write up trade-offs, ask.
3. Need for a dependency not in section 12 → ask before adding.
4. Apparent contradiction in this spec → ask, do not guess.
5. Anything that would require deviating from non-negotiables in section 2 → stop.

---

## 15. Acceptance criteria

The build is complete (Phase 1-3) when:

- [ ] Fresh machine can run `install.sh` and have a working PM-OS in <5 minutes.
- [ ] `pm-new` scaffolds a project correctly with all frontmatter and `.meta.yaml`.
- [ ] Running all 7 stages sequentially produces 7 artifacts + 2 HTML companions, all in `approved` status.
- [ ] Editing an approved artifact outside Claude Code is detected on next stage invocation.
- [ ] Implicit reapproval flow works as specified.
- [ ] Marking upstream stale cascades correctly to downstream.
- [ ] Telemetry events are hash-chained and tamper-evident.
- [ ] All telemetry and feedback pushes to `pm-os-feedback` repo succeed.
- [ ] `pm-status` correctly reports project state.
- [ ] `genai_flag` triggers correct conditional output in stages 03, 06, 07.
- [ ] Session-end hook flushes telemetry on Claude Code exit.

---

## 16. Notes on building this system *using* Claude Code

The executor (Claude Code) will be building PM-OS, which itself is a Claude Code extension. To avoid confusion:

- Keep build artifacts in a clean working directory separate from any `~/.claude/skills/` symlinks.
- Test the install flow on a clean directory before claiming Phase 1 done.
- Do not install PM-OS skills into the same Claude Code session that's building them — restart sessions between build and test.

---

End of specification.
