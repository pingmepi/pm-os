# PM-OS External Design Authority Plan (PDLC v2)

**Status:** 🔵 **Design only — nothing built.** Recorded 2026-08-13 against v1.5.0. A **zero-engine-change route** (context overlay + `--note` steering + three prompts) is specified in §6 and can be piloted today; the engine work in §8 is unstarted and unscheduled.
**Author:** Karan (with Claude Code)
**Trigger:** the Adcept engineering run (§2) — a coding agent could not reliably reproduce UI or reach intermediate states from PM-authored design prose.
**Relationship to `pm-os-modes-delivery-and-handoff-plan.md` Part C:** that plan reserves `/pm-handoff figma` for **outbound** work (PM *pulls* tokens to ground stage 04; later *pushes* frames from the prototype brief). This plan is **inbound and different in kind**: a designer-authored artifact entering the pipeline as a gated upstream input, carrying decision authority. Do not conflate them, and do not spend the `figma` name on this without reading that section — §9 covers the collision.
**Supersedes in part:** the current stage-04 premise that the PM authors information architecture, screen inventory, component inventory and tokens from the PRD. Under this plan those four are external.
**Post-pilot execution plan:** `pm-os-external-design-authority-execution-plan.md` assumes the zero-engine-change pilot succeeded, then productizes the two-pass stage-04 architecture, inbound validation, designer payload, and developer/QA Figma-state handoff.
**Pilot-distribution note (2026-09-01):** the prompts actually shared with pilot participants used four steps, splitting the designer work into (1) a pre-build scaffold workflow with designer approval of the work order and file convention, and (2) a separate read-only export after the designer finished Figma. Appendix A below compresses those into one designer-side section; the post-pilot execution plan preserves the four-step shape as the implementation contract.

---

## 1. The organizing principle

Today's stage 04 does double duty: it is **both the instruction to design and the record of design**. That works only because no designer is in the loop — the PM invents IA, screens, components and tokens from the PRD, and design reviews a document whose decisions are already made.

PDLC v2 puts a designer *and* an existing design system upstream of all four. The PM can then no longer author them. The PM can only **constrain them beforehand** and **verify them afterward**.

> The PM owns what the product must do. The designer owns how it is expressed. Neither signs off on the other's work — but nothing reaches engineering until both have.

The consequence for the artifact: **stage 04 splits in time, not in stage id.** See §5 — this choice is what keeps the cost bounded.

## 2. Why: the Adcept findings

Engineering ran the full PDLC for Adcept against PM-OS outputs. The coding agent handled UX state logic and transitions well, but did not reproduce the UI reliably. Two distinct failures:

1. **Incomplete screen composition.** A field specified in the requirements never appeared on the generated screen. Context bloat is a likely contributor — the artifacts carry more prose than the agent can hold against any one screen. (Hypothesis, not diagnosis; the artifact-shape rework proceeds on it.)
2. **Unreachable intermediate states.** The agent could follow a transition described in prose but could not reliably reach the *rendered* state it produces. For a toast appearing on `SCR-005` after the user clicks button 1, it had to reconstruct the path to that state, and did so imperfectly.

The second failure is the sharper one and it is **not** a prose-quality problem. Understanding the rule is not the same as being able to render the moment, and only the second is what a developer or coding agent needs. Prose cannot fix it; an addressable frame can.

**Both failures are fixable at exactly two points in the round trip**, and this plan's two highest-value inventions come directly from them:

| Failure | Fix | Where it lands |
|---|---|---|
| Missed field | `### Data fields per requirement` in the brief → `data_fields` per screen in the designer's return → reconciled at ingest | §6 prompts 1, 2, 3 |
| Unreachable state | `### Required state inventory` in the brief → every state a real frame with its own `node_id` → carried into the `SCR-###` block as a deep link | §6 prompts 1, 2, 3 |

Neither exists in any shipped artifact contract. They are the reason this plan is worth building rather than just tolerating.

## 3. The four handoff boundaries

| # | Boundary | State at v1.5.0 |
|---|---|---|
| 0 | world → PM | ✅ Built — `/pm-context-import`, `/pm-context-scan-docs`, `/pm-context-scan-codebase`, `/pm-interview` |
| A | PM → designer | ⚠️ Exists, wrong payload — one table edit |
| B | designer → PM | 🔴 Nothing — no route, no landing zone, no external state |
| — | PM verifies | 🔴 Nothing — but `/pm-check` is the right shape |
| C | PM → dev/QA | ✅ Built — the `SCR-###` spine carries it |

