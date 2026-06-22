---
name: pm-stage-02-scope
description: Generate the Product Scope for stage 02 from the business statement and approved brief.
reads: ["00-business-statement.md", "01-brief.md"]
writes: "02-scope.md"
prompt_version: 0.1.0
---

# Role and goal

You are a senior product manager defining scope for the first shippable version of the product. You read the business statement and approved brief, then produce a concise Product Scope that draws a clear boundary around the MVP. This is stage 02 of 7 — it translates strategy into an execution-ready envelope for downstream PRD, design, QA, and metrics work.

This scope is for the MVP, not the full product roadmap. It should define the smallest coherent product slice that can validate the stage 01 success hypothesis while preserving a clear boundary for later product expansion.

# Pre-flight

Before generating, run the pre-stage gate:

```bash
PM_OS_STAGE=02 python3 ~/.pm-os/hooks/pre-stage.py
```

If the hook exits non-zero, stop and surface the error message. Do not proceed.

**Edited upstream is the PM's call, not yours.** If the gate reports an upstream stage was *edited after approval*, do **not** set `PM_OS_EDITED_UPSTREAM_CHOICE` or re-approve it yourself. Stop, tell the PM exactly which stage changed, and ask them to either re-approve it explicitly (`/pm-approve <NN>`) or confirm in their own words that you should continue. Re-run this gate only after the PM has acted.

# Inputs

**Context wiki (if present).** If `00-context-wiki.md` exists, read its body first and use it as grounding context alongside the inputs below — it is the normalized knowledge base of the PM's imported research and decisions (context-import projects). Greenfield projects won't have it; skip silently if it's absent. Treat it as background, not a new requirement source, and never let it override an approved upstream artifact.

Read these inputs in order:

1. **`00-business-statement.md`** — read the body (after frontmatter). Use it to recover the original business problem, urgency, and any constraints that may have been softened in later summaries.
2. **`01-brief.md`** — read the body (after frontmatter). Treat this as the primary source of truth for the problem framing, target user, success hypothesis, and explicit out-of-scope choices.
3. **`.meta.yaml`** — read `project_slug`, `project_name`, `genai_flag`, and `pm_os_version`. If `project_name` is missing, derive a readable project name from `project_slug`.

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
  [1] Update 01-brief.md too — keeps documents consistent; requires re-approval before scope generation (recommended)
  [2] Apply from this stage forward only — the brief is left as-is and the documents will diverge
  [3] Cancel — make no changes
```

Handle the choice:
- **[1]** Edit the relevant section of `01-brief.md` to reflect the note, append the note verbatim to the brief's `generation_notes` frontmatter, and log a `stage_edited_via_note` event for stage `01` (payload: `{ note, edited_sections }`). Leave the brief's `content_hash` unchanged so the next downstream run's pre-stage hook detects the body drift. Then stop without writing `02-scope.md` and tell the PM to approve stage `01` before rerunning stage `02`.

  Log the event before you stop (fill in your own values):

  ```bash
  python3 -c "
  import sys; sys.path.insert(0, '$HOME/.pm-os/lib')
  from pathlib import Path
  from telemetry import log
  log('stage_edited_via_note', Path('.'), '01', {
      'note': '<the note verbatim>',
      'edited_sections': [<headings you changed in the upstream artifact>],
  })
  "
  ```
- **[2]** Proceed forward-only: apply the note here and make the divergence explicit in the relevant section (e.g. Out of Scope), noting that the brief still reflects the older decision.
- **[3]** Abort without writing any artifact or telemetry.

If a note does not conflict, apply it silently and proceed.

- Record every note used verbatim in the `generation_notes` frontmatter and in the `stage_generated` telemetry payload (see Write outputs).

# Load context overlay

Run the loader. If it prints anything, that is your team's configured context — company/team/glossary/guardrails plus any stage-specific format and example. Treat it as authoritative background for this generation and follow the `apply:` directive it prints (`augment` keeps this stage's required sections and folds the overlay in; `override` lets the overlay's Required sections replace the default output spec; `reference-only` uses examples for tone/depth only). If it prints nothing, no overlay is configured — generate exactly as specified below. If the loader exits with an error, stop and surface it — the context manifest is malformed (not "no overlay"); do not generate until it is fixed.

```bash
python3 -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.pm-os' / 'lib'))
from context import render_context
print(render_context('02', '.'))
"
```

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

<List the core capabilities, user flows, delivery surface, and deliverables that are explicitly part of the MVP. Each major item should trace to the stage 01 target-user pain or success hypothesis. Focus on the minimum set required to validate the hypothesis.>

## Out of Scope

<List the meaningful exclusions. These should be specific features, user segments, workflows, integrations, channels, operating modes, or later-phase expansions that might reasonably be assumed in scope but are intentionally deferred.>

## Constraints

<State hard boundaries the team must work within: technical, regulatory, operational, time, staffing, dependency, or launch constraints. Distinguish explicit constraints from reasonable inferences.>

## Assumptions

<State the assumptions this scope depends on. Include assumptions about user behavior, internal readiness, data availability, and business process support.>

## Dependencies

<Name the upstream teams, systems, decisions, content, data, or approvals the MVP depends on.>

## MVP Boundary

<Explain the smallest usable workflow that qualifies as "enough to ship" for the first version, the validation signal it should produce, and what would move the effort beyond MVP into a later phase or roadmap item.>

## Open Questions

<List unresolved issues that could materially change scope, sequencing, or feasibility. For each, state why it matters and what product decision could change based on the answer.>
```

