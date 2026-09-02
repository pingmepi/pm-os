# PM-OS — Technical Optimisation & Knowledge-Layer Exploration

**Date:** 2026-08-20 · **Status:** OPEN EXPLORATION — not a decision, not a committed plan.
**Participants:** Karan (PM, Indegene) + Claude. Prompted by "can we integrate Graphiti/Obsidian? what problems would that solve — or something else that optimises how PM-OS works?"
**Standing caveat:** v1 deliberately optimised for *working*, not for *optimal*. Everything below is a possibility surfaced for discussion. Nothing here is scoped or committed unless §6 says so explicitly.
**Sibling doc:** `product-shape-and-flexibility-brainstorm.md` covers *product-shape* flexibility (multi-capability, graduation, surface bias). This doc covers the *technical/knowledge layer* underneath it. They share a golden rule (§0).

---

## 0. The through-line (read this first)

> **PM-OS already has a knowledge graph. It is derived, per-project, flat-file, thin on edge types, and it has no reader.**

`.traceability.yaml` (schema v5) is a real graph: typed nodes (`REQ`/`US`/`FR`, `TC`, `TSK`, `EPIC`, `SCR`), typed edges between them, and **four reserved-but-empty slots** (`tickets`, `bugs`, `code_refs`, `design_refs`) that were designed to reach into execution systems. It is rebuilt from approved artifacts by a pure-Python resolver, with no network and no database.

That single fact reframes the whole question. "Should we integrate a knowledge graph?" is the wrong framing — we have one. The real questions are four, and every option in this doc is one of them:

