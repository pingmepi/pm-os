# PM-OS

PM-OS is a local-first Product Manager Operating System for turning a short business statement into structured product definition artifacts with human review at every stage.

It is built as a Claude Code skill suite plus small Python helpers. There is no web app or backend service: project state lives in Markdown, YAML, and JSONL files on the user's machine.

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

## Design Goals

- Keep Markdown as the source of truth for every product artifact.
- Keep the product manager in control at each stage boundary.
- Make generated artifacts reproducible, reviewable, and easy to edit.
- Track stage state, approvals, and generated hashes locally.
- Support both GenAI and non-GenAI products from the same stage skills, driven by the project's `genai_flag`.

## Repository Layout

```text
skills/      Claude Code skills for project commands and stage generation
scripts/     Python command wrappers for mechanical operations
lib/         Shared helpers for project state, hashing, config, and telemetry
hooks/       Stage gates and approval hooks
templates/   Markdown/YAML templates used by generated artifacts
```

## Basic Usage

Install or configure PM-OS:

```bash
./install.sh
```

Create a project:

```text
/pm-new <project-slug> "<business statement>"
```

Generate and approve stages:

```text
/pm-stage-01-brief
/pm-approve 01

/pm-stage-02-scope
/pm-approve 02

/pm-stage-03-prd
```

Inspect project state:

```text
/pm-status
```

Capture feedback on a stage:

```text
/pm-feedback 03
```

## Project Data

A generated PM-OS project stores its artifacts locally, typically under a project directory containing:

```text
.meta.yaml
00-business-statement.md
01-brief.md
02-scope.md
03-prd.md
...
telemetry.jsonl
feedback.jsonl
.history/
```

The `.meta.yaml` file tracks stage status, approvals, project configuration, and whether the product should receive GenAI-specific artifact sections.

## Safety Notes

PM-OS is intended for sanitized product-planning inputs. Do not put confidential customer data, PHI, PII, secrets, credentials, or proprietary material into prompts or artifacts unless your environment and policies explicitly allow it.

This README intentionally avoids internal names, private repository details, deployment targets, and user-specific configuration.

## Requirements

- Claude Code with local skill support
- Python 3.11+
- `pyyaml`

Configuration is managed by the PM-OS installer and stored locally in the PM-OS config file.
