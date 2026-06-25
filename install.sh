#!/usr/bin/env bash
set -euo pipefail

# PM_OS_REPO can be overridden via --repo or the PM_OS_REPO environment variable.
PM_OS_REPO="${PM_OS_REPO:-https://github.com/pingmepi/pm-os.git}"
INSTALL_DIR="$HOME/.pm-os"
PROJECTS_DIR="$HOME/pm-projects"
RUNTIME=""
PM_USER=""
FEEDBACK_REPO=""
CONFIG_PROJECTS_DIR=""
RECONFIGURE=false
SOURCE_DIR="${PM_OS_SOURCE:-}"

usage() {
  echo "Usage: ./install.sh --runtime claude|codex [options]"
  echo ""
  echo "Standard install (clone from GitHub or a git mirror):"
  echo "  ./install.sh --runtime claude --pm-user <id> --feedback-repo https://github.com/org/pm-os-feedback.git"
  echo "  ./install.sh --runtime claude --repo https://gitlab.example.com/org/pm-os.git --pm-user <id>"
  echo ""
  echo "Offline install from a local directory or extracted zip:"
  echo "  ./install.sh --runtime claude --source /path/to/pm-os --pm-user <id>"
  echo ""
  echo "Options:"
  echo "  --runtime claude|codex      Agent runtime to install skills for (required)"
  echo "  --repo <url>                Override git remote (env: PM_OS_REPO; default: GitHub)"
  echo "  --source <dir>              Install from local dir instead of git (env: PM_OS_SOURCE)"
  echo "  --pm-user <id>              PM/team member identifier used in telemetry paths"
  echo "  --feedback-repo <url>       Feedback/telemetry repository URL"
  echo "  --projects-dir <path>       Local PM-OS projects directory"
  echo "  --reconfigure               Prompt for and rewrite existing local config"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --runtime)
      if [[ $# -lt 2 ]]; then echo "ERROR: --runtime requires claude or codex"; exit 1; fi
      RUNTIME="$2"; shift 2 ;;
    --runtime=*)
      RUNTIME="${1#*=}"; shift ;;
    --repo)
      if [[ $# -lt 2 ]]; then echo "ERROR: --repo requires a value"; exit 1; fi
      PM_OS_REPO="$2"; shift 2 ;;
    --repo=*)
      PM_OS_REPO="${1#*=}"; shift ;;
    --source)
      if [[ $# -lt 2 ]]; then echo "ERROR: --source requires a value"; exit 1; fi
      SOURCE_DIR="$2"; shift 2 ;;
    --source=*)
      SOURCE_DIR="${1#*=}"; shift ;;
    --pm-user)
      if [[ $# -lt 2 ]]; then echo "ERROR: --pm-user requires a value"; exit 1; fi
      PM_USER="$2"; shift 2 ;;
    --pm-user=*)
      PM_USER="${1#*=}"; shift ;;
    --feedback-repo)
      if [[ $# -lt 2 ]]; then echo "ERROR: --feedback-repo requires a value"; exit 1; fi
      FEEDBACK_REPO="$2"; shift 2 ;;
    --feedback-repo=*)
      FEEDBACK_REPO="${1#*=}"; shift ;;
    --projects-dir)
      if [[ $# -lt 2 ]]; then echo "ERROR: --projects-dir requires a value"; exit 1; fi
      CONFIG_PROJECTS_DIR="$2"; PROJECTS_DIR="$2"; shift 2 ;;
    --projects-dir=*)
      CONFIG_PROJECTS_DIR="${1#*=}"; PROJECTS_DIR="$CONFIG_PROJECTS_DIR"; shift ;;
    --reconfigure)
      RECONFIGURE=true; shift ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "ERROR: unknown argument '$1'"
      usage; exit 1 ;;
  esac
done

if [[ -z "$RUNTIME" ]]; then
  echo "ERROR: missing required --runtime argument."
  usage
  exit 1
fi