1. **Grow the edges** — more node/edge types in the graph we already have. (Cheap. No new technology.)
2. **Give the graph a reader** — it is currently machine-only; no human can see it. (Obsidian's actual pitch.)
3. **Route context by relevance** — two independent context systems fire *whole* into every stage. (The largest certain win.)
4. **Close the loop across projects** — every project starts cold; the central feedback repo is write-only in practice. (The hosted-graph pitch — §3.5.)

Graphify (§3) is interesting precisely because it lands on **three of the four** at once — codebase edges, a real viewer, and traversal instead of re-reading files.

And one **golden rule**, inherited from the product-shape brainstorm and re-earned here:

> **Files stay canonical. Every index is derived and disposable. Nothing new may gate.**

`.traceability.yaml` proved this contract works: it is safe to delete and regenerate, so a bug in it can never corrupt product state. Any graph, index, database, or embedding we add must accept the same contract. **Options that respect it are cheap and reversible; the one option that would violate it — putting gate-relevant state in an LLM-extracted database — is the only one that can actually break PM-OS.**

A second lens worth keeping:

> **The costs that matter in PM-OS are tokens and PM attention. They are not CPU.** Approve-latency (#6) is fixed and central sync is already backgrounded. "Optimisation" here almost never means "faster code."

---

## 1. What exists today (grounded inventory)

| Layer | Mechanism | Where | What it can't do |
|---|---|---|---|
| Project state | `.meta.yaml` + artifact frontmatter, kept in lockstep | `lib/project.py`, `pm_approve.py` | No cross-project view of any kind |
| Gating | status machine + body-only hashing + stale cascade | `hooks/pre-stage.py`, `lib/hashing.py` | — (this is the crown jewel; leave it alone) |
| **Link graph** | `.traceability.yaml` v5, derived + disposable | `lib/traceability.py` | No `REQ→REQ` deps, no interface/entity/event nodes, no cross-project edges; `bugs`/`code_refs`/`design_refs` reserved and **empty** |
| Context A (stable) | overlay: company/team/glossary/guardrails + per-stage packs | `lib/context.py`, `context.example/` | **No stage affinity** — every global block fires into every stage unfiltered |
| Context B (per-project) | `00-context/` pack: manifest, sources, views | `pm_context_import.py` | `stage_affinities` is **empty**, `views/` unpopulated → whole ~4.7k-token pack per stage (#9) |
| Evidence graph | claims/insights + `supports`/`contradicts`/`updates`/`depends_on` | **designed, NOT built** — adaptive-context-pack Phase 3 | n/a — a knowledge-graph spec sitting unimplemented |
| History | per-project local git, commit per approval | `lib/project_git.py` | Local only — **no off-machine copy** (#18, remote half) |
| Cross-project | `telemetry.jsonl` + `feedback.jsonl` pushed to a central git repo | `lib/git_sync.py` | Write-only in practice; **nothing reads it back**. The self-improvement loop that would is designed, unbuilt |
| Retrieval | **none** | — | No index, no search, no embeddings. Confirmed absent from `lib/`, `scripts/`, `hooks/`. (`embeddings.py` in the spec was designed and deliberately abandoned) |
| Human read surface | `/pm-status` (one project), HTML companions (stages 04/05 only), `/pm-handoff --package` | `pm_status.py`, `lib/html_render.py` | No portfolio view, no graph view, no way to *see* traceability |
| External systems | Atlassian MCP (Jira export), Figma MCP (validated, unbuilt) | `pm_handoff.py` | Nothing inbound; no GitHub, no analytics, no QA system |
| Quality signal | edit distance + optional agent-estimated `semantic_distance` + 1–5 PM rating | `lib/text_metrics.py`, `pm_feedback.py` | Measures **PM effort and PM opinion, not correctness** (#26) |

**Runtime footprint today:** Python 3.11+, `pyyaml`, `jinja2`. That's it. No service, no container, no network dependency in the core path. This is a real asset and the main thing any integration puts at risk.

---

## 2. Obsidian — a reader for the graph we already have

**What it is, in PM-OS terms:** a local-first markdown editor pointed at a folder. Point a vault at `~/pm-projects/` and you get backlinks, full-text search, a graph view, and Dataview/Bases queries over YAML frontmatter. **Zero code to try.**

### What it actually solves

1. **The missing read surface — including a portfolio view — today, with no code change.** Every artifact already carries `stage`, `project`, `status`, `approved_at`, `approved_by`, `content_hash` in frontmatter (`templates/artifact-frontmatter.yaml.j2`), and that frontmatter is a *maintained mirror* of `.meta.yaml`, not a decoration. A single Dataview table gives the cross-project status board PM-OS has never had — `/pm-status` is per-project by construction (`resolve_project()` walks up from CWD).
2. **A viewer for traceability.** The trace graph exists but no human can look at it. Obsidian's backlink graph *is* a trace viewer — if the stable IDs are links. **Don't put `[[REQ-001]]` in artifact bodies** (see risks); instead have `pm_trace.py` emit a derived `graph/` folder of one stub note per ID, wikilinked to its neighbours. Same derived-and-disposable contract as `.traceability.yaml`, and the graph view comes free.
3. **The off-machine half of #18.** Per-project git history is local-only. A synced vault (Obsidian Sync, or the vault in OneDrive/iCloud) covers the "no off-machine copy" gap without building anything — and gives mobile read access to approved artifacts, which a PM in a meeting actually wants.
4. **Reading the generated HTML companions and the handoff package in situ**, alongside the markdown, instead of hunting for files.

### What it does not solve

Nothing about generation quality, token cost, correctness, or cross-project reuse. **Obsidian is a window, not an engine.** It should be judged purely on "does the PM see more, for free" — and on that basis it is strong.

### Risks and gotchas (precise)

- **Editing is fine; auto-formatting is not.** Hashing is body-only (`hash_artifact_body`), so frontmatter plugins are *inert* by design — good. But any Linter/Prettier-style plugin that reformats **bodies** creates genuine hash drift on approved artifacts and triggers the drift dance (#7). Mitigation: exclude `~/pm-projects/` from format-on-save, or accept that drift → re-approval is correct behaviour.
- **Obsidian can't see dotfiles.** `.meta.yaml`, `.traceability.yaml`, `.sources.yaml` are invisible to it. Any dashboard must ride on artifact frontmatter — which is exactly why the frontmatter-mirror design pays off here.
- **Wikilinks inside artifact bodies would be a mistake.** They change the hashed body, and they would leak into Jira/handoff exports unless `lib/jira_markup.py` learns to strip them. Keep links in the derived `graph/` folder.
- **`.codebase/` clones and `.history/` snapshots** would flood the vault and the graph view. Needs vault-level exclusions.

**Verdict:** the cheapest item in this document and the only one that is a single-evening experiment with a real chance of daily use. Try it **read-only** first (no plugins that write), and let the Dataview portfolio board be the thing that either earns it or doesn't.

---

## 3. Graphify — a codebase graph that fits PM-OS's shape almost exactly

**What it is** (`graphify.net` / `Graphify-Labs/graphify`, MIT, PyPI package `graphifyy`, installed as an isolated tool via `uv`/`pipx`): a tool **and a skill** — invoked as `/graphify` inside Claude Code, Codex, Cursor and Gemini CLI — that turns a repository plus its docs, manifests, PDFs and images into a typed knowledge graph.

Mechanics that matter for us:

- **Code parsing is local, deterministic, and makes zero API calls** — ~37 tree-sitter grammars, AST-level.
- **Typed edges** — `calls`, `imports`, `inherits`, `mixes_in`, `uses`, `references`, `depends_on` — each tagged `EXTRACTED` / `INFERRED` / `AMBIGUOUS`. Package manifests (`pyproject.toml`, `go.mod`, `pom.xml`) become canonical hubs with `depends_on` edges.
- **NetworkX in memory; no database, no vector store.** Output is files: `graphify-out/graph.json`, an interactive `graph.html`, `GRAPH_REPORT.md`, `manifest.json`, and an optional `cache/`.
- **Query surfaces:** CLI (`query` / `path` / `explain`) and an **MCP server** exposing `query_graph`, `get_node`, `get_neighbors`, `shortest_path`, `list_prs`, `get_pr_impact`, `triage_prs`.
- Incremental re-extract (`--update`), respects `.gitignore` plus a `.graphifyignore`.
- **Doc/PDF/image extraction is the only part that needs an LLM**, via a configured backend (default detection order Gemini → Kimi → Claude → OpenAI → DeepSeek → Azure → Bedrock → **Ollama**, i.e. a fully local option exists).

### Why this is a much better fit than a hosted temporal graph

It is **a skill that emits derived files**, not a service that owns state. No database, no embedder, no container, no index to keep alive. Its output has exactly the contract §0 demands — derived, disposable, regenerable. **It respects the golden rule almost by construction**, which is the opposite of the Graphiti-style option (see §3.5).

It also touches three of the four questions at once: codebase edges (Q1), a real graph viewer via `graph.html` (Q2), and token-efficient traversal instead of re-reading files (Q4).

### The concrete target: enhancement-mode codebase understanding

This is not speculative. PM-OS already has this exact machine, and it is the weakest deterministic layer in the product.

| | PM-OS today | Graphify |
|---|---|---|
| Deterministic substrate | `scripts/pm_codebase_inventory.py` — inventory, keyword matches, dependency edges, exclusions, dynamic-boundary gaps | tree-sitter AST, ~37 languages |
| **Dependency-edge coverage** | **`.py`, `.ts`, `.tsx`, `.js`, `.jsx` only** (`pm_codebase_inventory.py:129-169`) | ~37 languages + manifest hubs |
| Impact cone | Agent judgment over that substrate, then verification reads | `shortest_path` / `get_neighbors` / `get_pr_impact` traversal |
| Evidence grading | Agent ranks direct / supporting / uncertain | `EXTRACTED` / `INFERRED` / `AMBIGUOUS` on every edge |
| Re-scan | Full re-scan each time | Incremental `--update` with cache |
| Ignore list | **None (backlog #45)** | `.graphifyignore` |
| Multi-repo | **Single `codebase_path` (backlog #44)** | A graph can span trees |

**The sharp version of this:** for a Java, C#, Go, Ruby or PHP client codebase, PM-OS's deterministic substrate produces **no dependency edges at all** — and the mandatory affected-slice gate on stages 01–09 rests on that substrate. Graphify closes a real coverage hole, not a nice-to-have.

Worth naming as a good sign: graphify's `EXTRACTED`/`INFERRED`/`AMBIGUOUS` tagging maps almost one-to-one onto the scan skill's existing *direct / supporting / uncertain* ranking. Two independently designed systems reaching the same distinction suggests the boundary is real.

### Two secondary uses

- **Graph PM-OS's own artifacts.** It parses `.md` with wikilink and markdown-link resolution, so pointing it at `~/pm-projects/` gives `graph.html` as the trace viewer §2 wanted, and cross-project traversal as a Q4 answer. Marginal value is lower here than on code — the product artifacts already have stable IDs and a resolver — but it is nearly free once the tool is installed.
- **Doc corpora at import.** It handles PDF/DOCX/XLSX/images, the same formats `pm-context-import` registers. **Honest caveat:** its edges are structural and referential, not epistemic — there is no `supports` / `contradicts`. So it is a source of *candidate* edges for the unbuilt evidence ledger, not a drop-in replacement for it. Don't oversell this one.

### Four integration constraints, precisely

1. **It writes into the tree it scans.** `graphify-out/` inside the repo, plus optional git hooks and a merge driver. The scan skill's contract is *strictly read-only* on the target — "do not write a wiki, index, cache, tour, configuration, generated output, or any other file inside it." Survivable, because `.codebase/` is PM-OS's own disposable clone and is already project-gitignored — but it must be an explicit decision, with output redirected outside the scanned tree where possible, and **never** `graphify hook install` on a client repo.
2. **Data egress is the compliance gate, and it has a good answer.** Code-only extraction makes **zero API calls**. Doc/PDF/image extraction sends descriptions (not raw source) to a configured backend. For client code under NDA or GxP: run code-only, or point it at Ollama. That is a materially better story than any hosted graph — but it needs a **stated policy**, not an assumption.
3. **Optional, with graceful degradation — the Atlassian-MCP pattern.** `uv tool install` is an isolated tool, not a PM-OS library import, so the `pyyaml` + `jinja2` footprint survives intact. But the **offline-install path** (vendored wheels) will not carry a uv tool with dozens of tree-sitter grammars, so PM-OS must behave exactly as today when graphify is absent — the same shape as "Jira connector if authorized, else offline CSV."
4. **Pre-v1 and fast-moving.** Active development on a `v8` branch at roughly a release a day, with a hosted platform in early access. Pin a version; if PM-OS ever *depends* on it, `pm_os_verify.py` has to check for it.

### Verdict

Unlike the hosted-graph option, this is a **near-term candidate with a specific target**, not a watch item. Do it as a **bake-off, not an adoption**: run both substrates over one real client codebase in a non-Python/JS language and compare the affected slice and impact cone. Cheap, decisive, and it produces evidence instead of a preference.

One number to treat as a claim rather than a fact: the project's headline is a large token reduction per query (~70×) from traversing a graph instead of re-reading files. That is exactly the quantity **token telemetry (#13) would measure** — so §4.1 is the prerequisite for believing it, and the bake-off is how you check it.

---

## 3.5 The other kind of graph — hosted / temporal (Graphiti and similar)

Worth keeping distinct, because it is a genuinely different option and a much larger commitment. Graphiti-style systems are temporal knowledge graphs for agent memory: episodes in, LLM-extracted entities and relations, bi-temporal edges, hybrid semantic + keyword + traversal retrieval — and they **require a graph database, an embedder, and an extraction LLM**.

- **Where it would fit:** the *cross-project / evidence* layer only. Bi-temporality maps onto the unbuilt evidence ledger's `updates` / `contradicts` and the missing decision record (#23) — "this decision superseded that one, in March, because X." Entity resolution surfaces the same requirement or regulatory decision recurring across projects. Neither is reachable today.
- **Where it must never go:** anything gate-relevant. Probabilistic, service-backed, DB-resident state cannot host requirements, statuses, hashes or approvals. Read-only advisory or nothing.
- **The cheaper 80% first:** (Tier 0) a `/pm-recall` skill — the agent already has grep, so search `~/pm-projects/*/0*-*.md` plus each project's `.traceability.yaml` and return cited excerpts; (Tier 1) a SQLite FTS5 index, stdlib, no service, rebuildable from files; (Tier 2) a graph DB, only if a recall test on Tier 0/1 provably fails on precision.
- **Decision rule:** its cost is **fixed**, its value **scales with corpus size**. At a handful of projects grep wins. Record it as a watch item with a trigger condition, not a build.

---

## 4. The higher-leverage optimisations nobody calls "an integration"

Honest assessment: these are better ROI than either integration above, and they are all designed already.

### 4.1 Context routing — the largest certain win

Two independent context systems both fire **whole** into **every** stage: the overlay's globals (unfiltered by design — it never got the adaptive treatment the wiki did) and the `00-context/` pack (~4.7k tokens, because `stage_affinities` is empty and `views/` was deferred). Every stage pays for every other stage's context. Worse, irrelevant context is not just expensive — **it dilutes attention and makes generations worse**, which is a quality argument, not only a cost one.

Both fixes are already specified: `stage_affinities` + per-stage views (#9), stage-affinity for overlay globals (brainstorm §5.6 #1). **Do token telemetry (#13) first** — right now the saving would be estimated, not proven, and #13 is the one measurement that makes any context work defensible. Also on the list: the overlay's seed-drift leak (§5.6 #2), where stale unfilled scaffolding silently enters every prompt as real content — a *correctness* bug hiding in the context layer.

### 4.2 Grow edges, not technology

The "graph project" with zero graph technology, all additive to a derived file:

- Typed **`REQ→REQ` dependency edges** (none exist today — the original design's only edge type was `REQ↔TC`).
- **`IF-###` interface nodes** for seams between capabilities — the brainstorm's §4 conclusion that *the missing primitive is edges, not modules*.
- **Backend primitives** (`API-###` / `SVC-###` / `ENTITY-###` / `EVT-###`) so a non-UI product has something to trace through the design layer instead of only reappearing as a TRD task (§4.5).
- Then **derive stage-09 roadmap sequencing from the dependency graph** instead of writing prose disconnected from requirements.

### 4.3 Fill the reserved slots (definition ↔ execution)

`.traceability.yaml` reserves `tickets`, `bugs`, `code_refs`, `design_refs`. Only `tickets` is populated (Jira). A GitHub MCP writing `code_refs` (REQ → PR/commit) closes the definition↔execution loop, is the roadmap's "external artifact graph" gap, and is the **prerequisite for the unbuilt QA-triage phase** — you cannot map a bug to a requirement and a code location without those edges. `design_refs` is the Figma slot, already de-risked empirically.

### 4.4 A portfolio rollup

Reading every `~/pm-projects/*/.meta.yaml` is trivial and gives the cross-project state view that doesn't exist. Worth noting: **Obsidian + Dataview delivers this with no Python at all** — a genuine argument for §2 over building a new command. (The names `/pm-metrics` and `/pm-insights` are already **reserved** by the self-improvement-loop plan; don't spend them here.)

### 4.5 Make quality measurable at all

The uncomfortable one (#26). Today "quality" is edit distance plus a 1–5 rating: *how much the PM changed it* and *whether the PM liked it*. A fluent, confident, wrong artifact the PM doesn't catch scores as high quality. Candidate directions — all designed, none built:

- **Decision records at approval** (#23) — what makes an edit distance *interpretable* ("changed because the constraint changed" vs "changed because it was wrong").
- **The consistency spine's generation self-check (A.4)** promoted to a real cross-artifact check — the design-spec-contradicts-PRD class of defect (#5) was caught by a human building a prototype, never by a metric.
- **A golden-project regression suite.** `prompt_version` is already in telemetry: the *versioning* exists, the *evals* don't. Change a stage prompt today and nothing tells you whether output got better or worse.
- **Explicitly not embeddings** — that path is recorded as designed and deliberately abandoned, and it would add a fresh false-confidence surface.

### 4.6 Not the bottleneck (say so, so it doesn't eat deck space)

Approve latency is fixed (#6), central sync is backgrounded with a portable lock, hashing is body-only and cheap, the overlay's compute cost is negligible. **There is no CPU problem to optimise.** Any "performance" slide should be about tokens and PM attention.

---

## 5. Comparison

Ranked by (value ÷ cost), with the golden-rule test applied.

| Option | Problem solved | Cost | Golden rule | Pays off |
|---|---|---:|---|---|
| Obsidian vault, read-only | No read surface; no portfolio view; off-machine copy (#18) | ~1 evening | ✅ pure reader | Immediately |
| Token telemetry (#13) | Every context decision is currently unmeasurable | Small | ✅ additive payload | Immediately (unblocks below) |
| **Graphify bake-off** (one non-Python/JS client repo) | Dependency edges exist for 5 file extensions; the affected-slice gate rests on that | Small — a tool install + one comparison | ✅ derived files, disposable | **Immediately, as evidence** |
| Context routing (#9 + overlay affinity) | Token cost **and** attention dilution | Medium, designed | ✅ | Every stage, every project |
| Overlay seed-drift fix (§5.6 #2) | Stale scaffolding entering prompts as fact | Small | ✅ | Silent correctness bug |
| Derived `graph/` folder for Obsidian | Traceability is machine-only, invisible | Small | ✅ derived + disposable | With Obsidian |
| **Graphify as optional `00c` substrate** | Non-JS/Python codebases; #44 multi-repo; #45 ignore list | Medium — optional-dep plumbing + read-only/egress policy | ✅ if output stays outside the scanned tree | When a real client codebase lands |
| Typed edges / `IF-` / backend nodes | Seams unspecified; backend has no design-layer anchor | Medium | ✅ additive to derived index | When a multi-capability or non-UI product lands |
| `code_refs` via GitHub MCP | Definition↔execution disconnected; blocks QA triage | Medium | ✅ | When dev/QA phases start |
| `/pm-recall` (grep-based) | Every project starts cold | Small | ✅ cites files | With ≥5 projects of corpus |
| SQLite FTS5 index | Same, with better precision | Medium | ✅ rebuildable | When grep precision fails |
| Decision records (#23) | Quality metrics uninterpretable | Medium | ⚠️ touches approval flow — design carefully | Compounds over time |
| Golden-project evals | Prompt changes are unvalidated | Medium–large | ✅ test-side only | Before any prompt-tuning push |
| **Hosted / temporal graph** (§3.5) | Cross-project + temporal evidence memory | **Large** (service, embedder, extraction, staleness) | ⚠️ only as read-only advisory; fatal if it gates | **Only at corpus scale** |

---

## 6. My read (a recommendation, not a decision)

- **Free this week:** token telemetry (#13) + an Obsidian vault pointed read-only at `~/pm-projects/` + the **graphify bake-off** on one non-Python/JS codebase. Three small moves that between them make the system *visible*, *measurable*, and honest about how thin the codebase substrate actually is.
- **Next, and highest value:** context routing (§4.1). Designed, bounded, improves cost *and* output quality, and #13 makes the win provable rather than argued.
- **Then, the real "graph" work:** grow edge types and fill the reserved slots (§4.2–4.3). This is where knowledge-graph value lands for the *product-artifact* half of the graph — the half graphify knows nothing about — and it needs **no graph technology at all**.
- **Conditional, on bake-off evidence:** graphify as the optional `00c` substrate (§3), behind an explicit read-only + egress policy and the absent-tool degradation path. The decision should follow the comparison, not precede it.
- **Watch, don't build:** the hosted/temporal graph (§3.5). Record the trigger condition — corpus scale plus a failed recall test on grep/FTS5 — so the call is data-driven later instead of taste-driven now.
- **The two things no integration fixes**, and that matter more than any of the above if the deck is about where PM-OS *goes*: a real correctness signal (#26 / §4.5), and the **regulatory/MLR gate plus multi-approver model** (#21, brainstorm §1) — arguably mandatory rather than optional for a life-sciences org, and untouched by every option here.

---

## 7. Open questions for the discussion

- Is the goal **PM experience** (see more, navigate better → Obsidian) or **system intelligence** (reuse across projects → recall/graph)? Different roadmaps; the deck probably has to pick a lead.
- **Build or borrow the codebase substrate?** `pm_codebase_inventory.py` is ours, small, deterministic, and covers five file extensions. Do we extend it, or accept an optional third-party tool as the substrate and keep ours as the fallback? Borrowing buys ~37 languages immediately and costs us control over the layer a mandatory gate depends on.
- **What is the standing egress policy for client code?** Code-only graphify extraction makes zero API calls, and Ollama is a fully local path — but this needs to be a written rule before a client codebase is scanned, not a per-run judgment call.
- **Is depending on a pre-v1 tool acceptable at all**, given PM-OS's strict install discipline and the offline-install path? The "optional with graceful degradation" shape makes it survivable; whether it's *desirable* is a call to make once.
- Would a PM actually *use* a graph view of `REQ→TC→TSK`, or is that engineer-pleasing and PM-irrelevant? The honest answer decides whether §2's item 2 is worth building.
- If a second reader surface (Obsidian) becomes the daily driver, does the CLI/skill surface start to rot — and is that acceptable, or does it fragment the product?
- Cross-project reuse hides a **governance** question: is a prior project's approved requirement a *reusable asset* or a *precedent to be re-decided*? Recall that quietly imports last project's decisions is a risk, not a feature.
- At Indegene specifically: does anything here beat regulatory gate + multi-approver on priority? (Same question §7 of the product-shape brainstorm left open — still unanswered.)
- Are we willing to accept **one** non-plain-file dependency, ever? If the answer is a firm no, Graphiti is closed permanently and §3 becomes a single deck line instead of a slide.

---

## 8. Grounding references

- `lib/traceability.py` — the existing graph: schema v5, node/edge types, and the reserved `tickets`/`bugs`/`code_refs`/`design_refs` slots.
- `scripts/pm_codebase_inventory.py:129-169` — the deterministic codebase substrate's import resolution: `.py`, `.ts`, `.tsx`, `.js`, `.jsx` only. `skills/pm-context-scan-codebase/SKILL.md` — the strictly-read-only contract on the target and the direct/supporting/uncertain evidence ranking. `lib/repo_fingerprint.py` — pinned repository identity.
- External: `graphify.net` and `github.com/Graphify-Labs/graphify` (MIT; PyPI `graphifyy`) — tree-sitter AST extraction, typed `EXTRACTED`/`INFERRED`/`AMBIGUOUS` edges, `graphify-out/` file outputs, MCP server (`query_graph`, `get_neighbors`, `shortest_path`, `get_pr_impact`), `.graphifyignore`.
- `lib/context.py` — overlay resolution, the no-op guarantee, and the unfiltered-globals gap. `context.example/` — the seed pack.
- `docs/plans/adaptive-context-intelligence-pack.md` — Phase 3 (evidence ledger + typed claim relations) and Phase 4 (adaptive views): the unbuilt knowledge-graph spec.
- `docs/roadmap/backlog.md` — #9 (whole-pack-per-stage), #13 (no token telemetry), #18 (no off-machine copy), #23 (no decision record), #26 (quality metrics measure effort/opinion), #27 (contracts detect vocabulary), #28 (single-tier scope).
- `docs/roadmap/product-shape-and-flexibility-brainstorm.md` — §4 (edges, not modules), §4.5 (surface bias / backend primitives), §5.6 (context-overlay review), §6 (recurring principles), §7 (open skepticism).
- `docs/plans/pm-os-self-improvement-loop-plan.md` — the cross-project loop that would read the central feedback repo; reserves `/pm-metrics`, `/pm-insights`.
- `docs/plans/pm-os-consistency-spine-plan.md` — A.1–A.4, including the generation self-check that §4.5 would promote.
- `templates/artifact-frontmatter.yaml.j2` — the frontmatter fields any Obsidian/Dataview dashboard would query.
- `lib/project_git.py` — per-project local git history (the local half of #18). `lib/git_sync.py` — central telemetry/feedback push.
- `install.sh:132-141` — the entire dependency footprint (`pyyaml`, `jinja2`) that any integration puts at risk.
