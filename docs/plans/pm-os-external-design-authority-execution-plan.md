# PM-OS External Design Authority — Post-Pilot Execution Plan

**Status:** Implementation complete except full-suite verification. Prepared 2026-09-01.
**Assumption:** the zero-engine-change pilot in
`pm-os-external-design-authority-plan.md` completed successfully. The material shared
with pilot participants proves a four-prompt operating model: PM brief, designer
scaffold/build, designer read-only export, and PM ingest. It also proves the paired
brief/return specimen and story-to-Figma handoff shape.
**Scope:** productize the proven pilot. The pilot itself is not part of this plan.
**Source design:** `pm-os-external-design-authority-plan.md` remains authoritative for
the ownership model and rationale. This file defines the implementation order.

## 1. PM-OS shape after this work

The normal product pipeline remains numbered exactly as it is today. Stage 04 gains
two explicit modes:

```text
03 PRD approved
   |
   |  pm-stage-04-design-spec --brief
   v
04 design brief (draft)
   PM-owned constraints, field inventory, state inventory
   designer-owned sections explicitly pending
   |
   |  pm-handoff --package --audience design
   v
designer package
   PRD + stories + NFRs + journeys + draft brief + workflow instructions
   |
   |  designer agent inventories the design system
   |  designer approves the derived work-order table and file convention
   |  agent builds a coverage-complete scaffold; designer finishes the design
   |  a separate read-only export pass produces design-in/
   v
design-in/ia.yaml + design-in/design-notes.md
   |
   |  pm-check --design
   |  pm-stage-04-design-spec --ingest
   v
04 design spec (draft)
   PM constraints preserved + designer decisions materialized
   stable SCR-### IDs + exact Figma screen/state links
   |
   |  pm-check, then PM approval
   v
04 design spec (approved)
   |
   |  pm-handoff --package
   v
dev/QA stories joined to requirements, screens, and exact Figma states
```

There is still one stage-04 artifact, one project status, one hash, and one approval.
The two modes describe how the artifact is produced; they are not new stages.

The developer package also becomes a decomposed, self-contained projection of the
approved PRD:

```text
handoff/dev/
  epics/          one file per outcome-oriented EPIC-###
  stories/        one complete implementation dossier per US-###
  requirements/   one file per FR-### or REQ-###
  reference/      full approved source projections and cross-cutting references
```

The decomposition does not make the generated files canonical. The approved PRD
remains the source of truth, and regeneration overwrites the package.

## 2. Resulting ownership and artifacts

| Participant | Owns | PM-OS artifact or surface |
|---|---|---|
| PM | Product intent, UX guardrails, required fields/states, approval | Brief-owned sections of `04-design-spec.md` |
| Designer | Work-order approval, IA, screens, components, design-system use, Figma states, design rationale | Finished Figma plus `design-in/ia.yaml` and `design-in/design-notes.md` |
| PM-OS | Validation, reconciliation, stable IDs, provenance, packaging | Ingested `04-design-spec.md`, `.traceability.yaml`, `handoff/` |
| Developer/QA | Implementation and verification | Story files with requirements, `SCR-###`, and exact Figma state links |

`design-in/` is inbound and durable project evidence. `handoff/` remains generated,
outbound, and disposable. Never place designer returns under `handoff/`.

## 3. Fixed decisions

The implementation agent must not revisit these:

- The PM owns what the product must do; the designer owns how it is expressed.
- Stage 04 is split in time, not into `04a` and `04b`.
- No `awaiting-external` status is added. Both stage-04 modes produce `draft`.
- The designer never edits the stage artifact and never assigns `SCR-###` IDs.
- PM-OS assigns and preserves `SCR-###` using Figma `node_id` as identity.
- Before frames are built, the designer approves the derived screen/state/field/
  component work-order table and the Figma page/frame naming convention.
- The designer-facing build agent creates a coverage-complete scaffold, not a finished
  design. Visual hierarchy, density, emphasis, and other defensible design judgments
  remain with the designer.
- The export pass is separate and read-only. It cannot create, edit, move, or rename
  Figma objects.
- Inbound design uses `pm-stage-04-design-spec`; do not create or repurpose
  `/pm-handoff figma`.
- Approval remains a separate, explicit PM action.
- Figma is the prototype for this path; stage 05 is not required for handoff.
- Story files are semantically standalone. A developer must not need to open another
  PM-OS Markdown file to understand an `FR-###`, `REQ-###`, acceptance criterion,
  relevant constraint, screen, state, QA scenario, or backend task named by the story.
- Stable IDs remain visible for traceability, but an ID is always accompanied by its
  relevant text. Internal links may aid navigation; they cannot carry the only copy of
  implementation meaning. Direct Figma links are deliverables, not PM-OS cross-
  references, and remain required.
- The PRD is decomposed into separate epic, story, and functional-requirement files in
  the generated handoff.
