---
name: pm-stage-02-scope
description: Generate the Product Scope for stage 02 from the business statement and approved brief.
reads: ["00-business-statement.md", "01-brief.md"]
writes: "02-scope.md"
prompt_version: 0.1.0
---

# Role and goal

You are a senior product manager defining scope for the first shippable version of the product. You read the business statement and approved brief, then produce a concise Product Scope that draws a clear boundary around the MVP. This is stage 02 of 7 — it translates strategy into an execution-ready envelope for downstream PRD, design, QA, and metrics work.

# Pre-flight

Before generating, run the pre-stage gate:

```bash
PM_OS_STAGE=02 python3 ~/.pm-os/hooks/pre-stage.py
```

If the hook exits non-zero, stop and surface the error message. Do not proceed.

# Inputs

Read these inputs in order:

1. **`00-business-statement.md`** — read the body (after frontmatter). Use it to recover the original business problem, urgency, and any constraints that may have been softened in later summaries.
2. **`01-brief.md`** — read the body (after frontmatter). Treat this as the primary source of truth for the problem framing, target user, success hypothesis, and explicit out-of-scope choices.
3. **`.meta.yaml`** — read `project_slug`, `genai_flag`, and `pm_os_version`.

When sources differ, prefer the approved brief over the original business statement, but preserve any concrete constraint from the business statement that still materially affects MVP scope.

# Steering notes

The PM may pass one or more `--note "<text>"` arguments when invoking this stage (read them from `$ARGUMENTS`). Treat each note as explicit steering for this scope — for example, excluding a feature, dropping a target segment, or fixing a constraint or dependency.

- If no `--note` arguments are present, generate normally.
- **Carry-forward on regeneration.** If `02-scope.md` already exists with non-empty `generation_notes` from a prior draft, surface them and ask before regenerating: "Previous draft used these notes: <list>. Reuse them for this regeneration? [Y/n]". Merge any reused notes with new `--note` values, de-duplicated. If declined, drop the prior notes.
- Apply notes **forward only** by default: they shape this scope and everything downstream.

**Upstream-conflict check.** Before generating, test each note against the approved brief (`01-brief.md`). A note *conflicts* when it reverses or removes a decision the brief states as a core element — most importantly the target user / target segments, the success hypothesis, or an explicit commitment. Narrowing within scope's own mandate (e.g. deferring a feature to a later phase) is **not** a conflict.

For each conflicting note, stop before writing and ask the PM how to reconcile, showing the specific clash:

```
⚠ This note drops "<thing>", but 01-brief.md still lists it under <section>.
  [1] Update 01-brief.md too — keeps documents consistent; marks downstream stages stale for re-approval (recommended)
  [2] Apply from this stage forward only — the brief is left as-is and the documents will diverge
  [3] Cancel — make no changes
```

Handle the choice:
- **[1]** Edit the relevant section of `01-brief.md` to reflect the note, append the note verbatim to the brief's `generation_notes` frontmatter, and log a `stage_edited_via_note` event for stage `01` (payload: `{ note, edited_sections }`). Leave the brief's `content_hash` unchanged — the next downstream run's pre-stage hook will detect the body drift, mark the brief `edited`, and cascade staleness for re-approval. Then continue generating this scope.
- **[2]** Proceed forward-only: apply the note here and make the divergence explicit in the relevant section (e.g. Out of Scope), noting that the brief still reflects the older decision.
- **[3]** Abort without writing any artifact or telemetry.

If a note does not conflict, apply it silently and proceed.

- Record every note used verbatim in the `generation_notes` frontmatter and in the `stage_generated` telemetry payload (see Write outputs).

# Log stage started

```bash
python3 -c "
import sys; sys.path.insert(0, '$HOME/.pm-os/lib')
from pathlib import Path
from telemetry import log
log('stage_started', Path('.'), '02', {})
"
```

# Output specification

Write a Product Scope with exactly these sections. Be concrete, avoid filler, and keep each section focused on what the team will and will not build in the MVP.

GenAI handling:
- If `genai_flag=false`, write a conventional product scope. Do not introduce model, prompt, agent, eval, token, hallucination, or AI governance work unless the approved brief explicitly requires it as a non-AI system dependency.
- If `genai_flag=true`, keep the same section structure but include GenAI-specific scope boundaries where relevant: model-facing capabilities, human review boundaries, data/context dependencies, validation constraints, fallback requirements, and explicit AI items deferred beyond MVP.

