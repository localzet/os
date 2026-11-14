#!/usr/bin/env python3
"""QEMU-only test of the exact interactive installation candidate.

All writable disks are newly created temporary files. Test commands are
injected through a QEMU firmware data item and a local desktop terminal; the
candidate ISO contains no automatic test installer or credentials.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import tempfile
import time

LIVE = b"LOCALZET_LIVE_READY"
INSTALL = b"LOCALZET_CANDIDATE_INSTALLED"
READY = b"LOCALZET_CANDIDATE_DESKTOP"
FAIL = b"LOCALZET_CANDIDATE_FAILED"


class Guest:
    def __init__(self, args, directory: Path, disk: Path, script: Path, label: str, live: bool):
        self.serial = args.logs / f"{label}.serial.log"
        self.errors = args.logs / f"{label}.qemu.log"
        self.socket = directory / f"{label}.sock"
        variables = directory / f"{label}.fd"
        shutil.copyfile(args.ovmf_vars, variables)
        self.accel = "kvm" if os.access("/dev/kvm", os.R_OK | os.W_OK) else "tcg"
        cpu = "host" if self.accel == "kvm" else "max"
        command = [
            "qemu-system-x86_64", "-machine", "q35,smm=on", "-accel", self.accel,
            "-global", "driver=cfi.pflash01,property=secure,value=on",
            "-cpu", cpu, "-m", "5120", "-smp", "2", "-nic", "none",
            "-vga", "virtio", "-display", "none", "-monitor", "none", "-no-reboot",
            "-qmp", f"unix:{self.socket},server=on,wait=off",
            "-serial", f"file:{self.serial}",
            "-drive", f"if=pflash,format=raw,readonly=on,file={args.ovmf_code}",
            "-drive", f"if=pflash,format=raw,file={variables}",
            "-drive", f"if=none,id=target,file={disk},format=raw",
            "-device", "nvme,drive=target,serial=LZ_TEST_NVME",
            "-fw_cfg", f"name=opt/localzet/test,file={script}",
        ]
        command += ["-boot", "order=d", "-cdrom", str(args.iso)] if live else ["-boot", "order=c"]
        self.error_stream = self.errors.open("wb")
        self.process = subprocess.Popen(command, stdout=self.error_stream, stderr=self.error_stream)
        self.connection = None
        self.stream = None
        self.sequence = 0

    def connect(self):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                self.connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.connection.settimeout(10)
                self.connection.connect(str(self.socket))
                self.stream = self.connection.makefile("rwb")
                if "QMP" not in json.loads(self.stream.readline()):
                    raise RuntimeError("Invalid QMP greeting")
                self.qmp("qmp_capabilities")
                return
            except OSError:
                self.connection.close()
                time.sleep(0.5)
        raise RuntimeError("QMP unavailable")

    def qmp(self, execute, arguments=None):
        self.sequence += 1
        self.stream.write((json.dumps({"execute": execute, "arguments": arguments or {},
                                       "id": self.sequence}) + "\n").encode())
        self.stream.flush()
        while True:
            line = self.stream.readline()
            if not line:
                raise RuntimeError("QMP disconnected")
            reply = json.loads(line)
            if reply.get("id") == self.sequence:
                if "error" in reply:
                    raise RuntimeError(str(reply["error"]))
                return reply.get("return")

    def key(self, name):
        self.qmp("human-monitor-command", {"command-line": f"sendkey {name} 40"})
        time.sleep(0.12)

    def text(self, value):
        keys = {" ": "spc", "-": "minus", "_": "shift-minus", "/": "slash",
                ".": "dot", ";": "semicolon", "|": "shift-backslash",
                "'": "apostrophe", "=": "equal", ":": "shift-semicolon"}
        for char in value:
            if char in keys:
                self.key(keys[char])
            elif char.isascii() and char.isalnum():
                self.key("shift-" + char.lower() if char.isupper() else char)
            else:
                raise ValueError(f"Unsupported keyboard character {char!r}")

    def launch(self, app):
        self.key("alt-f2")
        time.sleep(1)
        self.text(app)
        self.key("ret")
        time.sleep(6)

    def wait(self, marker, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            lines = self.serial.read_bytes().splitlines() if self.serial.exists() else []
            if marker in lines:
                print(f"PASS: {marker.decode()}", flush=True)
                return
            if FAIL in lines or self.process.poll() is not None:
                break
            time.sleep(1)
        if self.serial.exists():
            print(self.serial.read_bytes()[-30000:].decode(errors="replace"), flush=True)
        raise RuntimeError(f"Missing {marker.decode()}")

    def close(self):
        if self.stream:
            self.stream.close()
        if self.connection:
            self.connection.close()
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.error_stream.close()


def installation_script(password):
    return """#!/bin/bash
