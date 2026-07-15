# Enhancement Mode + Context Intake Improvements — Final Work Scope

> Status: ✅ **Implemented** (shipped in v0.5.8 / v0.5.9). All changes in this plan landed: four new wiki sections (non-goals, success indicators, technical constraints, stakeholder authority), confidence tiers, stage-affinity hints, understanding doc trust table / assumption register / conflict-resolution block, PM annotation convention, 5-rule wiki consumption block across all 9 stage skills, and the `00c` codebase-understanding stage. Moved to `docs/archive/` 2026-07-15 (nothing left actionable) — retained for provenance.

## What this builds

Two things in one pass:

1. **Enhancement mode infrastructure** — `--mode enhancement` flag on `pm-new`, `--codebase` support (GitHub URL or local path), new `00c` codebase understanding doc (conditional pre-stage — only created and gated when a codebase is scanned; absent projects are unaffected), schema v3.
2. **Context intake quality improvements** — richer wiki (4 new sections, confidence tiers, stage-affinity hints), richer understanding doc (trust table, assumption register, conflict resolution block), PM annotation convention, 4-rule wiki consumption block across all 9 stage skills.

**Architectural principle:** Deterministic ops (clone, validate, SHA capture, commit) live in Python. Judgment (what to scan, how to synthesize) lives in SKILL.md as agentic steps.

---

## End-to-end PM flow

```
# Enhancement: codebase + statement at creation time
/pm-new my-feature "Add chatbot to the portal" --mode enhancement --codebase https://github.com/org/portal
/pm-context-import                   ← parallel subagents: doc scan + codebase scan
/pm-approve 00c / 00w / 00u / 00     ← all present pre-stages
/pm-stage-01-brief                   ← reads all; enhancement framing natural

# Enhancement: statement written via chat after pm-new (not as command-line arg)
/pm-new my-feature --mode enhancement --codebase /path/to/portal
  → system prompts "What do you want to build?" → PM answers in chat
  → Claude writes 00-business-statement.md
/pm-approve 00                       ← must happen before context-import (gate requires it)
/pm-context-import
/pm-approve 00c / 00w / 00u
/pm-stage-01-brief

# Forgot --mode flag
/pm-new my-feature "Add chatbot..."
  → PM tells Claude in chat → Claude edits project_type in .meta.yaml directly
```

---

## File change matrix

| File | What changes |
|---|---|
| `lib/project.py` | 00c stage, schema v3, migrate_meta v2→v3 |
| `scripts/pm_new.py` | --mode, --codebase, optional business statement |
| `scripts/pm_status.py` | mode display, codebase drift signal |
| `scripts/pm_context_import.py` | prepare_codebase (clone/validate/SHA) |
| `skills/pm-context-import/SKILL.md` | codebase subagent, richer wiki + understanding templates, PM annotations |
| `skills/pm-stage-01-brief/SKILL.md` | 4-rule wiki block + enhancement framing (reads 00c stage-affinity hints if present) |
| `skills/pm-stage-{02..09}-*/SKILL.md` (8 files) | 4-rule wiki consumption block only |

**13 files total.**

---

## Python changes

### `lib/project.py`
- Add to `STAGE_NAMES`: `"00c": "codebase-understanding"`
- Add to `STAGE_ARTIFACTS`: `"00c": "00-codebase-understanding.md"`
- Update `PRE_STAGES` to `["00", "00c", "00w", "00u"]`; update `STAGE_ORDER` accordingly (00c before 00w — wiki references it)
- Bump `SCHEMA_VERSION` to `3`
- Add v3 migration block in `migrate_meta()`:
  ```python
  if meta.get("schema_version", 1) < 3:
      meta.setdefault("project_type", "new_product")
      meta.setdefault("codebase_path", None)
      meta.setdefault("codebase_ref", None)
      changed = True
  ```
  Root-level fields, idempotent. Existing projects default to `new_product`.

### `scripts/pm_new.py`
- Add `--mode {new_product,enhancement}` (default `new_product`; env-var `PM_OS_PROJECT_TYPE`)
- Add `--codebase <url-or-path>` (optional, enhancement-only; if given with `new_product` → error + exit)
- Store `project_type`, `codebase_path` (as-given, not cloned here), `codebase_ref: null`, `schema_version: 3` in meta
- Business statement positional arg is now **optional**: if omitted on non-tty → scaffold with empty placeholder; if omitted on tty → prompt "What do you want to build? (Enter to add later):" — write if answered, leave placeholder if skipped
- Add `project_type` to `project_created` telemetry payload
- Update final print to show mode and next step

