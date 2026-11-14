#!/usr/bin/env bash
# Only in a disposable rootfs build. Bundle must come from the same trusted
# checkout's successful package job, not an arbitrary downloaded artifact.
set -Eeuo pipefail
[[ ${EUID} == 0 && ${LOCALZET_DISPOSABLE_VM:-} == 1 && $# == 3 ]]
root="$(realpath -e -- "$1")"
bundle="$(realpath -e -- "$2")"
repo="$(realpath -e -- "$3")"
[[ "$root" != / && -d "$root/var/lib/dpkg" && -d "$bundle" ]]
[[ "$(cat "$bundle/BUILD-COMMIT")" == "$(git -C "$repo" rev-parse HEAD)" ]]
# The expected exact two package names are determined by dpkg metadata.
shopt -s nullglob
files=("$bundle"/gnome-control-center_*.deb "$bundle"/gnome-control-center-data_*.deb)
[[ ${#files[@]} == 2 ]]
[[ -f "$bundle/SHA256SUMS" && ! -L "$bundle/SHA256SUMS" ]]
# Avoid accepting arbitrary paths from checksum manifests.
expected="$(for f in "${files[@]}"; do [[ -f "$f" && ! -L "$f" ]]; sha256sum "$f"; done | sed "s|  $bundle/|  |" | sort)"
actual="$(sort "$bundle/SHA256SUMS")"
[[ "$actual" == "$expected" ]] || { echo "Control Center bundle checksum mismatch" >&2; exit 2; }
staging="$(mktemp -d "$root/tmp/localzet-control-center.XXXXXXXX")"
trap 'rm -rf -- "$staging"' EXIT
rel="/tmp/${staging##*/}"
names=()
for f in "${files[@]}"; do
    package="$(dpkg-deb -f "$f" Package)"
    arch="$(dpkg-deb -f "$f" Architecture)"
    version="$(dpkg-deb -f "$f" Version)"
    case "$package:$arch" in
        gnome-control-center:amd64|gnome-control-center-data:all) ;;
        *) echo "Unexpected package metadata" >&2; exit 2 ;;
    esac
    [[ "$(dpkg-deb -f "$f" Source | cut -d' ' -f1)" == gnome-control-center || "$package" == gnome-control-center ]]
    old="$(chroot "$root" dpkg-query -W -f='${Version}' "$package")"
    [[ "$old" == 1:50.* && "$version" == "$old+localzet1" ]] || {
        echo "Ubuntu source version differs from rootfs; rebuild the branded bundle" >&2; exit 2;
    }
    install -m 0644 "$f" "$staging/$package.deb"
    names+=("$rel/$package.deb")
done
[[ -f "$staging/gnome-control-center.deb" && -f "$staging/gnome-control-center-data.deb" ]]
chroot "$root" dpkg -i "${names[@]}"
for package in gnome-control-center gnome-control-center-data; do
    [[ "$(chroot "$root" dpkg-query -W -f='${Version}' "$package")" == *+localzet1 ]]
done
# No version holds or pinning. New Ubuntu security versions must remain
# upgradeable, even if temporarily reverting to stock branding.
install -D -m 0644 "$bundle/SHA256SUMS" "$root/usr/share/doc/localzet-desktop/control-center.SHA256SUMS"
install -D -m 0644 "$bundle/BUILD-COMMIT" "$root/usr/share/doc/localzet-desktop/control-center.BUILD-COMMIT"
echo "PASS: exact source-matched branded Control Center installed into rootfs"
