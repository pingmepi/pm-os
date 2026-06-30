---
name: pm-context-import
description: Ingest the context a PM already has (research, brief, scope, PRD, design…), build a gated context wiki + understanding doc, then adopt/backfill stage artifacts into the normal pipeline.
reads: ["00-business-statement.md", ".meta.yaml", ".sources.yaml"]
writes: ["00-context-wiki.md", "00-context/manifest.yaml", "00-context/evidence.yaml", "00-context/sources.md", "00-context-understanding.md", "<adopted/backfilled stage artifacts>"]
prompt_version: 0.3.0
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
print("project:", meta["project_slug"])
print("business-statement:", bs["status"])
print("project_type:", meta.get("project_type", "new_product"))
print("codebase_path:", meta.get("codebase_path") or "(none)")
PY
```

If `00` (business statement) is not `approved`, tell the PM to review and approve it first (`/pm-approve 00`) — the wiki depends on it — then stop.

## Codebase pre-flight (enhancement mode only)

If `$ARGUMENTS` includes a `--codebase <url-or-path>` argument, or if `.meta.yaml` has `codebase_path` already set, prepare the codebase before scanning:

```bash
python3 ~/.pm-os/scripts/pm_context_import.py prepare-codebase <url-or-path>
```

This clones (for URLs) or validates (for local paths) the codebase and records the git SHA as `codebase_ref` in `.meta.yaml`. Fail fast if the clone fails — do not continue with a missing codebase. After preparation, the local path is available via `.meta.yaml` `codebase_path`.

# Inputs

Arguments are paths to the PM's source files and/or a folder. Read `$ARGUMENTS`.
- **A folder is walked recursively.** Passing a folder registers every document file in it *and all its subfolders* in one call (see Step 1) — the script reports how many files across how many folders it ingested and lists anything it skipped. You do not need to enumerate subfolders yourself; do confirm the reported coverage matches what the PM expects, and surface the skipped list so nothing is silently dropped.
- **Read each source directly — including `.pdf` and `.docx`.** `.md` / `.txt` are read verbatim. For `.pdf` / `.docx`, read the file with your runtime's native file reading (Claude Code reads PDFs directly and has `pdf` / `docx` skills). If your runtime cannot read a binary format directly, convert it with an available tool (`pandoc`, `pdftotext`, or the `pdf`/`docx` skill); only as a last resort ask the PM to export to Markdown.
- **Flag lossy extraction.** Text-based PDFs and `.docx` extract cleanly. A **scanned/image-only PDF** (no selectable text) or a **table-heavy / multi-column** layout extracts unreliably — order scrambles, tables merge, or OCR is needed. When a source looks like this, emit an `FYI:` calling it out and lean on the review gate: e.g. `FYI: payments-spec.pdf looks scanned/table-heavy — extraction may be imperfect; review the wiki section sourced from it carefully before approving.` Never silently treat a degraded extraction as faithful.
- Optional override: `--as <NN>=<path>` forces a specific file to be adopted as a specific core stage (01–07). Without it, you classify each source yourself.
- **`--upgrade-pack` mode.** If `$ARGUMENTS` contains `--upgrade-pack`, this is the migration flow for an existing single-file wiki, not a fresh import. Do not treat it as a source path. Run the `upgrade-pack` **subcommand** (`python3 ~/.pm-os/scripts/pm_context_import.py upgrade-pack` — note: a subcommand, not a `--upgrade-pack` script flag), then rebuild the pack from the already-registered sources via Steps 3–3c. See the upgrade note under Step 3c.

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

# Step 2b — Parallel subagent scan

Spawn both subagents in parallel. Each reads its own SKILL.md from the install and returns structured markdown output. You do not commit anything in this step — just collect the outputs for synthesis.

**Subagent A — Document scan** (always runs when sources are registered):

Read the doc-scan skill and spawn it as a subagent, providing the project root so it can read `.sources.yaml` and the registered source files:

```bash
cat ~/.pm-os/skills/pm-context-scan-docs/SKILL.md
```

Pass this skill content as the subagent prompt along with: the project root path, and the list of registered sources from `.sources.yaml`. The subagent returns a structured extraction keyed to wiki sections with src_NNN tags and confidence tiers.

**Subagent B — Codebase scan** (only when `codebase_path` is set in `.meta.yaml`):

Read the codebase-scan skill and spawn it as a subagent, providing the codebase path:

```bash
cat ~/.pm-os/skills/pm-context-scan-codebase/SKILL.md
```

Pass this skill content as the subagent prompt along with: the codebase path from `.meta.yaml` `codebase_path`. The subagent returns structured content for the `00-codebase-understanding.md` sections with file-path citations and `<!-- stage-affinity -->` hints.

Wait for both subagents to finish before proceeding to synthesis.

# Step 2c — Write `00-codebase-understanding.md` (only when Subagent B ran)

Using Subagent B's output, write `00-codebase-understanding.md` with a standard frontmatter block (`status: draft`) followed by the subagent's structured output verbatim (TL;DR through Known constraints & tech debt). Then commit:

```bash
python3 ~/.pm-os/scripts/pm_context_import.py commit 00c --kind generated --status draft --model "<the model id you are running as, e.g. claude-opus-4-8>" --prompt-version 0.1.0
```

`FYI: wrote 00-codebase-understanding.md from codebase scan (stage 00c, draft).`

# Step 3 — Build the modular context pack (`00-context-wiki.md` + `00-context/`)

The context wiki is a **modular pack**, not a single page. The engine supports and hashes a pack made of: the **wiki index** (`00-context-wiki.md`), an **evidence ledger** (`00-context/evidence.yaml`), and a **source inventory** (`00-context/sources.md`). (Adaptive per-topic *views* under `00-context/views/` are a later phase — do not generate them yet.) You write these files; the `pack-manifest` command then assembles `00-context/manifest.yaml` and records the pack in `.meta.yaml` (Step 3c). Downstream stages read the index plus the modules whose stage-affinity matches; when no manifest exists they fall back to reading the index whole, so the pack is always safe.

Write `00-context-wiki.md` as the **concise navigational index** — the persistent, skimmable summary a reader (human or model) grasps the project from. Keep the index lean: the exhaustive, per-claim provenance lives in the evidence ledger and source inventory (Step 3a), and the index cross-references them. Do **not** restate every claim in the index.

Synthesize from **Subagent A's structured extraction** (the primary source). Where `00-codebase-understanding.md` exists (Subagent B ran), reference it for the `## Technical constraints` and `## Decisions already made` sections where the codebase reveals constraints the docs don't cover — but do not re-describe the codebase here; cross-reference `00c` instead (e.g. "See 00-codebase-understanding.md § Known constraints & tech debt").

