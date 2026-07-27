# Offline and GitLab-friendly Install

## 0. Prerequisite: network access to fetch the base tools

On a corporate machine, having local admin rights is not the same as having network access —
a proxy/firewall team commonly blocks the download endpoints even when you're allowed to install
software yourself. PM-OS itself needs `git` and a Python 3.11+ runtime; the agent runtime (Claude
Code or Codex) is a separate prerequisite install. Before install day, file one ticket with your
network/IT team requesting outbound access to all of these — going one tool at a time tends to
turn into a multi-week back-and-forth:

| Tool | What you're fetching | Typical domains to allow-list |
|------|----------------------|-------------------------------|
| Git | Git for Windows / Xcode CLT / distro package | `github.com`, `objects.githubusercontent.com`, `gitforwindows.org` (Windows installer) |
| Python 3.11+ | Interpreter installer | `python.org`, `www.python.org` |
| pip / PyPI packages (`pyyaml`, `jinja2`) | Runtime dependencies `install.sh` installs automatically | `pypi.org`, `files.pythonhosted.org` |
| Claude Code | CLI install script / npm package | `claude.ai`, `anthropic.com`, `registry.npmjs.org` (if installed via npm) |
| Codex | CLI install script / npm package | `openai.com`, `registry.npmjs.org` (if installed via npm) |
| PM-OS itself | This repo, cloned by `install.sh` | `github.com` (or your internal GitLab mirror — see §2 below) |

Practical notes:
- Ask for the list above in one request rather than discovering blocks one at a time — each
  round trip through a network team's ticket queue can cost a day or more.
