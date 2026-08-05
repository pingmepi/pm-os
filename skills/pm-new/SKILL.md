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

Also resolve the entry route:

- If `$ARGUMENTS` already contains `--entry new`, `--entry prototype`, or `--entry enhancement`, pass it through.
- If `$ARGUMENTS` uses the older `--mode enhancement --codebase <path-or-url>` form, pass it through; this remains the Pathway 3 compatibility path.
- If no entry is provided and the PM's wording clearly says they are starting from an approved prototype/design with no code, append `--entry prototype`.
- If no entry is provided and the PM's wording clearly says they are starting from an existing live product/codebase, append `--entry enhancement` and include `--codebase <source>` if the PM provided one — a git URL, a local directory, or a `.zip` archive of the code.
- Otherwise append `--entry new`.

Routes:

- `new` keeps `project_type: new_product` and guides the PM to `/pm-stage-01-brief`.
- `prototype` keeps `project_type: new_product`, records the route, and guides the PM to `/pm-context-import <prototype-or-design-files>`.
- `enhancement` reuses today's enhancement scaffold behavior (`project_type: enhancement`, `codebase_path` when supplied) and guides the PM to `/pm-context-import --codebase <source>`, where `<source>` is a git URL, a local directory, or a `.zip` archive of the code.

Run the script with the resolved flag:

```bash
python3 ~/.pm-os/scripts/pm_new.py "$@"   # --genai/--no-genai and --entry already in $@ or appended
```

Report the script's output as-is. Do not summarize, restructure, or add commentary beyond a one-line confirmation that the script ran.
