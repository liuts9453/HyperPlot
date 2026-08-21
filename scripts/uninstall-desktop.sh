#!/usr/bin/env bash
set -euo pipefail

APPLICATIONS_DIR="${XDG_DATA_HOME:-${HOME}/.local/share}/applications"
DESKTOP_FILE="$APPLICATIONS_DIR/hyperplot.desktop"

if [[ -f "$DESKTOP_FILE" ]]; then
  rm -- "$DESKTOP_FILE"
  printf 'Removed HyperPlot desktop entry: %s\n' "$DESKTOP_FILE"
else
  printf 'HyperPlot desktop entry is not installed.\n'
fi

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
fi
