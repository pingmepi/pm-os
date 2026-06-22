# PM-OS Quality, Operations & Self-Improvement Loop Plan

**Status:** Draft plan
**Author:** Karan (with Codex)
**Date:** 2026-06-18
**Scope:** Add a local-first measurement and recommendation loop so PM-OS can track usage, artifact quality, operational health, and improvement opportunities across projects, while keeping agents in a suggestion-only role.

PM-OS already has the right primitives: local project state, hash-chained telemetry, stage feedback, approval metrics, and central sync into the feedback repo. This plan turns those primitives into a readable improvement system that Claude Code and Codex can fetch, summarize, and use to suggest enhancements without applying changes automatically.

The target is not a dashboard or service. The target is an agent-readable operating layer:

- deterministic scripts aggregate metrics from local JSONL logs
- Markdown summaries explain what is happening and why it matters
- recommendation logs capture suggested improvements with evidence
- PM decisions explicitly accept, reject, or defer each recommendation
- implementation work starts only after the PM asks for it

---

## 1. Goals

PM-OS should make these questions easy to answer:

1. **Usage:** Are PMs using PM-OS, and where do workflows start, stall, or complete?
2. **Quality:** Which stages produce useful artifacts, and which stages require heavy PM correction?
3. **Operations:** Is the local workflow reliable across install, generation, approval, sync, and verification?
4. **Improvement:** What should be improved next, based on evidence rather than guesswork?
5. **Governance:** Which suggestions were accepted, rejected, deferred, shipped, or later proven useful?

The system is successful when an agent can read local files and say:

> Stage 03 PRD quality is a recurring issue. Across recent projects it has higher edit distance, lower ratings, and repeated `weak_requirements` feedback. Recommended improvement: update the PRD prompt to require stable requirement IDs and acceptance criteria. Status: proposed; PM decision required before implementation.

---

## 2. Non-Goals

- No backend service.
- No hidden database.
- No automatic code changes from recommendations.
- No external analytics vendor.
- No mandatory dashboard for the first implementation.
- No editing historical telemetry events.
- No copying sensitive project content into central summaries beyond explicit summaries, IDs, hashes, and PM-provided feedback.

Agents may generate recommendations and plans. They must not implement those recommendations unless the PM explicitly asks for implementation.

---

## 3. Design Principles

1. **Local-first:** Project-level state stays beside existing PM-OS files.
2. **Append-only where possible:** Raw events, feedback, recommendations, and decisions are append logs.
3. **Readable by agents and humans:** JSON for aggregation, Markdown for review.
4. **Deterministic first:** Computation of counts, timings, edit distance, ratings, and funnel metrics happens in Python.
5. **Agent judgment second:** Qualitative diagnosis and recommendation synthesis can be agent-generated, but should cite deterministic evidence.
6. **PM authority:** Suggestions are not approvals. A recommendation becomes work only after a PM decision.
7. **Cross-runtime parity:** Claude Code and Codex should read the same files and follow the same governance model.

---

## 4. Project-Level Files

Add these files at the project root, beside `telemetry.jsonl` and `feedback.jsonl`.

```text
<project>/
  telemetry.jsonl
  feedback.jsonl
  metrics-summary.json
  metrics-summary.md
  recommendations.jsonl
  recommendations.md
  improvement-decisions.jsonl
```

### `metrics-summary.json`

Deterministic aggregate output for one project. Rebuildable at any time from `telemetry.jsonl`, `feedback.jsonl`, and `.meta.yaml`.

Example shape:

```json
{
  "schema_version": 1,
  "generated_at": "2026-06-18T00:00:00Z",
  "scope": "project",
  "project": "example-project",
  "pm_os_version": "0.5.3",
  "usage": {},
  "quality": {},
  "operations": {},
  "feedback": {},
  "recommendation_inputs": []
}
```

### `metrics-summary.md`

Human and agent-readable narrative summary of the same data:

- project status
- stage funnel
- notable quality signals
- operational warnings
- feedback themes
- candidate areas for recommendation

### `recommendations.jsonl`

Append-only recommendation log. Each line is one suggestion from PM-OS.