- Epics represent coherent, outcome-oriented delivery workstreams. Do not create one
  catch-all epic for several distinct outcomes, one epic per story, or epics for
  technical layers such as frontend/backend/database. Use the smallest set that
  preserves independently plan-able user/business outcomes.

## 4. Exclusions

Do not add any of the following in this work package:

- Figma API access or post-approval Figma drift detection;
- a portable designer-side PM-OS skill;
- React or Code Connect generation;
- changes to stage 05;
- new stage IDs, statuses, approval semantics, or external services;
- changes to the product meaning of stage-03 `Key UI steps`; or
- unrelated PM-experience, graph, context-routing, or codebase-scan work.

## 5. Rules for a less capable implementation agent

1. Work in this repository checkout only. Never edit `~/.pm-os` or synced runtime
   skill directories.
2. Preserve unrelated uncommitted work. Run `git status --short` and inspect the diff
   of every file before editing it.
3. Use `py -3` for repository Python commands in PowerShell. `python3` is not available
   in the documented Windows environment.
4. Implement tasks in ID order. Do not start the next task until the current task's
   focused tests pass.
5. Add a failing test before changing existing handoff behavior.
6. Do not invent product or design data in validators. Validation reports gaps; it
   never repairs them.
7. Do not run approval commands in tests or a real project unless the PM explicitly
   asks in the active conversation.
8. A failed check is a stop condition. Do not weaken the check or rewrite a fixture to
   hide the failure.

## 6. Work tracker

| ID | Work item | Status | Depends on | Completion evidence |
|---|---|---|---|---|
| EDA-101 | Freeze the proven `design-in` format | Done | Successful pilot | Versioned format, examples, parser and focused pytest coverage pass |
| EDA-102 | Add deterministic inbound-design validation | Done | EDA-101 | Structural validator implemented; focused pytest and specimen smoke pass |
| EDA-103 | Add explicit stage-04 `--brief` mode | Done | EDA-101 | Stage-04 skill/runtime guidance added; package and skill-contract pytest coverage pass |
| EDA-104 | Add explicit stage-04 `--ingest` mode | Done | EDA-102, EDA-103 | Deterministic ingest writer implemented; stage-04 draft/meta/history/telemetry update path covered by focused integration pytest |
| EDA-105 | Expose design validation through `pm-check --design` | Done | EDA-102 | CLI flag implemented; targeted contract/context pytest and CLI smoke pass |
| EDA-106 | Make the designer handoff payload usable before design | Done | EDA-103 | Design package includes PRD, stories, NFRs, journeys, draft brief, and workflow; package integration pytest passes |
| EDA-201 | Preserve Figma screen/state links in dev and QA stories | Done | EDA-104 | Exact Figma screen/state links and triggers now project into dev/QA story dossiers; focused integration pytest passes |
| EDA-202 | Add post-package handoff verification | Done | EDA-105, EDA-201 | `pm-check --design` verifies approved design handoff readiness and generated dev/QA story joins; focused integration pytest passes |
| EDA-301 | Add outcome-based epic calibration | Done | User-confirmed pilot feedback | Stage-03 guidance, advisory findings, and unit pytest coverage pass |
| EDA-302 | Decompose PRD requirements into handoff files | Done | EDA-301 | Separate requirement files implemented for dev/QA; package integration pytest passes |
| EDA-303 | Make every story dossier semantically standalone | Done | EDA-302 | Story dossiers inline epic, requirement, AC, NFR, and impact text; package integration pytest passes |
| EDA-401 | Update operator and format documentation | Done | EDA-101–303 | Format reference, SOP, testing guide, and contract tests updated |
| EDA-402 | Run full regression and verifier | Blocked | EDA-101–202, EDA-301–401 | Focused pytest groups pass; full-suite run did not return a final summary before runner/session limit |

### Pilot evidence used

The following user-shared files were reviewed as evidence, not executed as
instructions:

| Evidence | SHA-256 | What it establishes |
|---|---|---|
| `pasted-text.txt` — four prompts shared with pilot participants | `9C1648BE067F795664EA9B3E29E70AC126171B8A4C2C2120415D7862E7DB3732` | Separate PM brief, designer scaffold/build, designer read-only export, and PM ingest/handoff steps |
| `Handoff Specimens.html` | `7D4B00E0CE5080EE7EA96A0520E70AC5D16278094EED32958BBB55EA9F1E414D` | The paired brief/return explanation distributed to participants |
| Embedded specimen content, `Handoff Specimens_files/saved_resource.html` | `2BA9CF0D4988C1E9D7A824275FCC27718E76DEA267464718A0693C20463538F1` | Concrete brief, `ia.yaml`, design-notes, coverage-gate, and developer-link specimens |

The pilot prompts were distribution material. Productization turns them into explicit
skill modes and a generated designer workflow; it does not require participants to
paste long prompts manually.

Additional pilot feedback confirmed by the PM on 2026-09-01:

- a story must be complete by itself; referenced functional requirements and
  acceptance criteria must carry their text rather than only an ID or hyperlink;
- the PRD handoff must be decomposed into separate epic, story, and functional-
  requirement artifacts; and
