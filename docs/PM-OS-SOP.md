# PM-OS Standard Operating Procedure

**Audience:** Product managers and the cross-functional partners (design, engineering, QA, data) who review or consume PM-OS artifacts.
**Status:** Recommended defaults. Teams may adapt the governance below to project size and risk, but should do so deliberately, not by accident.
**Applies to:** PM-OS v1 across both supported runtimes (Claude Code and OpenAI Codex).

---

## 1. Purpose

PM-OS is a PM-led PDLC operating layer. It maintains one coherent thread from idea to ship — intake, product definition, design, dev handoff, QA, release readiness, and feedback — with the PM in control at every decision point.

**v1 scope:** PM-OS currently covers the product-definition phase — a gated pipeline from business statement to a reviewed chain of product artifacts: brief → scope → PRD → design spec → prototype brief → QA plan → metrics plan, with an optional technical capstone (TRD). Each stage is a Markdown file that a human reviews and explicitly approves before the next stage is generated. Approved upstream artifacts are the binding source of truth for everything downstream.

This SOP defines **how, when, and where** to use PM-OS, the best-fit use cases, and the pitfalls to avoid. It is about *process discipline*, not the tool's internals.

### Decision authority

PM-OS is not the final decision-maker and is not an executor. These roles are distinct and non-negotiable:

| Role | Responsibility |
|---|---|
| **PM decides** | Scope, trade-offs, approvals, priority, release calls, and whether to proceed |
| **PM-OS suggests, prepares, validates** | Drafts artifacts, checks upstream consistency, recommends next actions, coordinates lifecycle state |
| **Developers and QAs execute** | Implementation and testing — PM-OS supports them but does not replace them |

No stage progresses autonomously. Every gate requires explicit PM approval.

### What PM-OS is for
- Taking a fuzzy idea to a structured, reviewable product definition fast.
- Keeping product decisions, design intent, QA, and metrics in one traceable chain.
- Giving every stage a named human owner and an explicit approval gate.
- Producing artifacts that are reproducible, diffable, and easy to edit in Markdown.
- *(Planned)* Dev handoff, QA bug triage, release readiness, and feedback ingestion — coming in later phases.

### What PM-OS is not
- Not a replacement for product judgment. It drafts and recommends; the PM decides.
- Not a system of record for live execution (use Jira/Linear/Asana for that).
- Not a place for confidential customer data, PHI, PII, secrets, or credentials.
- Not a sign-off authority. Approving a stage in PM-OS records *your* decision; it does not substitute for whatever formal sign-off your org requires.

---

## 2. When to use PM-OS

Use PM-OS when **most** of the following are true:

| Signal | Why it fits |
|---|---|
| The idea is new or being re-scoped | The pipeline shines at going from a blank page to a structured definition. |
| You want a traceable decision chain | Each stage cites approved upstream artifacts, so decisions don't drift silently. |
| Multiple functions need a shared source of truth | Design, eng, QA, and data all read from the same approved Markdown. |
| The work spans more than a throwaway experiment | The stage overhead pays off when the artifact will be read by others. |
| Inputs can be sanitized | The business statement and notes contain no confidential or regulated data. |

**In v1**, the entry point is always a new business statement. Later phases will add entry points for existing PRDs, repos, Jira/Linear tickets, QA bugs, and existing-product enhancement work — but all will follow the same PM-approval model.

### When **not** to use it (or use a lighter touch)
- **Tiny or throwaway work** — a one-line bug fix or a quick spike doesn't need an eight-stage pipeline. The ceremony will cost more than it returns.
- **Decisions already made and documented elsewhere** — don't regenerate a PRD that already exists and is being executed against; you'll create a competing source of truth.
- **Inputs you cannot sanitize** — if the only useful framing requires PHI/PII/secrets, stop and resolve the data-handling question first (see §7).
- **Live incident or execution tracking** — PM-OS defines product intent and coordinates lifecycle state; it is not a ticket tracker or status board.

> Rule of thumb: if the artifact will be **read and relied on by someone other than you**, PM-OS is worth it. If it's a personal scratchpad, it probably isn't.

---

## 3. Roles & responsibilities

PM-OS keeps the PM in control at every stage boundary, but the *reviewers* of each stage differ. Assign a named owner and a named reviewer per stage before you start.

