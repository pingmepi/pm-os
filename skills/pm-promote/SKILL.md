---
name: pm-promote
description: Promote (or demote) a requirement's release tier — preview the cost, apply the re-tag, and regenerate the story at the right fidelity.
model_tier: utility
---

# Role and goal

The PM wants to move a requirement between release tiers (`mvp | v1 | v2 | later`) — usually to pull a `v1`/`v2` story into the MVP (promote), or push an MVP story out (demote). A tier change is a body edit to the PRD, so it can cascade staleness downstream; you preview that cost, get the PM's explicit go-ahead, apply the re-tag, and bring the story to the fidelity its new tier requires.

For a **user story** (`US-###`), tier and fidelity are coupled (D2): `mvp` stories are full self-contained mini-specs; `v1`/`v2`/`later` stories are SOW-grade stubs (Value, Size, Rationale, Depends on, Acceptance intent). So promoting a story **into** mvp means elaborating it to full fidelity; demoting **out of** mvp means reducing it to a stub.

For a **functional requirement** (`FR-###`/`REQ-###`) the coupling does **not** apply. An FR states observable system behavior; that behavior text is **tier-invariant** — the tier only records *which release band* the behavior lands in, not how much of it is written down. FRs have no SOW-stub contract, so promoting or demoting an FR is a **re-tag only**: never add story-style UI/acceptance fields on promote, and **never drop the behavior text on demote** (doing so would discard the very thing the FR id exists to preserve).

# Parse arguments

From `$ARGUMENTS`: the requirement id (e.g. `US-003`, `FR-012`) and either `--to <tier>` or `--demote` (default is promote one band toward mvp). Example invocations: `/pm-promote US-007 --to mvp`, `/pm-promote FR-004 --demote`.

# 1. Preview the cost (read-only)

Run the preview and show its output to the PM verbatim:

```bash
python3 ~/.pm-os/scripts/pm_promote.py <req-id> [--to <tier>] [--demote]
```

It reports the current → target tier and whether the change is **FREE** (PRD not yet approved), **LOW** (re-approve the PRD, no approved downstream), or a **CASCADE** (names the approved downstream stages that will re-stale on re-approval). It changes nothing.

# 2. Confirm

If the preview reports a **CASCADE**, stop and ask the PM to confirm in their own words before proceeding — re-staling design/QA/metrics is a real cost. If it is FREE or LOW, say so and proceed. Do not proceed on a CASCADE without an explicit yes (non-tty/unattended: only proceed if the invocation already said to apply, e.g. an `--apply`/`--yes` argument was passed).

# 3. Apply the re-tag + set fidelity

Edit `03-prd.md` (the source of truth for `US-###`/`FR-###` tiers):

1. **Re-tag:** set the requirement block's `- **Tier:** <target>` field (add the line if absent).
2. **Match fidelity to the new tier — but only for a user story (`US-###`):**
   - Promoting a **story into `mvp`** → elaborate it to the full stage-03 mini-spec: Happy path, Edge cases / alternate paths, Data fields, Key UI steps (with per-step system process + Acceptance + corner cases/exceptions), Acceptance criteria, Priority, and Traceability. Use the approved brief/scope + the story's stub fields as the seed; do not invent scope beyond what the item already commits to.
   - Demoting a **story out of `mvp`** → reduce it to a SOW-grade stub: keep Story, Epic, Tier, Value, Size, Rationale, Depends on, Acceptance intent, Traceability; drop the full mini-spec detail.
   - **For a functional requirement (`FR-###`/`REQ-###`): stop after the re-tag.** Its behavior text is tier-invariant (see Role and goal) — do not add story UI/acceptance fields, and do not strip or summarize the existing behavior spec. The `- **Tier:** <target>` change is the *only* edit to an FR block.
**Edit only the PRD here.** The PRD is the authoritative source of `US-###`/`FR-###` tiers, and the cost preview models a stage-03 edit. Do **not** also edit `02-scope.md` in this operation: editing an approved scope creates upstream hash drift the preview never disclosed and would need its own re-approval (with a larger cascade). If the scope's tier tag should change to match, do that as a **separate** `02` scope edit + `/pm-approve 02 --reapprove` afterwards, accepting its own cascade.

# 4. Validate

```bash
python3 ~/.pm-os/scripts/pm_validate_artifact.py 03 --mode strict
```

Section/fidelity findings are warnings; a promoted-to-mvp **story** should now carry the full mini-spec (no `USER_STORY_ACCEPTANCE_MISSING`/`_HAPPY_PATH_MISSING`/`_EDGE_CASES_MISSING` for it), and a demoted **story** stub should carry the SOW-grade fields (no `USER_STORY_STUB_FIELDS_MISSING`). For an **FR/REQ** re-tag, the only expectation is a valid `Tier:` and unchanged behavior text — those story findings do not apply. Repair and re-validate if needed.

# 5. Re-approve + let staleness cascade

The re-tag edited the PRD body. Re-approve it so the change sticks and cascades:

- **If the PRD was already approved** (the LOW/CASCADE cases) use **`--reapprove`** — a plain `/pm-approve 03` sees status `approved` and **exits early without recomputing the hash or cascading staleness**, so the tier change would never take effect:

  ```
  /pm-approve 03 --reapprove
  ```

- **If the PRD was still a draft** (the FREE case) a normal approve is correct:

  ```
  /pm-approve 03
  ```

Then regenerate any downstream stage the preview flagged as re-staled, in order. Do not touch gate/hash/status yourself — approval and the staleness cascade are the state machine's job.

# 6. Log telemetry

```bash
python3 -c "
import sys; sys.path.insert(0, '$HOME/.pm-os/lib')
from pathlib import Path
from telemetry import log
log('requirement_promoted', Path('.'), '03', {
    'requirement': '<req-id>',
    'from_tier': '<current tier>',
    'to_tier': '<target tier>',
})
"
```

# Print to PM

Summarize: the requirement moved `<from>` → `<to>`, whether it was free or cascaded, what you regenerated, and the next step (`/pm-approve 03 --reapprove` if the PRD was already approved, else `/pm-approve 03`, then regenerate any re-staled downstream stages).
