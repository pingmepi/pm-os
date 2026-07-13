# Generated Document Formats

**PM-OS version:** 1.0.8 · **Status:** reference (mirrors what the skills on `main` actually generate)

This is the canonical catalog of the format of **every document PM-OS generates** — each section with a one-line note on what it contains, the shared frontmatter they all carry, and the supporting machine-written files. Each format is sourced from the `# Output specification` block of the stage's `SKILL.md` (or the context templates for the 00-group), so it reflects the code on `main`, not the aspirational build spec.

Artifacts are plain Markdown with a YAML frontmatter block. Stages are gated (`pending → draft → approved`); the format below describes the **body** each stage writes. GenAI-only sections appear **only** when the project's `genai_flag` is `true`.

---

## Table of Contents

- [Shared: artifact frontmatter](#shared-artifact-frontmatter)
- [Stage map at a glance](#stage-map-at-a-glance)
- **Context / pre-stage group (00)**
  - [00 — Business Statement](#00--business-statement)
  - [00c — Codebase Understanding](#00c--codebase-understanding)
  - [00w — Context Wiki (pack)](#00w--context-wiki-pack)
  - [00u — Context Understanding](#00u--context-understanding)
- **Core pipeline (01–07)**
  - [01 — Product Brief](#01--product-brief)
  - [02 — Product Scope](#02--product-scope)
  - [03 — Product Requirements Document (PRD)](#03--product-requirements-document-prd)
  - [04 — Design Spec](#04--design-spec)
  - [05 — Prototype Brief](#05--prototype-brief)
  - [06 — QA Plan](#06--qa-plan)
  - [07 — Metrics Plan](#07--metrics-plan)
- **Capstones (optional)**
  - [08 — Technical Requirements Document (TRD)](#08--technical-requirements-document-trd)
  - [09 — Product Roadmap](#09--product-roadmap)
- [Supporting generated files](#supporting-generated-files)

---

## Shared: artifact frontmatter

Every stage artifact opens with the same YAML frontmatter block (from `templates/artifact-frontmatter.yaml.j2`). It is written/updated mechanically by the scaffold and approval scripts, not by the generating agent. The `content_hash` is computed over the **body only** (everything after the closing `---`), so frontmatter edits never trigger drift.

```yaml
---
stage: <NN>              # e.g. "01"
project: <project_slug>
status: pending | draft | approved | edited | stale
approved_at: <ISO timestamp or null>
approved_by: <pm_user or null>
content_hash: <sha of body, or null before approval>
generated_hash: <sha of the originally generated body>
pm_os_version: <e.g. 1.0.8>
genai_flag: true | false
generation_notes: <optional free text>
---
```

The body under the frontmatter follows the per-stage structure below.

---

## Stage map at a glance

| ID | Artifact file | Skill | Kind |
|----|---------------|-------|------|
| 00 | `00-business-statement.md` | `pm-new` | Freeform seed (gated) |
| 00c | `00-codebase-understanding.md` | `pm-context-scan-codebase` | Enhancement mode only |
| 00w | `00-context-wiki.md` (+ `00-context/`) | `pm-context-import` | Context import only |
| 00u | `00-context-understanding.md` | `pm-context-import` | Context import only |
| 01 | `01-brief.md` | `pm-stage-01-brief` | Core |
| 02 | `02-scope.md` | `pm-stage-02-scope` | Core |
| 03 | `03-prd.md` | `pm-stage-03-prd` | Core |
| 04 | `04-design-spec.md` (+ HTML) | `pm-stage-04-design-spec` | Core |
| 05 | `05-prototype-brief.md` (+ HTML) | `pm-stage-05-prototype-brief` | Core |
| 06 | `06-qa-plan.md` | `pm-stage-06-qa-plan` | Core |
| 07 | `07-metrics-plan.md` | `pm-stage-07-metrics-plan` | Core |
| 08 | `08-trd.md` | `pm-stage-08-trd` | Optional capstone |
| 09 | `09-roadmap.md` | `pm-stage-09-roadmap` | Optional capstone |

The 00-group is conditional: `00` always exists; `00c` appears only for enhancement projects (a codebase was scanned); `00w`/`00u` appear only when the project was created via `/pm-context-import`.

---

## 00 — Business Statement

**File:** `00-business-statement.md` · **Skill:** `pm-new`

The seed of the project and a normal gated stage. It has **no prescribed section structure** — the body is the PM's one-line-to-paragraph problem statement, written verbatim into the file. The PM reviews and approves it (`/pm-approve 00`) before stage 01 can run. If created without a statement, a placeholder is written for the PM to fill in.

---

## 00c — Codebase Understanding

**File:** `00-codebase-understanding.md` · **Skill:** `pm-context-scan-codebase` (enhancement mode only)

Structured read-only scan of an existing codebase. Uses these `##` headers **in this order**; each carries a `<!-- stage-affinity -->` comment (preserve exactly) that downstream stages use to decide what to read.

- **`## TL;DR`** — One paragraph: what the product does, who it serves, the stack it runs on, and the overall scale/maturity signal.
- **`## Current features & flows`** `<!-- 01 02 03 -->` — User-facing capabilities with entry-point file paths; what a user can *do*, not how it's implemented.
- **`## Architecture & modules`** `<!-- 08 03 -->` — Module/package-level structure and each part's role, with paths (short diagram/table if it helps).
- **`## Data model`** `<!-- 08 03 -->` — Key entities, their relationships, and the storage layer, citing schema/model files.
- **`## Tech stack & dependencies`** `<!-- 08 06 -->` — Languages, frameworks, key libraries, runtime, and infra (versions where known).
- **`## Design language`** `<!-- 04 05 -->` — Design system, token files, component library, or UI framework — or an explicit "not found".
- **`## Integration points`** `<!-- 08 03 -->` — External APIs, third-party services, auth providers, queues, webhooks, and how each is used.
- **`## Known constraints & tech debt`** `<!-- 02 08 -->` — TODOs, FIXMEs, deprecated patterns, duplication, and architectural warnings found in the code.

---

## 00w — Context Wiki (pack)

**Files:** `00-context-wiki.md` + `00-context/` · **Skill:** `pm-context-import`

The context wiki is a **modular pack**, not a single page. It comprises three hashed members: the wiki **index**, an **evidence ledger**, and a **source inventory**. (`pack-manifest` then assembles `00-context/manifest.yaml`.)

### `00-context-wiki.md` — navigational index

A concise, skimmable index, using these `##` headings **in this order**:

- **`## TL;DR`** — The takeaway up front: what the product is, the core problem, who it's for, and the decisions already locked. A reader should grasp the project from this section alone.
- **`## Problem & context`** — The problem space and why-now.
- **`## Users & needs`** — Who the users are and their jobs/pains.
- **`## Non-goals & explicit exclusions`** `<!-- 01 02 -->` — Things explicitly ruled out per the sources; each bullet tagged `[hard]`/`[inferred]` and carrying a `src_NNN`.
- **`## Success indicators`** `<!-- 01 07 -->` — KPIs, OKRs, and launch criteria from the sources (marked `⚠️` if none are measurable).
- **`## Decisions already made`** `<!-- 01 02 03 -->` — Scope calls, constraints, and commitments the PM has locked, so downstream stages don't relitigate them.
- **`## Technical constraints`** `<!-- 03 04 06 08 -->` — Hard/soft platform or integration constraints, each tagged `[hard]`/`[soft/preferred]`.
- **`## Stakeholder authority`** `<!-- 01 02 03 -->` — Decisions attributed to a named authority, as a `Decision | Authority | Source | Binding?` table (treated as binding unless a PM annotation overrides).
- **`## Concepts & glossary`** — Normalized domain terms used across sources.
- **`## Open questions & uncertainties`** — Gaps, conflicts, and thin evidence (also where the self-lint findings land).
- **`## Source map`** — A one-line pointer per source (`src_NNN → file → type`), linking to the full `sources.md` inventory.

Style rules: tag every factual claim with its `src_NNN`; prefix synthesized/inferred lines with `_Interpretation:_`; mark conflicts/thin evidence inline with `⚠️` and surface them under Open questions; open each content-bearing section with a `> Confidence: High / Medium / Low — <reason>` line. `> **PM:** ...` blockquotes are PM-authored overrides (highest priority, never machine-generated, part of the body hash).

### `00-context/evidence.yaml` — evidence ledger

Machine-readable backbone: every load-bearing claim and cross-source insight with stable IDs (`clm-001`, `ins-001` — reused across regenerations, only appended).

```yaml
schema_version: 1
claims:
  - id: clm-001
    statement: "<a single sourced factual claim>"
    sources: [src_001]
    confidence: high | medium | low
    stage_affinity: ["01", "02"]
    relationships:                 # optional
      - type: supports | contradicts | updates | depends_on
        target: clm-002
insights:
  - id: ins-001
    statement: "<an inference drawn across claims>"
    derived_from: [clm-001, clm-003]
    confidence: medium
    stage_affinity: ["03"]
```

Every claim cites ≥1 `src_NNN`; insights cite claim IDs. A `contradicts` relationship must also appear under the index's Open questions.

### `00-context/sources.md` — source inventory

Human-readable provenance table, one row per `src_NNN`:

```markdown
| Source | File | Type | Modality | Extraction quality | Authority | Strengths | Limitations |
|---|---|---|---|---|---|---|---|
| src_001 | research.pdf | research | text-pdf | Clean | secondary | broad market view | dated 2024 |
```

Extraction quality is `Clean / Lossy / Unknown`; anything `Lossy` downgrades the confidence of claims sourced from it.

---

## 00u — Context Understanding

**File:** `00-context-understanding.md` · **Skill:** `pm-context-import`

Human-facing synthesis the PM approves before the pipeline is seeded. Uses **exactly these six sections**:

- **`1. What I understood`** — Prose summary plus a structured block: Problem / Primary users / Key locked decisions / Non-goals (inferred ones flagged `[inferred]`).
- **`2. Source trust table`** — `Source | Type | Registered as | Extraction quality | Reliability | Strengths | Weaknesses | Role` — one row per source.
- **`3. Assumption register`** — For each freshly-generated or lossily-backfilled stage: `Stage | Section | Assumption I will use | Based on | Confidence | PM review needed?`.
- **`4. Conflict resolution block`** — One block per `⚠️` conflict that affects a stage, each ending with a `Your call: ___` line (or "No conflicts found" if none).
- **`5. Coverage map`** — Per stage 01–07: `✅` provided / `✅` faithful backfill / `⚠️` lossy backfill / `🔄` generated fresh / `⛔` not adoptable, naming what's lost or the top assumption.
- **`6. What happens on approval`** — Which stages adopt as `imported`, which as approved backfills, and which remain `draft` (named explicitly so the PM isn't surprised).

---

## 01 — Product Brief

**File:** `01-brief.md` · **Skill:** `pm-stage-01-brief`

Exactly these sections, each 2–5 sentences unless more is warranted:

- **`## Problem`** — The user pain, the current workaround/state and why it's insufficient, who feels it, and the business/user consequence of leaving it unsolved.
- **`## Target User`** — The primary first user segment: role/context, current behavior, motivation, and why they're the right initial focus (no "everyone who…" users).
- **`## Why Now`** — The concrete urgency or readiness signal (market, regulatory, capability, operational, competitive), or the best inferred timing driver if none is explicit.
- **`## Success Hypothesis`** — The observable outcome that changes if it works, framed as a measurable "we'll know it's working when… within…", plus the core assumption it validates.
- **`## Out of Scope`** — Adjacent segments, workflows/features, integrations/channels, or responsibilities intentionally excluded from this initiative.
- **`## GenAI Flag Rationale`** — Why GenAI/agentic approaches are relevant (if `genai_flag=true`), otherwise "Not applicable — this is not a GenAI product."

In enhancement mode (00c exists or `project_type: enhancement`), the brief covers the **new capability only** — "Problem" = the current-product gap, "Why Now" = why this change now.

---

## 02 — Product Scope

**File:** `02-scope.md` · **Skill:** `pm-stage-02-scope`

Exactly these sections (same structure whether or not `genai_flag` is set; GenAI scope boundaries fold into the existing sections):

- **`## In Scope`** — The core capabilities, user flows, delivery surface, and deliverables in the MVP, each tracing to a stage-01 pain or success hypothesis.
- **`## Out of Scope`** — ≥3 specific exclusions (features, segments, integrations, operating modes, later phases) that might be assumed in scope but are intentionally deferred.
- **`## Constraints`** — Hard boundaries the team must work within: technical, regulatory, operational, time, staffing, dependency, or launch.
- **`## Assumptions`** — What this scope depends on: user behavior, internal readiness, data availability, and process support.
- **`## Dependencies`** — Upstream teams, systems, decisions, content, data, or approvals the MVP relies on.
- **`## MVP Boundary`** — The smallest usable workflow that qualifies as "enough to ship," the validation signal it produces, and what would move work beyond MVP.
- **`## Open Questions`** — Unresolved issues that could materially change scope, sequencing, or feasibility — with why each matters and the decision it affects.

---

## 03 — Product Requirements Document (PRD)

**File:** `03-prd.md` · **Skill:** `pm-stage-03-prd`

Base sections:

- **`## Overview`** — The product, the user problem, the MVP boundary, and what this PRD covers.
- **`## Goals and Non-Goals`** — The outcomes this release targets, followed by the explicit non-goals for this version.
- **`## User Journeys`** — End-to-end journeys (`### UJ-###`): primary user, trigger, goal, preconditions, happy path, failure paths, completion signal, and traceability to US/FR.
- **`## User Stories with Acceptance Criteria`** — Prioritized stories (`US-###`): actor, trigger, happy path, key edge case, scope/journey trace, and QA-testable acceptance criteria. `US-###` are stable traceability handles — only ever appended.
- **`## Functional Requirements`** — Required system behaviors, workflows, states, rules, and integrations (`FR-###`/`REQ-###`), each mapped to a story or scope item.
- **`## Non-Functional Requirements`** — Performance, reliability, security, privacy, accessibility, auditability, maintainability, and operations — with measurable thresholds.
- **`## Data & Governance`** — What data is collected/stored/processed, its sensitivity, owner, retention, access, consent/legal basis, residency/regime, and any third-party or model-provider sharing.
- **`## Journey–Requirement Traceability`** *(recommended)* — Maps every `UJ-###` to its `US-###`/`FR-###`/NFRs and principal success/failure signal.
- **`## Assumptions & Open Decisions`** *(recommended)* — Unresolved decisions/assumptions that affect journeys, requirements, or validation, with owner and consequence.
- **`## Edge Cases`** — Realistic failure modes, unusual states, invalid inputs, permission issues, and data conditions the product must handle.
- **`## Risks`** — The main product, technical, dependency, rollout, adoption, or compliance risks attached to this MVP.

**If `genai_flag=true`,** append after `## Risks`:

- **`## Model Selection Rationale`** — Which model characteristics matter and why they fit, at the product-requirement level.
- **`## Prompt/Agent Architecture`** — The high-level prompting pattern, orchestration flow, agent steps, or decision logic (product view, not implementation).
- **`## Tool/Function Inventory`** — External tools, functions, retrieval systems, or structured actions the product needs.
- **`## Context Window Strategy`** — What context each invocation requires, how it's selected, and how overflow/retrieval is managed.
- **`## Fallback Behavior`** — What the product does when the model is uncertain, fails, times out, or produces low-confidence output.
- **`## Output Validation Strategy`** — How outputs are checked for quality, faithfulness, policy safety, and structure before acceptance.

---

## 04 — Design Spec

**File:** `04-design-spec.md` (+ HTML companion rendered on approval) · **Skill:** `pm-stage-04-design-spec`

Exactly these sections (Markdown only; the HTML companion is generated separately after approval):

- **`## Information Architecture`** — Screen/page inventory, hierarchy, entry points, and navigation rules, each major screen tied to the PRD requirement/story it supports.
- **`## Journey-to-Flow Traceability`** — Maps every PRD `UJ-###` to entry point, screens/overlays, states, happy-path completion, recovery paths, and supporting `US-###`/`FR-###`.
- **`## Key User Flows`** — Step-by-step critical flows: start state, user action, system response, decision/failure branch, completion state, and the requirement satisfied.
- **`## Product UX Guardrails`** — Declares `Interaction model: retrieval-only | generative | mixed | non-AI`, the product mental model, approved vocabulary, prohibited UI patterns, and trust/safety constraints.
- **`## Design Principles`** — The design principles guiding this MVP's UI and interaction decisions.
- **`## Component Inventory`** — Required components: purpose, placement, content/props, validation, and states (default/loading/empty/error/disabled/success/permission-denied), tied to PRD requirements.
- **`## Responsive & Platform Behavior`** *(recommended)* — Platform, viewport, orientation, input-method, low-bandwidth, and responsive behavior (or a single fixed environment stated explicitly).
- **`## UX Content Rules`** *(recommended)* — User-facing terminology, CTA naming, status language, error/recovery copy, and reviewer-only content.
- **`## Typography`** — Text hierarchy, usage guidance, and readability/density constraints.
- **`## Color Tokens`** — Practical color tokens and usage rules for actions, status, surfaces, borders, warnings, and errors.
- **`## Spacing Tokens`** — Spacing scale and layout-density guidance for screens, forms, lists, and panels.
- **`## Iconography`** — Icon usage, required icons, and rules for when icons should/shouldn't appear.
- **`## Accessibility Notes`** — Keyboard navigation, focus order, labels, contrast, error messaging, touch-target size, and screen-reader expectations.

Design tokens must stay parseable for the companion HTML renderer. A GenAI flag alone never justifies generative UI.

---

## 05 — Prototype Brief

**File:** `05-prototype-brief.md` (+ interactive HTML prototype) · **Skill:** `pm-stage-05-prototype-brief`

Exactly these sections. After the brief is written, stage 05 auto-invokes `pm-prototype-html` to produce a working HTML prototype.

- **`## What to Prototype`** — The bounded product slice/journey/behavior and its design/PRD source, plus why this slice is the right one to prototype first.
- **`## Fidelity Level`** — The appropriate fidelity (wireframe, clickable mid-fi, polished mockup, static HTML) and why.
- **`## Prototype Audience & Modes`** — Participant mode (the unbiased default experience) vs reviewer mode (facilitator surface holding journey IDs, research questions, build metadata).
- **`## Screens to Include`** — Screens/modals/panels/empty/error states, each with purpose, primary content, controls, states, and design/PRD reference *(bulleted — the renderer extracts list items)*.
- **`## Interactions to Demonstrate`** — Interactions/transitions/state changes, each naming start state, user action, system response, resulting state, and source *(bulleted — renderer extracts)*.
- **`## Prototype Data & Scenarios`** *(recommended)* — Realistic, safe sample data and task scenarios per participant/journey; prohibited sensitive/misleading content.
- **`## Questions the Prototype Should Answer`** — Product/usability/workflow/feasibility questions, each mapped to a screen/interaction and the evidence that answers it *(bulleted)*.
- **`## Validation Plan`** — Participants, tasks/scenarios, comparator/baseline, evidence and measures, decision thresholds, facilitator guidance, and bias/priming risks.
- **`## Known Limitations`** *(recommended)* — What the prototype can't validly test (simulated behavior, missing integrations, fidelity/timing limits).
- **`## Non-Goals for Prototype`** — Deferred flows, implementation details, and non-MVP capabilities intentionally excluded.

---

## 06 — QA Plan

**File:** `06-qa-plan.md` · **Skill:** `pm-stage-06-qa-plan`

Base sections:

- **`## Test Strategy`** — Testing approach, priorities, environments, test levels, manual vs automated coverage, must-pass gates, accepted limitations, and intentionally out-of-coverage areas.
- **`## Functional Test Cases`** — Concrete cases (`TC-###`) grouped by feature/flow, each citing the `US-###`/`FR-###`/`REQ-###` it covers, with preconditions, test data, steps, expected results, priority, and pass/fail signal.
- **`## Non-Functional Tests`** — Performance, reliability, accessibility, security/privacy, compatibility, and observability tests, including explicit Data & Governance verification (access control, retention/deletion, audit logging, data leakage).
- **`## Edge Cases`** — Unusual states, invalid inputs, failure modes, permissions, data conditions, and recovery paths, each traced to a PRD/design/prototype/risk item.
- **`## Acceptance Criteria`** — Release-level must-pass and should-pass conditions, accepted limitations, explicit no-go conditions, and who approves exceptions.
- **`## Requirement-Test Traceability`** *(recommended)* — Maps each PRD requirement id to the `TC-###`s covering it and flags gaps; the human mirror of the generated `.traceability.yaml`.

**If `genai_flag=true`,** append after `## Acceptance Criteria`:

- **`## Eval Dataset Spec`** — Dataset shape, input categories, expected outputs, coverage needs, and sample counts, traced to GenAI flows/risks.
- **`## Golden Set Construction`** — How trusted examples are selected, reviewed, maintained, and versioned.
- **`## LLM-as-Judge Rubric`** — Rubric dimensions, scoring scale, pass/fail thresholds, disagreement handling, and when human review overrides.
- **`## Hallucination Test Plan`** — Tests for unsupported claims, fabricated outputs, unsafe completions, and context misuse.
- **`## Latency/Cost SLOs`** — Acceptable latency, cost, token usage, and degradation thresholds for model-backed flows.
- **`## Red-Team Scenarios`** — Adversarial, ambiguous, or policy-sensitive scenarios with expected safe behavior and pass/fail criteria.
- **`## Prompt Regression Suite`** — How prompt changes are regression-tested against known examples and quality thresholds.

`TC-###` ids are stable traceability handles. On approval, PM-OS rebuilds a machine-readable `.traceability.yaml` from the cited ids.

---

## 07 — Metrics Plan

**File:** `07-metrics-plan.md` · **Skill:** `pm-stage-07-metrics-plan`

Base sections:

- **`## North Star Metric`** — The primary success metric tied to the stage-01 hypothesis: how it's calculated, its event/source, owner, segment, review cadence, baseline/target, and what movement signals progress.
- **`## Input Metrics`** — Leading indicators that should drive the north star, each with definition, formula, source, owner, segment, cadence, baseline/target, and the decision it informs.
- **`## Output Metrics`** — Outcome measures of product/business/user-value impact, traced to PRD goals, the success hypothesis, QA criteria, prototype questions, or risks.
- **`## Guardrail Metrics`** — Metrics that detect negative tradeoffs, misuse, quality regressions, or data/operational harm, with threshold/trigger guidance.
- **`## Instrumentation Plan`** — Events, properties, data sources, owners, privacy/governance notes, and how instrumentation is validated (concrete event names + required properties).
- **`## Dashboard Sketch`** — Dashboard structure, key views, filters, segments, and alert surfaces.
- **`## Review Cadence`** — Who reviews metrics, how often, and what thresholds trigger which decision (continue/iterate/rollback/expand/investigate/stop).

**If `genai_flag=true`,** append after `## Review Cadence`:

- **`## Quality Metrics`** — AI quality measures (accuracy, faithfulness, usefulness, correction/acceptance rate, safety) with thresholds, owners, cadence, and escalation triggers.
- **`## Cost per Invocation`** — How model/API cost is measured, attributed, bounded, and reviewed, with target/limit, owner, and escalation trigger.
- **`## Token Usage`** — Token usage measures, segmentation, limits, and signals of context/prompt inefficiency, with owner and expected action.
- **`## Model Performance Drift Detection`** — How quality/latency/cost/behavior drift is detected over time, the threshold that triggers investigation, and the follow-up owner.

---

## 08 — Technical Requirements Document (TRD)

**File:** `08-trd.md` · **Skill:** `pm-stage-08-trd` · Optional capstone (depends on the approved core pipeline 01–07)

Base sections:

- **`## System Context`** — What's being built, the system boundary, what it talks to, and what's explicitly outside it — tied to the scoped MVP.
- **`## Architecture`** — Major components, responsibilities, data ownership, trust and sync/async boundaries, failure modes, and how they interact (ASCII diagram optional).
- **`## Data Model`** — Core entities, key fields, relationships, storage, retention, ownership, and any privacy-relevant data.
- **`## Data Governance & Compliance Implementation`** — How the PRD's Data & Governance requirements are enforced in the build (access control, encryption, audit logging, retention/deletion, lineage), each control traced to the obligation it satisfies.
- **`## API / Interface Contracts`** — Interfaces between components and outward: endpoints/signatures, request/response shapes, error semantics, auth, idempotency, rate limits, versioning.
- **`## Key Technical Flows`** — Sequence-level walkthroughs of the highest-value/riskiest flows, mapping PRD user stories to system behavior across components.
- **`## Tech Stack & Rationale`** — Languages, frameworks, datastores, and major libraries, each with a one-line rationale tied to a requirement/constraint (not preference).
- **`## Non-Functional Implementation`** — How each PRD NFR *target* is actually met (performance, scaling, reliability, security, privacy, observability), referencing the specific target.
- **`## Dependencies & Integrations`** — External services, internal systems, and third-party APIs the build depends on, with failure assumptions.
- **`## Trade-offs & Alternatives Considered`** — The significant technical decisions, the alternatives weighed, and why the chosen path won.
- **`## Technical Risks & Mitigations`** — Engineering risks (scaling cliffs, data-integrity hazards, integration fragility, security exposure) with concrete mitigations.
- **`## Rollout, Migration & Deployment`** — Environments, migration/backfill needs, feature flags, rollback strategy, observability checks, and go/no-go criteria tied to QA and metrics.
- **`## Open Technical Questions`** — Unresolved technical decisions, including any product decision that technical reality calls into question.

**If `genai_flag=true`,** append after `## Open Technical Questions`:

- **`## Model Serving & Selection`** — Which models, how they're accessed/served (hosted vs self-hosted), versioning, provider/data-retention assumptions, and operational drivers.
- **`## Prompt / Agent Architecture (Implementation)`** — The concrete orchestration: prompt templates, version management, agent/tool loop, state handling, control flow, and human-review/escalation paths.
- **`## Tool / Function Implementation`** — The tools/functions exposed to the model: signatures, side effects, permissions, authorization checks, and output validation.
- **`## Context & Retrieval Engineering`** — How context is assembled per invocation: retrieval/indexing strategy, chunking, ranking, caching, and window budgeting.
- **`## Evaluation & Guardrail Implementation`** — How quality/safety/faithfulness is enforced at runtime: input/output validation, guardrails, eval hooks wired to stage-06, failure behavior, and monitoring.
- **`## Inference Cost & Latency Engineering`** — Token/cost budgeting, caching, batching, streaming, and latency controls, tied to the stage-07 metrics.

Use stable IDs (`TR-001`, `ADR-001`) for major technical requirements/decisions. The TRD goes deeper than the PRD — buildable detail, not a checklist.

---

## 09 — Product Roadmap

**File:** `09-roadmap.md` · **Skill:** `pm-stage-09-roadmap` · Optional capstone (depends on approved 01–07; uses 08 when the TRD is approved)

Exactly these top-level sections:

- **`## MVP Baseline`** — What the approved MVP is, who it serves, the problem it solves, the core value loop, the scope boundary, and the key stage-02 exclusions.
- **`## Roadmap Principles`** — The sequencing principles governing future work, tied to the hypothesis, stage-07 metrics, customer risk, operational readiness, and differentiation.
- **`## Release Horizons`** — Container for the phased horizons below:
  - **`### V1: Deliverable Product`** — The first post-MVP release: customer/market outcome, main capabilities, MVP evidence required, readiness dependencies, and what stays excluded.
  - **`### V2: Scale And Differentiation`** — The next horizon: scale, workflow depth, differentiation, reliability, governance, or GTM reach, each tied to evidence.
  - **`### Later / Optional`** — Longer-range conditional bets, each labeled with the evidence or strategic trigger required before investing.
- **`## Expansion Candidates`** — Prioritized candidate themes: user value, business rationale, dependency, signal required, rough confidence, and target horizon.
- **`## Decision Gates`** — Measurable continue/iterate/expand/pivot/pause/stop gates (using stage-07/06 thresholds), each naming owner, cadence, threshold, and resulting action.
- **`## Dependencies & Readiness`** — Product/design/eng/data/ops/legal/GTM dependencies for V1+, readiness risks/mitigations, and TRD implications where an approved 08 exists.
- **`## Not Planned`** — Features/markets/segments/platforms/directions kept out of scope for now, tied to stage-02 exclusions, risk, or strategic focus.
- **`## Open Questions`** — Unresolved product/market/user/ops/measurement questions that could change the roadmap, each with its learning plan.

When `genai_flag=true`, the **same** top-level sections are kept — GenAI considerations (eval maturity, model governance, cost/latency, drift, etc.) fold into the existing sections; no extra GenAI-only sections are added.

---

## Supporting generated files

Beyond the Markdown artifacts above, PM-OS writes several machine-managed files per project. These are engine state, not PM-authored docs, but they are "generated" and worth knowing:

| File | Written by | Purpose |
|------|-----------|---------|
| `.meta.yaml` | `pm-new`, `pm_approve.py`, hooks | Project + per-stage state (`schema_version: 4`); mirrors each artifact's frontmatter. |
| `telemetry.jsonl` | `lib/telemetry.py` | Append-only, hash-chained event log (`prev_event_hash` → `event_hash`). |
| `.traceability.yaml` | rebuilt on stage-06 approval | Machine-readable requirement↔test map from `US/FR/REQ` ↔ `TC` ids. |
| `04-design-spec.html` | `hooks/post-approve.py` via `lib/html_render.py` (`templates/design-spec.html.j2`) | HTML companion rendered on stage-04 approval. |
| `05-prototype-*.html` | `pm-prototype-html` (`templates/prototype-mockup.html.j2`) | Interactive prototype rendered after the stage-05 brief. |
| `00-context/manifest.yaml` | `pm_context_import.py pack-manifest` | Assembles the context-wiki pack; records it in `.meta.yaml`. |

---

*Formats are sourced from the `# Output specification` blocks of each `skills/pm-stage-*/SKILL.md` and the context templates in `pm-context-import` / `pm-context-scan-codebase`. When a stage's output spec changes, update this doc alongside it.*
