#!/usr/bin/env bash
# Run only on a disposable Ubuntu 26.04 amd64 CI runner.
set -Eeuo pipefail
[[ ${LOCALZET_DISPOSABLE_VM:-} == 1 && $EUID != 0 ]]
. /etc/os-release
[[ "$VERSION_CODENAME" == resolute && "$(dpkg --print-architecture)" == amd64 ]]
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
out="$repo/out/control-center"
mkdir -p "$out"
work="$(mktemp -d)"
trap 'rm -rf -- "$work"' EXIT
# APT verifies source indexes via the same Ubuntu archive key as binaries.
# Retain Ubuntu patches and security updates, never download unsigned source.
sudo tee /etc/apt/sources.list.d/localzet-build-source.sources >/dev/null <<'EOF'
Types: deb-src
URIs: https://archive.ubuntu.com/ubuntu
Suites: resolute resolute-updates
Components: main universe restricted multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg

Types: deb-src
URIs: https://security.ubuntu.com/ubuntu
Suites: resolute-security
Components: main universe restricted multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
EOF
sudo apt-get -o Acquire::Retries=3 update
version="$(apt-cache policy gnome-control-center | awk '/Candidate:/{print $2}')"
[[ "$version" == 1:50.* && "$version" != '(none)' ]]
printf 'Ubuntu source version: %s\n' "$version" | tee "$out/provenance.txt"
sudo apt-get install -y build-essential devscripts quilt xvfb xauth xdotool imagemagick dbus-x11
sudo apt-get -y build-dep "gnome-control-center=$version"
cd "$work"
apt-get source "gnome-control-center=$version"
shopt -s nullglob
dirs=(gnome-control-center-*/)
[[ ${#dirs[@]} == 1 ]]
sha256sum ./*.dsc ./*.tar.* >> "$out/provenance.txt"
cd "${dirs[0]}"
[[ "$(dpkg-parsechangelog -S Version)" == "$version" ]]
cp debian/rules "$out/upstream-debian-rules.txt"
# Inspect the actual distro packaging. Keep all options and patches intact.
grep -nE 'distributor_logo|dh_auto_configure|meson' debian/rules | tee "$out/upstream-build-options.txt" || true
export QUILT_PATCHES=debian/patches
quilt new localzet-distributor-logo.patch
quilt add meson.build
python3 "$repo/scripts/patch-control-center-brand.py" meson.build
quilt refresh
cp debian/patches/localzet-distributor-logo.patch "$out/"
export DEBFULLNAME="Localzet OS" DEBEMAIL="build@localzet.com"
new_version="${version}+localzet1"
dch --newversion "$new_version" --distribution resolute "Use the original Localzet OS distributor logo."
# Full binary build, including upstream tests. No privileged compiler.
DEB_BUILD_OPTIONS="parallel=2" xvfb-run -a dpkg-buildpackage -b -us -uc 2>&1 | tee "$out/build.log"
cd "$work"
debs=(gnome-control-center_*.deb gnome-control-center-data_*.deb)
[[ ${#debs[@]} == 2 ]]
for deb in "${debs[@]}"; do
    test "$(dpkg-deb -f "$deb" Version)" = "$new_version"
    cp "$deb" "$out/"
done
sha256sum "${debs[@]}" >> "$out/provenance.txt"
# Check embedded compiled logo and compare panel inventory with stock
# before installing the rebuilt pair on this disposable runner.
sudo apt-get install -y gnome-control-center
LC_ALL=C.UTF-8 XDG_CURRENT_DESKTOP=GNOME xvfb-run -a dbus-run-session -- gnome-control-center --list | sort > "$out/stock-panels.txt"
test -s "$out/stock-panels.txt"
grep -qw network "$out/stock-panels.txt"
grep -qw sound "$out/stock-panels.txt"
bash "$repo/scripts/build-desktop-deb.sh" "$work/desktop"
sudo apt-get install -y "$work"/desktop/localzet-desktop_*.deb
sudo apt-get install -y "$work"/gnome-control-center_*.deb "$work"/gnome-control-center-data_*.deb
test "$(dpkg-query -W -f='${Version}' gnome-control-center)" = "$new_version"
strings /usr/bin/gnome-control-center | grep -Fx '/usr/share/localzet/brand/localzet.svg' > "$out/compiled-logo.txt"
LC_ALL=C.UTF-8 XDG_CURRENT_DESKTOP=GNOME xvfb-run -a dbus-run-session -- gnome-control-center --list | sort > "$out/localzet-panels.txt"
diff -u "$out/stock-panels.txt" "$out/localzet-panels.txt"
export OUT="$out"
xvfb-run -a -s '-screen 0 1440x900x24' dbus-run-session -- bash "$repo/scripts/ci/control-center-about-smoke.sh"
echo "PASS: rebuilt package, original logo path, unchanged panel inventory and About capture"
