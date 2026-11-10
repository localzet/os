#!/usr/bin/env bash
# Read-only diagnostic for an actual local Ubuntu 26.04 GNOME 50 session.
set -euo pipefail
UUID='localzet-shell@localzet.com'
if [[ "${XDG_CURRENT_DESKTOP:-}" != *GNOME* || "${XDG_SESSION_TYPE:-}" != wayland ]]; then
    echo 'Expected an interactive GNOME Wayland session (Ubuntu 26.04 VM).' >&2
    exit 2
fi
for program in gnome-shell gnome-extensions; do
    command -v "$program" >/dev/null || { echo "Missing: $program" >&2; exit 2; }
done
version="$(gnome-shell --version)"
printf 'Shell: %s\n' "$version"
if [[ ! "$version" =~ ^GNOME\ Shell\ 50(\.[0-9]+)*$ ]]; then
    echo 'This smoke check requires GNOME Shell 50.' >&2
    exit 2
fi
if ! gnome-extensions info "$UUID"; then
    echo "Extension is not discoverable: $UUID" >&2
    echo 'Install with scripts/install-shell-dev.sh, then log out and in.' >&2
    exit 1
fi
if ! gnome-extensions list --enabled | grep -Fxq -- "$UUID"; then
    echo "Extension not enabled: $UUID" >&2
    exit 1
fi
printf 'PASS: %s enabled in GNOME Shell 50.\n' "$UUID"
echo 'Visual inspection and a genuine screenshot are still required.'
