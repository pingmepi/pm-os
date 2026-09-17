# PM-OS Standard Operating Procedure

**Audience:** Product managers and the cross-functional partners (design, engineering, QA, data) who review or consume PM-OS artifacts.
**Status:** Recommended defaults. Teams may adapt the governance below to project size and risk, but should do so deliberately, not by accident.
**Applies to:** PM-OS v1.5 across both supported runtimes (Claude Code and OpenAI Codex).
**Related guides:** [`enhancement-quickstart.md`](enhancement-quickstart.md) — the enhancement pathway, condensed · [`offline-install.md`](offline-install.md) — locked-down and air-gapped installs · [`testing.md`](testing.md) — what the test suite covers.

---

## Contents

1. [Purpose](#1-purpose)
2. [When to use PM-OS](#2-when-to-use-pm-os)
3. [Roles & responsibilities](#3-roles--responsibilities)
4. [The standard workflow](#4-the-standard-workflow)
5. [Best-fit use cases](#5-best-fit-use-cases)
6. [Pitfalls & anti-patterns](#6-pitfalls--anti-patterns)
7. [Data handling & safety](#7-data-handling--safety)
8. [Quick reference](#8-quick-reference)

---

## 1. Purpose

PM-OS is a PM-led PDLC operating layer. It maintains one coherent thread from idea to ship — intake, product definition, design, dev handoff, QA, release readiness, and feedback — with the PM in control at every decision point.

**v1 scope:** PM-OS currently covers the product-definition phase — a gated pipeline from business statement to a reviewed chain of product artifacts: brief → scope → PRD → design spec → prototype brief → QA plan → metrics plan, with optional technical (TRD) and product roadmap capstones. Each stage is a Markdown file that a human reviews and explicitly approves before the next stage is generated. Approved upstream artifacts are the binding source of truth for everything downstream.

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
- Handing that definition to the people who build it — a per-audience handoff package and Jira tickets (§4.5).
- *(Planned)* QA bug triage, release readiness, feedback ingestion, and the design half of external handoff (Figma pull/push) — coming in later phases.

### What PM-OS is not
- Not a replacement for product judgment. It drafts and recommends; the PM decides.
- Not a system of record for live execution (use Jira/Linear/Asana for that).
- Future Jira/Linear/GitHub integrations should consume and link those systems; they should not make PM-OS the execution tracker.
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

**In v1.5**, a project starts on one of three **entry routes** (`/pm-new <slug> --entry new|prototype|enhancement`), all following the same PM-approval model:

| Entry route | Use it when | What follows |
|---|---|---|
| **`new`** | You're starting from an idea or a business statement. | Straight to stage 01 — or seed it first with material you've already authored (research, brief, scope, PRD, design notes) via `/pm-context-import`, which builds a gated context wiki (`00w`) + understanding doc (`00u`), adopts your artifacts, and backfills the upstream gaps below them. |
| **`prototype`** | You already have an approved prototype or design, but no code yet. | The project stays a new-product project; `/pm-context-import <prototype-or-design-files>` turns the prototype into gated context before stage 01, so it enters as reviewed evidence rather than an unexamined input. |
| **`enhancement`** | You're changing a **live product**, and its codebase is the ground truth. | `--codebase <source>` names the code — a git URL (GitHub/GitLab/any remote), a local directory, or a `.zip` archive. `/pm-context-import --codebase <source>` then prepares it read-only and produces a gated codebase-understanding doc (`00c`) that every downstream stage cites. Continue in the same project for every later change (§4.6, and [`enhancement-quickstart.md`](enhancement-quickstart.md)). |

Later phases will add entry points for Jira/Linear tickets and QA bugs.

### When **not** to use it (or use a lighter touch)
- **Tiny or throwaway work** — a one-line bug fix or a quick spike doesn't need the full stage pipeline. The ceremony will cost more than it returns.
- **Decisions already made and documented elsewhere** — don't regenerate a PRD that already exists and is being executed against; you'll create a competing source of truth. **Adopt** the existing artifact with `/pm-context-import` instead of re-deriving it.
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
| 04 | Design spec *(deep-reasoning)* | PM + design | Design lead |
| 05 | Prototype brief | PM + design | Design lead, eng lead |
| 06 | QA plan *(deep-reasoning)* | PM + QA | QA lead |
| 07 | Metrics plan | PM + data | Data/analytics owner |
| 08 | TRD *(optional, deep-reasoning)* | Eng + PM | Eng lead / architect |
| 09 | Roadmap *(optional, deep-reasoning)* | PM + leadership | PM |

- **Driver** runs the generate command, edits the draft, and requests review.
- **Reviewer** reads the draft and gives the go/no-go. Approval should follow review, not precede it.
- One person can hold multiple hats on a small project — but the *roles* should still be conscious choices, not skipped.

**Deep-reasoning stages (03, 04, 06, 08, 09 — plus the context-build docs 00w/00u and, for enhancement projects, the codebase-understanding doc 00c, all from `/pm-context-import`)** carry the most downstream weight (requirements, design, quality bar, technical commitments, strategy, and synthesized context). They recommend your strongest available reasoning model. This is advisory, not a hard gate: if the runtime can tell it is on a lightweight model, switch before generating; if the model is unknown, proceed with a note and review carefully.

---

## 4. The standard workflow

> Commands are shown for both runtimes. Claude uses `/slash` commands; Codex uses `$skill` invocations or the `/skills` picker.

### 4.1 One-time setup (per machine)

**Prerequisites:**
- Network access to fetch the base tools below — on a locked-down corporate machine, local admin rights are not sufficient by themselves; the network/proxy team must also allow-list the relevant domains. Request this *before* the install day, since network changes usually go through a ticket queue. See `docs/guides/offline-install.md` §0 for the specific domains to request per tool.
- Python 3.11+
- `git` — required for `/pm-sync` (telemetry push) and for GitHub/GitLab install paths; not needed for the offline zip install path
- `pyyaml` and `jinja2` — auto-installed by `install.sh` if pip/PyPI is available; if pip is blocked, see `docs/guides/offline-install.md` for the `--with-wheels` zip option

```bash
# Claude
./install.sh --runtime claude --pm-user <id>

# Codex
./install.sh --runtime codex --pm-user <id>

# Optional: choose a non-default project directory
./install.sh --runtime codex --pm-user <id> --projects-dir ~/pm-projects
```
The `--runtime` argument is required so skills install into the correct agent directory. For team installs, prefer explicit config flags over accepting prompts:
- `--pm-user` becomes the teammate identity stored in `~/.pm-os/config.yaml` and used in feedback paths such as `telemetry/<pm_user>/<project-slug>/`.
- Each teammate should use a unique, stable PM identifier.
- `--feedback-repo` is optional. If configured, it should point to the team's approved feedback repository, not a personal placeholder; if omitted, `/pm-sync` skips remote telemetry sync.
- `--projects-dir` is optional, but should be standardized if the team wants consistent local paths.

Run the verifier after setup:
```bash
python3 ~/.pm-os/scripts/pm_os_verify.py --runtime claude
python3 ~/.pm-os/scripts/pm_os_verify.py --runtime codex
```
Or from inside an agent session: `/pm-os-verify` (Claude) / `$pm-os-verify` (Codex).

**Keeping an install current.** Updates go through one route only:
```text
Claude: /pm-os-update            Codex: $pm-os-update
```
It fast-forwards the install to the released version and re-syncs skills (and, for Claude, hooks) into the runtime's directories. Re-run `/pm-os-verify` afterwards. Never hand-edit the installed `~/.pm-os` or the runtime skill directories — a manual change diverges the install and blocks every future update. (`/pm-os-install` covers a first-time or reconfigured install from inside a session.)

### 4.2 Start a project
```text
Claude: /pm-new <project-slug> ["<business statement>"] --genai|--no-genai [--entry new|prototype|enhancement] [--codebase <source>]
Codex:  $pm-new <project-slug> ["<business statement>"] --genai|--no-genai [--entry new|prototype|enhancement] [--codebase <source>]
```
- Keep the slug short and stable; it's used in paths and history.
- Write the business statement in plain language. **Sanitize it first** (§7). The statement is optional — omit it to add it later (a placeholder is written into `00`).
- Pass `--genai` or `--no-genai` to set whether this is a GenAI/agentic product. In an interactive shell `pm-new` prompts; run non-interactively (the usual case inside an agent) you must pass the flag (or set `PM_OS_GENAI_FLAG`).
- **Pick the entry route** (§2). If you omit `--entry`, the skill infers it from how you described the work and defaults to `new`; state it explicitly when it matters.
- For an **approved prototype or design with no code behind it yet**, pass `--entry prototype`. The project stays a new-product project (`project_type: new_product`) and records the route; import the prototype and any supporting material with `/pm-context-import <prototype-or-design-files>` so it becomes gated context (`00w`/`00u`) rather than an unreviewed input.
- For a **live product not yet represented in PM-OS**, pass `--entry enhancement --codebase <source>` — a git URL (GitHub/GitLab), a local directory, or a `.zip` archive of the code. `/pm-new` only *records* the source in `.meta.yaml`; the next step, `/pm-context-import --codebase <source>`, is what clones a remote or extracts a zip into the project's own read-only `.codebase/` copy and builds the gated `00c` evidence. Your original repository is never modified. For every later enhancement, work inside this same project with `/pm-enhance` (§4.6); do not create another project.
- **Enhancement projects gate every product stage on a recorded affected slice** — stages 01–09 will not generate until the cycle is started and the boundary recorded. See §4.6; the gate does not apply to `new` or `prototype` projects.
- The project is created under the `projects_dir` from your config (default `~/pm-projects`).
- This seeds `00-business-statement.md` and `.meta.yaml`, including the `genai_flag` that controls whether stages emit GenAI-specific sections, and (for enhancements) `project_type`/`codebase_path`. The business statement is a gated stage (`00`): review and approve it before generating stage 01.

### 4.3 Generate → review → approve, one stage at a time
First approve the business statement, then proceed through the stages in order:
```text
Claude: /pm-approve 00            Codex: $pm-approve 00
   (the business statement is stage 00 — review, then approve)
Claude: /pm-stage-01-brief        Codex: $pm-stage-01-brief
   (read the draft, edit if needed, have the reviewer look)
Claude: /pm-approve 01            Codex: $pm-approve 01
```
Then 02, 03, … 07. (If you seeded the project with `/pm-context-import`, you also approve the context wiki `00w` and understanding doc `00u` before stage 01 — plus the codebase-understanding doc `00c` for enhancement projects.) Optional capstones come after 01-07 are approved: TRD (08) for technical requirements, and Roadmap (09) for the path from MVP to deliverable product. If TRD is approved before Roadmap, stage 09 uses it as technical delivery context.

**The core discipline (recommended default — relax only with eyes open):**
1. **Never generate a downstream stage from an unapproved upstream stage.** The gate exists to stop drift. If a pre-stage gate exits non-zero, stop and read the error; do not write the artifact anyway.
2. **Approval is explicit and follows review.** A draft is not a decision until someone runs `pm-approve` for that stage. Don't approve to "unblock" yourself.
3. **Surface conflicts; don't silently override.** If a new note contradicts an approved upstream artifact, raise it and decide deliberately — re-open the upstream stage if the decision actually changed.
4. **Edit drafts freely before approval.** The Markdown is yours to refine. Generated drafts are snapshotted under `.history/` by `pm_snapshot.py`, so you can regenerate without fear.
5. **Read the validation findings before you approve.** You don't run the validator yourself — PM-OS runs it for you. Generating stages 03, 04, 05, 06, 08 (and the HTML prototype) runs the artifact contract in **strict** mode, so a missing required section is caught and repaired before you ever see the draft. Approval re-runs it in **warning** mode: findings are printed, recorded as `artifact_validation_warning` telemetry, and surfaced by `/pm-status` as `⚠ contract warnings: N` on the stage. Warnings do not block approval — that is precisely the point at which *you* decide — so read each one with the same attention as a reviewer comment. For a whole-project consistency check at any time, run `/pm-check` (§4.4).

### 4.4 Check state and capture feedback any time
```text
Claude: /pm-status               Codex: $pm-status
Claude: /pm-check                Codex: $pm-check
Claude: /pm-feedback 03          Codex: $pm-feedback 03
Claude: /pm-sync                 Codex: $pm-sync
Claude: /pm-interview            Codex: $pm-interview
```

**Consistency check (`/pm-check`).** Read-only, safe to run any time, and the fastest way to answer *"is this project actually coherent?"* It checks that `.meta.yaml` and each artifact's frontmatter agree, that no approved artifact has been edited since approval (hash drift), that upstream approvals are shaped correctly, that the telemetry hash chain is intact, that expected artifacts exist, and that TRD `TSK-###` task ids are unique, sequential, and trace to real PRD requirements. In an **enhancement** project it adds the cycle invariants: baseline integrity, repository drift, changes made outside the recorded boundary, and missing surface / regression / implementation / migration traces. It never changes anything — it prints the remediation command for each finding (for example `/pm-approve 04`), and you decide. Run it before a handoff and before closing an enhancement cycle.

**Known unknowns.** When you seed a project via `/pm-context-import`, any interview question you skip is recorded in `00-context/known-unknowns.md` as an open gap — never a silent assumption. `/pm-status` shows the count (`Known unknowns: N open`). Run `/pm-interview` any time to re-run the interview against just those still-open gaps: answers are registered as PM-authored context and the resolved gaps are marked in place (never deleted), so the audit trail stays intact.
- `pm-feedback` prompts for a rating and note interactively; run non-interactively, pass `--rating 1-5` (or `--skip-rating`) and `--note "<text>"` (or `--skip-note`).
- Run `pm-status` before resuming work to see which stages are drafted vs. approved.
- Capture feedback while it's fresh — it's recorded locally in `feedback.jsonl` and feeds future improvement.
- `pm-sync` pushes all projects' telemetry and feedback to the team repo. Each approval triggers this automatically **in the background** (so approval never waits on the network push); run `pm-sync` manually to verify or retry a backgrounded sync, backfill a machine that was offline, or pass `--verify` to validate every project's hash chain.

### 4.5 Share approved artifacts

`/pm-handoff` is the single export skill — raw text, a readable per-audience
package, or Jira tickets.

```text
Claude: /pm-handoff --raw                Codex: $pm-handoff --raw
```
Use this to export the approved chain for stakeholders who don't run PM-OS. Share **approved** artifacts, not raw drafts, so external readers don't mistake a draft for a decision. By default this is a raw text dump of one stage (`/pm-handoff --raw 03`) or every approved stage; write it to a file with `--output <file>`.

**Readable handoff package (`--package`).**
```text
Claude: /pm-handoff --package      Codex: $pm-handoff --package
```
Instead of one dense text dump, this assembles a decomposed, human-readable package under `handoff/{dev,design,qa,business}/` — one audience folder per consumer. Each folder gets whatever's relevant to it: dev/qa get separate epic, story, and requirement files; every story is self-contained and embeds the text of referenced `FR-###`/`REQ-###` requirements, `AC-###` acceptance criteria, impact analysis, and NFRs instead of relying on hyperlinks for implementation-critical context. Story files also walk the traceability spine through journeys, covering test cases, serving `SCR-###` screens, exact Figma screen/state links when available, and implementing `TSK-###` backend tasks when the optional TRD is approved. Business gets the overview and epic index. Design/QA get `reference/screen-map.md` (the screen → stories reverse view) and the prototype; *(rolling out — external design authority, not yet on the released `main`:)* when stage 04 is a draft design brief (`design_mode: brief`), the design audience also gets `reference/design-brief.md` and `DESIGNER-WORKFLOW.md` so external designers can return structured `design-in/` evidence before PM-OS ingests the canonical design spec with `pm_design_ingest.py` / stage-04 `--ingest`. Add `--audience dev|design|qa|business` to rebuild just one folder (others are left untouched), `--html` for a cross-linked `index.html` per folder, or `--output <dir>` to write elsewhere. It requires an **approved** PRD (stage 03) and is a read-only projection — never edit files under `handoff/`; they're regenerated wholesale, so edit the canonical stage artifact and re-run. Re-run it after any PRD/QA/design re-approval to refresh the package.

**Export to Jira (`/pm-handoff`).**
```text
Claude: /pm-handoff jira         Codex: $pm-handoff jira
```
Turns the approved pipeline into tracker tickets keyed to PM-OS's stable ids using Jira's default hierarchy: each declared `EPIC-###` becomes a Jira Epic, each `US-###` becomes a Story under its declared epic, each `FR-###`/`REQ-###` becomes a Task under its declared epic, and each approved TRD `TSK-###` becomes a Subtask when it implements exactly one exported Story/Task. Same-epic multi-ref `TSK-###` items become Tasks under that epic; cross-epic or unresolved tasks stay unparented for review. It requires an **approved** PRD and always runs **(refresh local package) → dry-run → you confirm → create → record** — the same `/pm-handoff` also refreshes `handoff/{dev,design,qa,business}/` first, skippable with `--no-package-refresh`. Nothing is created in Jira without an explicit yes, and only ticket keys come back into `.traceability.yaml`.

Two routes:
- **Connector** (default) — creates the tickets directly through the Atlassian MCP. Needs that connector authorized for your session; PM-OS never handles tokens.
- **Offline** (`/pm-handoff jira --offline`) — writes `handoff/jira-import.csv` plus an import guide, which you upload through Jira's own CSV importer with your normal Jira login. No connector, no API token. Afterwards, recover the created keys from Jira (search the `pm-os` label) and record them with `pm_handoff.py record` so both routes end in the same state.

Re-running creates *new* tickets — it does not detect ones you already created. Check `.traceability.yaml` for recorded tickets before a second run.

**In an active enhancement cycle, the handoff is delta-only.** Both `--package` and the Jira export scope themselves automatically to the computed delta (§4.6): the changed epics, stories, requirements, test cases, and tasks, plus the minimum parent closure needed to keep the hierarchy intact, plus explicit tickets for anything you removed — each carrying its affected surfaces, regression invariants, compatibility/migration notes, and rollout/rollback context. Dev and QA read only what actually changed, not a re-dump of the whole product.

### 4.6 Enhancing a product that's already in PM-OS

**One product = one PM-OS project.** Every later change to that product is an **enhancement cycle** inside the same project — never a new project, never a child project, never a parallel approval state machine.

```text
Claude: /pm-enhance              Codex: $pm-enhance
```
The skill drives the cycle for you. The underlying steps are worth knowing, because `/pm-status` and `/pm-check` report against them:

| Step | What it does |
|---|---|
| `start` | Freezes the currently approved artifacts plus the pinned code evidence into an immutable cycle baseline. Refuses a second active cycle. It consumes an **already-prepared** local codebase — it never clones or extracts; that's `/pm-context-import`'s job (§4.2). |
| `set-boundary` | Records the affected slice from the decision interview: current → target behavior, affected surfaces (UI / API / data / service / event / integration / ops), explicit non-touch areas, regression invariants, compatibility and migration, rollout/rollback, and decision authority. |
| `show` | Prints the active cycle and the boundary it recorded. |
| `delta` | Computes the frozen-baseline-vs-current change set that scopes `/pm-check` and the handoff. |
| `refresh` | Re-pins the code evidence after the target repository moves, and stales the affected pipeline. Always explicit, never silent. |
| `complete` | Closes the cycle; the canonical artifacts become the next cycle's baseline. |

**The boundary is a hard gate.** Product stages 01–09 will not generate until `start` and `set-boundary` have run — and `set-boundary` requires `00c`/`00u` to be approved first. If you try a stage before that, PM-OS stops and tells you to record the affected slice. This is deliberate: the delta, the checks, and the handoff all need something to scope against. The interview questions are **skippable** — answer what you know; anything you skip is logged as a known unknown (§4.4) rather than assumed. An unresolved baseline, boundary, invariant, or required migration blocks downstream generation unless you record an explicit accepted risk.

Each stage then covers the **enhancement only** — the current-product gap and the delta — updating the affected blocks and carrying unaffected content forward untouched, rather than rewriting the whole product definition.

**The target codebase is read-only throughout.** PM-OS reads files and does read-only Git inspection. It never edits, commits, switches refs, installs dependencies, builds, or writes documentation into your repository — every artifact it produces lives inside the PM-OS project.

---

## 5. Best-fit use cases

- **New product or feature kickoff.** Go from a one-paragraph idea to a brief, scope, and PRD the team can rally around — in hours, not a week of doc-wrangling.
- **Re-scoping an existing product.** Feed the new framing as the business statement and let the pipeline force explicit scope and requirements decisions.
- **Cross-functional alignment.** When design, eng, QA, and data keep working off different mental models, the approved chain becomes the single shared reference.
- **GenAI product definition.** With `genai_flag` set, stages emit GenAI-specific sections and rationale — useful when the product's value depends on model behavior.
- **Regulated or data-sensitive products.** The PRD carries a required **Data & Governance** section (data, sensitivity, retention, access, compliance regime); the TRD's **Data Governance & Compliance Implementation** specifies the enforcing controls, and the QA plan verifies them — so PHI/PII handling and audit/retention obligations are defined before build, not after.
- **Onboarding a new PM to a domain.** The staged pipeline is a teaching scaffold: it makes the *shape* of a complete product definition visible.
- **Pre-build technical alignment.** The optional TRD (08) translates the approved product definition into technical requirements without re-litigating product decisions.
- **Post-MVP product planning.** The optional Roadmap (09) scopes the path from MVP to a deliverable product and later horizons, using the TRD as technical context when it exists.
- **Enhancement/brownfield work.** When you're extending an existing product, `--entry enhancement --codebase <source>` (git URL, local directory, or `.zip` archive) grounds the entire pipeline in what already exists — the codebase-understanding doc (`00c`) is produced before stage 01 and cited by every downstream stage, so requirements don't re-invent what the system already does. The affected-slice boundary you record with `/pm-enhance set-boundary` then keeps the delta, `/pm-check`, and `/pm-handoff` scoped to what actually changes — handoff exports the changed slice plus the minimum parent closure and explicit removal work, not the whole product.
- **Research-driven prototype validation.** Stage 05 produces an interactive HTML prototype (`pm-prototype-html`) tuned to the approved information architecture and interaction model. Participant mode is clean by default; reviewer controls and research questions appear via `?review=1`, so the same file serves both user research and PM review without contaminating participant sessions.

---

## 6. Pitfalls & anti-patterns

| Pitfall | Why it hurts | Do this instead |
|---|---|---|
| **Approving to unblock yourself** | Turns the gate into a rubber stamp; downstream builds on an unreviewed decision. | Approve only after the named reviewer has actually read the draft. |
| **Generating downstream from unapproved upstream** | Decisions drift; later stages cite something that was never agreed. | Respect the stage order. If the gate fails, fix the cause, don't bypass it. |
| **Silently overriding an approved upstream artifact** | The "source of truth" quietly forks; readers can't trust the chain. | Surface the conflict; re-open and re-approve the upstream stage if the decision changed. |
| **Treating a draft as a decision** | Stakeholders act on something that wasn't finalized. | Share/cite only approved artifacts; label drafts as drafts. |
| **Putting confidential data in prompts or artifacts** | PHI/PII/secrets end up in local files and possibly in pushed telemetry/feedback. | Sanitize inputs first (§7). If you can't, don't proceed. |
| **Using a lightweight model on the deep-reasoning stages (03/04/06/08/09, context build)** | The highest-leverage stages get under-reasoned output. | Prefer the strongest available reasoning model; if the model is unknown, proceed with a note and careful review. |
| **Running stage helpers outside the project directory** | Helpers act on the wrong (or no) project state. | Run PM-OS commands from inside the project directory unless the skill says otherwise. |
| **Maintaining a parallel PRD elsewhere** | Two sources of truth diverge; nobody knows which is current. | Pick one home. If PM-OS owns it, link to it from your tracker rather than copying; once import exists, ingest the external artifact instead. |
| **Editing `.meta.yaml` by hand** | Corrupts the state machine (status, hashes, approvals). | Let the helper commands manage state; edit Markdown bodies, not the meta file. |
| **Ignoring `pm-status` before resuming** | You regenerate or approve the wrong stage. | Run `pm-status` first to ground yourself in the current state. |
| **Dismissing artifact contract warnings** | Warnings flag user-journey gaps, unlabeled requirements, or interaction-model conflicts that propagate into the QA plan, the prototype, and the handoff. | Read the findings printed at generation and at approval, and run `/pm-check` before you approve — with the same rigor as a reviewer comment. `artifact_validation_warning` events are recorded in telemetry for later audit. |
| **Ignoring `/pm-check` before a handoff** | You export a package or Jira tickets built on drifted, unapproved, or untraceable state. | Run `/pm-check` first; it's read-only and prints the remediation command for every finding. |
| **Starting a second project for the next enhancement** | Baseline lineage breaks, the delta has nothing to compare against, and the product's history forks. | One product = one project. Continue with `/pm-enhance` in the existing project (§4.6). |
| **Hand-editing the installed `~/.pm-os` or the runtime skill directories** | Diverges the install and blocks every future update for you and everyone who follows the same route. | Change nothing there by hand; use `/pm-os-update`. |

---

## 7. Data handling & safety

- **Sanitize every input.** PM-OS is for sanitized product-planning inputs only. Do not put confidential customer data, PHI, PII, secrets, credentials, or proprietary material into business statements, notes, prompts, or artifacts unless your environment and policies explicitly allow it.
- **Local by default.** Project artifacts, history, telemetry, and feedback are plain files on the user's machine. PM-OS does not send project data to external services unless you explicitly ask for sharing, remote install, or another networked action.
- **Know where feedback goes.** PM-OS stores telemetry and feedback locally by default. If you configure `--feedback-repo`, `/pm-sync` pushes those local JSONL artifacts to that repository; otherwise sync is skipped. Treat any configured feedback repo as out-of-bounds for sensitive content, same as §7's first bullet.
- **When in doubt, abstract.** Describe the customer/segment generically rather than naming an account; describe the data rather than pasting it.

---

## 8. Quick reference

| Action | Claude | Codex |
|---|---|---|
| Install | `./install.sh --runtime claude --pm-user <id>` | `./install.sh --runtime codex --pm-user <id>` |
| New project | `/pm-new <slug> "<statement>"` | `$pm-new <slug> "<statement>"` |
| Start from an approved prototype | `/pm-new <slug> --entry prototype` | `$pm-new <slug> --entry prototype` |
| First intake of external product | `/pm-new <slug> --entry enhancement --codebase <source>` | `$pm-new <slug> --entry enhancement --codebase <source>` |
| Later enhancement in same project | `/pm-enhance` | `$pm-enhance` |
| Enhancement cycle steps | `/pm-enhance` → `start` / `set-boundary` / `show` / `delta` / `refresh` / `complete` | same |
| Import context | `/pm-context-import <files-or-folder>` | `$pm-context-import <files-or-folder>` |
| Scan a codebase (standalone) | `/pm-context-scan-codebase` | `$pm-context-scan-codebase` |
| Scan documents (standalone) | `/pm-context-scan-docs` | `$pm-context-scan-docs` |
| Generate stage *N* | `/pm-stage-0N-...` | `$pm-stage-0N-...` |
| Consistency check (read-only) | `/pm-check` | `$pm-check` |
| Approve stage *N* | `/pm-approve 0N` | `$pm-approve 0N` |
| Project status | `/pm-status` | `$pm-status` |
| Re-run interview (open gaps) | `/pm-interview` | `$pm-interview` |
| Capture feedback | `/pm-feedback 0N` | `$pm-feedback 0N` |
| Sync telemetry/feedback | `/pm-sync` | `$pm-sync` |
| Regenerate HTML prototype | `/pm-prototype-html` | `$pm-prototype-html` |
| Share approved set (raw text) | `/pm-handoff --raw` | `$pm-handoff --raw` |
| Handoff package (per-audience files) | `/pm-handoff --package` | `$pm-handoff --package` |
| Handoff to Jira | `/pm-handoff jira` | `$pm-handoff jira` |
| Verify install | `/pm-os-verify` | `$pm-os-verify` |
| Update install | `/pm-os-update` | `$pm-os-update` |

**Pipeline order:** (00 business statement) → [00w context wiki* + 00u understanding doc* + 00c codebase understanding*, if using `/pm-context-import`] → 01 brief → 02 scope → 03 PRD* → 04 design spec* → 05 prototype brief → 06 QA plan* → 07 metrics plan → (08 TRD*, optional) → (09 Roadmap*, optional; uses approved TRD when available).
`*` = deep-reasoning stage; prefer the strongest available reasoning model and review carefully. Stage generation and approval validate the artifact contract automatically (stages 03, 04, 05, 06, 08 and the HTML prototype) — read the findings, and run `/pm-check` for whole-project consistency before approving or handing off.

**The one rule to remember:** *generate, review, approve — in order, one stage at a time, on sanitized inputs.*