- If GitHub itself is blocked but an internal GitLab mirror is reachable, use the
  [GitLab mirror path](#2-gitlab-mirror-custom-git-remote) below instead of requesting a
  GitHub exception.
- If PyPI is blocked but GitHub/GitLab isn't, use `--with-wheels` (§3) to bundle `pyyaml`/`jinja2`
  so no PyPI access is needed at install time.
- If *all* outbound access is blocked (no exceptions available), use the fully offline zip path
  (§3) with `--with-wheels` — it needs no network access at install time, only a way to move the
  zip onto the machine (shared drive, MDM payload, USB).
- Confirm the base tools (`git`, `python3`, and your chosen agent runtime CLI) are actually
  installed and on `PATH` before running `install.sh` — a network unblock doesn't install the
  tool for you, it just lets the installer you run yourself reach the download.

---

PM-OS supports three install paths from the same `install.sh`:

1. **GitHub (default)** — standard path, clones from public GitHub.
2. **Custom git remote (GitLab mirror)** — for teams where GitHub is blocked but a GitLab or other
   internal mirror is available.
3. **Offline zip** — for environments with no git/network access at all; install from a zip shared
   by a teammate or deployed via MDM.

---

## 1. GitHub (default)

No changes needed. The existing install command works as-is:

```bash
bash install.sh --runtime claude --pm-user <id> \
  --feedback-repo https://github.com/org/pm-os-feedback.git
```

---

## 2. GitLab mirror (custom git remote)

A maintainer pushes a mirror of this repo to an internal GitLab instance once. Teammates then
install from there. Because `pm_os_update.py` follows the `origin` remote set at clone time,
updates automatically pull from GitLab — no change to the update script is needed.

**Maintainer (one-time setup):**

```bash
# Mirror to your internal GitLab
git push --mirror https://gitlab.example.com/org/pm-os.git

# Also create the feedback repo mirror (telemetry sink)
git push --mirror https://gitlab.example.com/org/pm-os-feedback.git
```

**Team member install:**

```bash
bash install.sh --runtime claude \
  --repo https://gitlab.example.com/org/pm-os.git \
  --pm-user <id> \
  --feedback-repo https://gitlab.example.com/org/pm-os-feedback.git
```

Or set `PM_OS_REPO` in the environment instead of passing `--repo`:

```bash
export PM_OS_REPO=https://gitlab.example.com/org/pm-os.git
bash install.sh --runtime claude --pm-user <id>
```

**Updates** (after a mirror refresh):

```bash
python3 ~/.pm-os/scripts/pm_os_update.py --runtime claude
```

This pulls from the GitLab origin — no GitHub traffic.

---

## 3. Offline zip (git-blocked environments)

A maintainer (who has git) builds the zip once. Teammates extract and install from it, then delete
the folder. The installed `~/.pm-os` has no developer-facing `CLAUDE.md`/`AGENTS.md` (excluded by
`.gitattributes export-ignore`), so the installed engine and the runtime skills dir can't
accidentally override a teammate's Claude/Codex instructions for other projects.

**Maintainer — build the zip:**

```bash
# Standard zip (teams with pip/PyPI access)
./scripts/pm_os_package.sh

# With bundled Python wheels (for environments where pip/PyPI is also blocked)
./scripts/pm_os_package.sh --with-wheels

# Custom output path
./scripts/pm_os_package.sh --output /shared-drive/pm-os-offline.zip
```

Push `pm-os-offline.zip` to a shared drive, internal artifact store, or MDM payload.

**Team member install:**

```bash
unzip pm-os-offline.zip
bash pm-os/install.sh --runtime claude --source pm-os --pm-user <id> \
  --feedback-repo https://gitlab.example.com/org/pm-os-feedback.git
# PM-OS runs from ~/.pm-os — you can now delete the pm-os/ folder
rm -rf pm-os/
```

**Codex runtime** — use `--runtime codex` instead of `claude` on any of the above.

**Updates for offline installs:** there is no auto-update path. When a new version is released,
the maintainer rebuilds the zip and redistributes; team members re-run the installer.
`pm_os_update.py` exits gracefully when `~/.pm-os` has no `.git`, so it will not break.

---

## 4. IT / MDM central deployment

For MDM-pushed installs (zero-touch, no interactive prompts):

```bash
# All config values can be provided as environment variables or flags
export PM_OS_REPO=https://gitlab.example.com/org/pm-os.git      # or use --repo
export PM_OS_FEEDBACK_REPO=https://gitlab.example.com/org/pm-os-feedback.git
export PM_OS_USER="$USER"   # or pass --pm-user explicitly

bash install.sh --runtime claude
```

`pm_user` falls back to `$USER`/`$USERNAME` from the machine environment when no other source
is provided, so an MDM payload that sets standard user env vars needs no extra configuration.

**Codex runtime** — same flags with `--runtime codex`. No hooks are installed for Codex.

**Note on "ask Claude to install":** when installing from a zip with `--source`, run the command
from *outside* the extracted folder so no directory-scoped instructions are in the agent's CWD.
The zip itself omits `CLAUDE.md`/`AGENTS.md`, so this is belt-and-suspenders.

---

## 5. Telemetry sink

The feedback/telemetry repository is plain git. Any git host works — GitHub, GitHub Enterprise,
GitLab, Gitea, Azure DevOps, etc. Set it via `--feedback-repo <url>` at install time or
`PM_OS_FEEDBACK_REPO` in the environment; it is stored in `~/.pm-os/config.yaml` and used by
`git_sync.py` (`/pm-sync`) to push telemetry and feedback.

To change it after install: run `python3 ~/.pm-os/scripts/pm_os_install.py --reconfigure`.

---

## 6. Python packages for IT procurement

PM-OS has two runtime Python dependencies, both pure Python (no C extensions, no system libs):

| Package | Category | Notes |
|---------|----------|-------|
| `pyyaml` | Data serialization — YAML parser | |
| `jinja2` | Template engine | Pulls in `MarkupSafe` (same category, also pure Python) |

If pip/PyPI is blocked: bundle wheels when building the zip (`--with-wheels`). If the packages are
pre-installed system-wide, `install.sh` skips pip automatically.
