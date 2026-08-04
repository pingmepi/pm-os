---
name: pm-handoff
description: Export the approved PM-OS pipeline — a raw text dump of one or all stages, a readable per-audience handoff package (dev/design/qa/business), or Jira tickets (connector or offline CSV). The single callable skill for all PM-OS export.
model_tier: utility
reads: ["01-brief.md", "02-scope.md", "03-prd.md", "04-design-spec.md", "05-prototype-mockup.html", "06-qa-plan.md", "08-trd.md", ".traceability.yaml"]
writes: ["handoff/**"]
---

# Role and goal

Export the approved PM-OS pipeline in whichever shape the PM needs. This is
the **single callable skill** for all export — it absorbs what used to be a
separate `pm-share` skill (raw text dump, and the readable `--package`
handoff package) alongside the existing Jira ticket export. `scripts/pm_share.py`
still does the raw/package mechanics; `scripts/pm_handoff.py` still does the
Jira mechanics — only the skill-level entrypoint changed.

# Modes

`$ARGUMENTS` is parsed as prose, same as before — look for `--package` or
`--raw` first (mutually exclusive with each other and with the Jira flow); if
neither is present, this is the **Jira flow** (unchanged default).

| Invocation | Mode |
|---|---|
| *(bare)* | Jira export, tracker=jira (default, unchanged) |
| `jira` | Jira export, explicit form of the default |
| `jira --offline` / `csv` | Jira export, offline CSV route |
| `--package` | Package build, all 4 audiences (`handoff/{dev,design,qa,business}/`) |
| `--package --audience <dev\|design\|qa\|business>` | Package build, one audience only |
| `--package [--audience ...] --html` | Package build + an `index.html` per built audience folder |
| `--raw [stage_id]` | Plain text dump of one stage or all approved stages |

`--package` and `--raw` never touch Jira. The Jira forms never touch the
local package **except** the implicit refresh below.

## Implicit local-package refresh before the Jira flow

When the invocation resolves to the **Jira flow** (bare, `jira`, or
`jira --offline`/`csv`), first run an implicit **Step 0**: a full package
rebuild (`pm_share.py --package`, all four audiences, no `--audience`
restriction, no `--html`) *before* Step 1's dry-run plan. The local,
human-readable package should reflect the same approved snapshot the Jira
tickets are about to be built from — running the Jira flow refreshes both.

- **Skip it** with `--no-package-refresh` if you only want the Jira flow
  without touching local docs (e.g. re-running ticket creation after a
  network failure, where the docs are already current).
- **If the implicit refresh fails** (e.g. PRD not approved — the same gate
  `--package` already enforces), **stop** — do not proceed to the Jira flow
  with stale or missing local docs. Report the failure exactly as `pm_share.py`
  reports it.
- Print a one-line status once it succeeds, e.g. `Local handoff package
  refreshed (handoff/{dev,design,qa,business}/).`, then continue into Step 1
  below.

# Package mode (`--package`)

A read-only **projection** of the canonical stage artifacts — never touches
gate, hash, status, or staleness. Run:

```bash
python3 ~/.pm-os/scripts/pm_share.py --package [--audience dev|design|qa|business] [--html] [--output DIR]
```

Writes into `handoff/<audience>/` at the project root (or `--output <dir>`)
for each requested audience:
- `README.md` — index + reading guide + provenance, scoped to what's actually
  in that audience folder.
- `00-overview.md` (business) — Business Perspective (Who / What & Why / How).
- `epics/EPIC-###-*.md` (dev, business) — one story/requirement index per
  Product Epic declared in the PRD.
- `stories/US-###-*.md` (dev, qa) — one self-contained story per file,
  including the `SCR-###` screens that story touches (with a link into the
  interactive prototype for each, when available), the QA scenarios covering
  it, and — when the TRD (stage 08) is approved — the `TSK-###` backend/
  technical tasks that implement it.
- `reference/` — `prd.md` (dev — the full approved PRD) and `trd.md` (dev —
  the full approved TRD, or a note when stage 08 is not approved); `design-spec.md`
  (design — the full approved design spec, or a note when stage 04 is not
  approved); `user-journeys.md` (all four), `prioritization.md` (dev,
  business), `impact-analysis.md` (dev, qa, business), `nfrs.md` (dev, qa),
  `qa-scenarios.md` (qa), `screen-map.md` (design, qa — the reverse view:
  each screen, the stories it serves, and a prototype link). The `prd`/`trd`/
  `design-spec` entries are full read-only projections of the source artifact
  (stamped with its content hash), so each audience has the whole document
  behind the decomposed stories/epics, not only the derived fragments.
- `wireframes/prototype.html` (dev, design, qa) — the approved stage-05
  prototype, copied in, if present.
