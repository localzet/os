#!/usr/bin/env python3
"""QEMU-only test of the exact interactive installation candidate.

All writable disks are newly created temporary files. Test commands are
injected through a QEMU firmware data item and a local desktop terminal; the
candidate ISO contains no automatic test installer or credentials.
"""
from __future__ import annotations

import argparse
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
LOCK_RECHECK = b"LOCALZET_CANDIDATE_STILL_LOCKED"


def evidence_module():
    spec = importlib.util.spec_from_file_location('visual_evidence', Path(__file__).with_name('visual-evidence.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Guest:
    def __init__(self, args, directory: Path, disk: Path, script: Path, label: str, live: bool):
        self.serial = args.logs / f"{label}.serial.log"
        self.errors = args.logs / f"{label}.qemu.log"
        self.screen = args.logs / f"{label}.ppm"
        self.socket = directory / f"{label}.sock"
        variables = directory / f"{label}.fd"
        shutil.copyfile(args.ovmf_vars, variables)
        self.accel = "kvm" if os.access("/dev/kvm", os.R_OK | os.W_OK) else "tcg"
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
                return
        raise RuntimeError(f"{stage}: blank or insufficient screenshot evidence")

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
            if marker in lines:
                print(f"PASS: {marker.decode()}", flush=True)
                return
            if any(line.startswith(FAIL) for line in lines) or self.process.poll() is not None:
                break
            time.sleep(1)
        if self.serial.exists():
            print(self.serial.read_bytes()[-30000:].decode(errors="replace"), flush=True)
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


def installation_script(password, boot_media):
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


def installed_script(archive_profile=None, containers=False, office=False, executive_review=False):
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
sha256sum /run/localzet-candidate-check/smoke.exe
printf '\nLOCALZET_CANDIDATE_FIXTURE_READY\n'
cat > /run/localzet-candidate-check/run-wine.sh <<'USERTEST'
#!/bin/bash
set -Eeuo pipefail
[[ $EUID != 0 ]]
data="$(mktemp -d)"
trap 'rm -rf -- "$data"' EXIT
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
test -x /usr/bin/localzet-containers
launch_app localzet-containers /usr/bin/localzet-containers
pgrep -u localzet-test -f /usr/bin/localzet-containers >/dev/null
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
printf 'PASS: installed Containers launched unprivileged; system daemon disabled\n'
"""
        script = script.replace("printf '\\nLOCALZET_CANDIDATE_DESKTOP\\n'", check + "printf '\\nLOCALZET_CANDIDATE_DESKTOP\\n'")
        assert "installed Containers launched" in script
    if office:
        check = r"""
test "$(dpkg-query -W -f='${Version}' onlyoffice-desktopeditors)" = 10.0.0-169
test -s /opt/onlyoffice/desktopeditors/LICENSE.txt
test -s /usr/share/localzet/office-review/upstream.json
test -x /usr/bin/onlyoffice-desktopeditors
launch_app onlyoffice-desktopeditors 'DesktopEditors|onlyoffice-desktopeditors'
cat > /run/localzet-candidate-check/office-window.sh <<'OFFICETEST'
#!/bin/bash
set -Eeuo pipefail
[[ $EUID != 0 ]]
window=""
for attempt in $(seq 1 90); do
    window="$(xdotool search --onlyvisible --class '[Dd]esktop[Ee]ditors|[Oo][Nn][Ll][Yy][Oo][Ff][Ff][Ii][Cc][Ee]' 2>/dev/null | head -n1 || true)"
    if [[ -z "$window" ]]; then
        window="$(xdotool search --onlyvisible --name '[Oo][Nn][Ll][Yy][Oo][Ff][Ff][Ii][Cc][Ee]|Desktop Editors' 2>/dev/null | head -n1 || true)"
    fi
    [[ -n "$window" ]] && break
    sleep 1
done
test -n "$window"
timeout 15 xdotool windowactivate --sync "$window"
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
        # Keep the foreground editor available while the host checks actual
        # content. This is a test delay, not a change to shipped software.
        marker = r"printf '\nLOCALZET_CANDIDATE_WINE_START\n'"
        script = script.replace(marker, "sleep 30\n" + marker)
    if executive_review:
        script += r"""
# Verify the native lock in the installed, authenticated Wayland session.
# No unlock bypass, no fake login UI and no password entered on camera.
test -s /usr/share/backgrounds/localzet/executive-dusk.jpg
test -s /usr/share/backgrounds/localzet/executive-dusk-glass.jpg
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
    parser.add_argument("--boot-media", choices=("optical", "usb"), default="optical")
    parser.add_argument("--expect-archive-profile", choices=("standard", "complete"))
    parser.add_argument("--expect-containers", action="store_true")
    parser.add_argument("--expect-office", action="store_true")
    parser.add_argument("--expect-executive-review", action="store_true")
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
    password = secrets.token_hex(12)
    with tempfile.TemporaryDirectory(prefix="lz-candidate-") as temp:
        directory = Path(temp)
        disk = directory / "target.raw"
        with disk.open("xb") as stream:
            stream.truncate(32 * 1024**3)
        script = directory / "install.sh"
        script.write_text(installation_script(password, args.boot_media))
        script.chmod(0o600)
        live = Guest(args, directory, disk, script, "candidate-live", True)
        try:
            live.connect()
            live.wait(LIVE, 480)
            live.launch("localzet-installer")
            live.capture("installer-launched")
            # Use GNOME's run dialog directly: opening a terminal and typing
            # into it races focus and terminal startup on slower Live images.
            # This command contains no credentials; the test payload is fw_cfg.
            live.launch("sudo -n bash -c 'modprobe qemu_fw_cfg; cp /sys/firmware/qemu_fw_cfg/by_name/opt/localzet/test/raw /run/localzet-test.sh; bash /run/localzet-test.sh'")
            live.wait(b"LOCALZET_CANDIDATE_INSTALL_STARTED", 90)
            live.wait(INSTALL, 1200)
        finally:
            live.close()
        script.write_text(installed_script(args.expect_archive_profile, args.expect_containers, args.expect_office, args.expect_executive_review))
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
            installed.wait(READY, 300)
            installed.capture("desktop-verified")
            if args.expect_containers:
                installed.capture("containers-installed")
            if args.expect_office:
                if args.expect_executive_review:
                    installed.visual_capture("office-installed", installed.office_region())
                else:
                    installed.capture("office-installed")
            installed.wait(WINE_READY, 360)
            if args.expect_executive_review:
                installed.wait(LOCK_READY, 45)
                installed.visual_capture("native-lock", wake=True)
                installed.wait(LOCK_RECHECK, 45)
        finally:
            installed.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
