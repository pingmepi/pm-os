# PM-OS context overlay

A **pluggable context layer** that mounts company/team and per-stage context on
top of the generic PM-OS engine. With no pack filled in, PM-OS behaves exactly as
today. With content filled in, every stage inherits global context and uses your
real formats/examples.

## This is the seed (`context.example/`)

This tree is the **seed template**, tracked in the repo. On install it is copied
to **`~/.pm-os/context/`** — the live overlay the engine actually reads. That live
copy is **user data**: it is gitignored, edited in place, and never overwritten by
`pm_os_update` (the updater only copies *new* seed files that are missing, so
added stage packs reach you without clobbering your edits).

> Because the live `~/.pm-os/context/` is gitignored, editing it does **not**
> diverge the install or fight `pm_os_update`'s fast-forward. It is the one place
> a PM edits inside `~/.pm-os` directly.

## How the engine reads it

- `lib/context.py` — `resolve_context(stage_id, project_root)` / `render_context(...)`
  merge the layers, apply precedence, and drop empty/TODO content so an unfilled
  pack is a no-op.
- Each stage `SKILL.md` runs a **"Load context overlay"** step that prints the
  resolved context and folds it into generation per the stage's `apply:` mode.
- `pm_os_verify` checks the manifest parses and warns on dangling file references.

## Layers

| Layer | Scope | Lives in |
|---|---|---|
| Global | All projects, all stages | `global/` |
| Stage pack | One stage, all projects | `stages/NN-*/` |
| Project override | One project | `<project>/context/` |

Precedence (high → low): **project > stage pack > global.**

## How to fill it in

Edit the files under `~/.pm-os/context/` (not this `context.example/` seed):

1. `global/*.md` — company, team, glossary, guardrails. Replace the `TODO`
   prompts with real content.
2. For each stage, edit `stages/NN-*/format.md` (your section structure /
   must-haves) and `stages/NN-*/example.md` (a real filled-in artifact used as a
   few-shot reference).
3. Each stage is registered in `context.yaml` under `stages:` with an `apply:`
   mode — `augment` (default; keep the skill's sections, fold yours in),
   `override` (your Required sections replace the default output spec), or
   `reference-only` (examples for tone/depth only).

All nine stages (01–09) are seeded. A stage whose `format.md`/`example.md` is
still all-`TODO` stays inert until you fill it in.
