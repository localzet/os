#!/usr/bin/env bash
set -Eeuo pipefail
[[ $# == 2 && $EUID != 0 ]]
deb="$(realpath -e "$1")"
out="$(realpath -e "$2")"
stage="$(mktemp -d)"
trap 'rm -rf -- "$stage"' EXIT
dpkg-deb -I "$deb" > "$out/control.txt"
dpkg-deb -c "$deb" > "$out/files.txt"
dpkg-deb -e "$deb" "$stage/control"
dpkg-deb -x "$deb" "$stage/root"
for script in preinst postinst prerm postrm config triggers; do
    if [[ -f "$stage/control/$script" ]]; then
        cp "$stage/control/$script" "$out/$script.txt"
    fi
done
test -f "$stage/root/usr/share/applications/com.localzet.usernet.desktop"
grep -Fx 'Icon=com.localzet.usernet' "$stage/root/usr/share/applications/com.localzet.usernet.desktop"
grep -E '^Exec=' "$stage/root/usr/share/applications/com.localzet.usernet.desktop" > "$out/desktop-exec.txt"
find "$stage/root" -type f -perm /6000 -print > "$out/setid.txt"
test ! -s "$out/setid.txt"
apt-get -s --no-install-recommends install "$deb" > "$out/apt-plan.txt"
! grep -q '^Remv ' "$out/apt-plan.txt"
echo 'PASS: original UserNet package and dependency plan reviewed; no helper or TUN started'