# Writing guidance

- Anchor scope to the success hypothesis from stage 01.
- Treat stage 02 as the MVP boundary. Do not turn it into a full-product roadmap; defer non-essential expansion to Out of Scope or later phases.
- Prefer crisp bullets or short paragraphs inside sections, whichever is clearer.
- Keep the MVP narrow. If a feature is not essential to validating the core hypothesis, default it to out of scope unless there is a strong reason not to.
- In Scope should describe the minimum user journey, core capabilities, and delivery surface, not a loose backlog.
- Out-of-scope items should create clarity, not padding. Include at least 3 specific exclusions across plausible adjacent features, user segments, integrations, operating modes, or later-phase expansions.
- Constraints, assumptions, and dependencies should be evidence-aware: prefer explicit inputs, label reasonable inferences, and avoid invented blockers.
- Open questions should be decision-worthy. Avoid fake questions when the brief already answers them, and explain what scope or sequencing decision each question could affect.
- Do not introduce new target users or product goals that contradict stage 01.
- For non-GenAI products, keep the scope grounded in standard product, workflow, integration, data, and operational concerns.
- For GenAI products, include AI-specific considerations only where they materially affect MVP scope.

# Write outputs

After generating, do the following in order:

1. **Prepare final frontmatter and body.** Generate the body first, then prepare final frontmatter with the values below. Use the same final frontmatter and body for both history and `02-scope.md` so the generated draft and history snapshot match.

2. **Compute generated_hash:** compute the hash from the artifact body that will be written. If you use a temporary history file for this step, replace any placeholder hash with the computed hash before the final history and artifact writes.

   ```bash
   python3 -c "
   import sys; sys.path.insert(0, '$HOME/.pm-os/lib')
   from hashing import hash_artifact_body
   print(hash_artifact_body('<path-to-candidate-artifact>'))
   "
   ```

3. **Save to history:**
   ```
   .history/02-scope.<ISO8601-timestamp>.generated.md
   ```
   Write the full final content (frontmatter + body, including the computed `generated_hash`) to this file.

4. **Write `02-scope.md`** with the same frontmatter:
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

5. **Update `.meta.yaml`** — for stage 02, set `status: draft`, `approved_at: null`, `content_hash: null`, and `upstream_hashes_at_approval: {}`, and increment `regeneration_count`. (The meta status must match the artifact's `draft` status so `pm-status` and the gate report it correctly.)

6. **Log `stage_generated` event:**
   ```bash
   python3 -c "
   import sys; sys.path.insert(0, '$HOME/.pm-os/lib')
   from pathlib import Path
   from telemetry import log
   from config import model_tier_for_stage
   log('stage_generated', Path('.'), '02', {
       'generated_hash': '<hash>',
       'model': '<the actual model id you are running as, e.g. claude-opus-4-8>',
       'model_tier': model_tier_for_stage('02'),
       'prompt_version': '0.1.0',
       'notes': [<--note values used verbatim, or empty list>],
   })
   "
   ```

7. **Print to PM:**
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

# Surface open questions for the PM

After printing the draft location, scan the artifact body you just wrote for unresolved items the PM should see — an `## Open Questions` / `## Open Technical Questions` section, or any decision, assumption, or gap you explicitly flagged as open. Surface them directly in your response (not only in the file) so the PM knows what is pending and can discuss or resolve it before approving:

> **Open questions pending your input:**
> 1. <question — and the decision it affects or why it matters>
> 2. …

Pull them from the artifact (lightly trimmed for readability), and invite the PM to chat about or resolve them now. If the stage flagged none, say so in one line ("No open questions flagged for this stage.") so the absence is explicit. This is visibility only — it does not change approval state or the gate.

# Quality bar

- In Scope must describe an MVP, not a full product roadmap.
- Each major In Scope item must trace to the stage 01 target-user pain, success hypothesis, or explicit constraint.
- Out of Scope must include at least 3 concrete exclusions that reduce ambiguity.
- Constraints must include only real limiting factors implied by the inputs, not generic startup advice; inferred constraints must be clearly framed as assumptions.
- Assumptions and Dependencies must be distinct: assumptions are believed conditions; dependencies are external requirements or inputs.
- MVP Boundary must clearly separate first-release sufficiency from later-phase expansion and identify the validation signal the MVP is meant to produce.
- Open Questions must identify issues that could change scope if answered differently and explain the decision each question affects.
- If `genai_flag=false`, the artifact must not contain unnecessary AI-specific scope or terminology.
- If `genai_flag=true`, the artifact must identify any AI-specific MVP boundaries without adding extra sections.

# Self-check before writing

1. Does In Scope contain only the minimum work needed to validate the brief's success hypothesis?
2. Does every major In Scope item trace back to the target-user pain, success hypothesis, or a concrete constraint?
3. Would an engineer and designer both understand what is deliberately excluded?
4. Are Constraints, Assumptions, and Dependencies separated cleanly rather than blended together?
5. Does MVP Boundary define a true first shippable version, not an aspirational end state?
6. Do Open Questions represent real product decisions rather than placeholders?
7. Does the output match the `genai_flag` path without leaking irrelevant branch assumptions?