PM-OS today has **one hard boundary and it is terminal and outbound**. All four audiences (`dev`, `design`, `qa`, `business`) are *consumers*; `handoff/` is a pure fan-out. PDLC v2 promotes design to a **contributor**, turning the fan-out into a loop — and the state machine is linear, hash-chained and single-editor by construction.

## 4. Verified constraints (do not re-derive these)

Checked against the code on `main` at v1.5.0. These are the expensive findings.

**Blocking:**
- `REQUIRED_SECTIONS["04"]` is hardcoded — 11 sections — in `lib/artifact_contracts.py:161`, and a missing section is an **ERROR** (`REQUIRED_SECTION_MISSING`) that fails `pm_validate_artifact.py 04 --mode strict`. **Therefore the context overlay must use `apply: augment`, never `override`.** An `override` overlay that drops sections cannot pass validation without engine work.

**Enabling (this is what makes the zero-change route possible):**
- `_validate_screens` in `lib/artifact_contracts.py:1145-1160` is **WARNING-only by design**, for backward compatibility with pre-contract-v3 specs. `SCREEN_IDS_MISSING` and `SCREEN_TRACE_MISSING` are warnings. **So a run-1 design spec whose IA declares no `SCR-###` passes strict validation.** That warning doubles as the only mechanical run-1/run-2 discriminator we have (§7).
- Each screen's **own block content is copied into the story files that touch it** (`scripts/pm_share.py:278`, `_screen_body`). So Figma deep links, state links and field lists placed inside an `SCR-###` block reach the developer with **no engine change**. This is the single most important mechanism in the plan.
- Story→screen coverage resolves **transitively** (`scripts/pm_share.py:517-522`): a screen serving `UJ-001`, which serves `US-001`, counts as covering `US-001`.
- `~/.pm-os/context/` is **gitignored user data and explicitly exempt** from the never-hand-modify rule (CLAUDE.md). Editing it never diverges `main` or blocks `pm_os_update.py`.
- The **state machine is content-agnostic.** `pm_approve.py`, `pm_snapshot.py`, hashing and the gates do not care how a body was produced. Running stage 04 twice is an ordinary regeneration.

**Gaps:**
- `AUDIENCE_CATEGORIES` (`scripts/pm_share.py:88`): `design` receives `design_spec_full`, `screen_map`, `wireframes`, `user_journeys`. It does **not** receive `stories` (`dev`/`qa` only), `prd_full` (`dev` only), `nfrs`, `epics`. The code comment marks most rows as "cheap to adjust later (one table edit)."
- `_REF_STAGE` scopes `design_spec_full` and `screen_map` to stage 04, which **degrades to a placeholder note when 04 is unapproved** (`skills/pm-handoff/SKILL.md:83-85`). So today's `handoff/design/` is a *post*-design projection; run it pre-design and the designer gets journeys plus two placeholders.
- `handoff/<audience>/` is `rmtree`'d wholesale on every regeneration (`scripts/pm_share.py:152`), guarded only by the `.pm-os-handoff` marker. The `handoff/` **root** is never wiped (`scripts/pm_share.py:124`). So there is no safe landing zone for inbound design artifacts inside an audience folder — and `handoff/` means *outbound* anyway.
- `.meta.yaml` hashes **file bodies**. A Figma file has no body. No `external_refs` concept exists, so design drift after approval is undetectable.
- `/pm-check` is internal-only (meta/frontmatter sync, hash drift, upstream approval shape, telemetry chain, schema shape, artifact presence, TRD task-id consistency). It has no notion of an external artifact — but its `TSK-###` → PRD tracing is the same class of check the design gate needs.
- **Precedent for external refs:** the Jira `record` step writing keys into `.traceability.yaml` `tickets: []` is the one existing case of external-system identity landing in project state. Reuse that shape for Figma `file_key` / `version` / `node_id`.

## 5. The design: split stage 04 in time, not in stage id

