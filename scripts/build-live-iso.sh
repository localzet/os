#!/usr/bin/env bash
# Build experimental Ubuntu 26.04 GNOME Live ISO. Does not install to a disk.
set -Eeuo pipefail
if [[ "$EUID" -ne 0 ]]; then echo "Run as root only in a disposable VM/CI builder." >&2; exit 2; fi
if [[ "$(dpkg --print-architecture)" != amd64 ]]; then echo "amd64 only." >&2; exit 2; fi
PROJECT="$(cd -- "$(dirname "$0")/.." && pwd -P)"
OUT="${LOCALZET_BUILD_DIR:-$PROJECT/out/live}"
mkdir -p -- "$OUT"
OUT="$(cd "$OUT" && pwd -P)"
case "$OUT" in
  "$PROJECT"|"/"|"/tmp"|"/home"|"/usr"|"/etc") echo "Unsafe output directory." >&2; exit 2;;
esac
ROOT="$OUT/rootfs"
ISO_TREE="$OUT/iso-tree"
ISO="$OUT/localzet-os-p1-amd64.iso"
if [[ -e "$ROOT" || -e "$ISO_TREE" || -e "$ISO" ]]; then
  echo "Build already exists; use another empty output directory: $OUT" >&2
  exit 2
fi
for tool in debootstrap chroot mount umount mksquashfs grub-mkrescue xorriso sha256sum; do
  command -v "$tool" >/dev/null || { echo "Missing command: $tool" >&2; exit 2; }
done
MOUNTED=()
cleanup() {
  local i
  for ((i=${#MOUNTED[@]}-1; i>=0; i--)); do
    umount -R "${MOUNTED[$i]}" 2>/dev/null || umount "${MOUNTED[$i]}" 2>/dev/null || true
  done
}
trap cleanup EXIT
echo "Building Localzet OS Live P1 from Ubuntu 26.04 (resolute)"
mkdir -p "$ROOT" "$ISO_TREE/casper" "$ISO_TREE/boot/grub" "$ISO_TREE/.disk"
debootstrap --arch=amd64 --variant=minbase resolute "$ROOT" http://archive.ubuntu.com/ubuntu
cat > "$ROOT/etc/apt/sources.list" <<'SOURCES'
deb http://archive.ubuntu.com/ubuntu resolute main restricted universe multiverse
deb http://archive.ubuntu.com/ubuntu resolute-updates main restricted universe multiverse
deb http://security.ubuntu.com/ubuntu resolute-security main restricted universe multiverse
SOURCES
printf 'localzet\n' > "$ROOT/etc/hostname"
printf '127.0.0.1 localhost\n127.0.1.1 localzet\n' > "$ROOT/etc/hosts"
install -d "$ROOT/usr/share/gnome-shell/extensions" "$ROOT/usr/share/backgrounds/localzet"
cp -R "$PROJECT/extensions/localzet-shell@localzet.com" "$ROOT/usr/share/gnome-shell/extensions/"
install -m644 "$PROJECT/assets/wallpapers/aurora.svg" "$ROOT/usr/share/backgrounds/localzet/aurora.svg"
install -Dm755 "$PROJECT/scripts/iso/configure-rootfs.sh" "$ROOT/tmp/localzet-configure-rootfs"
install -d "$ROOT/opt/localzet-os/src" "$ROOT/opt/localzet-os/config"
cp -R "$PROJECT/src/localzet" "$ROOT/opt/localzet-os/src/"
cp -R "$PROJECT/config/modules" "$ROOT/opt/localzet-os/config/"
cat > "$ROOT/usr/local/bin/localzet-modules" <<'MODULES'
#!/bin/sh
PYTHONPATH=/opt/localzet-os/src exec /usr/bin/python3 -m localzet.cli "$@"
MODULES
chmod 0755 "$ROOT/usr/local/bin/localzet-modules"
mount --bind /dev "$ROOT/dev"; MOUNTED+=("$ROOT/dev")
mount -t proc proc "$ROOT/proc"; MOUNTED+=("$ROOT/proc")
mount --bind /sys "$ROOT/sys"; MOUNTED+=("$ROOT/sys")
chroot "$ROOT" /usr/bin/env DEBIAN_FRONTEND=noninteractive /bin/bash /tmp/localzet-configure-rootfs
chroot "$ROOT" /usr/local/bin/localzet-modules validate
cleanup
MOUNTED=()
rm -f "$ROOT/tmp/localzet-configure-rootfs"
KERNEL="$(find "$ROOT/boot" -maxdepth 1 -type f -name 'vmlinuz-*' | sort -V | tail -1)"
if [[ -z "$KERNEL" ]]; then echo "Kernel missing." >&2; exit 1; fi
VERSION="${KERNEL##*/vmlinuz-}"
INITRD="$ROOT/boot/initrd.img-$VERSION"
if [[ ! -s "$INITRD" ]]; then echo "Initramfs missing: $INITRD" >&2; exit 1; fi
cp "$KERNEL" "$ISO_TREE/casper/vmlinuz"
cp "$INITRD" "$ISO_TREE/casper/initrd"
chroot "$ROOT" dpkg-query -W -f='${Package} ${Version}\n' > "$ISO_TREE/casper/filesystem.manifest"
du -sb "$ROOT" | awk '{print $1}' > "$ISO_TREE/casper/filesystem.size"
mksquashfs "$ROOT" "$ISO_TREE/casper/filesystem.squashfs" -comp xz -b 1M -noappend -processors 2
cat > "$ISO_TREE/boot/grub/grub.cfg" <<'GRUB'
set timeout=5
set default=0
search --no-floppy --set=root --label LOCALZET_OS
menuentry "Try Localzet OS (experimental Live)" {
  linux /casper/vmlinuz boot=casper username=localzet hostname=localzet quiet splash console=tty0 console=ttyS0,115200n8 systemd.show_status=1 systemd.log_target=console
  initrd /casper/initrd
}
menuentry "Try Localzet OS (serial diagnostics)" {
  linux /casper/vmlinuz boot=casper username=localzet hostname=localzet console=tty0 console=ttyS0,115200n8 loglevel=7
  initrd /casper/initrd
}
GRUB
printf 'Localzet OS P1 experimental Live (Ubuntu 26.04)\n' > "$ISO_TREE/.disk/info"
# casper-md5check verifies hashes during boot. Include every source ISO file
# present before grub-mkrescue adds its bootloader-generated files.
(cd "$ISO_TREE" && find . -type f ! -name md5sum.txt -print0 | sort -z | xargs -0 md5sum > md5sum.txt)
grub-mkrescue -o "$ISO" "$ISO_TREE" -- -volid LOCALZET_OS
test -s "$ISO"
(cd "$OUT" && sha256sum "$(basename "$ISO")" > SHA256SUMS)
echo "ISO: $ISO"
ls -lh "$ISO"
