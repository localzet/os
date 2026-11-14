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
root="$(mktemp -d /run/localzet-install.XXXXXX)"
cleanup() {
    if mountpoint -q "$root"; then umount -R "$root" || true; fi
    rmdir "$root" || true
}
trap cleanup EXIT
trap 'printf "\nLOCALZET_INSTALL_FAILED line=%s\n" "$LINENO" > /dev/ttyS0' ERR
# The only destructive device is the exact, previously validated QEMU target.
[[ "$(readlink -e "$byid")" == "$disk" ]]
parted -s "$disk" mklabel gpt
parted -s "$disk" mkpart ESP fat32 1MiB 513MiB
parted -s "$disk" set 1 esp on
parted -s "$disk" mkpart root ext4 513MiB 100%
udevadm settle
for i in 1 2; do
    for attempt in $(seq 1 20); do
        [[ -b "${byid}-part$i" ]] && break
        sleep 1
    done
    [[ -b "${byid}-part$i" ]]
    [[ "$(lsblk -dn -o PKNAME "${byid}-part$i")" == "${disk##*/}" ]]
done
esp="$(readlink -e "${byid}-part1")"
part="$(readlink -e "${byid}-part2")"
mkfs.vfat -F 32 -n LOCALZETEFI "$esp"
mkfs.ext4 -F -L LOCALZETROOT "$part"
mount "$part" "$root"
unsquashfs -f -d "$root" "$source"
mkdir -p "$root/boot/efi"
mount "$esp" "$root/boot/efi"
root_uuid="$(blkid -s UUID -o value "$part")"
esp_uuid="$(blkid -s UUID -o value "$esp")"
[[ -n "$root_uuid" && -n "$esp_uuid" ]]
printf 'UUID=%s / ext4 defaults 0 1\nUUID=%s /boot/efi vfat umask=0077 0 2\n' "$root_uuid" "$esp_uuid" > "$root/etc/fstab"
# The SquashFS is the pristine build root, not the running Live overlay.
# Remove all test/Live hooks and generate an authenticated installed account.
systemctl --root="$root" disable localzet-live-ready.service localzet-install-test.service
rm -f "$root/usr/lib/localzet/localzet-live-ready.py" \
    "$root/usr/lib/systemd/system/localzet-live-ready.service" \
    "$root/usr/lib/localzet/vm-install-test.sh" \
    "$root/usr/lib/systemd/system/localzet-install-test.service"
test ! -e "$root/home/localzet"
! grep -q '^localzet:' "$root/etc/passwd"
# The current audit expects a regular os-release file rather than a symlink.
rm -f "$root/etc/os-release"
cp "$root/usr/lib/os-release" "$root/etc/os-release"
for dir in dev proc sys; do
    mkdir -p "$root/$dir"
    mount --rbind "/$dir" "$root/$dir"
    mount --make-rslave "$root/$dir"
done
chroot "$root" useradd -m -s /bin/bash -G sudo localzet-test
password="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
printf 'localzet-test:%s\n' "$password" | chroot "$root" chpasswd
unset password
chroot "$root" passwd -l root
chroot "$root" dpkg --purge casper
chroot "$root" update-initramfs -u -k all
# Use only the selected disk's mounted ESP; never write firmware NVRAM.
chroot "$root" grub-install --target=x86_64-efi --efi-directory=/boot/efi \
    --bootloader-id=Localzet --removable --no-nvram
mkdir -p "$root/etc/default/grub.d"
cat > "$root/etc/default/grub.d/99-localzet-test.cfg" <<'EOF'
GRUB_DISABLE_OS_PROBER=true
GRUB_CMDLINE_LINUX="console=tty0 console=ttyS0,115200n8 systemd.show_status=1 systemd.mask=serial-getty@ttyS0.service"
EOF
chroot "$root" update-grub
[[ -f "$root/boot/efi/EFI/BOOT/BOOTX64.EFI" ]]
# Installed boot verification exists only in the VM test image.
install -m 0644 /usr/lib/localzet/vm-installed-ready.sh "$root/usr/lib/localzet/vm-installed-ready.sh"
install -m 0644 /usr/lib/systemd/system/localzet-installed-test.service "$root/usr/lib/systemd/system/localzet-installed-test.service"
systemctl --root="$root" enable localzet-installed-test.service
# Audit source is part of the desktop package; no hashes are printed.
PYTHONPATH=/opt/localzet-os/src python3 -m localzet.installer.audit "$root"
# Reset image identity after chroot operations, before first real boot.
truncate -s 0 "$root/etc/machine-id"
rm -f "$root/var/lib/dbus/machine-id"
ln -s /etc/machine-id "$root/var/lib/dbus/machine-id"
sync
umount -R "$root"
rmdir "$root"
trap - EXIT ERR
printf '\nLOCALZET_INSTALL_COMPLETE\n' > /dev/ttyS0
