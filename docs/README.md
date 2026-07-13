# PM-OS docs

Documentation is organized by purpose:

| Folder | Contents |
|---|---|
| [`guides/`](guides/) | Operator how-to. [`sop.md`](guides/sop.md) — the standard operating procedure for running PM-OS. [`testing.md`](guides/testing.md) — the central test-suite reference (what every suite/test checks). |
| [`reference/`](reference/) | Canonical reference. [`pm-os-spec.md`](reference/pm-os-spec.md) — the build spec (partly aspirational; the code on `main` is the source of truth — see [`../ARCHITECTURE.md`](../ARCHITECTURE.md)). [`codebase-wiki-format.md`](reference/codebase-wiki-format.md) — proposed shareable codebase-wiki format, pending eng-lead review; not yet implemented. [`generated-doc-formats.md`](reference/generated-doc-formats.md) — the section-by-section format of every artifact PM-OS generates (00-group through stage 09). |
| [`roadmap/`](roadmap/) | Current state + forward planning. [`current-state-review.md`](roadmap/current-state-review.md) — the canonical state review and roadmap. [`backlog.md`](roadmap/backlog.md) — the active backlog. |
| [`plans/`](plans/) | Design & implementation plans (each carries its own status — implemented / in-progress / not-started). |
| [`archive/`](archive/) | Superseded historical documents, kept for provenance. |

Top-level docs that live at the repo root (by convention): [`../README.md`](../README.md), [`../ARCHITECTURE.md`](../ARCHITECTURE.md) (as-built architecture), [`../CHANGELOG.md`](../CHANGELOG.md), [`../AGENTS.md`](../AGENTS.md), and [`../CLAUDE.md`](../CLAUDE.md).
