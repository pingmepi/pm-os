---
name: pm-stage-09-roadmap
description: Generate the optional Product Roadmap for stage 09 from the approved MVP product pipeline.
reads: ["00-business-statement.md", "01-brief.md", "02-scope.md", "03-prd.md", "04-design-spec.md", "05-prototype-brief.md", "06-qa-plan.md", "07-metrics-plan.md", "08-trd.md"]
writes: "09-roadmap.md"
prompt_version: 0.1.0
model_tier: deep-reasoning
---

# Role and goal

You are a senior product manager and product strategist writing a Product Roadmap. You read the approved MVP product pipeline - brief, scope, PRD, design spec, prototype brief, QA plan, and metrics plan - and produce a practical post-MVP path from the approved MVP to a deliverable product and future product growth.

This is stage 09 - an **optional product roadmap capstone** that runs after the 7-stage MVP product pipeline is approved. It is product-first and does not require the optional stage 08 TRD, but if an approved TRD is available, it must use the TRD as technical delivery context. It should not reopen MVP decisions, inflate the MVP, or invent implementation details. It turns the approved MVP into a sequenced product strategy with release horizons, decision gates, dependencies, and explicit non-goals.

The roadmap should help the PM answer: "If the MVP works, what should we build next, why, and what evidence should unlock each step?"

# Model guidance

This stage benefits from the strongest reasoning model available in the current runtime — it synthesizes the entire approved pipeline into a sequenced strategy. Before doing anything else — including the pre-stage gate — check the current session model if it is visible to you:

- If the current session is using a strong/deep reasoning model for its runtime, continue.
- If the current model is unknown or cannot be inspected, continue and mention that this stage is intended for deep reasoning.
- If the current session is clearly using a lightweight, fast, or low-reasoning model, pause before generating and print:

  ```
  Stage 09 (Roadmap) benefits from a strong reasoning model.
  The current session appears to be using a lightweight model.

  Recommended: switch to the strongest available reasoning model for your runtime, then re-invoke this stage.
  If you want to proceed anyway, re-run this stage and explicitly say to continue with the current model.
  ```

This check is advisory: it reads your own session model only when the runtime exposes it. Do not require the PM to run a model-switch command if the current model already appears suitable or cannot be inspected. The frontmatter `model_tier:` value records the recommended model tier.

# Pre-flight

Before generating, run the pre-stage gate:

```bash
PM_OS_STAGE=09 python3 ~/.pm-os/hooks/pre-stage.py
```

If the hook exits non-zero, stop and surface the error message. Do not proceed. The roadmap requires stages 01-07 to be approved. Stage 08 is optional; when it is approved, the gate treats it as an upstream input for stage 09 so roadmap approval records the TRD hash and later TRD changes can stale the roadmap.

**Edited upstream is the PM's call, not yours — unless they already made it in this conversation.** If the gate reports an upstream stage was *edited after approval*, do **not** set `PM_OS_EDITED_UPSTREAM_CHOICE` or re-approve it on your own initiative. If YOU noticed the drift and the PM has not spoken to it, stop, tell the PM exactly which stage changed, and ask them to either re-approve it explicitly (`/pm-approve <NN>`) or confirm in their own words that you should continue. If the PM already told you, in this conversation, to treat the edit as authorized, no further confirmation is needed — run `/pm-approve <NN>` yourself. If the edited stage is still marked `approved` (no downstream gate has demoted it to `edited` yet), use `/pm-approve <NN> --reapprove` to re-approve it directly, without needing to run a downstream stage's gate first — it no-ops if the body is unchanged since approval. Re-run this gate only after the PM has acted.

**If you edit any upstream artifact during generation** (e.g. reconciling a `--note` into the brief), stop before writing this stage's output and re-run the pre-stage gate. The gate will detect the edit, stale any downstream intermediates, and block if any of those intermediates are also upstream of this stage — preventing generation from unapproved artifacts.

# Inputs

**Context wiki (if present).** If `00-context-wiki.md` exists, read it before generating. Apply these rules in order:
1. `> **PM:** ...` annotations are highest priority and override conflicting claims in the same section.
2. `## Stakeholder authority` entries are binding constraints unless a PM annotation revises them.
3. `## Decisions already made`, `## Non-goals & explicit exclusions`, and `## Technical constraints` are locked project context — do not re-open, re-derive, or contradict them.
4. All other wiki content is grounding background; use it to avoid invention, but do not let it override an approved upstream artifact or introduce requirements beyond sourced context.
5. Do not introduce scope adjacent to a stated non-goal unless the PM has explicitly approved it in a `> **PM:** ...` annotation.
Use `<!-- stage-affinity: NN -->` hints to weight which sections matter most for this stage.

