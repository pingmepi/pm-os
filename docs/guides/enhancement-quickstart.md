# Enhancing an Existing Product with PM-OS

*A quickstart for the enhancement pathway (PM-OS v1.5). For the full workflow and governance, see [`sop.md`](sop.md).*

Commands are shown for Claude Code (`/command`). On OpenAI Codex, replace the leading `/` with `$` (e.g. `$pm-enhance`).

---

## What it's for

Most product work is not greenfield — it's a change to something that already exists. The **enhancement pathway** drives that change through PM-OS's normal gated pipeline, grounded in the product's real codebase:

- PM-OS **reads your code read-only** (it never modifies, commits to, or builds your repo), builds a lightweight inventory, and traces the **affected slice + impact cone** for your ask.
- You regenerate **only the stages/sections that change**; unaffected requirements are carried forward untouched.
- The handoff is **delta-only** — dev/QA get just the changed stories, requirements, tests, and tasks (plus explicit removal tickets), not a re-dump of the whole product.

**One product = one PM-OS project.** Every later enhancement to the same product continues in that same project — never a new one.

## What you need

Your codebase, in any one of these forms (PM-OS only reads it):

- a **git URL** — GitHub, GitLab, or any remote,
- a **local folder**, or
- a **`.zip` archive** of the code.

A zip (or remote) is extracted/cloned into the project's own read-only `.codebase/` copy — your original is never touched.

## The flow

**1. Create the project, pointed at the code, and approve the ask.**

```
/pm-new my-product --entry enhancement --codebase <git-url | /path/to/code | code.zip>
/pm-approve 00
```

**2. Scan the codebase and approve what PM-OS understood.**

```
/pm-context-import --codebase <same source>
```

This produces a gated **codebase-understanding** doc (`00c`) and a **context-understanding** doc (`00u`). Review them — correct any misreading — and approve. This is your early catch point: if PM-OS misread the affected area, you fix it here, not three stages later.

**3. Start the cycle and record the affected slice.**

```
/pm-enhance
```

The agent freezes the approved baseline (`start`), then walks you through a short **decision interview** to record the boundary (`set-boundary`): what's changing, which surfaces (UI / API / data / service / …) are affected, what must **not** break, and any migration/rollout notes. **The questions are skippable** — answer what you know; anything you skip is logged as a known-unknown. This step anchors the whole enhancement.

> **This is required.** Product stages (01–09) will **not** generate until the boundary is recorded. If you try to run a stage first, PM-OS stops and tells you to record the affected slice — by design, so the delta, checks, and handoff always have something to scope against.

**4. Generate the affected stages, approving each.**

```
/pm-stage-01-brief   → /pm-approve 01
/pm-stage-02-scope   → /pm-approve 02
...                    (through 07; optional 08 TRD, 09 roadmap)
```

Each stage covers the **enhancement only** — the current-product gap and the delta — not a rewrite of the whole product.

**5. Check, complete, and hand off.**

```
/pm-check
/pm-enhance          (agent runs 'complete' once the pipeline is coherent)
/pm-handoff --package        # readable per-audience package (dev / design / qa / business)
# or:
/pm-handoff jira             # Jira tickets (connector) or --offline for a CSV you import
```

The package and Jira export are automatically **scoped to the delta** — changed work plus the parent epics/stories needed to keep the hierarchy intact, and explicit tickets for anything you removed.

## Useful anytime

| Command | What it shows |
|---|---|
| `/pm-status` | Where the project is, the active enhancement, and the next safe action |
| `/pm-check` | Read-only consistency check (baseline integrity, drift, missing traces) |
| `/pm-enhance` → `show` / `delta` | The active boundary, and the computed baseline-vs-current change set |
| `/pm-enhance` → `refresh` | Re-pin the codebase evidence after the code moves (explicit, never silent) |

## The one rule to remember

PM-OS **only ever reads** your product's codebase. All generated artifacts live inside the PM-OS project — nothing is ever written to, committed to, or built in your repo.
