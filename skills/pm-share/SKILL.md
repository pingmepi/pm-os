---
name: pm-share
description: Export approved PM-OS artifacts — a raw text dump of one or all stages, or (--package) a readable, decomposed handoff package.
model_tier: utility
---

# Role and goal

Export approved PM-OS artifacts in one of two modes. Both are **read-only
projections** of the canonical stage artifacts — neither touches gate, hash,
status, or staleness.

- **Raw mode (default).** A single stage or every approved/edited stage,
  concatenated verbatim — for a quick paste into email/Slack/a doc.
- **Package mode (`--package`).** A decomposed handoff package: one
  self-contained file per user story in the team's house format (data
  fields, key UI steps, per-step acceptance/corner-cases), plus an overview
  and reference docs — shaped for people, not the gate/hash machine. Assembled
  by walking the traceability spine: `US-### → its FR-###s → its UJ-### journey
  → its covering TC-###s`.

Run:

```bash
python3 ~/.pm-os/scripts/pm_share.py "$@"
```

Pass through all arguments verbatim (`<stage_id>`, `--output`, `--package`,
`--html`). Do not interpret, validate, or reformat them. Report the script's
output as-is with a one-line confirmation — except for the package-mode
guidance below, which you must still convey to the PM.

# Package mode specifics (`--package`)

Into `handoff/` at the project root (or `--output <dir>`):
- `README.md` — index + reading guide + provenance.
- `00-overview.md` — Business Perspective (Who / What & Why / How) from the brief + scope.
- `epics/EPIC-01-mvp.md` — the story index.
- `stories/US-###-*.md` — one self-contained story per file.
- `reference/` — user journeys, QA scenarios, impact analysis, non-functional requirements.
- `wireframes/prototype.html` — the approved stage-05 prototype, if present.
- `--html` also emits `handoff/index.html`.

**Critical: the package is derived, not canonical.**
- **Never edit files under `handoff/`.** They are regenerated wholesale on each
  run and are not tracked by the state machine — a hand-edit there is silent
  drift, not a change to the product. To change content, edit the canonical
  stage artifact (e.g. `03-prd.md`) and re-run `/pm-share --package`.
- Sections with no source content are printed as `— not captured in source —`
  rather than invented. Treat that list as a coverage checklist showing where
  the PRD/QA is thin relative to the house format. Surface it to the PM if
  prominent; do not fabricate.
- Requires at least an approved PRD (`03-prd.md`). If it is missing, the
  script exits with an error — stop and tell the PM to approve the PRD first.

After running in package mode, confirm the output location and remind the PM
the package is read-only and should be regenerated after any PRD/QA
re-approval — the script already prints this; relay it, don't paraphrase it away.
