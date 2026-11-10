#!/usr/bin/env bash
# Run a Localzet OS Live ISO in an isolated QEMU VM. No physical disks attached.
set -Eeuo pipefail
usage() {
  cat <<'USAGE'
Usage: scripts/run-live-qemu.sh <path/to/localzet.iso> [bios|uefi]

This runs a non-persistent Live VM. It never selects a host disk, and does not
install or modify a physical operating system. Requires qemu-system-x86_64,
and for UEFI the Ubuntu OVMF firmware package. Close the VM to discard changes.
USAGE
}
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then usage; exit 0; fi
ISO="${1:-}"
MODE="${2:-uefi}"
if [[ -z "$ISO" ]]; then usage >&2; exit 2; fi
if [[ "$MODE" != bios && "$MODE" != uefi ]]; then echo "Invalid boot mode: $MODE" >&2; exit 2; fi
[[ -f "$ISO" && -s "$ISO" ]] || { echo "ISO missing or empty: $ISO" >&2; exit 2; }
ISO="$(realpath -- "$ISO")"
command -v qemu-system-x86_64 >/dev/null || { echo "qemu-system-x86_64 is required" >&2; exit 2; }
TMP="$(mktemp -d)"
trap 'rm -rf -- "$TMP"' EXIT
ACCEL=tcg
if [[ -r /dev/kvm && -w /dev/kvm ]]; then ACCEL=kvm; fi
ARGS=(
  -machine q35 -accel "$ACCEL"
  -smp 4 -m 4096 -vga std -display gtk
  -boot order=d
  -drive "file=$ISO,if=ide,media=cdrom,readonly=on,format=raw"
  -nic user,model=e1000
  -no-reboot
)
if [[ "$MODE" == uefi ]]; then
  CODE="/usr/share/OVMF/OVMF_CODE_4M.fd"
  VARS="/usr/share/OVMF/OVMF_VARS_4M.fd"
  [[ -f "$CODE" && -f "$VARS" ]] || { echo "UEFI firmware missing: install ovmf" >&2; exit 2; }
  cp -- "$VARS" "$TMP/OVMF_VARS.fd"
  ARGS+=(
    -drive "if=pflash,format=raw,readonly=on,file=$CODE"
    -drive "if=pflash,format=raw,file=$TMP/OVMF_VARS.fd"
  )
fi
echo "Localzet OS experimental Live ISO | boot=$MODE | accelerator=$ACCEL"
echo "No persistent virtual disk is attached. All changes are discarded on shutdown."
exec qemu-system-x86_64 "${ARGS[@]}"
