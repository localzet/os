#!/usr/bin/env bash
# Canonical checksum names shared by the builder and rootfs installer.
set -Eeuo pipefail
[[ $# == 1 ]]
cd "$(realpath -e -- "$1")"
shopt -s nullglob
files=(*.deb)
[[ ${#files[@]} == 3 ]] || { echo "Expected exactly three Nautilus DEBs" >&2; exit 2; }
for f in "${files[@]}"; do
    [[ -f "$f" && ! -L "$f" && "$f" =~ ^[A-Za-z0-9.+~:_-]+\.deb$ ]] || { echo "Invalid bundle filename" >&2; exit 2; }
done
sha256sum -- "${files[@]}" | LC_ALL=C sort