## Index section template (use these `##` headings, in this order)

- `## TL;DR` — the useful takeaway up front: what the product is, the core problem, who it's for, and the decisions already locked. A reader should grasp the project from this section alone.
- `## Problem & context` — the problem space and why-now.
- `## Users & needs` — who they are and their jobs/pains.
- `## Non-goals & explicit exclusions` `<!-- stage-affinity: 01 02 -->` — things explicitly ruled out per the sources; bullets tagged `[hard]` (explicitly stated) or `[inferred]` (derived from context); every item carries a `src_NNN` tag. Omit if no source excludes anything, but note the gap under Open questions.
- `## Success indicators` `<!-- stage-affinity: 01 07 -->` — KPIs, OKRs, and launch criteria from the sources. Mark `⚠️` if no measurable indicators exist in any source.
- `## Decisions already made` `<!-- stage-affinity: 01 02 03 -->` — scope calls, constraints, and commitments the PM has locked, so downstream stages don't relitigate them.
- `## Technical constraints` `<!-- stage-affinity: 03 04 06 08 -->` — hard/soft platform or integration constraints; tag each item `[hard]` or `[soft/preferred]`. Omit only if no source touches constraints, and record the gap under Open questions.
- `## Stakeholder authority` `<!-- stage-affinity: 01 02 03 -->` — decisions attributed to a named authority; format as a table: `Decision | Authority | Source | Binding?`. Treat entries as binding constraints unless a PM annotation overrides. Omit if absent.
- `## Concepts & glossary` — normalized domain terms used across sources.
- `## Open questions & uncertainties` — gaps, conflicts, and thin evidence (this is also where the self-lint findings land — see Step 3b).
- `## Source map` — a brief pointer to the full source inventory: list each `src_NNN` → file → type in one line, and link to `00-context/sources.md` for the detailed inventory (extraction quality, authority, strengths/limitations). The exhaustive table lives in `sources.md`, not here.

