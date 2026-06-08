#!/usr/bin/env bash
set -euo pipefail

PM_OS_REPO="https://github.com/pingmepi/pm-os.git"
INSTALL_DIR="$HOME/.pm-os"
PROJECTS_DIR="$HOME/pm-projects"
SKILLS_DIR="$HOME/.claude/skills"
HOOKS_DIR="$HOME/.claude/hooks"

echo "=== PM-OS Installer ==="

# --- Check Claude Code ---
if ! command -v claude &>/dev/null; then
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
mkdir -p "$HOOKS_DIR"

# --- Sync skills ---
echo "Installing skills..."
for skill_dir in "$INSTALL_DIR"/skills/*/; do
  skill_name=$(basename "$skill_dir")
  dest="$SKILLS_DIR/$skill_name"
  rm -rf "$dest"
  cp -r "$skill_dir" "$dest"
done

# --- Sync hooks ---
echo "Installing hooks..."
for hook in "$INSTALL_DIR"/hooks/*.py; do
  cp "$hook" "$HOOKS_DIR/"
done

# --- PM_OS_USER setup ---
if [ -z "${PM_OS_USER:-}" ]; then
  read -rp "Enter your PM identifier (e.g. 'karan'): " PM_ID
  RCFILE="$HOME/.zshrc"
  [ -f "$HOME/.bashrc" ] && RCFILE="$HOME/.bashrc"
  echo "export PM_OS_USER=\"$PM_ID\"" >> "$RCFILE"
  export PM_OS_USER="$PM_ID"
  echo "PM_OS_USER set to '$PM_ID' in $RCFILE"
fi

# --- Feedback repo setup ---
if [ -z "${PM_OS_FEEDBACK_REPO:-}" ]; then
  read -rp "Enter pm-os-feedback repo URL (SSH or HTTPS, or leave blank to skip): " FEEDBACK_URL
  if [ -n "$FEEDBACK_URL" ]; then
    RCFILE="$HOME/.zshrc"
    [ -f "$HOME/.bashrc" ] && RCFILE="$HOME/.bashrc"
    echo "export PM_OS_FEEDBACK_REPO=\"$FEEDBACK_URL\"" >> "$RCFILE"
    export PM_OS_FEEDBACK_REPO="$FEEDBACK_URL"
    echo "PM_OS_FEEDBACK_REPO configured."
  fi
fi

echo ""
echo "=== PM-OS installation complete ==="
echo "Version: $(cat "$INSTALL_DIR/VERSION")"
echo ""
echo "Next steps:"
echo "  1. Restart your Claude Code session for skills to load."
echo "  2. cd ~/pm-projects"
echo "  3. /pm-new <your-project-slug> \"<your business statement>\""