- `--html` also emits an `index.html` inside each built audience folder.

A lightweight `handoff/README.md` **hub** (not itself audience-scoped) always
lists whichever audience folders currently exist on disk, plus a pointer to
`jira-plan.md`/`jira-import.csv` if either is present at the `handoff/` root
— those are the Jira export's files, never inside an audience folder.

**`--audience` scopes the rebuild** to exactly that one subfolder — every
other audience folder already on disk (built in an earlier run) is left
completely untouched. Omitting `--audience` rebuilds all four in one pass.
Regenerate just the audience(s) affected by a stage re-approval, or all four
if unsure.

**Critical: the package is derived, not canonical.**
- **Never edit files under `handoff/`.** They are regenerated wholesale (per
  audience folder) on each run and are not tracked by the state machine — a
  hand-edit there is silent drift, not a change to the product. To change
  content, edit the canonical stage artifact (e.g. `03-prd.md`) and re-run
  `/pm-handoff --package`.
- Sections with no source content are printed as `— not captured in source —`
  rather than invented. Treat that list as a coverage checklist showing where
  the PRD/QA is thin relative to the house format. Surface it to the PM if
  prominent; do not fabricate.
- Requires at least an approved PRD (`03-prd.md`). If it is missing, the
  script exits with an error — stop and tell the PM to approve the PRD first.
- Screens come from the **approved** design spec's `SCR-###` inventory. If
  stage 04 is not approved, or predates screen ids, every story shows
  `— not captured in source —` for screens and the screen map says so;
  mention it to the PM rather than leaving them to notice the blanks.
- A screen link only appears once the prototype actually carries a matching
  `id="SCR-###"` anchor (added by `pm-prototype-html`, `prompt_version >=
  0.3.0`). A prototype generated before that requirement still copies into
  `wireframes/`, and the story/screen-map still links to it — just without
  jumping straight to the screen. Regenerate it standalone
  (`/pm-prototype-html`, no re-approval needed — the mockup is a rendered
  companion file, not a hash-gated stage artifact) to get direct anchors.

After running in package mode, confirm the output location(s) and remind the
PM the package is read-only and should be regenerated after any PRD/QA/design
re-approval — the script already prints this; relay it, don't paraphrase it away.

# Raw mode (`--raw [stage_id]`)

```bash
python3 ~/.pm-os/scripts/pm_share.py [stage_id] [--output FILE]
```

A single stage or every approved/edited stage, concatenated verbatim — for a
quick paste into email/Slack/a doc. Pass through only the raw-relevant part
of `$ARGUMENTS` (an optional `stage_id` and `--output`) verbatim; do not
interpret, validate, or reformat them. Report the script's output as-is.

# Jira flow

Turn the **approved** product pipeline into tracker tickets, keyed to PM-OS's
stable ids so the two systems stay linked. The single supported tracker is
**Jira** (via the Atlassian MCP connector). Each PRD Product Epic (`EPIC-###`)
becomes a Jira **Epic**; each PRD user story (`US-###`) becomes a **Story** under
its declared epic; each functional requirement (`FR-###`/`REQ-###`) becomes a
**Task** under its declared epic; each approved TRD task (`TSK-###`) becomes a
**Subtask** when it implements exactly one exported Story/Task. A task that spans
multiple refs in one epic becomes a Task under that epic; cross-epic or unresolved
tasks stay unparented for PM review.

This is an **outward-facing, side-effectful** action: it creates real objects in
the PM's Jira. The flow is therefore strict: **(implicit package refresh) →
dry-run → PM confirms → create → record**. You never create or modify a Jira
object without an explicit human "yes" in this conversation, and you only ever
store ticket keys/ids locally — never bulk copies of Jira data.

`$ARGUMENTS` may name the tracker (`jira`); if omitted, assume `jira`. Any other
tracker is not supported in this phase — say so and stop. `$ARGUMENTS` may also
carry `--offline` (or `csv`), which switches to the CSV route below — the PM
imports the file themselves and no connector is involved.

## Preconditions

1. **Approved PRD.** Stage 03 must be `approved`. The script enforces this and
   exits with an error otherwise — stop and tell the PM to `/pm-approve 03`.
2. **Jira connector authorized.** Creating tickets requires the Atlassian MCP to
   be connected and authorized for this session. If it is not available, **stop**
   before creating anything and tell the PM to authorize the Atlassian/Jira
   connector (claude.ai connector settings, or `/mcp` in an interactive session) —
   or to use the **offline CSV route** below, which needs no connector. Offer both;
   do not ask the PM for tokens or credentials.
3. **Target Jira project.** You need the destination Jira project key (e.g.
   `RA`). If the PM has not given it, ask for it before creating anything.

## Step 1 — Build the dry-run plan (no network)

