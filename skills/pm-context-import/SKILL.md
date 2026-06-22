---
name: pm-context-import
description: Ingest the context a PM already has (research, brief, scope, PRD, design…), build a gated context wiki + understanding doc, then adopt/backfill stage artifacts into the normal pipeline.
reads: ["00-business-statement.md", ".meta.yaml", ".sources.yaml"]
writes: ["00-context-wiki.md", "00-context-understanding.md", "<adopted/backfilled stage artifacts>"]
prompt_version: 0.2.0
---

# Role and goal

The PM walks in holding context they already produced — market research, a brief, a scope doc, a PRD, design notes, call transcripts — in any mix. Your job is to **adopt that work instead of regenerating it**: parse everything into one knowledge base the model can reuse (the *context wiki*), show the PM what you understood and how it maps onto the pipeline (the *understanding doc*), get explicit approval, then seed the stage pipeline (adopt the artifacts they authored, faithfully backfill the upstream gaps below them) and hand back to the normal flow.

You generate and judge; the `pm_context_import.py` script only moves bytes and updates state. Never hand-edit `.meta.yaml` — always go through the script.

This is the intake path. A greenfield project that starts from just a one-line statement does not use this skill.

# Model guidance

Building the context wiki (`00w`) and understanding doc (`00u`) is **deep-reasoning** work — you synthesize arbitrary, possibly conflicting sources into one normalized, provenance-tagged knowledge base plus a backfill-feasibility map, and you reverse-generate (`backfilled`) upstream artifacts. Use the strongest reasoning model available in the current runtime; if the session is clearly on a lightweight model, say so and recommend switching before building the wiki/understanding or backfilling. This is advisory, not a hard gate.

# Hard rules

- **Nothing is silent.** Every non-obvious action (format conversion/extraction, any lossy or uncertain extraction from a scanned/table-heavy source, reshaping a source into a stage template, adopting an artifact, reverse-generating a missing upstream, where the raw original is preserved) is surfaced as a plain `FYI:` line before approval.
- **The gate is the understanding doc.** Three stage-00 docs must be approved before stage 01 runs: `00-business-statement.md`, `00-context-wiki.md`, `00-context-understanding.md`. You scaffold the wiki and understanding as drafts; the **PM approves them** via `/pm-approve`. Do not self-approve them.
- **Never invent requirements** that aren't in the PM's sources. Reshaping maps their headings onto PM-OS sections; it does not add scope.
- **The gate is never weakened.** Gaps below an adopted artifact are backfilled, not skipped (see Feasibility map). Backfill commits are bottom-up so upstream hashes are honest.

# Pre-flight

```bash
python3 - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / ".pm-os" / "lib"))
from project import resolve_project, load_meta, get_stage
root = resolve_project()
meta = load_meta(root)
bs = get_stage(meta, "00")
print("project:", meta["project_slug"], "| business-statement:", bs["status"])
PY
```

If `00` (business statement) is not `approved`, tell the PM to review and approve it first (`/pm-approve 00`) — the wiki depends on it — then stop.

# Inputs

Arguments are paths to the PM's source files and/or a folder. Read `$ARGUMENTS`.
- **A folder is walked recursively.** Passing a folder registers every document file in it *and all its subfolders* in one call (see Step 1) — the script reports how many files across how many folders it ingested and lists anything it skipped. You do not need to enumerate subfolders yourself; do confirm the reported coverage matches what the PM expects, and surface the skipped list so nothing is silently dropped.
- **Read each source directly — including `.pdf` and `.docx`.** `.md` / `.txt` are read verbatim. For `.pdf` / `.docx`, read the file with your runtime's native file reading (Claude Code reads PDFs directly and has `pdf` / `docx` skills). If your runtime cannot read a binary format directly, convert it with an available tool (`pandoc`, `pdftotext`, or the `pdf`/`docx` skill); only as a last resort ask the PM to export to Markdown.
- **Flag lossy extraction.** Text-based PDFs and `.docx` extract cleanly. A **scanned/image-only PDF** (no selectable text) or a **table-heavy / multi-column** layout extracts unreliably — order scrambles, tables merge, or OCR is needed. When a source looks like this, emit an `FYI:` calling it out and lean on the review gate: e.g. `FYI: payments-spec.pdf looks scanned/table-heavy — extraction may be imperfect; review the wiki section sourced from it carefully before approving.` Never silently treat a degraded extraction as faithful.
- Optional override: `--as <NN>=<path>` forces a specific file to be adopted as a specific core stage (01–07). Without it, you classify each source yourself.

