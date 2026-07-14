---
name: pm-handoff
description: Generate a readable, decomposed handoff package (per-story files + reference docs) from the approved PM-OS pipeline.
model_tier: utility
---

# Role and goal

Generate a human-readable **handoff package** from the approved pipeline. Unlike the
dense canonical stage artifacts (written for the gate/hash/traceability machine), the
handoff is shaped for people: one self-contained file per user story in the team's
house format, plus an overview and reference docs. It is a **read-only projection** —
it never touches gate, hash, status, or staleness.

Run:

```bash
python3 ~/.pm-os/scripts/pm_handoff.py "$@"
```

Pass through all arguments verbatim (`--output <dir>`, `--html`). Do not interpret,
validate, or reformat them. Report the script's output as-is with a one-line
confirmation.

# What it produces

Into `handoff/` at the project root (or `--output <dir>`):
- `README.md` — index + reading guide + provenance.
- `00-overview.md` — Business Perspective (Who / What & Why / How) from the brief + scope.
- `epics/EPIC-01-mvp.md` — the story index.
- `stories/US-###-*.md` — one self-contained story per file (assembled by walking the
  traceability spine: US-### → its FR-###s → its UJ-### journey → its covering TC-###s).
- `reference/` — user journeys, QA scenarios, impact analysis, non-functional requirements.
- `wireframes/prototype.html` — the approved stage-05 prototype, if present.

# Critical: the package is derived, not canonical

- **Never edit files under `handoff/`.** They are regenerated wholesale on each run and
  are not tracked by the state machine — a hand-edit there is silent drift, not a change
  to the product. To change content, edit the canonical stage artifact (e.g. `03-prd.md`)
  and re-run this skill.
- Sections with no source content are printed as `— not captured in source —` rather than
  invented. Treat that list as a coverage checklist: it shows where the PRD/QA is thin
  relative to the house format. Surface it to the PM if prominent; do not fabricate.
- Requires at least an approved PRD (`03-prd.md`). If it is missing, the script exits with
  an error — stop and tell the PM to approve the PRD first.

# Report to the PM

After running, confirm the output location and remind the PM the package is read-only and
should be regenerated after any PRD/QA re-approval:

```
Handoff package written to handoff/.
Read-only projection — regenerate with /pm-handoff after approving PRD/QA changes.
```
