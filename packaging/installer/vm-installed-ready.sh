#!/usr/bin/env bash
set -Eeuo pipefail
! grep -qw 'boot=casper' /proc/cmdline
[[ "$(findmnt -n -o FSTYPE /)" == ext4 ]]
[[ -d /sys/firmware/efi ]]
[[ "$(findmnt -n -o FSTYPE /boot/efi)" == vfat ]]
disk="$(readlink -e /dev/disk/by-id/virtio-LZ_INSTALL_TARGET)"
[[ -b "$disk" ]]
for mount in / /boot/efi; do
    source="$(findmnt -n -o SOURCE "$mount")"
    [[ "$(lsblk -dn -o PKNAME "$source")" == "${disk##*/}" ]]
done
[[ ! -e /dev/disk/by-id/virtio-LZ_KEEP_DISK ]]
[[ ! -e /dev/disk/by-id/virtio-LZ_INSTALL_ISO ]]
getent passwd localzet-test >/dev/null
[[ "$(passwd -S localzet-test | cut -d ' ' -f2)" == P ]]
! getent passwd localzet >/dev/null
PYTHONPATH=/opt/localzet-os/src python3 -m localzet.installer.audit /
for attempt in $(seq 1 90); do
    if systemctl is-active --quiet display-manager.service && pgrep -x gnome-shell >/dev/null; then
        printf '\nLOCALZET_INSTALLED_READY\n' > /dev/ttyS0
        exit 0
    fi
    sleep 2
done
exit 1
