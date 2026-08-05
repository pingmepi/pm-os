# PM-OS Pathway 2 HTML Replica Intake — Execution Plan

**Working name:** P2H — HTML Replica Intake  
**Status:** Planned; the E2 dependency is now unblocked (E2 merged in v1.5.0, PR #68)  
**Execution branch:** create `feat/pathway-2-html-replica-intake` from refreshed `main` only after E2 merges  
**Scope:** Pathway 2 intake when the PM has an HTML replica of the product but no codebase access  
**Canonical pathway:** `docs/plans/pm-os-entry-pathways-plan.md`  

## 1. Outcome

PM-OS can consume an HTML application replica as observable product and interaction evidence, reconstruct the product intent and scope that the replica cannot prove, and formalize the complete product through the normal Pathway 2 pipeline.

The replica is not treated as production code, a deployed system, a backend contract, or proof of technical architecture.

The pathway must:

- avoid asking the PM to restate screens, controls, visible copy, and interactions that the replica demonstrates reliably;
- distinguish observed evidence from interpretation and unknown production behavior;
- preserve the supplied replica and its provenance without silently rewriting it;
- operate safely when the HTML contains executable JavaScript or external dependencies;
- work without codebase access and without invoking the E2 code scanner;
- produce a complete product definition, not an enhancement delta;
- allow the same PM-OS project to use E2 later if codebase access becomes available.

## 2. Dependency and pathway boundaries

P2H starts only after E2 is merged and the full suite is green on the resulting `main`. This ordering is deliberate: the new pathway must be tested against E2's final same-project lifecycle and must not restore an earlier child-project or promotion model.

### P2H is Pathway 2

- No `/pm-enhance` activation.
- No `.enhancements/` cycle until a later, explicit E2 enhancement begins.
- No `00-codebase-understanding.md` (`00c`).
- No `pm-context-scan-codebase` invocation.
- No codebase inventory or claims about production implementation.
- No delta-only stages or handoff.
- No use of `/pm-promote`; release-tier promotion remains a separate Part-B concern.
- The normal stage-00 context wiki and understanding document remain the approval boundary.

### Later E2 bridge

If codebase access is granted later, the product stays in this same PM-OS project. The HTML replica remains immutable historical product evidence. A later `/pm-enhance` cycle captures its own approved-artifact and code baselines, builds `00c`, and compares the current implementation against the approved product definition without converting or moving the project.

## 3. Intended PM experience

```text
/pm-new <product> --entry prototype

/pm-context-import \
  --prototype ./replica/index.html \
  ./supporting-context

register + preserve source
        ↓
safe static inspection
        ↓
sandboxed behavioral observation, when available
        ↓
prototype evidence inventory + coverage report
        ↓
Pathway 2 gap interview
        ↓
backfill stages 01–03
        ↓
formalize/adopt stages 04–05
        ↓
normal stages 06–08 and optional 09
        ↓
/pm-check → /pm-handoff
```

`--prototype <file-or-directory>` is an explicit semantic input, not an alias for `--codebase` and not the same as adopting an authored `05-prototype-brief.md`. Auto-detection may help folder import, but ambiguous entry points must not be guessed.

## 4. Evidence contract

Every extracted claim must be classified as one of:

| Class | Meaning | Permitted use |
|---|---|---|
| `observed` | Directly supported by HTML structure, visible runtime state, or a captured transition | May ground screen, interaction, content, and visible-state requirements |
| `inferred` | A reasonable interpretation of observed evidence | Must be surfaced for confirmation before becoming binding product intent |
| `unknown` | Not represented or not verifiable in the replica | Must remain a known unknown or be answered by another source/interview |
| `conflicting` | Replica and another registered source disagree | Must be resolved explicitly; never choose silently |

The replica cannot, by itself, establish:

- production framework or architecture;
- API, event, database, or storage contracts;
- authentication, authorization, tenancy, or data-governance rules;
- whether a visible action succeeds against production systems;
- actual performance, security, observability, deployment, or operational behavior;
- business intent, target segment, success measures, prioritization, non-goals, or decision authority.

Every observed claim must cite a stable evidence locator: source path plus DOM selector/element fingerprint, or captured state/transition/screenshot ID. Inferences must cite the observations they derive from.

## 5. Persisted artifacts

The original input remains immutable and content-hashed. Derived understanding belongs in the existing context-wiki pack rather than a parallel product stage.

```text
.history/
  sources/<timestamp>-<source-id>/...

00-context/
  prototype/
    prototype-inventory.yaml
    interaction-map.md
    coverage-report.md
    evidence/
      SCR-001-default.png
      SCR-001-validation-error.png
      SCR-002-mobile.png
```

The exact paths must be frozen in Loop 0 against the context-pack conventions present after E2 merges. Regardless of final filenames, ownership is fixed:

- `.sources.yaml` owns source registration and hashes;
- the stage-00 context pack owns derived evidence and coverage;
- `00-context-wiki.md` indexes the relevant prototype evidence;
- `00-context-understanding.md` owns interpretations, conflicts, assumptions, and known unknowns;
- stages 01–05 own the approved product definition derived from all sources;
- the supplied HTML never becomes a competing status or approval source.

### Stage-05 companion policy

- A safe, deterministic, self-contained replica may be adopted as the stage-05 runnable companion.
- A multi-file replica is preserved as a bounded bundle with an entry-point and asset manifest.
- A replica that cannot be replayed safely or deterministically remains evidence; PM-OS generates a normalized `05-prototype-mockup.html` from the approved stage-04/05 definition.
- PM-OS never mutates the preserved original or silently claims that a normalized prototype is byte-identical to it.

## 6. Security and execution model

HTML is untrusted executable input. Inspection is static-first.

Static inspection is always available and must not execute scripts. Behavioral observation, when supported, runs in an isolated adapter with:

- external network access blocked by default;
- a temporary browser profile and PM-OS-owned temporary local server;
- no filesystem access outside the registered source bundle;
- downloads, popups, service workers, external navigation, and permission prompts blocked;
- fixed viewports, locale, clock, and randomness where practical;
- bounded action, depth, state, and time budgets;
- console failures, blocked requests, and incomplete states recorded as coverage evidence;
- no automatic dependency installation or remote asset download.

Browser automation is progressive enhancement, not a universal runtime prerequisite. If the supported crawler is unavailable, the import completes static analysis, marks runtime behavior unverified, and routes the residual questions into the interview. It must not pretend static parsing observed interactive behavior.

## 7. Updated behavior table

| Condition | Required behavior |
|---|---|
| Explicit self-contained `.html`/`.htm` | Register as `interactive_prototype`; preserve and inspect it |
| HTML found during folder import | Include it rather than silently skipping it |
| Multi-file replica with one clear entry point | Register the bounded bundle and its asset manifest |
| Multiple plausible entry points | Stop preflight and request explicit selection |
| Entry point outside the supplied root | Reject it |
| Path traversal or unsafe symlink | Reject the unsafe asset/bundle and emit a finding |
| Missing local assets | Continue where possible; record degraded evidence and affected states |
| External fonts, APIs, scripts, or assets | Block by default and record the dependency and affected coverage |
| Browser adapter unavailable | Complete static inspection; mark runtime states unverified |
| JavaScript error or timeout | Preserve the last safe state and emit a bounded coverage failure |
| Navigation attempts to leave the bundle | Block it and emit a security finding |
| Replica plus supporting sources | Merge evidence with source-level provenance and trust classification |
| Replica conflicts with a brief/PRD/design source | Record `conflicting`; resolve during understanding/interview |
| Visible UI fact already evidenced | Do not ask the PM to restate it |
| Backend/data/permission behavior not evidenced | Ask or preserve as an explicit unknown; never infer it |
| Existing PM-OS-generated prototype | Preserve existing generation, validation, and handoff behavior |
| Codebase supplied accidentally on prototype route | Require explicit route confirmation; do not silently invoke E2 |
| Codebase becomes available later | Start E2 in the same project; preserve prototype lineage |
| Large or cyclic SPA | Enforce budgets and publish exclusions/unvisited states |
| Responsive replica | Observe prescribed desktop/tablet/mobile viewports and report gaps |

## 8. Dependency-ordered autonomous building loops

Every loop uses the established PM-OS discipline:

```text
AIM
  → write focused tests first
  → run them and confirm the intended red failure
  → implement the smallest coherent change
  → run focused verification
  → run the scheduled broader regression gate
  → update this plan's task state
```

Implementation runs autonomously. There is no PM approval checkpoint between loops. Stop only for a genuine product decision not resolved by this plan, a security boundary that requires new authority, or a repeatedly failing external dependency. Normal approvals remain part of using a PM-OS project; they are not development-loop gates.

### Loop 0 — Freeze contracts against post-E2 main

**AIM:** prevent semantic drift before production changes.

- Re-read the merged E2 pathway, source registry, context-pack, stage-05, checking, and handoff contracts.
- Freeze CLI grammar, single-file/bundle rules, persisted filenames, evidence schema, limits, failure codes, and runtime fallback.
- Confirm no new `.meta.yaml` field is necessary. If one is required, add a schema-version bump, `migrate_meta()` backfill, and red-first migration tests.
- Add the P2H phase/cross-reference to the merged canonical entry-pathways plan and the real development-order tracker present on `main`.
- Record the static parser and browser adapter dependency policy.

**Pass:** contract tests describe the complete behavior table and fail only because P2H is unimplemented.

### Loop 1 — Registration and provenance

**AIM:** make HTML a first-class, safely preserved prototype source.

- Add `.html` and `.htm` classification as `interactive_prototype`.
- Add explicit `--prototype` registration for files and bundle roots.
- Resolve and validate the entry point without escaping the registered root.
- Build a deterministic asset manifest with source hashes, missing assets, external references, and exclusions.
- Preserve the original bytes and source provenance.

**Tests:** direct file, recursive discovery, uppercase suffix, bundle entry point, duplicate source, missing asset, traversal, symlink escape, ambiguous entry point, size/count limits, and no source mutation.

**Pass:** registration works mechanically without executing HTML and all existing document registration tests remain green.

### Loop 2 — Deterministic static understanding

**AIM:** extract useful interface evidence without executing untrusted code.

- Add a PM-OS-owned prototype scanner, separate from the codebase scanner.
- Extract document titles, landmarks, routes/links, forms, inputs, controls, dialogs, tables, visible states, labels, accessibility attributes, CSS breakpoints, inline event targets, and local/external dependencies.
- Generate deterministic element fingerprints and evidence locators.
- Identify screen candidates without assigning product meaning that the markup cannot support.

**Tests:** semantic HTML, div-heavy UI, forms, dialogs, hash routes, embedded CSS/JS, external assets, malformed HTML, duplicate IDs, inaccessible controls, and deterministic repeated scans.

**Pass:** identical input produces identical inventory; scripts were not executed; every observation has a locator.

### Loop 3 — Sandboxed behavioral observer

**AIM:** observe interactive states without granting the replica production or host access.

- Implement a constrained browser adapter behind a capability check.
- Serve only the registered bundle from a temporary PM-OS-owned location.
- Block network, downloads, popups, service workers, external navigation, clipboard, camera, microphone, geolocation, and host-file access.
- Explore safe controls under action/depth/state budgets.
- Capture state fingerprints, transitions, responsive screenshots, console failures, blocked requests, and termination reasons.
- Freeze volatile sources where supported and mark remaining nondeterminism.

**Tests:** safe navigation, modal open/close, validation error, SPA state, blocked fetch, blocked external link, infinite transition loop, timer-driven changes, viewport variants, crawler unavailable, timeout, and read-only source proof.

**Pass:** the observer cannot access external network or files, bounded crawls terminate deterministically, and absence of the adapter degrades honestly.

### Loop 4 — Evidence synthesis and context-wiki integration

**AIM:** turn raw scan output into PM-readable, traceable product evidence.

- Add `pm-context-scan-prototype` with equivalent Claude and Codex entrypoints.
- Produce the prototype inventory, interaction/state map, screenshots, and coverage report.
- Assign stable `SCR-###` candidates using deterministic fingerprints and controlled aliases.
- Label every claim `observed`, `inferred`, `unknown`, or `conflicting`.
- Feed the existing context wiki and understanding document without creating a new gated stage or second inventory.

**Tests:** stable IDs across unchanged runs, controlled ID preservation after non-structural copy edits, evidence citations, conflict preservation, missing coverage, and no `00c` creation.

**Pass:** the context pack tells the PM what was observed, how it was observed, and what remains unknown.

### Loop 5 — Coverage-aware Pathway 2 interview

**AIM:** ask only for missing product truth.

- Extend Pathway 2 question selection to consume prototype coverage.
- Suppress questions already answered by reliable observed evidence.
- Prioritize problem/why, target users, scope, success, business rules, permissions, data ownership, integrations, errors, accessibility, operations, non-goals, and decision authority.
- Ask whether the replica is intended as faithful, partial, or exploratory evidence and record the answer as PM-authored provenance.
- Preserve skips as known unknowns.

**Tests:** observed UI fact not re-asked, inferred behavior requires confirmation, backend behavior never inferred, supporting docs shrink the interview, conflicts are asked before ordinary gaps, and non-interactive skips remain visible.

**Pass:** the interview complements the replica rather than narrating it back to the PM.

### Loop 6 — Backfill and stage-04/05 adoption

**AIM:** create one coherent, complete-forward product definition.

- Backfill stages 01–03 from all registered evidence plus interview answers.
- Map observed screens, states, and transitions into stage 04 with stable traces.
- Produce stage 05 from the approved product/design definition while retaining the supplied replica's provenance.
- Adopt a safe runnable companion only when it passes the frozen bundle/security/contract rules; otherwise generate the normalized PM-OS companion.
- Keep assumptions and unverified production behaviors explicit.

**Tests:** screen-to-journey traces, interaction/state coverage, stable IDs, provenance, safe adoption, normalized fallback, conflict blocking, and no fabricated backend/technical requirements.

**Pass:** stages 01–05 form a complete product definition and clearly distinguish approved intent from replica evidence.

### Loop 7 — Contracts, consistency, and QA propagation

**AIM:** detect drift between the replica evidence and the formalized pipeline.

- Validate bundle integrity, evidence locators, screen anchors, transitions, accessible names, responsive coverage, and missing assets.
- Compare stage-04/05 behavior against the observed inventory.
- Require QA coverage for adopted screens, states, journeys, visible validation, and unresolved uncertainty.
- Add precise, stable finding codes with blocking severity only where proceeding would create false confidence or unsafe execution.
- Extend `/pm-check` without changing existing approval semantics.

**Tests:** orphan screen, dead anchor, unmapped transition, unexplained visible behavior, missing error/empty/loading QA, stale source hash, modified bundle, and legacy generated prototype.

**Pass:** contradictions and coverage gaps are reported with actionable evidence and no false backend claims.

### Loop 8 — Handoff

**AIM:** make the formalized prototype product usable by design, development, QA, and business audiences.

- Export the safe runnable prototype or normalized companion with its manifest.
- Include the appropriate screen/state links, evidence inventory, known limitations, and provenance references by audience.
- Verify all copied relative assets and hash links.
- Export the whole formalized product; do not apply E2 delta-only filtering.
- Keep Jira output grounded in approved requirements rather than raw DOM elements.

**Tests:** self-contained HTML, bundle export, generated fallback, audience folders, direct screen links, missing asset refusal/warning policy, and archive/path safety.

**Pass:** handoff is replayable where promised and transparent where it is not.

### Loop 9 — Migration and backward compatibility

**AIM:** introduce P2H without changing existing projects or generated prototypes.

- Preserve imports that do not contain HTML.
- Preserve existing `05-prototype-mockup.html` generation and validation.
- Read older `.sources.yaml` records safely.
- Add metadata migration only if Loop 0 proved a schema change unavoidable.
- Verify both runtimes through isolated installations; never modify `~/.pm-os` or synchronized skill directories by hand.

**Pass:** all pre-P2H behavior is green and old projects require no manual edits.

### Loop 10 — E2 bridge and same-project lifecycle

**AIM:** prove P2H and E2 coexist without identity or provenance drift.

- Complete a prototype-only product through approval and handoff.
- Grant a separate test codebase later and start E2 in the same PM-OS project.
- Confirm the prototype remains historical evidence, E2 creates/refreshes `00c`, and the enhancement baseline uses the current approved product artifacts.
- Confirm no child project, project-type flip, or `/pm-promote` operation occurs.

**Pass:** the later enhancement is an ordinary E2 cycle in the same project and prior prototype provenance remains intact.

### Loop 11 — End-to-end dogfood and release gate

**AIM:** prove the pathway against representative real shapes.

Dogfood at least:

1. one self-contained HTML replica;
2. one multi-file replica with local assets;
3. one client-side SPA with several states;
4. one replica dependent on unavailable external services;
5. one incomplete or contradictory replica plus supporting documents;
6. one hostile/path-escaping fixture;
7. one responsive replica;
8. one static-only runtime without browser automation;
9. one later-E2 continuation in the same project;
10. equivalent Claude and Codex installed-harness runs.

Run focused tests after every loop, the intake/prototype/context/contract/handoff suites at loops 4, 7, and 9, and the complete repository suite at loops 3, 6, 9, and 11.

**Pass:** all focused suites, complete suite, isolated runtime verification, and dogfood cases pass with no writes to supplied source bundles.

## 9. Acceptance criteria

- [ ] `.html` and `.htm` are first-class `interactive_prototype` sources for direct and folder imports.
- [ ] An explicit prototype file or bounded bundle can be registered without codebase access.
- [ ] Original files are preserved byte-for-byte, content-hashed, and never modified.
- [ ] Entry-point ambiguity, traversal, unsafe symlinks, and out-of-root assets fail safely.
- [ ] Static inspection executes no replica script and works without browser automation.
- [ ] Behavioral observation, when available, blocks external network and unrelated host-file access.
- [ ] Every observed claim traces to a source locator or captured runtime state.
- [ ] Every conclusion is classified `observed`, `inferred`, `unknown`, or `conflicting`.
- [ ] PM-OS makes no production backend, architecture, security, or operational claim from HTML alone.
- [ ] The context wiki contains a lightweight prototype inventory, coverage, exclusions, and confidence; no `00c` or parallel product stage is created.
- [ ] The interview does not repeat reliable visible facts and does ask for load-bearing intent/production gaps.
- [ ] Supporting sources reduce the interview and conflicting sources trigger explicit resolution.
- [ ] Stages 01–03 backfill from combined evidence and PM answers; stages 04–05 preserve screen/state/interaction provenance.
- [ ] A safe runnable replica can be adopted; unsafe or non-replayable input produces an honest normalized fallback.
- [ ] QA maps adopted journeys, screens, states, visible validation, and known gaps.
- [ ] `/pm-check` detects stale source hashes, evidence drift, trace gaps, and unsafe/incomplete replay claims.
- [ ] `/pm-handoff` exports the whole approved product with a working prototype/bundle or an explicit replay limitation.
- [ ] Existing generated-prototype, document-import, greenfield, and E2 behavior remains backward-compatible.
- [ ] A later E2 enhancement runs in the same PM-OS project and retains the HTML replica as historical evidence.
- [ ] Claude and Codex paths are equivalent.
- [ ] Full regression, isolated install-harness verification, and dogfood pass.

## 10. Explicit non-goals

- Treating prototype JavaScript as production codebase access.
- Reconstructing production architecture from client-side assets.
- Connecting the replica to real credentials, APIs, databases, or environments.
- Automatically downloading missing dependencies or external assets.
- Replacing E2's codebase inventory with prototype inspection.
- Creating a child enhancement project or a second approval/status lineage.
- Implementing requirement-tier promotion or the separate `mvp | v1 | v2 | later` plan.
- Turning raw DOM elements directly into Jira work items.
- Making browser automation mandatory for ordinary PM-OS operation.

## 11. Post-E2 start checklist

- [ ] Confirm `feat/e2-affected-slice-enhancement` is merged into `main`.
- [ ] Pull and verify clean, current `main`.
- [ ] Run the complete baseline suite and record the count.
- [ ] Create `feat/pathway-2-html-replica-intake` from that commit.
- [ ] Reconcile this plan against merged E2 filenames, schemas, and contracts.
- [ ] Add P2H to the canonical entry-pathways phase table and current development-order tracker.
- [ ] Execute Loop 0 before changing production code.

---

End of plan.