```json
{
  "recommendation_id": "rec_20260618_001",
  "created_at": "2026-06-18T00:00:00Z",
  "scope": "stage_03_prd",
  "category": "quality",
  "severity": "medium",
  "confidence": "high",
  "source_signals": [
    "normalized_edit_distance:p90_above_threshold",
    "feedback_tag:weak_requirements",
    "rating:below_4"
  ],
  "recommendation": "Tighten the PRD prompt to require stable requirement IDs and explicit acceptance criteria.",
  "expected_effect": "Lower PRD edit distance and improve downstream QA and TRD traceability.",
  "suggested_next_step": "Draft an implementation plan for PM approval.",
  "status": "proposed"
}
```

### `recommendations.md`

Readable rollup grouped by severity, category, and status. This is the file agents should prefer when the PM asks, "What should we improve?"

### `improvement-decisions.jsonl`

Append-only PM decision log. Decisions do not mutate old recommendation records.

```json
{
  "decision_id": "dec_20260618_001",
  "recommendation_id": "rec_20260618_001",
  "decided_at": "2026-06-18T00:00:00Z",
  "decision": "accepted",
  "decided_by": "karan",
  "decision_note": "Accept, but sequence after stable IDs work.",
  "implementation_status": "not_started"
}
```

Valid `decision` values:

- `accepted`
- `rejected`
- `deferred`
- `needs_more_evidence`

Valid `implementation_status` values:

- `not_started`
- `planned`
- `in_progress`
- `shipped`
- `abandoned`

---

## 5. Central Feedback Repo Files

Extend the existing feedback repo structure without changing the raw sync model.

```text
pm-os-feedback/
  telemetry/
    <pm>/
      <project>/
        telemetry.jsonl
        feedback.jsonl
        metrics-summary.json
        metrics-summary.md
        recommendations.jsonl
        recommendations.md
        improvement-decisions.jsonl
  inferred/
    weekly/
      2026-W25-metrics.json
      2026-W25-summary.md
      2026-W25-recommendations.md
```

The central repo remains a Git-backed aggregation surface. Raw per-project files stay under `telemetry/<pm>/<project>/`; cross-project summaries go under `inferred/`.

---

## 6. Metric Families

### Usage Metrics

Purpose: understand adoption and workflow shape.

Track:

- projects created
- projects active in a period
- stage started/generated/approved counts
- stage completion funnel
- drop-off stage
- time between stage approvals
- regeneration count per stage
- optional stage usage: 08 TRD and 09 roadmap
- context import usage
- feedback submissions per project/stage
- runtime/source where available: Claude Code, Codex, manual script

Example derived fields:

```json
{
  "usage": {
    "stages_started": 7,
    "stages_generated": 6,
    "stages_approved": 5,
    "furthest_approved_stage": "05",
    "optional_stages_used": ["08"],
    "regenerations_total": 3,
    "feedback_entries": 4
  }
}
```

### Quality Metrics

Purpose: identify artifact quality issues and weak stages.

Track:

- `time_to_approve_seconds`
- `char_edit_distance`
- `normalized_edit_distance`
- optional `semantic_distance`
- regeneration count
- feedback rating
- feedback tags
- edited-after-approval events
- stale downstream stages caused by upstream changes
- repeated PM notes or carry-forward notes

Suggested feedback tags:

- `missing_context`
- `wrong_scope`
- `too_generic`
- `weak_requirements`
- `weak_metrics`
- `weak_qa`
- `hallucination`
- `format_issue`
- `tone_issue`
- `excellent`
- `good_enough`
- `other`

Example derived fields:

```json
{
  "quality": {
    "by_stage": {
      "03": {
        "approval_count": 1,
        "regeneration_count": 2,
        "normalized_edit_distance": 0.31,
        "semantic_distance": 0.2,
        "average_rating": 3.0,
        "feedback_tags": ["weak_requirements", "too_generic"]
      }
    }
  }
}
```

### Operational Metrics

Purpose: make reliability issues visible.

Track:

- pre-stage gate failures
- approval failures
- post-approval hook failures
- telemetry chain verification failures
- sync failures
- install/update/verify failures
- malformed metadata or artifacts
- context load failures
- HTML render failures
- missing generated snapshots
- missing expected telemetry events

