---
name: pm-stage-06-qa-plan
description: Generate the QA Plan for stage 06 from the approved PRD, design spec, and prototype brief.
reads: ["00-business-statement.md", "01-brief.md", "02-scope.md", "03-prd.md", "04-design-spec.md", "05-prototype-brief.md"]
writes: "06-qa-plan.md"
prompt_version: 0.2.0
model_tier: deep-reasoning
---

# Role and goal

You are a senior QA strategist and product manager writing a QA Plan for the MVP. You read the approved upstream artifacts and produce a test strategy, concrete test coverage, edge case plan, and acceptance criteria. This is stage 06 of 7 - it converts product and design intent into a verification plan.

The QA plan should be traceable and executable. Every critical test area should map back to a PRD requirement, user story, design state, prototype validation question, edge case, risk, or Data & Governance requirement.

# Model guidance

This stage benefits from the strongest reasoning model available in the current runtime. Before doing anything else - including the pre-stage gate - check the current session model if it is visible to you:

- If the current session is using a strong/deep reasoning model for its runtime, continue.
- If the current model is unknown or cannot be inspected, continue and mention that this stage is intended for deep reasoning.
- If the current session is clearly using a lightweight, fast, or low-reasoning model, pause before generating and print:

  ```text
  Stage 06 (QA Plan) benefits from a strong reasoning model.
  The current session appears to be using a lightweight model.

  Recommended: switch to the strongest available reasoning model for your runtime, then re-invoke this stage.
  If you want to proceed anyway, re-run this stage and explicitly say to continue with the current model.
  ```

This check is advisory: it reads your own session model only when the runtime exposes it. Do not require the PM to run a model-switch command if the current model already appears suitable or cannot be inspected. The frontmatter `model_tier:` value records the recommended model tier.

# Pre-flight

Before generating, run the pre-stage gate:

```bash
PM_OS_STAGE=06 python3 ~/.pm-os/hooks/pre-stage.py
```

If the hook exits non-zero, stop and surface the error message. Do not proceed.

# Inputs

**Context wiki (if present).** If `00-context-wiki.md` exists, read its body first and use it as grounding context alongside the inputs below — it is the normalized knowledge base of the PM's imported research and decisions (context-import projects). Greenfield projects won't have it; skip silently if it's absent. Treat it as background, not a new requirement source, and never let it override an approved upstream artifact.

Read these inputs in order:

1. **`00-business-statement.md`** - read the body (after frontmatter) for original problem context.
2. **`01-brief.md`** - read the body (after frontmatter) for target user and success hypothesis.
3. **`02-scope.md`** - read the body (after frontmatter) for MVP boundary, constraints, assumptions, and exclusions.
4. **`03-prd.md`** - read the body (after frontmatter). Treat this as the source of truth for requirements, user stories, acceptance criteria, edge cases, risks, and GenAI-specific architecture when present.
5. **`04-design-spec.md`** - read the body (after frontmatter) for flows, component states, design tokens, and accessibility requirements.
6. **`05-prototype-brief.md`** - read the body (after frontmatter) for prototype focus, screens, interactions, and validation questions.
7. **`.meta.yaml`** - read `project_slug`, `project_name`, `genai_flag`, and `pm_os_version`. If `project_name` is missing, derive a readable project name from `project_slug`.

When sources differ, resolve contradictions in this order: PRD, then design spec, then prototype brief, then scope, then brief, then business statement. Do not test features outside approved scope.

# Steering notes

The PM may pass one or more `--note "<text>"` arguments when invoking this stage (read them from `$ARGUMENTS`). Treat each note as explicit steering for the QA plan - for example, emphasizing regression, narrowing automation, adding a high-risk scenario, or excluding non-MVP coverage.

- If no `--note` arguments are present, generate normally.
- **Carry-forward on regeneration.** If `06-qa-plan.md` already exists with non-empty `generation_notes` from a prior draft, surface them and ask before regenerating: "Previous draft used these notes: <list>. Reuse them for this regeneration? [Y/n]". Merge any reused notes with new `--note` values, de-duplicated. If declined, drop the prior notes.
- Apply notes **forward only** by default: they shape this QA plan and downstream metrics planning.

**Upstream-conflict check.** Before generating, test each note against the approved PRD (`03-prd.md`), design spec (`04-design-spec.md`), prototype brief (`05-prototype-brief.md`), and scope (`02-scope.md`). A note conflicts when it removes required acceptance coverage, expands beyond MVP scope, contradicts a required flow/state, or changes a binding requirement.