# Step 1 — Register and preserve every source

For each source file (or folder), preserve the raw original(s) and register provenance:

```bash
python3 ~/.pm-os/scripts/pm_context_import.py register "<path>" --type <research|brief|scope|prd|design|context>
```

- If `<path>` is a **file**, it registers that one file.
- If `<path>` is a **folder**, it walks the folder **recursively**, registers every document file (`.md/.txt/.pdf/.docx/.doc/.rtf/.csv/…`) in it and its subfolders, and prints a coverage line (`Registered N file(s) across M folder(s)…`) plus any non-document files it skipped.

Surface both as FYIs so coverage is visible and nothing is dropped silently:
`FYI: registered N sources across M folders from <path> (raw originals preserved under .history/). FYI: skipped K non-document file(s): <list> — tell me if any of these hold context.`

# Step 2 — Classify each source: adopt vs. context

Decide, per source, which it is — and say so:
- **Authored artifact to adopt** — a source that *is* a pipeline artifact the PM signed off on (their actual PRD, scope, design spec). It will become that stage's artifact (`origin: imported`), normalized to the PM-OS section template but faithful to their content. Map it to a core stage 01–07.
- **Context only** — research, notes, transcripts, competitor analysis. It informs the wiki and downstream generation but is not itself a stage artifact.

