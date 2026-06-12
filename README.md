# PM-OS

PM-OS is a local-first Product Manager Operating System for turning a short business statement into structured product definition artifacts with human review at every stage.

It is built as an agent skill suite for Claude Code and OpenAI Codex, plus small Python helpers. There is no web app or backend service: project state lives in Markdown, YAML, and JSONL files on the user's machine.

## What It Produces

PM-OS guides a product idea through a seven-stage pipeline:

1. Product brief
2. Scope
3. PRD
4. Design spec
5. Prototype brief
6. QA plan
7. Metrics plan

Each stage writes a Markdown artifact, waits for review, and only proceeds after explicit approval. Later stages use the approved upstream artifacts as their source of truth.

Approving the design spec and prototype brief also creates HTML companions: a design-spec preview for stage 04 and a lo-fi static prototype for stage 05.

## Design Goals

- Keep Markdown as the source of truth for every product artifact.
- Keep the product manager in control at each stage boundary.
- Make generated artifacts reproducible, reviewable, and easy to edit.
- Track stage state, approvals, and generated hashes locally.
- Support both GenAI and non-GenAI products from the same stage skills, driven by the project's `genai_flag`.

## Repository Layout

```text
skills/      Agent skills for project commands and stage generation
scripts/     Python command wrappers for mechanical operations
lib/         Shared helpers for project state, hashing, config, and telemetry
hooks/       Stage gates and approval hooks
templates/   Markdown/YAML templates used by generated artifacts
```

## Basic Usage

Install or configure PM-OS:

```bash
./install.sh --runtime claude
./install.sh --runtime codex
```

The `--runtime` argument is required so PM-OS installs skills into the correct
agent directory.

Create a project:

```text
Claude: /pm-new <project-slug> "<business statement>"
Codex:  $pm-new <project-slug> "<business statement>"
```

Generate and approve stages:

```text
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

## Requirements

- Claude Code or OpenAI Codex with local skill support
- Python 3.11+
- `pyyaml`

Configuration is managed by the PM-OS installer and stored locally in the PM-OS config file.

Claude installs skills into `~/.claude/skills/` and hooks into `~/.claude/hooks/`.
Codex installs skills into `~/.agents/skills/`; native Codex hooks are not required
for baseline PM-OS behavior.

Model policy is runtime-neutral. PM-OS stores `default_model_tier: standard` and
`deep_reasoning_stages: ["03", "06", "08"]` in local config instead of concrete
provider model ids. Claude users should run deep-reasoning stages on Opus or the
strongest available reasoning model. Codex users should run those stages on a
high/deep reasoning model.

Update an existing install for a specific runtime:

```bash
python3 ~/.pm-os/scripts/pm_os_update.py --runtime claude
python3 ~/.pm-os/scripts/pm_os_update.py --runtime codex
```
