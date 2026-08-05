# PM-OS: Borrowable Skills & Connectors

**Status:** Analysis (no code changes); **E2 marketplace refresh added 2026-08-03.** **Original date:** 2026-06-18
**Purpose:** Identify which existing Claude Code / Codex agent skills and MCP connectors PM-OS can **borrow** instead of building from scratch — across both the current product and the roadmap in `../roadmap/current-state-review.md` §7 — and check the current skill suite against that catalog for gaps.

This is analysis only. Adopting any item still goes through the normal **commit → push → `pm_os_update.py`** path, and any MCP/external use must respect the **read-before-write, dry-run → confirm** sequencing principle already stated in §7.

---

## How "borrow" works here — three modes, governed by portability

PM-OS must behave identically on Claude Code and Codex (`CLAUDE.md`, Phase 1). Most agent skills in the environment are **Claude Code plugin skills** that may be absent on Codex, so "borrow" resolves to one of three modes, chosen per-case:

- **Mode A — MCP connector.** Use a running MCP server (Linear, Atlassian/Jira, Figma, Intercom…). Both Claude Code and Codex support MCP, so this is portable *and* removes the highest-effort, highest-risk roadmap work (auth, sync, provenance). Best for every external-integration phase.
- **Mode B — Pattern/content reuse.** Lift the checklist / structure / prompt of an existing skill into PM-OS's own portable `SKILL.md` (or `lib/`). Fully portable, no runtime dependency. Best for process skills (testing, security, release readiness, codebase understanding).
- **Mode C — Soft/optional runtime dependency.** Invoke the external skill if present, degrade gracefully if not. Use sparingly; **never on a gated path.** Any such use is a portability risk and must be flagged.

**Portability rule:** never put a Claude-only skill on a *gated* path. Gated stages stay self-contained Markdown + Python so Codex parity holds. External skills / MCP are enrichment, invoked behind opt-in / confirm.

**Current runtime boundary:** PM-OS has shipped Jira handoff support, but no external marketplace skill is a gated generation dependency. E2 may borrow vetted codebase-analysis patterns or offer opt-in enrichment, while PM-OS-owned Markdown and Python remain the portable, deterministic path on both Claude Code and Codex.

---

## Part 1 — Roadmap phase → borrowable capability

Phase titles key to `../roadmap/current-state-review.md` §7.

