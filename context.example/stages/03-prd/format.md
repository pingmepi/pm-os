# Stage 03 — PRD format (Indegene)

> apply: augment — the skill keeps its default PRD sections and folds these
> requirements in. Fill in the placeholders below with your team's real
> conventions, then save. An unfilled copy (identical to this seed) stays a
> no-op; edit it to activate.

## Per-story structure (house format)

> Each `US-###` in "User Stories with Acceptance Criteria" should be a
> self-contained mini-spec carrying, at minimum:
>
> - **Story** — As a `<role>`, I want `<capability>`, so that `<outcome>`.
> - **Data fields** — the superset of fields the story touches (name, type,
>   mandatory?), where a screen/grid is involved.
> - **Key UI steps** — the ordered user↔system interactions. For **each** step,
>   document:
>   - **System process** — the background behaviour for that step (for grids,
>     name the sort field).
>   - **Acceptance (Done)** — the completion definition for that step.
>   - **Corner cases** — at least two, each tied to a `TC-###` in the QA plan.
>   - **Exceptions** — where the system should *not* behave as described.
> - **Wireframes** — reference the screen(s); mandatory for new screens.

<!-- TODO: paste your team's exact per-story field list / wording here. -->

## Impact analysis & NFRs (per story or PRD-level)

> Include an **Impact Analysis** section covering impacted common components,
> impacted existing functionality across products, 3rd-party integrations, and
> jurisdiction impacts — plus non-functional expectations (performance on
> load/volume) relevant to the story.

<!-- TODO: name your common components (e.g. PS, Pitboss), products/apps in
     scope, and the jurisdictions/regulatory regimes that apply. -->

## Conventions & must-haves

<!-- TODO: requirement-ID conventions, acceptance-criteria format, NFR coverage,
     traceability expectations, anything your team always expects in a PRD. -->
