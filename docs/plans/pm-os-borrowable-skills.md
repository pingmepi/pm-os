# PM-OS: Borrowable Skills & Connectors

**Status:** Analysis (no code changes). **Date:** 2026-06-18
**Purpose:** Identify which existing Claude Code / Codex agent skills and MCP connectors PM-OS can **borrow** instead of building from scratch — across both the current product and the roadmap in `PM-OS-CURRENT-STATE-REVIEW.md` §7 — and check the current skill suite against that catalog for gaps.

This is analysis only. Adopting any item still goes through the normal **commit → push → `pm_os_update.py`** path, and any MCP/external use must respect the **read-before-write, dry-run → confirm** sequencing principle already stated in §7.

---

## How "borrow" works here — three modes, governed by portability

PM-OS must behave identically on Claude Code and Codex (`CLAUDE.md`, Phase 1). Most agent skills in the environment are **Claude Code plugin skills** that may be absent on Codex, so "borrow" resolves to one of three modes, chosen per-case:

- **Mode A — MCP connector.** Use a running MCP server (Linear, Atlassian/Jira, Figma, Intercom…). Both Claude Code and Codex support MCP, so this is portable *and* removes the highest-effort, highest-risk roadmap work (auth, sync, provenance). Best for every external-integration phase.
- **Mode B — Pattern/content reuse.** Lift the checklist / structure / prompt of an existing skill into PM-OS's own portable `SKILL.md` (or `lib/`). Fully portable, no runtime dependency. Best for process skills (testing, security, release readiness, codebase understanding).
- **Mode C — Soft/optional runtime dependency.** Invoke the external skill if present, degrade gracefully if not. Use sparingly; **never on a gated path.** Any such use is a portability risk and must be flagged.

**Portability rule:** never put a Claude-only skill on a *gated* path. Gated stages stay self-contained Markdown + Python so Codex parity holds. External skills / MCP are enrichment, invoked behind opt-in / confirm.

**Today PM-OS borrows nothing externally** — there are no live Linear/Jira/Figma/MCP references anywhere in the repo; every such mention in `docs/` is "planned."

---

## Part 1 — Roadmap phase → borrowable capability

Phase titles key to `PM-OS-CURRENT-STATE-REVIEW.md` §7.

| Roadmap phase | Borrow | Capability / connector | Mode | Note |
|---|---|---|---|---|
| **3 — Brownfield / codebase understanding** | `codebase-docs-alignment` (drift audit), `repo-interview-prep` / `customize-faqs` (repo mining → understanding), built-in `init` (generates CLAUDE.md), the `Explore` agent | Pattern for the enhancement-mode `00-codebase-understanding` doc + a drift signal | **B** | Reuse the audit/mining *approach*; PM-OS keeps its own gated stage-00 artifact. |
| **3.5 — Traceability spine (`REQ-` / `TC-` IDs)** | *(little external)* | Internal data model | — | No good external borrow; build natively. |
| **3.6 — Automated test suite** | `python-testing` (pytest/fixtures/mocking/coverage), `tdd-workflow`, `eval-harness` (formal EDD), `verification-loop`, `llm-output-hardening` (guard LLM-output parsing in context-import/backfill) | Test-harness patterns + LLM-output guards | **B** | Partly already shipped (`tests/`, `pyproject.toml`, `docs/TESTING.md`). Borrow remaining patterns. |
| **4a — Local handoff packet** | `doc-coauthoring` (structured spec authoring); `docx` / `pdf` / `pptx` (export to Word/PDF/deck) | Authoring workflow + format export | **B** (authoring) / **C** (format) | Packet stays local Markdown; format skills only when the PM wants Word/deck. |
| **4b — One tracker, export-only** | **Linear MCP** (full issue/project/milestone CRUD) **or** **Atlassian MCP** (Jira) | The connector itself — *do not build* | **A** | Biggest build-vs-borrow win. Cross-runtime via MCP. Keep PM-OS's dry-run → confirm → store-IDs-only policy. |
| **4 — Design-system / Figma (planned later)** | **Figma MCP** (design-context read, code-connect, diagrams) or **penpot MCP** (OSS) | Design source links + design context into stage 04/05 | **A** | Auth-gated, optional. penpot is the open-source fallback. |
| **5a — Bug intake + classification** | **Linear / Atlassian MCP** (pull bugs); reuse stage-06 `TC-…` IDs | Bug ingestion (classification stays PM-OS prompt logic) | **A** (ingest) / **B** (classify) | Classification is judgment — keep it in PM-OS, not borrowed. |
| **5b — Code-area suggestion (quarantined)** | built-in `code-review` / `security-review`, `git-workflow` (recent-changes heuristic), `Explore` agent, `repo-interview-prep` mining | Repo-snapshot → candidate-files → fix-plan pattern | **B** + **C** | Matches the "cite evidence, label suggestion, opt-in" quarantine. No hard dependency on this path. |
| **6a — Release-readiness report** | `deployment-patterns` (production-readiness checklist), `changelog-generator` (release notes from commits), `git-workflow` | Readiness checklist + release-notes generation | **B** | `deployment-patterns`' checklist maps ~1:1 onto the readiness rollup; `changelog-generator` produces the notes. |
| **6b — Feedback intake + iteration** | **Intercom / HubSpot MCP** (support feedback); `deep-research` + built-in `WebSearch` (market/competitor/user signal) | Feedback ingestion (classification stays PM-OS) | **A** (ingest) / **B** (classify) | The "optional analytics/support connectors later" the phase already anticipates. |
| **Self-improvement loop** (`pm-os-self-improvement-loop-plan.md`) | `continuous-learning` (extract patterns from sessions → skills), `eval-harness` (formal session eval) | Telemetry → recommendation + artifact-quality eval | **B** | Directly overlaps the existing self-improvement plan. |
| **Gemini runtime** (deferred) | `skill-creator`, `mcp-builder` | Authoring consistency for new skills/connectors | **B** | `skill-creator` keeps new PM-OS skills uniform; `mcp-builder` only if a *custom* connector is ever needed beyond existing MCP. |

