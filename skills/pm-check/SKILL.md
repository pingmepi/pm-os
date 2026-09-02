---
name: pm-check
description: Check a PM-OS project for internal consistency — meta/frontmatter sync, hash drift, upstream approval shape, telemetry chain integrity, schema shape, artifact presence, and TRD task-id consistency (unique/sequential TSK-### tracing to PRD requirements). Read-only.
model_tier: utility
---

Run: python3 ~/.pm-os/scripts/pm_check.py "$@"

Pass through all arguments verbatim. Do not interpret, validate, or reformat
them.

Optional design gate:

```bash
python3 ~/.pm-os/scripts/pm_check.py --design
```

`--design` runs the normal read-only project consistency checks plus deterministic
validation of `design-in/ia.yaml` and `design-in/design-notes.md`: schema, journey
coverage, story/screen coverage, required states, field coverage, token/component
rationales, excluded-frame use, and returned open questions. When stage 04 is
approved, it also verifies handoff readiness from canonical artifacts: every UI
story has a screen, screens are not orphaned, default/state Figma links and state
triggers are present, generated dev/QA story joins match when a package exists,
and the screen map agrees with story coverage. Missing stage-05 HTML is
informational on this path. It never calls Figma and never writes project state.

Report the script's output as-is. Do not summarize, restructure, or add
commentary beyond a one-line confirmation that the script ran. This command
never modifies project state — if it reports issues, point the PM at the
remediation command it prints for each one (for example `/pm-approve <NN>`);
do not attempt to fix anything on their behalf.
