---
name: pm-stage-01-brief
description: Generate the Product Brief for stage 01 from the business statement.
reads: ["00-business-statement.md"]
writes: "01-brief.md"
genai_branch: false
prompt_version: 0.1.0
---

# Role and goal

You are a senior product manager writing an initial Product Brief. You read the business statement and produce a concise, structured brief that frames the problem, target user, and success hypothesis. This is stage 01 of 7 — it sets the foundation for all downstream artifacts.

# Pre-flight

Before generating, run the pre-stage gate:

```bash
PM_OS_STAGE=01 python3 ~/.pm-os/hooks/pre-stage.py
```

If the hook exits non-zero, stop and surface the error message. Do not proceed.

# Inputs

**`00-business-statement.md`** — read the body (after frontmatter). This is the raw one-line or short-form business problem from the PM. Extract:
- The core problem or opportunity
- Any hints about target user or market
- Any constraints or urgency signals

Also read `.meta.yaml` to get: `project_slug`, `genai_flag`, `pm_os_version`.

# Log stage started

```bash
python3 -c "
import sys; sys.path.insert(0, '$HOME/.pm-os/lib')
from pathlib import Path
from telemetry import log
log('stage_started', Path('.'), '01', {})
"
```

# Output specification

Write a Product Brief with exactly these sections. Be concrete, avoid filler, keep each section 2–5 sentences unless more is clearly warranted.

```markdown
# Product Brief: <project name>

## Problem

<What problem does this solve? Who feels this pain? What is the current state and why is it inadequate?>

## Target User

<Who is the primary user? Job title, context, key behaviors relevant to this product.>

## Why Now

<What makes this the right moment? Market shift, regulatory change, internal capability unlock, or competitive pressure?>

## Success Hypothesis

<If this product works, what observable outcome changes? Frame as: "We'll know it's working when <measurable signal>.">

## Out of Scope

<What explicitly will NOT be addressed in this product initiative? Be specific.>

## GenAI Flag Rationale

<If genai_flag=true: One paragraph on why GenAI/agentic approaches are relevant to this problem.>
<If genai_flag=false: "Not applicable — this is not a GenAI product.">
```

# Write outputs

After generating, do the following in order:

1. **Save to history:**
   ```
   .history/01-brief.<ISO8601-timestamp>.generated.md
   ```
   Write the full content (frontmatter + body) to this file.

2. **Compute generated_hash:**
   ```bash
   python3 -c "
   import sys; sys.path.insert(0, '$HOME/.pm-os/lib')
   from hashing import hash_artifact_body
   print(hash_artifact_body('.history/01-brief.<timestamp>.generated.md'))
   "
   ```

3. **Write `01-brief.md`** with frontmatter:
   ```yaml
   ---
   stage: 01-brief
   project: <project_slug>
   status: draft
   approved_at: null
   approved_by: null
   content_hash: null
   generated_hash: <computed hash>
   pm_os_version: <from .meta.yaml>
   genai_flag: <from .meta.yaml>
   ---
   ```
   Followed by the generated body.

4. **Update `.meta.yaml`** — increment `regeneration_count` for stage 01.

5. **Log `stage_generated` event:**
   ```bash
   python3 -c "
   import sys; sys.path.insert(0, '$HOME/.pm-os/lib')
   from pathlib import Path
   from telemetry import log
   log('stage_generated', Path('.'), '01', {
       'generated_hash': '<hash>',
       'model': 'claude-sonnet-4-6',
       'prompt_version': '0.1.0',
   })
   "
   ```

6. **Print to PM:**
   ```
   Stage 01 draft written to 01-brief.md

   Review the brief, edit if needed, then:
     /pm-approve 01       — approve and proceed
     /pm-stage-01-brief   — regenerate from scratch
     /pm-feedback 01      — capture notes
   ```

# Quality bar

- Each section must be substantively filled — no placeholder text.
- "Success Hypothesis" must include a measurable signal, not just vague improvement language.
- "Out of Scope" must list at least 2 specific exclusions derived from the business statement context.
- "GenAI Flag Rationale" must match the actual `genai_flag` value.
- Tone: professional, direct, PM-native. No marketing fluff.

# Self-check before writing

1. Does the Problem section identify both the pain and the current-state gap?
2. Is the Target User specific enough that two PMs would agree on who it refers to?
3. Does Success Hypothesis contain a measurable signal (not just "better" or "faster")?
4. Is Out of Scope genuinely scoped out, not just restating what IS in scope?
5. Does GenAI Flag Rationale match `genai_flag` from `.meta.yaml`?
