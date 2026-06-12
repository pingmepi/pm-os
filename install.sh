#!/usr/bin/env bash
set -euo pipefail

PM_OS_REPO="https://github.com/pingmepi/pm-os.git"
INSTALL_DIR="$HOME/.pm-os"
PROJECTS_DIR="$HOME/pm-projects"
RUNTIME=""

usage() {
  echo "Usage: ./install.sh --runtime claude|codex"
  echo ""
  echo "Choose the agent runtime to install skills for:"
  echo "  ./install.sh --runtime claude"
  echo "  ./install.sh --runtime codex"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --runtime)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --runtime requires claude or codex"
        exit 1
      fi
      RUNTIME="$2"
      shift 2
      ;;
    --runtime=*)
      RUNTIME="${1#*=}"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument '$1'"
      usage
      exit 1
      ;;
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

# --- Check Python ---
if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 not found. Install Python 3.11+."
  exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
REQUIRED="3.11"
if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"; then
  echo "ERROR: Python 3.11+ required (found $PYTHON_VERSION)."
  exit 1
fi

# --- Install Python dependencies ---
echo "Installing Python dependencies..."
python3 -m pip install --quiet pyyaml jinja2 gitpython

# --- Clone or update pm-os repo ---
if [ -d "$INSTALL_DIR/.git" ]; then
  echo "Updating existing installation at $INSTALL_DIR..."
  git -C "$INSTALL_DIR" fetch --tags --quiet
  LATEST_TAG=$(git -C "$INSTALL_DIR" describe --tags --abbrev=0 2>/dev/null || echo "main")
  git -C "$INSTALL_DIR" checkout "$LATEST_TAG" --quiet
else
  echo "Cloning pm-os to $INSTALL_DIR..."
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
python3 "$INSTALL_DIR/scripts/pm_os_install.py"

echo ""
echo "=== PM-OS installation complete ==="
echo "Version: $(cat "$INSTALL_DIR/VERSION")"
echo ""
echo "Next steps:"
if [[ "$RUNTIME" == "claude" ]]; then
  echo "  1. Restart your Claude Code session for skills to load."
  echo "  2. cd ~/pm-projects"
  echo "  3. /pm-new <your-project-slug> \"<your business statement>\""
else
  echo "  1. Restart Codex or refresh /skills for skills to load."
  echo "  2. cd ~/pm-projects"
  echo "  3. Use /skills or invoke: \$pm-new <your-project-slug> \"<your business statement>\""
fi
