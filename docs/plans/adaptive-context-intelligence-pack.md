# Adaptive Context Intelligence Pack

> Status: approved for implementation.

## Summary

Replace the current flat wiki synthesis with an adaptive, evidence-linked
context pack.

- Keep `00-context-wiki.md` as the concise PM-facing index and canonical project
  summary.
- Add gated research modules only when supported by the uploaded evidence.
- Use one structured evidence ledger to connect sources, claims, insights,
  contradictions, decisions, and downstream stages.
- Introduce a five-question maximum discovery interview for thin inputs.
- Preserve existing projects unless the PM explicitly runs
  `/pm-context-import --upgrade-pack` in Claude or invokes
  `$pm-context-import --upgrade-pack` in Codex.

> **Supersedes the earlier single-page wiki decision.** Prior intake guidance
> locked the context wiki as a single page, deferring any modular/compounding
> layout to a later phase. This pack realizes that later phase: intake still
> **builds once** (no build-as-you-go yet), but the output is now a modular pack
> rather than one flat file. The single-page constraint is intentionally lifted
> here; the build-once constraint is retained.

## Context Pack and Interfaces

- Preserve the existing `/pm-context-import <paths>` and
  `$pm-context-import <paths>` entrypoints.
- Add support for images, PPTX, and XLSX alongside current text, PDF, DOCX, and
  CSV inputs. Unreadable or lossy material remains registered but cannot
  silently support claims.
- Add `--upgrade-pack` to rebuild an existing single-file wiki from its
  registered sources. The rebuilt `00w` and `00u` remain drafts pending
  approval.
- Produce:
  - `00-context-wiki.md`: TL;DR, locked decisions, non-goals, constraints,
    strongest insights, uncertainties, and module navigation.
  - `00-context/manifest.yaml`: active modules, stage affinities, and hashes.
  - `00-context/evidence.yaml`: structured claims, insights, source locators,
    confidence, and relationships.
  - `00-context/sources.md`: source inventory, inferred metadata, extraction
    quality, authority, strengths, and limitations.
  - Adaptive Markdown views under `00-context/views/`.
- Extend `.sources.yaml` with inferred document role, modality,
  author/organization, document date, authority, extraction quality, and
  uncertainty. The PM confirms only uncertain or consequential metadata.
- Support claim relationships: `supports`, `contradicts`, `updates`, and
  `depends_on`. Preserve stable claim and insight IDs during regeneration when
  meaning has not changed. ID preservation is best-effort: when the agent cannot
  confidently map a regenerated claim onto a prior ID, it mints a new ID and
  records the prior ID as superseded rather than silently reusing it, so
  targeted PM annotations never bind to a claim whose meaning has drifted.
- Continue accepting existing `> **PM:**` annotations; additionally allow
  targeted annotations referencing a claim or insight ID.

## Import and Synthesis Workflow

- Inventory and classify every source before synthesis. A mixed folder may
  contain several inferred source roles instead of inheriting one folder-wide
  type.
- Extract each source independently, using type-specific analysis:
  - Market research: drivers, segments, trends, alternatives, and evidence
    limitations.
  - Reviews and voice-of-customer material: themes, counts and denominator,
    sentiment, affected segments or jobs-to-be-done, representative evidence,
    and sampling bias.
  - Competitor and UX evidence: journey comparison, interaction patterns,
    observed strengths and frictions, and potential whitespace, with visual
    locators.
  - Meeting notes: decisions, proposals, owners, dates, dependencies, and
    superseded decisions.
  - Product artifacts: requirements, scope boundaries, constraints,
    assumptions, and approval status.
- Reconcile the extractions in a separate pass that deduplicates claims,
  identifies corroboration and contradiction, and creates cross-source
  insights.
- Generate applicable views:
  - Market landscape.
  - Cross-source themes and evidence triangulation.
  - Voice-of-customer clusters.
  - Competitor and UX comparison.
  - Decision timeline and dependency map.
  - Opportunity map.
  - Insight-to-stage traceability.
