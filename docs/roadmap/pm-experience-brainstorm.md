# PM-OS — Simplifying Usage for a Less Technical PM

**Date:** 2026-08-20 · **Status:** OPEN EXPLORATION — not a decision, not a committed plan.
**Participants:** Karan (PM, Indegene) + Claude.
**Driver:** Feedback from top management — **usage should be simplified; not every PM is as technically comfortable as the current user.** This is a rollout blocker, not a polish request.
**Fixed constraints (PM's call, not open for exploration):** **No GUI.** Stakeholder-facing workflows are out of scope. Editing is already solved — a PM can edit a section directly or ask the agent to change it, and `/pm-approve --reapprove` absorbs the drift.
**Sibling docs:** `product-shape-and-flexibility-brainstorm.md` (product shape) · `technical-optimisation-brainstorm.md` (technical/knowledge layer).

---

## 0. The through-line (read this first)

> **PM-OS ships with an agent and then tells it to get out of the way.**

The evidence is in the skill files. **Ten of the twenty-six skills carry the instruction:** *"Report the script's output as-is. Do not summarize, restructure, or add commentary beyond a one-line confirmation that the script ran."* Those ten are exactly the PM-facing operational skills — `pm-status`, `pm-approve`, `pm-check`, `pm-feedback`, `pm-handoff`, `pm-new`, `pm-sync`, `pm-os-install`, `pm-os-update`, `pm-os-verify`.

So in precisely the ten places where a less technical PM most needs a translator, the product has one — a capable agent, already in the room — and explicitly forbids it from helping.

Meanwhile, `skills/pm-new/SKILL.md` **already proves the better pattern exists**: it infers `--genai` from the PM's wording, infers the entry route from how they describe the work, and when it can't tell, it asks a plain-language question — *"Is this a GenAI/agentic product? (yes/no)"*. The product already knows how to let the agent stand between the PM and the machinery. It just does it in one skill and not the others.

**This reframes "no GUI" from a constraint into an advantage.** A form can't ask a follow-up, can't infer from how you phrased something, can't explain why a thing is blocked. An agent does all three. The problem was never the absence of a UI — it's that the best interface the product has is muzzled.

And the rule that makes unmuzzling safe, because the "as-is" instruction exists for a good reason:

> **The agent may never *restate* authoritative output. It must always be allowed to *render* it.**

Never paraphrase a status, a hash, an approval, or a gate decision — those must appear verbatim, because a paraphrase that drifts is worse than raw output. But adding a plain-language reading *beside* the verbatim block costs nothing in fidelity and is the entire difference for this audience.

Plus the constraint carried over from every other doc:

> **Simplify the operation. Never simplify the decision.**

---

## 1. The cliff before the product: installation

Most of the target audience will never reach the parts below, because they will not get past step one.

**The agent path is circular.** `install.sh` is what creates `~/.claude/skills` (`install.sh:187-196`). The `/pm-os-install` skill runs `python3 ~/.pm-os/scripts/pm_os_install.py` — a path that does not exist until `install.sh` has already run. **A PM cannot install PM-OS by asking Claude, because the skill that would do it is created by the installation.** Installation is necessarily terminal-first.

**And the naming misleads.** `pm_os_install.py`'s own docstring says *"PM-OS installer. Writes `~/.pm-os/config.yaml`."* It is a **config writer** — reconfiguration, not bootstrap. The skill called "install" cannot install.

**On Windows, which is the rollout platform, the first step is the worst step.** `install.sh` is bash-only, there is no `install.ps1`, and the `python3` resolution problem is live (backlog #2). A non-technical PM opening PowerShell and pasting a bash command gets a parser error with no path forward.

**The `.docx` install guide is the tell.** A Word document, hand-distributed, means someone is currently walking people through this one at a time. That doesn't scale to a rollout, and it is the clearest signal that install is the actual blocker.

**Options, and an honest read:**

- **(a) One artifact the PM double-clicks.** The offline-zip path already exists (`docs/guides/offline-install.md`) — make it a single self-contained thing that requires no shell literacy.
- **(b) Installed once by someone else.** IT-managed, or a colleague, or you. Then everything after is agent-driven and the shell never reappears.
- **(c) A pasteable one-liner** that works in whatever shell the PM has open.

**My read: (b) plus (a).** For this audience the realistic model is *someone installs it once, and the PM never sees a terminal again.* Trying to make a non-technical PM run an install script is solving the wrong problem — and every hour spent on (c) is an hour not spent on §2, which is where the recurring pain actually lives.

---

## 2. Unmuzzle the agent (the single biggest lever)

This is a **prompt-only change across ten files**. No Python, no schema, no state machine, no GUI — and it is the highest value-to-cost item in this document by a wide margin.

**The current instruction and why it exists:** *"Report the script's output as-is. Do not summarize."* This is protecting something real. If the agent paraphrases `stage 03: approved` into something loose, or narrates an approval that didn't happen, the product's core guarantee rots. The rule is correct in what it forbids.

**What it also forbids, accidentally:** any help at all. The rule bans *adding* an explanation just as firmly as it bans *replacing* the output.

**The fix is a distinction, not a deletion:**

| Never | Always allowed |
|---|---|
| Paraphrase or replace authoritative output | Print it verbatim, then explain it |
| Restate a status, hash, approval, or gate decision | Say what that status *means* for the PM |
| Invent, infer, or soften a result | Name the next action, and why |
| Summarize instead of showing | Summarize *in addition to* showing |

Concretely: keep the verbatim block exactly as it is today, then add two short lines under it — *what this means* and *what to do next*. The machine output stays canonical and auditable; the PM gets a reading.

Replace the blanket sentence in all ten skills with the distinction above. That one edit changes the felt experience of every operational command in the product.

---

## 3. Stop requiring machine-shaped input

`pm-new` already demonstrates the pattern and the product should apply it consistently.

**The principle:** *anything the agent can determine from context, or ask about in one plain sentence, should never be a required argument.*

| Today | What the agent could do |
|---|---|
| `/pm-new <slug> "<statement>"` — slug is a **required kebab-case positional** that hard-errors (`pm_new.py:56,73`) | Derive it from the statement and confirm: *"I'll call this `rep-coaching-assist` — fine?"* Same skill already infers two other flags |
| `/pm-approve 01` — the PM must know the stage number | The agent knows which stage is in `draft`. *"Approve the brief?"* |
| `/pm-handoff jira --offline` — modes and flags | *"Create the tickets in Jira, or give you a file to import yourself?"* |
| Every command needs the CWD inside the project (`resolve_project()`) | `projects_dir` is in config. Resolve it, or ask which project |
| Deep-reasoning model warnings mention "model tier" | A PM doesn't know what a tier is. *"This stage does better on the strongest model — you're on a lighter one. Continue anyway?"* |

Note the asymmetry that makes this cheap: **`pm-new` already asks a plain yes/no question when it can't infer `--genai`.** The interaction pattern, the tone, and the precedent all exist. This is extending a proven behaviour, not inventing one.

---

## 4. Speak PM, not state machine

PM-facing output uses implementation vocabulary: `edited`, `stale`, `drift`, `cascade`, `content_hash`, `contract warnings`, `traceability`. A PM who is comfortable with the pipeline reads `stale` correctly. A PM who isn't reads it as *"something is wrong and I don't know what I did."*

Translation is not dumbing down — it is saying what the word already means:

| Shown today | What it means to a PM |
|---|---|
| `stale` / `upstream changed` | *This was written before the PRD changed. It needs redoing.* |
| `edited since approval` | *You changed this after approving it. Approve it again to lock it in.* |
| `⚠ contract warnings: 3` | *Three required sections look thin or missing. Here they are.* |
| `Not inside a PM-OS project.` | *You're not in a project folder. Your projects are: …* |

**Two routes, and the cheap one is better.** Changing the strings means touching status values that tooling depends on. **Letting the agent render them (§2) costs nothing and is reversible** — the machine vocabulary stays in the files where `pm_check`, the gate, and the traceability resolver need it, and the PM gets English.

---

## 5. Don't make the PM hold the pipeline in their head

Thirteen stages, two optional capstones, three entry routes, and a set of modal commands whose applicability depends on how the project started. A technically comfortable PM builds that model after two projects. The target audience should never have to.

The affordance is not "print a next-step line" — that's CLI thinking again. It's that **a PM should be able to ask "what now?" in plain words and get a plain answer with the reason attached**: *"The PRD is drafted and waiting for you. Read it, then tell me to approve it — nothing downstream can run until you do."*

The agent can already compute this from `STAGE_ORDER` and the statuses. Today it's told to report the stage table as-is and add nothing.

---

## 6. The one place a PM's own knowledge must enter is expert-only

The **context overlay** is where a PM's company, team, glossary and house guardrails flow into every generation. It is the single highest-leverage thing a PM can give PM-OS — and it is a hand-edited YAML manifest plus a set of Markdown seed files.

**A non-technical PM will never fill this in.** Which means the audience that most needs generation grounded in their real context is the audience least able to supply it.

**The primitive to reuse already exists.** `/pm-interview` runs a coverage-driven conversation against open gaps and registers the answers as PM-authored context (`pm_context_import.py record-interview`). The same conversational pattern could populate the overlay — the agent asks about the company, the team, the vocabulary, the guardrails, and writes the files.

**Made worse by a live bug:** the seed-drift leak (product-shape brainstorm §5.6 #2) means a PM cannot tell whether their overlay edits took effect, and stale unfilled scaffolding can enter every prompt as though it were real content. For this audience — who can't inspect the files to check — that's not a cosmetic issue.

---

## 7. Recovery for people who can't debug

A technically comfortable PM who lands in a strange state reads `/pm-check`, understands the finding, and fixes it. The target audience cannot.

`/pm-check` returns a list of issues in machine vocabulary and stops. But many of its findings are **mechanically fixable** — a derived index that needs rebuilding, meta/frontmatter that drifted out of sync — as distinct from findings that need a **PM decision**.

The safe shape: **classify findings into "I can fix this" and "this needs you to decide," offer to fix only the first, and never touch the second.** That respects §0's rule exactly — it simplifies operation without touching a single decision.

---

## 8. What must not be simplified — and one real danger

- **The approval decision, the review, and the gate stay exactly as they are.** No auto-approve, no "approve all", no agent answering an approval prompt.
- **No GUI.** Reaffirmed, and it's the right call: a form cannot ask a follow-up, infer from phrasing, or explain a block. The agent is a better interface for this audience than a UI would be — once it's allowed to speak.

**The danger worth stating plainly:** a less technical PM is **more** likely to rubber-stamp. If we simplify the *operation* while the artifact stays a fourteen-section wall with no indication of what to check, "simpler" quietly becomes "approves faster without reading" — which is a worse outcome than the current clunkiness, and it lands squarely on the PM whose name is on the document.

So the operational simplification in §§2–5 has to ship **together with** pointing the PM at what deserves scrutiny. `generation_notes` already exists in frontmatter and `/pm-status` already counts it — the agent is simply told not to surface it. That's the same muzzle, and the same one-line fix.

---

## 9. Ranked

| Change | Cost | Touches the gate? | Effect for a less technical PM |
|---|---:|---|---|
| **Replace the blanket "as-is" rule with restate-vs-render, in 10 skills** | Prompt-only | No — fidelity preserved | **Transforms every operational command** |
| Surface `generation_notes` as "check these" at review | Prompt-only | No | Guards against rubber-stamping |
| Derive the slug in `/pm-new`, confirm it | Tiny | No | Removes the first hard failure |
| Plain-language rendering of `stale` / `edited` / warnings | Prompt-only | No — values unchanged | Removes the "what did I break?" moment |
| "What now?" answered conversationally, with the reason | Prompt-only | No | Pipeline stops being memorised |
| Agent resolves or asks which project | Small | No | Removes the working-directory concept |
| Agent picks up stage numbers and handoff modes | Small | No | Removes flag literacy |
| Install: one double-clickable artifact + install-once-by-someone-else | Medium | No | **Decides whether they arrive at all** |
| Overlay populated by interview, reusing `/pm-interview` | Medium | No | Their context finally gets in |
| `/pm-check` offers to fix mechanically-fixable findings only | Medium | ⚠ design carefully — never decisions | Recovery without debugging |
| Rename `pm_os_install.py` to match what it does | Tiny | No | Stops one misleading signpost |
| Windows shell decision (backlog #2) | Decision-blocked | No | Unblocks the platform |

---

## 10. My read (a recommendation, not a decision)

- **Ship §2 first, on its own.** Ten prompt edits, no code, no risk to the state machine, and it changes every operational command in the product. If only one thing happens from this document, this is it.
- **Pair it immediately with surfacing `generation_notes`** (§8). Simplifying operation without aiming attention makes rubber-stamping more likely, and that failure mode costs more than the friction it removes.
- **Then the input-shape work (§3) and the plain-language rendering (§4)** — both prompt-level, both extending a pattern `pm-new` already proves.
- **Treat install as a distribution problem, not a UX problem.** Decide who installs it. If the answer is "someone technical, once, per PM," most of the Tier-0 work disappears and the terminal never reappears in a PM's life.
- **The overlay-by-interview (§6) is the sleeper.** It is the difference between generic PDLC output and output that sounds like it came from your organisation — and generic output is what makes a PM distrust the tool in the first place.

---

## 11. Open questions

- **Who installs it?** This is the single highest-leverage unknown in the document. "The PM does" and "someone does it for them once" lead to completely different work.
- **What is the actual technical floor?** Does the target PM already use Claude Code for anything else? If not, the barrier isn't PM-OS — it's the runtime, and that changes what "simplify" can even mean.
- **Does the rollout assume training?** A thirty-minute walkthrough removes a lot of what §§3–5 addresses. If training is planned, invest in §2 and §6 instead; if it isn't, §§3–5 matter much more.
- **Is there a floor below which a PM shouldn't use PM-OS at all?** The tool asks someone to take responsibility for approving a PRD. If a PM can't evaluate the artifact, no amount of interface simplification makes their approval meaningful — and that's a staffing question, not a product one.
- **How much plain-language rendering before the PM stops reading the real output?** The verbatim block is the audit trail. If the agent's summary is always easier, the summary becomes the thing they trust — which is exactly what the "as-is" rule was written to prevent.

---

## 12. Grounding references

- `skills/pm-new/SKILL.md` — the proven good pattern: infers `--genai` and `--entry` from the PM's wording, asks a plain-language yes/no when uncertain. Also carries the "as-is" instruction, and still requires a kebab-case slug.
- The ten skills carrying *"Report the script's output as-is. Do not summarize"*: `pm-status`, `pm-approve`, `pm-check`, `pm-feedback`, `pm-handoff`, `pm-new`, `pm-sync`, `pm-os-install`, `pm-os-update`, `pm-os-verify`.
- `install.sh:187-196` — creates `~/.claude/skills`, i.e. the skills the `/pm-os-install` skill would need in order to run. `scripts/pm_os_install.py:1` — docstring: *"Writes `~/.pm-os/config.yaml`"* (a config writer, not a bootstrap).
- `scripts/pm_new.py:56,73` — the required kebab-case slug and its hard error. `lib/project.py` — `resolve_project()` (the working-directory requirement), `STAGE_ORDER` (the input to a conversational "what now?").
- `scripts/pm_status.py` — the raw status vocabulary (`edited since approval`, `upstream changed`), the `generation_notes` count that discards the notes, and the contract-warning count that discards the findings.
- `scripts/pm_interview.py` + `pm_context_import.py record-interview` — the existing conversational-intake primitive §6 would reuse. `lib/context.py`, `context.example/` — the hand-edited overlay it would populate.
- `docs/roadmap/backlog.md` — #2 (Windows/PowerShell, the install blocker), #14 (advisory model gate, in tier vocabulary), #26 (quality metrics measure effort and opinion — the rubber-stamp risk), #46-50 (verified gaps from this pass).
- `docs/roadmap/product-shape-and-flexibility-brainstorm.md` §5.6 — the overlay review and the seed-drift leak that makes §6 worse.
- `docs/guides/pm-os-installation-guide-for-pms.docx` — the hand-distributed Word guide; the clearest signal that install is currently a person-to-person process.
