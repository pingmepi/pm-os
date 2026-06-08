# PM-OS — Build Specification

**Owner:** Karan (PM, Indegene)
**Purpose:** Build a Product Manager Operating System that takes a business statement as input and runs it through a 7-stage product definition pipeline, generating draft artifacts at each stage with human-in-the-loop approval gates.
**Target executor:** Claude Code, working from this spec.

---

## 1. Context and intent

PM-OS is an internal tool that expedites PM work at Indegene. It is not a replacement for the dev team. PMs use it to go from a one-line business statement to a full set of product definition artifacts: brief, scope, PRD, design spec, prototype, QA plan, metrics plan.

The system is built as a set of Claude Code skills with shared libraries and hooks. There is no frontend. There is no backend service. Everything runs locally on each PM's machine, with shared state via two GitHub repos.

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
    pm-stage-01-brief/SKILL.md
    pm-stage-02-scope/SKILL.md
    pm-stage-03-prd/SKILL.md
    pm-stage-04-design-spec/SKILL.md
    pm-stage-05-prototype-brief/SKILL.md
    pm-stage-06-qa-plan/SKILL.md
    pm-stage-07-metrics-plan/SKILL.md
  lib/
    hashing.py                     # SHA-256 of artifact content excluding status
    frontmatter.py                 # YAML frontmatter read/write
    telemetry.py                   # append JSONL event with hash chain
    project.py                     # resolve project root from CWD, load .meta.yaml
    edit_distance.py               # Levenshtein + embedding cosine distance
    embeddings.py                  # local sentence-transformers wrapper
    git_sync.py                    # push telemetry/feedback to feedback repo
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
    telemetry.jsonl                # local, append-only, hash-chained
    feedback.jsonl                 # local, append-only
    .history/
      <NN>-<name>.<timestamp>.generated.md   # all initial generations
```

---

## 5. Data schemas

### 5.1 `.meta.yaml`

```yaml
schema_version: 1
project_slug: <kebab-case-slug>
project_name: <human readable>
created_at: <ISO 8601>
created_by: <pm identifier from $PM_OS_USER>
genai_flag: true | false              # set at /pm-new, propagates downstream
pm_os_version: <semver from VERSION file at scaffold time>
stages:
  - id: "01"
    name: brief
    status: pending | draft | approved | edited | stale
    approved_at: <ISO 8601 or null>
    content_hash: <sha256 or null>
    upstream_hashes_at_approval: {}   # map of stage id -> hash at this stage's approval
    regeneration_count: 0
  - id: "02"
    name: scope
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
  "event_type": "stage_started | stage_generated | stage_approved | stage_edited_post_approval | stage_marked_stale | implicit_reapproval | feedback_submitted | session_end",
  "stage": "<NN or null>",
  "payload": { ... event-specific fields }
}
```

Hash chain provides tamper-evidence. Append-only by convention.

**Event-specific payloads:**

- `stage_started`: `{}`
- `stage_generated`: `{ generated_hash, model, prompt_version }`
- `stage_approved`: `{ generated_hash, approved_hash, char_edit_distance, normalized_edit_distance, semantic_distance, time_to_approve_seconds, regeneration_count, implicit_reapproval: bool }`
- `stage_edited_post_approval`: `{ old_hash, new_hash, detected_via: "post_tool_use_hook" }`
- `stage_marked_stale`: `{ reason, triggering_upstream_stage }`
- `implicit_reapproval`: `{ stage, old_hash, new_hash }`
- `feedback_submitted`: `{ stage, scope: "stage" | "cross_stage", rating: 1-5, tags: [], free_text }`
- `session_end`: `{ session_duration_seconds, events_in_session }`

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
genai_branch: true | false
prompt_version: <semver>
---

# Role and goal
<who Claude is and what this stage produces>

# Inputs
<for each input file, what to extract>

# Output specification
<exact markdown structure with required sections>
<if genai_branch=true: additional sections that activate when project's genai_flag=true>

# Quality bar
<what good looks like, what to avoid, common failure modes>

# Self-check before writing
<3-5 checks the model runs on its own draft before emitting>
```

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

### 7.3 `pm-new <slug> "<business statement>"`

1. Validate slug is kebab-case and unique under `~/pm-projects/`.
2. Create `~/pm-projects/<slug>/`.
3. Write `00-business-statement.md` with frontmatter and the statement as body.
4. Prompt user: "Is this a GenAI/agentic product? [y/n]". Set `genai_flag` in `.meta.yaml`.
5. Initialize `.meta.yaml` with all 7 stages in `pending` status.
6. Initialize empty `telemetry.jsonl` and `feedback.jsonl`.
7. Log `project_created` event to telemetry.

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
9. Generate output via Claude (model choice: Sonnet default; Opus for stages 03, 06).
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
Output sections: Overview, Goals and non-goals, User stories with acceptance criteria, Functional requirements, Non-functional requirements, Edge cases, Risks.
**GenAI branch:** add sections — Model selection rationale, Prompt/agent architecture, Tool/function inventory, Context window strategy, Fallback behavior, Output validation strategy.

### Stage 04 — Design Spec
Output sections: Information architecture, Key user flows (narrative), Design principles, Component inventory, Typography, Color tokens, Spacing tokens, Iconography, Accessibility notes.
**Companion HTML:** rendered from these tokens.

### Stage 05 — Prototype Brief
Output sections: What to prototype, Fidelity level, Screens to include, Interactions to demonstrate, Questions the prototype should answer, Non-goals for prototype.
**Companion HTML:** mockup of described screens, Tailwind, static.

### Stage 06 — QA Plan (use Opus)
Output sections: Test strategy, Functional test cases, Non-functional tests, Edge cases, Acceptance criteria.
**GenAI branch:** add sections — Eval dataset spec, Golden set construction, LLM-as-judge rubric, Hallucination test plan, Latency/cost SLOs, Red-team scenarios, Prompt regression suite.

### Stage 07 — Metrics Plan
Output sections: North star metric, Input metrics, Output metrics, Guardrail metrics, Instrumentation plan, Dashboard sketch, Review cadence.
**GenAI branch:** add sections — Quality metrics (accuracy, faithfulness), Cost per invocation, Token usage, Model performance drift detection.

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
2. Verify GenAI branch activation works for stages 03, 06, 07.
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
- **Claude model selection:**
  - Default: Sonnet (latest available)
  - Opus for stages 03 (PRD) and 06 (QA Plan)
  - Configurable in skill frontmatter, not hardcoded
- **Embeddings model:** `sentence-transformers/all-MiniLM-L6-v2` — small, local, no API cost.
- **Timestamps:** ISO 8601 UTC throughout.
- **UUIDs:** uuid4.
- **Hash algorithm:** SHA-256.
- **Line endings:** LF only. Normalize on read for hash stability.

---

## 13. Out of scope for v1

Do not build these. If a design decision seems to require one, flag and stop.

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
- [ ] GenAI flag triggers correct branching in stages 03, 06, 07.
- [ ] Session-end hook flushes telemetry on Claude Code exit.

---

## 16. Notes on building this system *using* Claude Code

The executor (Claude Code) will be building PM-OS, which itself is a Claude Code extension. To avoid confusion:

- Keep build artifacts in a clean working directory separate from any `~/.claude/skills/` symlinks.
- Test the install flow on a clean directory before claiming Phase 1 done.
- Do not install PM-OS skills into the same Claude Code session that's building them — restart sessions between build and test.

---

End of specification.