```
03 PRD approved
   └─► 04 run 1 — Design Brief (status: draft)
          constraints only; designer-owned sections carry a pending marker
          │  out: 03-prd.md + 04-design-spec.md
          ▼
       DESIGNER  (own agent, own Figma MCP, existing design system)
          │  in:  design-in/ia.yaml + design-notes.md
          ▼
       04 run 2 — ingest: mint SCR-###, cite tokens (status: draft)
          │
          ▼  verify → /pm-approve 04
       05 / 06 / 07 / 08 unchanged
```

**Why this shape and not new stages:**

- **One artifact, one hash, one approval.** Dev and QA build against a single approved as-built spec. No "which design doc is canonical."
- **Zero stage-order change, zero schema migration.** `STAGE_ORDER`, `_REF_STAGE`, `deep_reasoning_stages`, the artifact contract version, and stages 05–09 are untouched. Adding `04a`/`04b` as real stages would mean renumbering 05–09, migrating `schema_version` in `.meta.yaml`, and touching every downstream `SKILL.md`.
- **`awaiting-external` becomes unnecessary.** Run-1 output is genuinely an incomplete `draft`, so `/pm-status` showing "04: draft" while the designer works is honest, and the existing linear gate already blocks 05–08. This deletes the state-machine change that would otherwise be the hard part.
- **No new skill name.** Inbound is `/pm-stage-04-design-spec` re-run reading `design-in/`, so the Part C `figma` reservation is never stepped on.

Net: the only genuinely new state is recording the Figma reference — and §4 gives the precedent for that.

## 6. The zero-engine-change route (pilot this first)

All three prompts are in **Appendix A**. Nothing here modifies `lib/`, `scripts/`, `hooks/` or `skills/`.

| Step | Command | Engine change |
|---|---|---|
| PRD | `/pm-approve 03` | none |
| Design brief | `/pm-stage-04-design-spec` + prompt 1 → run 1, stays `draft` | none |
| To designer | send `03-prd.md` + `04-design-spec.md` (not via `--package`; see §4) | none |
| Designer works | their agent + Figma MCP + prompt 2 → `design-in/ia.yaml` | none |
| Ingest + verify | `/pm-stage-04-design-spec` + prompt 3 → run 2 | none |
| Approve | `/pm-approve 04` | none |
| Dev/QA handoff | `/pm-handoff --package` + prompt 3's phase C | none |

**Two levers, both sanctioned:**
1. **Persistent:** `~/.pm-os/context/stages/04-design-spec/format.md`, `apply: augment` (never `override` — §4). Gitignored user data; safe to edit in place.
2. **Per-project:** pass prompt 1 / prompt 3 as `--note` or conversational steering. Notes land in `generation_notes` frontmatter and the `stage_generated` telemetry payload, and the skill **offers to reuse prior notes on regeneration** — so they half-persist.

**Recommended pilot:** run one project on `--note` steering only. Once the wording and the `ia.yaml` shape survive a real design cycle, promote prompt 1 into the overlay. Do not write the designer-side skill until the format has survived that cycle.

**The handoff payload is one set, identical for dev and QA:** stories joined to screens, plus the linked Figma frames those screens point to. There is no separate QA package to keep in step.

## 7. What the zero-change route gives up

Roughly 85% of the design works with no engine change. The 15% lost is precisely the part that would touch the state machine.

| Lost | Convention substitute |
|---|---|
| `handoff/design/` payload is still wrong | Hand the designer `handoff/dev/` or `--raw 03` |
| No Figma drift detection after approval | Record `file_key` + `version` inside the approved spec body — then it is covered by `content_hash`, so a deliberate change at least leaves a trail |
| No first-class `/pm-check --design` gate | Prompt 3 phase A performs it conversationally; determinism lost, the check kept |
| **Nothing distinguishes run 1 from run 2 in code** | See below |

**The run-1/run-2 discriminator is prompt-level only.** There is no code path that knows which run it is. Three shipped mechanisms give audit and recovery, not enforcement:

- `generation_notes` frontmatter + `stage_generated` telemetry `notes` — a permanent record of which run was which
- `.history/` snapshot per write + `regeneration_count` — run 1's exact artifact is recoverable and diffable
- `SCREEN_IDS_MISSING` from `pm_validate_artifact.py 04 --mode warn` — **present in run 1, absent after ingest.** The closest thing to a mechanical check available

