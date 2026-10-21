---
name: pm-check
description: Check a PM-OS project for internal consistency — meta/frontmatter sync, hash drift, upstream approval shape, telemetry chain integrity, schema shape, artifact presence, and TRD task-id consistency (unique/sequential TSK-### tracing to PRD requirements). With --release <path>, run the release check on any handoff folder or zip, PM-OS-built or hand-built. Read-only.
model_tier: utility
---

Run: python3 ~/.pm-os/scripts/pm_check.py "$@"

Pass through all arguments verbatim. Do not interpret, validate, or reformat
them.

Optional design gate:

```bash
python3 ~/.pm-os/scripts/pm_check.py --design
```

`--design` runs the normal read-only project consistency checks plus deterministic
validation of `design-in/ia.yaml` and `design-in/design-notes.md`: schema, journey
coverage, story/screen coverage, required states, field coverage, token/component
rationales, excluded-frame use, and returned open questions. When stage 04 is
approved, it also verifies handoff readiness from canonical artifacts: every UI
story has a screen, screens are not orphaned, default/state Figma links and state
triggers are present, generated dev/QA story joins match when a package exists,
and the screen map agrees with story coverage. Missing stage-05 HTML is
informational on this path. It never calls Figma and never writes project state.

Release check (any handoff folder, including one built by hand):

```bash
python3 ~/.pm-os/scripts/pm_check.py --release <folder-or-zip> [<folder-or-zip> ...] [--ignore-ids S,E] [--json]
python3 ~/.pm-os/scripts/pm_check.py --release        # inside a project: every handoff/<audience>/ folder
```

`--release` reads the folder the way the build team will and reports, per
finding, `file:line`, error or warning, and the exact fix:

- stories with no epic or no priority, or a priority still carrying Markdown;
- ids cited in prose that nothing in the folder defines (any prefix — `R-01`,
  `BR-12`, `S1-US-03`, not only PM-OS's own); a short form like `US-13` for the
  only defined `S1-US-13` is a warning, an ambiguous one is an error;
- relative links that don't resolve or that leave the package;
- files named in code under a folder the package ships, that it lacks;
- placeholders (`TODO`, `TBD`, `{{slot}}`, lorem ipsum) as errors, and disclosed
  gaps ("to be confirmed", "pending") as warnings;
- stale sources: a hand-built story whose `source: <doc> vX` is older than the
  `<doc>` in the folder, or a PM-OS file generated from an artifact that has
  changed or is no longer approved;
- PM-OS packages only, once the QA plan is approved: an exported story or
  requirement no `TC-###` covers.

It exits non-zero when there are errors. A `.zip` is read in place, never
unpacked into the project. `--ignore-ids` skips a prefix or an id the PM
confirms is a domain sample value rather than a reference (for example sentence
ids `S-001`); suggest it only after the PM confirms that, and prefer the fix the
report gives (putting sample values in `code`).

When relaying `--release` output, keep each finding's location and fix. If there
are many, group them by code and show the first few of each, then say how many
more there are and offer `--json` for the full list.

Report the script's output as-is. Do not summarize, restructure, or add
commentary beyond a one-line confirmation that the script ran. This command
never modifies project state — if it reports issues, point the PM at the
remediation command it prints for each one (for example `/pm-approve <NN>`);
do not attempt to fix anything on their behalf.
