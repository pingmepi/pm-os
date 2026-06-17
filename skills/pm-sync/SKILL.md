---
name: pm-sync
description: Catch-up sync of all PM-OS projects' telemetry + feedback to the central feedback repo, or verify their hash chains.
model_tier: utility
---

Run: python3 ~/.pm-os/scripts/pm_sync.py "$@"

This is the manual catch-up sync. With no arguments it walks every project under your
`projects_dir`, copies each project's `telemetry.jsonl` + `feedback.jsonl` into the
central feedback repo, and pushes them in a single commit. Use it to backfill projects
that never reached the central repo — e.g. created before central sync existed, or whose
only automatic push failed silently. Projects whose local directory was deleted are
skipped, not treated as errors.

`--verify` validates every project's telemetry hash chain and reports any breaks instead
of pushing.

Pass through all arguments verbatim. Report the script's output as-is, including any loud
`FAILED — …` lines — those indicate an auth/network problem to fix and retry, not a PM
error.
