# Offline / GitLab-friendly install for PM-OS trials

**Status:** ✅ **Implemented** (shipped in v0.5.9, commit `81f64f1`). `install.sh` now supports `--source <zip-or-dir>` for offline/zip installs and a configurable `--repo` for GitLab mirrors, without breaking the existing GitHub default path. Auto-runs `pm_os_verify.py` after install. Covered by `tests/integration/test_offline_install.py` and documented in `docs/guides/offline-install.md`. Moved to `docs/archive/` 2026-07-15 (nothing left actionable) — retained for provenance.

## Context

PM-OS is installed by `install.sh`, which **`git clone`s from a hardcoded GitHub URL**
(`PM_OS_REPO=https://github.com/pingmepi/pm-os.git`, `install.sh:159`) and then copies
skills/hooks into the runtime dirs. We want teammates to **trial** PM-OS, but:

1. **GitHub/git is blocked** on the org network. GitLab is allowed for most people, but
   blocked for some. So we need (a) a configurable git remote so the GitLab-allowed majority
   can clone+update normally, and (b) a **fully offline path** (a shared zip) for the
   git-blocked minority.
2. **A stray pm-os source folder can confuse agents.** The repo root ships developer-facing
   `CLAUDE.md` + `AGENTS.md`. These are *directory-scoped* (only load when an agent runs with
   cwd inside the folder), so they don't corrupt a teammate's other projects — but the dev
   `CLAUDE.md` says *"NEVER hand-modify `~/.pm-os`"*, which directly contradicts what the
   offline installer does. If someone "asks Claude to install" from inside the folder, that
   rule fights the installer.

**Intended outcome:** three install paths from one `install.sh` — (1) GitLab remote (git,
updatable), (2) offline zip (`--source`, no network), (3) existing GitHub default — plus a
clean, self-disposing trial folder that won't hijack an agent.

Key facts confirmed in the codebase:
- `pm_os_update.py` is remote-agnostic: it follows the `origin` remote set at clone time and
  already **fails gracefully** (`scripts/pm_os_update.py:203-207`) when `~/.pm-os` has no
  `.git`. So a GitLab clone updates from GitLab with no code change, and an offline install
  just can't auto-update (re-run the installer to update).
- `pm_os_verify.py` does **not** require git — it passes on an offline install.
- The runtime only uses `~/.pm-os` (engine) + `~/.claude/skills` / `~/.agents/skills`. The
  source folder is disposable after install.
- `~/.pm-os/context/` (gitignored user data) and `~/.pm-os/config.yaml` must be **preserved**
  across a re-install.
- `install.sh` is **not** exercised by the pytest suite (the harness builds the temp install via
  `shutil.copytree` in `tests/conftest.py`), so offline-mode coverage is mainly end-to-end.

---

## Changes

### 1. `install.sh` — configurable remote, offline source, deps resilience

- **Configurable remote (GitLab):** honor `--repo <url>` and `PM_OS_REPO` env (default stays the
  GitHub URL). The clone block (`install.sh:153-159`) uses it. Because `pm_os_update.py` follows
  `origin`, a GitLab clone is automatically updatable — no update.py change needed.
- **Offline mode:** add `--source <dir>` and `PM_OS_SOURCE` env. When set, **skip all git**;
  populate `~/.pm-os` from the source tree, **preserving** `config.yaml` and `context/`:
  ```bash
  rsync -a --delete \
    --exclude='/.git/' --exclude='/context/' --exclude='/config.yaml' \
    "$SOURCE"/ "$INSTALL_DIR"/
  ```
  with a `cp -R` (per top-level item, skipping `context/`+`config.yaml`) fallback when `rsync`
  is absent. The existing skill/hook sync (`install.sh:170-189`) already reads from
  `$INSTALL_DIR/...`, so it works unchanged once the tree is in place.
- **Deps resilience (pip may also be blocked):** before `pip install pyyaml jinja2`
  (`install.sh ~145`), check `python -c "import yaml, jinja2"` and skip if present; else if
  `$SOURCE/vendor/` exists, `pip install --no-index --find-links "$SOURCE/vendor" pyyaml jinja2`;
  else try PyPI and, on failure, print a clear "bundle wheels with --with-wheels" message.
- **Closing message (offline mode):** "Installed from `<source>` into `~/.pm-os`. PM-OS runs from
  `~/.pm-os` + the runtime skills dir — you can delete `<source>`. To update later, re-run this
  installer with a newer copy."