- Each view uses compact Markdown tables. Relationship diagrams may supplement
  them but must have a text or table fallback.
- Treat opportunities and interpretations as synthesis, not approved
  requirements.

### Thin-context behavior

- Assess coverage across problem, users, pains and current behavior, desired
  outcomes, scope boundaries, constraints, and decision authority.
- If essential evidence is missing, ask no more than five questions ranked by
  downstream impact. The PM may explicitly skip them.
- Register answers as a PM-authored source so they remain traceable and
  reusable.
- Record skipped or unanswered questions as known unknowns; never convert them
  into silent assumptions.
- Allow one signed-off combined client document to supply multiple artifact
  roles, such as brief and scope, with the shared provenance disclosed in
  `00u`.
- Separate structural feasibility from content sufficiency. A stage-number
  combination may permit a backfill in principle, but it is only faithful when
  the actual source coverage supports every decision-bearing section.
  Otherwise it is lossy and remains draft.

## Approval, Hashing, and Compatibility

- Make stage `00w` a composite gated artifact. Its hash covers the wiki index
  body, the evidence ledger, the source inventory, and every active view —
  enumerated by the manifest.
- Add a generic stage-artifact hashing helper alongside the existing
  `hash_artifact_body`; ordinary stages retain their current body-hash behavior.
  The pre-stage gate and `pm_approve.py` dispatch on stage type: `00w` uses the
  composite helper, every other stage uses body hashing.
- Define the composite hash precisely so regeneration does not produce false
  drift:
  - Members are hashed in a **fixed, manifest-declared order**, not filesystem
    order. The member list and order are part of the manifest.
  - Markdown members (wiki index, `sources.md`, views) are hashed body-only with
    the existing frontmatter-strip + CRLF→LF normalization, reusing
    `hash_artifact_body` per member.
  - YAML members (`evidence.yaml`) are hashed over a **canonical serialization**
    (sorted keys, normalized list ordering by stable ID, comments and
    whitespace ignored), not the raw bytes, so cosmetic reformatting is inert.
  - The composite hash is computed over the ordered tuple of per-member hashes.
    The **manifest's own member-hash table is excluded** from the composite
    input to avoid the circularity of hashing a file that contains the hashes;
    the manifest's member *list and order* are covered, its recorded hashes are
    validated separately (see manifest safety).
- For composite artifacts, approval edit-distance metrics
  (`char_edit_distance`, `normalized_edit_distance`) are computed over the
  **wiki index body only** for now; ledger/view churn is out of scope for the
  drift metric until a per-member metric is designed. The composite hash, not
  the metric, is what gates drift.
- Reject missing, duplicate, unsafe, or hash-mismatched manifest members.
- Any authoritative pack-file edit marks `00w` edited and uses the existing
  reapproval and downstream-staleness behavior.
- Snapshot the complete active pack before regeneration and remove obsolete
  generated modules only after preserving them in history.
- Bump project metadata schema to v4 with optional context-pack metadata.
  Existing approved single-file wikis retain their current hashes and behavior.
- Downstream stage skills read:
  1. The wiki index and locked context.
  2. Manifest modules matching that stage's affinity.
  3. The evidence ledger only when deeper traceability or conflict inspection
     is needed.
- Downstream reading is **dual-mode**. When no manifest is present (legacy
  single-file wikis, and any pre-v4 project), stage skills fall back to reading
  `00-context-wiki.md` whole, exactly as today. Selective module reading is a
  pack-only optimization and must never be a precondition for a stage to run.
- Keep `00-context-understanding.md` as the pipeline contract covering source
  roles, interview gaps, adoption, content-aware backfills, unresolved
  conflicts, and approval consequences.
- Keep `00-codebase-understanding.md` unchanged and reference it rather than
  duplicating its contents.

## Phased Deployment Plan

Ship in dependency order. Each phase is independently mergeable, testable, and
reversible; nothing in an earlier phase assumes a later one exists. The whole
pack is not a single PR.

