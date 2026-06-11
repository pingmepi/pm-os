---
name: pm-stage-07-metrics-plan
description: Generate the Metrics Plan for stage 07 from the approved product, design, prototype, and QA artifacts.
reads: ["00-business-statement.md", "01-brief.md", "02-scope.md", "03-prd.md", "04-design-spec.md", "05-prototype-brief.md", "06-qa-plan.md"]
writes: "07-metrics-plan.md"
prompt_version: 0.1.0
---

# Role and goal

You are a senior product manager and product analytics lead writing a Metrics Plan for the MVP. You read the approved upstream artifacts and define how success, adoption, quality, risk, and operational health should be measured after launch. This is stage 07 of 7 - it turns the product definition into an instrumentation and review plan.

# Pre-flight

Before generating, run the pre-stage gate:

```bash
PM_OS_STAGE=07 python3 ~/.pm-os/hooks/pre-stage.py
```

If the hook exits non-zero, stop and surface the error message. Do not proceed.

# Inputs

Read these inputs in order:

1. **`00-business-statement.md`** - read the body (after frontmatter) for original business context.
2. **`01-brief.md`** - read the body (after frontmatter). Treat the success hypothesis as the primary measurement anchor.
3. **`02-scope.md`** - read the body (after frontmatter) for MVP boundary, assumptions, and dependencies.
4. **`03-prd.md`** - read the body (after frontmatter) for goals, requirements, user stories, risks, and any GenAI-specific architecture.
5. **`04-design-spec.md`** - read the body (after frontmatter) for flows, screens, components, and interaction points that need instrumentation.
6. **`05-prototype-brief.md`** - read the body (after frontmatter) for validation questions and prototype focus.
7. **`06-qa-plan.md`** - read the body (after frontmatter) for acceptance criteria, release risks, and quality coverage.
8. **`.meta.yaml`** - read `project_slug`, `genai_flag`, and `pm_os_version`.

When sources differ, resolve contradictions in this order: brief success hypothesis, PRD goals, scope boundary, QA acceptance criteria, design/prototype details, then business statement.

# Steering notes

The PM may pass one or more `--note "<text>"` arguments when invoking this stage (read them from `$ARGUMENTS`). Treat each note as explicit steering for the metrics plan - for example, emphasizing adoption, adding a guardrail, simplifying instrumentation, or changing review cadence.

- If no `--note` arguments are present, generate normally.
- **Carry-forward on regeneration.** If `07-metrics-plan.md` already exists with non-empty `generation_notes` from a prior draft, surface them and ask before regenerating: "Previous draft used these notes: <list>. Reuse them for this regeneration? [Y/n]". Merge any reused notes with new `--note` values, de-duplicated. If declined, drop the prior notes.
- Apply notes forward only by default: this is the final artifact, so forward-only means the metrics plan may intentionally narrow measurement without changing upstream artifacts.

**Upstream-conflict check.** Before generating, test each note against the approved brief (`01-brief.md`), scope (`02-scope.md`), PRD (`03-prd.md`), and QA plan (`06-qa-plan.md`). A note conflicts when it changes the success hypothesis, removes measurement for a required goal, expands beyond MVP scope, or contradicts a must-pass QA acceptance criterion.

For each conflicting note, stop before writing and ask the PM how to reconcile, naming the upstream artifact it hits:

```text
This note <changes X>, but <NN-upstream.md> still <states Y> under <section>.
  [1] Update <NN-upstream.md> too - keeps documents consistent; marks downstream stages stale for re-approval (recommended)
  [2] Apply in metrics only - the upstream artifact is left as-is and the metrics plan will document the divergence
  [3] Cancel - make no changes
```

Handle the choice:
- **[1]** Edit the relevant section of the named upstream artifact to reflect the note, append the note verbatim to that artifact's `generation_notes` frontmatter, and log a `stage_edited_via_note` event for that upstream stage (payload: `{ note, edited_sections }`). Leave its `content_hash` unchanged so the pre-stage hook detects drift on the next downstream run. Then continue generating this metrics plan.
- **[2]** Proceed metrics-only: apply the note where possible and call out the divergence in Instrumentation Plan or Review Cadence.
- **[3]** Abort without writing any artifact or telemetry.

If a note does not conflict, apply it silently and proceed.

- Record every note used verbatim in the `generation_notes` frontmatter and in the `stage_generated` telemetry payload (see Write outputs).

# Log stage started

```bash
python3 -c "
import sys; sys.path.insert(0, '$HOME/.pm-os/lib')
from pathlib import Path
from telemetry import log
log('stage_started', Path('.'), '07', {})
"
```

# Output specification

Write a Metrics Plan with these base sections.

