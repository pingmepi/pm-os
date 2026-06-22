# PM-OS Backlog

Tracked issues and fixes, surfaced during testing/rollout prep. Newest concerns first.
Status legend: 🔴 open · 🟡 partially fixed · 🟢 fixed (pending release).

---

## 1. 🟢 Edited-upstream re-approval gate is auto-answered by the agent (human-in-the-loop bypass)

**Severity:** P0 — undermines the core "PM approves every step" guarantee.
**Status:** **Fixed** (this change), pending release.

**Symptom:** A PM edits an already-approved upstream artifact (e.g. `00w` context wiki), then runs the next stage (`01`). The gate detects the edit and reports "edited after approval," but the stage **just runs** — the PM is never actually asked to re-approve.

**Root cause:** `hooks/pre-stage.py` correctly detects the drift and prints the `[1] Continue / [2] Re-approve / [3] Cancel` menu, then calls `read_edited_choice()`. That function only prompts a **human at a TTY**. Inside Claude Code/Codex the gate runs in a non-interactive shell (`stdin` is not a TTY), so instead of asking it exits with an error message that *literally tells the agent how to bypass it*: "Set `PM_OS_EDITED_UPSTREAM_CHOICE=continue` …". The agent reads that, sets the env var, re-runs, and the edit is **implicitly re-approved by the agent, not the PM**. Downstream stages cascade stale as a side effect.

**Evidence:** `hooks/pre-stage.py:25-57` (`read_edited_choice`, non-TTY branch) and `:151-199` (implicit-reapproval path). Confirmed live: `00w` edited → `01` run → telemetry shows `stage_edited_post_approval` immediately followed by `implicit_reapproval` with no human action.

**Proposed fix:** Decouple "genuinely unattended" runs from "interactive agent session." When an upstream is edited and there is no human TTY, the gate should **block** and the skill should **surface the choice to the PM in chat** ("`00w` changed since approval — re-approve it? `/pm-approve 00w`"), requiring an explicit human action. Reserve `PM_OS_EDITED_UPSTREAM_CHOICE` for true cron/CI use only; the gate's error message must stop instructing the agent to self-bypass.

**Fixed (this change):**
- `hooks/pre-stage.py` non-TTY branch no longer prints the `Set PM_OS_EDITED_UPSTREAM_CHOICE=continue` hint. It now **blocks** and routes the decision to the PM (`/pm-approve <NN>`), explicitly telling the agent to STOP and not re-approve on the PM's behalf. The env var is still honored *if already set* (CI/cron escape) but is no longer advertised to the agent.
- All 9 stage skills (`pm-stage-01…09/SKILL.md`) now carry an explicit instruction next to the gate: on an edited upstream, do **not** set the env var or self-approve — surface the changed stage to the PM and wait for `/pm-approve` or an explicit human go-ahead.
- Test renamed/updated: `tests/integration/test_stage_gates.py::test_non_tty_without_choice_routes_to_pm` asserts the block routes to `/pm-approve` and that `PM_OS_EDITED_UPSTREAM_CHOICE` is *not* present in stderr. `test_implicit_reapproval_continue` still verifies the CI escape works when the var is set. `docs/guides/testing.md` updated to match.

---

## 2. 🟡 Windows-friendly install + runtime

**Severity:** P1 — every Windows PM hits this; blocks Windows rollout.
**Status:** Partially fixed (see below); remainder open.

**Symptom (as observed):** On Windows, `python3` does not exist (Python installs as `python` / `py`). The `post-approve` hook failed with Windows error **9009 (command not recognized)** even though a `python3` shell alias was set up — because the alias does not propagate into Python `subprocess` calls. The failed hook left `.meta.yaml` upstream-hash bookkeeping inconsistent, producing false "edited"/"stale" flags on subsequent gate runs.

**Fixed now (this change):**
- The 3 internal `subprocess.run(["python3", …])` calls now use `sys.executable` so hooks run under the same interpreter that launched the script — fixes the 9009 cascade. `scripts/pm_approve.py:151`, `scripts/pm_context_import.py:247`, `scripts/pm_os_verify.py:157`.
- `install.sh` now resolves the interpreter (`python3` → `python` → `py -3`) and uses it throughout, so a Git-Bash install no longer hard-requires a literal `python3`.

**Still open:**
- **24 skill-inline `python3 …` invocations** in `skills/**/SKILL.md` (e.g. `PM_OS_STAGE=03 python3 ~/.pm-os/hooks/pre-stage.py`) still assume `python3` resolves *and* use bash-only `VAR=val cmd` env-prefix syntax — which breaks under **PowerShell** (the shell Claude Code used on the test machine).
- **Shell standardization decision needed:** require Git Bash on Windows (then only `python3` resolution remains — solvable via an installer-created shim) **vs.** make skills shell-portable + ship an `install.ps1`. Recommendation: **standardize on Git Bash + installer shim** (lowest blast radius; CC already prefers Git Bash on Windows).
- No `install.ps1` exists; `install.sh` is bash-only.

**Note:** Must be tested on a real Windows box — cannot be verified from macOS.

---

## 3. 🟢 Recursive folder import for context folders

**Severity:** P2 — silent incompleteness; PM could believe a folder was fully ingested when subfolders were missed.
**Status:** **Fixed** (this change), pending release.

**Symptom:** `/pm-context-import <folder>` did not reliably ingest files in **subfolders**. The skill never specified recursion, and the script registered one file at a time, so coverage of nested folders was left to the agent's discretion — inconsistent and silent.

**Fix:** `scripts/pm_context_import.py register` now accepts a folder and walks it **recursively**, registering every document file (`.md/.txt/.pdf/.docx/.doc/.rtf/.csv/…`) across all subfolders, skipping engine/OS cruft and non-document files, and printing a coverage summary (`Registered N file(s) across M folder(s)…`) plus the skipped list. `skills/pm-context-import/SKILL.md` Inputs + Step 1 updated to use folder recursion and surface coverage/skips as FYIs.

---

_Recorded 2026-06-20 during v0.5.6 rollout testing. Changes above land via the normal commit → push → `pm_os_update.py` path; they are inert until then._
