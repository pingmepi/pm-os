---
name: pm-new
description: Scaffold a new PM-OS project from a business statement.
args:
  - name: slug
    description: kebab-case project identifier (e.g. "rx-refill-agent")
  - name: business_statement
    description: One-line business problem statement in quotes
---

# Role and goal

You are scaffolding a new PM-OS project. Create the project directory, all required files, and initialize metadata so the PM can begin running stages.

# Steps

1. **Validate slug** — confirm it is kebab-case (lowercase letters, numbers, hyphens only) and does not already exist under `~/pm-projects/`. If invalid or duplicate, print a clear error and stop.

2. **Create project directory and subdirectories:**
   ```
   ~/pm-projects/<slug>/
   ~/pm-projects/<slug>/.history/
   ```

3. **Write `00-business-statement.md`** with this exact structure:
   ```
   ---
   stage: 00-business-statement
   project: <slug>
   status: approved
   approved_at: <current ISO 8601 UTC timestamp>
   approved_by: <PM_OS_USER env var value>
   content_hash: null
   generated_hash: null
   pm_os_version: <read from ~/.pm-os/VERSION, fallback to "0.1.0">
   genai_flag: null
   ---

   <business statement text as-is>
   ```

4. **Ask the PM:** "Is this a GenAI/agentic product? [y/n]" — set `genai_flag: true` if y, `false` if n.

5. **Write `.meta.yaml`** using this structure (replace placeholders):
   ```yaml
   schema_version: 1
   project_slug: <slug>
   project_name: <slug with hyphens replaced by spaces, title-cased>
   created_at: <ISO 8601 UTC>
   created_by: <PM_OS_USER env var>
   genai_flag: <true|false>
   pm_os_version: <from VERSION file or "0.1.0">
   stages:
     - id: "01"
       name: brief
       status: pending
       approved_at: null
       content_hash: null
       upstream_hashes_at_approval: {}
       regeneration_count: 0
     - id: "02"
       name: scope
       status: pending
       approved_at: null
       content_hash: null
       upstream_hashes_at_approval: {}
       regeneration_count: 0
     - id: "03"
       name: prd
       status: pending
       approved_at: null
       content_hash: null
       upstream_hashes_at_approval: {}
       regeneration_count: 0
     - id: "04"
       name: design-spec
       status: pending
       approved_at: null
       content_hash: null
       upstream_hashes_at_approval: {}
       regeneration_count: 0
     - id: "05"
       name: prototype-brief
       status: pending
       approved_at: null
       content_hash: null
       upstream_hashes_at_approval: {}
       regeneration_count: 0
     - id: "06"
       name: qa-plan
       status: pending
       approved_at: null
       content_hash: null
       upstream_hashes_at_approval: {}
       regeneration_count: 0
     - id: "07"
       name: metrics-plan
       status: pending
       approved_at: null
       content_hash: null
       upstream_hashes_at_approval: {}
       regeneration_count: 0
   ```

6. **Create empty files:**
   - `~/pm-projects/<slug>/telemetry.jsonl` (empty file)
   - `~/pm-projects/<slug>/feedback.jsonl` (empty file)

7. **Log `project_created` telemetry event** by running:
   ```bash
   cd ~/pm-projects/<slug> && python3 -c "
   import sys; sys.path.insert(0, '$HOME/.pm-os/lib')
   from pathlib import Path
   from telemetry import log
   log('project_created', Path('.'), None, {})
   "
   ```

8. **Print confirmation:**
   ```
   Project '<slug>' created at ~/pm-projects/<slug>/
   GenAI flag: <yes/no>
   Next step: cd ~/pm-projects/<slug> && run /pm-stage-01-brief
   ```

# Error handling

- If `PM_OS_USER` is not set, warn but continue (use "unknown").
- If telemetry logging fails (e.g. lib not found), warn but do not block project creation.
