# PM-OS context overlay

A **pluggable context layer** that mounts company/team and per-stage context on
top of the generic PM-OS engine. With no pack mounted, PM-OS behaves exactly as
today. With a pack mounted, every stage inherits global context and uses your
real formats/examples.

## Status: SKELETON ONLY

The engine does **not** read this directory yet. This is scaffolding so the
content is ready to mount. Wiring happens in Phase 1 (see "Next: Phase 1").

## Layers

| Layer | Scope | Lives in |
|---|---|---|
| Global | All projects, all stages | `global/` |
| Stage pack | One stage, all projects | `stages/NN-*/` |
| Project override (Phase 2) | One project | `<project>/context/` |

Precedence (high → low): **project > stage pack > global.**

## How to fill it in

1. `global/*.md` — company, team, glossary, guardrails. Replace the `TODO`
   prompts with real content.
2. For each stage you have a format for, edit `stages/NN-*/format.md` (your
   section structure / must-haves) and `stages/NN-*/example.md` (a real
   filled-in artifact used as a few-shot reference).
3. Register the stage in `context.yaml` under `stages:` with an `apply:` mode.
   Default is `augment` (keep the skill's sections, fold yours in).

Seeded stage packs: **04 design-spec, 06 qa-plan, 08 trd.** Add 01/02/03/05/07
by copying the same shape.

## Next: Phase 1 (not done — separate approval)

- `lib/context.py` — `resolve_context(stage_id, project_root)` merges manifests,
  applies precedence.
- `lib/context_cli.py` — prints resolved context; called by skills.
- A "Load context" step added to each of the 8 stage `SKILL.md` files.
- `pm_os_install.py` / `pm_os_update.py` treat an installed `context/` as user
  data (never overwrite); ship this tree as `context.example/` and copy on first
  install only.
- `pm_os_verify.py` — new check: manifest parses + referenced files exist.
