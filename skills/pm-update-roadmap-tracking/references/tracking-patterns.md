# Roadmap Tracking Patterns

Read this when no clear tracking format exists, multiple tracking docs disagree, or a new tracker must be created.

## Source Of Truth

Prefer one canonical tracker over scattered status notes. Good candidates are:

- a roadmap or implementation plan under `docs/`, `plans/`, `product/`, or `spec/`;
- a stage-09 PM-OS roadmap when the project uses PM-OS;
- a release-readiness, milestone, or backlog document that already has owners/statuses;
- a changelog only for shipped user-visible changes, not as the main tracker.

When two docs conflict, treat approved product docs and the most recently maintained canonical tracker as binding. Leave a note in secondary docs instead of duplicating a full tracker.

## Minimal Tracker Shape

Use this shape only when creating a new tracker or normalizing a sparse one:

```markdown
| Item | Horizon / Milestone | Status | Evidence | Owner | Next step | Updated |
| --- | --- | --- | --- | --- | --- | --- |
```

Keep IDs, ticket references, requirement IDs, or roadmap item names from the source docs when they exist.

## Evidence Rules

Good evidence includes:

- approved product artifacts, PRDs, scopes, design specs, QA plans, or roadmap sections;
- git diffs, commits, merged PR notes, tests, migration files, API routes, UI components, or configuration changes;
- release notes, QA results, monitoring dashboards, analytics instrumentation, or explicit user confirmation.

Weak evidence includes:

- TODO comments without implementation;
- untested code paths;
- aspirational roadmap text;
- generated files with no source change;
- assumptions based only on file names.

## Common Updates

- Move an item to `In progress` when code, design, tests, or docs show active work but acceptance evidence is incomplete.
- Move an item to `Done` only when implementation and validation evidence match the product requirement.
- Add a blocker when the codebase shows missing dependencies, failing tests, unresolved decisions, or upstream product drift.
- Add an at-risk note when scope grew beyond the approved MVP, requirements are ambiguous, or QA/metrics coverage is missing.
- Split an item when one part shipped and another part remains meaningfully incomplete.
- Add a new item only when it is grounded in approved scope, explicit user instruction, or a real code/product gap.

## PM-OS Projects

For PM-OS projects, do not silently edit approved stage artifacts. If codebase reality diverges from approved `02-scope.md`, `03-prd.md`, `06-qa-plan.md`, `07-metrics-plan.md`, `08-trd.md`, or `09-roadmap.md`, record the mismatch in the tracker and ask the PM whether to revise the approved upstream artifact through the normal PM-OS approval flow.
