#!/usr/bin/env bash
# Boot a Live ISO using QEMU direct kernel boot, without disks, writes or KVM.
# This verifies the casper rootfs path. GRUB BIOS/UEFI are independent gates.
set -Eeuo pipefail
ISO="${1:?Usage: bash scripts/ci/qemu-live-diagnostics.sh ISO [OUTPUT_DIR]}"
OUT="${2:-$(pwd)/qemu-diagnostics}"
if [[ ! -s "$ISO" ]]; then echo "ISO not found: $ISO" >&2; exit 2; fi
for tool in qemu-system-x86_64 xorriso python3 timeout; do
  command -v "$tool" >/dev/null || { echo "Missing: $tool" >&2; exit 2; }
done
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd -P)"
TMP="$(mktemp -d)"
PID=""
cleanup() {
  [[ -z "$PID" ]] || { kill "$PID" 2>/dev/null || true; wait "$PID" 2>/dev/null || true; }
  rm -rf -- "$TMP"
}
trap cleanup EXIT
xorriso -osirrox on -indev "$ISO" -extract /casper/vmlinuz "$TMP/vmlinuz" -extract /casper/initrd "$TMP/initrd" > "$OUT/extract.log" 2>&1
SOCKET="$TMP/monitor.sock"
SERIAL="$OUT/serial.log"
qemu-system-x86_64 -machine q35 -accel tcg -m 3072 -smp 2 \
  -kernel "$TMP/vmlinuz" -initrd "$TMP/initrd" \
  -append "boot=casper username=localzet hostname=localzet console=tty0 console=ttyS0,115200n8 systemd.show_status=1 systemd.log_target=console loglevel=7" \
  -cdrom "$ISO" -boot order=d -no-reboot -display none -vga virtio \
  -monitor "unix:$SOCKET,server=on,wait=off" -serial "file:$SERIAL" \
  > "$OUT/qemu.log" 2>&1 &
PID=$!
SECONDS_TO_WAIT="${LOCALZET_QEMU_BOOT_WAIT_SECONDS:-300}"
if [[ ! "$SECONDS_TO_WAIT" =~ ^[0-9]+$ ]] || ((SECONDS_TO_WAIT < 60 || SECONDS_TO_WAIT > 900)); then
  echo "Invalid QEMU wait value" >&2
  exit 2
fi
# Capture throughout startup. GNOME can appear long after graphical.target.
graphical_seen=0
visual_seen=0
for ((elapsed=20; elapsed<=SECONDS_TO_WAIT; elapsed+=20)); do
  sleep 20
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "QEMU exited prematurely" >&2
    exit 1
  fi
  if python3 scripts/ci/assert-graphical.py "$SERIAL" >/dev/null 2>&1; then
    graphical_seen=1
  fi
  FRAME="$OUT/frame-${elapsed}.ppm"
  PNG="$OUT/frame-${elapsed}.png"
  python3 - "$SOCKET" "$FRAME" "$PNG" <<'PY'
import socket
import sys
import time
from pathlib import Path
from PIL import Image

monitor, frame, png = sys.argv[1:]
with socket.socket(socket.AF_UNIX) as sock:
    deadline = time.monotonic() + 10
    while True:
        try:
            sock.connect(monitor)
            break
        except OSError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(.25)
    sock.sendall(("screendump " + frame + "\n").encode())
    sock.settimeout(5)
    try:
        sock.recv(4096)
    except TimeoutError:
        pass
deadline = time.monotonic() + 10
while not Path(frame).is_file() and time.monotonic() < deadline:
    time.sleep(.25)
if not Path(frame).is_file():
    raise SystemExit("QEMU screenshot absent")
Image.open(frame).convert("RGB").save(png)
PY
  if python3 scripts/ci/assert-session-visual.py "$PNG" --report "$OUT/visual-${elapsed}.json"; then
    visual_seen=1
    cp "$PNG" "$OUT/guest-screen.png"
    cp "$OUT/visual-${elapsed}.json" "$OUT/visual-check.json"
  fi
  if [[ "$graphical_seen" -eq 1 && "$visual_seen" -eq 1 ]]; then
    echo "PASS: direct-kernel Live boot rendered branded desktop after ${elapsed}s."
    exit 0
  fi
done
echo "Direct-kernel boot not proven: serial=${graphical_seen}, framebuffer=${visual_seen}" >&2
exit 1