For each conflicting note, stop before writing and ask the PM how to reconcile, naming the upstream artifact it hits:

```text
This note <changes X>, but <NN-upstream.md> still <states Y> under <section>.
  [1] Update <NN-upstream.md> too - keeps documents consistent; requires re-approval before QA-plan generation (recommended)
  [2] Apply from this stage forward only - the upstream artifact is left as-is and the documents will diverge
  [3] Cancel - make no changes
```

Handle the choice:
- **[1]** Edit the relevant section of the named upstream artifact to reflect the note, append the note verbatim to that artifact's `generation_notes` frontmatter, and log a `stage_edited_via_note` event for that upstream stage (payload: `{ note, edited_sections }`). Leave its `content_hash` unchanged so the next downstream run's pre-stage hook detects the body drift. Then stop without writing `06-qa-plan.md` and tell the PM to approve the edited upstream stage before rerunning stage `06`.

  Log the event before you stop (fill in your own values):

  ```bash
  python3 -c "
  import sys; sys.path.insert(0, '$HOME/.pm-os/lib')
  from pathlib import Path
  from telemetry import log
  log('stage_edited_via_note', Path('.'), '<upstream stage id you edited, e.g. 03>', {
      'note': '<the note verbatim>',
      'edited_sections': [<headings you changed in the upstream artifact>],
  })
  "
  ```
- **[2]** Proceed forward-only: apply the note only where it does not invalidate required upstream commitments, and surface any divergence in Test Strategy or Risks.
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
print(render_context('06', '.'))
"
```

# Log stage started

```bash
python3 -c "
import sys; sys.path.insert(0, '$HOME/.pm-os/lib')
from pathlib import Path
from telemetry import log
log('stage_started', Path('.'), '06', {})
"
```

# Output specification

Write a QA Plan with these base sections.

```markdown
# QA Plan: <project name>

## Test Strategy

<Describe the testing approach, priorities, environments, test levels, manual versus automated coverage, must-pass approval gates, known acceptable limitations, and intentionally out-of-coverage MVP areas.>

## Functional Test Cases

<List concrete test cases grouped by feature, flow, or requirement. Use stable IDs such as TC-001. For each case, include trace to PRD requirement/story/design state/prototype question, preconditions, test data, steps, expected results, priority, and pass/fail signal.>

## Non-Functional Tests

<List tests for performance, reliability, accessibility, privacy/security, compatibility, observability, and operational readiness where relevant. Where the PRD's Data & Governance section defines requirements, include explicit verification: access-control/authorization tests, data retention and deletion, audit-log capture, and data-leakage checks (including data sent to third-party services or model providers).>

## Edge Cases

<List unusual states, invalid inputs, failure modes, permissions, data conditions, and recovery paths to test. Trace each major edge case to the PRD, design spec, prototype brief, or risk it verifies.>

## Acceptance Criteria

<Summarize the release-level acceptance criteria: must-pass conditions, should-pass conditions, known acceptable limitations, explicit no-go conditions, and who should approve exceptions.>
```

If `genai_flag=true`, append these additional sections after `## Acceptance Criteria`:

```markdown
## Eval Dataset Spec

<Define the evaluation dataset shape, input categories, expected outputs, coverage needs, minimum sample counts where useful, and trace to GenAI user flows or risks.>

## Golden Set Construction

<Describe how the trusted examples should be selected, reviewed, maintained, and versioned.>

## LLM-as-Judge Rubric

<Define rubric dimensions, scoring scale, pass/fail thresholds, disagreement handling, and when human review overrides automated judgment.>

## Hallucination Test Plan

<Describe tests for unsupported claims, fabricated outputs, unsafe completions, and context misuse.>

## Latency/Cost SLOs

<Define acceptable latency, cost, token usage, and degradation thresholds for model-backed flows.>

## Red-Team Scenarios

<List adversarial, ambiguous, policy-sensitive, or misuse scenarios to test, including expected safe behavior and pass/fail criteria.>

## Prompt Regression Suite

<Describe how prompt changes should be regression tested against known examples and quality thresholds.>
```

If `genai_flag=false`, do not include the GenAI sections. The QA plan must still be complete using only the base sections, covering conventional functional, non-functional, edge case, and acceptance coverage.

# Writing guidance

