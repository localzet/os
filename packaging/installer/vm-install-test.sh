#!/usr/bin/env bash
# Test-only installer. Never distributed in the ordinary Live ISO.
# Invoked in a private mount namespace of a disposable QEMU guest.
set -Eeuo pipefail
[[ $EUID == 0 && -d /sys/firmware/efi ]] || exit 2
grep -qw 'boot=casper' /proc/cmdline
grep -qw 'localzet.install-test=1' /proc/cmdline
grep -qiE 'qemu|kvm' /sys/class/dmi/id/product_name /sys/class/dmi/id/sys_vendor
[[ "$(findmnt -n -o FSTYPE /)" == overlay ]]
source=/cdrom/casper/filesystem.squashfs
[[ -f "$source" ]]
byid=/dev/disk/by-id/virtio-LZ_INSTALL_TARGET
keep=/dev/disk/by-id/virtio-LZ_KEEP_DISK
udevadm settle
[[ -L "$byid" && -L "$keep" ]]
disk="$(readlink -e "$byid")"
other="$(readlink -e "$keep")"
[[ -b "$disk" && -b "$other" && "$disk" != "$other" ]]
[[ "$(lsblk -dn -o SERIAL "$disk")" == LZ_INSTALL_TARGET ]]
[[ "$(lsblk -dn -o SERIAL "$other")" == LZ_KEEP_DISK ]]
[[ "$(lsblk -dn -o TYPE "$disk")" == disk ]]
[[ "$(lsblk -dn -o RO "$disk")" == 0 ]]
[[ "$(lsblk -dn -o SIZE -b "$disk")" == 34359738368 ]]
[[ "$(lsblk -nr -o NAME "$disk" | wc -l)" == 1 ]]
[[ -z "$(lsblk -nr -o MOUNTPOINTS "$disk")" ]]
# Require a genuinely blank target; don't overwrite an existing partition table.
[[ -z "$(wipefs -n --noheadings -o TYPE "$disk")" ]]
trap 'printf "\nLOCALZET_INSTALL_FAILED line=%s\n" "$LINENO" > /dev/ttyS0' ERR
password="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
printf '%s\n' "$password" | /bin/bash /usr/lib/localzet/install-engine.sh vm "$byid" localzet-test "$disk" "$(stat -Lc '%t:%T' "$byid")"
unset password
printf '\nLOCALZET_INSTALL_COMPLETE\n' > /dev/ttyS0