---

## Part 2 — Gap check: current skills vs the catalog ("did we miss anything?")

Cross-referencing the 11 stage skills + 10 utility skills against the available catalog surfaces capabilities PM-OS could already use but does not:

1. **Discovery research is ungrounded (stages 01/02).** `pm-stage-01-brief` and `-02-scope` generate purely from the business statement + context overlay — no external grounding. `deep-research` (firecrawl/exa) and built-in `WebSearch` could enrich discovery with market/competitor/user evidence (Mode B/C, opt-in). **Likely the biggest current-product miss.**
2. **`.docx` / `.pdf` intake conversion is an open Phase-2 "remaining" item.** The `pdf` and `docx` skills solve it directly for `/pm-context-import` (Mode C). Low effort, already-blocked work.
3. **Share/export is text-only.** `pm-share` emits plain text; PMs share decks/docs. `pptx` / `docx` / `pdf` would let `pm-share` export a stakeholder deck or Word doc (Mode C, on demand).
4. **PM-OS's own docs drift.** `codebase-docs-alignment` / the `docs-audit` skill could be a maintenance routine for PM-OS's own `docs/` and skill catalog — and doubles as the engine for the Phase-3 brownfield drift signal.
5. **LLM-output parsing is unguarded.** `pm_context_import.py` and backfill parse model output; `llm-output-hardening` patterns (null fields, malformed JSON, injection via extracted strings) belong in those Python paths (Mode B) and in the Phase 3.6 tests.
6. **Stage generation has no authoring-quality scaffold.** Each stage skill is structured doc generation; `doc-coauthoring`'s "transfer context → iterate → verify it works for the reader" loop is a reusable pattern to tighten stage prompts (Mode B).
7. **Connector security is unowned.** Phases 4b/5b/6b introduce auth, secrets, and repo access. `security-review` (auth/input/secrets/endpoint checklist) and `security-scan` (audit `.claude` config) should gate those phases — `security-review` as a borrowed checklist (Mode B), `security-scan` on demand (Mode C). PM-OS's `guardrails.md` overlay is the natural home.
8. **New-skill consistency.** As the suite grows (handoff, triage, release skills), `skill-creator` keeps `SKILL.md` + `agents/openai.yaml` uniform across runtimes (Mode B, authoring-time only).

---

## Part 3 — Headline recommendations (build-vs-borrow)

- **Don't build tracker connectors.** Phases 4b / 5a / 6b should sit on **Linear / Atlassian (Jira) / Intercom MCP servers** (Mode A). This deletes the single highest-effort, highest-risk roadmap stream (auth, sync, provenance) while preserving the dry-run → confirm → store-references-only policy.
- **Borrow process skills as content, not dependencies.** Test suite (`python-testing` / `tdd-workflow` / `eval-harness`), release readiness (`deployment-patterns` / `changelog-generator`), codebase understanding (`codebase-docs-alignment`), security (`security-review`) → lift their checklists into PM-OS's own portable skills (Mode B). Zero portability cost.
- **Two quick current-product wins:** (a) wire `deep-research` / `WebSearch` into discovery stages 01/02; (b) use `pdf` / `docx` to close the open `.docx`/`.pdf` intake gap and to enrich `pm-share` exports.
- **Keep gated paths self-contained.** External skills / MCP are enrichment behind opt-in / confirm — never on a gated stage path — so Claude/Codex parity holds.

---

## Catalog reference

**Borrowable agent skills seen in this environment (selected):** `api-design`, `autonomous-loops`, `backend-patterns`, `brand-voice`, `changelog-generator`, `claude-api`, `codebase-docs-alignment`, `coding-standards`, `continuous-learning`, `cost-aware-llm-pipeline`, `customize-faqs`, `database-migrations`, `deep-research`, `deployment-patterns`, `doc-coauthoring`, `docker-patterns`, `docx`, `e2e-testing`, `eval-harness`, `frontend-design`, `frontend-patterns`, `git-workflow`, `llm-output-hardening`, `mcp-builder`, `pdf`, `postgres-patterns`, `pptx`, `python-patterns`, `python-testing`, `repo-interview-prep`, `search-first`, `security-review`, `security-scan`, `skill-creator`, `tdd-workflow`, `verification-loop`, `webapp-testing`, `xlsx`; built-in commands `init`, `verify`, `code-review`, `simplify`, `review`, `run`, `docs-audit`.

**MCP connectors available:** Linear (full CRUD), Atlassian/Jira & Confluence, Figma, penpot, Notion, Google Drive / Gmail / Calendar, Asana, monday.com, HubSpot, Intercom, Box, Canva, Supabase, Vercel — plus built-in `WebSearch` / `WebFetch`.
