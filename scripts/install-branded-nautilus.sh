#!/usr/bin/env bash
# Exact trusted same-checkout bundle, only in disposable rootfs builds.
set -Eeuo pipefail
[[ $EUID == 0 && ${LOCALZET_DISPOSABLE_VM:-} == 1 && $# == 3 ]]
root="$(realpath -e -- "$1")"
bundle="$(realpath -e -- "$2")"
repo="$(realpath -e -- "$3")"
[[ "$root" != / && -d "$root/var/lib/dpkg" && -d "$bundle" ]]
[[ -f "$bundle/BUILD-COMMIT" && ! -L "$bundle/BUILD-COMMIT" ]]
[[ "$(cat "$bundle/BUILD-COMMIT")" == "$(git -c "safe.directory=$repo" -C "$repo" rev-parse HEAD)" ]]
shopt -s nullglob
files=("$bundle"/*.deb)
[[ ${#files[@]} == 3 && -f "$bundle/SHA256SUMS" && ! -L "$bundle/SHA256SUMS" ]]
for f in "${files[@]}"; do [[ -f "$f" && ! -L "$f" ]]; done
expected="$(cd "$bundle"; for f in "${files[@]}"; do sha256sum -- "${f##*/}"; done | sort)"
[[ "$(sort "$bundle/SHA256SUMS")" == "$expected" ]]
stage="$(mktemp -d "$root/tmp/localzet-nautilus.XXXXXXXX")"
trap 'rm -rf -- "$stage"' EXIT
rel="/tmp/${stage##*/}"
names=()
for f in "${files[@]}"; do
    package="$(dpkg-deb -f "$f" Package)"
    arch="$(dpkg-deb -f "$f" Architecture)"
    version="$(dpkg-deb -f "$f" Version)"
    case "$package:$arch" in
        nautilus:amd64|nautilus-data:all|libnautilus-extension4:amd64) ;;
        *) echo "Unexpected package: $package:$arch" >&2; exit 2 ;;
    esac
    old="$(chroot "$root" dpkg-query -W -f='${Version}' "$package")"
    [[ "$old" =~ ^([0-9]+:)?50\. && "$version" == "$old+localzet1" ]]
    [[ ! -e "$stage/$package.deb" ]]
    install -m 0644 "$f" "$stage/$package.deb"
    names+=("$rel/$package.deb")
done
for package in nautilus nautilus-data libnautilus-extension4; do
    test -f "$stage/$package.deb"
done
chroot "$root" dpkg -i "${names[@]}"
for package in nautilus nautilus-data libnautilus-extension4; do
    [[ "$(chroot "$root" dpkg-query -W -f='${Version}' "$package")" == *+localzet1 ]]
done
# Do not hold or pin: later Ubuntu security updates must remain installable.
install -D -m 0644 "$bundle/SHA256SUMS" "$root/usr/share/doc/localzet-desktop/nautilus.SHA256SUMS"
install -D -m 0644 "$bundle/BUILD-COMMIT" "$root/usr/share/doc/localzet-desktop/nautilus.BUILD-COMMIT"
echo "PASS: exact-version Executive Nautilus bundle installed"