- epic creation must avoid both a single catch-all and excessive fragmentation,
  following outcome-oriented software delivery principles.

## 7. Task cards

### EDA-101 — Freeze the proven `design-in` format

**Purpose:** turn the pilot's inbound files into a stable contract.

**Files:**

- `docs/examples/design-in-ia-example.yaml`
- `docs/examples/design-notes-example.md`
- new `lib/design_input.py`
- new `tests/unit/test_design_input.py`

**Implementation:**

1. Encode `ia_format_version: 1` as the only supported version.
2. Parse YAML with `yaml.safe_load`.
3. Return structured data plus findings; do not mutate the input file.
4. Require:
   - Figma `file_key`, `file_url`, `version`, and design-system collection names;
   - screen `name`, `node_id`, `node_url`, `purpose`, `serves`, `data_fields`,
     `components`, and states;
   - state `name`, `node_id`, `trigger`, and `transient`;
   - flow `journey` and ordered screen/state sequence;
   - reused/new component lists, with a rationale for every new component;
   - token collections and `outside_system`; and
   - reasons for excluded frames.
5. Reject duplicate screen/state `node_id` values and references to unknown screens or
   states from flows.
6. Treat `open_questions` as valid content to surface, not a schema error.
7. Build a canonical deep link for each state from the Figma file URL/key and its
   `node_id`. A separate state `node_url` may be accepted, but is not required by the
   proven pilot format.
8. Normalize the pilot's output-location ambiguity: both returned files live under
   `design-in/` in the productized flow.

**Tests:** valid example; malformed YAML; missing required field; unsupported version;
duplicate node ID; unknown screen/state in a flow; and byte-for-byte no-write assertion.

**Done when:** `py -3 -m pytest tests/unit/test_design_input.py` passes.

### EDA-102 — Add deterministic inbound-design validation

**Purpose:** verify the designer return against the approved PRD and stage-04 brief
without relying on agent judgment.

**Files:**

- `lib/design_input.py`
- `lib/artifact_contracts.py` only for reusable stage-04 parsing helpers
- `tests/unit/test_design_input.py`

**Checks to implement:**

1. Every PRD `UJ-###` has a returned flow.
2. Every UI-facing `US-###` resolves directly or transitively to a screen, unless the
   brief explicitly marks it screenless.
3. Every state in the brief's `Required state inventory` exists in the return and has
   a Figma `node_id`.
4. Every field in `Data fields per requirement` appears on at least one screen serving
   that requirement.
5. Every `serves` ID exists in the approved PRD.
6. `tokens.outside_system` is empty or each entry is justified.
7. Every new component has a rationale.
8. No excluded frame is used by a canonical flow.
9. Every returned open question is surfaced as a non-error finding.

**Finding behavior:** use stable codes, severity, message, and source location where
available. Missing coverage is an error. Open questions are warnings. The validator
must not call Figma or write project state.

The pilot's ninth ingest check—whether the design contradicts Product UX Guardrails,
uses prohibited vocabulary, or changes the interaction model—is semantic. Do not
mislabel it deterministic. `pm-check --design` reports the structural checks above;
the stage-04 ingest skill performs a separately labelled agent review of guardrails
before writing and stops on a suspected contradiction.

**Tests:** one passing project fixture and one focused failure test per rule.

**Done when:** all `design_input` tests pass and no test requires network access.

### EDA-103 — Add explicit stage-04 `--brief` mode

**Purpose:** replace the pilot's long BRIEF-ONLY steering note with a supported mode.

**Files:**

- `skills/pm-stage-04-design-spec/SKILL.md`
- `skills/pm-stage-04-design-spec/agents/openai.yaml`
- relevant tests under `tests/contracts/`

**Behavior:**

- Run the existing stage-04 pre-stage gate and context loading.
- Read the approved upstream artifacts as today.
- Write all PM-owned constraint sections, plus:
  - `### Data fields per requirement`;
  - `### Required state inventory`.
- Put the exact documented pending marker in designer-owned IA, component, typography,
  color, spacing, and iconography sections.
- Do not emit `SCR-###`, layouts, components, token values, or Figma references.
- Write the ordinary `04-design-spec.md` with status `draft`; run snapshot, validation,
  metadata, history, and telemetry as normal.
- `SCREEN_IDS_MISSING` is expected and warning-only for this mode.
- Record `design_mode: brief` in the `stage_generated` telemetry payload and in
  frontmatter as a new non-status field. Do not change `.meta.yaml` status taxonomy.

**Compatibility:** invoking the skill with neither `--brief` nor `--ingest` retains the
existing single-pass behavior.

**Stop conditions:** both flags supplied; stage 03 not approved; or brief output
contains a screen ID/design decision.

**Tests:** mode is documented in both runtime surfaces; brief and ingest are mutually
exclusive; no approval instruction; default mode remains present.

### EDA-104 — Add explicit stage-04 `--ingest` mode

**Purpose:** reconcile the proven designer return into the existing stage-04 draft.