**Two footguns:**
- `apply: augment` means the skill **keeps its default output spec**, which instructs it to declare `SCR-###` screens. Prompt 1 must explicitly override that instruction or run 1 will invent screens.
- On run 2 the skill offers *"Previous draft used these notes… Reuse them?"* — **decline it**, or run 1's BRIEF-ONLY instruction carries forward and suppresses the ingest.
- `/pm-approve 04` will happily approve a run-1 artifact; approval does not inspect for placeholders. Check `--mode warn` for `SCREEN_IDS_MISSING` before approving.

## 8. If we build it: ordered engine work

Nothing below is started. Ordered by dependency and by value-per-cost.

**B1 — `design-in/ia.yaml` format, versioned.** No code. Schema in Appendix B. `ia_format_version: 1`, validated at ingest so a stale designer-side export fails loudly rather than obscurely. **The designer never assigns `SCR-###`** — PM-OS mints them keyed on `node_id`, so renaming a frame can never renumber the spine. Non-negotiable; it is the whole reason the ids are trustworthy.

**B2 — Boundary A payload (one table edit).** `AUDIENCE_CATEGORIES`: `design` gains `stories`, `prd_full`, `nfrs`. Cheapest real progress available.

**B3 — Stage 04 two-phase flags.** `--brief` / `--ingest` on `skills/pm-stage-04-design-spec/`, replacing prompt-level discrimination with an explicit mode. Fixes the §7 footguns properly. Update `agents/openai.yaml` too (runtime agnosticism).

**B4 — `/pm-check --design`.** Read-only structural validation over stable ids, same class as the existing `TSK-###` tracing: every `UJ-###` has a surface; every `US-###` resolves (direct or transitive, matching `pm_share.py:517-522`) or is declared screenless; every state in the brief's `Required state inventory` exists as a frame; every field in `Data fields per requirement` appears on a screen; `tokens.outside_system` empty or justified; every new component has a rationale; no orphan canonical frames. No Figma auth needed PM-side — it validates the returned YAML.

**B5 — External-ref record + drift.** `.traceability.yaml` gains a `design:` block (file key, version, node ids at approval), mirroring `tickets: []`. Then "Figma moved since 04 was approved" is a cheap follow-on.

**B6 — Designer-side portable skill.** **Last, and only after B1's format survives a real project.** Hard constraints: fully self-contained — no `sys.path.insert(~/.pm-os/lib)`, no `pre-stage.py`, no telemetry, no `config.yaml`. This would be PM-OS's **first portable skill**, a new category with a maintenance story separate from `pm_os_update.py`; opening that door should be deliberate. It must self-check against the brief before export (prompt 2 step 4) — without that it is just an exporter and not worth the distribution cost.

**Explicitly not doing:**
- No new stage numbers, no renumbering 05–09
- No `awaiting-external` status — `draft` already means this
- Designer never writes a stage artifact, never mints ids
- No touching stage 05 yet: it now generates from *cited real* tokens, which is an improvement for free. Part C's `/pm-handoff react` is its eventual successor.

## 9. Naming and reservations

Per the CLAUDE.md convention (grep `docs/plans/` before minting a name — the `/pm-share` → `/pm-handoff` collision cost a rebuild):

- **`/pm-handoff figma` is already reserved** in `pm-os-modes-delivery-and-handoff-plan.md` §9 for *outbound* pull/push. This plan is inbound. **Direction mismatch inside one reserved name** — decide deliberately whether inbound shares it or gets its own, and do not assume.
- The §5 design **avoids minting any new name** (inbound is a re-run of `/pm-stage-04-design-spec`). Prefer keeping it that way; a new name is a cost, not a feature.
- `design-in/` as a directory name is unreserved. Do **not** land inbound artifacts under `handoff/` — that directory means outbound, and its audience subfolders are wiped on regeneration (§4).

## 10. Open decisions