```bash
python3 ~/.pm-os/scripts/pm_handoff.py plan
```

This writes `handoff/jira-plan.md` (PM-readable) and `handoff/jira-plan.json`
(the machine map) at the `handoff/` root — never inside an audience folder, so
this can never collide with a package build regardless of run order. It touches
nothing external. Read `handoff/jira-plan.md` and present its summary to the
PM: how many epics / stories / tasks, and — if any — the unparented/unassigned
items (missing Product Epic ownership or cross-epic TRD tasks). Call those out
explicitly; the PM may want to fix ownership in the PRD/TRD first rather than
create standalone tickets.

## Step 2 — STOP and get explicit confirmation

Do **not** create anything yet. Show the PM the plan and the target Jira project,
and ask for an explicit go-ahead, e.g.:

> Ready to create in Jira project **RA**: 2 epics, 3 stories, 3 tasks (2
> unparented/unassigned — review these first). Nothing has been created yet.
> Create them?

Wait for a clear "yes". If the PM wants changes, they edit the canonical stage
artifact (`03-prd.md` / `08-trd.md`), re-approve, and you re-run Step 1 — never
hand-edit `handoff/`. If the PM says no, stop.

## Step 3 — Create the tickets via the Atlassian MCP

Only after an explicit yes. Read `handoff/jira-plan.json` and create objects in
dependency order using the Atlassian/Jira MCP tools:

1. Create every **Epic** first (the items with `type: "Epic"`). Use its `summary`
   and `description`. Record the returned Jira key against its `ref`.
2. Create every **Story** and **Task**, setting each one's parent/epic link to
   the Jira key of the epic named by its `parent_ref` when present. If `parent_ref`
   is empty, create the item standalone and mention it in the PM summary. Use each
   item's `summary` and `description`; for tasks, the `implements` ids are useful
   context to include.
3. Create every **Subtask** after its Story/Task parent exists, using the Jira key
   of the item named by `parent_ref`.

Build a flat map of `{ stable-id: created-jira-key }` as you go, e.g.
`{"US-001": "RA-1", "FR-001": "RA-2", "TSK-001": "RA-3"}`.

**If creation fails partway:** stop creating, keep the map of what *did* succeed,
and proceed to Step 4 to record those — then tell the PM exactly which items were
created and which were not, so a re-run does not double-create. Do not retry blindly.

## Step 4 — Record the ticket keys back into the spine

Write the created keys into `.traceability.yaml` and log telemetry by piping the
map to the script (only the ids/keys you actually created):

```bash
echo '{"US-001":"RA-1","FR-001":"RA-2","TSK-001":"RA-3"}' \
  | python3 ~/.pm-os/scripts/pm_handoff.py record
```

The script writes each key into the matching requirement's / task's `tickets: []`
slot (preserved across future traceability rebuilds) and logs a `handoff_exported`
telemetry event with refs/counts/keys only. Report its summary as-is, including
any ids it skipped as "not found in the index" (those weren't created or the
source stage isn't approved).

## Offline path (no Atlassian connector)

When the PM passes `--offline`/`csv`, or the Atlassian connector is unavailable
and the PM would rather not wait for it, use this route instead of Steps 2–4:

```bash
python3 ~/.pm-os/scripts/pm_handoff.py export
```

This runs the same plan builder (same approval gate, same EPIC→Epic / US→Story /
FR→Task / TSK→Subtask-or-Task mapping) and writes `handoff/jira-import.csv` plus
`handoff/jira-import-README.md`. Descriptions are converted to Jira wiki markup,
each row carries its stable id as a `pm-os-<id>` label, and parent links are
expressed with `Issue Id` / `Parent Id` so the epic hierarchy survives the import.

Nothing is created — **the PM runs the import**. Report where the two files are,
the issue counts, and any items exported without a parent, then point the PM at
the README for the field mapping. There is no confirmation step here because
nothing outward-facing happens; the PM's own import is the decision point.

After the PM imports, they can recover the created keys from Jira (search the
`pm-os` label, export to CSV) and record them with the same Step 4 command, so
the offline route ends in exactly the same state as the connector route.

## Guardrails

- **Confirm before creating.** No Jira object is created or modified without an
  explicit human "yes" in this conversation. Approval for one run does not carry
  to a later run.
- **Idempotency is the PM's call.** Re-running creates new tickets — it does not
  detect already-created ones. Before a second run, check `handoff/jira-plan.md`
  against `.traceability.yaml`'s recorded `tickets` and confirm with the PM.
- **Local storage is minimal.** Only ticket keys/ids/summaries live locally
  (in `.traceability.yaml` and telemetry). Never copy bulk Jira data back.
- **Derived, not canonical.** `handoff/jira-plan.*` is regenerated on each run;
  never hand-edit it. Change content by editing the approved stage artifact.
