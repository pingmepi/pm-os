# PM-OS User Guide

*How to install, configure, and use PM-OS — from first setup to first approved artifact.*

> **Who this is for:** PMs who attended the demo and received the PM-OS zip file, or anyone setting up PM-OS for the first time. This guide walks you through every step independently.

---

## Table of Contents

1. [What is PM-OS?](#1-what-is-pm-os)
2. [Prerequisites](#2-prerequisites)
3. [Installation](#3-installation)
4. [Verify Your Install](#4-verify-your-install)
5. [Recommended Setup](#5-recommended-setup)
6. [Your First Project — End-to-End Walkthrough](#6-your-first-project--end-to-end-walkthrough)
7. [The Stage Pipeline (Reference)](#7-the-stage-pipeline-reference)
8. [Approval and the Gate Model](#8-approval-and-the-gate-model)
9. [Context Customization](#9-context-customization)
10. [Importing Existing Material](#10-importing-existing-material)
11. [All Commands Quick Reference](#11-all-commands-quick-reference)
12. [Failure Modes and Recovery](#12-failure-modes-and-recovery)
13. [Keeping PM-OS Up to Date](#13-keeping-pm-os-up-to-date)
14. [Data and Privacy Notes](#14-data-and-privacy-notes)

---

## 1. What is PM-OS?

PM-OS is a **PM-led product development operating layer** built as an agent skill suite. It is not a web app and has no backend service — it runs entirely on your machine as a set of commands you invoke inside Claude Code (or Codex).

A PM drives a product idea through a gated pipeline of stages. Each stage produces a Markdown artifact that you read, edit, and explicitly approve before the next stage can run. The agent (Claude) drafts each artifact; you make every decision.

**The core loop:**

```
  /pm-new  →  Stage 01 (Brief)  →  /pm-approve 01
           →  Stage 02 (Scope)  →  /pm-approve 02
           →  Stage 03 (PRD)    →  /pm-approve 03
           →  ...all stages...
           →  /pm-share
```

**What PM-OS is NOT:**
- Not a SaaS tool — no account, no login, no data sent to a server
- Not autonomous — nothing progresses without your explicit `/pm-approve`
- Not a template filler — the agent reasons from your approved upstream artifacts

**Decision authority model:** The agent drafts and the gate enforces sequencing. You review, edit, and approve. Nothing moves forward unless you say so.

---

## 2. Prerequisites

Check each of the following before running the installer.

### Claude Code

Claude Code is the agent runtime that runs PM-OS skills. Install it from [claude.ai/code](https://claude.ai/code) if you don't have it already.

To check: open a terminal and run:
```bash
claude --version
```
If you see a version number, you're good.

### Python 3.11 or higher

PM-OS gate logic runs in Python. You need version 3.11 or later.

To check:
```bash
python3 --version
```
You should see `Python 3.11.x` or higher.

**If Python is missing or too old:**
- **Mac:** `brew install python@3.13` (requires [Homebrew](https://brew.sh))
- **Ubuntu/WSL:** `sudo apt update && sudo apt install python3.13`
- **Windows (native):** Download from [python.org](https://www.python.org/downloads/), check "Add to PATH"

### Git

Used by PM-OS to push telemetry and handle updates.

To check:
```bash
git --version
```
If missing:
- **Mac:** `brew install git`
- **Ubuntu/WSL:** `sudo apt install git`
- **Windows (native):** [git-scm.com](https://git-scm.com)

### Internet access (for standard install)

The standard install clones from GitHub and pip-installs `pyyaml` and `jinja2`. If you're in a network-restricted environment or installing from the zip, see the **Offline install** path in §3.

---

## 3. Installation

### A. Standard install (from GitHub)

This is the recommended path if you have GitHub access.

```bash
git clone https://github.com/pingmepi/pm-os.git
cd pm-os
./install.sh --runtime claude \
  --pm-user <your-id> \
  --feedback-repo <team-repo-url>
```

Replace the values:
- `<your-id>` — your unique PM identifier. Use `firstname-lastname` or `fLastname`, all lowercase, no spaces. Example: `jane-smith`. **This is permanent** — it appears in team telemetry, so use the same ID forever.
- `<team-repo-url>` — the shared feedback repo your team lead gives you. Example: `https://github.com/yourorg/pm-os-feedback.git`

Optional flags:
```bash
  --projects-dir ~/work/pm-projects   # override default ~/pm-projects
  --reconfigure                        # re-run config prompts if already installed
```

A successful install prints:
```
✓ PM-OS installed to ~/.pm-os
✓ Skills synced to ~/.claude/skills (N skills)
✓ Hooks installed to ~/.claude/hooks
✓ Config written to ~/.pm-os/config.yaml
✓ pm_os_verify passed all checks.
PM-OS v0.x.x is ready.
```

---

### B. Offline install (from the demo zip)

If you received `pm-os.zip` and don't have direct GitHub access:

```bash
unzip pm-os.zip
cd pm-os
./install.sh --runtime claude --source . \
  --pm-user <your-id> \
  --feedback-repo <team-repo-url>
```

The `--source .` flag tells the installer to use the local directory instead of cloning from GitHub.

> For more complex scenarios (bundled Python wheels, GitLab mirrors, IT/MDM zero-touch deploy), see [`docs/guides/offline-install.md`](offline-install.md).

---

### C. Config flags explained

| Flag | Required? | Description |
|---|---|---|
| `--runtime claude` | **Yes** | Route skills to `~/.claude/skills`. Use `codex` for Codex. |
| `--pm-user <id>` | Recommended | Your PM identifier for telemetry attribution |
| `--feedback-repo <url>` | Recommended | Team git repo where ratings and telemetry are pushed |
| `--projects-dir <path>` | Optional | Where PM-OS creates project folders (default: `~/pm-projects`) |
| `--source <dir>` | Optional | Local directory to install from instead of GitHub |
| `--reconfigure` | Optional | Overwrite an existing config interactively |

---

## 4. Verify Your Install

Run the verifier right after install — and any time something feels wrong:

```bash
python3 ~/.pm-os/scripts/pm_os_verify.py
```

Or from inside Claude Code:
```
/pm-os-verify
```

**What it checks (10 checks total):**
1. PM-OS install directory present
2. VERSION file readable
3. Lib modules importable (`project`, `hashing`, `config`, `telemetry`, etc.)
4. Gate hooks present (`pre-stage.py`, `post-approve.py`)
5. Config valid and all required keys present
6. Skills installed for your runtime
7. Gate self-test (blocks unapproved upstream, allows first stage)
8. Telemetry self-test (append, hash-chain, push status)
9. Artifact contract self-test (detects missing required sections)
10. Context overlay manifest parseable

**A passing run looks like:**
```
PM-OS Verify
============
Runtime: claude

  ✓ PM-OS install present (~/.pm-os)
  ✓ VERSION readable (0.x.x)
  ✓ Shared lib imports
  ✓ Gate hooks present (~/.pm-os/hooks)
  ✓ Config valid (~/.pm-os/config.yaml)
  ✓ claude skills installed (12/12)
  ✓ Gate self-test (blocks unapproved upstream, allows first stage)
  ✓ Telemetry self-test (append + hash chain + push status)
  ✓ Artifact contract self-test (detects missing PRD journeys)
  ✓ Context overlay manifest

PASS: PM-OS install is healthy.
```

**If a check fails**, the verifier prints the problem and a fix. Common fixes:

| Failure | Fix |
|---|---|
| `Config file not found` | Re-run `./install.sh` with all required flags |
| `claude skills installed (8/12)` | Run `python3 ~/.pm-os/scripts/pm_os_update.py --runtime claude` |
| `pyyaml not found` | Run `pip3 install pyyaml jinja2` |
| `Gate self-test failed` | Confirm Python version is 3.11+ with `python3 --version` |

---

## 5. Recommended Setup

### Where projects live

By default, PM-OS creates projects in `~/pm-projects/`. Each project gets its own subdirectory:
```
~/pm-projects/
  onboarding-redesign/
    .meta.yaml
    00-business-statement.md
    01-brief.md
    ...
  crm-export/
    ...
```

You don't need to create the project directory — `/pm-new` does it for you.

### Model recommendations for deep-reasoning stages

Some stages carry the most downstream weight and benefit significantly from the strongest available model. These are stages **03 (PRD)**, **04 (Design Spec)**, **06 (QA Plan)**, **08 (TRD)**, and **09 (Roadmap)**.

Before generating these stages, toggle Opus in Claude Code:
```
/fast
```
This switches to Opus for the current session. Toggle it off after if needed.

### GenAI flag

When starting a project, declare whether the product uses AI/ML:
- `--genai` — the product uses a language model, recommendation engine, or AI agent. GenAI-specific sections are added to relevant stages (AI data sourcing, model governance, GenAI failure modes).
- `--no-genai` — standard product. No AI-specific sections.

### Always run PM-OS commands from inside the project directory

PM-OS finds the active project by walking up from your current directory to the nearest `.meta.yaml`. If you run a command from the wrong directory, it will error or act on the wrong project.

```bash
cd ~/pm-projects/onboarding-redesign
# now run /pm-approve, /pm-stage-*, /pm-status etc.
```

---

## 6. Your First Project — End-to-End Walkthrough

Use a real idea from your current work, or follow the example below.

---

### Step 1 — Create the project

In Claude Code:
```
/pm-new onboarding-redesign "We need to redesign the PM onboarding flow to cut time-to-first-value from 2 weeks to 3 days" --no-genai
```

Breaking this down:
- `onboarding-redesign` — the **slug**. Lowercase, hyphenated, short. Becomes the folder name. Can't be changed later.
- `"We need to redesign..."` — the **business statement**. One or two sentences: problem + goal. No PII, no customer names.
- `--no-genai` — this product doesn't use AI/ML.

**Expected output:**
```
[pm-new] Scaffolded project: onboarding-redesign
[pm-new] Created: ~/pm-projects/onboarding-redesign/
[pm-new]   .meta.yaml
[pm-new]   00-business-statement.md
[pm-new] Stage 00 status: draft
[pm-new] Next: review 00-business-statement.md, then run /pm-approve 00
```

---

### Step 2 — Review and approve the business statement

Open `~/pm-projects/onboarding-redesign/00-business-statement.md` in any editor or in Claude Code. Read it, edit the wording if needed, then:

```
/pm-approve 00
```

**Expected output:**
```
[approve] Stage 00 (business-statement) approved.
[approve] Content hash recorded.
[approve] Telemetry: stage_approved logged.
[approve] Ready to generate stage 01.
```

> **The rule:** approve only when you and your named reviewer are satisfied. Approving to unblock yourself defeats the gate.

---

### Step 3 — Generate the Product Brief

```
/pm-stage-01-brief
```

Claude reads your approved business statement and produces `01-brief.md`. Takes 20–60 seconds. Read the draft, edit freely, then:

```
/pm-approve 01
```

---

### Step 4 — Generate the Scope

```
/pm-stage-02-scope
```

Produces `02-scope.md`: what's in scope for MVP, explicit out-of-scope items, constraints, and assumptions. Review, edit, approve:

```
/pm-approve 02
```

---

### Step 5 — Check status mid-pipeline

At any point:
```
/pm-status
```

**Expected output:**
```
Project: onboarding-redesign  [non-GenAI]
────────────────────────────────────────────
  00  business-statement  ✓ approved
  01  brief               ✓ approved
  02  scope               ✓ approved
  03  prd                 ○ pending
  04  design-spec         ○ pending
  05  prototype-brief     ○ pending
  06  qa-plan             ○ pending
  07  metrics-plan        ○ pending
  08  trd                 ○ (optional)
  09  roadmap             ○ (optional)
```

---

### Step 6 — Generate the PRD (deep-reasoning stage)

The PRD drives the design spec, QA plan, and metrics plan. Use the strongest model:

```
/fast
```
Then:
```
/pm-stage-03-prd
```

This takes 1–3 minutes. The output includes user stories, acceptance criteria, edge cases, data governance, and success criteria. Review carefully — a weak PRD propagates downstream. When satisfied:

```
/pm-approve 03
```

---

### Step 7 — Continue through the pipeline

Repeat generate → review → edit → approve for each remaining stage. Stages 04 and 06 are also deep-reasoning stages; run them on Opus too.

```
/pm-stage-04-design-spec     → /pm-approve 04
/pm-stage-05-prototype-brief → /pm-approve 05
/pm-stage-06-qa-plan         → /pm-approve 06
/pm-stage-07-metrics-plan    → /pm-approve 07
```

After approving stage 04, PM-OS automatically renders `04-design-spec.html` — an HTML companion you can open in a browser and share with design/eng.

After approving stage 05, PM-OS renders `05-prototype-mockup.html` — a clickable HTML prototype.

---

### Step 8 — Optional capstone stages

After all of 01–07 are approved:

```
/pm-stage-08-trd      → /pm-approve 08    (Technical Requirements Document)
/pm-stage-09-roadmap  → /pm-approve 09    (Product Roadmap)
```

Stage 09 automatically uses the approved TRD (08) if it exists — generate and approve 08 before 09 if you want technical context in your roadmap.

---

### Step 9 — Share approved artifacts

```
/pm-share
```

Exports the approved artifact chain in a clean, readable format suitable for stakeholders. Only approved stages appear in the output — drafts are excluded.

---

## 7. The Stage Pipeline (Reference)

### Core pipeline (required)

| # | Stage name | Command | Output files | Deep-reasoning? |
|---|---|---|---|---|
| 00 | Business Statement | *(created by `/pm-new`)* | `00-business-statement.md` | No |
| 01 | Product Brief | `/pm-stage-01-brief` | `01-brief.md` | No |
| 02 | Scope | `/pm-stage-02-scope` | `02-scope.md` | No |
| 03 | PRD | `/pm-stage-03-prd` | `03-prd.md` | **Yes** |
| 04 | Design Spec | `/pm-stage-04-design-spec` | `04-design-spec.md` + `.html` | **Yes** |
| 05 | Prototype Brief | `/pm-stage-05-prototype-brief` | `05-prototype-brief.md` + `.html` | No |
| 06 | QA Plan | `/pm-stage-06-qa-plan` | `06-qa-plan.md` | **Yes** |
| 07 | Metrics Plan | `/pm-stage-07-metrics-plan` | `07-metrics-plan.md` | No |

### Optional capstone stages

| # | Stage name | Command | Output files | Deep-reasoning? |
|---|---|---|---|---|
| 08 | TRD | `/pm-stage-08-trd` | `08-trd.md` | **Yes** |
| 09 | Roadmap | `/pm-stage-09-roadmap` | `09-roadmap.md` | **Yes** |

### Context intake stages (run before the main pipeline when importing existing material)

| # | Stage name | How triggered | What it produces |
|---|---|---|---|
| 00c | Codebase Understanding | `/pm-context-scan-codebase` | `00-codebase-understanding.md` |
| 00w | Context Wiki | `/pm-context-import` | `00-context-wiki.md` |
| 00u | Context Understanding | `/pm-context-import` | `00-context-understanding.md` |

See §10 for details on importing existing material.

---

## 8. Approval and the Gate Model

### What approval does

Running `/pm-approve NN`:
1. Hashes the artifact body and saves the hash to `.meta.yaml` and the artifact's YAML frontmatter
2. Records who approved it and when
3. Unlocks downstream generation (the pre-stage gate checks the hash)
4. Triggers post-approval actions: HTML rendering for stages 04/05, telemetry push to the feedback repo

### What happens if you edit an approved artifact

If you edit the body of an approved artifact, the next generation attempt detects the hash mismatch and gives you a choice:

1. **Implicit re-approval** — accept the edited version as the new approved content, cascade staleness to downstream approved stages, and continue
2. **Explicit re-approval** — run `/pm-approve NN` again for the edited stage, then retry

Either path is valid. Small edits (typo, rephrasing): use implicit. Decision changes: use explicit so there's a clear approval record.

Re-approving upstream **cascades staleness** to all approved downstream stages — they'll need to be regenerated to reflect the change.

### Stage statuses

| Status | Meaning |
|---|---|
| `pending` | Not yet generated |
| `draft` | Generated, not yet approved |
| `approved` | Reviewed and approved — gate is open |
| `edited` | Approved, but body changed since approval — gate will prompt |
| `stale` | An upstream stage was re-approved after this stage — regeneration needed |

---

## 9. Context Customization

The **context overlay** teaches PM-OS your company's terminology, format standards, and constraints. Without it, every stage uses generic defaults. With it, every artifact reflects your org's language and structure.

The overlay lives at: `~/.pm-os/context/`

The installer seeds this folder from the template in the repo. You edit files there directly — changes take effect on the next generation. Your edits are never overwritten by updates.

### 9.1 Global context files

These apply to every project, every stage:

```
~/.pm-os/context/global/
  company.md    ← what the company does, domains, regulatory posture
  team.md       ← PM team structure, engineering partners, approval flow
  glossary.md   ← shared terminology, product names, acronyms
  guardrails.md ← data handling, compliance, accessibility, brand rules
```

Open each file and replace the `<!-- TODO: ... -->` placeholders with your real content. A few examples:

**`global/company.md` (example)**
```markdown
## Who we are
Acme Corp builds B2B SaaS tools for enterprise sales teams. Our flagship product,
SalesPilot, helps field reps log calls, track deals, and surface coaching recommendations.

## Domains & product surfaces
- SalesPilot web app (primary surface)
- SalesPilot mobile app (iOS + Android)
- Admin console for IT and RevOps

## Regulatory & compliance posture
SOC 2 Type II certified. GDPR compliance required for EU customers.
No PHI/PII in product telemetry.
```

**`global/glossary.md` (example)**
```markdown
## Product terminology
- **SalesPilot** — flagship desktop + mobile sales tool (never "the app")
- **Rep** — a sales representative using SalesPilot
- **Manager** — has coaching view and team rollup access
- **Coaching card** — AI-generated nudge shown to managers based on rep activity

## Acronyms
- **ACV** — Annual Contract Value
- **ICP** — Ideal Customer Profile
```

**`global/guardrails.md` (example)**
```markdown
## Data handling
- Never include customer names, deal names, or email addresses in artifacts
- Rep activity data is PII-adjacent — describe patterns, not individual records

## Compliance
- All new features touching customer data require a Data & Privacy review
- GDPR right-to-erasure must be addressed in any PRD that creates new data stores

## Accessibility
- WCAG 2.1 AA is the minimum bar for all new product surfaces
```

### 9.2 Per-stage format and examples

For each stage you can provide:
- **`format.md`** — required sections and structure for that stage
- **`example.md`** — one or two real filled-in examples (few-shot reference)

These live at:
```
~/.pm-os/context/stages/
  01-brief/
    format.md
    example.md
  03-prd/
    format.md
    example.md
  ... (01 through 09)
```

**Fastest way to get started:** paste a real artifact your team previously approved into `example.md` for stages 03 and 04 (the highest-value stages). Strip confidential data first.

**`apply` mode** in `~/.pm-os/context/context.yaml` controls how PM-OS uses your customization:

| Mode | Behavior |
|---|---|
| `augment` *(default)* | PM-OS default sections + your custom ones |
| `override` | Your `format.md` replaces the skill's default structure entirely |
| `reference-only` | Your `example.md` guides tone only; structure unchanged |

To change the mode for a specific stage, edit `~/.pm-os/context/context.yaml`:
```yaml
stages:
  "03":
    format:   stages/03-prd/format.md
    examples: [stages/03-prd/example.md]
    apply: override     # my PRD template is the complete spec
  "01":
    format:   stages/01-brief/format.md
    apply: augment      # add my sections on top of defaults
```

---

## 10. Importing Existing Material

### Import existing documents

If you already have a brief, PRD, or research notes:

```
/pm-context-import ~/Documents/q3-brief.md ~/Documents/user-research-summary.pdf
```

PM-OS reads your documents and produces:
- `00-context-wiki.md` — structured knowledge extracted from your docs
- `00-context-understanding.md` — what PM-OS understood about your product intent and gaps

Both are gated stages — you review and approve them before generation continues. Once approved, all downstream stages use them as additional context.

### Scan a codebase (enhancement mode)

When adding a feature to an existing product, scan the codebase first:

```
/pm-context-scan-codebase https://github.com/acme/salespilot
```

This produces `00-codebase-understanding.md` — a structured summary of the current system. All downstream stages use this to frame the **delta** (what's new), not re-describe the whole product.

Or start the project in enhancement mode directly:

```
/pm-new feature-coaching-alerts "Add rep activity coaching alerts for managers" --no-genai --mode enhancement --codebase https://github.com/acme/salespilot
```

---

## 11. All Commands Quick Reference

### Project lifecycle

| Command | Example | What it does |
|---|---|---|
| `/pm-new <slug> "<statement>" --genai\|--no-genai` | `/pm-new crm-export "Add bulk export for managers" --no-genai` | Create a new project |
| `/pm-new ... --mode enhancement --codebase <url>` | `/pm-new coaching-v2 "Add coaching alerts" --no-genai --mode enhancement --codebase https://github.com/acme/salespilot` | Create an enhancement project with codebase scan |
| `/pm-approve <NN>` | `/pm-approve 03` | Approve a stage after review |
| `/pm-status` | `/pm-status` | Show all stage statuses for current project |
| `/pm-share` | `/pm-share` | Export approved artifacts for stakeholders |
| `/pm-feedback <NN>` | `/pm-feedback 03 --rating 4 --note "PRD was strong but missed admin persona"` | Rate a stage and leave a note |
| `/pm-sync` | `/pm-sync` | Push pending telemetry/feedback to team repo |

### Generation commands

Run these in order, from inside your project directory:

| Command | Stage | Use Opus? |
|---|---|---|
| `/pm-stage-01-brief` | Product Brief | No |
| `/pm-stage-02-scope` | Scope | No |
| `/pm-stage-03-prd` | PRD | **Yes — run `/fast` first** |
| `/pm-stage-04-design-spec` | Design Spec | **Yes** |
| `/pm-stage-05-prototype-brief` | Prototype Brief | No |
| `/pm-stage-06-qa-plan` | QA Plan | **Yes** |
| `/pm-stage-07-metrics-plan` | Metrics Plan | No |
| `/pm-stage-08-trd` | TRD (optional) | **Yes** |
| `/pm-stage-09-roadmap` | Roadmap (optional) | **Yes** |

To toggle Opus before a deep-reasoning stage:
```
/fast
```
Run `/fast` again to toggle it off.

### Context and import

| Command | Example | What it does |
|---|---|---|
| `/pm-context-import <files>` | `/pm-context-import ~/Documents/brief.md ~/Documents/research.pdf` | Ingest existing docs into a context wiki |
| `/pm-context-scan-codebase <url>` | `/pm-context-scan-codebase https://github.com/acme/salespilot` | Scan a codebase for enhancement mode |
| `/pm-context-scan-docs <url>` | `/pm-context-scan-docs https://github.com/acme/salespilot` | Scan docs for context |
| `/pm-prototype-html` | `/pm-prototype-html` | Re-render the HTML prototype for stage 05 |

### Maintenance

| Command | Example | What it does | When to run |
|---|---|---|---|
| `/pm-os-verify` | `/pm-os-verify` | Health check: config, deps, skills, gate | After install or when something feels wrong |
| `/pm-os-update` | `/pm-os-update` | Pull latest PM-OS, resync skills + hooks | When team lead announces a new version |
| `/pm-os-install` | `/pm-os-install --reconfigure` | Reconfigure an existing install | When changing pm-user or feedback-repo |

Or from terminal (equivalent):
```bash
python3 ~/.pm-os/scripts/pm_os_verify.py --runtime claude
python3 ~/.pm-os/scripts/pm_os_update.py --runtime claude
```

---

## 12. Failure Modes and Recovery

### Gate blocks

**"Upstream stage(s) not approved"**

A stage you're trying to generate has an unapproved upstream.

Fix: Run `/pm-status` to see which stages are pending or draft. Approve them first with `/pm-approve NN`, then retry.

---

**"Upstream stage was edited after approval"**

You edited an approved artifact, and the gate detected the hash change.

Fix: PM-OS will prompt you to choose:
1. **Implicit re-approve** — accept the edit, cascade staleness, continue
2. **Explicit re-approve** — run `/pm-approve NN` for the edited stage, then retry

---

**"Stage is stale"**

An upstream stage was re-approved after this stage was already approved.

Fix: Regenerate the stale stage (`/pm-stage-NN-*`), then review and re-approve it.

---

### Setup and path issues

| Symptom | Cause | Fix |
|---|---|---|
| "Not inside a PM-OS project" | Running from wrong directory | `cd ~/pm-projects/<slug>` then retry |
| "Config file not found" | Install incomplete or not run | Re-run `./install.sh` with all required flags |
| Skills missing after update | Skills not synced | `python3 ~/.pm-os/scripts/pm_os_update.py --runtime claude` |
| Gate self-test failed | Python version or hook path issue | Check `python3 --version` (needs 3.11+) and re-run `./install.sh` |
| "Central sync FAILED" | Network or repo access issue | Work is safe locally. Retry later with `/pm-sync` |
| Local `main` diverged | Someone edited `~/.pm-os` directly | `python3 ~/.pm-os/scripts/pm_os_update.py --runtime claude --reset-main` |

### Common mistakes to avoid

| Mistake | What happens | How to avoid |
|---|---|---|
| Approving to unblock yourself | The gate becomes a rubber stamp; downstream stages build on an unreviewed decision | Approve only after the named reviewer has read the draft |
| Editing `.meta.yaml` by hand | Corrupts the state machine | Only edit Markdown artifact files; let PM-OS commands manage state |
| Running PM-OS commands outside the project directory | Acts on the wrong project (or fails) | Always `cd ~/pm-projects/<slug>` before running commands |
| Using a lightweight model on deep-reasoning stages | The highest-leverage stages get under-reasoned output | Use `/fast` before stages 03, 04, 06, 08, 09 |
| Sharing draft artifacts with stakeholders | Stakeholders act on unfinished content | Only run `/pm-share` after all relevant stages are approved |
| Putting customer names or PII in the business statement | Sensitive data lands in local files and pushed telemetry | Use generic descriptions: "enterprise sales reps" not real customer names |

---

## 13. Keeping PM-OS Up to Date

When your team lead announces a new PM-OS version:

```
/pm-os-update
```

Or from terminal:
```bash
python3 ~/.pm-os/scripts/pm_os_update.py --runtime claude
```

**What the update does:**
1. Fast-forwards `~/.pm-os` to `origin/main`
2. Resyncs all updated skills to `~/.claude/skills`
3. Resyncs hooks to `~/.claude/hooks`

After updating, run the verifier to confirm everything is healthy:
```bash
python3 ~/.pm-os/scripts/pm_os_verify.py
```

> **Your context customization is never overwritten by updates.** The `~/.pm-os/context/` folder is user data. Updates may add new seed files for stages that didn't exist before, but your edits to `company.md`, `team.md`, stage examples, etc. are always preserved.

**Important:** Never edit files directly inside `~/.pm-os/`. Manual edits there diverge the local checkout, which causes the update script to refuse to fast-forward. If this happens, recover with `--reset-main` (see §12).

---

## 14. Data and Privacy Notes

### What stays local

All PM-OS artifacts (`.md` files, `.meta.yaml`, `.html` companions) live on your machine under `~/pm-projects/<slug>/`. Nothing is uploaded to a cloud service.

### What gets pushed to the feedback repo

After each `/pm-approve` and `/pm-feedback`, PM-OS pushes:
- A hash-chained telemetry event (event type, stage, timestamp, project slug)
- Your feedback rating and note (if you ran `/pm-feedback`)

**No artifact content is ever pushed.** The feedback repo contains only structured metadata — no PRD text, no business statements, no user stories.

### Sanitize inputs before generation

PM-OS generates artifacts from what you give it. Before running any generation command:
- Use generic descriptions, not real customer names, deal names, or project codes
- Do not include email addresses, phone numbers, or internal system credentials in your business statement or imported docs
- If you're in a regulated environment (HIPAA, GxP, etc.), fill in `global/guardrails.md` with your specific constraints — PM-OS will apply them at generation time

---

*For process governance, decision authority, and best-fit use cases, see [`docs/guides/sop.md`](sop.md).*
*For the full build specification and architecture, see [`docs/reference/pm-os-spec.md`](../reference/pm-os-spec.md).*
*For offline/zip/MDM install variants, see [`docs/guides/offline-install.md`](offline-install.md).*