Some of these require new event types or explicit logging where failures currently only print to stdout.

Candidate event types:

- `gate_failed`
- `approval_failed`
- `sync_failed`
- `verify_failed`
- `install_failed`
- `update_failed`
- `context_load_failed`
- `render_failed`

### Improvement Metrics

Purpose: measure whether the improvement loop itself works.

Track:

- recommendations created
- recommendations accepted/rejected/deferred
- accepted recommendations converted into plans
- accepted recommendations shipped
- repeat occurrence of the same issue after shipment
- before/after stage metrics for shipped improvements
- recommendation precision: accepted / proposed

Example:

```json
{
  "improvement": {
    "recommendations_proposed": 8,
    "recommendations_accepted": 3,
    "recommendations_shipped": 1,
    "repeat_issues_after_shipment": 0
  }
}
```

---

## 7. Recommendation Governance

Recommendations must remain suggestions until the PM decides.

Recommended status flow:

```text
proposed -> accepted -> planned -> in_progress -> shipped
proposed -> rejected
proposed -> deferred
proposed -> needs_more_evidence
```

Implementation rule:

- `pm-insights` may create or update recommendation summaries.
- `pm-improvement-plan` may draft a plan for accepted recommendations.
- No command should edit PM-OS source files from a recommendation unless the PM explicitly asks for implementation.

Agent language should be explicit:

- Good: "Recommended improvement: update stage 03 prompt. PM decision required."
- Bad: "I improved stage 03 based on telemetry."

---

## 8. Proposed Commands

### `pm-metrics`

Generate or refresh project-level metrics from the current project.

Outputs:

- `metrics-summary.json`
- `metrics-summary.md`

Modes:

```bash
python3 ~/.pm-os/scripts/pm_metrics.py
python3 ~/.pm-os/scripts/pm_metrics.py --json
python3 ~/.pm-os/scripts/pm_metrics.py --since 2026-06-01
```

### `pm-system-metrics`

Aggregate all projects under `projects_dir` or the central feedback repo cache.

Outputs:

- local console summary
- optional central `inferred/<period>-metrics.json`
- optional central `inferred/<period>-summary.md`

Modes:

```bash
python3 ~/.pm-os/scripts/pm_system_metrics.py
python3 ~/.pm-os/scripts/pm_system_metrics.py --period weekly
```

### `pm-insights`

Agent-assisted synthesis step. Reads metrics summaries and feedback, then drafts recommendations.

Outputs:

- `recommendations.jsonl`
- `recommendations.md`

Rules:

- cite source signals
- distinguish deterministic findings from agent judgment
- avoid duplicate recommendations when a similar open recommendation already exists
- do not implement

### `pm-improvement-decision`

Record PM decisions against recommendations.

Modes:

```bash
python3 ~/.pm-os/scripts/pm_improvement_decision.py rec_20260618_001 --decision accepted --note "Sequence after stable IDs."
python3 ~/.pm-os/scripts/pm_improvement_decision.py rec_20260618_002 --decision rejected --note "Not important for current usage."
```

### `pm-improvement-plan`

Draft an implementation plan for accepted recommendations. This should create a plan document or update an existing one, not change code.

Inputs:

- accepted recommendation IDs
- relevant metrics summaries
- current PM-OS source tree

Outputs:

- a Markdown implementation plan under `docs/plans/`

---

## 9. Implementation Phases

### Phase 0 — Schema and Taxonomy

Define:

- `metrics-summary.json` schema
- `recommendations.jsonl` schema
- `improvement-decisions.jsonl` schema
- feedback tag taxonomy
- recommendation categories and severities

Recommended categories:

- `usage`
- `quality`
- `operations`
- `workflow`
- `documentation`
- `runtime_parity`
- `performance`
- `security_privacy`

Recommended severities:

- `low`
- `medium`
- `high`
- `critical`

Acceptance criteria:

- [ ] Schemas documented in `docs/reference/pm-os-spec.md` or a dedicated reference doc.
- [ ] Feedback tags are shared by `pm-feedback`, metrics, and insights.
- [ ] Recommendation and decision records are append-only.