- **Auto-run the verifier (all paths).** After config is written, replace the *manual*
  "Verify the install: /pm-os-verify" suggestion with an actual call:
  `$PY "$INSTALL_DIR/scripts/pm_os_verify.py" --runtime "$RUNTIME"`. Capture the exit code; on
  pass, print the success/next-steps message; on fail, print "Install verification FAILED — see
  the checks above" and `exit 1` so a broken install (e.g. missing `pyyaml` when pip was blocked)
  is caught immediately rather than surfacing later. Still print the manual `/pm-os-verify`
  command (it must be re-run after a session restart for skills to load into the agent).

### 2. Distribution packaging

- **`.gitattributes`** (new) using `export-ignore` so `git archive` produces a clean trial zip:
  ```
  CLAUDE.md   export-ignore
  AGENTS.md   export-ignore
  tests/      export-ignore
  .github/    export-ignore
  .gitattributes export-ignore
  ```
  (The untracked local `.claude/` is already excluded by `git archive`.) This is the fix for
  problem #2 — the trial folder and the installed `~/.pm-os` carry **no agent-instruction
  files**, so they can't hijack a teammate's Claude/Codex session even if the folder lingers.
- **`scripts/pm_os_package.sh`** (new, run by a maintainer who has git): builds the shareable
  artifact:
  ```bash
  git archive --format=zip --prefix=pm-os/ -o pm-os-offline.zip HEAD
  # with --with-wheels: pip download pyyaml jinja2 -d <stage>/pm-os/vendor && re-zip
  ```
  Produces `pm-os-offline.zip` containing `install.sh`, `lib/`, `scripts/`, `hooks/`, `skills/`,
  `templates/`, `context.example/`, `VERSION`, `README.md`, `docs/` (optionally `vendor/`).

### On the post-install success check — use `pm_os_verify.py`, don't add a new helper

`scripts/pm_os_verify.py` **already is** the "did everything install correctly" check, and it is
more thorough than a file-presence test: it imports every shared lib module (catches a missing
`pyyaml`/`jinja2`), validates `config.yaml`, confirms skills are installed in the runtime dir
(count vs source), and **runs the real gate and telemetry self-tests**. It needs no git/network,
so it passes on an offline install. The only thing missing is that `install.sh` doesn't *trigger*
it — that's the "Auto-run the verifier" bullet in change #1. No new helper is written.

### 3. Docs

- **`docs/guides/offline-install.md`** (new) — three flows:
  - *GitLab (most people):* push a GitLab mirror once; teammates run
    `bash install.sh --runtime claude --repo <gitlab-url> --pm-user <id> --feedback-repo <gitlab-feedback-url>`
    (feedback repo must also be GitLab, since the default is GitHub).
  - *Offline zip (git-blocked):* extract `pm-os-offline.zip`, then
    `bash pm-os/install.sh --runtime claude --source pm-os --pm-user <id>`, then delete the folder.
  - *Codex:* same with `--runtime codex` (skills → `~/.agents/skills`, no hooks).
  - "Ask Claude to install" note: run the install command **from outside** the extracted folder
    (point `--source` at it) so no stray `CLAUDE.md` is in cwd — and the zip omits it anyway.
- Add a short "Offline / GitLab install" pointer in `README.md`.

### 4. Test: end-to-end offline install (shell) — `tests/integration/test_offline_install.py` (new)

Keep the copy/preserve logic in `install.sh` (shell) and cover it by actually invoking the
script. Tests run `bash install.sh` with `HOME` pointed at a temp tree (same isolation pattern as
the `pmos` fixture). Use **`--runtime codex`** so no `claude` CLI is required and no bypass is
needed (`~/.pm-os/hooks` is still populated by the source copy, so the gate self-test in verify
still runs). `skipif` when `bash` or `git` is unavailable.

- `test_offline_source_install_populates_and_autoverifies` — `bash install.sh --runtime codex
  --source <repo-root> --pm-user trial`; assert exit 0, output contains the verifier's `PASS`,
  `~/.pm-os/{lib,scripts,hooks,skills,VERSION}` exist, and skills landed in `~/.agents/skills`.
