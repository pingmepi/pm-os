---
name: pm-interview
description: Re-run a coverage-driven interview against a project's still-open known unknowns, register the answers, and mark the resolved gaps.
model_tier: standard
---

Standalone re-run of the PM interview against the **known unknowns already recorded** for this project (in `00-context/known-unknowns.md`). Use it after a context import or an earlier interview left gaps open, to close them once the PM has answers — without re-importing anything. This skill only revisits recorded known unknowns; it does **not** re-run feasibility preflight or discover new gaps (that stays in `/pm-context-import`).

Run from inside the project directory.

## Step 1 — Read the open unknowns

```bash
python3 ~/.pm-os/scripts/pm_interview.py list-unknowns --json
```

Each item is `{"question": ..., "source": ...}` for a bullet with **no** `[resolved: ...]` marker. If the list is empty, tell the PM there are no open known unknowns and stop — there is nothing to interview about.

## Step 2 — Conduct the re-run (judgment)

Ask only the still-open gaps. The interview is **coverage-driven, not a fixed count and not a fixed numeric total** — never impose a quota. Present the open unknowns **batched by topic** in **strictly decreasing order of impact** (the highest-impact gap first: problem/why → users & pains → success criteria → scope boundary → non-goals → constraints → decision authority). Keep each round digestible (a soft ~5 questions), and let the PM skip any question or stop early.

Echo each open unknown's **question text verbatim** so the answer can be matched back to it. Never fabricate an answer, and never convert a skipped question into an assumption — a skipped question simply **stays a known unknown**.

## Step 3 — Write the answers file

Capture the round in a Markdown answers file (e.g. `interview-answers.md`), one bullet per question, using the same format the recorder already understands:

```markdown
- [x] ANSWERED: <verbatim question text> :: <the PM's answer>
- [ ] SKIPPED: <verbatim question text>
```

The ` :: ` separates the verbatim question (the match key) from the PM's answer, so an answered gap can be traced back to the exact known unknown it closes.

If the session is non-interactive or `PM_OS_INTERVIEW=skip` is set, do **not** prompt: leave the unknowns as they are (they remain open) and stop after Step 1.

## Step 4 — Register the answers (reused E1 machinery)

Register the answers as a PM-authored, high-confidence interview source in `.sources.yaml`, with provenance — the same recorder the context import uses. Pass `--mode rerun` so this pass is counted **once** (Step 5's `resolve` logs the single rerun event); without it the recorder would also log an *intake* event and the rerun would be double-counted:

```bash
python3 ~/.pm-os/scripts/pm_context_import.py record-interview --interview-answers <answers-file> --mode rerun
```

Registering records the answers as a **source**; it does **not** by itself fold them into the consumable context pack (the wiki/evidence/understanding docs the stages actually read). Step 6 reconciles that.

## Step 5 — Mark the resolved unknowns

Mark every open unknown the answers addressed as resolved **in place** (the bullet is annotated `[resolved: <source> <date>]`, never deleted — the audit trail stays intact), and log the re-run:

```bash
python3 ~/.pm-os/scripts/pm_interview.py resolve <answers-file>
```

Skipped/unanswered unknowns remain open. Report the script's summary as-is.

## Step 6 — Reconcile against the context understanding

Read `00-context-understanding.md` (and, where relevant, `00-context-wiki.md` / `00-context/evidence.yaml`). For **each answer**, check whether it **contradicts** a statement or assumption already recorded there.

- **If an answer contradicts the context understanding:** do not silently absorb it. Surface a clear notice to the PM naming exactly what conflicts — the answered question, the PM's new answer, and the specific claim/assumption in the context understanding it contradicts — and recommend the PM resolve it (regenerate/revise the affected context-pack docs and re-approve, or reconcile the answer). Do **not** edit or re-approve the stage-00 documents here.
- **If no answer contradicts the context understanding:** report that the answers are appended to `.sources.yaml` with **no contradiction found** — and still recommend **regenerating the context packs**, because the wiki/evidence/understanding docs are what downstream stages read (not `.sources.yaml`), so the new answers only reach generation once those are regenerated and re-approved.

## After the re-run

Answering a gap may also mean an upstream **stage** artifact should be regenerated — mention which stage(s) look affected, but **do not** re-run or re-approve them here. This skill informs generation only: **do not self-approve** any stage or stage-00 document; regenerating and re-approving the context pack or any stage stays a deliberate PM action via `/pm-approve`.