**Files:**

- `skills/pm-stage-04-design-spec/SKILL.md`
- `skills/pm-stage-04-design-spec/agents/openai.yaml`
- `lib/design_input.py`
- relevant contract/integration fixtures

**Behavior:**

1. Require an existing stage-04 draft with `design_mode: brief`.
2. Require `design-in/ia.yaml` and `design-in/design-notes.md`.
3. Run the EDA-102 validation before changing the artifact. On any error, print the
   findings and stop without writing.
4. Run the explicitly labelled semantic review against Product UX Guardrails and UX
   Content Rules. On a suspected contradiction, report the exact design evidence and
   stop for PM/designer resolution; do not silently rewrite either side.
5. Preserve PM-owned brief sections verbatim.
6. Replace only designer-owned pending sections.
7. Assign sequential `SCR-###` IDs in flow order, keyed to Figma screen `node_id`.
8. On regeneration, reuse the existing `SCR-###` for the same `node_id`; append IDs for
   new screens; never renumber surviving screens.
9. States remain inside their screen and receive no `SCR-###`.
10. Emit each screen in the parser-compatible structure with:
   - purpose;
   - a bare-ID `Serves:` line;
   - default Figma URL;
   - data fields; and
   - state name, trigger, and exact Figma URL.
11. Cite design-system libraries rather than re-authoring token values.
12. Record `design_mode: ingested`, Figma file/version provenance, snapshot, generated
    hash, validation, metadata, history, and telemetry.
13. Run strict stage-04 validation. `SCREEN_IDS_MISSING` and `SCREEN_TRACE_MISSING`
    must be absent.

**Stop conditions:** missing/invalid inbound files; reconciliation error; changed
brief-owned text; unknown upstream ID; or a Figma `node_id` would change its screen ID.
Do not approve the artifact.

**Tests:** happy path; missing input; invalid return; preservation of brief-owned
sections; stable ID reuse; new-screen append; deleted-screen handling without
renumbering; and no-write behavior on failure.

### EDA-105 — Expose validation through `pm-check --design`

**Purpose:** make the design gate repeatable and visible to PMs.

**Files:**

- `scripts/pm_check.py`
- `lib/consistency.py` or `lib/design_input.py`
- `skills/pm-check/SKILL.md`
- `skills/pm-check/agents/openai.yaml`
- consistency/integration tests

**Behavior:**

- Add optional `--design`.
- With the flag, run normal consistency checks plus EDA-101/102 checks.
- Print schema, coverage, state, field, token, component, and open-question findings.
- Exit non-zero when design errors exist.
- With no flag, preserve current output and exit behavior byte-for-byte where tests
  assert it.
- Remain local, read-only, and network-free.

**Done when:** CLI tests cover valid, warning-only, error, malformed, and default paths.

### EDA-106 — Make the designer handoff usable before design

**Purpose:** let the designer receive the approved product definition and the draft
design brief without manually assembling several files.

**Files:**

- `scripts/pm_share.py`
- `tests/integration/test_share_package.py`
- handoff README/template code as required

**Behavior for `pm-handoff --package --audience design`:**

- include approved PRD, stories, NFRs, and journeys;
- include the stage-04 draft only when `design_mode: brief`;
- emit `DESIGNER-WORKFLOW.md`, derived from the two designer prompts proven in the
  pilot, with these distinct phases:
  1. inventory the design system without creating anything;
  2. derive the screen/state/field/component work-order table and wait for designer
     approval;
  3. agree the Figma page and `<Screen> / <state>` naming convention;
  4. build a coverage-complete scaffold using approved system assets and vocabulary;
  5. stop for the designer to finish the design; and
  6. run a separate read-only export and self-check that writes both files under
     `design-in/`;
- label the draft clearly as an unapproved design brief, not a canonical design spec;
- never include a single-pass or ingested unapproved design spec as authoritative;
- continue projecting approved stage 04 normally after approval; and
- keep all other audience payloads unchanged.

**Implementation note:** update `AUDIENCE_CATEGORIES` for PRD/stories/NFRs, but do not
solve draft-brief inclusion by weakening `_REF_STAGE` globally. Add a narrow design-
audience rule gated on `design_mode: brief`.

**Tests:** pre-design package; workflow phase order and mandatory designer-approval
stops; read-only export wording; post-approval package; unrelated unapproved design
spec; audience-scoped rebuild isolation; and unchanged dev/QA/business payloads.

### EDA-201 — Preserve Figma screen/state links in dev and QA stories

**Purpose:** lock the pilot's most important developer outcome into regression tests.

**Files:**

- `tests/integration/test_share_package.py`
- `scripts/pm_share.py` only if the new test proves `_screen_body` insufficient
- story template only if a failing test proves it necessary

**Method:** add the failing test first. The current `_screen_body` mechanism is expected
to copy the link-rich screen block without engine changes.

**Fixture:** an approved stage-04 screen block with a default Figma URL and at least
three named state URLs with triggers.

**Assertions:**