### Phase 1 — Deterministic Project Metrics

Add `pm-metrics`.

Implementation:

- parse `telemetry.jsonl`
- parse `feedback.jsonl`
- read `.meta.yaml`
- compute stage funnel, timing, edit-distance, ratings, operational warnings
- write `metrics-summary.json`
- write `metrics-summary.md`

Acceptance criteria:

- [ ] A project with existing telemetry can produce a metrics summary.
- [ ] Missing feedback or telemetry is reported clearly, not treated as zero quality.
- [ ] Imported/backfilled stages do not pollute generation-quality metrics.
- [ ] Telemetry chain status is included.
- [ ] Output is stable and deterministic.

### Phase 2 — Sync Metrics Files

Extend `lib/git_sync.py` to sync the new project-level summary and recommendation files when present.

Files to sync:

- `metrics-summary.json`
- `metrics-summary.md`
- `recommendations.jsonl`
- `recommendations.md`
- `improvement-decisions.jsonl`

Acceptance criteria:

- [ ] Existing telemetry/feedback sync behavior remains unchanged.
- [ ] Missing optional files do not fail sync.
- [ ] Synced project folder remains agent-readable in the central feedback repo.

### Phase 3 — Cross-Project Metrics

Add `pm-system-metrics`.

Implementation:

- walk all projects under `projects_dir`, or central cache when requested
- aggregate usage, quality, operations, and feedback by project, stage, PM, period, and PM-OS version
- generate weekly or ad hoc Markdown summaries

Acceptance criteria:

- [ ] Aggregation works without network access.
- [ ] One broken project file does not prevent summarizing the rest.
- [ ] Summary identifies top quality and operational issues by evidence.
- [ ] Summary can be read directly by Claude Code or Codex.

### Phase 4 — Recommendation Generation

Add `pm-insights`.

Implementation:

- deterministic pre-pass identifies candidate signals
- agent synthesizes recommendations from summaries and feedback
- recommendations are written to `recommendations.jsonl`
- `recommendations.md` groups open items by severity and category

Acceptance criteria:

- [ ] Every recommendation cites source signals.
- [ ] Recommendations clearly state whether they are deterministic findings or agent judgment.
- [ ] Duplicate open recommendations are avoided.
- [ ] No source code is modified.
- [ ] Each recommendation has a PM-decision status of `proposed` until acted on.

### Phase 5 — PM Decisions

Add `pm-improvement-decision`.

Implementation:

- append PM decision records
- rebuild `recommendations.md` with current effective status
- optionally add `pm-status` summary of open recommendations

Acceptance criteria:

- [ ] PM decisions are append-only.
- [ ] Rejected or deferred recommendations remain historically visible.
- [ ] Accepted recommendations do not trigger implementation automatically.

### Phase 6 — Improvement Planning

Add `pm-improvement-plan`.

Implementation:

- read accepted recommendations
- inspect current PM-OS repo state
- draft a concrete implementation plan under `docs/plans/`
- include acceptance criteria and verification commands
- do not edit implementation files

Acceptance criteria:

- [ ] The generated plan is reviewable before code changes.
- [ ] The plan traces each proposed change to accepted recommendations.
- [ ] The PM can ask an agent to implement the plan in a separate step.

---

## 10. Thresholds and Heuristics

Initial thresholds should be conservative and easy to tune.

Candidate quality flags:

- `normalized_edit_distance >= 0.25`: meaningful PM rewrite
- `normalized_edit_distance >= 0.50`: severe artifact mismatch
- `rating <= 3`: quality concern
- `regeneration_count >= 2`: generation instability
- same feedback tag appears on 3 or more projects: recurring stage issue
- stage has high edit distance and low rating: priority candidate

Candidate operational flags:

- any broken telemetry chain: high severity
- repeated sync failures: medium severity
- post-approve hook failure: medium severity
- install/update/verify failure: high severity
- missing generated snapshot for generated stage: medium severity

Candidate usage flags:

- frequent drop-off before stage 03: onboarding or early-stage quality issue
- frequent drop-off after stage 05: downstream stages may be too heavy or unclear
- low feedback submission rate: feedback capture UX issue

