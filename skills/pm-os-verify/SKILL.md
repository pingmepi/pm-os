---
name: pm-os-verify
description: Verify the PM-OS installation is healthy for this runtime — config, shared lib, gate hooks, installed skills, and a deterministic gate self-test.
model_tier: utility
---

Run: python3 ~/.pm-os/scripts/pm_os_verify.py "$@"

Pass through all arguments verbatim (for example `--runtime claude` or
`--runtime codex`). Do not interpret, validate, or reformat them. If no runtime
is passed, the script checks all installed runtimes.

Report the script's output as-is. Do not summarize, restructure, or add
commentary beyond a one-line confirmation that the script ran. If the script
exits non-zero, surface the failing checks so the PM can re-run the installer
or updater for the affected runtime.
