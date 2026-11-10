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
SECONDS_TO_WAIT="${LOCALZET_QEMU_BOOT_WAIT_SECONDS:-150}"
if [[ ! "$SECONDS_TO_WAIT" =~ ^[0-9]+$ ]] || ((SECONDS_TO_WAIT < 10 || SECONDS_TO_WAIT > 900)); then
  echo "Invalid QEMU wait value" >&2
  exit 2
fi
for ((i=0;i<SECONDS_TO_WAIT;i+=5)); do
  if ! kill -0 "$PID" 2>/dev/null; then echo "QEMU exited prematurely" >&2; exit 1; fi
  if grep -Eiq 'Reached target Graphical Interface|Reached target graphical.target' "$SERIAL" 2>/dev/null; then break; fi
  sleep 5
done
python3 - "$SOCKET" "$OUT/guest-screen.ppm" <<'PY'
import socket
import sys
import time
socket_path, screenshot = sys.argv[1:]
with socket.socket(socket.AF_UNIX) as sock:
    deadline = time.monotonic() + 10
    while True:
        try:
            sock.connect(socket_path)
            break
        except OSError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.2)
    sock.sendall(("screendump " + screenshot + "\n").encode("utf-8"))
    sock.settimeout(5)
    try:
        print(sock.recv(4096).decode("utf-8", "replace"))
    except TimeoutError:
        pass
PY
if grep -Eiq 'Reached target Graphical Interface|Reached target graphical.target' "$SERIAL"; then
  echo "Direct-kernel casper boot reached graphical.target."
else
  echo "QEMU ran, but graphical.target not confirmed. Inspect logs and screenshot." >&2
  exit 1
fi
