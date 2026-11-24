#!/usr/bin/env python3
"""Capture a real GNOME 50 Wayland session from the Live ISO using QMP."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time

from PIL import Image


WIDTH = 1536
HEIGHT = 1024
READY_MARKER = b"LOCALZET_LIVE_READY"


class QMP:
    def __init__(self, path: Path, timeout: int):
        deadline = time.monotonic() + timeout
        self.connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.connection.settimeout(5)
        while True:
            try:
                self.connection.connect(str(path))
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.25)
        self.stream = self.connection.makefile("rwb")
        greeting = json.loads(self.stream.readline())
        if "QMP" not in greeting:
            raise RuntimeError("QMP returned an invalid greeting")
        self.sequence = 0
        self.execute("qmp_capabilities")

    def execute(self, command: str, arguments: dict | None = None):
        self.sequence += 1
        request_id = self.sequence
        request = {"execute": command, "id": request_id}
        if arguments is not None:
            request["arguments"] = arguments
        self.stream.write((json.dumps(request) + "\n").encode())
        self.stream.flush()
        while True:
            line = self.stream.readline()
            if not line:
                raise OSError("QMP disconnected")
            response = json.loads(line)
            if response.get("id") != request_id:
                continue
            if "error" in response:
                raise RuntimeError(f"QMP {command} failed: {response['error']}")
            return response.get("return")

    def close(self):
        self.stream.close()
        self.connection.close()


def wait_for_ready(
    serial: Path,
    process: subprocess.Popen,
    timeout: int,
    stderr_log: Path,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if serial.is_file() and READY_MARKER in serial.read_bytes().splitlines():
            return
        if process.poll() is not None:
            details = stderr_log.read_text(encoding="utf-8", errors="replace").strip()
            raise RuntimeError(
                f"QEMU exited before the GNOME readiness marker ({process.returncode})"
                + (f": {details[-4000:]}" if details else "")
            )
        time.sleep(0.5)
    raise TimeoutError("Live GNOME Wayland session did not become ready")


def pause(seconds: float = 1.0) -> None:
    time.sleep(seconds)


def press(qmp: QMP, *keys: str) -> None:
    qmp.execute("send-key", {
        "keys": [{"type": "qcode", "data": key} for key in keys],
        "hold-time": 100,
    })


def type_text(qmp: QMP, value: str) -> None:
    codes = {
        " ": "spc",
        "-": "minus",
        "_": ("shift", "minus"),
        "/": "slash",
        ".": "dot",
        ":": ("shift", "semicolon"),
        "'": "apostrophe",
        '"': ("shift", "apostrophe"),
    }
    for character in value:
        if character.isalpha():
            if character.isupper():
                press(qmp, "shift", character.lower())
            else:
                press(qmp, character)
        elif character.isdigit():
            press(qmp, character)
        elif character in codes:
            code = codes[character]
            if isinstance(code, tuple):
                press(qmp, *code)
            else:
                press(qmp, code)
        else:
            raise ValueError(f"Unsupported test key character: {character!r}")
        time.sleep(0.04)


def click(qmp: QMP, x: int, y: int) -> None:
    if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
        raise ValueError("Click is outside the configured QEMU display")
    qmp.execute("input-send-event", {"events": [
        {"type": "abs", "data": {"axis": "x", "value": round(x * 32767 / (WIDTH - 1))}},
        {"type": "abs", "data": {"axis": "y", "value": round(y * 32767 / (HEIGHT - 1))}},
        {"type": "btn", "data": {"button": "left", "down": True}},
        {"type": "btn", "data": {"button": "left", "down": False}},
    ]})


def open_app(qmp: QMP, query: str) -> None:
    press(qmp, "meta_l")
    pause(1.0)
    type_text(qmp, query)
    pause(1.0)
    press(qmp, "enter")
    pause(5.0)


def capture(qmp: QMP, output: Path, name: str, theme: str, records: list[dict]) -> None:
    raw = output / f".{name}.ppm"
    png = output / f"{name}.png"
    qmp.execute("screendump", {"filename": str(raw)})
    deadline = time.monotonic() + 10
    while not raw.is_file() and time.monotonic() < deadline:
        time.sleep(0.1)
    if not raw.is_file():
        raise RuntimeError(f"QMP did not write framebuffer capture {name}")
    with Image.open(raw) as image:
        rgb = image.convert("RGB")
        rgb.save(png, optimize=True)
        size = list(rgb.size)
    raw.unlink()
    if size != [WIDTH, HEIGHT]:
        raise RuntimeError(
            f"Unexpected guest resolution for {name}: {size[0]}x{size[1]}"
        )
    records.append({
        "file": png.name,
        "theme": theme,
        "scene": name.removeprefix(f"{theme}-"),
        "resolution": size,
        "sha256": hashlib.sha256(png.read_bytes()).hexdigest(),
    })
    print(f"Captured {theme} {records[-1]['scene']}: {size[0]}x{size[1]}", flush=True)


def capture_shell_scenes(qmp: QMP, output: Path, theme: str, records: list[dict]) -> None:
    capture(qmp, output, f"{theme}-desktop", theme, records)

    click(qmp, 135, 16)
    pause(1.5)
    capture(qmp, output, f"{theme}-launcher", theme, records)
    press(qmp, "esc")
    pause(0.5)

    click(qmp, WIDTH - 64, 16)
    pause(1.5)
    capture(qmp, output, f"{theme}-quick-settings", theme, records)
    press(qmp, "esc")
    pause(0.5)

    open_app(qmp, "files")
    capture(qmp, output, f"{theme}-nautilus", theme, records)
    press(qmp, "alt", "f4")
    pause(1.0)

    press(qmp, "ctrl", "alt", "t")
    pause(2.5)
    type_text(qmp, f"notify-send -t 10000 localzet {theme}")
    press(qmp, "enter")
    pause(1.0)
    press(qmp, "alt", "f4")
    pause(0.6)
    capture(qmp, output, f"{theme}-notifications", theme, records)
    press(qmp, "esc")
    pause(0.5)


def click_appearance_tab(qmp: QMP) -> None:
    # The app uses a centered four-tab Adwaita ViewSwitcher in its header bar.
    click(qmp, 700, 207)
    pause(1.0)


def click_settings_tab(qmp: QMP) -> None:
    click(qmp, 625, 207)
    pause(1.0)


def apply_theme_in_ui(qmp: QMP, theme: str) -> None:
    row_y = {"blue": 304, "purple": 378, "black": 452}[theme]
    click(qmp, 1123, row_y)
    pause(2.0)


def restore_in_ui(qmp: QMP) -> None:
    click(qmp, 1084, 643)
    pause(2.0)


def set_restore_source(qmp: QMP) -> None:
    press(qmp, "ctrl", "alt", "t")
    pause(2.0)
    commands = (
        "gsettings set org.gnome.desktop.background picture-uri "
        "\"'file:///usr/share/backgrounds/localzet/aurora-black.webp'\"",
        "gsettings set org.gnome.desktop.background picture-uri-dark "
        "\"'file:///usr/share/backgrounds/localzet/aurora-black.webp'\"",
        "gsettings set org.gnome.desktop.interface icon-theme \"'Adwaita'\"",
        "gsettings set com.localzet.shell appearance \"'purple'\"",
    )
    for command in commands:
        type_text(qmp, command)
        press(qmp, "enter")
        pause(0.6)
    press(qmp, "alt", "f4")
    pause(1.0)


def check_installed_icons(
    qmp: QMP,
    output: Path,
    records: list[dict],
) -> None:
    for page in range(1, 5):
        open_app(qmp, "ptyxis")
        type_text(qmp, f"python3 /usr/lib/localzet/gnome-icon-resolution-smoke.py --page {page}")
        press(qmp, "enter")
        pause(2.0)
        capture(qmp, output, f"installed-icon-resolution-page-{page}", "blue", records)
        press(qmp, "alt", "f4")
        pause(0.5)


def check_shell_logs(qmp: QMP, output: Path, records: list[dict]) -> None:
    open_app(qmp, "ptyxis")
    type_text(qmp, "python3 /usr/lib/localzet/gnome-shell-log-smoke.py")
    press(qmp, "enter")
    pause(2.0)
    capture(qmp, output, "shell-log-check", "restored", records)
    press(qmp, "alt", "f4")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iso", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=480)
    args = parser.parse_args()
    if not args.iso.is_file():
        parser.error("Live ISO does not exist")
    qemu = shutil.which("qemu-system-x86_64")
    if not qemu:
        parser.error("qemu-system-x86_64 is required")
    if args.timeout <= 0:
        parser.error("timeout must be positive")

    args.out.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    qemu_version = subprocess.run(
        [qemu, "--version"], check=True, capture_output=True, text=True
    ).stdout.splitlines()[0]

    with tempfile.TemporaryDirectory(prefix="localzet-gnome-visual-") as temporary:
        tmp = Path(temporary)
        serial = tmp / "serial.log"
        qemu_stderr = tmp / "qemu-stderr.log"
        monitor = tmp / "qmp.sock"
        vnc_socket = tmp / "display.sock"
        accel = "kvm" if os.access("/dev/kvm", os.R_OK | os.W_OK) else "tcg"
        cpu = "host" if accel == "kvm" else "max"
        command = [
            qemu, "-machine", "q35", "-accel", accel, "-cpu", cpu,
            "-m", "4096", "-smp", "2", "-nic", "none",
            "-device", f"virtio-vga,xres={WIDTH},yres={HEIGHT},edid=on",
            "-device", "qemu-xhci,id=xhci", "-device", "usb-tablet,bus=xhci.0",
            "-display", f"vnc=unix:{vnc_socket},share=force-shared", "-monitor", "none",
            "-qmp", f"unix:{monitor},server=on,wait=off",
            "-no-reboot", "-boot", "order=d", "-cdrom", str(args.iso.resolve()),
            "-serial", f"file:{serial}",
        ]
        print(f"Starting real GNOME 50 Live guest with {accel}", flush=True)
        stderr_stream = qemu_stderr.open("w", encoding="utf-8")
        process = subprocess.Popen(
            command, stdout=subprocess.DEVNULL, stderr=stderr_stream,
        )
        qmp = None
        try:
            wait_for_ready(serial, process, args.timeout, qemu_stderr)
            qmp = QMP(monitor, timeout=20)
            pause(12.0)

            capture(qmp, args.out, "first-login-defaults", "blue", records)
            check_installed_icons(qmp, args.out, records)
            set_restore_source(qmp)
            capture(qmp, args.out, "restore-source-desktop", "restore-source", records)

            open_app(qmp, "localzet")
            click_appearance_tab(qmp)
            apply_theme_in_ui(qmp, "blue")
            capture(qmp, args.out, "blue-appearance", "blue", records)
            click_settings_tab(qmp)
            capture(qmp, args.out, "blue-settings", "blue", records)
            press(qmp, "alt", "f4")
            pause(1.0)
            capture_shell_scenes(qmp, args.out, "blue", records)

            for theme in ("purple", "black"):
                open_app(qmp, "localzet")
                click_appearance_tab(qmp)
                apply_theme_in_ui(qmp, theme)
                capture(qmp, args.out, f"{theme}-appearance", theme, records)
                click_settings_tab(qmp)
                capture(qmp, args.out, f"{theme}-settings", theme, records)
                press(qmp, "alt", "f4")
                pause(1.0)
                capture_shell_scenes(qmp, args.out, theme, records)

            open_app(qmp, "localzet")
            click_appearance_tab(qmp)
            restore_in_ui(qmp)
            capture(qmp, args.out, "restored-appearance", "restored", records)
            press(qmp, "alt", "f4")
            pause(1.0)
            capture(qmp, args.out, "restored-desktop", "restored", records)
            check_shell_logs(qmp, args.out, records)

            (args.out / "manifest.json").write_text(json.dumps({
                "captured_at_utc": datetime.now(timezone.utc).isoformat(),
                "capture_method": "QEMU QMP screendump from the Ubuntu 26.04 GNOME 50 Wayland Live session",
                "qemu": qemu_version,
                "guest_resolution": [WIDTH, HEIGHT],
                "records": records,
            }, indent=2) + "\n", encoding="utf-8")
            print(f"Captured {len(records)} real GNOME framebuffer screens in {args.out}", flush=True)
        finally:
            if qmp:
                qmp.close()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            stderr_stream.flush()
            stderr_stream.close()
            if qemu_stderr.is_file():
                shutil.copyfile(qemu_stderr, args.out / "qemu-stderr.log")
            if serial.is_file():
                shutil.copyfile(serial, args.out / "guest-serial.log")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
