#!/usr/bin/env bash
# Read-only GRUB boot smoke for BIOS or UEFI using a disposable QEMU VM.
# This checks the ISO's *bootloader* path, unlike the direct-kernel casper test.
set -Eeuo pipefail
ISO="${1:?Usage: bash scripts/ci/qemu-grub-boot.sh ISO bios|uefi [OUT]}"
MODE="${2:?Specify bios or uefi}"
OUT="${3:-$(pwd)/qemu-grub-$MODE}"
case "$MODE" in bios|uefi) ;; *) echo "Invalid mode: $MODE" >&2; exit 2;; esac
[[ -s "$ISO" ]] || { echo "Missing ISO: $ISO" >&2; exit 2; }
ISO="$(realpath -- "$ISO")"
for name in qemu-system-x86_64 python3; do
  command -v "$name" >/dev/null || { echo "Missing tool: $name" >&2; exit 2; }
done
mkdir -p -- "$OUT"
OUT="$(cd -- "$OUT" && pwd -P)"
TMP="$(mktemp -d)"
QEMU_PID=""
cleanup() {
  [[ -z "$QEMU_PID" ]] || { kill "$QEMU_PID" 2>/dev/null || true; wait "$QEMU_PID" 2>/dev/null || true; }
  rm -rf -- "$TMP"
}
trap cleanup EXIT
ARGS=( -machine q35 -accel tcg -smp 2 -m 3072 -no-reboot
       -display none -vga std
       -drive "file=$ISO,if=ide,media=cdrom,readonly=on,format=raw"
       -boot order=d
       -serial "file:$OUT/serial.log"
       -monitor "unix:$TMP/monitor.sock,server=on,wait=off" )
if [[ "$MODE" == uefi ]]; then
  OVMF_CODE="/usr/share/OVMF/OVMF_CODE_4M.fd"
  OVMF_VARS="/usr/share/OVMF/OVMF_VARS_4M.fd"
  [[ -s "$OVMF_CODE" && -s "$OVMF_VARS" ]] || { echo "OVMF 4M firmware missing" >&2; exit 2; }
  cp "$OVMF_VARS" "$TMP/OVMF_VARS.fd"
  ARGS+=( -drive "if=pflash,format=raw,readonly=on,file=$OVMF_CODE"
          -drive "if=pflash,format=raw,file=$TMP/OVMF_VARS.fd" )
fi
printf 'QEMU mode: %s (read-only ISO)\n' "$MODE" > "$OUT/mode.txt"
qemu-system-x86_64 "${ARGS[@]}" > "$OUT/qemu.log" 2>&1 &
QEMU_PID=$!
WAIT="${LOCALZET_QEMU_GRUB_WAIT_SECONDS:-240}"
[[ "$WAIT" =~ ^[0-9]+$ ]] && ((WAIT >= 60 && WAIT <= 900)) || {
  echo "Invalid wait: $WAIT" >&2; exit 2;
}
for ((elapsed=0; elapsed<WAIT; elapsed+=5)); do
  if ! kill -0 "$QEMU_PID" 2>/dev/null; then echo "QEMU died before guest boot" >&2; exit 1; fi
  if python3 scripts/ci/assert-graphical.py "$OUT/serial.log" >/dev/null 2>&1 2>/dev/null; then
    sleep 20
    break
  fi
  sleep 5
done
python3 - "$TMP/monitor.sock" "$OUT/screen.ppm" "$OUT/screen.png" <<'PY'
from pathlib import Path
import socket
import sys
import time
from PIL import Image
monitor, ppm, png = sys.argv[1:]
with socket.socket(socket.AF_UNIX) as s:
    deadline = time.monotonic() + 15
    while True:
        try:
            s.connect(monitor)
            break
        except OSError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(.25)
    s.sendall(("screendump " + ppm + "\n").encode())
    s.settimeout(5)
    try:
        print(s.recv(4096).decode(errors="replace"))
    except TimeoutError:
        pass
deadline = time.monotonic() + 10
while not Path(ppm).is_file() and time.monotonic() < deadline:
    time.sleep(.25)
if not Path(ppm).is_file():
    raise SystemExit("No QEMU framebuffer screenshot")
im = Image.open(ppm).convert("RGB")
im.save(png)
colors = len(set(im.resize((80, 50)).getdata()))
print("Screenshot:", im.size, "sample colors:", colors)
if colors < 15:
    raise SystemExit("QEMU framebuffer appears blank")
PY
if ! python3 scripts/ci/assert-graphical.py "$OUT/serial.log" >/dev/null 2>&1; then
  echo "Boot unverified: guest did not report reaching graphical.target on serial (check guest screenshot)" >&2
  exit 1
fi
python3 scripts/ci/assert-session-visual.py "$OUT/screen.png" --report "$OUT/visual-check.json"
echo "PASS: $MODE GRUB boot reached graphical.target with the P1 wallpaper visible."
