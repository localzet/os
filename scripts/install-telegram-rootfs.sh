#!/usr/bin/env bash
# Engineering-only preloading into the target root, never the workstation.
set -Eeuo pipefail
trap 'printf "Telegram preload failed at line %s: %s\n" "$LINENO" "$BASH_COMMAND" >&2' ERR
[[ $EUID == 0 && "${LOCALZET_DISPOSABLE_VM:-}" == 1 && "${LOCALZET_EXPERIMENTAL_TELEGRAM:-}" == 1 && $# == 1 ]]
[[ "${LOCALZET_ARCHIVE_PROFILE:-}" == standard || "${LOCALZET_ARCHIVE_PROFILE:-}" == complete ]]
root="$(realpath -e -- "$1")"
[[ "$root" != / && -f "$root/var/lib/dpkg/status" && -x "$root/usr/bin/flatpak" ]]
# Ubuntu's package may initialize an empty system repository during its
# postinst. Accept that state, not an arbitrary preexisting installation.
app=org.telegram.desktop
flatpak() { chroot "$root" /usr/bin/flatpak "$@"; }
echo "Telegram preload: inspecting target Flatpak installation"
test -z "$(flatpak list --system --columns=ref)" || { echo "Target already has deployed Flatpak refs" >&2; exit 2; }
remotes="$(flatpak remotes --system --columns=name)"
[[ -z "$remotes" || "$remotes" == flathub ]] || { echo "Unexpected target Flatpak remote" >&2; exit 2; }
flatpak remote-add --system --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
echo "Telegram preload: verifying remote trust"
python3 - "$root/var/lib/flatpak/repo/config" <<'PY'
import configparser
import sys
config = configparser.ConfigParser(interpolation=None)
config.read(sys.argv[1])
remote = config['remote "flathub"']
assert remote.getboolean("gpg-verify"), "Unsigned Flathub remote"
assert remote["url"].rstrip("/") in {"https://dl.flathub.org/repo", "https://flathub.org/repo"}, "Unexpected Flathub URL"
PY
# Automated consent is scoped to an explicitly selected disposable build.
# No app runs as root. The runtime is deployed as part of the same transaction.
echo "Telegram preload: deploying signed app and runtime"
flatpak install --system --noninteractive --assumeyes --arch=x86_64 flathub "app/$app/x86_64/stable"
test "$(flatpak info --system --show-origin "$app")" = flathub
commit="$(flatpak info --system --show-commit "$app")"
[[ "$commit" =~ ^[a-f0-9]{64}$ ]]
runtime="$(flatpak info --system --show-runtime "$app")"
[[ "$runtime" =~ ^[a-zA-Z0-9._-]+/x86_64/[a-zA-Z0-9._-]+$ ]]
flatpak info --system "$runtime" >/dev/null
chroot "$root" test -f "/var/lib/flatpak/exports/share/applications/$app.desktop"
receipt="$root/usr/share/localzet/telegram-review"
install -d -m 0755 "$receipt"
printf '%s\n' "$commit" > "$receipt/app-commit"
flatpak list --system --columns=ref,commit,origin > "$receipt/refs.tsv"
flatpak info --system --show-permissions "$app" > "$receipt/permissions.txt"
flatpak info --system "$app" > "$receipt/app-info.txt"
cat "$receipt/refs.tsv"
du -sh "$root/var/lib/flatpak"
echo 'PASS: actual Telegram and runtime preloaded in target; redistribution not approved'