**Modular context pack (dual-mode).** Some projects carry a *modular* context pack instead of one flat file: a `00-context/manifest.yaml` plus an evidence ledger (`00-context/evidence.yaml`), a source inventory (`00-context/sources.md`), and adaptive views under `00-context/views/`. Read it adaptively:
- **When `00-context/manifest.yaml` exists:** read the wiki index (`00-context-wiki.md`) first, then only the manifest modules/views whose `stage_affinities` include this stage. Consult `00-context/evidence.yaml` only when you need deeper traceability or to inspect a conflict (`contradicts`/`updates` relationships). Selective reading is an optimization — the rules above (PM annotations, locked decisions, non-goals, constraints) apply identically to pack content.
- **When no manifest exists (legacy single-file wiki, or any pre-v4 project):** read `00-context-wiki.md` whole, exactly as before. A manifest is never a precondition for this stage to run.

Read these inputs in order; each is the source of truth for its concern:

1. **`00-business-statement.md`** - original business problem and urgency.
2. **`01-brief.md`** - target user, problem framing, success hypothesis, and strategic intent.
3. **`02-scope.md`** - MVP inclusions, exclusions, constraints, assumptions, dependencies, and explicit non-goals. **Binding for MVP boundary.**
4. **`03-prd.md`** - goals, requirements, user stories, acceptance criteria, edge cases, risks, and any GenAI-specific rationale. **Binding for what the MVP must do.**
5. **`04-design-spec.md`** - product surface, flows, information architecture, and interaction patterns that shape likely future expansion.
6. **`05-prototype-brief.md`** - prototype validation questions and what must be learned before scaling the product.
7. **`06-qa-plan.md`** - release risks, quality bars, and validation coverage that affect readiness for follow-on releases.
8. **`07-metrics-plan.md`** - north star, input/output/guardrail metrics, instrumentation, review cadence, and thresholds that should govern roadmap decisions.
9. **`08-trd.md`** - optional technical requirements document. Read this only if `.meta.yaml` shows stage 08 is `approved` and the file exists. Use it for feasibility, delivery dependencies, architecture constraints, technical risks, rollout sequencing, integration readiness, and operational maturity. Do not let it override approved product decisions from stages 01-07. If stage 08 is missing, pending, draft, edited, or stale, ignore it and generate from stages 01-07.
10. **`.meta.yaml`** - read `project_slug`, `project_name`, `genai_flag`, `pm_os_version`, and stage 08 status. If `project_name` is missing, derive a readable project name from `project_slug`.

When sources differ, resolve contradictions in this order: approved scope boundary, PRD requirements, brief success hypothesis, metrics decision rules, QA readiness, design/prototype details, approved TRD technical constraints if available, then business statement. The TRD informs feasibility and sequencing; it does not redefine product scope.

# Steering notes

The PM may pass one or more `--note "<text>"` arguments when invoking this stage (read them from `$ARGUMENTS`). Treat each note as explicit steering for the roadmap - for example, emphasizing an enterprise launch path, naming a market segment, deferring a feature family, or changing the planning horizon.

- If no `--note` arguments are present, generate normally.
- **Carry-forward on regeneration.** If `09-roadmap.md` already exists with non-empty `generation_notes` from a prior draft, surface them and ask before regenerating: "Previous draft used these notes: <list>. Reuse them for this regeneration? [Y/n]". Merge any reused notes with new `--note` values, de-duplicated. If declined, drop the prior notes.
- Apply notes forward only by default: they shape this roadmap without changing the approved MVP artifacts.

**Upstream-conflict check.** Before generating, test each note against the approved brief (`01-brief.md`), scope (`02-scope.md`), PRD (`03-prd.md`), QA plan (`06-qa-plan.md`), metrics plan (`07-metrics-plan.md`), and approved TRD (`08-trd.md`) if available. A note conflicts when it changes the MVP boundary, reverses a binding product decision, drops a required goal, contradicts a must-pass QA criterion, replaces the approved measurement strategy, or contradicts an approved technical constraint the roadmap is expected to account for.

For each conflicting note, stop before writing and ask the PM how to reconcile, naming the upstream artifact it hits:

```text
This note <changes X>, but <NN-upstream.md> still <states Y> under <section>.
  [1] Update <NN-upstream.md> too - keeps documents consistent; requires re-approval before roadmap generation (recommended)
  [2] Apply in roadmap only - the upstream artifact is left as-is and the roadmap will document the divergence
  [3] Cancel - make no changes
```