Omit a section only if no source touches it at all — and when you do, note the gap under Open questions rather than dropping it silently.

## Style rules

- **Lead with the takeaway**, then support it. Keep the page skimmable.
- **Tag every factual claim** with its `src_NNN` id from `.sources.yaml` so provenance is traceable.
- **Distinguish sourced claims from interpretation.** Anything you synthesized or inferred (not stated in a source) is prefixed `_Interpretation:_` so the PM can tell evidence from inference.
- **Mark uncertainty inline** with `⚠️` when sources conflict or evidence is thin — never resolve a conflict by silently picking one side; surface it under Open questions.
- **Open each content-bearing section** (all except TL;DR, Concepts & glossary, and Source map) with a confidence tier line: `> Confidence: High / Medium / Low — <reason>`. High = PM-authored, current, unconflicted. Medium = secondary source or inferred from strong evidence. Low = model-inferred, lossy, contradicted, or missing decision owner.
- **No filler.** Every line must add navigation, synthesis, or decision value.

## PM annotation override convention

`> **PM:** ...` blockquotes added anywhere in this wiki are highest-priority overrides of the immediately preceding content. They are PM-authored corrections added after the draft is written — do not generate them yourself, and do not remove them when updating the wiki. If a PM annotation conflicts with a sourced claim, the annotation wins; preserve the original claim in `## Open questions & uncertainties` so the PM has a record.

PM annotations are included in the body hash — the PM should be aware that editing them after approval triggers drift detection and cascades staleness downstream.

# Step 3a — Write the evidence ledger and source inventory

These two pack members carry the detail the index points to. Both are part of the composite `00w` hash, so write them before assembling the manifest (Step 3c).

## `00-context/evidence.yaml` — structured evidence ledger

The machine-readable backbone: every load-bearing claim and cross-source insight, with stable IDs, source locators, confidence, the stages it informs, and relationships between claims. Downstream stages consult it when they need traceability or to inspect a conflict. Use stable IDs (`clm-001`, `ins-001`) and **reuse them across regenerations** when the meaning is unchanged; only append new IDs — never renumber.

```yaml
schema_version: 1
claims:
  - id: clm-001
    statement: "<a single sourced factual claim>"
    sources: [src_001]            # src_NNN ids from .sources.yaml
    confidence: high | medium | low
    stage_affinity: ["01", "02"]  # stages this claim informs
    relationships:                # optional; omit if none
      - type: supports | contradicts | updates | depends_on
        target: clm-002
insights:                          # cross-source synthesis (not a raw source claim)
  - id: ins-001
    statement: "<an inference drawn across claims>"
    derived_from: [clm-001, clm-003]
    confidence: medium
    stage_affinity: ["03"]
```

Rules: every `claims[].statement` must cite at least one `src_NNN`; insights cite the claim IDs they derive from (not sources directly). A `contradicts` relationship must also surface under the index's `## Open questions & uncertainties` — never silently reconcile. Keep confidence honest: a claim from a lossy source (scanned/table-heavy) cannot be `high`.

## `00-context/sources.md` — source inventory

The human-readable provenance table the index's `## Source map` points to. One row per `src_NNN`:

```markdown
| Source | File | Type | Modality | Extraction quality | Authority | Strengths | Limitations |
|---|---|---|---|---|---|---|---|
| src_001 | research.pdf | research | text-pdf | Clean | secondary | broad market view | dated 2024 |
```

Extraction quality: Clean / Lossy (scanned/table-heavy) / Unknown. Anything Lossy here must downgrade the confidence of every claim sourced from it in `evidence.yaml`.

# Step 3b — Self-lint the wiki