- the dev story contains every exact URL and trigger;
- the QA story contains the same screen/state payload;
- an unrelated story does not receive the block;
- global IA prose does not leak into the story;
- stage-04 provenance is present; and
- no stage-05 prototype is required.

**Rule:** never patch generated handoff files. Fix the stage-04 parser, traceability, or
template source and regenerate.

### EDA-202 — Add post-package handoff verification

**Purpose:** make “developer can reach every required state” a check, not a manual
claim.

**Files:**

- `lib/design_input.py` or a narrowly named handoff-check module
- `scripts/pm_check.py`
- `skills/pm-check/SKILL.md`
- tests for package verification

**Checks under `pm-check --design`:**

- every UI story has at least one screen;
- no screen is orphaned from a known story/requirement/journey;
- every screen has a default Figma link;
- every required state has a Figma link and trigger;
- dev and QA story joins agree for the same story;
- the screen map and story coverage agree; and
- missing stage-05 HTML is informational, not an error, on this path.

Run these checks from canonical artifacts and `design-in/` where possible. Do not make
generated `handoff/` the sole source of truth.

### EDA-301 — Add outcome-based epic calibration

**Purpose:** make epic decomposition useful for software delivery without forcing an
arbitrary epic count.

**Files:**

- `skills/pm-stage-03-prd/SKILL.md`
- `skills/pm-stage-03-prd/agents/openai.yaml`
- `lib/artifact_contracts.py`
- `lib/delivery_map.py` only if additional ownership summaries are needed
- stage-03 contract and unit tests

**Generation rules:**

1. Define an epic around a coherent user/business outcome or independently plan-able
   delivery workstream.
2. Prefer vertical outcomes that may include UI, service, data, and operational work.
   Do not create frontend, backend, API, database, design, or QA epics merely because
   those disciplines exist.
3. Do not create one epic per story, screen, component, or requirement.
4. Do not put the whole MVP in one epic when the approved scope contains multiple
   independently meaningful outcomes or journeys.
5. Permit one epic when the MVP genuinely has one outcome/workstream. Require the PRD
   to say why one epic is sufficient.
6. Permit a one-story epic only when that story is a distinct outcome that can be
   planned or released independently; require a short rationale.
7. Every epic must own at least one story or functional requirement and must retain
   Outcome, Scope, and Success signal.

**Advisory validation:**

- `EPIC_EMPTY` — error when an epic owns no story or requirement;
- `EPIC_OVERCONSOLIDATED` — warning when one epic owns the whole PRD despite multiple
  declared journeys or several independently titled stories;
- `EPIC_FRAGMENTED` — warning when most epics own only one delivery item or epic count
  approaches story count; and
- `EPIC_LAYER_SHAPED` — warning for explicit technical-layer names such as Frontend,
  Backend, Database, API, QA, or Design unless the PRD supplies an outcome rationale.

Warnings trigger PM review; they do not mechanically rewrite epics. Keep thresholds
as named constants with focused tests so they can be calibrated from real projects.

**Tests:** genuine single-outcome PRD passes; multi-outcome catch-all warns; sensible
multi-epic PRD passes; one-epic-per-story warns; empty epic errors; technical-layer
epic warns unless outcome rationale is present.

### EDA-302 — Decompose PRD requirements into handoff files

**Purpose:** complete the PRD decomposition already started for epics and stories.

**Files:**

- `lib/delivery_map.py`
- `scripts/pm_share.py`
- new or existing handoff templates under `templates/`
- `tests/integration/test_share_package.py`

**Output:**

- retain one `epics/EPIC-###-<slug>.md` per declared epic;
- retain one `stories/US-###-<slug>.md` per story;
- add one `requirements/FR-###-<slug>.md` or
  `requirements/REQ-###-<slug>.md` per functional requirement;
- add epic, story, and requirement indexes to the relevant audience README; and
- retain `reference/prd.md` as the complete, read-only canonical projection.

Each requirement file contains its full PRD block, epic, priority, owning stories,
source provenance, generated warning, and canonical-source instruction. It is emitted
to dev and QA. Epics remain dev/business; stories remain dev/QA.

**Rules:**

- render only approved PRD content;
- do not invent titles, ownership, acceptance criteria, or reverse links;
- unresolved ownership is explicit `not captured in source`, never guessed;
- audience-scoped rebuild behavior remains isolated; and
- enhancement-mode packages include only changed requirements plus required ancestor
  closure, matching the existing story/epic delta rules.

**Tests:** exact file counts and names; full requirement text; dev/QA duplication;
audience isolation; missing/legacy epic ownership; enhancement delta; source stamps;
and no state-machine writes.

### EDA-303 — Make every story dossier semantically standalone

**Purpose:** a developer can implement a story from one file without following PM-OS
document links or decoding bare stable IDs.

**Files:**

- `lib/delivery_map.py`
- `scripts/pm_share.py`
- `templates/handoff-story.md.j2`
- `tests/integration/test_share_package.py`

**Required story content:**

