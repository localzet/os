#!/usr/bin/env python3
"""Boot an ISO in an isolated QEMU guest and require a serial readiness marker."""
import argparse
import json
import socket
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


def capture_screen(monitor: Path, output: Path) -> None:
    """Best-effort screenshot; never changes the readiness result."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(5)
        connection.connect(str(monitor))
        with connection.makefile("rwb") as stream:
            def read_response(request_id):
                while True:
                    line = stream.readline()
                    if not line:
                        raise OSError("QMP disconnected")
                    message = json.loads(line)
                    if message.get("id") == request_id:
                        if "error" in message:
                            raise OSError(str(message["error"]))
                        return message
            greeting = json.loads(stream.readline())
            if "QMP" not in greeting:
                raise OSError("Invalid QMP greeting")
            for request_id, command, arguments in (
                (1, "qmp_capabilities", {}),
                (2, "screendump", {"filename": str(output)}),
            ):
                stream.write((json.dumps({"execute": command, "arguments": arguments,
                                          "id": request_id}) + "\n").encode())
                stream.flush()
                read_response(request_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iso", type=Path)
    parser.add_argument("--firmware", choices=("bios", "uefi"), required=True)
    parser.add_argument("--ovmf-code", type=Path)
    parser.add_argument("--ovmf-vars", type=Path)
    parser.add_argument("--marker", required=True,
                        help="Exact guest serial marker emitted after readiness checks")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()
    if not args.marker.strip() or args.timeout <= 0:
        parser.error("nonempty marker and positive timeout required")
    if not args.iso.is_file():
        parser.error("ISO does not exist")
    qemu = shutil.which("qemu-system-x86_64")
    if not qemu:
        parser.error("qemu-system-x86_64 is required")
    if args.firmware == "uefi" and not all(
        p and p.is_file() for p in (args.ovmf_code, args.ovmf_vars)
    ):
        parser.error("UEFI requires matching OVMF code and vars images")
    args.log.parent.mkdir(parents=True, exist_ok=True)
    marker = args.marker.encode()
    with tempfile.TemporaryDirectory(prefix="localzet-qemu-") as tmp:
        serial = Path(tmp) / "serial.log"
        monitor = Path(tmp) / "qmp.sock"
        screen = Path(tmp) / "screen.ppm"
        accel = "kvm" if os.access("/dev/kvm", os.R_OK | os.W_OK) else "tcg"
        cpu = "host" if accel == "kvm" else "max"
        cmd = [qemu, "-machine", "q35", "-accel", accel, "-cpu", cpu,
               "-m", "4096", "-smp", "2", "-nic", "none",
               "-display", "none", "-monitor", "none",
               "-qmp", f"unix:{monitor},server=on,wait=off",
               "-no-reboot", "-boot", "order=d", "-cdrom",
               str(args.iso.resolve()), "-serial", f"file:{serial}"]
        if args.firmware == "uefi":
            vars_copy = Path(tmp) / "vars.fd"
            shutil.copyfile(args.ovmf_vars, vars_copy)
            cmd += ["-drive", f"if=pflash,format=raw,readonly=on,file={args.ovmf_code.resolve()}",
                    "-drive", f"if=pflash,format=raw,file={vars_copy}"]
        print(f"QEMU firmware={args.firmware} accel={accel} cpu={cpu}", flush=True)
        with tempfile.TemporaryFile() as errors:
            proc = subprocess.Popen(cmd, stdout=errors, stderr=errors)
            found = False
            try:
                deadline = time.monotonic() + args.timeout
                while time.monotonic() < deadline:
                    if serial.exists() and marker in serial.read_bytes().splitlines():
                        found = True
                        break
                    if proc.poll() is not None:
                        break
                    time.sleep(0.5)
            finally:
                if proc.poll() is None:
                    try:
                        capture_screen(monitor, screen)
                        if screen.is_file():
                            shutil.copyfile(screen, args.log.with_suffix(".ppm"))
                    except (OSError, ValueError) as exc:
                        print(f"QMP screenshot unavailable: {exc}", file=sys.stderr)
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                errors.seek(0)
                with args.log.open("wb") as log:
                    if serial.exists():
                        log.write(serial.read_bytes())
                    log.write(b"\n--- QEMU diagnostics ---\n")
                    log.write(errors.read())
        if not found:
            print(f"FAIL: readiness marker not observed; see {args.log}", file=sys.stderr)
            return 1
        print(f"PASS: {args.firmware} ({accel}) guest readiness marker observed; see {args.log}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
