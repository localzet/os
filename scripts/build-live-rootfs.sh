#!/usr/bin/env bash
# Run only inside a disposable Ubuntu amd64 build VM, never a workstation.
set -euo pipefail
[[ ${EUID} == 0 && "${LOCALZET_DISPOSABLE_VM:-}" == 1 && $# == 1 ]] || {
    echo "Requires root in disposable VM: LOCALZET_DISPOSABLE_VM=1 $0 NEW_ROOTFS" >&2; exit 2;
}
[[ "$(dpkg --print-architecture)" == amd64 ]] || exit 2
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
root="$(realpath -m -- "$1")"
[[ "$root" != / && ! -e "$root" && ! -L "$root" && "$root" != "$repo" && "$root" != "$repo/"* ]] || {
    echo "Choose a new rootfs outside the source checkout" >&2; exit 2;
}
for tool in mmdebstrap dpkg-deb chroot systemctl; do
    command -v "$tool" >/dev/null || { echo "Missing $tool" >&2; exit 2; }
done
keyring=/usr/share/keyrings/ubuntu-archive-keyring.gpg
[[ -r "$keyring" ]] || { echo "Missing Ubuntu archive keyring" >&2; exit 2; }
build="$(mktemp -d)"
trap 'rm -rf -- "$build"' EXIT
export LOCALZET_REPO="$repo"
export LOCALZET_PACKAGE_VERSION=0.1.0~dev1
bash "$repo/scripts/build-desktop-deb.sh" "$build"
export LOCALZET_DESKTOP_DEB="$build/localzet-desktop_${LOCALZET_PACKAGE_VERSION}_all.deb"
mkdir -p "$(dirname "$root")"
# Use a minimal GNOME stack, not the Ubuntu-branded desktop metapackage.
packages="ubuntu-keyring,ubuntu-minimal,systemd-sysv,linux-generic,linux-firmware,casper,initramfs-tools,dbus,dbus-user-session,gdm3,gnome-session,gnome-shell,gnome-shell-extension-appindicator,gnome-control-center,gnome-settings-daemon,nautilus,ptyxis,network-manager,pipewire-audio,wireplumber,xwayland,libgl1-mesa-dri,fonts-dejavu-core,fonts-noto-core,dconf-cli,locales,language-pack-ru,language-pack-gnome-ru,python3,python3-gi,gir1.2-gtk-4.0,gir1.2-adw-1,pkexec,procps,pciutils,usbutils,nvme-cli,smartmontools,efibootmgr,gparted,gnome-disk-utility,ntfs-3g,exfatprogs,btrfs-progs,gnome-system-monitor,gnome-text-editor,gnome-calculator,gnome-software,file-roller,loupe,papers,epiphany-browser,papirus-icon-theme,plymouth,plymouth-theme-spinner,librsvg2-bin"
if [[ "${LOCALZET_INSTALL_TEST:-0}" == 1 && "${LOCALZET_INSTALLER:-0}" == 1 ]]; then
    echo "Test and interactive installation profiles are mutually exclusive" >&2
    exit 2
fi
if [[ "${LOCALZET_INSTALL_TEST:-0}" == 1 || "${LOCALZET_INSTALLER:-0}" == 1 ]]; then
    export LOCALZET_INSTALL_TEST LOCALZET_INSTALLER
    packages+=",parted,dosfstools,e2fsprogs,squashfs-tools,grub-efi-amd64-bin,grub2-common,sudo"
fi
if [[ "${LOCALZET_WINDOWS:-0}" == 1 ]]; then
    packages+=",wine,wine64,fonts-wine"
fi
mmdebstrap --mode=root --variant=apt --format=directory --architectures=amd64 \
    --keyring="$keyring" --include="$packages" \
    --customize-hook='bash "$LOCALZET_REPO/packaging/live/customize-rootfs.sh" "$1"' \
    resolute "$root" \
    "deb https://archive.ubuntu.com/ubuntu resolute main restricted universe multiverse" \
    "deb https://archive.ubuntu.com/ubuntu resolute-updates main restricted universe multiverse" \
    "deb https://security.ubuntu.com/ubuntu resolute-security main restricted universe multiverse"
echo "Prepared Live rootfs: $root"