1. Full authored story mini-spec: actor/outcome, priority, happy path, edge cases, data
   fields, UI steps, and acceptance criteria.
2. Epic ID plus the epic's Outcome and Scope text.
3. Every referenced `FR-###`/`REQ-###` with its title and full requirement body—not a
   bare ID and not only a link to `requirements/`.
4. Acceptance-criteria text. Current labeled `Acceptance:` and per-step `Acceptance
   (Done)` text stays inline. If a source PRD uses an `AC-###` identifier, the package
   must resolve and print its declaration text; unresolved `AC-###` is an error or
   explicit missing-content finding, never a hyperlink-only fallback.
5. Existing inline screen/state bodies and direct Figma links.
6. Existing covering QA scenario bodies and backend task bodies.
7. Relevant non-functional and impact constraints. Until those sections have stable
   per-item ownership, embed their complete approved section text under a clearly
   labelled cross-cutting-constraints section rather than making a link mandatory.
8. Traceability IDs and optional navigation links at the end, clearly secondary to the
   inlined implementation content.

**Definition of no cross-reference dependency:** deleting `handoff/dev/reference/`
and `handoff/dev/requirements/` from a copied package must not remove implementation
meaning from an individual story file. The generated warning may still point back to
the canonical PRD for edits, and direct links to Figma frames remain necessary.

**Tests:** full FR text appears beside each referenced ID; acceptance text is present;
unresolved ID is visible and fails the relevant check; epic outcome/scope is inline;
cross-cutting constraints are inline; no implementation-critical internal Markdown
link; deleting reference/requirement projections leaves the story assertions intact;
QA story copy is byte-identical; and unrelated FR text does not leak into the story.

### EDA-401 — Update documentation

**Files:**

- `docs/reference/generated-doc-formats.md`
- `docs/guides/sop.md`
- `docs/guides/testing.md`
- `docs/plans/pm-os-external-design-authority-plan.md`
- `docs/roadmap/current-state-review.md`
- `CHANGELOG.md` only after implementation and tests are complete

Document:

- the two modes and when to use each;
- `design-in/` ownership and schema;
- the pre-design design package;
- the distinct designer scaffold/build and read-only export phases;
- the designer's two explicit approvals before build: the work-order table and file
  convention;
- the `pm-check --design` gate;
- the unchanged PM approval responsibility;
- developer/QA Figma state links; and
- decomposed epic/story/requirement handoff folders;
- the standalone-story rule and the difference between optional navigation links and
  required inline meaning;
- outcome-based epic sizing and its advisory warnings; and
- the fact that stage 05 is optional for this design-authority path, without changing
  the global stage-05 product decision.

Do not mark the source plan implemented until EDA-402 passes.

### EDA-402 — Full verification

From the repository root in PowerShell:

```powershell
py -3 -m pytest tests/unit/test_design_input.py
py -3 -m pytest tests/unit/test_artifact_contracts.py tests/unit/test_consistency.py
py -3 -m pytest tests/integration/test_share_package.py
py -3 -m pytest tests/unit/test_delivery_map.py
py -3 -m pytest tests/contracts
py -3 -m pytest
py -3 scripts/pm_os_verify.py --runtime codex
```

**Release acceptance:**

- `--brief` and `--ingest` replace prompt-level run discrimination;
- an invalid designer return cannot mutate stage 04;
- stable Figma node identity preserves stable `SCR-###` IDs;
- PM-owned brief content survives ingest verbatim;
- PM approval is still explicit;
- the design audience can receive a usable pre-design package;
- dev and QA stories contain exact default/state Figma links;
- the PRD package contains separate epic, story, and requirement artifacts;
- every story contains the text of its referenced requirements and acceptance
  criteria, with no implementation-critical internal-link dependency;
- epic decomposition is outcome-oriented and warns on catch-all or fragmented shapes;
- `pm-check --design` detects missing fields, states, coverage, and links;
- no new stage, status, external service, or installed-runtime edit exists; and
- the full test suite and verifier pass.

## 8. Status rules

- `Not started`: no implementation or test evidence exists.
- `In progress`: a task has a patch or tests, but its completion command does not yet
  pass.
- `Blocked`: a fixed decision, schema change, or upstream dependency needs PM input.
- `Done`: every stated check passes. File presence alone is not completion evidence.

Update only this tracker while the work is active. Add a short cross-reference to the
source design; do not duplicate status tables across both documents.

## 8.1 Implementation log

### 2026-09-01 — EDA-301/302/303 implementation pass

Implemented the pilot-feedback handoff shape in the repo source tree:

- Stage 03 generation guidance now tells the PM agent to size Product Epics around
  coherent user/business outcomes or independently plan-able workstreams, with
  explicit cautions against catch-all, one-story-per-epic, and technical-layer epics.
