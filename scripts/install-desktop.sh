#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="$APP_DIR/desktop/hyperplot.desktop.in"
APPLICATIONS_DIR="${XDG_DATA_HOME:-${HOME}/.local/share}/applications"
DESKTOP_FILE="$APPLICATIONS_DIR/hyperplot.desktop"
temporary_file="$(mktemp)"
trap 'rm -f "$temporary_file"' EXIT

escaped_app_dir="${APP_DIR//\\/\\\\}"
escaped_app_dir="${escaped_app_dir//&/\\&}"
escaped_app_dir="${escaped_app_dir//|/\\|}"
sed "s|@APP_DIR@|$escaped_app_dir|g" "$TEMPLATE" >"$temporary_file"

mkdir -p "$APPLICATIONS_DIR"
install -m 0644 "$temporary_file" "$DESKTOP_FILE"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
fi

printf 'Installed HyperPlot desktop entry: %s\n' "$DESKTOP_FILE"
