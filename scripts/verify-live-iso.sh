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
xorriso -indev "$ISO" -find /casper -type f -print > "$REPORT_DIR/casper-files.txt"
grep -qx '/casper/vmlinuz' "$REPORT_DIR/casper-files.txt"
grep -qx '/casper/initrd' "$REPORT_DIR/casper-files.txt"
grep -qx '/casper/filesystem.squashfs' "$REPORT_DIR/casper-files.txt"
xorriso -indev "$ISO" -report_el_torito plain > "$REPORT_DIR/boot-report.txt" 2>&1
if ! grep -Eiq 'BIOS|x86|UEFI|EFI' "$REPORT_DIR/boot-report.txt"; then
  echo 'Boot records not recognized; inspect boot-report.txt' >&2
  exit 1
fi
echo "ISO structural checks passed. This does not prove it boots."