set -Eeuo pipefail
exec >/dev/ttyS0 2>&1
trap 'printf "\\nLOCALZET_CANDIDATE_FAILED\\n"' ERR
pgrep -u localzet -f /usr/bin/localzet-installer >/dev/null
findmnt --mountpoint /sys/firmware/efi/efivars || true
for flag in /sys/firmware/efi/efivars/SecureBoot-* /sys/firmware/efi/efivars/SetupMode-*; do
    if test -f "$flag"; then printf '%s: ' "$flag"; od -An -t u1 "$flag"; fi
done
export PYTHONPATH=/opt/localzet-os/src
python3 - <<'PY' | /usr/lib/localzet/installer-backend
import json
from localzet.installer.interactive import eligible_plan, live_source_disk, confirmation_for
from localzet.installer.preflight import read_lsblk
from localzet.installer.target import identity
payload = read_lsblk()
target = next(d for d in payload["blockdevices"] if d.get("serial") == "LZ_TEST_NVME")
plan = eligible_plan(payload, identity(target), live_source_disk())
print(json.dumps({"plan": plan, "confirmation": confirmation_for(plan),
                  "backup_acknowledged": True, "username": "localzet-test",
                  "password": """ + repr(password) + """}))
PY
sync
printf '\\nLOCALZET_CANDIDATE_INSTALLED\\n'
"""


def installed_script():
    return r"""#!/bin/bash
set -Eeuo pipefail
exec >/dev/ttyS0 2>&1
trap 'printf "\nLOCALZET_CANDIDATE_FAILED\n"' ERR
[[ "$(findmnt -n -o FSTYPE /)" == ext4 ]]
[[ "$(findmnt -n -o FSTYPE /boot/efi)" == vfat ]]
for point in / /boot/efi; do
    parent="$(lsblk -dn -o PKNAME "$(findmnt -n -o SOURCE "$point")")"
    [[ "$(lsblk -dn -o SERIAL "/dev/$parent")" == LZ_TEST_NVME ]]
done
if grep -qw boot=casper /proc/cmdline; then exit 2; fi
PYTHONPATH=/opt/localzet-os/src python3 -m localzet.installer.audit /
[[ "$(passwd -S localzet-test | cut -d ' ' -f2)" == P ]]
pgrep -u localzet-test -x gnome-shell >/dev/null
pgrep -u localzet-test -f /usr/bin/localzet-settings >/dev/null
session="$(loginctl list-sessions --no-legend | awk '$3=="localzet-test" && $4=="seat0" {print $1; exit}')"
[[ -n "$session" ]]
[[ "$(loginctl show-session "$session" -p Active --value)" == yes ]]
[[ "$(loginctl show-session "$session" -p Type --value)" == wayland ]]
uid="$(id -u localzet-test)"
runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
    gnome-extensions list --active | grep -Fx localzet-shell@localzet.com
printf '\nLOCALZET_CANDIDATE_DESKTOP\n'
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iso", type=Path)
    parser.add_argument("--ovmf-code", type=Path, required=True)
    parser.add_argument("--ovmf-vars", type=Path, required=True)
    parser.add_argument("--logs", type=Path, required=True)
    args = parser.parse_args()
    for name in ("iso", "ovmf_code", "ovmf_vars"):
        path = getattr(args, name).resolve(strict=True)
        if not path.is_file():
            parser.error(f"{name} must be a regular file")
        setattr(args, name, path)
    args.logs = args.logs.resolve()
    args.logs.mkdir(parents=True, exist_ok=False)
    password = secrets.token_hex(12)
    with tempfile.TemporaryDirectory(prefix="lz-candidate-") as temp:
        directory = Path(temp)
        disk = directory / "target.raw"
        with disk.open("xb") as stream:
            stream.truncate(32 * 1024**3)
        script = directory / "install.sh"
        script.write_text(installation_script(password))
        script.chmod(0o600)
        live = Guest(args, directory, disk, script, "candidate-live", True)
        try:
            live.connect()
            live.wait(LIVE, 480)
            live.launch("localzet-installer")
            live.launch("ptyxis")
            live.text("sudo -n modprobe qemu_fw_cfg; sudo -n bash /sys/firmware/qemu_fw_cfg/by_name/opt/localzet/test/raw")
            live.key("ret")
            live.wait(INSTALL, 1200)
        finally:
            live.close()
        script.write_text(installed_script())
        installed = Guest(args, directory, disk, script, "candidate-installed", False)
        try:
            installed.connect()
            # Installed image has no test service or automatic login.
            # Drive the actual GDM greeter using the ephemeral account.
            time.sleep(45 if installed.accel == "kvm" else 120)
            installed.key("ret")
            time.sleep(4)
            installed.text(password)
            installed.key("ret")
            time.sleep(25 if installed.accel == "kvm" else 60)
            installed.launch("localzet-settings")
            installed.launch("ptyxis")
            installed.text(f"echo {password} | sudo -S modprobe qemu_fw_cfg; echo {password} | sudo -S bash /sys/firmware/qemu_fw_cfg/by_name/opt/localzet/test/raw")
            installed.key("ret")
            installed.wait(READY, 180)
        finally:
            installed.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