1. **Concurrent two-way drift.** The PM edits the PRD while the designer works. PM-OS's hash chain assumes one editor moving forward through a line; this is a loop with two authors. **Recommendation: freeze convention, not code, for v1** — because if 03 does change, prompt 3 phase A *fails* (journeys and stories will not reconcile against `ia.yaml`). That is correct behavior, and it means detection comes free.
2. **Is "Key UI steps" in the stage-03 story mini-spec product intent or pre-drawn layout?** The PRD already mandates *Key UI steps* — "the ordered user↔system interactions," per step, with system process, acceptance and corner cases — authored one stage *earlier* than the 04 split and well before any designer opens Figma. Either it is behavioral sequence the design must satisfy (legitimate, and useful to hand a designer), or it is the PM pre-drawing the interaction, in which case half of what the designer is for is already foreclosed. **This changes what stage 03 writes, not just what 04 does, and it is the one input the design needs before build.** My read of the field list (*System process*, *Acceptance (Done)*, *Exceptions*) is that it was written for the first meaning and will drift toward the second unless the brief explicitly says "steps are behavioral sequence, not layout."
3. **Does stage 05 survive?** Figma is now the prototype. 05 either dies, or becomes "generate from real design-system tokens + Code Connect mappings" — a different and more useful thing. Do not resolve this before B1–B4 ship.
4. **Should the §4 gaps become numbered backlog entries?** They are verified against code, which meets the `docs/roadmap/backlog.md` bar. Not filed yet — deliberately, to avoid numbering churn on a design that may change shape.

## 11. Companion artifacts

- **Management-facing note (PDLC v2):** published as a private artifact; local copy `pdlc-v2-proposal.html`. Covers the flow as a three-participant sequence diagram, the ownership table, what verification checks, what does not change, and three risks with mitigations. Aimed at approval, not implementation.
- **Adcept run findings:** §2 above is the canonical write-up.

---

## Appendix A — the three prompts

Paste-ready. Prompt 1 and 3 are PM-side steering on `/pm-stage-04-design-spec`; prompt 2 runs in the designer's own agent and assumes no PM-OS install.

### A.1 — PM, after PRD approval, before design (run 1)

```text
BRIEF-ONLY RUN. Design authority for this project is external — the designer owns
information architecture, screens, components, and tokens. Your job is to state
constraints, not make design decisions.

Override the default output spec where it conflicts with the following.

WRITE FULLY, from the approved PRD, scope and brief:
- Product UX Guardrails — declare the interaction model, the product mental model,
  approved user-facing vocabulary, prohibited/misleading patterns, and the rules
  separating screens, overlays and states.
- Design Principles.
- Input Behavior Reconciliation — carry forward every empty, missing, invalid,
  malformed, permission-denied and recovery behaviour from the PRD's Edge Cases and
  per-story edge cases. Name the required UI response, copy, focus behaviour and
  state transition for each. Name a real label, helper text or aria-label for every
  input; placeholder-only discoverability is not acceptable.
- UX Content Rules — terminology, CTA naming, status language, error copy.
- Responsive & Platform Behavior — or state the single fixed target explicitly.
- Accessibility Notes — keyboard, focus order, labels, contrast, error messaging,
  touch targets, screen-reader expectations, specific to these flows.

Inside Input Behavior Reconciliation, add a subsection `### Required state inventory`.
For every US-### and UJ-###, list every state that must exist as its own designed
frame — including transient ones. Cover at minimum: default, loading, empty, error,
invalid input, permission-denied, success confirmation, and every toast, banner or
inline message the PRD implies. Give each a name and the trigger that produces it.
A state that is not listed here will not be designed.

Also add `### Data fields per requirement` — for every US-### with a data surface,
list the fields the PRD says it touches, with mandatory/optional. This is the
checklist the returned design is reconciled against.

DO NOT WRITE, but keep the heading present with the exact line
`_Pending external design input — see design-in/ia.yaml._`:
Information Architecture · Journey-to-Flow Traceability · Key User Flows ·
Component Inventory · Typography · Color Tokens · Spacing Tokens · Iconography

Do not declare SCR-### screens. Do not name components, colours, type or spacing.
Do not describe screen layouts. If the PRD implies a surface, say what must be
possible there, not what it looks like.

Add to Product UX Guardrails: the design must be built on the existing design
system. Any new component is an explicit, justified addition.

Keep this document short. It is a constraint set, not a narrative — every sentence
the designer does not need is context the downstream coding agent has to carry.
```

### A.2 — Designer, after Figma is created, before handing back

```text
You are producing a machine-readable index of a finished Figma design so it can be
reconciled against approved product requirements. You are READ-ONLY: do not create,
edit, move or rename anything in Figma.

INPUTS
1. The Figma file (URL provided by me).
2. 04-design-spec.md — the design brief. Read `Product UX Guardrails`,
   `Input Behavior Reconciliation` (including `Required state inventory` and
   `Data fields per requirement`), `Accessibility Notes` and `UX Content Rules`.