Before scaffolding the draft, review the wiki for all of the following. Emit each finding as an `FYI:` line (per the "Nothing is silent" rule).

**Content checks (fix before committing):**
- **Contradictions** — claims from different sources that conflict → must surface under `## Open questions & uncertainties`, never silently reconciled. e.g. `FYI: sources src_002 and src_004 disagree on the target segment — flagged under Open questions for your call.`
- **Gaps** — pipeline-relevant areas (problem / users / scope) with no source coverage → note them under `## Open questions & uncertainties`.
- **Unsourced claims** — any factual assertion lacking a `src_NNN` tag, a PM annotation, a Stakeholder authority entry, or `_Interpretation:_` label → source it, mark it as interpretation, or cut it.
- **Confidence mismatch** — any claim extracted from a lossy source (scanned PDF, table-heavy layout) must not be marked High confidence; downgrade to Medium or Low and note the extraction quality.

**Structural warnings (emit FYI, do not block):**
- If sources contain KPIs, OKRs, or measurable targets but `## Success indicators` is empty or all Low confidence → `FYI: sources mention metrics but Success indicators has no high-confidence entries — review before approving.`
- If the highest provided stage is ≥ 04 but `## Technical constraints` is empty → `FYI: no technical constraints found in sources — is this expected for a stage-04+ project?`

**Understanding doc pre-checks (also verified in Step 5):**
- Every inferred claim that drives a downstream stage should appear in the assumption register; flag any obvious gap as `FYI:`.
- Any `⚠️` conflict in the wiki that affects a named stage must appear in the conflict resolution block of the understanding doc; flag preemptively if the conflict is clearly stage-relevant.

Then scaffold the wiki index as a draft stage (write `00-context-wiki.md` with a normal frontmatter block — `status: draft` — plus the index body first):

```bash
python3 ~/.pm-os/scripts/pm_context_import.py commit 00w --kind generated --status draft --model "<the model id you are running as, e.g. claude-opus-4-8>" --prompt-version 0.3.0
```

# Step 3c — Assemble the pack manifest

With the index committed and `00-context/evidence.yaml` + `00-context/sources.md` written, build the manifest. This enumerates the pack members in fixed order, computes their composite hashes, writes `00-context/manifest.yaml`, and records `context_pack` in `.meta.yaml` so downstream stages know the pack exists. Pass a stage-affinity for any member that is stage-specific (the index and ledger apply broadly, so they need none):

```bash
python3 ~/.pm-os/scripts/pm_context_import.py pack-manifest
python3 ~/.pm-os/scripts/pm_context_import.py pack-validate
```

`pack-validate` confirms the manifest is safe and its recorded hashes are current; if it reports stale hashes (you edited a member after building), re-run `pack-manifest`. The composite hash now covers the index + ledger + inventory together, so editing any member after approval is detected as drift and cascades staleness — exactly like a single-file artifact.

`FYI: built the modular context pack — 00-context-wiki.md (index) + 00-context/evidence.yaml + 00-context/sources.md, assembled into 00-context/manifest.yaml.`

> **Existing single-file project?** A PM migrates by running `/pm-context-import --upgrade-pack` (Codex: `$pm-context-import --upgrade-pack`). When you see that flag in `$ARGUMENTS`, run the script's `upgrade-pack` **subcommand** — `python3 ~/.pm-os/scripts/pm_context_import.py upgrade-pack` (the script takes a positional subcommand, not a `--upgrade-pack` option). It snapshots the old single-page `00-context-wiki.md` to `.history/`, scaffolds `00-context/`, and flips `00w` back to draft so you can rebuild it as a pack via Steps 3–3c. The rebuilt `00w`/`00u` remain drafts pending PM approval.

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

Human-facing synthesis the PM approves. Use exactly these six sections:

**1. What I understood**
Prose summary followed by a structured block:
```
**Problem:** <one sentence>
**Primary users:** <one sentence>
**Key locked decisions:** <bullets>
**Non-goals I extracted:** <bullets; flag any inferred as [inferred] for PM confirmation>
```

**2. Source trust table**
| Source | Type | Registered as | Extraction quality | Reliability | Strengths | Weaknesses | Role |
|---|---|---|---|---|---|---|---|