case "$RUNTIME" in
  claude)
    SKILLS_DIR="$HOME/.claude/skills"
    HOOKS_DIR="$HOME/.claude/hooks"
    ;;
  codex)
    SKILLS_DIR="$HOME/.agents/skills"
    HOOKS_DIR=""
    ;;
  *)
    echo "ERROR: runtime must be 'claude' or 'codex' (got '$RUNTIME')"
    exit 1
    ;;
esac

echo "=== PM-OS Installer ==="
echo "Runtime: $RUNTIME"

# --- Check Claude Code ---
if [[ "$RUNTIME" == "claude" ]] && ! command -v claude &>/dev/null; then
  echo "ERROR: Claude Code not found. Install it first: https://claude.ai/code"
  exit 1
fi

# --- Check Python (resolve interpreter: python3, python, or the py launcher) ---
# Windows installs Python as `python` / `py`, not `python3`, so don't hard-assume.
PY=""
for candidate in python3.13 python3.12 python3.11 python3 python "py -3"; do
  if $candidate -c "import sys" &>/dev/null; then
    PY="$candidate"
    break
  fi
done
if [[ -z "$PY" ]]; then
  echo "ERROR: Python not found. Install Python 3.11+ (provides python3, python, or the py launcher)."
  exit 1
fi