STEP 1 — READ THE FILE
Use get_metadata for the frame tree, get_variable_defs for the tokens and variable
collections actually used, get_libraries / search_design_system to establish which
components come from the existing design system, and get_screenshot where a frame's
purpose is ambiguous. Ask me before guessing.

STEP 2 — DECIDE WHAT IS CANONICAL
Figma carries explorations, scratch frames and rejected directions. Decide which
frames are the real deliverable. List everything you exclude and why — do not
silently drop frames.

STEP 3 — WRITE design-in/ia.yaml  (schema: see Appendix B)

RULES
- Every state in the brief's `Required state inventory` must appear as a real frame
  or component variant with its own node_id. Transient states (toasts, banners,
  inline validation, confirmations) are first-class: a developer must be able to
  open that exact frame, not reconstruct the interaction to reach it.
- Do NOT assign SCR-### ids. Those are minted downstream, keyed to node_id.
- Report gaps; never invent to satisfy a check. An honest gap is useful; a fabricated
  entry is not.

STEP 4 — SELF-CHECK, and print the result as a table before I send this on
For each, report PASS or the specific gap:
  1. Every UJ-### in the brief has at least one screen.
  2. Every US-### maps to a screen — directly, or through a journey — or is listed
     as deliberately screenless with a reason.
  3. Every state in `Required state inventory` exists as a frame or variant.
  4. Every field in `Data fields per requirement` appears on at least one screen.
  5. `tokens.outside_system` is empty, or each entry is justified.
  6. Every `components.new` entry has a rationale.
  7. No canonical frame is missing from `screens`, and no excluded frame is
     load-bearing.

STEP 5 — WRITE design-notes.md
Short. What you decided and why, what you rejected, what the brief left ambiguous,
and anything the PM should know that the YAML cannot carry.

Then stop. Do not fix failing checks by editing the YAML — tell me, so I can decide
whether to change the design or push back on the brief.
```

### A.3 — PM, after the designer hands back (run 2 + handoff)

Decline the "reuse previous notes?" prompt (§7 footgun).

```text
INGEST RUN. design-in/ia.yaml and design-notes.md are present. Design decisions are
now settled and external — cite them, do not re-make them.

═══ PHASE A — VERIFY FIRST. Write nothing until this passes. ═══

Reconcile design-in/ia.yaml against the approved 03-prd.md and the run-1 brief
sections in 04-design-spec.md. Print a table of PASS / GAP for each:

  1. Every UJ-### in the PRD has at least one screen.
  2. Every US-### resolves to at least one screen — directly via `serves`, or
     transitively (a screen serves UJ-001, which serves US-001) — or is declared
     screenless with a reason.
  3. Every state in the brief's `Required state inventory` exists in ia.yaml with
     its own node_id.
  4. Every field in the brief's `Data fields per requirement` appears in some
     screen's `data_fields`.
  5. Every FR-###/REQ-### with a user-facing surface is served by a screen.
  6. tokens.outside_system is empty, or each entry is justified in design-notes.md.
  7. Every components.new entry has a rationale.
  8. No frame in excluded_frames is load-bearing for a requirement.
  9. Nothing in ia.yaml contradicts the run-1 Product UX Guardrails — no prohibited
     pattern, no vocabulary drift, no interaction-model violation.

If anything is a GAP: stop, report it, and tell me whether it looks like a design
gap or a brief that was wrong. Do not fill gaps yourself, and do not soften a check
to make it pass. Also surface anything in design-notes.md's open_questions.

═══ PHASE B — POPULATE 04-design-spec.md ═══

Preserve every run-1 section VERBATIM: Product UX Guardrails, Design Principles,
Input Behavior Reconciliation (including both subsections), UX Content Rules,
Responsive & Platform Behavior, Accessibility Notes. Do not rewrite or re-derive
them. Replace only the `_Pending external design input_` placeholders.

Mint SCR-### ids: sequential from SCR-001, one per screen in ia.yaml, assigned in
`flows` order where possible. Key each id to its Figma node_id and record that
mapping — on any future regeneration, the same node_id keeps the same SCR-###. Never
renumber. States never get their own SCR-###; they belong to their owning screen.

