---
name: pm-approve
description: Approve the current draft for a given stage, compute content hash, update state, and cascade staleness.
model_tier: utility
---

# Optional: estimate semantic drift before approving

The script computes deterministic character/normalized edit distances on its own.
You may *additionally* supply a subjective semantic-distance estimate so the team
can tell a large-but-cosmetic edit from a small-but-meaningful one.

Determine the stage id from `$ARGUMENTS` (the first argument, e.g. `03`). If a
generation snapshot exists — `.history/<NN>-<name>.*.generated.md` — then:

1. Read the body of the most recent matching snapshot and the body of the current
   `<NN>-<name>.md` artifact.
2. If they differ in **meaning** (ignore pure whitespace/markdown reflows), estimate
   a semantic distance between `0.0` (identical meaning) and `1.0` (completely
   different intent), and append `--semantic-distance <value>` to the approve call.
   This is explicitly a subjective agent judgment and is recorded as such.

If the bodies are effectively identical, or no snapshot exists, omit the flag.
Never block approval on this step — it is best-effort.

# Run

Run: python3 ~/.pm-os/scripts/pm_approve.py "$@"

Append only the optional `--semantic-distance <value>` if you computed one. Pass
through all of the PM's arguments verbatim — do not interpret, validate, or reformat
them. Report the script's output as-is, beyond a one-line confirmation that it ran.