| Stage | Artifact | Driver | Recommended reviewer(s) before approval |
|---|---|---|---|
| 01 | Product brief | PM | Product lead / sponsor |
| 02 | Scope (MVP) | PM | Product lead, eng lead (feasibility sanity check) |
| 03 | PRD *(deep-reasoning)* | PM | Eng lead, design lead |
| 04 | Design spec | PM + design | Design lead |
| 05 | Prototype brief | PM + design | Design lead, eng lead |
| 06 | QA plan *(deep-reasoning)* | PM + QA | QA lead |
| 07 | Metrics plan | PM + data | Data/analytics owner |
| 08 | TRD *(optional, deep-reasoning)* | Eng + PM | Eng lead / architect |

- **Driver** runs the generate command, edits the draft, and requests review.
- **Reviewer** reads the draft and gives the go/no-go. Approval should follow review, not precede it.
- One person can hold multiple hats on a small project — but the *roles* should still be conscious choices, not skipped.

**Deep-reasoning stages (03, 06, 08)** carry the most downstream weight (requirements, quality bar, technical commitments). Run these on your strongest available reasoning model — Opus for Claude users, a high/deep reasoning model for Codex users — and give them a more careful human review.

---

## 4. The standard workflow

> Commands are shown for both runtimes. Claude uses `/slash` commands; Codex uses `$skill` invocations or the `/skills` picker.

### 4.1 One-time setup (per machine)
```bash
# Claude
./install.sh --runtime claude
# Codex
./install.sh --runtime codex
```
The `--runtime` argument is required so skills install into the correct agent directory.

### 4.2 Start a project
```text
Claude: /pm-new <project-slug> "<business statement>" --genai|--no-genai
Codex:  $pm-new <project-slug> "<business statement>" --genai|--no-genai
```
- Keep the slug short and stable; it's used in paths and history.
- Write the business statement in plain language. **Sanitize it first** (§7).
- Pass `--genai` or `--no-genai` to set whether this is a GenAI/agentic product. In an interactive shell `pm-new` prompts; run non-interactively (the usual case inside an agent) you must pass the flag (or set `PM_OS_GENAI_FLAG`).
- The project is created under the `projects_dir` from your config (default `~/pm-projects`).
- This seeds `00-business-statement.md` and `.meta.yaml`, including the `genai_flag` that controls whether stages emit GenAI-specific sections.

### 4.3 Generate → review → approve, one stage at a time
For each stage, in order:
```text
Claude: /pm-stage-01-brief        Codex: $pm-stage-01-brief
   (read the draft, edit if needed, have the reviewer look)
Claude: /pm-approve 01            Codex: $pm-approve 01
```
Then 02, 03, … 07. The optional TRD (08) comes after 01–07 are approved.

**The core discipline (recommended default — relax only with eyes open):**
1. **Never generate a downstream stage from an unapproved upstream stage.** The gate exists to stop drift. If a pre-stage gate exits non-zero, stop and read the error; do not write the artifact anyway.
2. **Approval is explicit and follows review.** A draft is not a decision until someone runs `pm-approve` for that stage. Don't approve to "unblock" yourself.
3. **Surface conflicts; don't silently override.** If a new note contradicts an approved upstream artifact, raise it and decide deliberately — re-open the upstream stage if the decision actually changed.
4. **Edit drafts freely before approval.** The Markdown is yours to refine. History is snapshotted under `.history/` before each regeneration, so you can regenerate without fear.

### 4.4 Check state and capture feedback any time
```text
Claude: /pm-status               Codex: $pm-status
Claude: /pm-feedback 03          Codex: $pm-feedback 03
```
- `pm-feedback` prompts for a rating and note interactively; run non-interactively, pass `--rating 1-5` (or `--skip-rating`) and `--note "<text>"` (or `--skip-note`).
- Run `pm-status` before resuming work to see which stages are drafted vs. approved.
- Capture feedback while it's fresh — it's recorded locally in `feedback.jsonl` and feeds future improvement.

### 4.5 Share approved artifacts
```text
Claude: /pm-share                Codex: $pm-share
```
Use this to export the approved chain for stakeholders who don't run PM-OS. Share **approved** artifacts, not raw drafts, so external readers don't mistake a draft for a decision.

---

## 5. Best-fit use cases

