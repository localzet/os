#!/usr/bin/env bash
# Retain and verify the corresponding modified Debian source package.
# Call from the pristine, patched source directory before the binary build.
set -Eeuo pipefail
[[ $# == 4 && $EUID != 0 && "${LOCALZET_DISPOSABLE_VM:-}" == 1 ]]
out="$(realpath -m -- "$1")"
package="$2"
version="$3"
patch="$4"
[[ "$package" =~ ^[a-z0-9][a-z0-9+.-]+$ && "$patch" =~ ^[a-zA-Z0-9._-]+\.patch$ ]]
[[ "$(dpkg-parsechangelog -S Source)" == "$package" ]]
[[ "$(dpkg-parsechangelog -S Version)" == "$version" ]]
[[ -f "debian/patches/$patch" ]]
grep -Fx "$patch" debian/patches/series
test ! -e "$out"
mkdir -p "$out"
dpkg-source -b .
dsc="$(realpath -e -- "../${package}_${version#*:}.dsc")"
# dcmd copies only the descriptor and files listed by that descriptor.
dcmd cp -- "$dsc" "$out/"
test -s "$out/$(basename "$dsc")"
(
    cd "$out"
    sha256sum -- *.dsc *.tar.* > SHA256SUMS
    sha256sum -c SHA256SUMS
)
review="$(mktemp -d)"
trap 'rm -rf -- "$review"' EXIT
dpkg-source -x "$out/$(basename "$dsc")" "$review/source"
(
    cd "$review/source"
    test "$(dpkg-parsechangelog -S Source)" = "$package"
    test "$(dpkg-parsechangelog -S Version)" = "$version"
    grep -Fx "$patch" debian/patches/series
    test -s debian/copyright
)
cmp "debian/patches/$patch" "$review/source/debian/patches/$patch"
printf '%s\n' "$version" > "$out/SOURCE-VERSION"
printf '%s\n' 'Corresponding modified source package retained; redistribution review required.' > "$out/REVIEW-STATUS"
