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
# The exact inspected DEB contains only postrm, no installation scripts.
# Do not purge it: upstream postrm(purge) deletes users' preferences.
# This runner is disposable and has no user documents.
test -f "$out/control/postrm"
for script in preinst postinst prerm config; do test ! -e "$out/control/$script"; done
dpkg-deb -x "$deb" "$work/deb-review"
install -m 0644 "$work/deb-review/opt/onlyoffice/desktopeditors/LICENSE.txt" "$out/LICENSE.txt"
test -s "$out/LICENSE.txt"
# No recommended fonts/EULA, no APT source change, no purge.
chmod 0755 "$work"
chmod 0644 "$deb"
sudo apt-get install -y --no-install-recommends "$deb"
test "$(dpkg-query -W -f='${Version}' onlyoffice-desktopeditors)" = "$version"
test -x /usr/bin/onlyoffice-desktopeditors
dpkg-query -W -f='${Package} ${Version} ${db:Status-Abbrev}\n' onlyoffice-desktopeditors > "$out/installed-package.txt"
export OFFICE_APP=/usr/bin/onlyoffice-desktopeditors OUT="$out"
export HOME="$work/home"
mkdir -p "$HOME"
export XDG_CONFIG_HOME="$HOME/.config" XDG_DATA_HOME="$HOME/.local/share" XDG_CACHE_HOME="$HOME/.cache"
export GDK_BACKEND=x11 GTK_A11Y=none LC_ALL=C.UTF-8
xvfb-run -a -s '-screen 0 1440x900x24' dbus-run-session -- bash "$repo/scripts/ci/onlyoffice-window-smoke.sh"
