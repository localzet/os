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
WAIT="${LOCALZET_QEMU_GRUB_WAIT_SECONDS:-420}"
[[ "$WAIT" =~ ^[0-9]+$ ]] && ((WAIT >= 60 && WAIT <= 900)) || {
  echo "Invalid QEMU wait value: $WAIT" >&2
  exit 2
}
# Poll the actual guest framebuffer, not just a boot status line.
# Firmware and GDM greeter frames do not match the Localzet wallpaper.
graphical_seen=0
visual_seen=0
visual_streak=0
for ((elapsed=20; elapsed<=WAIT; elapsed+=20)); do
  if ! kill -0 "$QEMU_PID" 2>/dev/null; then
    echo "QEMU exited before desktop validation" >&2
    exit 1
  fi
  sleep 20
  frame="$OUT/frame-$(printf '%03d' "$elapsed").ppm"
  png="$OUT/frame-$(printf '%03d' "$elapsed").png"
  python3 - "$TMP/monitor.sock" "$frame" "$png" <<'PY'
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
        s.recv(4096)
    except TimeoutError:
        pass

deadline = time.monotonic() + 10
while not Path(ppm).is_file() and time.monotonic() < deadline:
    time.sleep(.25)
if not Path(ppm).is_file():
    raise SystemExit("No QEMU framebuffer screenshot")
im = Image.open(ppm).convert("RGB")
im.save(png)
print("Captured:", im.size)
PY
  if python3 scripts/ci/assert-graphical.py "$OUT/serial.log" >/dev/null 2>&1; then
    graphical_seen=1
  fi
  if python3 scripts/ci/assert-session-visual.py "$png" --report "$OUT/frame-$(printf '%03d' "$elapsed").json"; then
    visual_seen=1
    visual_streak=$((visual_streak + 1))
    cp "$png" "$OUT/screen.png"
    cp "$OUT/frame-$(printf '%03d' "$elapsed").json" "$OUT/visual-check.json"
  else
    visual_streak=0
  fi
  if [[ "$graphical_seen" -eq 1 && "$visual_streak" -ge 3 ]]; then
    echo "PASS: $MODE GRUB boot reached graphical target and rendered Localzet desktop after $elapsed seconds."
    exit 0
  fi
done
if [[ "$graphical_seen" -ne 1 ]]; then
  echo "No systemd graphical.target evidence from guest serial console." >&2
fi
if [[ "$visual_seen" -ne 1 ]]; then
  echo "No recognizable Localzet desktop framebuffer. Inspect captured frames." >&2
fi
# Diagnostic only: once *automatic* boot has already FAILED, attempt
# Ctrl+Alt+F2 to find a GNOME user session displaced by the GDM greeter.
# This capture must NEVER be counted as a successful boot.
python3 - "$TMP/monitor.sock" "$OUT/manual-vt2.png" <<'PY' || true
from pathlib import Path
import socket
import sys
import time
from PIL import Image

monitor, png = sys.argv[1:]
ppm = str(Path(png).with_suffix(".ppm"))
with socket.socket(socket.AF_UNIX) as s:
    s.settimeout(10)
    s.connect(monitor)
    s.sendall(b"sendkey ctrl-alt-f2\n")
time.sleep(5)
with socket.socket(socket.AF_UNIX) as s:
    s.settimeout(10)
    s.connect(monitor)
    s.sendall(("screendump " + ppm + "\n").encode())
deadline = time.monotonic() + 10
while not Path(ppm).is_file() and time.monotonic() < deadline:
    time.sleep(.25)
if Path(ppm).is_file():
    Image.open(ppm).convert("RGB").save(png)
    print("Saved manual-VT diagnostic ONLY:", png)
PY
exit 1