### `scripts/pm_status.py`
- Show `Mode: enhancement  Codebase: <path>` line when `project_type=enhancement`
- Drift check (only when `codebase_path` is a local dir and `codebase_ref` is set):
  `git -C <codebase_path> rev-parse HEAD` → if SHA ≠ `codebase_ref`: `⚠ codebase drift — re-run /pm-context-import`; skip silently on any failure

### `scripts/pm_context_import.py`
Add `prepare-codebase <url-or-path>` subcommand (called by SKILL.md before the scan):
```python
def prepare_codebase(raw: str, project_root: Path) -> Path:
    # URL (https://, git@, http://): git clone --depth 1 <url> <project_root>/.codebase/
    # Local path: Path(raw).resolve(), validate is directory
    # Capture: git -C <local_path> rev-parse HEAD → write codebase_ref to .meta.yaml
    # Returns: resolved local path
```
- Add `.codebase/` to project `.gitignore` (Python writes this on first use)
- `commit` command already handles any stage ID; no additional logic needed for `00c`

---

## `skills/pm-context-import/SKILL.md` changes

### New pre-flight step
If `--codebase` arg present, call `pm_context_import.py prepare-codebase <url-or-path>` first. Python clones/validates and returns the local path. Fail fast if clone fails.

### Parallel subagent pass (one combined pass)
Run both in parallel:
- **Subagent A — doc processing** (existing, runs when docs/folder provided): reads each source, extracts structured knowledge
- **Subagent B — codebase scan** (new, runs when codebase provided): Explore agent over local path. Reports: current user-facing features & flows, architecture & key modules, data model & key entities, tech stack & notable dependencies, existing design language (tokens/components found in code), integration points & external surfaces, known constraints & tech-debt signals. Cites file paths throughout.

### Synthesis — sequential, each feeds the next

**1. Write `00-codebase-understanding.md`** (only if codebase provided) — from Subagent B alone:
```
## TL;DR
## Current features & flows       <!-- stage-affinity: 01 02 03 -->
## Architecture & modules          <!-- stage-affinity: 08 03 -->
## Data model                      <!-- stage-affinity: 08 03 -->
## Tech stack & dependencies       <!-- stage-affinity: 08 06 -->
## Design language                 <!-- stage-affinity: 04 05 -->
## Integration points              <!-- stage-affinity: 08 03 -->
## Known constraints & tech debt   <!-- stage-affinity: 02 08 -->
```
Commit as stage `00c`.

**2. Write `00-context-wiki.md`** — synthesized from Subagent A output + references `00c` where relevant.

Updated section order:
```
## TL;DR
## Problem & context
## Users & needs
## Non-goals & explicit exclusions   <!-- stage-affinity: 01 02 -->
## Success indicators                <!-- stage-affinity: 01 07 -->
## Decisions already made            <!-- stage-affinity: 01 02 03 -->
## Technical constraints             <!-- stage-affinity: 03 04 06 08 -->
## Stakeholder authority             <!-- stage-affinity: 01 02 03 -->
## Concepts & glossary
## Open questions & uncertainties
## Source map
```

Four new sections:
- **Non-goals & explicit exclusions** — things ruled out per docs; bullets tagged `[hard]` or `[inferred]` with `src_NNN`; prevents stage 01 filling gaps with scope the PM already rejected
- **Success indicators** — KPIs/OKRs/launch criteria from sources; mark `⚠️` if none measurable exist
- **Technical constraints** — hard/soft platform or integration constraints; tag `[hard]` vs `[soft/preferred]`; omit section entirely if no constraints in sources
- **Stakeholder authority** — decisions attributed to named authority; table: Decision | Authority | Source; these are binding constraints, not assertions to evaluate; omit if absent

Two new signals on each content-bearing section (not TL;DR, Concepts & glossary, or Source map):
- **Confidence tier** (opening line): `> Confidence: High — stated in PM-authored PRD (src_002).` High = PM-authored artifact. Medium = secondary source. Low = inferred by model.
- **Stage-affinity hints** — `<!-- stage-affinity: NN -->` comments on section headers

Two new self-lint rules (Step 3b):
1. Sources contain KPIs/OKRs but Success indicators is empty or Low confidence → emit `FYI:` warning
2. Highest-provided stage ≥ 04 but Technical constraints is empty → emit `FYI:` warning

Commit as stage `00w`.

**3. Write `00-context-understanding.md`** — PM-facing, 6 sections:

1. **What I understood** — prose + structured block:
   ```
   **Problem:** <one sentence>
   **Primary users:** <one sentence>
   **Key locked decisions:** <bullets>
   **Non-goals I extracted:** <bullets, flagging [inferred] for PM confirmation>
   ```

2. **Source trust table**:
   | Source | Type | Reliability | Strengths | Weaknesses | Role |
   |---|---|---|---|---|---|
   | src_001 | PM-authored PRD | High | Complete requirements | Missing metrics | Adopted as stage 03 |

3. **Assumption register** — for every gap/backfill stage, the specific assumptions the model will use:
   | Stage | Section | Assumption | Based on | Confidence |
   |---|---|---|---|---|

4. **Conflict resolution block** — every `⚠️` in the wiki becomes an explicit block with a PM blank to fill before approving:
   ```
   **Conflict 1: <topic>**
   - src_002 says "..."
   - src_004 says "..."
   - This affects: <downstream implications>
   - **Your call:** ___________
   ```
   "No conflicts found across sources." if none.

5. **Coverage map** — `✅/⚠️/⛔` per stage; for `⚠️` name what's likely lost; for fresh-generation stages name the top assumption (link to register row)

6. **What happens on approval** — existing content unchanged

Commit as stage `00u`.

### PM annotation convention
`> **PM:** ...` blockquote anywhere in `00-context-wiki.md` = highest-priority override of the immediately preceding content. Applies to the wiki only — not to `00c` (factual codebase scan) or `00u` (understanding doc).

Priority rules all stage skills apply when reading the wiki:
1. `> **PM:** ...` annotations — highest priority; overrides conflicting claims in same section
2. `## Stakeholder authority` entries — binding constraints; treat as non-negotiable
3. `## Decisions already made` — locked; do not re-open
4. All other wiki content — grounding background; not a new requirement source

PM annotations are included in the body hash — editing after approval triggers drift detection and cascades staleness downstream. No Python changes needed.

---

## Stage SKILL.md changes (all 9 stages: 01–09)

**Identical change across all 9 files.** Replace the current one-sentence wiki consumption block in the Inputs section with:

```
**Context wiki (if present).** If `00-context-wiki.md` exists, read it before generating. Apply these rules in order:
1. `> **PM:** ...` annotations — highest priority; override any conflicting claim in the same section.
2. `## Stakeholder authority` entries — binding constraints; treat as non-negotiable.
3. `## Decisions already made` — locked choices; do not re-open or re-derive them.
4. All other wiki content — grounding background; use it to avoid invention, not as a new requirement source.
Use the `<!-- stage-affinity: NN -->` hints to weight which sections matter most for this stage.
```

### `skills/pm-stage-01-brief/SKILL.md` — additional changes

**Additional input:** If `00-codebase-understanding.md` is present, read its `<!-- stage-affinity -->` hints to weight which sections matter for the brief. The wiki already synthesizes 00c's substance — read 00c for the affinity weighting only, not as a parallel knowledge source.

**Enhancement framing** (added to Output spec and Writing guidance):
If `00-codebase-understanding.md` exists OR `project_type=enhancement` in `.meta.yaml`: the brief covers the **enhancement only** — the new capability being added to the existing product. "Problem" is the current-product gap (what's missing or broken in the existing product). "Why Now" is why this change at this point in the product's life. The existing product context lives in the pre-stage docs; the brief should not re-describe it, only reference it where needed. If neither condition is true: standard greenfield brief, unchanged.

---

## Tests

### `tests/unit/test_project.py`
- `test_migrate_v2_to_v3`: v2 meta dict → `migrate_meta()` → `project_type=="new_product"`, `codebase_path is None`, `codebase_ref is None`, `schema_version==3`; existing stages/hashes unchanged
- `test_00c_in_stage_tables`: `"00c"` in `STAGE_NAMES`, `STAGE_ARTIFACTS`, `PRE_STAGES`, `STAGE_ORDER`; position before `"00w"`

### `tests/integration/test_stage_gates.py`
- `test_enhancement_project_scaffolds`: `pm_new.py --mode enhancement` → meta has `project_type: enhancement`, `schema_version: 3`
- `test_brief_gates_on_00c_when_present`: approve `00` + `00c` + `00w` + `00u` → gate for `01` passes; unapprove `00c` → gate blocks

---

## Verification

```bash
python3 -m pytest tests/unit/test_project.py tests/integration/test_stage_gates.py

# Manual smoke
/pm-new test-enhance "Add chatbot to portal" --mode enhancement
# Inspect .meta.yaml: project_type, schema_version: 3
/pm-status   # shows Mode: enhancement
```