| Roadmap phase | Borrow | Capability / connector | Mode | Note |
|---|---|---|---|---|
| **3 — Brownfield / codebase understanding** | GitHub Awesome Copilot [`acquire-codebase-knowledge`](https://github.com/github/awesome-copilot/tree/main/skills/acquire-codebase-knowledge); [`arch:doc-and-modernize`](https://awesome-copilot.github.com/plugin/arch/) documentation mode; regression-scope patterns; built-in Explore agent | Deterministic inventory + focused inquiry, cited architecture/contradiction review, change-impact/regression reasoning | **B** primarily; **C** only in a PM-OS-owned snapshot | Reuse reviewed/pinned patterns behind PM-OS's portable `pm-context-scan-codebase`. Never let an external skill write to the target repo or become a gated dependency. |
| **3.5 — Traceability spine (`REQ-` / `TC-` IDs)** | *(little external)* | Internal data model | — | No good external borrow; build natively. |
| **3.6 — Automated test suite** | `python-testing` (pytest/fixtures/mocking/coverage), `tdd-workflow`, `eval-harness` (formal EDD), `verification-loop`, `llm-output-hardening` (guard LLM-output parsing in context-import/backfill) | Test-harness patterns + LLM-output guards | **B** | Partly already shipped (`tests/`, `pyproject.toml`, `docs/guides/testing.md`). Borrow remaining patterns. |
| **4a — Local handoff packet** | `doc-coauthoring` (structured spec authoring); `docx` / `pdf` / `pptx` (export to Word/PDF/deck) | Authoring workflow + format export | **B** (authoring) / **C** (format) | Packet stays local Markdown; format skills only when the PM wants Word/deck. |
| **4b — One tracker, export-only** | **Linear MCP** (full issue/project/milestone CRUD) **or** **Atlassian MCP** (Jira) | The connector itself — *do not build* | **A** | Biggest build-vs-borrow win. Cross-runtime via MCP. Keep PM-OS's dry-run → confirm → store-IDs-only policy. |
| **4 — Design-system / Figma (planned later)** | **Figma MCP** (design-context read, code-connect, diagrams) or **penpot MCP** (OSS) | Design source links + design context into stage 04/05 | **A** | Auth-gated, optional. penpot is the open-source fallback. |
| **5a — Bug intake + classification** | **Linear / Atlassian MCP** (pull bugs); reuse stage-06 `TC-…` IDs | Bug ingestion (classification stays PM-OS prompt logic) | **A** (ingest) / **B** (classify) | Classification is judgment — keep it in PM-OS, not borrowed. |
| **5b — Code-area suggestion (quarantined)** | built-in `code-review` / `security-review`, `git-workflow` (recent-changes heuristic), `Explore` agent, ECC `iterative-retrieval`/`code-tour` evidence-anchor patterns | Repo-snapshot → candidate-files → fix-plan pattern | **B** + **C** | Matches the "cite evidence, label suggestion, opt-in" quarantine. `repo-interview-prep` is explicitly excluded. No hard dependency on this path. |
| **6a — Release-readiness report** | `deployment-patterns` (production-readiness checklist), `changelog-generator` (release notes from commits), `git-workflow` | Readiness checklist + release-notes generation | **B** | `deployment-patterns`' checklist maps ~1:1 onto the readiness rollup; `changelog-generator` produces the notes. |
| **6b — Feedback intake + iteration** | **Intercom / HubSpot MCP** (support feedback); `deep-research` + built-in `WebSearch` (market/competitor/user signal) | Feedback ingestion (classification stays PM-OS) | **A** (ingest) / **B** (classify) | The "optional analytics/support connectors later" the phase already anticipates. |
| **Self-improvement loop** (`pm-os-self-improvement-loop-plan.md`) | `continuous-learning` (extract patterns from sessions → skills), `eval-harness` (formal session eval) | Telemetry → recommendation + artifact-quality eval | **B** | Directly overlaps the existing self-improvement plan. |
| **Gemini runtime** (deferred) | `skill-creator`, `mcp-builder` | Authoring consistency for new skills/connectors | **B** | `skill-creator` keeps new PM-OS skills uniform; `mcp-builder` only if a *custom* connector is ever needed beyond existing MCP. |

---

## Part 2 — Gap check: current skills vs the catalog ("did we miss anything?")

Cross-referencing the 11 stage skills + 10 utility skills against the available catalog surfaces capabilities PM-OS could already use but does not:

1. **Discovery research is ungrounded (stages 01/02).** `pm-stage-01-brief` and `-02-scope` generate purely from the business statement + context overlay — no external grounding. `deep-research` (firecrawl/exa) and built-in `WebSearch` could enrich discovery with market/competitor/user evidence (Mode B/C, opt-in). **Likely the biggest current-product miss.**
2. **`.docx` / `.pdf` intake conversion is an open Phase-2 "remaining" item.** The `pdf` and `docx` skills solve it directly for `/pm-context-import` (Mode C). Low effort, already-blocked work.
3. **Share/export is text-only.** `/pm-handoff --raw`/`--package` (the export modes of the single `pm-handoff` skill; formerly the standalone `pm-share`) emits plain text/Markdown; PMs share decks/docs. `pptx` / `docx` / `pdf` would let it export a stakeholder deck or Word doc (Mode C, on demand).
4. **PM-OS's own docs drift.** `codebase-docs-alignment` / the `docs-audit` skill could be a maintenance routine for PM-OS's own `docs/` and skill catalog — and doubles as the engine for the Phase-3 brownfield drift signal.
5. **LLM-output parsing is unguarded.** `pm_context_import.py` and backfill parse model output; `llm-output-hardening` patterns (null fields, malformed JSON, injection via extracted strings) belong in those Python paths (Mode B) and in the Phase 3.6 tests.
6. **Stage generation has no authoring-quality scaffold.** Each stage skill is structured doc generation; `doc-coauthoring`'s "transfer context → iterate → verify it works for the reader" loop is a reusable pattern to tighten stage prompts (Mode B).
7. **Connector security is unowned.** Phases 4b/5b/6b introduce auth, secrets, and repo access. `security-review` (auth/input/secrets/endpoint checklist) and `security-scan` (audit `.claude` config) should gate those phases — `security-review` as a borrowed checklist (Mode B), `security-scan` on demand (Mode C). PM-OS's `guardrails.md` overlay is the natural home.
8. **New-skill consistency.** As the suite grows (handoff, triage, release skills), `skill-creator` keeps `SKILL.md` + `agents/openai.yaml` uniform across runtimes (Mode B, authoring-time only).

---

## E2 marketplace refresh — selected codebase-understanding patterns (2026-08-03)

### PM-provided repository review — pinned evidence

| Repository | Reviewed commit | License result | E2 decision |
|---|---|---|---|
| `affaan-m/ecc` | `0c1d7be9a750627fb2a6534c78a998cc46d03f9c` | Root MIT license | **Adapt patterns only.** Use `iterative-retrieval`'s bounded broad→evaluate→refine loop, `code-tour`'s verified file/line anchors, `architecture-decision-records`' evidence-backed decisions, and `loop-design-check`'s machine-decidable boundaries. Reject `.tour` or other writes inside the target and do not ship an ECC runtime dependency. |
| `obra/superpowers` | `44c9b2d6e889982ac18c27d05a19fefe335194e1` | Root MIT license | **Adapt process only.** E2's execution runbook incorporates tests-first red/green, root-cause-before-fix, minimal implementation, and fresh verification-before-completion. Do not import its runtime orchestration or human-review checkpoints as gated dependencies. |
| `ComposioHQ/awesome-claude-skills` | `be2a406907dbc61b73e6827ded415c96139d13a2` | No repository-wide license found; licenses are skill-specific | **Reject as an E2 code dependency.** `webapp-testing`'s reconnaissance-before-action idea is useful for later optional UI validation, but it starts servers/Playwright and therefore cannot participate in E2's read-only codebase scan. No content is copied without a separately verified skill license. |

**Security/write/network review:** the repositories were shallow-cloned only into a disposable `/tmp` directory for inspection. E2 adopts no executable, network call, install step, subprocess wrapper, or target-repository output from them. The production path remains the PM-OS-owned `pm-context-scan-codebase` skill plus deterministic local helpers. This also preserves Claude/Codex parity.

**PM-OS skills inspired by the review:** strengthen `pm-context-scan-codebase` with inventory → bounded focus → evidence-driven widening; add `/pm-enhance` for same-project lifecycle/baseline mechanics; and keep the tests-first building loop in `pm-os-e2-execution-runbook.md`. These are original PM-OS-owned contracts, not vendored marketplace skills.

### Primary candidate: `acquire-codebase-knowledge`

GitHub's Awesome Copilot catalog publishes an MIT-licensed skill with a deterministic Python scanner, 25+ language/manifest detection, CI/container/security/performance inventory, focus-area mode, evidence-only claims, explicit `[TODO]`/`[ASK USER]` gaps, monorepo handling, and generated-output exclusions. These are strong foundations for E2's **cheap whole-repo inventory → affected-slice/impact-cone scan**.

Adoption mode: review and pin a commit, preserve license/attribution, and adapt the scan/checkpoint patterns into PM-OS. The upstream workflow normally writes seven documents under the target's `docs/codebase/`; E2 must not do that. Its adapter runs against the read-only target and writes scan output only under the PM-OS project. The PM-OS-owned `00c` format remains the single gated output.

### Secondary candidate: `arch:doc-and-modernize` documentation mode

Useful patterns: repository-local-first evidence, file/line citations, explicit unverified facts, contradiction handling, and deeper analysis of complex subsystems. Its normal authoring workflow writes architecture documentation, so E2 may only reuse its pattern or run it against a disposable PM-OS-owned snapshot. Its modernization mode is out of scope.

### Regression-scope candidates

Community regression-scope skills can contribute checklists for changed files, dependency spread, risk ordering, and minimum retest suites. They are lower-trust than the GitHub-maintained candidates: E2.0 must verify license, source, prompts, scripts, write/network behavior, and cross-runtime portability before borrowing. Regardless of outcome, the approved PM regression boundary and PM-OS traceability checks remain authoritative.

### Rejected as baseline dependencies

- Marketplace agents that require a proprietary code-intelligence backend (for example CAST Imaging) may be useful optional enrichment if the organization already approves that service, but cannot be required for local-first E2.
- Tools that create an index, documentation, cache, build output, or configuration inside the target repo are rejected unless redirected to a PM-OS-owned snapshot/output directory and proven read-only against the target.
- No marketplace skill may weaken the stage-00 human approval gate, send code to an additional unapproved service, or create Claude/Codex behavior divergence.

---

## Part 3 — Headline recommendations (build-vs-borrow)

- **Don't build tracker connectors.** Phases 4b / 5a / 6b should sit on **Linear / Atlassian (Jira) / Intercom MCP servers** (Mode A). This deletes the single highest-effort, highest-risk roadmap stream (auth, sync, provenance) while preserving the dry-run → confirm → store-references-only policy.
- **Borrow process skills as content, not dependencies.** Test suite (`python-testing` / `tdd-workflow` / `eval-harness`), release readiness (`deployment-patterns` / `changelog-generator`), codebase understanding (`codebase-docs-alignment`), security (`security-review`) → lift their checklists into PM-OS's own portable skills (Mode B). Zero portability cost.
- **Two quick current-product wins:** (a) wire `deep-research` / `WebSearch` into discovery stages 01/02; (b) use `pdf` / `docx` to close the open `.docx`/`.pdf` intake gap and to enrich `/pm-handoff` exports.
- **Keep gated paths self-contained.** External skills / MCP are enrichment behind opt-in / confirm — never on a gated stage path — so Claude/Codex parity holds.

---

## Catalog reference

**Borrowable agent skills seen in this environment (selected):** `api-design`, `autonomous-loops`, `backend-patterns`, `brand-voice`, `changelog-generator`, `claude-api`, `codebase-docs-alignment`, `coding-standards`, `continuous-learning`, `cost-aware-llm-pipeline`, `customize-faqs`, `database-migrations`, `deep-research`, `deployment-patterns`, `doc-coauthoring`, `docker-patterns`, `docx`, `e2e-testing`, `eval-harness`, `frontend-design`, `frontend-patterns`, `git-workflow`, `llm-output-hardening`, `mcp-builder`, `pdf`, `postgres-patterns`, `pptx`, `python-patterns`, `python-testing`, `search-first`, `security-review`, `security-scan`, `skill-creator`, `tdd-workflow`, `verification-loop`, `webapp-testing`, `xlsx`; built-in commands `init`, `verify`, `code-review`, `simplify`, `review`, `run`, `docs-audit`. `repo-interview-prep` is deliberately excluded from E2.

**MCP connectors available:** Linear (full CRUD), Atlassian/Jira & Confluence, Figma, penpot, Notion, Google Drive / Gmail / Calendar, Asana, monday.com, HubSpot, Intercom, Box, Canva, Supabase, Vercel — plus built-in `WebSearch` / `WebFetch`.
