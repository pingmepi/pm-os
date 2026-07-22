# PM-OS Architecture

This document describes the **as-built** architecture of PM-OS on the `main` branch. Where the build spec (`docs/reference/pm-os-spec.md`) and the running code differ, this document follows the code — see [Spec vs. implemented](#spec-vs-implemented) at the end.

PM-OS is a **local-first, PM-led product-definition layer** delivered as an **agent skill suite** — not an app. There is no frontend and no backend service. A PM drives a product idea through a fixed, gated pipeline of stages; each stage emits a Markdown artifact that a human reviews and explicitly approves before the next stage can run. All state is plain files on the PM's machine.

---

## 1. System context

PM-OS spans three planes: the **agent runtime** (the generation engine), the **local Python engine** (mechanical state), and **two GitHub repos** (source + shared telemetry).

```mermaid
flowchart TB
    PM([Product Manager])

    subgraph Runtime["Agent runtime (Claude Code / OpenAI Codex)"]
        SK["Skills (SKILL.md + agents/openai.yaml)<br/>prompt + inline bash"]
    end

    subgraph Local["Local Python engine (~/.pm-os)"]
        SC["scripts/*.py<br/>command wrappers"]
        HK["hooks/*.py<br/>gates & approval"]
        LB["lib/*.py<br/>shared state helpers"]
    end

    subgraph Files["Project files (~/pm-projects/&lt;slug&gt;)"]
        ART["NN-*.md artifacts<br/>+ HTML companions"]
        META[".meta.yaml"]
        TEL["telemetry.jsonl<br/>feedback.jsonl"]
    end

    subgraph GH["GitHub"]
        SRC["pm-os repo<br/>(source of the system)"]
        FB["pm-os-feedback repo<br/>(shared telemetry)"]
    end

    PM -->|/pm-* or $pm-*| SK
    SK -->|runs inline bash| SC
    SK -->|PM_OS_STAGE=NN| HK
    SC --> LB
    HK --> LB
    LB --> ART
    LB --> META
    LB --> TEL
    SRC -.->|install.sh / pm_os_update| Local
    LB -->|git_sync push| FB

    classDef store fill:#eef,stroke:#557;
    class ART,META,TEL,META store;
```

**Key idea:** the agent is the *judgment/generation* layer (lives in `SKILL.md`); Python is the *mechanical state* layer (scaffold, hash, approve, gate, telemetry). Nothing progresses autonomously — a human approval sits at every stage boundary.

---

## 2. Install / sync topology

The repo you edit is **not** the running system. Code reaches the runtime in two hops.

```mermaid
flowchart LR
    REPO["pm-os repo<br/>(this working copy)"]
    CANON["~/.pm-os<br/>(canonical install)"]
    CLAUDE["~/.claude/skills<br/>~/.claude/hooks"]
    CODEX["~/.agents/skills<br/>(no hooks)"]

    REPO -->|"install.sh / pm_os_update.py<br/>(clone/ff from GitHub remote)"| CANON
    CANON -->|"sync skills+hooks<br/>--runtime claude"| CLAUDE
    CANON -->|"sync skills only<br/>--runtime codex"| CODEX
    CANON -.->|"scripts import lib via<br/>hardcoded ~/.pm-os/lib"| CANON
```

- `install.sh --runtime claude|codex|all` clones `~/.pm-os` from the **GitHub remote** and syncs skills (and, for Claude, hooks) into the runtime discovery dirs.
- Gates always execute from `~/.pm-os/hooks` — the copy into `~/.claude/hooks` is vestigial/reserved for future native-hook registration. Codex skips hooks entirely.
- `scripts/*.py` insert `~/.pm-os/lib` on `sys.path`, so **edits in the working copy are inert until they reach `~/.pm-os`.**

---

## 3. Component wiring

How a stage actually runs, end to end, across skills → scripts → hooks → lib.

```mermaid
flowchart TD
    subgraph Skills["skills/"]
        S1["pm-stage-NN-*<br/>(generate artifact)"]
        S2["pm-approve"]
        S3["pm-new / pm-status<br/>pm-feedback / pm-share / pm-sync"]
        S4["pm-os-install / pm-os-update<br/>pm-os-verify"]
        S5["pm-context-import"]
        S6["pm-prototype-html<br/>(standalone HTML regen)"]
        S7["pm-update-roadmap-tracking"]
    end

    subgraph Scripts["scripts/"]
        P1["pm_new.py"]
        P2["pm_approve.py"]
        P3["pm_status.py"]
        P4["pm_feedback.py"]
        P5["pm_share.py / pm_sync.py"]
        P6["pm_os_install.py / pm_os_update.py<br/>pm_os_verify.py"]
        P7["pm_context_import.py"]
        P8["pm_validate_artifact.py<br/>(Stage 03–06/08 contract checks)"]
        P9["discover_tracking_context.py<br/>(roadmap tracking helper)"]
    end

    subgraph Hooks["hooks/ (run from ~/.pm-os/hooks)"]
        H1["pre-stage.py<br/>(gate)"]
        H2["post-approve.py<br/>(render + cascade + push)"]
    end

    subgraph Lib["lib/"]
        L1["project.py<br/>resolve/load/save meta"]
        L2["hashing.py<br/>body & event hashes"]
        L3["frontmatter.py<br/>read/write/update_status"]
        L4["telemetry.py<br/>hash-chained JSONL"]
        L5["config.py<br/>config + model policy"]
        L6["html_render.py<br/>04/05 HTML companions"]
        L7["git_sync.py<br/>push feedback repo"]
        L8["text_metrics.py<br/>edit distance"]
        L9["context.py<br/>context overlay"]
        L10["artifact_contracts.py<br/>Stage 03–06 quality contracts"]
    end

    S1 -->|PM_OS_STAGE=NN inline bash| H1
    S1 -->|writes draft + logs| L3 & L4
    S1 -->|load context overlay| L9
    S1 -->|strict contract check| P8
    S2 --> P2
    S3 --> P1 & P3 & P4 & P5
    S4 --> P6
    S5 --> P7
    S6 --> L6
    S7 --> P9

    P2 -->|"subprocess, PM_OS_STAGE=NN"| H2
    P2 -->|warn contract check| P8
    P7 -->|"subprocess, PM_OS_STAGE=NN (on approve)"| H2
    P7 -->|warn contract check on import| P8
    H1 --> L1 & L2 & L3 & L4
    H2 --> L6 & L7 & L1 & L3 & L4
    P1 --> L1 & L4 & L5
    P2 --> L1 & L2 & L3 & L4 & L5 & L8
    P3 --> L1
    P4 --> L4
    P7 --> L1 & L2 & L3 & L4 & L5
    P8 --> L10
```

**State flows between scripts and hooks via the `PM_OS_STAGE` environment variable, not arguments.**

### Component responsibilities

| Component | Responsibility |
|-----------|----------------|
| `skills/pm-stage-NN-*/SKILL.md` | The stage prompt + the inline bash the agent runs: pre-stage gate, read upstream, generate, write draft, log telemetry. Ships an `agents/openai.yaml` twin for Codex. |
| `skills/pm-approve` → `scripts/pm_approve.py` | Validates status, computes body `content_hash`, writes approval to frontmatter + `.meta.yaml`, logs `stage_approved`, then shells out to `post-approve.py`. |
| `skills/pm-new` → `scripts/pm_new.py` | Scaffolds `~/pm-projects/<slug>/`: business statement (`00` as `draft`; optional — a placeholder is written if omitted), `.meta.yaml` (stages `01–09` `pending`), empty telemetry/feedback, `.history/`. Sets `genai_flag`. `--mode enhancement` (or `PM_OS_PROJECT_TYPE`) records `project_type: enhancement`; `--codebase <url-or-path>` records `codebase_path` for the codebase scan. |
| `skills/pm-context-import` → `scripts/pm_context_import.py` | Mechanical state for the context-intake flow. `register` preserves a raw source in `.history/` + `.sources.yaml` (logs `context_ingested`); `preflight` prints backfill-feasibility verdicts (`resolve_backfill`) and exits non-zero on an infeasible gap; `prepare-codebase` clones (URL) or validates (local path) the enhancement codebase, records its git SHA as `codebase_ref`, and gitignores `.codebase/`; `commit` stamps an SKILL-written artifact slot to draft/approved with `origin` (`generated`/`imported`/`backfilled`), body hash, meta + frontmatter, telemetry, and (on approve) `post-approve.py`. Generates no content — judgment lives in the SKILL. |
| `skills/pm-status` → `scripts/pm_status.py` | Reads `.meta.yaml`; reports stage statuses, recent events, feedback count. |
| `skills/pm-feedback` → `scripts/pm_feedback.py` | Appends a rating/tags/free-text entry to `feedback.jsonl`; logs `feedback_submitted` into the hash chain; triggers a central sync. |
| `skills/pm-sync` → `scripts/pm_sync.py` | Manual catch-up sync of **all** projects' telemetry/feedback to the central repo (`git_sync.push_all`); `--verify` validates every project's hash chain. |
| `skills/pm-share` → `scripts/pm_share.py` | Two modes, both read-only projections that never touch gate/hash/status. Default: a single stage or all approved/edited stages, concatenated verbatim, to stdout or a file. `--package`: a decomposed handoff package (`handoff/`) — one self-contained file per user story in house format, assembled by walking the traceability spine (`US-### → FR-###s → UJ-### journey → covering TC-###s → serving SCR-### screens`), plus overview/reference docs (including `reference/screen-map.md`, the screen→stories reverse view) and an optional `--html` index. |
| `skills/pm-os-verify` → `scripts/pm_os_verify.py` | Health-checks the *installed* `~/.pm-os` for a runtime: `git` binary on PATH, all 9 `lib` module imports (including `html_render`, `context`, `text_metrics`), gate hooks, all 4 Jinja2 templates, config keys + `projects_dir` existence, installed skills count, plus three deterministic self-tests — gate (`pre-stage.py` blocks unapproved upstream / allows first stage), telemetry (append + hash chain + `push_all` status), and artifact contracts (detects missing PRD sections). |
| `skills/pm-prototype-html` | Standalone skill to generate or regenerate `05-prototype-mockup.html` from the approved prototype brief and design spec without re-running the full stage 05 brief generation. Auto-invoked by `pm-stage-05-prototype-brief` after the brief is written; also callable directly to rebuild the prototype only. |
| `skills/pm-update-roadmap-tracking` → `scripts/discover_tracking_context.py` | Reads roadmap, implementation-plan, and status docs in a product root; calls `discover_tracking_context.py` to surface recent git/doc change signals; updates only the relevant tracking docs with evidence-backed status changes, risks, and next steps. |
| `scripts/pm_validate_artifact.py` | CLI entry point for the Stage 03–06 (+ GenAI-only stage 08) artifact contract validator (`lib/artifact_contracts.py`). Accepts `<stage> --mode strict\|warn`: strict mode exits non-zero on any required-section or journey-traceability finding; warn mode prints findings and exits 0. Called in strict mode by stage skills before generation telemetry; called in warn mode by `pm_approve.py` and `pm_context_import.py` so approval/import continue with visible findings logged as `artifact_validation_warning`. |
| `scripts/discover_tracking_context.py` | Read-only helper that walks a product root, finds tracking documents (roadmap, implementation plans, status docs, backlogs), and reports recent git-log and doc-change signals as a compact Markdown digest. Used by `pm-update-roadmap-tracking` to ground status updates in evidence. |
| `hooks/pre-stage.py` | **The gate.** Blocks if any upstream is `pending`/`draft`/`stale`; re-hashes approved upstreams to detect post-approval `edited` drift; runs the implicit-reapproval prompt, cascading `stale` to downstream approved stages on implicit reapproval. |
| `hooks/post-approve.py` | Renders HTML companions for stages 04/05, cascades `stale` to downstream approved stages, and syncs telemetry/feedback via `git_sync` — deferred to a detached background process by default so the network push never gates approval completion (`PM_OS_SYNC_BLOCKING=1` forces an inline push). |
| `lib/project.py` | `resolve_project()` walks up from CWD to the nearest `.meta.yaml`; stage order/name tables; `upstream_stage_ids()`. |
| `lib/hashing.py` | `hash_artifact_body()` (SHA-256 over body only, LF-normalized) and `hash_event()` (chain link). |
| `lib/frontmatter.py` | YAML frontmatter read/write/`update_status`. |
| `lib/telemetry.py` | Append-only, hash-chained JSONL event log; `last_event()` reader and `verify_chain()` validator. |
| `lib/config.py` | Loads `~/.pm-os/config.yaml`; applies runtime-neutral model policy (`default_model_tier`, `deep_reasoning_stages`); migrates from env vars. |
| `lib/html_render.py` | Jinja2 render of `04-design-spec.html` and `05-prototype-mockup.html`. |
| `lib/jira_markup.py` | `to_jira_markup()` — Markdown → Jira wiki markup for the offline CSV export's ticket descriptions. A documented subset (headings, emphasis, lists, links, tables, code); unrecognized syntax passes through, and code spans/blocks are protected from every other rule. |
| `lib/traceability.py` | **The traceability spine** (`.traceability.yaml`, **schema v3**) — a derived, safe-to-delete index rebuilt from the artifact bodies at approval. Links requirement ids (`REQ`/`US`/`FR-###`) to QA scenarios (`TC-###`), TRD tasks (`TSK-###`, only from an **approved** stage 08), and design-spec screens (`SCR-###`, only from an **approved** stage 04, scoped to `## Information Architecture`), with reverse links on each requirement and reserved slots (`tickets`/`bugs`/`code_refs`/`design_refs`) preserved across rebuilds. Resolver queries: `scenarios_for_requirement`, `tasks_for_requirement`, `screens_for_requirement`, and their inverses. |
| `lib/git_sync.py` | Clone-or-fetch the feedback repo cache, copy JSONL, commit, push. `push_feedback_repo()` (one project) and `push_all()` (every project) share one helper, report failures loudly with a status dict, and skip deleted projects. |
| `lib/text_metrics.py` | Pure-stdlib Levenshtein `char_edit_distance` + `normalized_edit_distance` for generated-vs-approved drift. |
| `lib/context.py` | **Context overlay loader.** `resolve_context()` / `render_context()` merge the company/team/glossary/guardrails **global** layer + per-stage **format/example** packs + a per-project override (precedence project > stage > global), applying `augment`/`override`/`reference-only` modes and dropping empty/TODO content so an unfilled pack is a no-op. `seed_context()` copies missing files from `context.example/` → `~/.pm-os/context/`. The 9 stage skills call it in a "Load context overlay" step; install/update seed it, and the loader self-seeds on first read if the dir is absent (covers the self-update bootstrap). The live `~/.pm-os/context/` is gitignored user data. |
| `lib/artifact_contracts.py` | **Stage 03–06 artifact quality contracts** (plus a GenAI-only check on stage 08). `CONTRACT_VERSION = 3`. Validates required sections (`UJ-###` user journeys in PRD; journey-to-flow traceability and product interaction model in design spec; prototype audience modes and validation plan in prototype brief), recommended sections, journey drift across stages, and high-signal HTML prototype checks (reviewer chrome uses `class="review-only"`). For `genai_flag: true` projects it also warns (v3) when the PRD's `Model Selection Rationale` or the TRD's `Model Serving & Selection` names no availability path or no fallback model — stage 08 has no required-section contract, so it is validated for that check only and is exempt from the `artifact_contract_version` warning. Strict mode raises on any required-section finding; warn mode returns findings as structured dicts. Called via `scripts/pm_validate_artifact.py`; findings logged as `artifact_validation_warning` telemetry. |

---

## 4. Stage pipeline & state machine

Stages are fixed (`lib/project.py`): **01 brief → 02 scope → 03 prd → 04 design-spec → 05 prototype-brief → 06 qa-plan → 07 metrics-plan**, followed by optional capstones: **08 trd** and **09 roadmap**. Stage 08 and 09 both depend on stages 01-07. Stage 09 also depends on stage 08 when an approved TRD is available, so roadmap generation and approval can incorporate technical delivery context without making TRD mandatory.

Each stage carries one status. Two off-path states — `edited` (body changed after approval, caught by hash drift) and `stale` (an upstream was re-approved) — sit beside the happy path.

```mermaid
stateDiagram-v2
    [*] --> pending
    pending --> draft: run /pm-stage-NN
    draft --> approved: /pm-approve NN
    approved --> edited: body edited after approval<br/>(hash drift, pre-stage hook)
    approved --> stale: upstream re-approved<br/>(post-approve or implicit-reapproval cascade)
    edited --> approved: /pm-approve NN<br/>or implicit reapproval
    stale --> draft: re-run /pm-stage-NN
    stale --> approved: /pm-approve NN (attest still valid)
    approved --> [*]
```

**Two synchronized sources of truth:** stage state lives in **both** `.meta.yaml` (`stages[]`) **and** each artifact's frontmatter, kept in lockstep by `pm_approve.py` and the hooks. `content_hash` is computed over the **body only**, so frontmatter edits never trigger false drift.

---

## 5. End-to-end sequence: generate → approve

```mermaid
sequenceDiagram
    participant PM
    participant Skill as pm-stage-NN (SKILL.md)
    participant Pre as pre-stage.py
    participant Approve as pm_approve.py
    participant Post as post-approve.py
    participant Lib as lib/*
    participant FB as feedback repo

    PM->>Skill: /pm-stage-NN
    Skill->>Pre: PM_OS_STAGE=NN python3 pre-stage.py
    Pre->>Lib: re-hash upstream, detect edited/blocking
    alt upstream blocking
        Pre-->>Skill: exit 1 (halt)
    else upstream ok / edited resolved
        Pre-->>Skill: exit 0
    end
    Skill->>Lib: read upstream, log stage_started
    Skill->>Lib: write .history + NN-*.md (status=draft), log stage_generated
    Skill-->>PM: draft ready — review

    PM->>Approve: /pm-approve NN
    Approve->>Lib: hash body, update frontmatter + .meta.yaml, log stage_approved
    Approve->>Post: subprocess PM_OS_STAGE=NN
    Post->>Lib: render 04/05 HTML (if applicable)
    Post->>Lib: cascade stale to downstream approved, log stage_marked_stale
    Post->>FB: git_sync push telemetry + feedback
    Post-->>Approve: exit 0
    Approve-->>PM: approved (+ any downstream now stale)
```

---

## 6. Data & telemetry

- **`.meta.yaml`** — project metadata + `stages[]` list (id, name, status, `approved_at`, `content_hash`, `upstream_hashes_at_approval`, `regeneration_count`, `optional`, `origin`). Carries `schema_version` (currently 3; `lib/project.py:migrate_meta` upgrades older projects in place). v3 adds `project_type` (`new_product | enhancement`), `codebase_path`, and `codebase_ref` for enhancement projects. `origin` is `generated | imported | backfilled`. The stage-00 understanding group (`00` business-statement, plus the conditional `00c` codebase-understanding, `00w` context-wiki, and `00u` context-understanding when `/pm-context-import` is used) gates stage 01.
- **`.sources.yaml`** — registry of externally-provided sources ingested via `/pm-context-import` (id, type, uri, captured_at, snapshot path); raw originals preserved under `.history/`.
- **Artifact frontmatter** — `status`, `approved_at/by`, `content_hash`, `generated_hash`, `pm_os_version`, `genai_flag`, `generation_notes`, `origin`, and (for current Stage 03–06 generations) `artifact_contract_version`, followed by the Markdown body.
- **`telemetry.jsonl`** — append-only, hash-chained (`prev_event_hash` → `event_hash`). Event types include `project_created`, `stage_started`, `stage_generated`, `stage_approved`, `stage_imported`, `stage_backfilled`, `context_ingested`, `stage_edited_post_approval`, `stage_edited_via_note`, `artifact_validation_warning`, `implicit_reapproval`, `stage_marked_stale`, `feedback_submitted`. Telemetry failures warn but never break the workflow.
- **`feedback.jsonl`** — append-only stage feedback entries (`rating`, `note`, PM, project, timestamp). Feedback is also joined into `telemetry.jsonl` as `feedback_submitted` so it participates in the hash chain.
- Both JSONL files are pushed to the shared `pm-os-feedback` repo under `telemetry/<pm>/<slug>/`.

### What telemetry lets PM-OS infer

Telemetry is useful because it records both **workflow facts** (events that happened) and enough timestamps/hashes to derive **process signals**. The event log should be treated as evidence about PM-OS usage and artifact lifecycle, not as a complete record of all human reasoning outside the tool.

| What can be understood | How it is inferred | Supporting events / fields | Caveats |
|---|---|---|---|
| Project creation volume | Count `project_created` events by PM, project, version, and time window. | `event_type`, `pm`, `project`, `pm_os_version`, `timestamp` | Projects created before telemetry or never synced centrally may be missing from shared analysis. |
| Stage funnel progress | For each project, read the latest stage events and `.meta.yaml` status to see which stages started, generated, approved, edited, stale, imported, or backfilled. | `stage_started`, `stage_generated`, `stage_approved`, `stage_imported`, `stage_backfilled`, `stage_marked_stale`, `.meta.yaml` | Telemetry is chronological evidence; `.meta.yaml` is the current state snapshot. Use both when diagnosing. |
| Time spent generating a stage | Difference between `stage_started.timestamp` and the matching `stage_generated.timestamp`. | `stage_started`, `stage_generated`, `stage` | This measures elapsed agent/workflow time, not pure model runtime. It can include tool execution and user interruption. |
| Time from draft to approval | `stage_approved.payload.time_to_approve_seconds`, computed from `stage_generated` to approval when a generated snapshot exists. | `stage_generated`, `stage_approved.payload.time_to_approve_seconds` | Correctly `null` for stage-00 docs, imported artifacts, and backfilled artifacts that did not have a generated snapshot. |
| PM edit effort before approval | Compare generated snapshot body with approved artifact body. Current approval telemetry records character and normalized edit distance. | `.history/*.generated.md`, approved artifact body, `stage_approved.payload.char_edit_distance`, `normalized_edit_distance` | Character distance measures textual change, not meaning. Formatting-only edits can look larger than their product impact. |
| Semantic drift from generated draft | Agent-estimated drift can be passed on approval when available. | `stage_approved.payload.semantic_distance` | Subjective and runtime-dependent. Treat as review guidance, not a deterministic metric. |
| Model usage by stage | `stage_generated.payload.model` captures the actual model id supplied by the agent; `model_tier` captures PM-OS policy tier for the stage. | `stage_generated.payload.model`, `stage_generated.payload.model_tier`, `config.deep_reasoning_stages` | The model id is only as reliable as the agent/runtime filling it in. Older events may lack it. |
| Regeneration frequency | Use stage metadata and approval payloads to count how many times a stage was regenerated before approval. | `.meta.yaml.stages[].regeneration_count`, `stage_approved.payload.regeneration_count`, repeated `stage_generated` | Regeneration count is per stage, not a full explanation of why regeneration happened. Use `generation_notes` and feedback for context. |
| Steering note impact | Notes used during generation appear in frontmatter and `stage_generated` payload; upstream edits made because of notes log `stage_edited_via_note`. | Artifact `generation_notes`, `stage_generated.payload.notes`, `stage_edited_via_note.payload.note`, `edited_sections` | Notes explain explicit steering, not every implicit PM preference. |
| Artifact contract quality | Count and group non-blocking structural/traceability findings that remained when approval continued. | `artifact_validation_warning.payload.findings`, `contract_version`, `origin`, `stage` | A warning is evidence of a contract gap, not proof the artifact is unusable; imported sources are intentionally preserved. |
| Imported versus generated pipeline shape | `origin` and import/backfill events show whether a stage was authored by PM-OS, imported from PM material, or backfilled from supplied downstream context. | `.meta.yaml.stages[].origin`, artifact frontmatter `origin`, `stage_imported`, `stage_backfilled`, `context_ingested` | Imported/backfilled artifacts may skip generation metrics by design. Use provenance rather than treating them as normal generated drafts. |
| Context intake coverage | Registered sources and backfill verdicts indicate what material was provided, preserved, adopted, or only used as context. | `.sources.yaml`, `context_ingested`, `stage_imported`, `stage_backfilled`, `payload.source_*`, `payload.derived_from` | The event log proves provenance and movement through PM-OS, not that the source content was complete or correct. |
| Upstream drift and rework | Detect approved artifacts edited after approval, implicit reapprovals, and downstream stale cascades. | `stage_edited_post_approval`, `implicit_reapproval`, `stage_marked_stale`, `payload.triggering_upstream_stage(s)` | Drift is detected lazily by the pre-stage gate on later runs, not continuously at every file edit. |
| Feedback quality signals | Stage ratings and notes can be joined to generation, approval, model, edit distance, and stage metadata. | `feedback.jsonl`, `feedback_submitted.payload.rating`, `free_text`, `stage` | Feedback is optional; null ratings or sparse notes are absence of signal, not proof of quality. |
| Sync and data freshness | Central repo contents plus local `pm-sync --verify` reveal whether projects have intact chains and whether telemetry reached the shared cache. | `telemetry.jsonl`, `event_hash`, `prev_event_hash`, `pm_sync.py --verify`, `git_sync` status | A valid local chain does not guarantee central sync succeeded. Sync failures are operational issues, not workflow events unless separately captured. |
| Tamper or corruption detection | Recompute each event hash from the previous event hash and payload. The first mismatch identifies where the chain broke. | `event_hash`, `prev_event_hash`, `telemetry.verify_chain()` | Hash chaining detects edits to telemetry lines, not edits to artifacts unless artifact hashes or stage status are also checked. |

Useful aggregate views from these signals:

- **Adoption:** projects created, stages started/generated/approved, optional 08/09 usage, context-import usage.
- **Throughput:** elapsed time per stage, approval cycle time, stages completed per project.
- **Quality and rework:** edit distance, semantic distance when present, regeneration count, stale cascades, feedback ratings/notes.
- **Process risk:** unapproved blockers, edited upstreams, stale downstream artifacts, broken telemetry chains, failed central sync.
- **Runtime/model policy:** model ids actually used, model tier by stage, deep-reasoning stage compliance.

For diagnosis, prefer a layered read:

1. Verify the telemetry chain with `pm-sync --verify` or `telemetry.verify_chain()`.
2. Read `.meta.yaml` for current stage state.
3. Read `telemetry.jsonl` for the chronological event trail.
4. Read artifact frontmatter and `.history/` snapshots to explain hashes, generated drafts, approvals, and edit distance.
5. Read `feedback.jsonl` and `feedback_submitted` events for PM judgment about quality or usefulness.

---

## 7. Runtime agnosticism

Every skill ships **`SKILL.md`** (Claude, YAML frontmatter) **and** **`agents/openai.yaml`** (Codex interface metadata). `install.sh` / `pm_os_update.py` route to `~/.claude/{skills,hooks}` for Claude and `~/.agents/skills` for Codex (Codex skips hooks). Model choice is **config-driven, not hardcoded**: `config.py` stores `default_model_tier` and `deep_reasoning_stages` (`["00w","00u","03","04","06","08","09"]`); skills advise running deep-reasoning stages on the strongest available model rather than naming a provider model id.

---

## Spec vs. implemented

`docs/reference/pm-os-spec.md` is partly aspirational. The `main` code is **leaner** than the spec in these ways — trust the code:

| Spec describes | Status on `main` |
|----------------|-----------------|
| `lib/edit_distance.py`, `lib/embeddings.py` | **Replaced/deferred.** Character and normalized edit distance are implemented in `lib/text_metrics.py`; embedding-based semantic distance is not built and is only recorded when the approving agent supplies an estimate. |
| `hooks/post-tool-use.py` | **Not built.** Out-of-band edits are detected lazily by `pre-stage.py` on the next stage run, not on every tool use. |
| `hooks/session-end.py` | **Not built.** Telemetry writes are synchronous; `telemetry.flush_pending()` is a no-op. |
| Full MCP `pm-share` integration | `pm_share.py` exports a text bundle; no live connector. |
| `sentence-transformers` dependency | Not installed. Runtime deps are `pyyaml`, `jinja2` only (git operations shell out to `git`). |

Everything else in this document reflects code that exists and runs on `main`.
