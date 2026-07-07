# PM-OS — Permissions & Tooling Review for Tech Lead

**Purpose:** align on what PM-OS needs to run today, what the roadmap will require later, and what needs Indegene approval before wider rollout.

---

## 1. Required now

| Item | Detail |
|---|---|
| Local runtime | Python 3.11+ (3.12 targeted), `pip install pyyaml jinja2` on PM laptops — no other third-party packages |
| Engine repo access | Read access to clone the PM-OS engine repo (currently `github.com/pingmepi/pm-os` — **personal account, needs to move**, see §4) |
| Agent CLI | Claude Code and/or Codex CLI approved for local use, with permission to run local skills and the two hook scripts (`pre-stage.py`, `post-approve.py`) as local subprocesses. No daemons, no open ports |
| Local filesystem | Write access to `~/.pm-os`, `~/.claude/skills` (or `~/.agents/skills`), `~/pm-projects` — everything is local-first, nothing shared or networked by default |

---

## 2. Codebase access for enhancement mode

Enhancement mode (`--mode enhancement --codebase <url-or-path>`) needs **read-only** access to the target product repo:

- `prepare-codebase` runs a plain `git clone --depth 1 <url> .codebase/` into the project folder (or points at a local path directly), using whatever credentials the PM already has (HTTPS token / SSH key).
- The clone is gitignored — never committed, lives only in the project folder.
- A read-only subagent scan (`pm-context-scan-codebase`) reads that clone and distills it into `00-codebase-understanding.md`. The LLM never sees the raw repo — only this distilled doc.

**Ask:** no new access beyond what the PM's existing git credentials already grant. No write access, no CI integration, no service account needed.

---

## 3. Telemetry / feedback sink — needs to move off a personal repo

Current mechanism (`lib/git_sync.py`): copies `telemetry.jsonl` / `feedback.jsonl` per project, single commit+push to a git remote. That remote is currently personal — **not acceptable**, needs an Indegene-owned sink.

**Options, lowest to highest effort:**

1. **Org-owned private git repo** (recommended to unblock immediately) — same code path, just point `feedback_repo` config at an Indegene-owned GitHub/GitLab repo. Config change only, no code change.
2. **Internal object storage** (S3-compatible / Azure Blob) — replace the git push with an upload call; needs bucket write credentials.
3. **Internal API/database endpoint** — a proper ingest endpoint for queryable telemetry; needs an API token + network egress to an internal host. Recommended as the target state if Indegene wants analytics on this data, not just files in a repo.

---

## 4. Engine repo — also needs to move off a personal account

`install.sh` clones from `github.com/pingmepi/pm-os`, and `pm_os_update.py` fast-forwards `~/.pm-os` from that same remote's `origin/main` on every update. Same problem as §3, but for the code itself.

**Ask — streamline the update channel:** `pm_os_update.py` already supports `--repo <url>` (built for offline/GitLab installs) — no new code needed, just redirect:

- Mirror the engine repo into an Indegene-owned repo; commits/tags get promoted into it on a controlled cadence, PM machines update from the mirror instead of the public repo.
- Pin installs to version tags rather than tracking `main` live, with a lightweight review step before a tag is promoted.

---

## 5. Approvals needed from the tech lead

1. **LLM data flow approval (the core dependency):** explicit sign-off to send product artifacts (briefs, PRDs, design specs) and, in enhancement mode, source-code excerpts to the agent's backing LLM (Anthropic via Claude Code / OpenAI via Codex). Everything else here is secondary to this approval.
2. **Approved tool list:** if Indegene maintains an approved-tools/vendor list, share it so Claude Code / Codex / GitHub usage can be checked against it, rather than guessing.

---

## 6. Settled decisions

- **No telemetry opt-out.** All actions are captured by design — no per-PM opt-out planned.

---

## 7. Roadmap — access needed later, by phase

| Roadmap item | New access needed |
|---|---|
| Gemini runtime support | Gemini CLI + API access, if adopted |
| Jira/Linear handoff | API tokens with write scope (create tickets) |
| Figma integration | Figma API token, read access to design files |
| Dev-phase / QA bug analysis, release readiness | GitHub/GitLab API read access, bug-tracker access, release-tool access |
| Feedback ingestion | Access to Indegene's support/analytics tooling (Intercom/Zendesk/PostHog/Amplitude equivalent) |

---

## 8. Other flags

- **No auth model in PM-OS itself** — access control is entirely OS file permissions + git remote ACLs. Whoever owns the org repos (§3, §4) is the real control point.
- **Plaintext local storage** — all artifacts are unencrypted Markdown/YAML/JSONL on disk. Worth a data-classification check if pre-launch product content is sensitive.
