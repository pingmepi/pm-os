# PM-OS Architecture

This document describes the **as-built** architecture of PM-OS on the `main` branch. Where the build spec (`docs/spec/pm-os-spec.md`) and the running code differ, this document follows the code — see [Spec vs. implemented](#spec-vs-implemented) at the end.

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

- `install.sh --runtime claude|codex` clones `~/.pm-os` from the **GitHub remote** and syncs skills (and, for Claude, hooks) into the runtime discovery dirs.
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
        S3["pm-new / pm-status<br/>pm-feedback / pm-share"]
        S4["pm-os-install / pm-os-update"]
    end

    subgraph Scripts["scripts/"]
        P1["pm_new.py"]
        P2["pm_approve.py"]
        P3["pm_status.py"]
        P4["pm_feedback.py"]
        P5["pm_share.py"]
        P6["pm_os_install.py / pm_os_update.py"]
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
    end

    S1 -->|PM_OS_STAGE=NN inline bash| H1
    S1 -->|writes draft + logs| L3 & L4
    S2 --> P2
    S3 --> P1 & P3 & P4 & P5
    S4 --> P6

    P2 -->|"subprocess, PM_OS_STAGE=NN"| H2
    H1 --> L1 & L2 & L3 & L4
    H2 --> L6 & L7 & L1 & L3 & L4
    P1 --> L1 & L4 & L5
    P2 --> L1 & L2 & L3 & L4 & L5
    P3 --> L1
    P4 --> L4
```

**State flows between scripts and hooks via the `PM_OS_STAGE` environment variable, not arguments.**

### Component responsibilities

| Component | Responsibility |
|-----------|----------------|
| `skills/pm-stage-NN-*/SKILL.md` | The stage prompt + the inline bash the agent runs: pre-stage gate, read upstream, generate, write draft, log telemetry. Ships an `agents/openai.yaml` twin for Codex. |
| `skills/pm-approve` → `scripts/pm_approve.py` | Validates status, computes body `content_hash`, writes approval to frontmatter + `.meta.yaml`, logs `stage_approved`, then shells out to `post-approve.py`. |
| `skills/pm-new` → `scripts/pm_new.py` | Scaffolds `~/pm-projects/<slug>/`: business statement, `.meta.yaml` (9 stages `pending`), empty telemetry/feedback, `.history/`. Sets `genai_flag`. |
| `skills/pm-status` → `scripts/pm_status.py` | Reads `.meta.yaml`; reports stage statuses, recent events, feedback count. |
| `skills/pm-feedback` → `scripts/pm_feedback.py` | Appends a rating/tags/free-text entry to `feedback.jsonl`; logs `feedback_submitted`. |
| `skills/pm-share` → `scripts/pm_share.py` | Exports approved artifacts to a shareable text bundle. |
| `hooks/pre-stage.py` | **The gate.** Blocks if any upstream is `pending`/`draft`/`stale`; re-hashes approved upstreams to detect post-approval `edited` drift; runs the implicit-reapproval prompt, cascading `stale` to downstream approved stages on implicit reapproval. |
| `hooks/post-approve.py` | Renders HTML companions for stages 04/05, cascades `stale` to downstream approved stages, pushes telemetry/feedback via `git_sync`. |
| `lib/project.py` | `resolve_project()` walks up from CWD to the nearest `.meta.yaml`; stage order/name tables; `upstream_stage_ids()`. |
| `lib/hashing.py` | `hash_artifact_body()` (SHA-256 over body only, LF-normalized) and `hash_event()` (chain link). |
| `lib/frontmatter.py` | YAML frontmatter read/write/`update_status`. |
| `lib/telemetry.py` | Append-only, hash-chained JSONL event log. |
| `lib/config.py` | Loads `~/.pm-os/config.yaml`; applies runtime-neutral model policy (`default_model_tier`, `deep_reasoning_stages`); migrates from env vars. |
| `lib/html_render.py` | Jinja2 render of `04-design-spec.html` and `05-prototype-mockup.html`. |
| `lib/git_sync.py` | Clone-or-fetch the feedback repo cache, copy JSONL, commit, push. |

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

- **`.meta.yaml`** — project metadata + `stages[]` list (id, name, status, `approved_at`, `content_hash`, `upstream_hashes_at_approval`, `regeneration_count`, `optional`). Carries `schema_version`.
- **Artifact frontmatter** — `status`, `approved_at/by`, `content_hash`, `generated_hash`, `pm_os_version`, `genai_flag`, `generation_notes`, followed by the Markdown body.
- **`telemetry.jsonl`** — append-only, hash-chained (`prev_event_hash` → `event_hash`). Event types include `project_created`, `stage_started`, `stage_generated`, `stage_approved`, `stage_edited_post_approval`, `implicit_reapproval`, `stage_marked_stale`, `feedback_submitted`. Telemetry failures warn but never break the workflow.
- **`feedback.jsonl`** — append-only ratings/tags/free-text.
- Both JSONL files are pushed to the shared `pm-os-feedback` repo under `telemetry/<pm>/<slug>/`.

---

## 7. Runtime agnosticism

Every skill ships **`SKILL.md`** (Claude, YAML frontmatter) **and** **`agents/openai.yaml`** (Codex interface metadata). `install.sh` / `pm_os_update.py` route to `~/.claude/{skills,hooks}` for Claude and `~/.agents/skills` for Codex (Codex skips hooks). Model choice is **config-driven, not hardcoded**: `config.py` stores `default_model_tier` and `deep_reasoning_stages` (`["03","06","08"]`); skills advise running deep-reasoning stages on the strongest available model rather than naming a provider model id.

---

## Spec vs. implemented

`docs/spec/pm-os-spec.md` is partly aspirational. The `main` code is **leaner** than the spec in these ways — trust the code:

| Spec describes | Status on `main` |
|----------------|-----------------|
| `lib/edit_distance.py`, `lib/embeddings.py` | **Not built.** Distance metrics in `stage_approved` telemetry are emitted as `None`. |
| `hooks/post-tool-use.py` | **Not built.** Out-of-band edits are detected lazily by `pre-stage.py` on the next stage run, not on every tool use. |
| `hooks/session-end.py` | **Not built.** Telemetry writes are synchronous; `telemetry.flush_pending()` is a no-op. |
| Full MCP `pm-share` integration | `pm_share.py` exports a text bundle; no live connector. |
| `sentence-transformers` dependency | Not installed. Runtime deps are `pyyaml`, `jinja2`, `gitpython` only. |

Everything else in this document reflects code that exists and runs on `main`.
