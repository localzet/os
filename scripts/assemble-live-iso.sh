#!/usr/bin/env bash
# Assemble a Live-only ISO from a prepared, offline Ubuntu 26.04 rootfs.
# Does not mount or partition any device. Run in a disposable build VM.
set -euo pipefail
if [[ $# != 2 ]]; then
    echo "Usage: $0 PREPARED_ROOTFS OUTPUT.iso" >&2
    exit 2
fi
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
root="$(realpath -e -- "$1")"
out="$(realpath -m -- "$2")"
[[ "$root" != / && -d "$root" && "$out" == *.iso && "$out" != "$root/"* && ! -e "$out" ]] || {
    echo "Unsafe rootfs or output path; use a new ISO outside rootfs" >&2; exit 2;
}
for cmd in mksquashfs grub-mkrescue grub-script-check xorriso dpkg-query findmnt; do
    command -v "$cmd" >/dev/null || { echo "Missing $cmd" >&2; exit 2; }
done
for platform in i386-pc x86_64-efi; do
    [[ -d "/usr/lib/grub/$platform" ]] || { echo "Missing GRUB $platform modules" >&2; exit 2; }
done
# Fail closed if the mount inventory fails; process substitution would hide
# findmnt's exit status. JSON preserves mount paths containing spaces.
mount_inventory="$(findmnt --json --output TARGET)"
python3 -c '
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
def visit(nodes):
    for node in nodes:
        target = pathlib.Path(node["target"])
        if target == root or root in target.parents:
            raise SystemExit(f"Rootfs contains a mounted filesystem: {target}")
        visit(node.get("children", []))
visit(json.load(sys.stdin)["filesystems"])
' "$root" <<< "$mount_inventory"
for path in etc/passwd etc/shadow usr/lib/os-release usr/lib/localzet/localzet-live-ready.py; do
    [[ -f "$root/$path" && ! -L "$root/$path" ]] || { echo "Missing or symlinked $path" >&2; exit 2; }
done
grep -Eq '^ID=("localzet"|localzet)$' "$root/usr/lib/os-release" || {
    echo "Not a prepared Localzet rootfs" >&2; exit 2;
}
[[ -L "$root/etc/systemd/system/graphical.target.wants/localzet-live-ready.service" ]] || {
    echo "Live readiness service is not enabled" >&2; exit 2;
}
# Casper must create the temporary account at boot, not ship it in the image.
if grep -q '^localzet:' "$root/etc/passwd" || [[ -e "$root/home/localzet" || -L "$root/home/localzet" ]]; then
    echo "Refusing a rootfs with a pre-created Live account" >&2; exit 2
fi
# Select exactly one installed kernel and its matching initramfs.
shopt -s nullglob
kernels=("$root"/boot/vmlinuz-*)
[[ ${#kernels[@]} == 1 ]] || { echo "Expected exactly one kernel" >&2; exit 2; }
kernel="${kernels[0]}"
release="${kernel##*/vmlinuz-}"
initrd="$root/boot/initrd.img-$release"
[[ -f "$kernel" && ! -L "$kernel" && -f "$initrd" && ! -L "$initrd" ]] || {
    echo "Kernel/initramfs missing or symlinked" >&2; exit 2;
}
mkdir -p -- "$(dirname "$out")"
stage="$(mktemp -d -- "$(dirname "$out")/.localzet-iso.XXXXXX")"
trap 'rm -rf -- "$stage"' EXIT
mkdir -p "$stage/tree/casper" "$stage/tree/boot/grub" "$stage/tree/.disk"
install -m 0644 "$kernel" "$stage/tree/casper/vmlinuz"
install -m 0644 "$initrd" "$stage/tree/casper/initrd"
install -m 0644 "$repo/packaging/live/grub.cfg" "$stage/tree/boot/grub/grub.cfg"
theme="$root/boot/grub/themes/localzet-aurora"
for file in theme.txt background.png logo.png dejavu-20.pf2 dejavu-24.pf2; do
    [[ -f "$theme/$file" && ! -L "$theme/$file" && -s "$theme/$file" ]]
    install -D -m 0644 "$theme/$file" "$stage/tree/boot/grub/themes/localzet-aurora/$file"
done
if [[ "${LOCALZET_INSTALL_TEST:-0}" == 1 ]]; then
    [[ -f "$root/usr/lib/localzet/vm-install-test.sh" ]]
    sed -i 's/boot=casper /boot=casper localzet.install-test=1 /g' "$stage/tree/boot/grub/grub.cfg"
    printf 'Localzet OS VM installation test ONLY\n' > "$stage/tree/.disk/info"
elif [[ "${LOCALZET_INSTALLER:-0}" == 1 ]]; then
    [[ -f "$root/usr/lib/localzet/installer-enabled" && ! -e "$root/usr/lib/localzet/vm-install-test.sh" ]]
    printf 'Localzet OS interactive installation candidate\n' > "$stage/tree/.disk/info"
else
    [[ ! -e "$root/usr/lib/localzet/vm-install-test.sh" && ! -e "$root/usr/lib/localzet/installer-enabled" ]]
    printf 'Localzet OS development Live amd64\n' > "$stage/tree/.disk/info"
fi
grub-script-check "$stage/tree/boot/grub/grub.cfg"
dpkg-query --admindir="$root/var/lib/dpkg" -W -f='${Package} ${Version}\n' > "$stage/tree/casper/filesystem.manifest"
mksquashfs "$root" "$stage/tree/casper/filesystem.squashfs" -noappend -comp zstd -one-file-system
du -sb "$root" | cut -f1 > "$stage/tree/casper/filesystem.size"
# Casper's media verification reads md5sum.txt. The external SHA-256 remains
# the distribution integrity check. Hash only files present before GRUB adds
# its generated boot images.
(
    cd "$stage/tree"
    find . -type f ! -name md5sum.txt -print0 | sort -z | xargs -0 md5sum > md5sum.txt
    md5sum -c md5sum.txt
)
grub-mkrescue -o "$stage/image.iso" "$stage/tree"
# Publish only after a successful build and boot catalog inspection.
xorriso -indev "$stage/image.iso" -report_el_torito plain > "$stage/boot-catalog.txt" 2>&1
grep -q 'BIOS' "$stage/boot-catalog.txt"
grep -q 'UEFI' "$stage/boot-catalog.txt"
mv -n -- "$stage/image.iso" "$out"
[[ ! -e "$stage/image.iso" ]] || { echo "Output appeared during build" >&2; exit 2; }
(cd "$(dirname "$out")" && sha256sum -- "$(basename "$out")") > "$out.sha256"
echo "Live-only ISO assembled: $out"