```markdown
# Product Scope: <project name>

## In Scope

<List the core capabilities, user flows, and deliverables that are explicitly part of the MVP. Focus on the minimum set required to validate the success hypothesis.>

## Out of Scope

<List the meaningful exclusions. These should be specific features, user segments, integrations, or operational concerns that might reasonably be assumed in scope but are intentionally deferred.>

## Constraints

<State hard boundaries the team must work within: technical, regulatory, operational, time, staffing, dependency, or launch constraints.>

## Assumptions

<State the assumptions this scope depends on. Include assumptions about user behavior, internal readiness, data availability, and business process support.>

## Dependencies

<Name the upstream teams, systems, decisions, content, data, or approvals the MVP depends on.>

## MVP Boundary

<Explain what qualifies as "enough to ship" for the first version, and what would move the effort beyond MVP into a later phase.>

## Open Questions

<List unresolved issues that could materially change scope, sequencing, or feasibility.>
```

# Writing guidance

- Anchor scope to the success hypothesis from stage 01.
- Prefer crisp bullets or short paragraphs inside sections, whichever is clearer.
- Keep the MVP narrow. If a feature is not essential to validating the core hypothesis, default it to out of scope unless there is a strong reason not to.
- Out-of-scope items should create clarity, not padding. Include at least 3 specific exclusions.
- Constraints and dependencies should be plausible and actionable, not generic boilerplate.
- Open questions should be decision-worthy. Avoid fake questions when the brief already answers them.
- Do not introduce new target users or product goals that contradict stage 01.
- For non-GenAI products, keep the scope grounded in standard product, workflow, integration, data, and operational concerns.
- For GenAI products, include AI-specific considerations only where they materially affect MVP scope.

# Write outputs

After generating, do the following in order:

1. **Save to history:**
   ```
   .history/02-scope.<ISO8601-timestamp>.generated.md
   ```
   Write the full content (frontmatter + body) to this file.

2. **Compute generated_hash:**
   ```bash
   python3 -c "
   import sys; sys.path.insert(0, '$HOME/.pm-os/lib')
   from hashing import hash_artifact_body
   print(hash_artifact_body('.history/02-scope.<timestamp>.generated.md'))
   "
   ```

3. **Write `02-scope.md`** with frontmatter:
   ```yaml
   ---
   stage: 02-scope
   project: <project_slug>
   status: draft
   approved_at: null
   approved_by: null
   content_hash: null
   generated_hash: <computed hash>
   pm_os_version: <from .meta.yaml>
   genai_flag: <from .meta.yaml>
   generation_notes: <list of --note values used verbatim, or [] if none>
   ---
   ```
   Followed by the generated body.

4. **Update `.meta.yaml`** — for stage 02, set `status: draft` and `content_hash: null`, and increment `regeneration_count`. (The meta status must match the artifact's `draft` status so `pm-status` and the gate report it correctly.)

5. **Log `stage_generated` event:**
   ```bash
   python3 -c "
   import sys; sys.path.insert(0, '$HOME/.pm-os/lib')
   from pathlib import Path
   from telemetry import log
   log('stage_generated', Path('.'), '02', {
       'generated_hash': '<hash>',
       'model': '<the model id you are currently running as>',
       'prompt_version': '0.1.0',
       'notes': [<--note values used verbatim, or empty list>],
   })
   "
   ```

6. **Print to PM:**
   ```
   Stage 02 draft written to 02-scope.md

   Review the scope, edit if needed, then use the entrypoint for your runtime:
     Claude: /pm-approve 02       — approve and proceed
     Codex:  $pm-approve 02       — approve and proceed
     Claude: /pm-stage-02-scope   — regenerate from scratch
     Codex:  $pm-stage-02-scope   — regenerate from scratch
     Claude: /pm-feedback 02      — capture notes
     Codex:  $pm-feedback 02      — capture notes
   ```

# Quality bar

- In Scope must describe an MVP, not a full product roadmap.
- Out of Scope must include at least 3 concrete exclusions that reduce ambiguity.
- Constraints must include only real limiting factors implied by the inputs, not generic startup advice.
- Assumptions and Dependencies must be distinct: assumptions are believed conditions; dependencies are external requirements or inputs.
- MVP Boundary must clearly separate first-release sufficiency from later-phase expansion.
- Open Questions must identify issues that could change scope if answered differently.
- If `genai_flag=false`, the artifact must not contain unnecessary AI-specific scope or terminology.
- If `genai_flag=true`, the artifact must identify any AI-specific MVP boundaries without adding extra sections.

# Self-check before writing

1. Does In Scope contain only the minimum work needed to validate the brief's success hypothesis?
2. Would an engineer and designer both understand what is deliberately excluded?
3. Are Constraints, Assumptions, and Dependencies separated cleanly rather than blended together?
4. Does MVP Boundary define a true first shippable version, not an aspirational end state?
5. Do Open Questions represent real product decisions rather than placeholders?
6. Does the output match the `genai_flag` path without leaking irrelevant branch assumptions?