Thresholds should live in config eventually, but the first implementation can keep them in the metrics script with clear constants.

---

## 11. Agent-Readable Summary Format

`metrics-summary.md` and central weekly summaries should use stable headings:

```markdown
# PM-OS Metrics Summary

## Scope
## Executive Summary
## Usage
## Quality
## Operations
## Feedback Themes
## Recommendation Inputs
## Open Questions
```

`recommendations.md` should use stable headings:

```markdown
# PM-OS Recommendations

## High Priority
## Medium Priority
## Low Priority
## Deferred
## Rejected
## Shipped
```

Stable headings make the files easy for agents to fetch and summarize without needing a special parser.

---

## 12. Privacy and Data Boundaries

Raw project artifacts should not be copied into metrics summaries by default.

Allowed in central summaries:

- project slug
- PM identifier
- stage id
- event counts
- timings
- edit-distance metrics
- rating values
- feedback tags
- short PM-provided feedback text only if already in `feedback.jsonl`
- recommendation text
- decision notes

Avoid by default:

- full artifact bodies
- raw imported source content
- external document contents
- secrets, credentials, tokens
- PHI/PII

If richer summaries are needed later, add an explicit redaction/sanitization step.

---

## 13. Verification

Unit tests:

```bash
python3 -m pytest tests/unit/test_metrics.py
python3 -m pytest tests/unit/test_recommendations.py
```

Integration tests:

```bash
python3 -m pytest tests/integration/test_pm_metrics.py
python3 -m pytest tests/integration/test_pm_system_metrics.py
python3 -m pytest tests/integration/test_improvement_decisions.py
```

Manual checks:

1. Create a scratch PM-OS project.
2. Approve stage 00 and at least one generated stage.
3. Capture feedback with rating and tags.
4. Run `pm-metrics`.
5. Confirm `metrics-summary.json` and `metrics-summary.md` are readable and correct.
6. Run `pm-insights`.
7. Confirm recommendations cite evidence and do not modify source.
8. Record a PM decision.
9. Confirm the decision is append-only and reflected in `recommendations.md`.
10. Run `pm-sync` and confirm optional summary files are copied when present.

---

## 14. Open Decisions

1. Should `pm-feedback` require at least one tag when a rating is 3 or below?
2. Should recommendations be project-local only at first, or should central weekly recommendations be the first-class surface?
3. Should `pm-insights` be a standalone skill, a script plus skill, or part of `pm-status`?
4. Should recommendation IDs be deterministic hashes of category/scope/signals, or timestamp-based IDs?
5. Should thresholds be hardcoded in v1 or stored in `~/.pm-os/config.yaml`?
6. How much free-text feedback is acceptable in central summaries for team-wide use?

---

## 15. Suggested Build Order

1. Add feedback tags to `pm-feedback`.
2. Add deterministic `pm-metrics` for one project.
3. Extend sync to include optional summary and recommendation files.
4. Add `pm-system-metrics` for cross-project summaries.
5. Add `recommendations.jsonl` and `recommendations.md`.
6. Add `pm-insights` as a suggestion-only agent workflow.
7. Add `improvement-decisions.jsonl` and `pm-improvement-decision`.
8. Add `pm-improvement-plan` for accepted recommendations.
9. Add tests and spec updates as each phase lands.

This keeps the first useful version small: PM-OS can summarize its own usage and quality before it tries to recommend changes.

---

## 16. Acceptance Criteria for the Whole Loop

- [ ] A PM can run one command in a project and get a readable metrics summary.
- [ ] A PM can run one command across projects and get a readable system summary.
- [ ] Claude Code and Codex can read the summaries without external services.
- [ ] PM-OS can propose improvement recommendations with cited signals.
- [ ] Recommendations are suggestions, not implementation triggers.
- [ ] PM decisions are recorded append-only.
- [ ] Accepted recommendations can be converted into implementation plans.
- [ ] No source code changes happen until the PM explicitly asks for implementation.
- [ ] The central feedback repo can store raw logs, summaries, recommendations, and decisions in a predictable structure.

End of plan.
