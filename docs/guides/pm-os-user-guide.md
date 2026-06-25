# PM-OS User Guide

This guide takes you from zero to a fully running PM-OS setup. Follow it top-to-bottom on your first run, then use it as a reference once you know the system.

---

## Table of Contents

1. [What is PM-OS?](#1-what-is-pm-os)
2. [Prerequisites](#2-prerequisites)
3. [Installation](#3-installation)
4. [Verify Your Install](#4-verify-your-install)
5. [Recommended Setup](#5-recommended-setup)
6. [Your First Project — End-to-End Walkthrough](#6-your-first-project--end-to-end-walkthrough)
7. [The Stage Pipeline](#7-the-stage-pipeline)
8. [Approval and the Gate Model](#8-approval-and-the-gate-model)
9. [Context Customization](#9-context-customization)
10. [Importing Existing Material](#10-importing-existing-material)
11. [All Commands — Quick Reference](#11-all-commands--quick-reference)
12. [Failure Modes and Recovery](#12-failure-modes-and-recovery)
13. [Keeping PM-OS Up to Date](#13-keeping-pm-os-up-to-date)
14. [Data and Privacy](#14-data-and-privacy)

---

## 1. What is PM-OS?

PM-OS is a **PM-led product development operating layer** — an agent skill suite that guides a product idea through a structured, gated pipeline of stages, from business statement through to metrics plan, TRD, and roadmap. It is not an app, not a backend service, and not a SaaS tool. It runs entirely on your machine, inside your existing AI coding agent (Claude Code or OpenAI Codex).

**What it does:** At each stage, the agent drafts a Markdown artifact (brief, PRD, design spec, etc.) based on all previously approved upstream artifacts. You review it, edit it as needed, and explicitly approve it. Only after approval does the gate allow the next stage to run.

**What it does not do:** It never progresses autonomously. Nothing moves forward without your explicit `/pm-approve` (Claude) or `$pm-approve` (Codex). The agent drafts and validates; you decide.

**The core loop:**

```
Business Statement
       ↓ approve
   01 Brief → 02 Scope → 03 PRD → 04 Design Spec → 05 Prototype Brief
                                                           ↓
                              07 Metrics Plan ← 06 QA Plan
                                                           ↓
                              (optional) 08 TRD → 09 Roadmap
```

Each arrow is gated. You must approve each stage before the next one can generate.

**Decision authority:**

| Who | Does what |
|-----|-----------|
| You (PM) | Decides scope, trade-offs, approvals — controls every gate |
| PM-OS agent | Drafts artifacts, validates gates, detects drift |
| Developers / QA | Execute against the approved artifacts |

---

## 2. Prerequisites

| Requirement | Notes |
|-------------|-------|
| **Claude Code** (for Claude runtime) | Install from [claude.ai/code](https://claude.ai/code) |
| **OpenAI Codex** (for Codex runtime) | Install via your org's Codex setup |
| **Python 3.11 or higher** | Check with `python3 --version` |
| **Git** | Required for the install and update path |
| **Internet access** | Required for initial install from GitHub; see [offline path](#b-offline--from-zip) if blocked |

You only need the runtime(s) you plan to use. `--runtime all` installs for both simultaneously.

---

## 3. Installation

The same `install.sh` script handles all three paths. Pick the one that fits your environment.

### A. Standard — from GitHub

```bash
# Claude only
./install.sh --runtime claude --pm-user <your-id>

# Codex only
./install.sh --runtime codex --pm-user <your-id>

# Both runtimes at once
./install.sh --runtime all --pm-user <your-id>
```

`<your-id>` is a short unique identifier for you (e.g. `kmandalam`). It labels your telemetry and is used in project paths.

### B. Offline / from zip

If you received PM-OS as a zip file (e.g. from a demo), use the `--source` flag to install from the extracted directory instead of cloning from GitHub:

```bash
unzip pm-os.zip
cd pm-os
./install.sh --runtime all --source . --pm-user <your-id>
```

This path requires no network access after unzipping. Note: there is no auto-update path from a zip install — see [Section 13](#13-keeping-pm-os-up-to-date) for how to get updates later.

### C. Flags reference

| Flag | What it does | Default |
|------|-------------|---------|
| `--runtime claude\|codex\|all` | Which runtime(s) to install for | *(required)* |
| `--pm-user <id>` | Your PM identifier | *(prompted if omitted)* |
| `--projects-dir <path>` | Where your projects live | `~/pm-projects` |
| `--source <dir>` | Install from a local directory instead of GitHub | *(not set — uses GitHub)* |
| `--reconfigure` | Re-prompt all config values even if already set | `false` |

### What the installer does

1. Checks Python 3.11+ and installs `pyyaml` and `jinja2` (the only runtime dependencies)
2. Clones (or copies) PM-OS to `~/.pm-os` — the canonical install location
3. Creates your projects directory (`~/pm-projects` by default)
4. Syncs skills to `~/.claude/skills` (Claude) and/or `~/.agents/skills` (Codex)
5. Writes `~/.pm-os/config.yaml` with your settings
6. Runs a self-verification pass to confirm everything is working

---

## 4. Verify Your Install

After installing, run the verifier to confirm everything is healthy:

**From the terminal:**
```bash
python3 ~/.pm-os/scripts/pm_os_verify.py
```

**From inside Claude Code:**
```
/pm-os-verify
```

**From Codex:**
```
$pm-os-verify
```

The verifier checks:

- Config file present and readable (`~/.pm-os/config.yaml`)
- Python dependencies installed (`pyyaml`, `jinja2`)
- Projects directory exists and is writable
- All expected skills are synced to the runtime's skill directory
- Gate self-test: scaffolds a throw-away project, runs the pre-stage gate, verifies it blocks an unapproved upstream and allows the first stage

**A passing run looks like:**

```
[verify] Config OK
[verify] Python deps OK (pyyaml 6.0.1, jinja2 3.1.2)
[verify] Projects dir OK: /Users/kmandalam/pm-projects
[verify] Skills OK: 19/19 installed
[verify] Gate self-test: PASSED
[verify] All checks passed.
```

**If a check fails:** the verifier prints exactly what failed and why. Common fixes are in [Section 12](#12-failure-modes-and-recovery). When in doubt, re-run the installer with `--reconfigure`.

---

## 5. Recommended Setup

**Projects directory:** Keep all projects under `~/pm-projects/<slug>/`. The `resolve_project()` function in PM-OS walks up from your current directory to find the nearest `.meta.yaml`, so all PM-OS commands must be run from inside a project directory.

**Runtime command syntax:**

| Runtime | Command prefix | Example |
|---------|---------------|---------|
| Claude Code | `/pm-*` | `/pm-approve 03` |
| Codex | `$pm-*` | `$pm-approve 03` |

All examples in this guide use the Claude `/pm-*` syntax. Substitute `$pm-*` for Codex.

**Model recommendations:**

PM-OS stages are divided into two tiers:

| Tier | Stages | Recommendation |
|------|--------|---------------|
| **Deep-reasoning** | 03 PRD, 04 Design Spec, 06 QA Plan, 08 TRD, 09 Roadmap, context wiki/understanding (00w, 00u) | Use the strongest available model — Claude Opus (`/fast` in Claude Code) or o1/o3 in Codex |
| **Standard** | 01 Brief, 02 Scope, 05 Prototype Brief, 07 Metrics Plan | Default model is fine |

Skimping on model quality for deep-reasoning stages produces shallower artifacts. The gate does not enforce this, but the output quality difference is significant.

**GenAI flag:** Set at project creation and cannot be changed later.
- Use `--genai` if the product involves AI models, agents, LLMs, or model-driven behaviour
- Use `--no-genai` for everything else

With `--genai`, stages emit additional sections covering model selection, evaluation, hallucination mitigation, data governance, and responsible AI — sections that are suppressed for non-GenAI products.

---

## 6. Your First Project — End-to-End Walkthrough

This walkthrough uses a GenAI product example: an AI-powered assistant that helps site coordinators at clinical research organizations match eligible patients to open clinical trials, cutting manual screening time by 60%.

### Step 1: Create the project

```
/pm-new trial-match "We need an AI assistant that helps site coordinators match eligible patients to open clinical trials, reducing manual screening time by 60%" --genai
```

PM-OS scaffolds the project and prints:

```
[pm-new] Scaffolded: /Users/kmandalam/pm-projects/trial-match
  .meta.yaml
  00-business-statement.md
```

Move into the project directory — all subsequent commands run from here:

```bash
cd ~/pm-projects/trial-match
```

### Step 2: Review and approve the business statement

Open `00-business-statement.md`. PM-OS has pre-populated it from your statement. Edit it to your satisfaction — add context, sharpen the problem, note constraints. When ready:

```
/pm-approve 00
```

Output:

```
[approve] Stage 00 (business-statement) approved.
  Content hash: a3f9c2...
  Recorded in .meta.yaml and frontmatter.
```

### Step 3: Generate the Product Brief

```
/pm-stage-01-brief
```

The agent reads your approved business statement, applies any context overlay (see [Section 9](#9-context-customization)), and generates `01-brief.md`. Read the output. Edit anything that doesn't reflect your intent. Then approve:

```
/pm-approve 01
```

### Step 4: Generate the Scope

```
/pm-stage-02-scope
```

Reads: approved business statement + brief. Produces `02-scope.md` covering MVP boundary, in-scope items, explicit exclusions, constraints, and assumptions.

Review, edit, approve:

```
/pm-approve 02
```

### Step 5: Generate the PRD (deep-reasoning — switch to Opus first)

**Claude Code:** Toggle fast mode before running:
```
/fast
/pm-stage-03-prd
```

**Codex:** Select o1 or o3 in your model settings, then:
```
$pm-stage-03-prd
```

This is the most complex artifact. Reads all approved upstream stages. Produces `03-prd.md` covering user stories, acceptance criteria, edge cases, GenAI-specific requirements (model selection rationale, eval strategy, data governance), and non-functional requirements.

Review carefully. The PRD is the source of truth for stages 04–07. Approve when solid:

```
/pm-approve 03
```

### Step 6: Check your status mid-pipeline

At any point:

```
/pm-status
```

Sample output:

```
Project: trial-match  [genai]
─────────────────────────────────────────────
  00 business-statement  approved  ✓
  01 brief               approved  ✓
  02 scope               approved  ✓
  03 prd                 approved  ✓
  04 design-spec         pending
  05 prototype-brief     pending
  06 qa-plan             pending
  07 metrics-plan        pending
─────────────────────────────────────────────
Feedback entries: 0
```

### Step 7: Continue through stages 04–07

Repeat the same generate → review → approve pattern for each remaining stage:

| Stage | Command | Notable output |
|-------|---------|---------------|
| Design Spec | `/pm-stage-04-design-spec` | `04-design-spec.md` **+** `04-design-spec.html` (rendered on approval) |
| Prototype Brief | `/pm-stage-05-prototype-brief` | `05-prototype-brief.md` **+** `05-prototype-mockup.html` (rendered on approval) |
| QA Plan | `/pm-stage-06-qa-plan` | `06-qa-plan.md` — use Opus |
| Metrics Plan | `/pm-stage-07-metrics-plan` | `07-metrics-plan.md` |

### Step 8: Optional capstones

Run either or both after stage 07 is approved:

```
# Technical Requirements Document (for engineering handoff)
/pm-stage-08-trd        # use Opus

# Product Roadmap (post-MVP sequencing)
/pm-stage-09-roadmap    # use Opus; uses TRD as context if it is approved
```

### Step 9: Share approved artifacts

```
/pm-share
```

Exports all approved stage artifacts to a single shareable text document for directors, stakeholders, or cross-functional teams.

### Step 10: Leave feedback

Capture a rating and note for any stage you want to flag:

```
/pm-feedback 03 --rating 4 --note "PRD was strong but the hallucination-mitigation section needs more depth"
```

---

## 7. The Stage Pipeline

### Core pipeline (always required)

| # | Stage | Command | Output file | Deep-reasoning |
|---|-------|---------|-------------|---------------|
| 00 | Business Statement | *(scaffolded by pm-new; edit manually)* | `00-business-statement.md` | No |
| 01 | Product Brief | `/pm-stage-01-brief` | `01-brief.md` | No |
| 02 | Product Scope | `/pm-stage-02-scope` | `02-scope.md` | No |
| 03 | PRD | `/pm-stage-03-prd` | `03-prd.md` | **Yes** |
| 04 | Design Spec | `/pm-stage-04-design-spec` | `04-design-spec.md` + `.html` | **Yes** |
| 05 | Prototype Brief | `/pm-stage-05-prototype-brief` | `05-prototype-brief.md` + `.html` | No |
| 06 | QA Plan | `/pm-stage-06-qa-plan` | `06-qa-plan.md` | **Yes** |
| 07 | Metrics Plan | `/pm-stage-07-metrics-plan` | `07-metrics-plan.md` | No |

### Optional capstones (run after stage 07)

| # | Stage | Command | Output file | Deep-reasoning |
|---|-------|---------|-------------|---------------|
| 08 | Technical Requirements Document | `/pm-stage-08-trd` | `08-trd.md` | **Yes** |
| 09 | Product Roadmap | `/pm-stage-09-roadmap` | `09-roadmap.md` | **Yes** |

Stage 09 uses stage 08 as additional context if it is approved. You can run 09 without 08.

### Context intake stages (optional, run before stage 01)

These run automatically when you use `/pm-context-import` (see [Section 10](#10-importing-existing-material)).

| # | Stage | What it produces |
|---|-------|-----------------|
| 00w | Context Wiki | `00-context-wiki.md` — synthesized knowledge base from your imported docs |
| 00u | Context Understanding | `00-context-understanding.md` — how your docs map to the pipeline |

Both are deep-reasoning stages. They feed into all downstream stage generations as additional context.

### Project structure

```
~/pm-projects/<slug>/
├── .meta.yaml                    ← project state (do not edit by hand)
├── 00-business-statement.md
├── 01-brief.md
├── 02-scope.md
├── 03-prd.md
├── 04-design-spec.md
├── 04-design-spec.html           ← rendered on stage 04 approval
├── 05-prototype-brief.md
├── 05-prototype-mockup.html      ← rendered on stage 05 approval
├── 06-qa-plan.md
├── 07-metrics-plan.md
├── 08-trd.md                     ← if run
├── 09-roadmap.md                 ← if run
├── telemetry.jsonl               ← append-only event log
├── feedback.jsonl                ← ratings and notes
└── .history/                     ← generation snapshots
```

---

## 8. Approval and the Gate Model

### What approval does

When you run `/pm-approve <NN>`, PM-OS:

1. Computes a deterministic hash of the artifact body
2. Stamps `approved_at`, `approved_by`, and `content_hash` into `.meta.yaml` and the artifact's YAML frontmatter
3. Records a snapshot of all upstream hashes at approval time
4. Marks all downstream **already-approved** stages as `stale` (they were generated from a now-superseded upstream)
5. Logs a `stage_approved` telemetry event

### Stage statuses

| Status | Meaning |
|--------|---------|
| `pending` | Not yet generated |
| `draft` | Generated, not yet approved |
| `approved` | Reviewed and locked by PM |
| `edited` | Approved, but the artifact body was changed after approval (hash drift detected) |
| `stale` | An upstream stage was re-approved; this stage's content may be out of date |

### What happens if you edit an approved artifact

Before the next stage generates, the gate re-hashes all upstream artifacts. If it detects that an approved artifact was edited (hash drift), it marks it `edited` and blocks generation. You will be asked:

1. **Implicit re-approval:** Accept the edit as a re-approval. The gate marks downstream approved stages `stale` and continues.
2. **Explicit re-approval:** Run `/pm-approve <NN>` on the edited stage yourself before continuing.
3. **Cancel:** Abort — go back and decide what you want to do.

In agent sessions (non-interactive), the gate always chooses option 2 — it blocks and tells you to re-approve explicitly.

### Clearing staleness

A `stale` stage means its content was generated from an older version of an upstream. To clear it:

1. Re-generate: `/pm-stage-NN-<name>`
2. Review the new output
3. Re-approve: `/pm-approve NN`

This cascades down: re-approving stage 03 after an edit marks stages 04–09 as stale — but only those that were already approved. Pending stages are unaffected.

---

## 9. Context Customization

PM-OS generates artifacts using a default output spec for each stage. You can customize this spec — the required sections, tone, terminology, and format — by filling in a **context overlay** that lives at `~/.pm-os/context/`.

This overlay is private to your machine and is never overwritten by PM-OS updates.

### What to fill in

**Global context** (applied to every stage, every project):

| File | What to put in it |
|------|------------------|
| `~/.pm-os/context/global/company.md` | Company mission, product surface, key audiences, how you build |
| `~/.pm-os/context/global/team.md` | Team structure, roles, norms, stakeholder map |
| `~/.pm-os/context/global/glossary.md` | Shared terminology, acronyms, product names to use consistently |
| `~/.pm-os/context/global/guardrails.md` | Compliance posture, accessibility standards, data-handling rules, brand constraints |

**Per-stage context** (applied to that stage only):

Each stage has two optional files under `~/.pm-os/context/stages/<NN>-<name>/`:

- `format.md` — the required/recommended sections for your organization's version of this artifact
- `example.md` — one or two filled-in real examples (few-shot, for tone and depth)

### Apply modes

Set per-stage in `~/.pm-os/context/context.yaml`:

| Mode | Effect |
|------|--------|
| `augment` *(default)* | PM-OS keeps its default sections and folds your custom context in |
| `override` | Your `format.md` sections replace the skill's default spec entirely |
| `reference-only` | Your examples are shown for tone and depth; structure is unchanged |

### How changes take effect

Edits to `~/.pm-os/context/` take effect immediately on the next stage generation. No restart or reinstall needed.

### Checking the manifest

The overlay manifest lives at `~/.pm-os/context/context.yaml`. Open it to see which stages have context configured and what apply mode each uses. Files containing only placeholder text (`TODO`) are silently skipped — they don't affect generation until you fill them in.

---

## 10. Importing Existing Material

If you already have material — a research brief, an old PRD, a design doc, user interview transcripts — you can import it before generating any stages. PM-OS will synthesize it into a context wiki and understanding doc, then adopt it into the pipeline where it fits rather than regenerating from scratch.

### Import documents

Run from inside the project directory:

```
/pm-context-import ~/Documents/q3-research.pdf ~/Documents/old-prd.docx
```

PM-OS:
1. Classifies each document and maps it to the relevant pipeline stage
2. Builds `00-context-wiki.md` — a synthesized, provenance-tagged knowledge base
3. Builds `00-context-understanding.md` — how your docs map to the pipeline
4. Shows you the mapping and asks for your approval
5. Adopts the documents you authored directly into the relevant stage artifacts
6. Faithfully backfills any upstream gaps

Use the strongest available model for this — it is deep-reasoning work.

### Import with a codebase scan (enhancement projects)

```
/pm-context-import ~/Documents/brief.md --codebase https://github.com/acme/platform
```

### Map a document directly to a stage

If you know exactly which stage a document belongs to:

```
/pm-context-import --as 01=~/Documents/existing-brief.md
```

### Enhancement mode

For adding features to an existing product rather than building from scratch, create the project in enhancement mode:

```
/pm-new salespilot-export --mode enhancement --codebase https://github.com/acme/salespilot
```

PM-OS runs a read-only codebase scan (producing `00-codebase-understanding.md`) and frames all downstream stages as a *delta* — what is new or missing — rather than describing the entire existing product.

If you don't have a codebase URL, omit it and describe the existing product in the business statement:

```
/pm-new salespilot-export --mode enhancement
```

---

## 11. All Commands — Quick Reference

### Starting projects

```bash
# New GenAI product
/pm-new trial-match "AI assistant for clinical trial patient matching" --genai

# New non-GenAI product
/pm-new onboarding-v2 "Redesign PM onboarding to cut time-to-value to 3 days" --no-genai

# Enhancement to an existing product — with codebase scan
/pm-new salespilot-export --mode enhancement --codebase https://github.com/acme/salespilot

# Enhancement — no codebase URL, describe existing product in business statement
/pm-new salespilot-export --mode enhancement
```

### Importing existing material

```bash
# Import documents before generating any stages
/pm-context-import ~/Documents/q3-research.pdf ~/Documents/old-prd.docx

# Import with a codebase scan at the same time
/pm-context-import ~/Documents/brief.md --codebase https://github.com/acme/platform

# Map a specific document directly to a stage (skip classification)
/pm-context-import --as 01=~/Documents/existing-brief.md

# Import multiple documents mapped to different stages
/pm-context-import --as 01=~/Documents/brief.md --as 03=~/Documents/prd-draft.docx
```

### Generating stages

```bash
# Standard stages (default model)
/pm-stage-01-brief
/pm-stage-02-scope
/pm-stage-05-prototype-brief
/pm-stage-07-metrics-plan

# Deep-reasoning stages — switch to Opus/strongest model first
# Claude Code:
/fast                         # toggles Opus
/pm-stage-03-prd
/pm-stage-04-design-spec
/pm-stage-06-qa-plan
/pm-stage-08-trd
/pm-stage-09-roadmap

# Codex: select o1/o3 in model settings, then:
$pm-stage-03-prd
$pm-stage-04-design-spec
$pm-stage-06-qa-plan
$pm-stage-08-trd
$pm-stage-09-roadmap
```

### Approving stages

```bash
/pm-approve 00    # business statement
/pm-approve 01    # brief
/pm-approve 03    # PRD — use two-digit stage number throughout
```

### Checking project state

```bash
/pm-status        # full project status table
```

### Leaving feedback

```bash
# Rating + note
/pm-feedback 03 --rating 4 --note "PRD missed the admin persona"

# Note only, skip rating prompt
/pm-feedback 04 --skip-rating --note "Design spec needs accessibility section expanded"

# Rating only, skip note prompt
/pm-feedback 06 --rating 5 --skip-note
```

### Sharing artifacts

```bash
/pm-share         # export all approved artifacts to shareable text
```

### Reconfigure

```bash
/pm-os-install --reconfigure    # re-prompt all config values
```

### Update PM-OS to the latest version

```bash
# From the terminal
python3 ~/.pm-os/scripts/pm_os_update.py --runtime all

# From inside Claude Code
/pm-os-update --runtime all

# From Codex
$pm-os-update --runtime all
```

### Verify install health

```bash
# From the terminal
python3 ~/.pm-os/scripts/pm_os_verify.py

# From inside Claude Code
/pm-os-verify

# From Codex
$pm-os-verify
```

### Prototype HTML

```bash
# Generate a standalone interactive prototype from an approved prototype brief
/pm-prototype-html
```

---

## 12. Failure Modes and Recovery

| Symptom | Cause | Fix |
|---------|-------|-----|
| `BLOCKED: upstream stage(s) are not approved` | A stage upstream is still `draft` or `pending` | Approve the blocking upstream: `/pm-approve <NN>` |
| `BLOCKED: upstream edited post-approval` | An approved artifact's body was changed after approval | Re-approve the edited upstream (`/pm-approve <NN>`), or confirm implicit re-approval when prompted |
| Stage shows `stale` in `/pm-status` | An upstream stage was re-approved after this stage was generated | Re-run the stage (`/pm-stage-NN-<name>`), review, re-approve |
| `Not inside a PM-OS project` | Running a command from a directory with no `.meta.yaml` ancestor | `cd ~/pm-projects/<slug>` first |
| `Config file not found` | Install incomplete or `config.yaml` missing | Re-run: `./install.sh --runtime all --pm-user <id> --reconfigure` |
| `pm_os_verify.py` fails — missing skills | Skills not synced to runtime dir | `python3 ~/.pm-os/scripts/pm_os_update.py --runtime all` |
| `pm_os_verify.py` fails — missing deps | `pyyaml` or `jinja2` not installed | `pip3 install pyyaml jinja2` |
| Gate self-test fails in verify | Hooks not found at `~/.pm-os/hooks/` | Reinstall: `./install.sh --runtime all` |
| `pm_os_update.py` refuses to fast-forward | Local `~/.pm-os` main has diverged (someone edited `~/.pm-os` by hand) | `python3 ~/.pm-os/scripts/pm_os_update.py --runtime all --reset-main` |
| HTML companion not generated after approving stage 04 or 05 | Post-approve hook failed silently | Run `/pm-os-verify` to check hook health; rerun `pm_os_update.py` if hooks are missing |
| `genai_flag` wrong | Set at project creation, cannot be changed | Start a new project with the correct flag; copy the business statement over manually |

### The one rule you must never break

**Never hand-edit `~/.pm-os/` directly** (except `~/.pm-os/context/`, which is yours to edit freely). The installed `~/.pm-os/` updates through exactly one path: `pm_os_update.py`. Manual edits to `lib/`, `hooks/`, or `skills/` inside `~/.pm-os` will diverge the local checkout and break future updates.

---

## 13. Keeping PM-OS Up to Date

### Standard update (from GitHub remote)

```bash
# Terminal
python3 ~/.pm-os/scripts/pm_os_update.py --runtime all

# Claude Code
/pm-os-update --runtime all

# Codex
$pm-os-update --runtime all
```

This fast-forwards `~/.pm-os` to `origin/main` and re-syncs skills and hooks to the runtime directories. Your `~/.pm-os/context/` is never touched.

### If you installed from a zip

There is no auto-update path from a zip install. To update:

1. Get the new zip from whoever maintains your PM-OS distribution
2. Extract it and re-run: `./install.sh --runtime all --source . --pm-user <your-id>`

### Checking your installed version

```bash
cat ~/.pm-os/VERSION
```

### After any update

Run `/pm-os-verify` once to confirm the new version is healthy before starting new projects.

---

## 14. Data and Privacy

**All artifacts are local by default.** Your project files, stage outputs, and `.meta.yaml` live entirely on your machine under `~/pm-projects/`. Nothing leaves your machine automatically.

**What the event log captures:** stage timings, content hashes, model tier used, character edit distances between drafts and approvals, and optional ratings and notes you add via `/pm-feedback`. It does not capture the content of your artifacts.

**Sanitize inputs before generation.** Treat your business statement and steering notes the same way you treat email: no raw PII, no confidential patient or customer data, no internal codenames that shouldn't leave your org's systems. Use placeholders (`[patient cohort A]`, `[internal product X]`) and replace them in the final approved document.

**Abstract early, be specific late.** Describe features precisely in your business statement. Do not paste a patient list, a financial model, or a confidential term sheet into a prompt.

---

*PM-OS v1 covers the product-definition phase (stages 01–09). Dev handoff, QA triage, release, and feedback loop phases are planned for future versions.*
