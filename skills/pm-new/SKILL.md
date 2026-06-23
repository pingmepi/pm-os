---
name: pm-new
description: Scaffold a new PM-OS project from a business statement.
model_tier: utility
---

Before running the script, resolve the `--genai` / `--no-genai` flag:

- If `$ARGUMENTS` already contains `--genai` or `--no-genai`, pass `"$@"` as-is.
- If neither flag is present, determine from context:
  - **Pass `--genai`** if the PM's statement or project clearly involves AI, agents, LLMs, or model-driven behaviour.
  - **Pass `--no-genai`** if it clearly does not.
  - **If uncertain**, ask the PM first: "Is this a GenAI/agentic product? (yes/no)" — then append the matching flag.

This flag is required in agent sessions (non-interactive stdin). Omitting it causes the script to exit with an error before scaffolding anything.

Run the script with the resolved flag:

```bash
python3 ~/.pm-os/scripts/pm_new.py "$@"   # --genai or --no-genai already in $@ or appended
```

Report the script's output as-is. Do not summarize, restructure, or add commentary beyond a one-line confirmation that the script ran.
