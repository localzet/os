#!/usr/bin/env bash
# ISO structural verification only; QEMU is required to verify actual boot.
set -Eeuo pipefail
ISO="${1:?Usage: bash scripts/verify-live-iso.sh path/to/image.iso}"
[[ -s "$ISO" ]] || { echo "Missing or empty ISO: $ISO" >&2; exit 2; }
DIR="$(dirname -- "$ISO")"
REPORT_DIR="${LOCALZET_REPORT_DIR:-$(pwd)/iso-reports}"
mkdir -p -- "$REPORT_DIR"
for tool in xorriso sha256sum; do command -v "$tool" >/dev/null || exit 2; done
if [[ -f "$DIR/SHA256SUMS" ]]; then (cd "$DIR" && sha256sum --check SHA256SUMS); fi
xorriso -sh_style_result on -indev "$ISO" -find /casper -type f -exec echo -- > "$REPORT_DIR/casper-files.txt"
for required in /casper/vmlinuz /casper/initrd /casper/filesystem.squashfs; do
  if ! grep -Fqx -- "$required" "$REPORT_DIR/casper-files.txt"; then
    printf 'Missing required ISO file: %s\n' "$required" >&2
    cat "$REPORT_DIR/casper-files.txt" >&2
    exit 1
  fi
done
xorriso -indev "$ISO" -report_el_torito plain > "$REPORT_DIR/boot-report.txt" 2>&1
for mode in BIOS UEFI; do
  if ! grep -Eq "El Torito boot img[[:space:]]*:[[:space:]]*[0-9]+[[:space:]]+$mode" "$REPORT_DIR/boot-report.txt"; then
    printf 'Missing El Torito %s boot entry; inspect %s\n' "$mode" "$REPORT_DIR/boot-report.txt" >&2
    exit 1
  fi
done
echo "ISO structural checks passed. This does not prove it boots."
