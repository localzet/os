#!/usr/bin/env bash
# Shared UEFI installation engine. The VM and interactive entry points use
# this same implementation. Never execute against a nonblank target.
set -Eeuo pipefail
[[ $# == 5 ]] || exit 2
mode="$1"
byid="$2"
username="$3"
expected_disk="$4"
expected_devno="$5"
IFS= read -r password
[[ $EUID == 0 && -d /sys/firmware/efi ]] || exit 2
grep -qw 'boot=casper' /proc/cmdline
[[ "$(findmnt -n -o FSTYPE /)" == overlay ]]
[[ "$username" =~ ^[a-z][a-z0-9_-]{0,30}$ && "$username" != localzet && "$username" != root ]]
[[ ${#password} -ge 10 && ${#password} -le 128 && "$password" != *:* && "$password" != *$'\r'* ]]
[[ "$byid" =~ ^/dev/disk/by-id/[^/]+$ && ! "$byid" =~ -part[0-9]+$ ]]
case "$mode" in
    vm)
        grep -qw 'localzet.install-test=1' /proc/cmdline
        grep -qiE 'qemu|kvm' /sys/class/dmi/id/product_name /sys/class/dmi/id/sys_vendor
        [[ "$byid" == /dev/disk/by-id/virtio-LZ_INSTALL_TARGET ]]
        ;;
    interactive)
        [[ -f /usr/lib/localzet/installer-enabled ]]
        if grep -qw 'localzet.install-test=1' /proc/cmdline; then exit 2; fi
        ;;
    *) exit 2 ;;
esac
source=/cdrom/casper/filesystem.squashfs
[[ -f "$source" ]]
# The private mount namespace still shares block devices. Serialize this
# installer's own processes and revalidate identity before device operations.
mkdir -p /run/lock
exec 9>/run/lock/localzet-install.lock
flock -n 9
udevadm settle
disk="$(readlink -e "$byid")"
same_disk() {
    [[ -b "$byid" && "$(readlink -e "$byid")" == "$expected_disk" &&
       "$(stat -Lc '%t:%T' "$byid")" == "$expected_devno" &&
       "$(lsblk -dn -o TYPE "$byid")" == disk &&
       "$(lsblk -dn -o RO "$byid")" == 0 ]]
}
same_disk
[[ "$disk" == "$expected_disk" ]]
[[ "$(lsblk -dn -o SIZE -b "$byid")" -ge 34359738368 ]]
[[ "$(lsblk -nr -o NAME "$byid" | wc -l)" == 1 ]]
mountpoints="$(lsblk -nr -o MOUNTPOINTS "$byid")"
[[ -z "$mountpoints" ]]
signatures="$(wipefs --no-act --noheadings --output TYPE "$byid")"
[[ -z "$signatures" ]]
# Check the contents of the media before creating any partition.
(cd /cdrom && md5sum -c md5sum.txt)
same_disk
root="$(mktemp -d /run/localzet-install.XXXXXX)"
cleanup() {
    if mountpoint -q "$root"; then umount -R "$root" || true; fi
    rmdir "$root" || true
}
trap cleanup EXIT
# The only destructive device is the exact, previously validated QEMU target.
same_disk
same_disk
parted -s "$byid" mklabel gpt
same_disk
parted -s "$byid" mkpart ESP fat32 1MiB 513MiB
same_disk
parted -s "$byid" set 1 esp on
same_disk
parted -s "$byid" mkpart root ext4 513MiB 100%
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
same_disk
[[ "$(lsblk -dn -o PKNAME "$esp")" == "${disk##*/}" ]]
mkfs.vfat -F 32 -n LOCALZETEFI "$esp"
same_disk
[[ "$(lsblk -dn -o PKNAME "$part")" == "${disk##*/}" ]]
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
systemctl --root="$root" disable localzet-live-ready.service
if [[ "$mode" == vm ]]; then
    systemctl --root="$root" disable localzet-install-test.service
fi
rm -f "$root/usr/lib/localzet/localzet-live-ready.py" \
    "$root/usr/lib/systemd/system/localzet-live-ready.service" \
    "$root/usr/lib/localzet/vm-install-test.sh" \
    "$root/usr/lib/systemd/system/localzet-install-test.service" \
    "$root/usr/lib/localzet/install-engine.sh" \
    "$root/usr/lib/localzet/installer-backend" \
    "$root/usr/lib/localzet/installer-enabled" \
    "$root/usr/bin/localzet-installer" \
    "$root/usr/share/applications/com.localzet.Installer.desktop"
test ! -e "$root/home/localzet"
if grep -q '^localzet:' "$root/etc/passwd"; then exit 2; fi
# The current audit expects a regular os-release file rather than a symlink.
rm -f "$root/etc/os-release"
cp "$root/usr/lib/os-release" "$root/etc/os-release"
for dir in dev proc sys; do
    mkdir -p "$root/$dir"
    mount --rbind "/$dir" "$root/$dir"
    mount --make-rslave "$root/$dir"
done
chroot "$root" useradd -m -s /bin/bash -G sudo "$username"
printf '%s:%s\n' "$username" "$password" | chroot "$root" chpasswd
unset password
chroot "$root" passwd -l root
printf "localzet-pc\n" > "$root/etc/hostname"
printf "127.0.0.1 localhost\n127.0.1.1 localzet-pc\n::1 localhost ip6-localhost ip6-loopback\n" > "$root/etc/hosts"
chroot "$root" dpkg --purge casper
chroot "$root" update-initramfs -u -k all
# Use only the selected disk's mounted ESP; never write firmware NVRAM.
chroot "$root" grub-install --target=x86_64-efi --efi-directory=/boot/efi \
    --bootloader-id=Localzet --removable --no-nvram
mkdir -p "$root/etc/default/grub.d"
printf 'GRUB_DISABLE_OS_PROBER=true\n' > "$root/etc/default/grub.d/90-localzet.cfg"
if [[ "$mode" == vm ]]; then
    printf '%s\n' 'GRUB_CMDLINE_LINUX="console=tty0 console=ttyS0,115200n8 systemd.show_status=1 systemd.mask=serial-getty@ttyS0.service"' > "$root/etc/default/grub.d/99-localzet-test.cfg"
fi
chroot "$root" update-grub
[[ -f "$root/boot/efi/EFI/BOOT/BOOTX64.EFI" ]]
# Installed boot verification exists only in the VM test image.
if [[ "$mode" == vm ]]; then
    install -m 0644 /usr/lib/localzet/vm-installed-ready.sh "$root/usr/lib/localzet/vm-installed-ready.sh"
    install -m 0644 /usr/lib/systemd/system/localzet-installed-test.service "$root/usr/lib/systemd/system/localzet-installed-test.service"
    systemctl --root="$root" enable localzet-installed-test.service
fi
# Audit source is part of the desktop package; no hashes are printed.
PYTHONPATH=/opt/localzet-os/src python3 -m localzet.installer.audit "$root"
# Reset image identity after chroot operations, before first real boot.
truncate -s 0 "$root/etc/machine-id"
rm -f "$root/var/lib/dbus/machine-id"
ln -s /etc/machine-id "$root/var/lib/dbus/machine-id"
sync
umount -R "$root"
rmdir "$root"
trap - EXIT
echo "Localzet OS installation completed successfully"