Record the set of **provided core stages** (the stages you'll adopt). Honor any `--as` overrides.

# Step 3 — Build the context wiki (`00-context-wiki.md`)

Write **one** normalized knowledge base the model will read as grounding for every downstream stage. This is a *persistent, compounding artifact*, not a one-off summary — exhaustive but organized, source-grounded, and skimmable. Keep it a **single page**: do not split it into per-topic files; cross-reference sections by name instead.

## Section template (use these `##` headings, in this order)

- `## TL;DR` — the useful takeaway up front: what the product is, the core problem, who it's for, and the decisions already locked. A reader should grasp the project from this section alone.
- `## Problem & context` — the problem space and why-now.
- `## Users & needs` — who they are and their jobs/pains.
- `## Decisions already made` — scope calls, constraints, and commitments the PM has locked, so downstream stages don't relitigate them.
- `## Concepts & glossary` — normalized domain terms used across sources.
- `## Open questions & uncertainties` — gaps, conflicts, and thin evidence (this is also where the self-lint findings land — see Step 3b).
- `## Source map` — a provenance table: `src_NNN` → file → type → what it contributed.

Omit a section only if no source touches it at all — and when you do, note the gap under Open questions rather than dropping it silently.

## Style rules

- **Lead with the takeaway**, then support it. Keep the page skimmable.
- **Tag every factual claim** with its `src_NNN` id from `.sources.yaml` so provenance is traceable.
- **Distinguish sourced claims from interpretation.** Anything you synthesized or inferred (not stated in a source) is prefixed `_Interpretation:_` so the PM can tell evidence from inference.
- **Mark uncertainty inline** with `⚠️` when sources conflict or evidence is thin — never resolve a conflict by silently picking one side; surface it under Open questions.
- **No filler.** Every line must add navigation, synthesis, or decision value.

# Step 3b — Self-lint the wiki

Before scaffolding the draft, review the wiki you just wrote for:
- **Contradictions** — claims from different sources that conflict → must surface under `## Open questions & uncertainties`, never silently reconciled.
- **Gaps** — pipeline-relevant areas (problem / users / scope) with no source coverage → note them under `## Open questions & uncertainties`.
- **Unsourced claims** — any assertion lacking a `src_NNN` tag and not marked `_Interpretation:_` → either source it, mark it as interpretation, or cut it.

Emit each finding as an `FYI:` line (per the "Nothing is silent" rule), e.g. `FYI: sources src_002 and src_004 disagree on the target segment — flagged under Open questions for your call.`

Then scaffold the wiki as a draft stage:

```bash
python3 ~/.pm-os/scripts/pm_context_import.py commit 00w --kind generated --status draft --model "<the model id you are running as, e.g. claude-opus-4-8>" --prompt-version 0.2.0
```

(The script creates the `00w` stage entry. Write the file with a normal frontmatter block — `status: draft` — plus the body before committing.)

# Step 4 — Run the feasibility preflight

```bash
python3 ~/.pm-os/scripts/pm_context_import.py preflight --provided <comma-separated provided core stages>
```

This prints, for each still-missing upstream stage below the highest provided one, whether it can be reconstructed ✅ faithfully, ⚠️ only lossily, or ⛔ not at all. Use the verdicts to write the coverage section of the understanding doc.

## Feasibility map (why some combos can't be reconstructed)

Information flows downstream and gets more concrete (WHY → WHAT → HOW), so a downstream artifact can only reconstruct an upstream one if it carries that upstream's substance. Only artifacts the PM **provided** count as evidence — a reconstruction is never chained through another reconstructed artifact.

| Gap to backfill | ✅ Faithful if provided | ⚠️ Lossy if best provided is | ⛔ Infeasible if best is |
|---|---|---|---|
| 01 Brief | 02 Scope or 03 PRD | 04 Design | 05 / 06 / 07 only |
| 02 Scope | 03 PRD | 04 Design | 05 / 06 / 07 only |
| 03 PRD | — | 04 Design | 05 / 06 / 07 only |
| 04 Design | — | 05 Prototype brief | 06 / 07 only |
| 05 Prototype brief | — | 06 QA plan | 07 only |
| 06 QA plan | — | — | 07 only |

**If a provided artifact is so deep that the chain below it has an ⛔ gap** (e.g. the PM provided only a metrics plan or only a QA plan), do **not** adopt it as a stage — you cannot honestly reconstruct its upstreams. Demote it to **context** (it still lives in the wiki and grounds generation), and tell the PM. Re-run preflight on the reduced provided set until no ⛔ remains.

# Step 5 — Write the understanding doc (`00-context-understanding.md`)

Human-facing synthesis the PM approves. Include:
- **What I understood** — the problem, users, decisions already made, drawn from the sources.
- **Source classification** — each source: adopted-as-stage-NN vs. context-only.
- **Coverage map** — per stage 01–07: provided / ✅ faithful backfill / ⚠️ lossy backfill (review carefully) / will be generated fresh / ⛔ not adoptable.
- **What happens on approval** — exactly which stages will be adopted (`imported`), which backfilled, which generated later in the normal flow.

Then scaffold it as a draft:

```bash
python3 ~/.pm-os/scripts/pm_context_import.py commit 00u --kind generated --status draft --model "<the model id you are running as, e.g. claude-opus-4-8>" --prompt-version 0.2.0
```

# Step 6 — Surface FYIs and hand the gate to the PM

Print the FYI summary (registered sources, adopt vs. context split, any reshaping, the coverage verdicts incl. any ⚠️ lossy or demoted-to-context items, provenance paths).

**Surface the open questions.** Reprint the items from the wiki's `## Open questions & uncertainties` section directly in your response (under "Open questions pending your input:"), so the PM sees every unresolved or conflicting point explicitly and can discuss or resolve it before approving — don't make them open the file to find them. If there are none, say so in one line.

Then stop and tell the PM:

> Review `00-context-wiki.md` and `00-context-understanding.md`. Approve them to proceed:
> `/pm-approve 00w` then `/pm-approve 00u`.

Do not continue until both are approved (the stage-01 gate enforces this anyway).

# Step 7 — On approval, seed the pipeline

After the PM approves the wiki and understanding, adopt and backfill **bottom-up** (lowest stage id first) so each commit's upstream hashes capture already-written upstreams:

For each backfilled gap (ascending), reverse-generate the artifact from the **provided** artifacts + wiki, write the slot (frontmatter `status: draft` + body), then:

```bash
python3 ~/.pm-os/scripts/pm_context_import.py commit <NN> --kind backfilled --status approved --derived-from <provided-stage> --model "<the model id you are running as, e.g. claude-opus-4-8>"
```

For each adopted artifact, normalize it into the stage's section template, write the slot, then:

```bash
python3 ~/.pm-os/scripts/pm_context_import.py commit <NN> --kind imported --status approved --source-name <orig> --source-format md
```

`FYI:` for each — e.g. `FYI: reverse-generated 01-brief.md and 02-scope.md from your PRD (faithful). FYI: adopted your PRD as 03-prd.md (origin: imported).`

# Step 8 — Report and hand off

Show `/pm-status`. Tell the PM the next pending stage and that it runs through the **normal** flow (`/pm-stage-NN-…`), reading the approved wiki as context.

```bash
python3 ~/.pm-os/scripts/pm_status.py
```

Stages above the highest adopted one are generated normally; nothing about the downstream pipeline, gates, hashing, or staleness changes.