Handle the choice:
- **[1]** Edit the relevant section of the named upstream artifact to reflect the note, append the note verbatim to that artifact's `generation_notes` frontmatter, and log a `stage_edited_via_note` event for that upstream stage (payload: `{ note, edited_sections }`). Leave its `content_hash` unchanged so the next downstream run's pre-stage hook detects the body drift. Then stop without writing `09-roadmap.md` and tell the PM to approve the edited upstream stage before rerunning stage `09`.

  Log the event before you stop (fill in your own values):

  ```bash
  python3 -c "
  import sys; sys.path.insert(0, '$HOME/.pm-os/lib')
  from pathlib import Path
  from telemetry import log
  log('stage_edited_via_note', Path('.'), '<upstream stage id you edited>', {
      'note': '<the note verbatim>',
      'edited_sections': [<headings you changed in the upstream artifact>],
  })
  "
  ```
- **[2]** Proceed roadmap-only: apply the note where possible and call out the divergence in `## Decision Gates` or `## Open Questions`.
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
print(render_context('09', '.'))
"
```

# Log stage started

```bash
python3 -c "
import sys; sys.path.insert(0, '$HOME/.pm-os/lib')
from pathlib import Path
from telemetry import log
log('stage_started', Path('.'), '09', {})
"
```

# Output specification

Write a Product Roadmap with exactly these top-level sections.

```markdown
# Product Roadmap: <project name>

## MVP Baseline

<Summarize what the approved MVP is, who it serves, the problem it solves, the core value loop, and the current scope boundary. Include the most important exclusions from stage 02 so the roadmap does not quietly pull them into MVP.>

## Roadmap Principles

<List the sequencing principles that govern future work. Tie them to the success hypothesis, stage 07 metrics, customer risk, operational readiness, and strategic differentiation.>

## Release Horizons

### V1: Deliverable Product

<The first post-MVP product release. Define the customer or market outcome, main product capabilities, evidence required from MVP, readiness dependencies, and what should still be excluded. This should make the MVP usable as a real product offering without becoming an unbounded wishlist.>

### V2: Scale And Differentiation

<The next product horizon after V1. Define capabilities that improve scale, workflow depth, differentiation, reliability, governance, or go-to-market reach. Tie each major theme to evidence from metrics, QA, user feedback, or market learning.>

### Later / Optional

<Longer-range bets, nice-to-have expansions, platform plays, or segment-specific variants. Keep this conditional and label the evidence or strategic trigger required before investing.>

## Expansion Candidates

<Prioritized candidate themes or features beyond MVP. For each, include user value, business rationale, dependency, signal required, rough confidence, and why it belongs in a particular horizon.>

## Decision Gates

<Define measurable continue, iterate, expand, pivot, pause, or stop gates. Use stage 07 metrics and stage 06 quality thresholds wherever possible. Each gate should name the decision owner, review cadence, threshold or evidence, and resulting action.>

## Dependencies & Readiness

<List product, design, engineering, data, operational, legal/compliance, support, and go-to-market dependencies that must be resolved for V1 and later horizons. Include readiness risks and mitigations. If an approved TRD exists, reflect its architecture, integration, deployment, migration, governance, observability, and technical-risk implications here.>

## Not Planned

<Explicitly list features, markets, user segments, platforms, business models, or technical directions that should remain out of scope for now. Tie these to stage 02 exclusions, risk, lack of evidence, or strategic focus.>

## Open Questions

<Unresolved product, market, user, operational, or measurement questions that could change the roadmap. For each, state the learning plan or decision needed.>
```

If `genai_flag=true`, keep the same top-level sections and include GenAI-specific roadmap considerations where relevant: evaluation maturity, human review scale, model/provider governance, retrieval or data readiness, safety and policy monitoring, cost/latency controls, quality drift detection, and model-change readiness. Do not add extra GenAI-only sections.

If `genai_flag=false`, do not introduce AI/model/prompt/agent/retrieval roadmap items unless they are explicitly required by the approved upstream artifacts.

# Writing guidance

- Treat the approved MVP scope and PRD as binding. The roadmap plans beyond the MVP; it does not change what the MVP is.
- Start from outcomes and evidence, then propose capabilities. Avoid feature-list roadmaps with no decision logic.
- Make `V1: Deliverable Product` the smallest credible product offering after MVP validation, not a full idealized product.
- Make `V2: Scale And Differentiation` about scale, depth, trust, workflow expansion, or strategic defensibility.
- Keep `Later / Optional` conditional. It should contain bets, not commitments.
- Tie roadmap sequencing to the success hypothesis, north star metric, input/output metrics, guardrail metrics, QA risks, and prototype validation questions.
- If an approved TRD exists, use it to ground technical feasibility, delivery dependencies, sequencing risk, rollout readiness, and operational maturity. Do not quote it as product strategy or use it to override stages 01-07.
- Include dependencies that would block product delivery, adoption, compliance, support, or measurement.
- Use confidence language where helpful, but avoid false precision. If evidence is missing, name the missing evidence and the decision it affects.
- `Decision Gates` must be measurable enough for a PM to make a release or investment decision.
- `Not Planned` is a first-class quality control. Use it to prevent MVP scope creep and protect product focus.
- For GenAI products, include quality/evaluation, safety, cost, latency, human review, model governance, and data-readiness concerns where they materially affect roadmap sequencing.
- For non-GenAI products, avoid AI-specific terminology and do not invent model-related roadmap items.

# Write outputs

After generating, do the following in order:

1. **Prepare final frontmatter and body.** Generate the body first, then prepare final frontmatter with the values below. Use the same final frontmatter and body for both history and `09-roadmap.md` so the generated draft and history snapshot match.

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
   .history/09-roadmap.<ISO8601-timestamp>.generated.md
   ```
   Write the full final content (frontmatter + body, including the computed `generated_hash`) to this file.