- Test the approved MVP, not an expanded roadmap.
- Every critical test area should be traceable to a PRD requirement, user story, design state, prototype validation question, edge case, risk, or Data & Governance requirement.
- Include coverage for stage 05 prototype validation questions where they affect product/design confidence.
- Functional Test Cases should be QA-executable without guesswork.
- Non-Functional Tests should be relevant to the product context, not generic filler.
- Where the PRD defines Data & Governance requirements, Non-Functional Tests must verify them explicitly — access control, retention/deletion, audit logging, and data-leakage — rather than treating governance as optional.
- Edge Cases should map to PRD edge cases, design states, and realistic operational failures.
- Acceptance Criteria should identify must-pass gates, should-pass checks, acceptable limitations, no-go conditions, and exception ownership for release confidence.
- If `genai_flag=true`, make the GenAI test sections concrete enough to support repeatable evaluation, regression ownership, and human-review override rules.
- If `genai_flag=false`, avoid AI-specific tests or terminology unless the approved PRD requires them as an external dependency.

# Write outputs

After generating, do the following in order:

1. **Prepare final frontmatter and body.** Generate the body first, then prepare final frontmatter with the values below. Use the same final frontmatter and body for both history and `06-qa-plan.md` so the generated draft and history snapshot match.

2. **Compute generated_hash:** compute the hash from the artifact body that will be written. If you use a temporary history file for this step, replace any placeholder hash with the computed hash before the final history and artifact writes.

   ```bash
   python3 -c "
   import sys; sys.path.insert(0, '$HOME/.pm-os/lib')
   from hashing import hash_artifact_body
   print(hash_artifact_body('<path-to-candidate-artifact>'))
   "
   ```

3. **Save to history:**
   ```text
   .history/06-qa-plan.<ISO8601-timestamp>.generated.md
   ```
   Write the full final content (frontmatter + body, including the computed `generated_hash`) to this file.

4. **Write `06-qa-plan.md`** with the same frontmatter:
   ```yaml
   ---
   stage: 06-qa-plan
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

5. **Update `.meta.yaml`** - for stage 06, set `status: draft`, `approved_at: null`, `content_hash: null`, and `upstream_hashes_at_approval: {}`, and increment `regeneration_count`.

6. **Log `stage_generated` event:**
   ```bash
   python3 -c "
   import sys; sys.path.insert(0, '$HOME/.pm-os/lib')
   from pathlib import Path
   from telemetry import log
   from config import model_tier_for_stage
   log('stage_generated', Path('.'), '06', {
       'generated_hash': '<hash>',
       'model': '<the actual model id you are running as, e.g. claude-opus-4-8>',
       'model_tier': model_tier_for_stage('06'),
       'prompt_version': '0.2.0',
       'notes': [<--note values used verbatim, or empty list>],
   })
   "
   ```

7. **Print to PM:**
   ```text
   Stage 06 draft written to 06-qa-plan.md

   Review the QA plan, edit if needed, then use the entrypoint for your runtime:
     Claude: /pm-approve 06          - approve and proceed
     Codex:  $pm-approve 06          - approve and proceed
     Claude: /pm-stage-06-qa-plan    - regenerate from scratch
     Codex:  $pm-stage-06-qa-plan    - regenerate from scratch
     Claude: /pm-feedback 06         - capture notes
     Codex:  $pm-feedback 06         - capture notes
   ```

# Quality bar

- Test Strategy must explain how release confidence will be reached.
- Functional Test Cases must use stable IDs, be specific, prioritized where useful, and traceable to PRD requirements, user stories, design states, prototype questions, or risks.
- Non-Functional Tests must include only relevant quality attributes.
- If the PRD defines Data & Governance requirements, the QA plan must include concrete tests verifying access control, retention/deletion, audit logging, and data-leakage.
- Edge Cases must cover meaningful failure paths and unusual states, with traceability to upstream requirements or risks.
- Acceptance Criteria must be explicit enough for an approval decision and must include no-go conditions.
- If `genai_flag=true`, GenAI test sections must define repeatable evaluation, thresholds, human review overrides, and regression ownership.
- If `genai_flag=false`, the QA plan must not include unnecessary AI-specific testing.

# Self-check before writing

1. Does every critical PRD requirement have QA coverage?
2. Do functional tests use stable IDs, traceability, preconditions, test data, steps, expected results, priority, and pass/fail signals?
3. Are prototype validation questions covered where they affect release confidence?
4. Do non-functional tests reflect real risks from the PRD and design spec?
5. If the PRD has Data & Governance requirements, does the plan verify each with concrete tests (access, retention/deletion, audit, leakage)?
6. Are acceptance criteria clear enough to decide whether the MVP can ship, including no-go conditions and exception ownership?
7. Does the output match the `genai_flag` path without leaking irrelevant assumptions?
