#!/usr/bin/env bash
# Engineering-only preloading into the target root, never the workstation.
set -Eeuo pipefail
[[ $EUID == 0 && "${LOCALZET_DISPOSABLE_VM:-}" == 1 && "${LOCALZET_EXPERIMENTAL_TELEGRAM:-}" == 1 && $# == 1 ]]
[[ "${LOCALZET_ARCHIVE_PROFILE:-}" == standard || "${LOCALZET_ARCHIVE_PROFILE:-}" == complete ]]
root="$(realpath -e -- "$1")"
[[ "$root" != / && -f "$root/var/lib/dpkg/status" && -x "$root/usr/bin/flatpak" ]]
# Do not inherit a host installation; the target starts with an empty repository.
[[ ! -e "$root/var/lib/flatpak/repo" ]]
app=org.telegram.desktop
flatpak() { chroot "$root" /usr/bin/flatpak "$@"; }
flatpak remote-add --system flathub https://dl.flathub.org/repo/flathub.flatpakrepo
python3 - "$root/var/lib/flatpak/repo/config" <<'PY'
import configparser
import sys
config = configparser.ConfigParser(interpolation=None)
config.read(sys.argv[1])
remote = config['remote "flathub"']
assert remote.getboolean("gpg-verify"), "Unsigned Flathub remote"
assert remote["url"].startswith("https://")
PY
# Automated consent is scoped to an explicitly selected disposable build.
# No app runs as root. The runtime is deployed as part of the same transaction.
flatpak install --system --noninteractive --assumeyes --arch=x86_64 flathub "app/$app/x86_64/stable"
test "$(flatpak info --system --show-origin "$app")" = flathub
commit="$(flatpak info --system --show-commit "$app")"
[[ "$commit" =~ ^[a-f0-9]{64}$ ]]
runtime="$(flatpak info --system --show-runtime "$app")"
[[ "$runtime" =~ ^[a-zA-Z0-9._-]+/x86_64/[a-zA-Z0-9._-]+$ ]]
flatpak info --system "$runtime" >/dev/null
test -f "$root/var/lib/flatpak/exports/share/applications/$app.desktop"
receipt="$root/usr/share/localzet/telegram-review"
install -d -m 0755 "$receipt"
printf '%s\n' "$commit" > "$receipt/app-commit"
flatpak list --system --columns=ref,commit,origin > "$receipt/refs.tsv"
flatpak info --system --show-permissions "$app" > "$receipt/permissions.txt"
flatpak info --system "$app" > "$receipt/app-info.txt"
cat "$receipt/refs.tsv"
du -sh "$root/var/lib/flatpak"
echo 'PASS: actual Telegram and runtime preloaded in target; redistribution not approved'
