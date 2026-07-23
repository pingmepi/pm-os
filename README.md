# PM-OS

PM-OS is a local-first, PM-led PDLC operating layer. It maintains one coherent thread from idea to ship — intake, product definition, design, dev handoff, QA, release readiness, and feedback — with the PM in control at every decision point.

It is built as an agent skill suite for Claude Code and OpenAI Codex, plus small Python helpers. There is no web app or backend service: project state lives in Markdown, YAML, and JSONL files on the user's machine.

## Contents

- [Decision Authority](#decision-authority)
- [What PM-OS Does](#what-pm-os-does)
- [Design Goals](#design-goals)
- [Repository Layout](#repository-layout)
- [Basic Usage](#basic-usage)
- [Project Data](#project-data)
- [Safety Notes](#safety-notes)
- [Testing](#testing)
- [Requirements](#requirements)

## Decision Authority

PM-OS is not the final decision-maker and is not an executor.

- **The PM decides:** scope, trade-offs, approvals, priority, and release calls.
- **PM-OS suggests, prepares, and validates:** it drafts artifacts, checks upstream consistency, recommends next actions, and coordinates lifecycle state.
- **Developers and QAs execute:** implementation and testing remain with the team.

No stage progresses without explicit PM approval.

## What PM-OS Does

**Current scope (v1):** PM-OS covers the product-definition phase — a gated pipeline from business statement to approved product artifacts:

1. Product brief
2. Scope
3. PRD
4. Design spec
5. Prototype brief
6. QA plan
7. Metrics plan
8. TRD *(optional technical capstone)*
9. Roadmap *(optional product capstone)*

Each stage writes a Markdown artifact, waits for review, and only proceeds after explicit PM approval. Later stages use the approved upstream artifacts as their source of truth. Approving the design spec and prototype brief also creates HTML companions: a design-spec preview for stage 04 and a lo-fi static prototype for stage 05.

The optional roadmap scopes the path from MVP to a deliverable product and future horizons. It can run after stages 01-07 are approved; if an approved TRD exists, the roadmap uses it as technical delivery context.

**Planned phases:** dev-phase support and dev handoff, QA bug triage, release readiness, and feedback ingestion will be added in later phases without replacing the product-definition pipeline.

## Design Goals

- Keep Markdown as the source of truth for every product artifact.
- Keep the PM in control at every decision point — PM-OS recommends, PM approves.
- Make generated artifacts reproducible, reviewable, and easy to edit.
- Track stage state, approvals, and artifact hashes locally; detect and surface upstream drift.
- Support both GenAI and non-GenAI products from the same stage skills, driven by the project's `genai_flag`.
- Run on each PM's own machine: no shared service, no backend, no central database.

## Repository Layout

```text
skills/      Agent skills for project commands and stage generation
scripts/     Python command wrappers for mechanical operations
lib/         Shared helpers for project state, hashing, config, and telemetry
hooks/       Stage gates and approval hooks
templates/   Markdown/YAML templates used by generated artifacts
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the as-built system diagrams (component
wiring, stage state machine, and the generate→approve sequence).

## Basic Usage

Install or configure PM-OS:

```bash
./install.sh --runtime claude
./install.sh --runtime codex
```

The `--runtime` argument is required so PM-OS installs skills into the correct
agent directory. For GitLab mirrors, offline zip installs, or IT/MDM deployments,
see **[`docs/guides/offline-install.md`](docs/guides/offline-install.md)**.

Create a project:

```text
Claude: /pm-new <project-slug> ["<business statement>"] --genai|--no-genai
Codex:  $pm-new <project-slug> ["<business statement>"] --genai|--no-genai
```

`pm-new` needs to know whether this is a GenAI/agentic product. In an
interactive shell it prompts; when run non-interactively (the usual case inside
an agent) pass `--genai` or `--no-genai` (or set `PM_OS_GENAI_FLAG`). The
business statement is optional — omit it to add it later. Projects are created
under the `projects_dir` from your config (default `~/pm-projects`).

Building an enhancement to an existing product? Point PM-OS at the codebase:

```text
Claude: /pm-new <project-slug> --mode enhancement --codebase <github-url-or-local-path>
Codex:  $pm-new <project-slug> --mode enhancement --codebase <github-url-or-local-path>
```

Then run `/pm-context-import`: PM-OS does a read-only scan of the codebase and
produces a gated codebase-understanding doc (`00c`) that grounds every
downstream stage on the existing system, so the brief and beyond cover the
enhancement delta rather than re-describing the whole product.

Already have context? If you walk in with material you've authored — research, a
brief, a scope doc, a PRD, design notes — seed the project from it instead of
generating from scratch:

```text
Claude: /pm-context-import <files-or-folder>
Codex:  $pm-context-import <files-or-folder>
```

PM-OS builds a context wiki and an understanding doc for you to review and
approve, then adopts the artifacts you authored and faithfully backfills the
upstream stages below them before handing back to the normal pipeline.

Day to day you'll also use `/pm-status` (project state), `/pm-check` (read-only
consistency check for a project), `/pm-feedback <NN>` (rate a
stage), `/pm-share` (export approved artifacts as raw text, or `--package` to build a
readable, decomposed handoff package of per-story files + reference docs under
`handoff/`), `/pm-handoff jira` (export the approved pipeline to Jira as
epics/stories/tasks via the Atlassian connector — dry-run → confirm → create, with
ticket keys recorded back into the traceability spine; add `--offline` to get a
`handoff/jira-import.csv` for Jira's own CSV importer instead, no connector needed), and `/pm-sync` (push every
project's telemetry/feedback to the team repo; `--verify` checks each hash chain).

Approve the business statement, then generate and approve stages. The business
statement is stage `00` — gated like any other stage, so approve it first:

```text
Claude: /pm-approve 00
Codex:  $pm-approve 00

Claude: /pm-stage-01-brief
Codex:  $pm-stage-01-brief
Claude: /pm-approve 01
Codex:  $pm-approve 01

Claude: /pm-stage-02-scope
Codex:  $pm-stage-02-scope
Claude: /pm-approve 02
Codex:  $pm-approve 02

Claude: /pm-stage-03-prd
Codex:  $pm-stage-03-prd
```

Inspect project state:

```text
Claude: /pm-status
Codex:  $pm-status
```

Capture feedback on a stage:

```text
Claude: /pm-feedback 03
Codex:  $pm-feedback 03
```

`pm-feedback` prompts for a rating and a note interactively. Run
non-interactively, pass `--rating 1-5` (or `--skip-rating`) and `--note "<text>"`
(or `--skip-note`), otherwise it will stop and ask you to supply them.

Verify the installation is healthy (config, shared lib, gate hooks, installed skills, gate self-test):

```text
Claude: /pm-os-verify
Codex:  $pm-os-verify
```

## Project Data

A generated PM-OS project stores its artifacts locally, typically under a project directory containing:

```text
.meta.yaml
00-business-statement.md
01-brief.md
02-scope.md
03-prd.md
04-design-spec.md
04-design-spec.html
05-prototype-brief.md
05-prototype-mockup.html
...
telemetry.jsonl
feedback.jsonl
.history/
```

The `.meta.yaml` file tracks stage status, approvals, project configuration, and whether the product should receive GenAI-specific artifact sections.

## Safety Notes

PM-OS is intended for sanitized product-planning inputs. Do not put confidential customer data, PHI, PII, secrets, credentials, or proprietary material into prompts or artifacts unless your environment and policies explicitly allow it.

By default, PM-OS is configured to push local telemetry and feedback artifacts to `https://github.com/pingmepi/pm-os-feedback.git`. Override this during setup if your team needs a private or organization-specific feedback repository.

## Testing

PM-OS has a pytest suite under `tests/` — run `python3 -m pytest`. It covers the `lib/`
helpers, the full project lifecycle, the gate/approval/staleness machine, skill &
documentation contracts, telemetry metrics, and failure recovery, and is fully isolated
from your real `~/.pm-os` install (temp-install fixtures). See **`docs/guides/testing.md`** for the
catalog of what every suite and test checks.

## Requirements

- Claude Code or OpenAI Codex with local skill support
- Python 3.11+
- `pyyaml`, `jinja2` (runtime); `pytest` to run the test suite

Configuration is managed by the PM-OS installer and stored locally in the PM-OS config file.

Claude installs skills into `~/.claude/skills/` and copies hooks into
`~/.claude/hooks/`. Codex installs skills into `~/.agents/skills/`.

The gate hooks **execute from `~/.pm-os/hooks/`** on both runtimes — `pre-stage.py`
is run by inline commands inside each stage skill, and `post-approve.py` is run by
`pm-approve`. The `~/.claude/hooks/` copy is not on that execution path (it is
reserved for any future native-hook registration), so Codex skipping it does not
reduce gate coverage. Approval, hash-drift, and staleness behavior are identical
across runtimes; `pm-os-verify` confirms this with a gate self-test.

Model policy is runtime-neutral. PM-OS stores `default_model_tier: standard` and
`deep_reasoning_stages: ["00w", "00u", "03", "04", "06", "08", "09"]` in local config instead of concrete
provider model ids. Claude users should run deep-reasoning stages on Opus or the
strongest available reasoning model. Codex users should run those stages on a
high/deep reasoning model.

Update an existing install for a specific runtime:

```bash
python3 ~/.pm-os/scripts/pm_os_update.py --runtime claude
python3 ~/.pm-os/scripts/pm_os_update.py --runtime codex
```