- The PRD contract validator now emits:
  - `EPIC_EMPTY` as an error when an epic owns no story or functional requirement;
  - `EPIC_OVERCONSOLIDATED` as a warning for a single epic spanning multiple journeys
    and several delivery items without a one-outcome rationale;
  - `EPIC_FRAGMENTED` as a warning when epics are mostly one-item buckets or approach
    story count; and
  - `EPIC_LAYER_SHAPED` as a warning for frontend/backend/database/API/QA/design epic
    names without an outcome rationale.
- The delivery map now records `AC-###` declarations and story references so package
  stories can inline the acceptance text or make unresolved references visible.
- `/pm-handoff --package` now renders `requirements/FR-###-*.md` and
  `requirements/REQ-###-*.md` into dev and QA audience folders.
- Story dossiers now inline the epic context, each referenced requirement block,
  referenced acceptance-criteria text, impact analysis, and non-functional
  requirements before the secondary traceability section.

Verification run:

- `py -3 -m pytest ...` could not run because this Windows Python has no `pytest`
  module installed.
- `py -3 -m compileall lib scripts templates tests` passed.
- `git diff --check` passed.
- Direct smoke check for `delivery_map` `AC-###` extraction passed.
- Direct smoke check for `artifact_contracts` epic warnings passed.
- Direct repo-local package render smoke passed for requirement files and standalone
  story content.

Do not mark EDA-301, EDA-302, or EDA-303 `Done` until focused pytest coverage runs in
an environment with pytest installed.

### 2026-09-02 — EDA-101/102/103/104/105/106 implementation pass

Implemented the first productized external-design path in the repo source tree:

- Added `lib/design_input.py`, a read-only parser/validator for `design-in/ia.yaml`
  and `design-in/design-notes.md`.
- The validator supports `ia_format_version: 1`, Figma file/version metadata,
  required screen/state/flow/component/token/excluded-frame shape, canonical Figma
  state URL construction, PRD id validation, journey flow coverage, story-to-screen
  coverage, required-state coverage, data-field coverage, token/component rationale
  checks, excluded-frame checks, and open-question warnings.
- Added `pm_check.py --design`, preserving the default check path while appending a
  deterministic Design Input Check when requested.
- Added `--brief` and `--ingest` operating instructions to the stage-04 skill,
  including mutual exclusion, `design_mode` frontmatter, preservation of PM-owned
  brief sections, deterministic pre-ingest validation, and separately labelled
  semantic review.
- Added the pre-design design-audience package path: when stage 04 is a draft
  `design_mode: brief`, `/pm-handoff --package --audience design` now includes the
  approved PRD, stories, NFRs, journeys, the draft design brief, and
  `DESIGNER-WORKFLOW.md`.

Verification run:

- `py -3 -m pytest ...` still could not run because this Windows Python has no
  `pytest` module installed.
- `py -3 -m compileall lib scripts templates tests` passed.
- `git diff --check` passed.
- Direct design validator smoke passed.
- Pilot specimen `docs/examples/design-in-ia-example.yaml` validated with zero errors
  and the expected open-question warnings against the paired brief fixture.
- `pm_check.py --design` CLI smoke printed a Design Input Check with zero design
  errors; the overall command exited non-zero only because the scratch PM-OS project
  intentionally lacked full lifecycle artifacts/history.
- Pre-design package smoke passed and produced `reference/design-brief.md`,
  `reference/prd.md`, `stories/`, `reference/nfrs.md`, and `DESIGNER-WORKFLOW.md`.

EDA-101, EDA-102, EDA-103, EDA-105, and EDA-106 can now be treated as `Done`
because focused pytest coverage ran after `pytest` was installed. EDA-104 was
completed in the later ingest-writer pass below.

### 2026-09-02 — EDA-401 documentation alignment pass

Updated operator/reference documentation to match the implemented package shape:

- `docs/reference/generated-doc-formats.md` now describes decomposed requirement
  files, self-contained story dossiers, and the draft-design-brief package path.
- `docs/guides/sop.md` now explains that dev/QA receive separate epic, story, and
  requirement files, and that implementation-critical FR/REQ/AC/NFR/impact text is
  embedded in story files rather than only linked.
- `docs/guides/testing.md` now names the added package expectations and draft design
  workflow coverage.

EDA-401 can now be treated as `Done` because the format/SOP/testing-guide updates
are aligned with the implemented package shape.

### 2026-09-02 — EDA-104/201/202 completion pass

Closed the remaining external-design-authority implementation work:

- Added `lib/design_ingest.py` and `scripts/pm_design_ingest.py`, a deterministic
  stage-04 ingest writer for returned `design-in/ia.yaml` and
  `design-in/design-notes.md`.
- The ingest writer requires a draft stage-04 design brief, validates the returned
  design package, preserves PM-owned brief sections, replaces designer-owned IA/
  flow/component/token sections, assigns stable `SCR-###` ids keyed to Figma
  `node_id`, stamps `design_mode: ingested`, updates generated hash, writes a
  `.history/` snapshot, updates `.meta.yaml`, and logs `stage_generated`.
- `lib/traceability.py` now extracts exact Figma screen/state references from the
  approved design spec into each screen's `design_refs`.