- `test_offline_reinstall_preserves_user_data` — after install, drop a marker file in
  `~/.pm-os/context/` and a sentinel key in `~/.pm-os/config.yaml`, re-run the installer, assert
  both survive (the rsync/cp excludes worked).
- `test_package_excludes_dev_files` — run `scripts/pm_os_package.sh` (or `git archive` with the
  new `.gitattributes`) and assert the archive **omits** `CLAUDE.md`, `AGENTS.md`, `tests/`,
  `.github/` but **includes** `install.sh`, `lib/`, `skills/`.
- Catalog all three in `docs/guides/testing.md` (every test carries a docstring + entry).

Because the pip step uses an import-check first and `pyyaml`/`jinja2` are already present in the
test env, these tests need no network.

---

## Decision: CLAUDE.md / AGENTS.md excluded from the zip

The distribution zip **omits** `CLAUDE.md` and `AGENTS.md` (via `.gitattributes` export-ignore,
change #2). They're folder-scoped so they never touch a teammate's other projects, but the dev
`CLAUDE.md` forbids writing `~/.pm-os` — which the offline installer must do — so shipping it
would make "ask Claude to install" self-conflicting. Packaging-only change: the repo keeps both
files; the installed `~/.pm-os` never needs dev docs at runtime.

---

## Verification

- **Offline E2E (throwaway HOME, no network):**
  ```bash
  ./scripts/pm_os_package.sh                       # build pm-os-offline.zip (maintainer, with git)
  cd /tmp && unzip /path/pm-os-offline.zip
  HOME=/tmp/fakehome bash /tmp/pm-os/install.sh --runtime claude --source /tmp/pm-os --pm-user trial
  ```
  Expect: installer **auto-runs `pm_os_verify.py` and ends with "PASS"** (exit 0); `~/.pm-os`
  populated, skills in `~/.claude/skills`, **no `CLAUDE.md`/`AGENTS.md`** under `~/.pm-os`.
  Negative check: remove `pyyaml` (or simulate blocked pip) → installer's auto-verify reports the
  lib-import failure and exits non-zero.
- **Re-install preserves user data:** put a marker in `~/.pm-os/context/` and `config.yaml`,
  re-run the offline install, confirm both survive.
- **GitLab remote:** `install.sh --repo <gitlab-url>` clones from GitLab; `pm_os_update.py`
  then fetches from GitLab (origin).
- **Regression:** `python3 -m pytest` stays green (Python install/verify/config paths unchanged);
  the new `tests/integration/test_offline_install.py` shell tests pass.

## Out of scope

- Auto-update for offline installs (re-run the installer instead; update.py already warns).
- Windows-native install (bash-only today; WSL works).
- Vendoring wheels by default (only via `--with-wheels` when pip/PyPI is confirmed blocked).

---

## Later phase — IT central / MDM rollout (not a blocker)

> **Do not implement this as part of the offline-zip work above.** These are good-to-have
> improvements for a future IT-distribution phase. They are captured here so context isn't
> lost, but they carry no dependency on the offline install and should not block it.

### Config enrollment default

`pm_os_install.py` already supports `--pm-user`, `--feedback-repo` flags and
`PM_OS_USER` / `PM_OS_FEEDBACK_REPO` env vars. One small gap: when `pm_user` has no flag, no
env, and no existing config value, it fails in non-interactive mode rather than defaulting.
Fix (later): default to `os.environ.get("USER") or os.environ.get("USERNAME", "")` so a
machine username is used automatically. IT MDM can still override via `PM_OS_USER`.

### Telemetry sink

No code change needed. `git_sync.py` reads `feedback_repo` from `config.yaml` (or
`PM_OS_FEEDBACK_REPO` env var) and does a plain `git push` — it works with any git host
(GitHub Enterprise, GitLab, Gitea, Azure DevOps). IT sets `PM_OS_FEEDBACK_REPO=<internal-url>`
in their MDM payload. For a non-git sink (REST API, S3) a `git_sync.py` refactor is needed — deferred.

### Python package categories for IT procurement

Two runtime deps, both pure Python (no C extensions):

| Package | Category |
|---------|----------|
| `pyyaml` | Data serialization — YAML parser |
| `jinja2` | Template engine (pulls in `MarkupSafe`, same category) |

If pip/PyPI is blocked: vendor wheels via `--with-wheels` when building the zip (see packaging
script). IT can also pre-install these system-wide; the installer skips pip if the imports succeed.
