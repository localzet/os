#!/usr/bin/env bash
set -Eeuo pipefail
[[ $# == 2 && $EUID != 0 ]]
packages="$(realpath -e "$1")"
out="$(realpath -e "$2")"
stage="$(mktemp -d)"
trap 'rm -rf -- "$stage"' EXIT
for pkg in netbird netbird-ui; do
    deb="$packages/$pkg"_0.83.1_linux_amd64.deb
    dpkg-deb -I "$deb" > "$out/$pkg-control.txt"
    dpkg-deb -c "$deb" > "$out/$pkg-files.txt"
    dpkg-deb -x "$deb" "$stage"
done
test -x "$stage/usr/bin/netbird"
test -x "$stage/usr/bin/netbird-ui"
test -f "$stage/usr/share/applications/org.wails.netbird.desktop"
grep -Fx 'Icon=netbird' "$stage/usr/share/applications/org.wails.netbird.desktop"
"$stage/usr/bin/netbird" version | tee "$out/version.txt"
grep -F 0.83.1 "$out/version.txt"
"$stage/usr/bin/netbird" status --help > "$out/status-help.txt"
grep -F -- --json "$out/status-help.txt"
# Simulate Ubuntu dependency installation. Do not install package, start daemon,
# call up/login, alter routes, or register a machine in an external account.
apt-get -s --no-install-recommends install "$packages/netbird_0.83.1_linux_amd64.deb" "$packages/netbird-ui_0.83.1_linux_amd64.deb" > "$out/apt-plan.txt"
! grep -q '^Remv ' "$out/apt-plan.txt"
echo 'PASS: exact official CLI and desktop packages reviewed; service not started'
