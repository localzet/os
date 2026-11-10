#!/usr/bin/env bash
# Explicitly user-scoped development installation: no sudo, no system files.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
UUID='localzet-shell@localzet.com'
SOURCE="$ROOT/extensions/$UUID"
DEST="${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/$UUID"
[[ -f "$SOURCE/metadata.json" && -f "$SOURCE/extension.js" ]] || { echo 'Missing extension source' >&2; exit 1; }
if [[ -e "$DEST" || -L "$DEST" ]]; then
    echo "Refusing to overwrite existing installation: $DEST" >&2
    exit 2
fi
mkdir -p "$(dirname -- "$DEST")"
cp -R -- "$SOURCE" "$DEST"
echo "Installed to $DEST"
echo 'Log out and log back in. Enable the extension with the GNOME Extensions app.'
echo "Removal (after disabling): rm -r -- '$DEST'"