PYTHON_VERSION=$($PY -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
REQUIRED="3.11"
if ! $PY -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"; then
  echo "ERROR: Python 3.11+ required (found $PYTHON_VERSION via '$PY')."
  exit 1
fi
echo "Python: $PY ($PYTHON_VERSION)"

# --- Install Python dependencies ---
# Skip if already present; use vendored wheels if available; fall back to PyPI.
echo "Installing Python dependencies..."
if $PY -c "import yaml, jinja2" &>/dev/null; then
  echo "Python dependencies already present (pyyaml, jinja2)."
elif [[ -n "$SOURCE_DIR" && -d "$SOURCE_DIR/vendor" ]]; then
  $PY -m pip install --quiet --no-index --find-links "$SOURCE_DIR/vendor" pyyaml jinja2 \
    || { echo "ERROR: could not install pyyaml/jinja2 from $SOURCE_DIR/vendor."; \
         echo "       Rebuild the zip with bundled wheels: ./scripts/pm_os_package.sh --with-wheels"; \
         exit 1; }
else
  $PY -m pip install --quiet pyyaml jinja2 \
    || { echo "ERROR: could not install pyyaml/jinja2 from PyPI."; \
         echo "       If pip/PyPI is blocked, use a zip built with: ./scripts/pm_os_package.sh --with-wheels"; \
         exit 1; }
fi

# --- Populate ~/.pm-os (from a local source dir or via git) ---
if [[ -n "$SOURCE_DIR" ]]; then
  SOURCE_DIR="$(cd "$SOURCE_DIR" && pwd)"
  echo "Installing from source: $SOURCE_DIR"
  mkdir -p "$INSTALL_DIR"
  if command -v rsync &>/dev/null; then
    rsync -a --delete \
      --exclude='/.git/' \
      --exclude='/context/' \
      --exclude='/config.yaml' \
      "$SOURCE_DIR"/ "$INSTALL_DIR"/
  else
    # rsync not available — copy top-level items individually, skipping user-data dirs
    for item in "$SOURCE_DIR"/*/; do
      name=$(basename "$item")
      [[ "$name" == "context" ]] && continue
      rm -rf "${INSTALL_DIR:?}/$name"
      cp -R "$item" "$INSTALL_DIR/$name"
    done
    for item in "$SOURCE_DIR"/*; do
      [[ -d "$item" ]] && continue
      name=$(basename "$item")
      [[ "$name" == "config.yaml" ]] && continue
      cp "$item" "$INSTALL_DIR/$name"
    done
  fi
elif [ -d "$INSTALL_DIR/.git" ]; then
  echo "Updating existing installation at $INSTALL_DIR..."
  git -C "$INSTALL_DIR" fetch --tags origin main --quiet
  git -C "$INSTALL_DIR" checkout main --quiet
  git -C "$INSTALL_DIR" merge --ff-only origin/main --quiet \
    || { echo "ERROR: could not fast-forward ~/.pm-os to origin/main (local branch has diverged)."; \
         echo "       Run: python3 ~/.pm-os/scripts/pm_os_update.py --runtime claude --reset-main"; \
         exit 1; }
else
  echo "Cloning pm-os from $PM_OS_REPO..."
  git clone --quiet "$PM_OS_REPO" "$INSTALL_DIR"
fi

# --- Set up directories ---
mkdir -p "$PROJECTS_DIR"
mkdir -p "$SKILLS_DIR"
if [[ -n "$HOOKS_DIR" ]]; then
  mkdir -p "$HOOKS_DIR"
fi

# --- Sync skills ---
echo "Installing skills..."
for skill_dir in "$INSTALL_DIR"/skills/*/; do
  skill_name=$(basename "$skill_dir")
  dest="$SKILLS_DIR/$skill_name"
  rm -rf "$dest"
  cp -r "$skill_dir" "$dest"
done

# --- Make scripts executable ---
if [ -d "$INSTALL_DIR/scripts" ]; then
  chmod +x "$INSTALL_DIR"/scripts/*.py
fi

# --- Sync hooks ---
if [[ "$RUNTIME" == "claude" ]]; then
  echo "Installing hooks..."
  for hook in "$INSTALL_DIR"/hooks/*.py; do
    cp "$hook" "$HOOKS_DIR/"
  done
else
  echo "Skipping Claude hooks for Codex runtime."
fi

# --- Configure PM-OS (writes ~/.pm-os/config.yaml, does NOT touch ~/.zshrc) ---
CONFIG_ARGS=()
if [[ "$RECONFIGURE" == "true" ]]; then
  CONFIG_ARGS+=("--reconfigure")
fi
if [[ -n "$PM_USER" ]]; then
  CONFIG_ARGS+=("--pm-user" "$PM_USER")
fi
if [[ -n "$FEEDBACK_REPO" ]]; then
  CONFIG_ARGS+=("--feedback-repo" "$FEEDBACK_REPO")
fi
if [[ -n "$CONFIG_PROJECTS_DIR" ]]; then
  CONFIG_ARGS+=("--projects-dir" "$CONFIG_PROJECTS_DIR")
fi
$PY "$INSTALL_DIR/scripts/pm_os_install.py" "${CONFIG_ARGS[@]}"

echo ""
echo "=== PM-OS installation complete ==="
echo "Version: $(cat "$INSTALL_DIR/VERSION")"
echo ""

# --- Auto-verify: confirm the install is healthy before handing off ---
echo "Verifying install..."
if $PY "$INSTALL_DIR/scripts/pm_os_verify.py" --runtime "$RUNTIME"; then
  echo ""
  if [[ -n "$SOURCE_DIR" ]]; then
    echo "Installed from $SOURCE_DIR. PM-OS runs from ~/.pm-os — you can delete the source folder."
    echo "To update later, re-run this installer with a newer copy."
    echo ""
  fi
  echo "Next steps:"
  if [[ "$RUNTIME" == "claude" ]]; then
    echo "  1. Restart your Claude Code session for skills to load."
    echo "     Then run: /pm-os-verify  (re-confirms skills loaded into the new session)"
    echo "  2. cd $PROJECTS_DIR"
    echo "  3. /pm-new <your-project-slug> \"<your business statement>\" --genai|--no-genai"
  else
    echo "  1. Restart Codex or refresh /skills for skills to load."
    echo "     Then run: \$pm-os-verify  (re-confirms skills loaded into the new session)"
    echo "  2. cd $PROJECTS_DIR"
    echo "  3. Use /skills or invoke: \$pm-new <your-project-slug> \"<your business statement>\" --genai|--no-genai"
  fi
else
  echo ""
  echo "Install verification FAILED — see the checks above."
  echo "Fix the reported issues and re-run this installer."
  exit 1
fi