- **New product or feature kickoff.** Go from a one-paragraph idea to a brief, scope, and PRD the team can rally around — in hours, not a week of doc-wrangling.
- **Re-scoping an existing product.** Feed the new framing as the business statement and let the pipeline force explicit scope and requirements decisions.
- **Cross-functional alignment.** When design, eng, QA, and data keep working off different mental models, the approved chain becomes the single shared reference.
- **GenAI product definition.** With `genai_flag` set, stages emit GenAI-specific sections and rationale — useful when the product's value depends on model behavior.
- **Onboarding a new PM to a domain.** The staged pipeline is a teaching scaffold: it makes the *shape* of a complete product definition visible.
- **Pre-build technical alignment.** The optional TRD (08) translates the approved product definition into technical requirements without re-litigating product decisions.

---

## 6. Pitfalls & anti-patterns

| Pitfall | Why it hurts | Do this instead |
|---|---|---|
| **Approving to unblock yourself** | Turns the gate into a rubber stamp; downstream builds on an unreviewed decision. | Approve only after the named reviewer has actually read the draft. |
| **Generating downstream from unapproved upstream** | Decisions drift; later stages cite something that was never agreed. | Respect the stage order. If the gate fails, fix the cause, don't bypass it. |
| **Silently overriding an approved upstream artifact** | The "source of truth" quietly forks; readers can't trust the chain. | Surface the conflict; re-open and re-approve the upstream stage if the decision changed. |
| **Treating a draft as a decision** | Stakeholders act on something that wasn't finalized. | Share/cite only approved artifacts; label drafts as drafts. |
| **Putting confidential data in prompts or artifacts** | PHI/PII/secrets end up in local files and possibly in pushed telemetry/feedback. | Sanitize inputs first (§7). If you can't, don't proceed. |
| **Skipping deep-reasoning model on 03/06/08** | The highest-leverage stages get under-reasoned output. | Use Opus (Claude) or a high/deep reasoning model (Codex) for these stages. |
| **Running stage helpers outside the project directory** | Helpers act on the wrong (or no) project state. | Run PM-OS commands from inside the project directory unless the skill says otherwise. |
| **Maintaining a parallel PRD elsewhere** | Two sources of truth diverge; nobody knows which is current. | Pick one home. If PM-OS owns it, link to it from your tracker rather than copying. |
| **Editing `.meta.yaml` by hand** | Corrupts the state machine (status, hashes, approvals). | Let the helper commands manage state; edit Markdown bodies, not the meta file. |
| **Ignoring `pm-status` before resuming** | You regenerate or approve the wrong stage. | Run `pm-status` first to ground yourself in the current state. |

---

## 7. Data handling & safety

- **Sanitize every input.** PM-OS is for sanitized product-planning inputs only. Do not put confidential customer data, PHI, PII, secrets, credentials, or proprietary material into business statements, notes, prompts, or artifacts unless your environment and policies explicitly allow it.
- **Local by default.** Project artifacts, history, telemetry, and feedback are plain files on the user's machine. PM-OS does not send project data to external services unless you explicitly ask for sharing, remote install, or another networked action.
- **Know where feedback goes.** By default PM-OS is configured to push local telemetry and feedback artifacts to a remote feedback repository. If your team needs a private or organization-specific destination, **override this during setup** — before anyone runs real projects. Treat the feedback repo as out-of-bounds for any sensitive content, same as §7's first bullet.
- **When in doubt, abstract.** Describe the customer/segment generically rather than naming an account; describe the data rather than pasting it.

---

## 8. Quick reference

| Action | Claude | Codex |
|---|---|---|
| Install | `./install.sh --runtime claude` | `./install.sh --runtime codex` |
| New project | `/pm-new <slug> "<statement>"` | `$pm-new <slug> "<statement>"` |
| Generate stage *N* | `/pm-stage-0N-...` | `$pm-stage-0N-...` |
| Approve stage *N* | `/pm-approve 0N` | `$pm-approve 0N` |
| Project status | `/pm-status` | `$pm-status` |
| Capture feedback | `/pm-feedback 0N` | `$pm-feedback 0N` |
| Share approved set | `/pm-share` | `$pm-share` |
| Verify install | `/pm-os-verify` | `$pm-os-verify` |

**Pipeline order:** 01 brief → 02 scope → 03 PRD* → 04 design spec → 05 prototype brief → 06 QA plan* → 07 metrics plan → (08 TRD*, optional).
`*` = deep-reasoning stage; run on the strongest available reasoning model and review carefully.

**The one rule to remember:** *generate, review, approve — in order, one stage at a time, on sanitized inputs.*
