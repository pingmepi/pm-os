---
name: pm-feedback
description: Capture qualitative feedback and a rating for a PM-OS stage artifact.
model_tier: utility
---

Before running the script, resolve the required flags for non-interactive mode:

- If `$ARGUMENTS` already contains `--rating` or `--skip-rating`, and `--note` or `--skip-note`, pass `"$@"` as-is.
- If those flags are absent, collect them from the PM:
  1. **Rating** — ask "Rate this stage 1–5 (or skip)." Use `--rating <N>` if they give a number, or `--skip-rating` if they skip.
  2. **Note** — ask "Any notes on quality or gaps?" Use `--note "<text>"` if they provide one, or `--skip-note` if they skip.

Both flags are required in agent sessions (non-interactive stdin). Omitting either causes the script to exit with an error before writing any feedback.

Run the script with the resolved flags:

```bash
python3 ~/.pm-os/scripts/pm_feedback.py "$@"   # --rating/--skip-rating and --note/--skip-note in $@ or appended
```

Report the script's output as-is. Do not summarize, restructure, or add commentary beyond a one-line confirmation that the script ran.
