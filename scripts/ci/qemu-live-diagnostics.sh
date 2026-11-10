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
  -append "boot=casper username=localzet hostname=localzet console=ttyS0,115200n8 systemd.show_status=1 systemd.log_target=console loglevel=7" \
  -cdrom "$ISO" -boot order=d -no-reboot -display none -vga std \
  -monitor "unix:$SOCKET,server=on,wait=off" -serial "file:$SERIAL" \
  > "$OUT/qemu.log" 2>&1 &
PID=$!
SECONDS_TO_WAIT="${LOCALZET_QEMU_BOOT_WAIT_SECONDS:-240}"
if [[ ! "$SECONDS_TO_WAIT" =~ ^[0-9]+$ ]] || ((SECONDS_TO_WAIT < 10 || SECONDS_TO_WAIT > 900)); then
  echo "Invalid QEMU wait value" >&2
  exit 2
fi
for ((i=0;i<SECONDS_TO_WAIT;i+=5)); do
  if ! kill -0 "$PID" 2>/dev/null; then echo "QEMU exited prematurely" >&2; exit 1; fi
  if python3 scripts/ci/assert-graphical.py "$SERIAL" >/dev/null 2>&1 2>/dev/null; then break; fi
  sleep 5
done
# The graphical login may take a few more seconds after systemd reaches graphical.target.
if python3 scripts/ci/assert-graphical.py "$SERIAL" >/dev/null 2>&1 2>/dev/null; then
  sleep 20
fi
# Multiple snapshots avoid accepting an old SeaBIOS frame as a GNOME desktop.
if ! python3 scripts/ci/assert-graphical.py "$SERIAL" >/dev/null 2>&1; then
  echo "No graphical.target marker in serial log." >&2
  exit 1
fi
passed=0
for attempt in 1 2 3 4; do
  FRAME="$OUT/screen-attempt-${attempt}.ppm"
  PNG="$OUT/screen-attempt-${attempt}.png"
  python3 - "$SOCKET" "$FRAME" "$PNG" <<'PY'
import socket
import sys
import time
from pathlib import Path
from PIL import Image
socket_path, frame, png = sys.argv[1:]
with socket.socket(socket.AF_UNIX) as sock:
    deadline = time.monotonic() + 10
    while True:
        try:
            sock.connect(socket_path)
            break
        except OSError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(.2)
    sock.sendall(("screendump " + frame + "\n").encode())
    sock.settimeout(5)
    try:
        print(sock.recv(4096).decode(errors="replace"))
    except TimeoutError:
        pass
deadline = time.monotonic() + 10
while not Path(frame).is_file() and time.monotonic() < deadline:
    time.sleep(.2)
if not Path(frame).is_file():
    raise SystemExit("QEMU screenshot absent")
image = Image.open(frame).convert("RGB")
image.save(png)
print("Captured:", image.size)
PY
  if python3 scripts/ci/assert-session-visual.py "$PNG" --report "$OUT/visual-attempt-${attempt}.json"; then
    cp "$PNG" "$OUT/guest-screen.png"
    cp "$OUT/visual-attempt-${attempt}.json" "$OUT/visual-check.json"
    echo "PASS: graphical.target with Localzet wallpaper visible (attempt $attempt)"
    passed=1
    break
  fi
  echo "Attempt $attempt: no recognizable Localzet wallpaper yet."
  sleep 12
done
if [[ "$passed" != 1 ]]; then
  echo "No visually verified frame after four captures; inspect serial and PNGs." >&2
  exit 1
fi