- **Phase 0 — Spec lock (no code).** Pin the composite-hash canonicalization
  (member order, YAML canonical form, manifest-circularity exclusion) and the
  `evidence.yaml` / `manifest.yaml` shapes. Prototype the hash helper against a
  fixture to confirm regeneration is drift-stable before committing the format.
- **Phase 1 — Registration + formats + richer source metadata.** Extend
  `DOC_EXTS` for images, PPTX, and XLSX; add inferred role/modality/author/date/
  authority/extraction-quality to `.sources.yaml`. Mostly `pm_context_import.py`;
  low risk, no gate or schema change. Lossy material is registered but flagged.
- **Phase 2 — Modular pack + composite hashing + safety + schema v4.** Introduce
  the `00-context/` layout, the generic composite-hash helper, manifest safety
  validation in the pre-stage gate, the v3→v4 idempotent migration, and the
  dual-mode downstream reader. Gated on Phase 0. Existing wikis stay on the flat
  path untouched; new packs use composite hashing with index-only distance
  metrics.
- **Phase 3 — Evidence ledger + claim relationships + stable IDs.** The
  highest-judgment, least-deterministic layer. Lands with its own validation for
  ID-preservation/supersession behavior; isolated so its instability cannot
  destabilize Phase 2's gate.
- **Phase 4 — Type-specific extraction + adaptive views.** Pure skill-side
  generation (market landscape, VoC clusters, competitor/UX, decision timeline,
  opportunity map, traceability). Views activate only when evidence supports
  them.
- **Phase 5 — Thin-context discovery interview.** Self-contained and orthogonal;
  may ship earlier if convenient. ≤5 ranked questions, skippable, answers
  registered as a PM-authored source, skips recorded as known unknowns.

The opt-in `--upgrade-pack` path becomes available once Phase 2 lands and gains
richer output as Phases 3–4 land. Cross-runtime (Claude/Codex) contract tests
run from Phase 1 onward.

## Test Plan

- Composite hashing: stable manifest-declared ordering and line endings;
  cosmetic YAML reformatting is inert; changes to any member detect drift;
  ordinary artifacts remain unchanged; approval distance metrics for `00w`
  cover the wiki index body only.
- Manifest safety: reject missing members, path traversal, duplicates, stale
  hashes, and unlisted authoritative modules.
- Registration: recursively preserve and classify images, PPTX, XLSX, CSV, PDF,
  DOCX, and text sources.
- Rich-corpus fixture: market report, competitor screenshots, G2 review data,
  and meeting notes produce the applicable views, corroboration links,
  conflicts, visual locators, and selective stage affinities.
- Thin-corpus fixture: a combined client brief and scope triggers at most five
  questions, records answers as evidence, exposes skipped gaps, and prevents
  unsupported faithful backfills.
- Lossy extraction: unreadable visual or tabular content is surfaced and cannot
  receive High confidence.
- Approval integration: editing a module after approval marks `00w` edited and
  blocks or stales downstream work through existing gates.
- Compatibility: existing single-file wiki projects remain untouched; opt-in
  upgrade produces drafts and preserves old wiki content and PM annotations in
  history.
- Cross-runtime contract tests ensure Claude and Codex receive equivalent
  extraction, review, and selective-reading instructions.

## Assumptions

- Do not encode provider-specific model IDs or add mandatory heavyweight Python
  dependencies.
- Runtime-native multimodal capabilities perform visual and Office analysis;
  unavailable capabilities degrade explicitly and may request an export. Where a
  runtime exposes existing document skills (`pdf`, `pptx`, `xlsx`), prefer them
  over assuming raw multimodal reading; the degrade-and-request-export path is
  expected to be exercised regularly across runtimes, not rarely.
- This plan and `docs/plans/context-intake-improvements.md` both touch the
  `pm-context-import` skill and `pm_context_import.py`; sequence them so they do
  not collide on the same files, with this pack's phases layered on top of the
  intake-quality work.
- Rich modules appear only when evidence supports them; sparse projects retain
  a concise pack.
- Approval remains explicit, and context import never approves drafts on the
  PM's behalf.