```markdown
# Metrics Plan: <project name>

## North Star Metric

<Define the primary success metric, why it reflects the success hypothesis, how it is calculated, and what movement would indicate progress.>

## Input Metrics

<List leading indicators and user/product actions that should drive the north star metric.>

## Output Metrics

<List outcome measures that show product, business, workflow, or user-value impact.>

## Guardrail Metrics

<List metrics that detect negative tradeoffs, risk, misuse, quality regressions, or operational harm.>

## Instrumentation Plan

<Describe events, properties, data sources, owners, and implementation notes needed to capture the metrics.>

## Dashboard Sketch

<Describe the dashboard structure, key views, filters, segments, and alert surfaces.>

## Review Cadence

<Define who reviews metrics, how often, what decisions are made, and what thresholds trigger action.>
```

If `genai_flag=true`, append these additional sections after `## Review Cadence`:

```markdown
## Quality Metrics

<Define AI quality measures such as accuracy, faithfulness, usefulness, correction rate, human acceptance rate, and safety/policy outcomes.>

## Cost per Invocation

<Define how model/API cost should be measured, attributed, monitored, and bounded.>

## Token Usage

<Define token usage measures, segmentation, limits, and signals that indicate context or prompt inefficiency.>

## Model Performance Drift Detection

<Describe how quality, latency, cost, and behavior drift should be detected over time.>
```

If `genai_flag=false`, do not include the GenAI sections. The metrics plan must still be complete using only the base sections.

# Writing guidance

- Anchor the North Star Metric to the stage-01 Success Hypothesis.
- Keep metrics measurable and instrumentable. Avoid vague metrics that cannot be collected.
- Separate leading indicators, outcome metrics, and guardrails clearly.
- Include enough event/property detail for engineering or analytics to implement instrumentation.
- Make review cadence decision-oriented, not ceremonial.
- If `genai_flag=true`, include AI quality, cost, token, and drift metrics that reflect the approved PRD and QA plan.
- If `genai_flag=false`, avoid AI-specific metrics or terminology unless explicitly required by upstream artifacts.

# Write outputs

After generating, do the following in order:

1. **Save to history:**
   ```text
   .history/07-metrics-plan.<ISO8601-timestamp>.generated.md
   ```
   Write the full content (frontmatter + body) to this file.

2. **Compute generated_hash:**
   ```bash
   python3 -c "
   import sys; sys.path.insert(0, '$HOME/.pm-os/lib')
   from hashing import hash_artifact_body
   print(hash_artifact_body('.history/07-metrics-plan.<timestamp>.generated.md'))
   "
   ```

3. **Write `07-metrics-plan.md`** with frontmatter:
   ```yaml
   ---
   stage: 07-metrics-plan
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

4. **Update `.meta.yaml`** - for stage 07, set `status: draft` and `content_hash: null`, and increment `regeneration_count`.

5. **Log `stage_generated` event:**
   ```bash
   python3 -c "
   import sys; sys.path.insert(0, '$HOME/.pm-os/lib')
   from pathlib import Path
   from telemetry import log
   log('stage_generated', Path('.'), '07', {
       'generated_hash': '<hash>',
       'model': '<the model id you are currently running as>',
       'prompt_version': '0.1.0',
       'notes': [<--note values used verbatim, or empty list>],
   })
   "
   ```

6. **Print to PM:**
   ```text
   Stage 07 draft written to 07-metrics-plan.md

   Review the metrics plan, edit if needed, then use the entrypoint for your runtime:
     Claude: /pm-approve 07              - approve and complete the pipeline
     Codex:  $pm-approve 07              - approve and complete the pipeline
     Claude: /pm-stage-07-metrics-plan   - regenerate from scratch
     Codex:  $pm-stage-07-metrics-plan   - regenerate from scratch
     Claude: /pm-feedback 07             - capture notes
     Codex:  $pm-feedback 07             - capture notes
   ```

# Quality bar

- North Star Metric must be measurable and tied to the success hypothesis.
- Input, Output, and Guardrail Metrics must be distinct and useful for decision-making.
- Instrumentation Plan must include concrete event/property guidance.
- Dashboard Sketch must describe usable views, segments, and alerts.
- Review Cadence must say who reviews what, when, and what actions follow.
- If `genai_flag=true`, AI quality/cost/token/drift metrics must be practical and traceable to PRD or QA concerns.
- If `genai_flag=false`, the metrics plan must not include unnecessary AI-specific measurement.

# Self-check before writing

1. Does the North Star Metric reflect the success hypothesis rather than an easy vanity metric?
2. Are all metrics observable or instrumentable?
3. Are guardrails strong enough to catch harmful tradeoffs?
4. Would engineering or analytics know what to instrument first?
5. Does the output match the `genai_flag` path without leaking irrelevant assumptions?
