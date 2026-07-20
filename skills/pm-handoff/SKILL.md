---
name: pm-handoff
description: Export the approved PM-OS pipeline to Jira — build a dry-run ticket plan, get explicit PM confirmation, create the epics/issues via the Atlassian MCP, then record the ticket keys back into the traceability spine.
model_tier: utility
reads: ["03-prd.md", "08-trd.md", ".traceability.yaml"]
---

# Role and goal

Turn the **approved** product pipeline into tracker tickets, keyed to PM-OS's
stable ids so the two systems stay linked. The single supported tracker is
**Jira** (via the Atlassian MCP connector). Each PRD user story (`US-###`)
becomes an **epic**; each functional requirement (`FR-###`/`REQ-###`) it owns
becomes a child **story**; each approved TRD task (`TSK-###`) becomes a child
**task** under the epic that owns the requirement it implements.

This is an **outward-facing, side-effectful** action: it creates real objects in
the PM's Jira. The flow is therefore strict: **dry-run → PM confirms → create →
record**. You never create or modify a Jira object without an explicit human
"yes" in this conversation, and you only ever store ticket keys/ids locally —
never bulk copies of Jira data.

`$ARGUMENTS` may name the tracker (`jira`); if omitted, assume `jira`. Any other
tracker is not supported in this phase — say so and stop.

# Preconditions

1. **Approved PRD.** Stage 03 must be `approved`. The script enforces this and
   exits with an error otherwise — stop and tell the PM to `/pm-approve 03`.
2. **Jira connector authorized.** Creating tickets requires the Atlassian MCP to
   be connected and authorized for this session. If it is not available, **stop**
   before creating anything and tell the PM to authorize the Atlassian/Jira
   connector (claude.ai connector settings, or `/mcp` in an interactive session),
   then re-run. Do not ask the PM for tokens or credentials.
3. **Target Jira project.** You need the destination Jira project key (e.g.
   `RA`). If the PM has not given it, ask for it before creating anything.

# Step 1 — Build the dry-run plan (no network)

```bash
python3 ~/.pm-os/scripts/pm_handoff.py plan
```

This writes `handoff/jira-plan.md` (PM-readable) and `handoff/jira-plan.json`
(the machine map). It touches nothing external. Read `handoff/jira-plan.md` and
present its summary to the PM: how many epics / stories / tasks, and — if any —
the **Unassigned** items (requirements or tasks with no owning user story). Call
those out explicitly; the PM may want to fix ownership in the PRD first rather
than create orphan tickets.

# Step 2 — STOP and get explicit confirmation

Do **not** create anything yet. Show the PM the plan and the target Jira project,
and ask for an explicit go-ahead, e.g.:

> Ready to create in Jira project **RA**: 2 epics, 3 stories, 3 tasks (2
> unassigned — review these first). Nothing has been created yet. Create them?

Wait for a clear "yes". If the PM wants changes, they edit the canonical stage
artifact (`03-prd.md` / `08-trd.md`), re-approve, and you re-run Step 1 — never
hand-edit `handoff/`. If the PM says no, stop.

# Step 3 — Create the tickets via the Atlassian MCP

Only after an explicit yes. Read `handoff/jira-plan.json` and create objects in
dependency order using the Atlassian/Jira MCP tools:

1. Create every **Epic** first (the items with `type: "Epic"`, excluding
   `ref: "UNASSIGNED"`). Use its `summary` and `description`. Record the returned
   Jira key against its `ref`.
2. Create every **Story** and **Task**, setting each one's parent/epic link to
   the Jira key of the epic named by its `parent_ref` (skip the parent link for
   items whose `parent_ref` is `"UNASSIGNED"` — create them standalone). Use each
   item's `summary` and `description`; for tasks, the `implements` ids are useful
   context to include.

Build a flat map of `{ stable-id: created-jira-key }` as you go, e.g.
`{"US-001": "RA-1", "FR-001": "RA-2", "TSK-001": "RA-3"}`.

**If creation fails partway:** stop creating, keep the map of what *did* succeed,
and proceed to Step 4 to record those — then tell the PM exactly which items were
created and which were not, so a re-run does not double-create. Do not retry blindly.

# Step 4 — Record the ticket keys back into the spine

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

# Guardrails

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
