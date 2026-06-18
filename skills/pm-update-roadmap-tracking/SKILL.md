---
name: pm-update-roadmap-tracking
description: Update roadmap, implementation-plan, status, backlog, release-readiness, or tracking documentation after product or code work. Use when the user asks to sync roadmap tracking, update progress docs, reconcile product docs with the codebase, review what changed and update relevant docs, mark roadmap items done/in-progress/blocked, refresh implementation plans, or keep PM/product tracking current for any active product or repository.
---

# Update Roadmap Tracking

## Overview

Keep roadmap and progress-tracking documents aligned with the real product state. Inspect the product docs and codebase first, then update only the relevant tracking docs with evidence-backed status changes, risks, decisions, and next steps.

## Core Workflow

1. Identify the active product root. Use the current working directory unless the user names another repo, PM-OS project, or docs folder.
2. Run the discovery helper to find likely tracking docs and code/doc change signals:

   ```bash
   python3 ~/.pm-os/scripts/discover_tracking_context.py <product-root>
   ```

3. Read the likely tracking docs before editing. Prefer docs whose titles or paths include roadmap, plan, implementation, status, tracker, release, milestone, backlog, or TODO.
4. Read the authoritative product docs that define intent and scope. For PM-OS projects, include approved stage artifacts when present: `00-*`, `01-brief.md`, `02-scope.md`, `03-prd.md`, `04-design-spec.md`, `05-prototype-brief.md`, `06-qa-plan.md`, `07-metrics-plan.md`, optional approved `08-trd.md`, and optional `09-roadmap.md`. For ordinary repos, inspect `README`, `docs/`, `spec/`, `plans/`, `product/`, `requirements`, `tickets`, and release notes.
5. Inspect codebase reality. Use git status/diff/log, tests, package/config files, routes, APIs, components, migrations, schemas, or other implementation landmarks relevant to the product.
6. Build an evidence map before editing: changed capability, source evidence, affected tracking row/section, proposed status, confidence, and remaining gap.
7. Update only the docs that are clearly tracking roadmap/progress. Preserve the existing document structure, wording style, status taxonomy, owners, IDs, dates, and checkboxes.
8. Verify the edits by rereading the changed sections and checking that each status change is supported by a cited doc/code/test signal.

## Editing Rules

- Do not mark work complete from code presence alone. Require at least one completion signal such as passing tests, merged/committed implementation, updated acceptance criteria, release note, QA result, or explicit user confirmation.
- Do not change approved PM-OS stage artifacts unless the user explicitly asks. If implementation reality conflicts with an approved artifact, update the tracker with a drift/risk note and tell the user which upstream artifact may need revision and re-approval.
- Do not invent owners, dates, metrics, ticket IDs, or release names. Keep unknowns as `TBD`, `Unassigned`, or an existing local equivalent.
- Use the current local date for `Last reviewed`, `Updated`, or changelog entries only when the document already tracks review dates or a date is needed for the new entry.
- Keep roadmap scope stable. Move work between horizons only when product docs, code state, or user instruction clearly justify it.
- Prefer small, reviewable patches. If many tracking docs exist, update the source-of-truth tracker first and add cross-reference notes elsewhere only when they would otherwise become misleading.

## Status Guidance

- `Done` / `Shipped`: capability is implemented, validated, and no known blocking release work remains.
- `In progress`: implementation, validation, or documentation is actively underway with observable evidence.
- `Blocked`: progress depends on an unresolved decision, dependency, approval, bug, environment, or external party.
- `At risk`: work can continue, but delivery, scope, quality, compliance, or measurement risk is materially higher than the tracker currently says.
- `Not started`: no meaningful implementation or validation evidence is present.

Use the local document's own status names when they differ. Map the meaning, not the exact label.

## When Structure Is Ambiguous

Read `references/tracking-patterns.md` when the repo has no obvious tracker, when several docs disagree, or when the user asks to create or normalize tracking. Use it for a compact schema, evidence rules, and common update patterns.

## Output

In the final response, summarize:

- which tracking docs changed;
- the most important status changes;
- evidence used from docs/code/tests;
- any unresolved drift, blockers, or decisions the PM should review.
