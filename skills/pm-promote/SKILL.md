---
name: pm-promote
description: Promote (or demote) a requirement's release tier — preview the cost, apply the re-tag, and regenerate the story at the right fidelity.
model_tier: utility
---

# Role and goal

The PM wants to move a requirement between release tiers (`mvp | v1 | v2 | later`) — usually to pull a `v1`/`v2` story into the MVP (promote), or push an MVP story out (demote). A tier change is a body edit to the PRD, so it can cascade staleness downstream; you preview that cost, get the PM's explicit go-ahead, apply the re-tag, and bring the story to the fidelity its new tier requires.

Tier assignment and fidelity are coupled (D2): `mvp` stories are full self-contained mini-specs; `v1`/`v2`/`later` stories are SOW-grade stubs (Value, Size, Rationale, Depends on, Acceptance intent). So promoting **into** mvp means elaborating the story to full fidelity; demoting **out of** mvp means reducing it to a stub.

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
2. **Match fidelity to the new tier:**
   - Promoting **into `mvp`** → elaborate the story to the full stage-03 mini-spec: Happy path, Edge cases / alternate paths, Data fields, Key UI steps (with per-step system process + Acceptance + corner cases/exceptions), Acceptance criteria, Priority, and Traceability. Use the approved brief/scope + the story's stub fields as the seed; do not invent scope beyond what the item already commits to.
   - Demoting **out of `mvp`** → reduce the story to a SOW-grade stub: keep Story, Epic, Tier, Value, Size, Rationale, Depends on, Acceptance intent, Traceability; drop the full mini-spec detail.
3. **Keep the scope consistent:** if the matching item in `02-scope.md` carries a tier tag, update it to the same tier so scope and PRD agree.

If the item also appears in the approved scope and that edit matters upstream, note it — but do not edit stages other than the PRD/scope here.

# 4. Validate

```bash
python3 ~/.pm-os/scripts/pm_validate_artifact.py 03 --mode strict
```

Section/fidelity findings are warnings; a promoted-to-mvp story should now carry the full mini-spec (no `USER_STORY_ACCEPTANCE_MISSING`/`_HAPPY_PATH_MISSING`/`_EDGE_CASES_MISSING` for it), and a demoted stub should carry the SOW-grade fields (no `USER_STORY_STUB_FIELDS_MISSING`). Repair and re-validate if needed.

# 5. Re-approve + let staleness cascade

Tell the PM the re-tag edited the PRD body, so the PRD is now `edited` (hash drift). To make it stick and cascade correctly:

```
/pm-approve 03            # re-approve the PRD (cascades stale to approved downstream)
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

Summarize: the requirement moved `<from>` → `<to>`, whether it was free or cascaded, what you regenerated, and the next step (`/pm-approve 03`, then regenerate any re-staled downstream stages).