Information Architecture — hierarchy, entry points and navigation from ia.yaml's
`flows`, then the screen inventory in exactly this shape:

- **SCR-001 — Case queue**
  - Purpose: <one line, from ia.yaml>
  - Serves: US-001, FR-003, UJ-001
  - Figma: <node_url of the default frame>
  - Data fields: <from ia.yaml data_fields>
  - States:
    - default — <node_url>
    - empty (no cases assigned) — <node_url>
    - toast-saved (after Save on SCR-002) — <node_url>

`Serves:` must be its own line with bare ids — it is the only line read as the
trace, and a story with no resolvable screen renders as "not captured in source"
downstream. Every state line needs its trigger in parentheses and its own link, so
a developer opens the frame instead of reconstructing the interaction that produces
it.

Journey-to-Flow Traceability — map every UJ-### using ia.yaml `flows`: entry point,
ordered screens and states, happy-path completion, recovery paths, supporting ids.
Key User Flows — narrate each flow step by step against the same sequences: start
state, action, system response, branch, completion, requirement satisfied. Name the
specific state each step lands on.
Component Inventory — from ia.yaml `components`. Mark each reused or new; for new,
carry the rationale. List states and validation per component. Do not invent any.
Typography / Color Tokens / Spacing Tokens / Iconography — CITE the design system
from ia.yaml `tokens` and get_variable_defs values. Name the collection or library.
Author no new values. If the design system covers something you would otherwise
specify, say so and reference it rather than restating it.

Record the Figma file_key and version from ia.yaml near the top of Information
Architecture, so the approved spec states exactly which design version it reflects.

Then follow the skill's normal write sequence: compute the hash, write the artifact,
run pm_snapshot.py 04, run pm_validate_artifact.py 04 --mode strict, update
.meta.yaml, log stage_generated. Report any validation warnings. SCREEN_IDS_MISSING
must NOT appear — if it does, the SCR block format is wrong.

═══ STOP ═══

Print the Phase A table, a summary of what you populated, and any open questions.
Do not approve. I approve stage 04 myself.
```

Then, after `/pm-approve 04`:

```text
Prep the dev/QA handoff and verify the join actually resolved.

1. Run /pm-handoff --package. Both dev and QA read the same payload — stories joined
   to screens, with the Figma links carried inside each screen block.

2. Then verify, and report specifics rather than "looks fine":
   - No story file says "not captured in source" for screens. If any does, its
     Serves: trace is broken — fix the design spec, re-approve, regenerate.
   - reference/screen-map.md lists no uncovered story and no orphan screen.
   - Every screen entry in a story file carries its Figma link and its state links.
   - Every state from the brief's Required state inventory is reachable as a link
     from at least one story.

3. Do not generate stage 05 to satisfy the package. Figma is the prototype now; a
   missing prototype renders as an explicit note, which is correct.

4. Report what a developer picking up any single story file can now see: the
   requirement, the screens it touches, and the exact frame for each state.
```

---

## Appendix B — `design-in/ia.yaml` schema, v1

`states` and `data_fields` are the two Adcept fixes (§2) and are the reason this format exists rather than prose.

```yaml
ia_format_version: 1
figma:
  file_key: <key>
  file_url: <url>
  version: <version id or lastModified>
  design_system: [<library or collection names this builds on>]
screens:
  - name: <human name, as in Figma>
    node_id: "<id>"                       # PM-OS mints SCR-### keyed on this
    node_url: <deep link to the frame>
    purpose: <one line: what the user does here>
    serves: [US-###, FR-###, UJ-###]      # PRD ids this surface supports
    data_fields: [<field names visible on this screen>]
    components: [<component names used>]
    states:
      - name: default
        node_id: "<id>"
      - name: <empty | error | invalid-input | permission-denied | toast-saved | …>
        node_id: "<id>"
        trigger: <what produces this state>
        transient: true|false
flows:
  - journey: UJ-###
    sequence:
      - {screen: <name>, state: <state name>}
components:
  reused: [<from the design system>]
  new:
    - name: <name>
      node_id: "<id>"
      rationale: <why the system could not cover this>
tokens:
  outside_system: []        # any colour/type/spacing literal not from the design system
excluded_frames:
  - {name: <name>, node_id: "<id>", reason: <exploration | superseded | scratch>}
open_questions:
  - <anything unresolvable from the brief>
```