Extraction quality: Clean / Lossy (scanned/table-heavy) / Unknown. Reliability: High / Medium / Low.

**3. Assumption register**
For every stage that will be generated fresh or backfilled lossily, list the specific assumptions the model will use:
| Stage | Section | Assumption I will use | Based on | Confidence | PM review needed? |
|---|---|---|---|---|---|

**4. Conflict resolution block**
Every `⚠️` conflict in the wiki that affects a pipeline stage becomes an explicit block:
```
**Conflict N: <topic>**
- src_NNN says "..."
- src_NNN says "..."
- This affects: <downstream stages and what changes>
- **Your call:** ___________
```
If no conflicts affect any stage: "No conflicts found across sources."

**5. Coverage map**
Per stage 01–07: `✅` provided / `✅` faithful backfill / `⚠️` lossy backfill (PM must approve) / `🔄` generated fresh / `⛔` not adoptable. For `⚠️` stages, name what's likely lost. For `🔄` stages, name the top assumption (link to assumption register row).

**6. What happens on approval**
Exactly which stages will be adopted (`imported`), which backfilled as approved, and which will remain `draft` after seeding (lossy backfills and backfills with unfilled conflicts). Name the draft-remaining stages explicitly so the PM is not surprised.

Then scaffold it as a draft:

```bash
python3 ~/.pm-os/scripts/pm_context_import.py commit 00u --kind generated --status draft --model "<the model id you are running as, e.g. claude-opus-4-8>" --prompt-version 0.2.0
```

# Step 6 — Surface FYIs and hand the gate to the PM

Print the FYI summary (registered sources, adopt vs. context split, any reshaping, the coverage verdicts incl. any ⚠️ lossy or demoted-to-context items, provenance paths).

**Surface the open questions.** Reprint the items from the wiki's `## Open questions & uncertainties` section directly in your response (under "Open questions pending your input:"), so the PM sees every unresolved or conflicting point explicitly and can discuss or resolve it before approving — don't make them open the file to find them. If there are none, say so in one line.

Then stop and tell the PM:

> Review and approve all stage-00 docs before proceeding. Approve in this order:
> - **Enhancement mode only:** `/pm-approve 00c` (codebase understanding — skip if no codebase was scanned)
> - `/pm-approve 00w` (context wiki)
> - `/pm-approve 00u` (context understanding)

Do not continue until all present stage-00 docs are approved — the stage-01 gate blocks until every stage-00 doc in the project metadata is approved.

# Step 7 — On approval, seed the pipeline

After the PM approves the wiki and understanding, adopt and backfill **bottom-up** (lowest stage id first) so each commit's upstream hashes capture already-written upstreams:

For each backfilled gap (ascending), reverse-generate the artifact from the **provided** artifacts + wiki, write the slot (frontmatter `status: draft` + body), then commit using the status that matches the extraction quality. For stages 03–05, load the target stage skill's current required/recommended section contract, write `artifact_contract_version: 1`, and run `pm_validate_artifact.py <NN> --mode strict` before commit; repair required-section errors before continuing.

**Faithful backfill with no unresolved stage-relevant conflicts:**
```bash
python3 ~/.pm-os/scripts/pm_context_import.py commit <NN> --kind backfilled --status approved --derived-from <provided-stage> --model "<the model id you are running as, e.g. claude-opus-4-8>"
```

**Lossy backfill, OR any backfill with an unfilled conflict decision that affects this stage:**
```bash
python3 ~/.pm-os/scripts/pm_context_import.py commit <NN> --kind backfilled --status draft --derived-from <provided-stage> --model "<the model id you are running as, e.g. claude-opus-4-8>"
```
Emit `FYI: <NN>-<name>.md is a lossy/conflicted backfill — committed as draft; PM must /pm-approve <NN> before the pipeline can proceed.`

For each adopted artifact, load the target stage skill and normalize into its current section template while remaining faithful to the PM-authored source. Never invent a missing required or recommended section. Preserve the source coverage, run `pm_validate_artifact.py <NN> --mode warn` for stages 03–05, surface every finding, and continue with approval as requested:

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
