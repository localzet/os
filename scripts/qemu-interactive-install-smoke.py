#!/usr/bin/env python3
"""QEMU-only test of the exact interactive installation candidate.

All writable disks are newly created temporary files. Test commands are
injected through a QEMU firmware data item and a local desktop terminal; the
candidate ISO contains no automatic test installer or credentials.
"""
from __future__ import annotations

import argparse
import base64
import importlib.util
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
WINE_READY = b"LOCALZET_CANDIDATE_WINE_READY"
LOCK_READY = b"LOCALZET_CANDIDATE_LOCKED"
FAIL = b"LOCALZET_CANDIDATE_FAILED"


def ensure_ci_kvm_access(device: Path = Path("/dev/kvm")) -> bool:
    """Refresh only this disposable GitHub runner's KVM ACL between guest boots."""
    if not device.exists():
        return False
    if os.access(device, os.R_OK | os.W_OK):
        return True
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return False
    try:
        subprocess.run(
            ["sudo", "setfacl", "-m", f"u:{os.getuid()}:rw", str(device)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"KVM ACL refresh failed: {exc}", flush=True)
        return False
    if os.access(device, os.R_OK | os.W_OK):
        print("PASS: refreshed CI /dev/kvm ACL before next guest", flush=True)
        return True
    print("KVM remains unavailable after ACL refresh; this guest will use TCG", flush=True)
    return False
LOCK_RECHECK = b"LOCALZET_CANDIDATE_STILL_LOCKED"
CONTAINERS_CAPTURE_READY = b"LOCALZET_CANDIDATE_CONTAINERS_CAPTURE_READY"


def foreign_fixture_module():
    spec = importlib.util.spec_from_file_location("foreign_fixture", Path(__file__).with_name("qemu-install-smoke.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evidence_module():
    spec = importlib.util.spec_from_file_location('visual_evidence', Path(__file__).with_name('visual-evidence.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Guest:
    def __init__(self, args, directory: Path, disk: Path, script: Path, label: str, live: bool, foreign: Path | None = None):
        self.serial = args.logs / f"{label}.serial.log"
        self.errors = args.logs / f"{label}.qemu.log"
        self.screen = args.logs / f"{label}.ppm"
        self.socket = directory / f"{label}.sock"
        variables = directory / f"{label}.fd"
        shutil.copyfile(args.ovmf_vars, variables)
        ensure_ci_kvm_access()
        self.accel = "kvm" if os.access("/dev/kvm", os.R_OK | os.W_OK) else "tcg"
        # The runner can lose /dev/kvm between boots; retain evidence.
        try:
            device = os.stat("/dev/kvm")
            kvm_state = f"mode={device.st_mode & 0o777:o} uid={device.st_uid} gid={device.st_gid}"
        except OSError as exc:
            kvm_state = f"unavailable: {exc}"
        print(f"{label}: QEMU accelerator={self.accel}; /dev/kvm {kvm_state}", flush=True)
        with (args.logs / "accelerators.tsv").open("a", encoding="utf-8") as stream:
            stream.write(f"{label}\t{self.accel}\t{kvm_state}\n")
        cpu = "host" if self.accel == "kvm" else "max"
        command = [
            "qemu-system-x86_64", "-machine", "q35,smm=on,usb=on", "-accel", self.accel,
            "-global", "driver=cfi.pflash01,property=secure,value=on",
            "-cpu", cpu, "-m", "6144", "-smp", "4", "-nic", "none",
            "-vga", "virtio", "-device", "usb-tablet", "-display", "none", "-monitor", "none", "-no-reboot",
            "-qmp", f"unix:{self.socket},server=on,wait=off",
            "-serial", f"file:{self.serial}",
            "-drive", f"if=pflash,format=raw,readonly=on,file={args.ovmf_code}",
            "-drive", f"if=pflash,format=raw,file={variables}",
            "-drive", f"if=none,id=target,file={disk},format=raw",
            "-device", "nvme,drive=target,serial=LZ_TEST_NVME",
            "-fw_cfg", f"name=opt/localzet/test,file={script}",
            "-fw_cfg", f"name=opt/localzet/fixture,file={args.fixture}",
        ]
        if not live and args.fixture32 is not None:
            command += ["-fw_cfg", f"name=opt/localzet/fixture32,file={args.fixture32}",
                        "-fw_cfg", f"name=opt/localzet/msi,file={args.msi_fixture}"]
        if live and foreign is not None:
            command += foreign_fixture_module().drive(foreign, "foreign", "LZ_KEEP_DISK")
        if live and args.boot_media == "usb":
            # Attach the unmodified hybrid ISO as a read-only USB mass-storage
            # device, not as a CD-ROM. This exercises the real USB source
            # exclusion path in the privileged installer.
            command += [
                "-device", "qemu-xhci,id=installusb",
                "-drive", f"if=none,id=installmedia,format=raw,readonly=on,file={args.iso}",
                "-device", "usb-storage,bus=installusb.0,drive=installmedia,removable=on,bootindex=1",
            ]
        elif live:
            command += ["-boot", "order=d", "-cdrom", str(args.iso)]
        else:
            command += ["-boot", "order=c"]
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
        time.sleep(0.22 if self.accel == "kvm" else 0.35)

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

    def click(self, x, y):
        self.qmp("input-send-event", {"events": [
            {"type": "abs", "data": {"axis": "x", "value": x}},
            {"type": "abs", "data": {"axis": "y", "value": y}},
            {"type": "btn", "data": {"down": True, "button": "left"}},
            {"type": "btn", "data": {"down": False, "button": "left"}},
        ]})
        time.sleep(1)

    def wake_display(self):
        # Pointer motion only; no clicks, keys, password or unlock request.
        self.qmp("input-send-event", {"events": [
            {"type": "abs", "data": {"axis": "x", "value": 16384}},
            {"type": "abs", "data": {"axis": "y", "value": 16384}},
        ]})

    def visual_capture(self, stage, region=None, wake=False, attempts=8):
        evidence = evidence_module()
        path = self.screen.with_name(f"{self.screen.stem}-{stage}.ppm")
        for attempt in range(attempts):
            if wake:
                self.wake_display()
            time.sleep(2)
            self.capture(stage)
            if not path.is_file():
                continue
            metrics = evidence.visual_metrics(path, region)
            print(stage, "visual evidence", metrics, flush=True)
            if evidence.meaningful(metrics):
                if stage == "native-lock":
                    desktop = self.screen.with_name(f"{self.screen.stem}-desktop-before-console.ppm")
                    if not desktop.is_file():
                        raise RuntimeError("Missing pre-lock desktop capture for wallpaper comparison")
                    similarity = evidence.wallpaper_similarity(desktop, path)
                    print("native-lock wallpaper similarity:", round(similarity, 4), flush=True)
                    if similarity < 0.55:
                        raise RuntimeError(f"Lock screen lost the installed desktop wallpaper (similarity={similarity:.3f})")
                return
        raise RuntimeError(f"{stage}: blank or insufficient screenshot evidence")

    def office_document(self):
        # The guest captures the editor's own X11 drawable, not the host
        # screen region. Transfer only this synthetic test document window.
        prefix = b"LOCALZET_CANDIDATE_OFFICE_PNG "
        lines = self.serial.read_bytes().splitlines()
        matches = [line[len(prefix):] for line in lines if line.startswith(prefix)]
        if len(matches) != 1 or len(matches[0]) > 2 * 1024**2:
            raise RuntimeError("Missing, duplicate or oversized Office window evidence")
        image = base64.b64decode(matches[0], validate=True)
        if not image.startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError("Invalid Office PNG evidence")
        path = self.screen.with_name(f"{self.screen.stem}-office-document.png")
        path.write_bytes(image)
        evidence = evidence_module()
        metrics = evidence.visual_metrics(path)
        ink = evidence.document_ink(path)
        print("Office document drawable:", metrics, "blue fixture ink:", ink, flush=True)
        if not evidence.meaningful(metrics) or ink < 250:
            raise RuntimeError("Office document pixels missing")
        return path

    def office_region(self):
        lines = self.serial.read_text(errors="replace").splitlines()
        line = next(line for line in reversed(lines)
                    if line.startswith("LOCALZET_CANDIDATE_OFFICE_GEOMETRY "))
        x, y, w, h = map(int, line.split()[1:])
        # Exclude titlebar and outer wallpaper; inspect central app content.
        return (x + w//10, y + h//10, w*8//10, h*8//10)

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
            if CONTAINERS_CAPTURE_READY in lines and not getattr(self, "_containers_qmp_captured", False):
                self.wake_display()
                time.sleep(2)
                self.capture("containers-window")
                path = self.screen.with_name(f"{self.screen.stem}-containers-window.ppm")
                geometry_lines = [line for line in lines
                                  if line.startswith(b"LOCALZET_CANDIDATE_CONTAINERS_GEOMETRY ")]
                if len(geometry_lines) != 1:
                    raise RuntimeError("Missing or duplicate Containers window geometry")
                values = geometry_lines[0].split()
                if len(values) != 5:
                    raise RuntimeError("Invalid Containers window geometry")
                x, y, width, height = map(int, values[1:])
                if width < 600 or height < 400:
                    raise RuntimeError("Containers window is too small for visual acceptance")
                if not path.is_file() or path.stat().st_size == 0:
                    raise RuntimeError("Missing Containers compositor capture")
                metrics = evidence_module().visual_metrics(path, (x, y, width, height))
                print("Containers window visual evidence:", metrics, flush=True)
                if not evidence_module().meaningful(metrics):
                    raise RuntimeError("Containers window capture is blank or visually insufficient")
                self._containers_qmp_captured = True
            if marker in lines:
                print(f"PASS: {marker.decode()}", flush=True)
                return
            # Capture the compositor output while the guest is still displaying
            # the document, independently of the XWayland drawable capture.
            if b"LOCALZET_CANDIDATE_OFFICE_CAPTURE_READY" in lines and not getattr(self, "_office_qmp_captured", False):
                self.wake_display()
                time.sleep(2)
                self.capture("office-compositor")
                self._office_qmp_captured = True
            if any(line.startswith(FAIL) for line in lines) or self.process.poll() is not None:
                break
            time.sleep(1)
        if self.serial.exists():
            lines = self.serial.read_bytes().splitlines()
            # Do not dump megabytes of base64 screenshot data into CI logs.
            filtered = b"\n".join(line for line in lines
                                  if not line.startswith((b"LOCALZET_CANDIDATE_OFFICE_PNG ", b"LOCALZET_CANDIDATE_OFFICE_FAILED_PNG ")))
            print(filtered[-30000:].decode(errors="replace"), flush=True)
        self.capture()
        raise RuntimeError(f"Missing {marker.decode()}")

    def capture(self, stage=None):
        try:
            self.qmp("screendump", {"filename": str(self.screen.with_name(f"{self.screen.stem}-{stage}.ppm") if stage else self.screen)})
        except (OSError, RuntimeError, ValueError) as error:
            print(f"QMP capture unavailable: {error}", flush=True)

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


def installation_script(password, boot_media, expect_foreign=False):
    return """#!/bin/bash
set -Eeuo pipefail
exec >/dev/ttyS0 2>&1
trap 'printf "\\nLOCALZET_CANDIDATE_FAILED\\n"' ERR
printf '\\nLOCALZET_CANDIDATE_INSTALL_STARTED\\n'
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
if """ + repr(expect_foreign) + """:
    foreign = next(d for d in payload["blockdevices"] if d.get("serial") == "LZ_KEEP_DISK")
    assert foreign.get("path") != target.get("path")
    assert len(foreign.get("children", [])) == 2, "Existing GPT fixture must be visible"
    print("PASS: existing foreign GPT disk present", file=__import__("sys").stderr)
source_disk = live_source_disk()
expected_media = """ + repr(boot_media) + """
if expected_media == "usb":
    assert source_disk is not None, "USB boot source must resolve to a physical device"
    source = next(d for d in payload["blockdevices"] if d.get("path") == source_disk)
    assert source.get("tran") == "usb", "Boot source must be a USB mass-storage disk"
    assert source_disk != target.get("path")
    print("PASS: USB media excluded from installation target", file=__import__("sys").stderr)
else:
    assert source_disk is None, "Expected an optical boot source"
plan = eligible_plan(payload, identity(target), source_disk)
print(json.dumps({"plan": plan, "confirmation": confirmation_for(plan),
                  "backup_acknowledged": True, "username": "localzet-test",
                  "password": """ + repr(password) + """}))
PY
sync
printf '\\nLOCALZET_CANDIDATE_INSTALLED\\n'
"""



def foreign_refusal_script(password, boot_media):
    """Exercise the privileged backend's existing multiple-disk refusal."""
    return """#!/bin/bash
set -Eeuo pipefail
exec >/dev/ttyS0 2>&1
trap 'printf "\\nLOCALZET_CANDIDATE_FAILED\\n"' ERR
printf '\\nLOCALZET_CANDIDATE_INSTALL_STARTED\\n'
pgrep -u localzet -f /usr/bin/localzet-installer >/dev/null
export PYTHONPATH=/opt/localzet-os/src
python3 - <<'PY'
import json
import subprocess
from localzet.installer.interactive import live_source_disk, confirmation_for
from localzet.installer.preflight import read_lsblk
from localzet.installer.target import identity, read_only_target_plan
payload = read_lsblk()
target = next(d for d in payload["blockdevices"] if d.get("serial") == "LZ_TEST_NVME")
foreign = next(d for d in payload["blockdevices"] if d.get("serial") == "LZ_KEEP_DISK")
assert target["path"] != foreign["path"]
assert len(foreign.get("children", [])) == 2
source = live_source_disk()
if """ + repr(boot_media) + """ == "usb":
    assert source is not None and source not in (target["path"], foreign["path"])
    assert next(d for d in payload["blockdevices"] if d.get("path") == source)["tran"] == "usb"
else:
    assert source is None
plan = read_only_target_plan(payload, identity(target))
request = {"plan": plan, "confirmation": confirmation_for(plan),
           "backup_acknowledged": True, "username": "localzet-test",
           "password": """ + repr(password) + """}
result = subprocess.run(["/usr/lib/localzet/installer-backend"],
                        input=json.dumps(request), text=True, capture_output=True, timeout=60)
assert result.returncode == 2, result.returncode
assert "Для первой версии отключите все остальные диски" in result.stderr, result.stderr
fresh = read_lsblk()
target_after = next(d for d in fresh["blockdevices"] if d.get("serial") == "LZ_TEST_NVME")
assert not target_after.get("children") and not target_after.get("pttype") and not target_after.get("fstype")
assert not subprocess.check_output(["wipefs", "--no-act", "--noheadings", "--output", "TYPE", target_after["path"]], text=True).strip()
print("PASS: privileged backend refused additional disk; target still blank")
PY
printf '\\nLOCALZET_CANDIDATE_FOREIGN_REFUSED\\n'
"""


def installed_script(archive_profile=None, containers=False, office=False, executive_review=False, native_files=False, office_render_mode="default", branded_control_center=False, windows_matrix=False, telegram=False, network_preload=False):
    if office_render_mode not in ("default", "software-disable-gpu", "fresh-profile", "isolated-x11"):
        raise ValueError("Invalid Office render mode")
    if office_render_mode != "default" and not (office and executive_review):
        raise ValueError("Office rendering diagnostics require executive office review")
    script = r"""#!/bin/bash
set -Eeuo pipefail
exec >/dev/ttyS0 2>&1
trap 'printf "\nLOCALZET_CANDIDATE_FAILED line=%s status=%s\n" "$LINENO" "$?"' ERR
[[ "$(findmnt -n -o FSTYPE /)" == ext4 ]]
[[ "$(findmnt -n -o FSTYPE /boot/efi)" == vfat ]]
for point in / /boot/efi; do
    parent="$(lsblk -dn -o PKNAME "$(findmnt -n -o SOURCE "$point")")"
    [[ "$(lsblk -dn -o SERIAL "/dev/$parent")" == LZ_TEST_NVME ]]
done
if grep -qw boot=casper /proc/cmdline; then exit 2; fi
PYTHONPATH=/opt/localzet-os/src python3 -m localzet.installer.audit /
test -x /usr/bin/localzet-recovery
/usr/bin/localzet-recovery > /run/localzet-recovery-check.json
python3 - <<'PY'
import json
from pathlib import Path
report = json.loads(Path("/run/localzet-recovery-check.json").read_text())
assert report["live_session"] is False, report
assert report["package_audit"] == "clean", report
assert report["kernel"]["running_pair_present"], report
assert report["grub"]["running_normal_entry"], report
assert report["grub"]["running_recovery_entry"], report
assert report["root_filesystem"] == "ext4" and report["esp_filesystem"] == "vfat", report
assert report["writes_performed"] is False and report["rollback_verified"] is False, report
print(json.dumps(report, sort_keys=True))
print("PASS: installed recovery diagnostic and kernel menu entries")
PY
[[ "$(passwd -S localzet-test | cut -d ' ' -f2)" == P ]]
pgrep -u localzet-test -x gnome-shell >/dev/null
[[ -x /usr/lib/localzet/install-nectarlink ]]
[[ -x /usr/bin/wine ]]
[[ -f /usr/share/polkit-1/actions/org.localzet.install-nectarlink.policy ]]
# The validation console is a separate authenticated TTY. Find the actual
# Wayland session, return to its VT, then require it to be active.
session=""
while read -r candidate _; do
    if [[ "$(loginctl show-session "$candidate" -p Name --value)" == localzet-test &&
          "$(loginctl show-session "$candidate" -p Seat --value)" == seat0 &&
          "$(loginctl show-session "$candidate" -p Type --value)" == wayland ]]; then
        session="$candidate"
        break
    fi
done < <(loginctl list-sessions --no-legend)
[[ -n "$session" ]]
vt="$(loginctl show-session "$session" -p VTNr --value)"
[[ "$vt" =~ ^[1-9][0-9]*$ ]]
chvt "$vt"
for attempt in $(seq 1 20); do
    [[ "$(loginctl show-session "$session" -p Active --value)" == yes ]] && break
    sleep 1
done
[[ "$(loginctl show-session "$session" -p Active --value)" == yes ]]
uid="$(id -u localzet-test)"
# Launch from the real authenticated GNOME user manager, not a burst of
# Alt+F2 keystrokes that can race the compositor and TTY switch.
launch_app() {
    local app="$1" pattern="$2"
    runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
        systemd-run --user --collect --unit="localzet-candidate-$app" "/usr/bin/$app"
    for attempt in $(seq 1 45); do
        if pgrep -u localzet-test -f "$pattern" >/dev/null; then return 0; fi
        sleep 1
    done
    echo "Application did not launch: $app"
    return 1
}
launch_app_x11() {
    local app="$1" pattern="$2"
    runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
        systemd-run --user --collect --unit="localzet-candidate-$app" \
        --setenv=GDK_BACKEND=x11 "/usr/bin/$app"
    for attempt in $(seq 1 45); do
        if pgrep -u localzet-test -f "$pattern" >/dev/null; then return 0; fi
        sleep 1
    done
    echo "Application did not launch: $app"
    return 1
}
home="$(getent passwd localzet-test | cut -d: -f6)"
test -s "$home/.local/share/org.gnome.Ptyxis/palettes/aurora.palette"
test "$(runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" gsettings get org.gnome.Ptyxis default-profile-uuid)" = "'4e6f25d9af1244aa896f5b028bf7a020'"
test "$(runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" gsettings get org.gnome.Ptyxis.Profile:/org/gnome/Ptyxis/Profiles/4e6f25d9af1244aa896f5b028bf7a020/ palette)" = "'xterm'"
launch_app ptyxis /usr/bin/ptyxis
launch_app localzet-settings /usr/bin/localzet-settings
launch_app localzet-windows /usr/bin/localzet-windows
launch_app localzet-connect /usr/bin/localzet-connect
runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
    gnome-extensions list --active | grep -Fx localzet-shell@localzet.com
runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
    gnome-extensions list --active | grep -Fx ubuntu-appindicators@ubuntu.com
runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
    gdbus call --session --dest org.kde.StatusNotifierWatcher --object-path /StatusNotifierWatcher \
    --method org.freedesktop.DBus.Properties.Get org.kde.StatusNotifierWatcher IsStatusNotifierHostRegistered | grep -F true
# Stage host-built test data outside the installed image. No credentials
# or testing service are baked into the distribution.
install -d -m 0755 /run/localzet-candidate-check
printf '\nLOCALZET_CANDIDATE_FIXTURE_COPY\n'
install -m 0644 /sys/firmware/qemu_fw_cfg/by_name/opt/localzet/fixture/raw \
    /run/localzet-candidate-check/smoke.exe
test -s /run/localzet-candidate-check/smoke.exe
runuser -u localzet-test -- env PYTHONPATH=/opt/localzet-os/src /usr/bin/python3 - <<'SHORTCUTTEST'
from pathlib import Path
from localzet.windows_shortcuts import ShortcutStore
store = ShortcutStore()
fixture = Path("/run/localzet-candidate-check/smoke.exe")
key = store.save(fixture, "ci-smoke", "Localzet original test application")
try:
    assert store.load(key)["profile"] == "ci-smoke"
    assert store.load(key)["file"] == str(fixture)
    desktop = store.apps / ("com.localzet.WindowsApp." + key + ".desktop")
    assert "Exec=/usr/bin/localzet-windows --shortcut " + key in desktop.read_text()
finally:
    store.remove(key)
assert fixture.is_file()
print("PASS: installed Windows menu shortcut roundtrip; EXE preserved")
SHORTCUTTEST
sha256sum /run/localzet-candidate-check/smoke.exe
printf '\nLOCALZET_CANDIDATE_FIXTURE_READY\n'
cat > /run/localzet-candidate-check/run-wine.sh <<'USERTEST'
#!/bin/bash
set -Eeuo pipefail
[[ $EUID != 0 ]]
data="$(mktemp -d "$HOME/.localzet-wine-ci.XXXXXXXX")"
printf 'Wine fixture filesystem:\n'
df -h "$data"
df -i "$data"
cleanup_wine() {
    local result=$?
    trap - EXIT
    if [[ -n "${WINESERVER:-}" && -x "$WINESERVER" ]]; then
        for prefix in "$data/localzet/windows/prefixes/"*; do
            [[ -d "$prefix" ]] || continue
            if ! WINEPREFIX="$prefix" timeout 30 "$WINESERVER" -w; then
                printf 'Wine server still active; retaining test prefix: %s\n' "$prefix" >&2
                exit 1
            fi
        done
    fi
    rm -rf -- "$data"
    exit "$result"
}
trap cleanup_wine EXIT
export XDG_DATA_HOME="$data" WINEDLLOVERRIDES="mscoree,mshtml=" WINEDEBUG=-all
export WINEPREFIX="$data/localzet/windows/prefixes/ci-smoke"
mkdir -p "$WINEPREFIX"
wineboot --init
server="$(command -v wineserver || true)"
if [[ -z "$server" ]]; then
    while IFS= read -r path; do
        case "$path" in
            */wineserver|*/wineserver64)
                if [[ -x "$path" && -f "$path" ]]; then server="$path"; break; fi ;;
        esac
    done < <(dpkg -L wine64 libwine wine-common)
fi
[[ -x "$server" ]]
export WINESERVER="$server"
"$WINESERVER" -w
set +e
timeout 240 python3 /opt/localzet-os/src/localzet/windows_runtime.py /run/localzet-candidate-check/smoke.exe --profile ci-smoke --run
status=$?
set -e
printf 'Installed Wine fixture exit code: %s\n' "$status"
"$WINESERVER" -w
test "$status" -eq 42
test -s "$WINEPREFIX/system.reg"
USERTEST
chmod 0755 /run/localzet-candidate-check/run-wine.sh
printf '\nLOCALZET_CANDIDATE_DESKTOP\n'
# Use the GNOME user's systemd manager, which inherits the real graphical
# environment. The fixture remains unprivileged, with no console focus needed.
printf '\nLOCALZET_CANDIDATE_WINE_START\n'
runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
    systemd-run --user --wait --pipe --collect /usr/bin/timeout 300 /bin/bash /run/localzet-candidate-check/run-wine.sh
printf '\nLOCALZET_CANDIDATE_WINE_READY\n'
"""

    if windows_matrix:
        matrix_copy = r"""
install -m 0644 /sys/firmware/qemu_fw_cfg/by_name/opt/localzet/fixture32/raw \
    /run/localzet-candidate-check/smoke32.exe
install -m 0644 /sys/firmware/qemu_fw_cfg/by_name/opt/localzet/msi/raw \
    /run/localzet-candidate-check/fixture.msi
test -s /run/localzet-candidate-check/smoke32.exe
test -s /run/localzet-candidate-check/fixture.msi
"""
        copy_marker = "test -s /run/localzet-candidate-check/smoke.exe\n"
        assert script.count(copy_marker) == 1
        script = script.replace(copy_marker, copy_marker + matrix_copy)
        matrix_run = r"""
set +e
timeout 240 python3 /opt/localzet-os/src/localzet/windows_runtime.py /run/localzet-candidate-check/smoke32.exe --profile ci-smoke --run
status=$?
set -e
printf 'Installed Wine x86 fixture exit code: %s\n' "$status"
"$WINESERVER" -w
test "$status" -eq 42
original="$WINEPREFIX"
export WINEPREFIX="$data/localzet/windows/prefixes/ci-msi"
mkdir -p "$WINEPREFIX"
wineboot --init
"$WINESERVER" -w
set +e
WINEDEBUG=+msi timeout 240 python3 /opt/localzet-os/src/localzet/windows_runtime.py /run/localzet-candidate-check/fixture.msi --profile ci-msi --run > "$data/msi.log" 2>&1
status=$?
set -e
printf 'Installed Wine MSI fixture exit code: %s\n' "$status"
"$WINESERVER" -w
if [[ "$status" -ne 0 ]]; then
    tail -n 120 "$data/msi.log" >&2
    exit "$status"
fi
test -s "$WINEPREFIX/system.reg"
found="$(find "$WINEPREFIX/drive_c/users" -type f -path "*/LocalzetFixture/payload.txt")"
test -n "$found"
printf 'Localzet original MSI fixture\n' | cmp - "$found"
test -z "$(find "$original/drive_c" -type f -path "*/LocalzetFixture/payload.txt")"
printf 'PASS: installed Wine x86 and original MSI verified in distinct prefixes\n'
"""
        run_marker = 'test -s "$WINEPREFIX/system.reg"\nUSERTEST'
        assert script.count(run_marker) == 1
        script = script.replace(run_marker, 'test -s "$WINEPREFIX/system.reg"\n' + matrix_run + "USERTEST")
        script = script.replace("/usr/bin/timeout 300 /bin/bash /run/localzet-candidate-check/run-wine.sh",
                                "/usr/bin/timeout 840 /bin/bash /run/localzet-candidate-check/run-wine.sh")
    if archive_profile:
        check = r"""
PYTHONPATH=/opt/localzet-os/src python3 - <<'PY'
import json
from pathlib import Path
import subprocess
from localzet.profiles import load_manifest, plan
receipt = json.loads(Path("/usr/share/localzet/archive-profile-plan.json").read_text())
expected = plan(load_manifest(Path("/opt/localzet-os/config/profiles.json")), ARCHIVE_PROFILE)
assert receipt == expected
packages = expected["ubuntu_package_candidates"]
output = subprocess.check_output(["dpkg-query", "-W", "-f=${Package}\\t${db:Status-Abbrev}\\n", *packages], text=True)
assert set(output.splitlines()) == {name + "\tii " for name in packages}, output
assert not expected["install_ready"]
print("PASS: installed archive profile package inventory; external components remain pending")
PY
test -x /usr/bin/flatpak
test -x /usr/bin/localzet-apps
test -x /usr/lib/localzet/install-netbird
test -x /usr/lib/localzet/install-usernet
test -f /usr/share/polkit-1/actions/org.localzet.install-network.policy
launch_app localzet-apps /usr/bin/localzet-apps
test -x /usr/bin/localzet-ai
test -x /usr/bin/localzet-ai-install
test -x /usr/bin/localzet-ai-workspace
test -x /usr/bin/localzet-mcp
test -x /usr/bin/gpg
test -s /usr/share/icons/Aurora/scalable/apps/com.localzet.AIWorkspace.svg
launch_app localzet-ai-workspace /usr/bin/localzet-ai-workspace
launch_app vlc /usr/bin/vlc
launch_app qbittorrent /usr/bin/qbittorrent
pgrep -u localzet-test -x vlc >/dev/null
pgrep -u localzet-test -x qbittorrent >/dev/null
"""
        # Constant, allowlisted profile name; no arbitrary shell interpolation.
        assert archive_profile in ("standard", "complete")
        check = check.replace("ARCHIVE_PROFILE", repr(archive_profile))
        script = script.replace("printf '\\nLOCALZET_CANDIDATE_DESKTOP\\n'", check + "printf '\\nLOCALZET_CANDIDATE_DESKTOP\\n'")
        assert "installed archive profile package inventory" in script
    if telegram:
        if archive_profile not in ("standard", "complete"):
            raise ValueError("Telegram preinstall requires an archive profile")
        check = r"""
test -s /usr/share/localzet/telegram-review/refs.tsv
test -s /var/lib/flatpak/exports/share/applications/org.telegram.desktop.desktop
test "$(flatpak info --system --show-commit org.telegram.desktop)" = "$(cat /usr/share/localzet/telegram-review/app-commit)"
test "$(flatpak info --system --show-origin org.telegram.desktop)" = flathub
runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
    /usr/bin/python3 -c 'import sys; sys.path.insert(0, "/opt/localzet-os/src"); from localzet.app_catalog import action, flatpak_installed; assert action("telegram", flatpak_installed())[0] == "launch"'
runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
    systemd-run --user --collect --unit=localzet-candidate-telegram /usr/bin/flatpak run --system org.telegram.desktop
telegram_ready=0
for attempt in $(seq 1 90); do
    if runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" /usr/bin/flatpak ps --columns=application | grep -Fx org.telegram.desktop; then
        sleep 5
        if runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" /usr/bin/flatpak ps --columns=application | grep -Fx org.telegram.desktop; then
            telegram_ready=1; break
        fi
    fi
    sleep 1
done
if [[ "$telegram_ready" != 1 ]]; then
    runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" journalctl --user -u localzet-candidate-telegram --no-pager -n 80 || true
    exit 2
fi
printf 'PASS: preloaded system Telegram app and signed runtime launched offline as desktop user\n'
runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
    systemctl --user stop localzet-candidate-telegram.service
"""
        script = script.replace("printf '\\nLOCALZET_CANDIDATE_DESKTOP\\n'", check + "printf '\\nLOCALZET_CANDIDATE_DESKTOP\\n'")
    if network_preload:
        if archive_profile != "complete":
            raise ValueError("Network preload requires Complete")
        check = r"""
test "$(dpkg-query -W -f='${Version}' usernet)" = 0.5.12.2026110805
test -x /opt/UserNet/UserNet
test -s /usr/share/applications/com.localzet.usernet.desktop
test -s /usr/share/localzet/network-preload/netbird/netbird_0.83.1_linux_amd64.deb
test -s /usr/share/localzet/network-preload/netbird/netbird-ui_0.83.1_linux_amd64.deb
if systemctl is-enabled --quiet usernet-helper.service || systemctl is-active --quiet usernet-helper.service || ip link show wt0 >/dev/null 2>&1; then
    echo "Unexpected UserNet helper or NetBird tunnel" >&2
    exit 2
fi
ip -j route show table main > /run/localzet-candidate-check/network-before.json
# Exercise the exact production installer in an authenticated, isolated
# guest. No internet NIC, so any attempted download cannot succeed.
PKEXEC_UID="$uid" /usr/bin/python3 -I /usr/lib/localzet/install-network-client.py netbird
test "$(dpkg-query -W -f='${Version}' netbird)" = 0.83.1
test "$(dpkg-query -W -f='${Version}' netbird-ui)" = 0.83.1
systemctl is-active --quiet netbird.service
runuser -u localzet-test -- env PYTHONPATH=/opt/localzet-os/src /usr/bin/python3 - <<'NETWORKTEST'
import time
from localzet.netbird import status
for attempt in range(30):
    report = status()
    if report["state"] in ("NeedsLogin", "Idle"):
        break
    time.sleep(1)
assert report["state"] in ("NeedsLogin", "Idle"), report
assert report.get("total", 0) == report.get("connected", 0) == 0, report
print("PASS: cached NetBird installed offline and unregistered daemon responded")
NETWORKTEST
launch_app localzet-network /usr/bin/localzet-network
runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
    systemd-run --user --collect --unit=localzet-candidate-usernet --setenv=LIBGL_ALWAYS_SOFTWARE=1 /opt/UserNet/UserNet
for attempt in $(seq 1 45); do
    if pgrep -u localzet-test -f '/opt/UserNet/UserNet' >/dev/null; then break; fi
    sleep 1
done
sleep 5
pgrep -u localzet-test -f '/opt/UserNet/UserNet' >/dev/null
if systemctl is-enabled --quiet usernet-helper.service || systemctl is-active --quiet usernet-helper.service || ip link show wt0 >/dev/null 2>&1; then
    echo "Unexpected UserNet helper or NetBird tunnel" >&2
    exit 2
fi
ip -j route show table main > /run/localzet-candidate-check/network-after.json
python3 - <<'ROUTES'
import json
from pathlib import Path
def defaults(name):
    return [r for r in json.loads(Path("/run/localzet-candidate-check/network-" + name + ".json").read_text()) if r.get("dst") == "default"]
assert defaults("before") == defaults("after")
ROUTES
printf 'PASS: preinstalled UserNet launched unprivileged without helper or default route changes\n'
runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
    systemctl --user stop localzet-candidate-usernet.service
"""
        script = script.replace("printf '\\nLOCALZET_CANDIDATE_DESKTOP\\n'", check + "printf '\\nLOCALZET_CANDIDATE_DESKTOP\\n'")
    if containers:
        check = r"""
test -x /usr/bin/localzet-hardware-manager
test -x /usr/sbin/localzet-install-drivers
test -f /usr/lib/systemd/system/localzet-hardware-firstboot.timer
test ! -e /etc/localzet/hardware-auto
test ! -e /usr/lib/localzet/hardware-auto-enabled
if systemctl is-enabled --quiet localzet-hardware-firstboot.timer; then
    echo "Unexpected automatic hardware setup without consent"; exit 2
fi
test -s /usr/share/icons/Aurora/index.theme
for icon in com.localzet.Settings com.localzet.Hardware com.localzet.Containers org.gnome.Nautilus org.gnome.Ptyxis; do
    test -s "/usr/share/icons/Aurora/scalable/apps/$icon.svg"
done
test "$(runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" gsettings get org.gnome.desktop.interface icon-theme)" = "'Aurora'"
for glyph in launcher browser files terminal settings; do
    test -s "/usr/share/gnome-shell/extensions/localzet-shell@localzet.com/icons/$glyph.svg"
done
launch_app localzet-hardware-manager /usr/bin/localzet-hardware-manager
dpkg-query -W docker.io docker-compose-v2 gir1.2-vte-3.91
/usr/bin/docker compose version
for unit in docker.service docker.socket containerd.service; do
    if systemctl is-enabled --quiet "$unit" || systemctl is-active --quiet "$unit"; then
        echo "Unexpected enabled or active Docker unit: $unit"; exit 2
    fi
done
if id -nG localzet-test | tr ' ' '\n' | grep -Fxq docker; then
    echo "Unexpected docker group access"; exit 2
fi
test -f /usr/lib/systemd/user/localzet-rootless-docker.service
test -s /usr/share/localzet/docker-rootless.json
cleanup_containers() {
    local failed=0
    runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
        systemctl --user stop localzet-candidate-localzet-containers.service >/dev/null 2>&1 || failed=1
    if runuser -u localzet-test -- /usr/bin/docker --host "unix:///run/user/$uid/docker.sock" \
        container inspect localzet-ui-fixture >/dev/null 2>&1; then
        runuser -u localzet-test -- /usr/bin/docker --host "unix:///run/user/$uid/docker.sock" \
            container rm -f localzet-ui-fixture >/dev/null 2>&1 || failed=1
    fi
    if runuser -u localzet-test -- /usr/bin/docker --host "unix:///run/user/$uid/docker.sock" \
        container inspect localzet-ui-fixture >/dev/null 2>&1; then
        echo "Rootless UI fixture container survived cleanup" >&2
        failed=1
    fi
    if runuser -u localzet-test -- /usr/bin/docker --host "unix:///run/user/$uid/docker.sock" \
        image inspect localzet-installed-rootless-fixture:ci >/dev/null 2>&1; then
        runuser -u localzet-test -- /usr/bin/docker --host "unix:///run/user/$uid/docker.sock" \
            image rm localzet-installed-rootless-fixture:ci >/dev/null 2>&1 || failed=1
    fi
    runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
        systemd-run --user --wait --pipe --collect --setenv=PYTHONPATH=/opt/localzet-os/src \
        /usr/bin/python3 -c 'from localzet.rootless_docker import change; print(change("stop"))' \
        >/dev/null 2>&1 || failed=1
    return "$failed"
}
trap 'cleanup_containers || true' EXIT
# The rootless engine is the only engine started by this test. It stays
# active only while a disposable, unprivileged fixture is visible in the UI.
if ! runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
    systemd-run --user --wait --pipe --collect --setenv=PYTHONPATH=/opt/localzet-os/src /usr/bin/python3 -c '
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import time
from localzet.containers import Engine, metric_sample
from localzet.rootless_docker import change

docker = ["/usr/bin/docker", "--host", "unix:///run/user/" + str(os.getuid()) + "/docker.sock"]
tag = "localzet-installed-rootless-fixture:ci"
def run(*args):
    return subprocess.check_output(docker + list(args), text=True, timeout=150).strip()

keep_running = False
try:
    assert change("start") == "rootless подтверждён"
    engine = Engine()
    assert engine.inventory() == ()
    print("PASS: installed managed rootless Docker returned a real empty inventory", flush=True)
    with tempfile.TemporaryDirectory(prefix=".localzet-rootless-ci-", dir=Path.home()) as directory:
        archive = Path(directory) / "fixture.tar"
        with tarfile.open(archive, "w") as output:
            output.add("/usr/bin/busybox", arcname="bin/busybox", recursive=False)
        run("import", str(archive), tag)
    assert run("run", "--rm", "--network", "none", tag, "/bin/busybox", "echo", "ROOTLESS_OK") == "ROOTLESS_OK"
    print("PASS: installed unprivileged container executed offline", flush=True)
    change("stop")
    assert change("start") == "rootless подтверждён"
    run("image", "inspect", tag)
    assert run("run", "--rm", "--network", "none", tag, "/bin/busybox", "echo", "PERSISTENCE_OK") == "PERSISTENCE_OK"
    fixture_id = run("run", "--detach", "--name", "localzet-ui-fixture", "--network", "none",
                     tag, "/bin/busybox", "sh", "-c",
                     "echo LOCALZET_LOG_FIXTURE; while true; do /bin/busybox sleep 1; done")
    rows = engine.inventory()
    fixture = next(row for row in rows if row.id == fixture_id and row.name == "localzet-ui-fixture")
    assert fixture.state == "running", fixture
    logs = ""
    truncated = False
    for attempt in range(10):
        logs, truncated = engine.logs(fixture.id)
        if "LOCALZET_LOG_FIXTURE" in logs:
            break
        time.sleep(1)
    assert not truncated and "LOCALZET_LOG_FIXTURE" in logs, (logs, truncated)
    sample = metric_sample(engine.metrics(fixture.id))
    assert sample.cpu >= 0 and sample.memory >= 0, sample
    print("PASS: installed rootless inventory, bounded logs and live metrics snapshots", flush=True)
    keep_running = True
finally:
    if not keep_running:
        change("stop")
'; then
    echo "Installed rootless Docker failure diagnostics:"
    runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
        journalctl --user -u localzet-rootless-docker.service --no-pager -n 150 || true
    journalctl -k --no-pager -b -n 200 | grep -Ei 'apparmor|audit|denied|rootless|overlay|netfilter|namespace' || true
    lsmod || true
    exit 2
fi
for tool in xdotool xprop xwininfo; do
    command -v "$tool" >/dev/null || { echo "Missing disposable X11 window-discovery tool: $tool" >&2; exit 2; }
done
launch_app_x11 localzet-containers /usr/bin/localzet-containers
containers_window=""
for attempt in $(seq 1 45); do
    clients="$(xprop -root _NET_CLIENT_LIST 2>/dev/null || true)"
    for hex in $(grep -Eo '0x[0-9a-fA-F]+' <<< "$clients" || true); do
        candidate="$((hex))"
        identity="$(xprop -id "$hex" WM_CLASS _NET_WM_NAME WM_NAME 2>/dev/null)" || continue
        grep -Eiq 'localzet-containers|com\.localzet\.Containers|Localzet Containers' <<< "$identity" || continue
        geometry="$(xdotool getwindowgeometry --shell "$candidate" 2>/dev/null)" || continue
        width="$(sed -n 's/^WIDTH=//p' <<< "$geometry")"
        height="$(sed -n 's/^HEIGHT=//p' <<< "$geometry")"
        [[ "$width" =~ ^[0-9]+$ && "$height" =~ ^[0-9]+$ ]] || continue
        (( width >= 600 && height >= 400 )) || continue
        timeout 2 xdotool windowactivate "$candidate" || continue
        for poll in $(seq 1 5); do
            if [[ "$(xdotool getactivewindow 2>/dev/null || true)" == "$candidate" ]]; then
                containers_window="$candidate"
                break
            fi
            sleep 0.2
        done
        [[ -n "$containers_window" ]] && break
    done
    [[ -n "$containers_window" ]] && break
    sleep 1
done
if [[ -z "$containers_window" ]]; then
    echo "No visible, activatable Localzet Containers GTK window" >&2
    xprop -root _NET_CLIENT_LIST _NET_ACTIVE_WINDOW >&2 || true
    xwininfo -root -tree >&2 || true
    runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \\
        systemctl --user status localzet-candidate-localzet-containers.service --no-pager >&2 || true
    runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \\
        journalctl --user -u localzet-candidate-localzet-containers.service --no-pager -n 100 >&2 || true
    exit 2
fi
geometry="$(xdotool getwindowgeometry --shell "$containers_window")"
x="$(sed -n 's/^X=//p' <<< "$geometry")"
y="$(sed -n 's/^Y=//p' <<< "$geometry")"
width="$(sed -n 's/^WIDTH=//p' <<< "$geometry")"
height="$(sed -n 's/^HEIGHT=//p' <<< "$geometry")"
[[ "$x" =~ ^-?[0-9]+$ && "$y" =~ ^-?[0-9]+$ && "$width" =~ ^[0-9]+$ && "$height" =~ ^[0-9]+$ ]]
(( width >= 600 && height >= 400 ))
test "$(xdotool getactivewindow)" = "$containers_window"
printf 'LOCALZET_CANDIDATE_CONTAINERS_GEOMETRY %s %s %s %s\n' "$x" "$y" "$width" "$height"
printf 'LOCALZET_CANDIDATE_CONTAINERS_CAPTURE_READY\n'
sleep 8
cleanup_containers
trap - EXIT
if runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
    systemctl --user is-active --quiet localzet-rootless-docker.service; then
    echo "Rootless Docker service remained active after its disposable GUI fixture"
    exit 2
fi
printf 'PASS: installed Containers window displayed a live rootless fixture and closed cleanly\n'
"""
        script = script.replace("printf '\\nLOCALZET_CANDIDATE_DESKTOP\\n'", check + "printf '\\nLOCALZET_CANDIDATE_DESKTOP\\n'")
        assert "installed Containers window displayed a live rootless fixture" in script
    if office:
        check = r"""
test "$(dpkg-query -W -f='${Version}' onlyoffice-desktopeditors)" = 10.0.0-169
test -s /opt/onlyoffice/desktopeditors/LICENSE.txt
test -s /usr/share/localzet/office-review/upstream.json
test -x /usr/bin/onlyoffice-desktopeditors
test -x /usr/bin/localzet-office
mapfile -t office_entries < <(dpkg-query -L onlyoffice-desktopeditors | grep -E '^/usr/share/applications/[^/]+\.desktop$')
((${#office_entries[@]} > 0))
for entry in "${office_entries[@]}"; do
    test -s "/usr/local/share/applications/${entry##*/}"
    grep -Eq '^Exec=/usr/bin/localzet-office([[:space:]]|$)' "/usr/local/share/applications/${entry##*/}"
done
# Do not prelaunch ONLYOFFICE without the fixture: it is single-instance, so a later
# wrapper invocation could only forward the document to a renderer started with
# a different GPU policy.
# The real wrapper launch happens below with the DOCX.
cat > /run/localzet-candidate-check/office-window.sh <<'OFFICETEST'
#!/bin/bash
set -Eeuo pipefail
[[ $EUID != 0 ]]
window=""
for attempt in $(seq 1 90); do
    # Enumerate managed clients directly, including windows obscured by
    # earlier applications. Match identity before requesting activation.
    clients="$(xprop -root _NET_CLIENT_LIST 2>/dev/null || true)"
    for hex in $(grep -Eo '0x[0-9a-fA-F]+' <<< "$clients" || true); do
        candidate="$((hex))"
        identity="$(xprop -id "$hex" WM_CLASS _NET_WM_NAME WM_NAME 2>/dev/null)" || continue
        grep -Eiq 'DesktopEditors|ONLYOFFICE|Desktop Editors' <<< "$identity" || continue
        geometry="$(xdotool getwindowgeometry --shell "$candidate" 2>/dev/null)" || continue
        width="$(sed -n 's/^WIDTH=//p' <<< "$geometry")"
        height="$(sed -n 's/^HEIGHT=//p' <<< "$geometry")"
        [[ "$width" =~ ^[0-9]+$ && "$height" =~ ^[0-9]+$ ]] || continue
        (( width >= 400 && height >= 300 )) || continue
        # Avoid xdotool's synchronous desktop-switch wait on Mutter.
        # The active-window check below remains mandatory.
        timeout 2 xdotool windowactivate "$candidate" || continue
        for poll in $(seq 1 5); do
            if [[ "$(xdotool getactivewindow 2>/dev/null || true)" == "$candidate" ]]; then
                window="$candidate"
                break
            fi
            sleep 0.2
        done
        [[ -n "$window" ]] && break
    done
    [[ -n "$window" ]] && break
    sleep 1
done
if [[ -z "$window" ]]; then
    echo "No activatable managed ONLYOFFICE window" >&2
    xprop -root _NET_CLIENT_LIST _NET_ACTIVE_WINDOW >&2 || true
    xwininfo -root -tree >&2 || true
    exit 1
fi
xdotool getwindowname "$window"
geometry="$(xdotool getwindowgeometry --shell "$window")"
width="$(sed -n 's/^WIDTH=//p' <<< "$geometry")"
height="$(sed -n 's/^HEIGHT=//p' <<< "$geometry")"
[[ "$width" =~ ^[0-9]+$ && "$height" =~ ^[0-9]+$ ]]
(( width >= 400 && height >= 300 ))
x="$(sed -n 's/^X=//p' <<< "$geometry")"
y="$(sed -n 's/^Y=//p' <<< "$geometry")"
[[ "$x" =~ ^-?[0-9]+$ && "$y" =~ ^-?[0-9]+$ ]]
test "$(xdotool getactivewindow)" = "$window"
printf 'LOCALZET_CANDIDATE_OFFICE_GEOMETRY %s %s %s %s\n' "$x" "$y" "$width" "$height"
printf 'PASS: visible ONLYOFFICE window %s x %s\n' "$width" "$height"
OFFICETEST
chmod 0755 /run/localzet-candidate-check/office-window.sh
runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
    systemd-run --user --wait --pipe --collect /bin/bash /run/localzet-candidate-check/office-window.sh
printf 'PASS: installed native ONLYOFFICE launched in authenticated offline user session\n'
"""
        script = script.replace("printf '\\nLOCALZET_CANDIDATE_DESKTOP\\n'", check + "printf '\\nLOCALZET_CANDIDATE_DESKTOP\\n'")
        assert "installed native ONLYOFFICE launched" in script
    if executive_review and office:
        # Use exactly the same original DOCX as the successful offline matrix.
        spec = importlib.util.spec_from_file_location("office_fixture", Path(__file__).with_name("ci") / "office-fixture.py")
        fixture_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture_module)
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "Localzet-offline-review.docx"
            fixture_module.build(fixture)
            encoded = base64.b64encode(fixture.read_bytes()).decode("ascii")
        launch = r"""
# Avoid late activation by earlier test applications; stop only transient
# units created by this disposable validation session.
for app in ptyxis localzet-settings localzet-windows localzet-connect vlc qbittorrent localzet-hardware-manager localzet-containers nautilus gnome-control-center localzet-apps localzet-ai-workspace; do
    runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
        systemctl --user stop "localzet-candidate-$app.service" || true
done
# The test document must live in a writable directory of the authenticated
# user, just like a real local file. The earlier root-owned /run fixture
# did not allow the editor to create a sibling lock or temporary file.
office_dir="$(runuser -u localzet-test -- mktemp -d "$home/.localzet-office-review.XXXXXXXX")"
printf '%s' 'FIXTURE_BASE64' | base64 -d | runuser -u localzet-test -- tee "$office_dir/Localzet-offline-review.docx" >/dev/null
runuser -u localzet-test -- test -w "$office_dir/Localzet-offline-review.docx"
runuser -u localzet-test -- test -w "$office_dir"
printf 'Office diagnostic mode: RENDER_MODE (explicit X11 toolkit backend; C.UTF-8 editor locale)\n'
free -m
# Only the disposable test user's session is changed.
runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
    gsettings set org.gnome.desktop.session idle-delay 0
df -h "$home" /dev/shm
echo "Office local runtime prerequisites:"
ip -brief address show dev lo || true
runuser -u localzet-test -- timeout 15 fc-match sans-serif || true
runuser -u localzet-test -- timeout 15 fc-match Calibri || true
for binary in /opt/onlyoffice/desktopeditors/DesktopEditors /opt/onlyoffice/desktopeditors/converter/x2t; do
    if [[ -x "$binary" ]]; then
        echo "Dynamic dependencies: $binary"
        ldd "$binary" | grep -E 'not found|libcef|libstdc\+\+' || true
    fi
done
printf 'Office shared memory and GPU:\n'
ls -ld /dev/shm /dev/dri || true
runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
    systemd-run --user --unit=localzet-candidate-onlyoffice-desktopeditors \
    --property=StandardOutput=journal --property=StandardError=journal \
    --setenv=QT_QPA_PLATFORM=xcb --setenv=GDK_BACKEND=x11 RENDER_ENV \
    /usr/bin/localzet-office RENDER_FLAGS "$office_dir/Localzet-offline-review.docx"
"""
        marker = "# The real wrapper launch happens below with the DOCX."
        assert script.count(marker) == 1
        render_env = ""
        render_flags = "--disable-gpu" if office_render_mode == "software-disable-gpu" else ""
        if office_render_mode == "fresh-profile":
            # Same actual Mutter/Xwayland session, fresh editor settings.
            render_env = ('--setenv=HOME="$office_dir/profile/home" '
                          '--setenv=XDG_CONFIG_HOME="$office_dir/profile/config" '
                          '--setenv=XDG_DATA_HOME="$office_dir/profile/data" '
                          '--setenv=XDG_CACHE_HOME="$office_dir/profile/cache"')
            launch = launch.replace("free -m", 'runuser -u localzet-test -- mkdir -p "$office_dir/profile/"{home,config,data,cache}\nfree -m')
        launch = (launch.replace("FIXTURE_BASE64", encoded)
                  .replace("RENDER_MODE", office_render_mode)
                  .replace("RENDER_ENV", render_env)
                  .replace("RENDER_FLAGS", render_flags))
        if office_render_mode == "isolated-x11":
            # Same installed package and fixture, separate X server and
            # fresh user-local profile. Do not change the default session.
            launch = launch[:launch.index('runuser -u localzet-test -- env XDG_RUNTIME_DIR=', launch.index('Office shared memory and GPU:'))]
            launch += r"""
cat > /run/localzet-candidate-check/office-isolated.sh <<'ISOLATEDOFFICE'
#!/bin/bash
set -Eeuo pipefail
[[ $EUID != 0 ]]
work="$(mktemp -d)"
wm=""
editor=""
cleanup() {
    if [[ -n "$editor" ]]; then kill -TERM -- "-$editor" 2>/dev/null || true; fi
    if [[ -n "$wm" ]]; then kill "$wm" 2>/dev/null || true; fi
    rm -rf -- "$work"
}
trap cleanup EXIT
export HOME="$work/home" XDG_CONFIG_HOME="$work/config" XDG_DATA_HOME="$work/data" XDG_CACHE_HOME="$work/cache"
export QT_QPA_PLATFORM=xcb GDK_BACKEND=x11 LANG=C.UTF-8
unset WAYLAND_DISPLAY
mkdir -p "$HOME" "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$XDG_CACHE_HOME"
cp "$1" "$HOME/Localzet-offline-review.docx"
openbox > "$work/openbox.log" 2>&1 &
wm=$!
sleep 2
setsid /usr/bin/onlyoffice-desktopeditors "$HOME/Localzet-offline-review.docx" > "$work/editor.log" 2>&1 &
editor=$!
if ! /bin/bash /run/localzet-candidate-check/office-window.sh; then
    tail -n 100 "$work/editor.log" "$work/openbox.log" >&2 || true
    exit 1
fi
ISOLATEDOFFICE
chmod 0755 /run/localzet-candidate-check/office-isolated.sh
"""
        script = script.replace(marker, launch)
        first = script.index("window=\"\"\n", script.index("<<'OFFICETEST'"))
        last = script.index("\nOFFICETEST", first)
        script = script[:first] + r"""window=""
mode=""
if (( $# > 0 )); then mode="$1"; fi
for attempt in $(seq 1 90); do
    window="$(xdotool search --onlyvisible --name 'Localzet-offline-review' 2>/dev/null | tail -n1 || true)"
    [[ -n "$window" ]] && break
    sleep 1
done
test -n "$window"
xdotool getwindowname "$window" | grep -F Localzet-offline-review
work="$(mktemp -d)"
trap 'rm -rf -- "$work"' EXIT
for attempt in $(seq 1 45); do
    timeout 4 xdotool windowactivate --sync "$window" || continue
    sleep 2
    [[ "$(xdotool getactivewindow)" == "$window" ]] || continue
    import -window "$window" "$work/document.png" || continue
    [[ "$(xdotool getactivewindow)" == "$window" ]] || continue
    if python3 - "$work/document.png" <<'PY'
from PIL import Image
import sys
im = Image.open(sys.argv[1]).convert("RGB")
w, h = im.size
assert w >= 400 and h >= 300
# Restrict the ink check to the document page, not the ribbon or titlebar.
page = im.crop((w//8, h//3, w*7//8, h*4//5))
ink = sum(20 <= r <= 65 and 65 <= g <= 125 and 130 <= b <= 205
          and b > g+35 and g > r+25 for r,g,b in page.getdata())
print("Fixture heading ink:", ink)
assert ink >= 250
PY
    then
        test "$(stat -c %s "$work/document.png")" -lt 1572864
        if [[ "$mode" == "--check-virtio-policy" ]]; then
            virtio_gpu=0
            for pci_device in /sys/bus/pci/devices/*; do
                [[ -r "$pci_device/vendor" && -r "$pci_device/class" ]] || continue
                vendor="$(cat "$pci_device/vendor")"
                pci_class="$(cat "$pci_device/class")"
                if [[ "$vendor" == 0x1af4 && "$pci_class" == 0x03* ]]; then
                    virtio_gpu=1
                    break
                fi
            done
            office_pid="$(pgrep -u "$(id -u)" -x DesktopEditors | head -n 1)"
            test -n "$office_pid"
            office_cmdline="$(ps -p "$office_pid" -o args=)"
            if [[ "$virtio_gpu" == 1 ]]; then
                grep -Fq -- '--disable-gpu' <<< "$office_cmdline"
                echo "PASS: virtio GPU fallback is scoped to the ONLYOFFICE process"
            else
                ! grep -Fq -- '--disable-gpu' <<< "$office_cmdline"
                echo "PASS: non-virtio GPU retains the upstream acceleration path"
            fi
        fi
        printf 'LOCALZET_CANDIDATE_OFFICE_PNG '
        base64 -w0 "$work/document.png"
        printf '\nPASS: actual ONLYOFFICE document drawable captured\n'
        exit 0
    fi
done
# Leave the active document visible for an independent host QMP capture.
printf 'LOCALZET_CANDIDATE_OFFICE_CAPTURE_READY\n'
sleep 8
echo "No rendered fixture heading in named document window" >&2
xdotool getwindowgeometry --shell "$window" >&2 || true
xdotool getwindowname "$window" >&2 || true
if [[ -s "$work/document.png" ]]; then
    stat -c "Failed drawable bytes: %s" "$work/document.png" >&2
fi
if [[ -s "$work/document.png" && "$(stat -c %s "$work/document.png")" -lt 1572864 ]]; then
    printf 'LOCALZET_CANDIDATE_OFFICE_FAILED_PNG '
    base64 -w0 "$work/document.png"
    printf '\n'
fi
exit 1""" + script[last:]
        check_marker = "systemd-run --user --wait --pipe --collect /bin/bash /run/localzet-candidate-check/office-window.sh"
        if office_render_mode != "isolated-x11":
            script = script.replace(check_marker, check_marker + " --check-virtio-policy")
            check_marker += " --check-virtio-policy"
        assert script.count(check_marker) == 1
        if office_render_mode == "isolated-x11":
            script = script.replace(check_marker, 'systemd-run --user --wait --pipe --collect /usr/bin/xvfb-run -a -s "-screen 0 1440x900x24" /usr/bin/dbus-run-session -- /bin/bash /run/localzet-candidate-check/office-isolated.sh "$office_dir/Localzet-offline-review.docx"')
            check_marker = 'systemd-run --user --wait --pipe --collect /usr/bin/xvfb-run -a -s "-screen 0 1440x900x24" /usr/bin/dbus-run-session -- /bin/bash /run/localzet-candidate-check/office-isolated.sh "$office_dir/Localzet-offline-review.docx"'
            assert script.count(check_marker) == 1
        script = script.replace(check_marker, check_marker + r""" || {
    echo "Office user-service diagnostics:"
    journalctl -b "_UID=$uid" --user-unit=localzet-candidate-onlyoffice-desktopeditors.service --no-pager -n 150 -o cat || true
    journalctl -k -b --no-pager -o cat | grep -Ei 'apparmor|segfault|oom|out of memory|virtio_gpu' | tail -n 80 || true
    ps -u localzet-test -o pid,ppid,stat,pcpu,rss,comm
    echo "Office local sockets:"
    ss -lntp || true
    echo "Office profile diagnostic files (synthetic user only):"
    for directory in "$home/.local/share/onlyoffice" "$home/.config/onlyoffice" "$home/.cache/onlyoffice"; do
        [[ -d "$directory" ]] || continue
        find "$directory" -maxdepth 5 -type f \( -iname '*.log' -o -iname '*font*' -o -iname '*error*' \) -printf '%s %p\n' | head -n 60 || true
        while IFS= read -r -d '' logfile; do
            printf 'Office log: %s\n' "$logfile"
            tail -c 8192 -- "$logfile" || true
            printf '\n'
        done < <(find "$directory" -maxdepth 5 -type f -iname '*.log' -print0 | head -z -n 8)
    done
    free -m
    exit 2
}""")
    if native_files:
        check = r"""
for package in nautilus nautilus-data libnautilus-extension4; do
    [[ "$(dpkg-query -W -f='${Version}' "$package")" == *+localzet1 ]]
done
test -s /usr/share/doc/localzet-desktop/nautilus.BUILD-COMMIT
launch_app nautilus /usr/bin/nautilus
printf '\nPASS: installed Executive Files package launched\n'
"""
        marker = r"printf '\nLOCALZET_CANDIDATE_FIXTURE_COPY\n'"
        if script.count(marker) != 1:
            raise ValueError("Missing or duplicated installed Files insertion marker")
        script = script.replace(marker, check + marker)
        assert "installed Executive Files package launched" in script
    if branded_control_center:
        check = r"""
for package in gnome-control-center gnome-control-center-data; do
    [[ "$(dpkg-query -W -f='${Version}' "$package")" == *+localzet3 ]]
done
test -s /usr/share/doc/localzet-desktop/control-center.BUILD-COMMIT
test -s /usr/share/localzet/brand/localzet-about.svg
test -s /usr/share/localzet/brand/localzet-about-dark.svg
launch_app gnome-control-center /usr/bin/gnome-control-center
printf '\nPASS: installed branded Control Center package launched\n'
"""
        if native_files:
            check += r"""
cmp /usr/share/doc/localzet-desktop/control-center.BUILD-COMMIT /usr/share/doc/localzet-desktop/nautilus.BUILD-COMMIT
"""
        marker = r"printf '\nLOCALZET_CANDIDATE_FIXTURE_COPY\n'"
        if script.count(marker) != 1:
            raise ValueError("Missing or duplicated installed Control Center insertion marker")
        script = script.replace(marker, check + marker)
    if executive_review and office:
        # Keep the foreground editor available while the host checks actual
        # content. This is a test delay, not a change to shipped software.
        marker = r"printf '\nLOCALZET_CANDIDATE_WINE_START\n'"
        if script.count(marker) != 1:
            raise ValueError("Missing or duplicated office visual wait marker")
        script = script.replace(marker, "sleep 30\n" + marker)
    if executive_review:
        script += r"""
# Verify the native lock in the installed, authenticated Wayland session.
# No unlock bypass, no fake login UI and no password entered on camera.
test -s /usr/share/backgrounds/localzet/executive-dusk.jpg
test -s /usr/share/backgrounds/localzet/executive-dusk-glass.jpg
test "$(runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" gsettings get org.gnome.desktop.background picture-uri)" = "'file:///usr/share/backgrounds/localzet/executive-dusk.jpg'"
test "$(runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" gsettings get org.gnome.desktop.background picture-uri-dark)" = "'file:///usr/share/backgrounds/localzet/executive-dusk.jpg'"
test "$(runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" gsettings get org.gnome.desktop.interface color-scheme)" = "'prefer-dark'"
loginctl lock-session "$session"
for attempt in $(seq 1 30); do
    [[ "$(loginctl show-session "$session" -p LockedHint --value)" == yes ]] && break
    sleep 1
done
[[ "$(loginctl show-session "$session" -p LockedHint --value)" == yes ]]
runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
    gnome-extensions list --active | grep -Fx localzet-lock@localzet.com
# The user-session shell extension must not be active on the lock screen.
if runuser -u localzet-test -- env XDG_RUNTIME_DIR="/run/user/$uid" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
    gnome-extensions list --active | grep -Fx localzet-shell@localzet.com; then
    echo "Desktop extension unexpectedly active on lock screen"
    exit 2
fi
journalctl -b "_UID=$uid" --no-pager -o cat | grep -F "Localzet Lock: visual stylesheet active"
printf '\nLOCALZET_CANDIDATE_LOCKED\n'
# Keep the validation session alive for the host to wake the display.
sleep 25
[[ "$(loginctl show-session "$session" -p LockedHint --value)" == yes ]]
printf '\nLOCALZET_CANDIDATE_STILL_LOCKED\n'
"""
    return script


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iso", type=Path)
    parser.add_argument("--ovmf-code", type=Path, required=True)
    parser.add_argument("--ovmf-vars", type=Path, required=True)
    parser.add_argument("--logs", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--fixture32", type=Path)
    parser.add_argument("--msi-fixture", type=Path)
    parser.add_argument("--boot-media", choices=("optical", "usb"), default="optical")
    parser.add_argument("--expect-archive-profile", choices=("standard", "complete"))
    parser.add_argument("--expect-containers", action="store_true")
    parser.add_argument("--expect-office", action="store_true")
    parser.add_argument("--expect-preloaded-telegram", action="store_true")
    parser.add_argument("--expect-network-preload", action="store_true")
    parser.add_argument("--expect-executive-review", action="store_true")
    parser.add_argument("--expect-native-files", action="store_true")
    parser.add_argument("--expect-branded-control-center", action="store_true")
    parser.add_argument("--expect-foreign-disk", action="store_true", help="Verify privileged refusal with a second GPT disk, then install with that disk disconnected")
    parser.add_argument("--office-render-mode", choices=("default", "software-disable-gpu", "fresh-profile", "isolated-x11"), default="default",
                        help="Non-default modes are explicit diagnostics, not release acceptance.")
    args = parser.parse_args()
    if args.expect_office and not args.expect_archive_profile:
        parser.error("Office candidate requires Standard or Complete archive profile")
    if args.expect_containers and args.expect_archive_profile != "complete":
        parser.error("Containers candidate requires complete archive profile")
    for name in ("iso", "ovmf_code", "ovmf_vars"):
        path = getattr(args, name).resolve(strict=True)
        if not path.is_file():
            parser.error(f"{name} must be a regular file")
        setattr(args, name, path)
    args.logs = args.logs.resolve()
    args.logs.mkdir(parents=True, exist_ok=False)
    args.fixture = args.fixture.resolve(strict=True)
    if not args.fixture.is_file():
        parser.error("fixture must be a regular file")
    fixture = args.fixture.read_bytes()
    if not fixture.startswith(b"MZ") or len(fixture) > 2 * 1024**2:
        parser.error("expected a small original PE fixture")
    if (args.fixture32 is None) != (args.msi_fixture is None):
        parser.error("32-bit EXE and MSI fixtures must be supplied together")
    if args.fixture32 is not None:
        for name, magic in (("fixture32", b"MZ"), ("msi_fixture", bytes.fromhex("d0cf11e0a1b11ae1"))):
            path = getattr(args, name).resolve(strict=True)
            if not path.is_file() or not 0 < path.stat().st_size <= 2 * 1024**2:
                parser.error("expected a small original Windows fixture")
            with path.open("rb") as stream:
                if stream.read(len(magic)) != magic:
                    parser.error("invalid Windows fixture header")
            setattr(args, name, path)
    password = secrets.token_hex(12)
    with tempfile.TemporaryDirectory(prefix="lz-candidate-") as temp:
        directory = Path(temp)
        disk = directory / "target.raw"
        with disk.open("xb") as stream:
            stream.truncate(32 * 1024**3)
        script = directory / "install.sh"
        foreign = directory / "foreign.raw" if args.expect_foreign_disk else None
        fixture_tools = foreign_fixture_module() if foreign is not None else None
        before = None
        if foreign is not None:
            fixture_tools.foreign_disk(directory, foreign)
            before = fixture_tools.digest(foreign)
        if foreign is not None:
            script.write_text(foreign_refusal_script(password, args.boot_media))
            script.chmod(0o600)
            refusal_guest = Guest(args, directory, disk, script, "candidate-foreign-refusal", True, foreign)
            try:
                refusal_guest.connect()
                refusal_guest.wait(LIVE, 480)
                refusal_guest.launch("localzet-installer")
                refusal_guest.launch("sudo -n bash -c 'modprobe qemu_fw_cfg; cp /sys/firmware/qemu_fw_cfg/by_name/opt/localzet/test/raw /run/localzet-test.sh; bash /run/localzet-test.sh'")
                refusal_guest.wait(b"LOCALZET_CANDIDATE_FOREIGN_REFUSED", 180)
                refusal_guest.capture("refused")
            finally:
                refusal_guest.close()
                after = fixture_tools.digest(foreign)
                (args.logs / "foreign-disk.sha256").write_text(f"before {before}\nafter  {after}\n")
                if after != before:
                    raise RuntimeError("Non-target GPT disk was modified during refusal test")
            print("PASS: foreign GPT disk unchanged after explicit refusal", flush=True)
            # The current installer intentionally requires disconnected foreign
            # disks. Boot the exact ISO again with only the blank target.
            # Do not represent this as successful multi-disk installation.
        script.write_text(installation_script(password, args.boot_media))
        script.chmod(0o600)
        live = Guest(args, directory, disk, script, "candidate-live", True)
        try:
            live.connect()
            live.wait(LIVE, 480)
            live.launch("localzet-installer")
            live.capture("installer-launched")
            live.launch("sudo -n bash -c 'modprobe qemu_fw_cfg; cp /sys/firmware/qemu_fw_cfg/by_name/opt/localzet/test/raw /run/localzet-test.sh; bash /run/localzet-test.sh'")
            live.wait(b"LOCALZET_CANDIDATE_INSTALL_STARTED", 90)
            live.wait(INSTALL, 1200)
        finally:
            live.close()
        script.write_text(installed_script(args.expect_archive_profile, args.expect_containers, args.expect_office, args.expect_executive_review, args.expect_native_files, args.office_render_mode, args.expect_branded_control_center, args.fixture32 is not None, args.expect_preloaded_telegram, args.expect_network_preload))
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
            # Authenticate the installed system via GDM, then switch to the
            # real TTY before launching applications. No GUI key queue.
            installed.capture("desktop-before-console")
            installed.key("esc")
            installed.key("ctrl-alt-f3")
            time.sleep(20 if installed.accel == "kvm" else 45)
            installed.capture("tty-login")
            installed.text("localzet-test")
            installed.key("ret")
            time.sleep(8)
            installed.text(password)
            installed.key("ret")
            time.sleep(12)
            # Do not capture authentication screens: an unexpected prompt
            # can echo the ephemeral password as a username.
            installed.text("sudo -k; sudo -v")
            installed.key("ret")
            time.sleep(3)
            installed.text(password)
            installed.key("ret")
            time.sleep(3)
            installed.text("sudo -n modprobe qemu_fw_cfg; sudo -n cp /sys/firmware/qemu_fw_cfg/by_name/opt/localzet/test/raw /run/localzet-test.sh; sudo -n bash /run/localzet-test.sh")
            installed.key("ret")
            try:
                installed.wait(READY, (600 if args.expect_office and args.expect_executive_review else 300) + (600 if args.expect_containers else 0))
            except RuntimeError:
                if args.expect_office and args.expect_executive_review and installed.serial.exists():
                    prefix = b"LOCALZET_CANDIDATE_OFFICE_FAILED_PNG "
                    matches = [line[len(prefix):] for line in installed.serial.read_bytes().splitlines()
                               if line.startswith(prefix)]
                    if len(matches) == 1 and len(matches[0]) <= 2 * 1024**2:
                        image = base64.b64decode(matches[0], validate=True)
                        if image.startswith(b"\x89PNG\r\n\x1a\n"):
                            installed.screen.with_name("candidate-installed-office-failed.png").write_bytes(image)
                raise
            installed.capture("desktop-verified")
            if args.expect_containers:
                containers_capture = installed.screen.with_name("candidate-installed-containers-window.ppm")
                if not containers_capture.is_file() or containers_capture.stat().st_size == 0:
                    raise RuntimeError("Missing actual installed Containers window screenshot")
            if args.expect_office:
                if args.expect_executive_review:
                    installed.office_document()
                installed.capture("office-installed")
                if args.expect_containers:
                    containers_capture = installed.screen.with_name("candidate-installed-containers-window.ppm")
                    office_capture = installed.screen.with_name("candidate-installed-office-installed.ppm")
                    if not containers_capture.is_file() or not office_capture.is_file():
                        raise RuntimeError("Missing distinct Containers or ONLYOFFICE installed screenshot")
                    if containers_capture.read_bytes() == office_capture.read_bytes():
                        raise RuntimeError("Containers and ONLYOFFICE screenshots are identical; refusing false visual evidence")
            installed.wait(WINE_READY, 900 if args.fixture32 is not None else 360)
            if args.expect_executive_review:
                installed.wait(LOCK_READY, 45)
                installed.visual_capture("native-lock", wake=True)
                installed.wait(LOCK_RECHECK, 45)
        finally:
            installed.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
