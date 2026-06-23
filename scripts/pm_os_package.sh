#!/usr/bin/env bash
# Build a shareable offline distribution zip of PM-OS.
#
# Usage:
#   ./scripts/pm_os_package.sh
#   ./scripts/pm_os_package.sh --with-wheels        # bundle pyyaml/jinja2 wheels for pip-blocked envs
#   ./scripts/pm_os_package.sh --output /path/to/out.zip
#
# The resulting zip contains install.sh, lib/, scripts/, hooks/, skills/, templates/,
# context.example/, VERSION, README.md, and docs/. CLAUDE.md, AGENTS.md, tests/, and
# .github/ are excluded via .gitattributes export-ignore so the folder is safe to unzip
# and hand to teammates — no developer-facing agent instructions will be present.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WITH_WHEELS=false
OUTPUT="$PWD/pm-os-offline.zip"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-wheels) WITH_WHEELS=true; shift ;;
    --output)
      if [[ $# -lt 2 ]]; then echo "ERROR: --output requires a path"; exit 1; fi
      OUTPUT="$2"; shift 2 ;;
    --output=*) OUTPUT="${1#*=}"; shift ;;
    -h|--help)
      echo "Usage: $0 [--with-wheels] [--output <path>]"; exit 0 ;;
    *) echo "ERROR: unknown argument '$1'"; exit 1 ;;
  esac
done

cd "$REPO_ROOT"

if [[ "$WITH_WHEELS" == "true" ]]; then
  STAGE="$(mktemp -d)"
  trap 'rm -rf "$STAGE"' EXIT
  echo "Archiving source tree..."
  git archive --format=tar --prefix=pm-os/ HEAD | tar -x -C "$STAGE"
  echo "Downloading wheels into vendor/..."
  python3 -m pip download pyyaml jinja2 -d "$STAGE/pm-os/vendor" --quiet
  (cd "$STAGE" && zip -r -q "$OUTPUT" pm-os/)
else
  git archive --format=zip --prefix=pm-os/ -o "$OUTPUT" HEAD
fi

echo "Created: $OUTPUT"
echo ""
echo "To install from this zip:"
echo "  unzip $(basename "$OUTPUT") && bash pm-os/install.sh --runtime claude --source pm-os --pm-user <id>"