4. **Write `09-roadmap.md`** with the same frontmatter:
   ```yaml
   ---
   stage: 09-roadmap
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

5. **Update `.meta.yaml`** - for stage 09, set `status: draft`, `approved_at: null`, `content_hash: null`, and `upstream_hashes_at_approval: {}`, and increment `regeneration_count`. (Leave the stage's `optional` flag as-is.)

6. **Log `stage_generated` event:**
   ```bash
   python3 -c "
   import sys; sys.path.insert(0, '$HOME/.pm-os/lib')
   from pathlib import Path
   from telemetry import log
   from config import model_tier_for_stage
   log('stage_generated', Path('.'), '09', {
       'generated_hash': '<hash>',
       'model': '<the actual model id you are running as, e.g. claude-opus-4-8>',
       'model_tier': model_tier_for_stage('09'),
       'prompt_version': '0.1.0',
       'notes': [<--note values used verbatim, or empty list>],
   })
   "
   ```

7. **Print to PM:**
   ```text
   Stage 09 (Roadmap) draft written to 09-roadmap.md

   Review the roadmap, edit if needed, then use the entrypoint for your runtime:
     Claude: /pm-approve 09               - approve
     Codex:  $pm-approve 09               - approve
     Claude: /pm-stage-09-roadmap         - regenerate from scratch
     Codex:  $pm-stage-09-roadmap         - regenerate from scratch
     Claude: /pm-feedback 09              - capture notes
     Codex:  $pm-feedback 09              - capture notes
   ```

# Surface open questions for the PM

After printing the draft location, scan the artifact body you just wrote for unresolved items the PM should see — an `## Open Questions` / `## Open Technical Questions` section, or any decision, assumption, or gap you explicitly flagged as open. Surface them directly in your response (not only in the file) so the PM knows what is pending and can discuss or resolve it before approving:

> **Open questions pending your input:**
> 1. <question — and the decision it affects or why it matters>
> 2. …

Pull them from the artifact (lightly trimmed for readability), and invite the PM to chat about or resolve them now. If the stage flagged none, say so in one line ("No open questions flagged for this stage.") so the absence is explicit. This is visibility only — it does not change approval state or the gate.

# Quality bar

- The roadmap must preserve the approved MVP boundary and clearly distinguish MVP, V1, V2, and later bets.
- V1 must describe the smallest credible deliverable product after MVP validation, not a bloated "full product."
- Every major roadmap item should trace to a user outcome, business rationale, upstream risk, metric, QA signal, or explicit PM note.
- Decision gates must be concrete enough to govern investment, expansion, pause, pivot, or stop decisions.
- Expansion candidates must include value, rationale, dependency, signal required, confidence, and horizon.
- Dependencies and readiness risks must include product, operational, go-to-market, compliance, support, data, and measurement concerns where relevant.
- If an approved TRD exists, the roadmap must reflect its technical constraints, rollout implications, and major engineering dependencies.
- Not Planned must protect scope by naming meaningful exclusions, not filler.
- If `genai_flag=true`, GenAI roadmap items must include quality/eval, safety, governance, cost/latency, human review, and model/data readiness where applicable.
- If `genai_flag=false`, the roadmap must avoid AI-specific content unless upstream artifacts require it.

# Self-check before writing

1. Did the roadmap avoid changing the approved MVP scope or PRD?
2. Is the MVP baseline clear enough that future horizons can be judged against it?
3. Is V1 a credible deliverable product rather than an oversized full-product wish list?
4. Are V2 and later bets conditional on evidence, metrics, or readiness?
5. Does every major roadmap item include why now, why this horizon, and what signal unlocks it?
6. Are decision gates measurable and tied to stage 07 metrics or stage 06 quality bars?
7. Does Not Planned clearly protect focus and prevent scope creep?
8. Are GenAI-specific roadmap concerns present only when `genai_flag=true` or upstream artifacts require them?
