---
name: pm-check
description: Check a PM-OS project for internal consistency — meta/frontmatter sync, hash drift, upstream approval shape, telemetry chain integrity, schema shape, and artifact presence. Read-only.
model_tier: utility
---

Run: python3 ~/.pm-os/scripts/pm_check.py "$@"

Pass through all arguments verbatim. Do not interpret, validate, or reformat
them.

Report the script's output as-is. Do not summarize, restructure, or add
commentary beyond a one-line confirmation that the script ran. This command
never modifies project state — if it reports issues, point the PM at the
remediation command it prints for each one (for example `/pm-approve <NN>`);
do not attempt to fix anything on their behalf.
