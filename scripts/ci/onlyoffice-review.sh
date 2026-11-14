#!/usr/bin/env bash
# Disposable, unprivileged CI. No external APT sources or EULA acceptance.
set -Eeuo pipefail
[[ ${LOCALZET_DISPOSABLE_VM:-} == 1 && $EUID != 0 ]]
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
out="$repo/out/onlyoffice-review"
mkdir -p "$out"
work="$(mktemp -d)"
trap 'rm -rf -- "$work"' EXIT
deb="$(python3 "$repo/scripts/fetch-onlyoffice.py" deb "$work")"
test "$(dpkg-deb -f "$deb" Package)" = onlyoffice-desktopeditors
test "$(dpkg-deb -f "$deb" Architecture)" = amd64
version="$(dpkg-deb -f "$deb" Version)"
[[ "$version" == 10.0.0 || "$version" == 10.0.0-* ]]
dpkg-deb -I "$deb" > "$out/deb-info.txt"
dpkg-deb -c "$deb" > "$out/deb-files.txt"
dpkg-deb -e "$deb" "$out/control"
# Inspect scripts and license metadata without executing maintainer scripts.
dpkg-deb --fsys-tarfile "$deb" | tar -tf - > "$out/deb-paths.txt"
# APT resolves dependencies but must not install anything.
apt-get --simulate --no-install-recommends install "$deb" > "$out/apt-simulation.txt" 2>&1 || {
    cat "$out/apt-simulation.txt"; exit 1;
}
if grep -E '^Inst (ttf-mscorefonts-installer|ubuntu-restricted-extras)( |:)' "$out/apt-simulation.txt"; then
    echo "Separate font license review required" >&2
    exit 2
fi
if grep -q '^Remv ' "$out/apt-simulation.txt"; then
    echo "Unexpected package removal in office dependency plan" >&2
    exit 2
fi
echo "PASS: pinned official DEB, package metadata and dependency simulation"
# Exercise the original official AppImage without installing the DEB or
# running its scripts. Extract in temporary user-owned storage, no FUSE.
image="$(python3 "$repo/scripts/fetch-onlyoffice.py" appimage "$work")"
chmod 0700 "$image"
cd "$work"
"$image" --appimage-extract > "$out/appimage-extract.log"
test -x squashfs-root/AppRun
export OFFICE_APP="$work/squashfs-root/AppRun" OUT="$out"
export HOME="$work/home"
mkdir -p "$HOME"
export XDG_CONFIG_HOME="$HOME/.config" XDG_DATA_HOME="$HOME/.local/share" XDG_CACHE_HOME="$HOME/.cache"
export GDK_BACKEND=x11 GTK_A11Y=none LC_ALL=C.UTF-8
xvfb-run -a -s '-screen 0 1440x900x24' dbus-run-session -- bash "$repo/scripts/ci/onlyoffice-window-smoke.sh"