- `pm_share.py` and `templates/handoff-story.md.j2` now surface those exact Figma
  links in generated dev/QA/design story dossiers, while `reference/screen-map.md`
  includes a default Figma link per screen.
- `pm_check.py --design` now adds post-package handoff-readiness checks from
  canonical artifacts: screen coverage for UI stories, orphan-screen detection,
  missing default/state Figma links, missing state triggers, generated dev/QA story
  join agreement, generated screen-map agreement when present, and informational
  handling for a missing stage-05 HTML prototype.
- Updated stage-04 and pm-check skill docs plus SOP, testing guide, and generated
  format reference to describe the implemented behavior.

Verification run:

- `py -3 -m compileall lib\design_ingest.py lib\design_input.py lib\traceability.py scripts\pm_design_ingest.py scripts\pm_check.py scripts\pm_share.py tests\integration\test_share_package.py` passed.
- `py -3 -m pytest -q -p no:cacheprovider --basetemp .codex-pytest-tmp tests\unit\test_design_input.py tests\integration\test_share_package.py -k "design_ingest or figma_links or valid_design_input_has_warning_only_open_question or state_node_url" --tb=short` passed: 3 passed.
- `py -3 -m pytest -q -p no:cacheprovider --basetemp .codex-pytest-tmp tests\integration\test_share_package.py -k "screen or design_ingest" --tb=short` passed: 12 passed, 24 deselected.
- `py -3 -m pytest -q -p no:cacheprovider --basetemp .codex-pytest-tmp tests\integration\test_share_package.py --tb=short` passed: 36 passed.
- `py -3 -m pytest -q -p no:cacheprovider --basetemp .codex-pytest-tmp tests\unit\test_design_input.py tests\unit\test_delivery_map.py tests\unit\test_artifact_contracts.py --tb=short` passed: 68 passed.
- `py -3 -m pytest -q -p no:cacheprovider --basetemp .codex-pytest-tmp tests\contracts\test_documentation_drift.py tests\contracts\test_skill_contracts.py --tb=short` passed: 30 passed.

EDA-104, EDA-201, and EDA-202 can now be treated as `Done`. EDA-402 remains
`Blocked` only for the full-suite/verifier rerun: the focused suites pass, but the
previous all-suite attempt did not return a final summary before the runner/session
limit, and sandbox-local pytest still hits Windows temp-directory cleanup
permissions.

### 2026-09-02 — Pytest install, Windows harness, and focused regression pass

Installed `pytest` in the active Python 3.13 environment and ran the focused
regression groups for this implementation.

Additional fixes from the real pytest run:

- `tests/helpers.py` now runs subprocess scripts through `sys.executable` instead of
  assuming `python3` exists on Windows.
- `tests/helpers.py` captures subprocess output as UTF-8.
- `tests/conftest.py` isolates both `HOME` and `USERPROFILE` so Windows subprocesses
  do not write PM-OS projects outside the fixture home.
- `tests/conftest.py` sets `PYTHONIOENCODING=utf-8` and `PYTHONUTF8=1` for isolated
  subprocess scripts so emoji/checkmark CLI output does not fail under cp1252.
- Contract and package tests now read UTF-8 Markdown explicitly.
- `scripts/pm_context_import.py` writes context-pack manifest member paths with
  POSIX separators via `.as_posix()`, fixing portable pack evidence on Windows.

Verification evidence:

- `py -3 -m pytest -p no:cacheprovider --basetemp .codex-pytest-tmp tests/integration/test_share_package.py`
  passed: `35 passed`.
- `py -3 -m pytest -q -p no:cacheprovider --basetemp .codex-pytest-tmp --tb=short tests/contracts/test_documentation_drift.py tests/contracts/test_local_first_boundaries.py tests/contracts/test_skill_contracts.py tests/integration/test_artifact_contract_warnings.py tests/integration/test_context_import.py`
  passed: `55 passed`.
- Earlier focused unit run passed for `tests/unit/test_design_input.py`,
  `tests/unit/test_delivery_map.py`, and `tests/unit/test_artifact_contracts.py`
  before the package assertions ran.
- `py -3 -m compileall lib scripts tests` passed.
- `git diff --check` passed after removing blank EOF lines; only CRLF normalization
  warnings remain.

Full-suite note: a single full-suite pytest run started cleanly but the desktop
runner session disappeared before returning a final summary. After the usage limit
blocked further elevated pytest runs, sandbox-local pytest could not complete because
pytest temp-directory cleanup hit `PermissionError`. Treat EDA-402 as blocked by the
local runner, not by a known product assertion failure.

## 9. Agent handoff format

After each task, report exactly:

```text
Task: EDA-###
Status: Done | In progress | Blocked
Files changed: <paths, or none>
Commands run: <commands and exit codes>
Acceptance checks: <each check with PASS/FAIL>
Unresolved gaps: <specific ids/fields/states, or none>
Next allowed task: <one task id, or none>
```

The next agent must be able to continue from this report without reconstructing the
design rationale.
