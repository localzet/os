#!/usr/bin/env python3
"""Capture a real GNOME 50 Wayland session from the Live ISO using QMP."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import select
import shutil
import socket
import subprocess
import tempfile
import time
from qemu_serial import has_serial_marker, serial_integer


WIDTH = 1536
HEIGHT = 1024
ABSOLUTE_POINTER_MAX = 0x7FFFF
READY_MARKER = b"LOCALZET_LIVE_READY"
GRAPHICAL_VT_KEY = b"LOCALZET_LIVE_GRAPHICAL_VT"
GUEST_AGENT_READY_TIMEOUT = 30
QCODE_ALIASES = {"enter": "ret"}


def choose_acceleration(requested: str) -> str:
    if requested != "auto":
        return requested
    return "kvm" if os.access("/dev/kvm", os.R_OK | os.W_OK) else "tcg"


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


class GuestControl:
    def __init__(self, path: Path, timeout: int):
        deadline = time.monotonic() + timeout
        self.connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.buffer = bytearray()
        self.sequence = 0
        while True:
            try:
                self.connection.connect(str(path))
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.25)

    def _read_line(self, timeout: float) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            newline = self.buffer.find(b"\n")
            if newline >= 0:
                line = bytes(self.buffer[:newline])
                del self.buffer[:newline + 1]
                return json.loads(line)
            readable, _, _ = select.select(
                [self.connection], [], [], max(0, deadline - time.monotonic())
            )
            if not readable:
                break
            chunk = self.connection.recv(65536)
            if not chunk:
                raise OSError("guest visual control channel disconnected")
            self.buffer.extend(chunk)
            if len(self.buffer) > 1024 * 1024:
                raise RuntimeError("guest visual control response exceeds 1 MiB")
        raise TimeoutError("guest visual control response timed out")

    def wait_ready(self, timeout: int = 120) -> dict:
        greeting = self._read_line(timeout)
        if greeting.get("event") != "ready" or greeting.get("protocol") != 1:
            raise RuntimeError(f"invalid guest visual control greeting: {greeting}")
        if not greeting.get("wayland"):
            raise RuntimeError("guest visual test agent did not start in Wayland")
        return greeting

    def call(self, operation: str, arguments: dict | None = None, timeout: int = 45) -> dict:
        self.sequence += 1
        request_id = self.sequence
        request = {
            "id": request_id,
            "op": operation,
            "args": arguments or {},
        }
        self.connection.sendall(
            json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode()
            + b"\n"
        )
        response = self._read_line(timeout)
        if response.get("id") != request_id:
            raise RuntimeError("guest visual control response ID mismatch")
        if not response.get("ok"):
            raise RuntimeError(
                f"guest operation {operation} failed: {response.get('error', 'unknown error')}"
            )
        result = response.get("result")
        if not isinstance(result, dict):
            raise RuntimeError(f"guest operation {operation} returned no structured result")
        return result

    def close(self):
        self.connection.close()


def wait_for_ready(
    serial: Path,
    process: subprocess.Popen,
    timeout: int,
    stderr_log: Path,
) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if serial.is_file():
            data = serial.read_bytes()
            if has_serial_marker(data, READY_MARKER):
                vt_number = serial_integer(data, GRAPHICAL_VT_KEY)
                if vt_number is None or vt_number <= 0:
                    raise RuntimeError(
                        "GNOME readiness marker appeared without an active graphical VT"
                    )
                return vt_number
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
        "keys": [
            {"type": "qcode", "data": QCODE_ALIASES.get(key, key)}
            for key in keys
        ],
        "hold-time": 100,
    })


def click(qmp: QMP, x: int, y: int) -> None:
    if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
        raise ValueError("Click is outside the configured QEMU display")
    qmp.execute("input-send-event", {"events": [
        {"type": "abs", "data": {
            "axis": "x",
            "value": round(x * ABSOLUTE_POINTER_MAX / (WIDTH - 1)),
        }},
        {"type": "abs", "data": {
            "axis": "y",
            "value": round(y * ABSOLUTE_POINTER_MAX / (HEIGHT - 1)),
        }},
        {"type": "btn", "data": {"button": "left", "down": True}},
        {"type": "btn", "data": {"button": "left", "down": False}},
    ]})


def inspect_frame(path: Path) -> str:
    if not shutil.which("tesseract"):
        raise RuntimeError("tesseract-ocr is required to validate framebuffer content")
    result = subprocess.run(
        ["tesseract", str(path), "stdout", "--psm", "11"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    text = " ".join(result.stdout.casefold().split())
    if not text:
        raise RuntimeError(f"Framebuffer has no readable GNOME UI text: {path.name}")
    if "display output is not active" in text:
        raise RuntimeError(f"Framebuffer has no active display output: {path.name}")
    if re.search(r"systemd\s*\[\s*1\s*\]|gnu grub|kernel panic|\btty\d+\b|login:", text):
        raise RuntimeError(f"Framebuffer shows a boot or login console: {path.name}")
    return text


def capture(
    qmp: QMP,
    output: Path,
    name: str,
    theme: str,
    records: list[dict],
    readiness: dict,
) -> None:
    from PIL import Image, ImageStat

    if not readiness.get("ready"):
        raise RuntimeError(f"Guest did not confirm scene readiness for {name}: {readiness}")
    time.sleep(0.4)
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
        stats = ImageStat.Stat(rgb)
        rgb.save(png, optimize=True)
        size = list(rgb.size)
        mean = [round(value, 2) for value in stats.mean]
        stddev = [round(value, 2) for value in stats.stddev]
    raw.unlink()
    if size != [WIDTH, HEIGHT]:
        raise RuntimeError(
            f"Unexpected guest resolution for {name}: {size[0]}x{size[1]}"
        )
    try:
        ocr_text = inspect_frame(png)
    except RuntimeError as error:
        raise RuntimeError(
            f"{error}; mean={mean}, stddev={stddev}; "
            f"diagnostic frame saved to {png}"
        ) from error
    if max(stddev) < 3 or max(mean) < 8:
        raise RuntimeError(
            f"Framebuffer is black or inactive: {name}; mean={mean}, stddev={stddev}; "
            f"diagnostic frame saved to {png}"
        )
    records.append({
        "file": png.name,
        "theme": theme,
        "scene": name.removeprefix(f"{theme}-"),
        "window_readiness": readiness,
        "resolution": size,
        "sha256": hashlib.sha256(png.read_bytes()).hexdigest(),
        "ocr_text": ocr_text,
    })
    print(f"Captured {theme} {records[-1]['scene']}: {size[0]}x{size[1]}", flush=True)


def capture_shell_scenes(
    qmp: QMP,
    agent: GuestControl,
    output: Path,
    theme: str,
    records: list[dict],
) -> None:
    ready = agent.call("desktop_ready")
    capture(qmp, output, f"{theme}-desktop", theme, records, ready)

    click(qmp, 80, 16)
    ready = agent.call("wait_popup", {"popup": "launcher"})
    capture(qmp, output, f"{theme}-launcher", theme, records, ready)
    press(qmp, "esc")
    agent.call("desktop_ready")

    click(qmp, WIDTH - 64, 16)
    ready = agent.call("wait_popup", {"popup": "quick_settings"})
    capture(qmp, output, f"{theme}-quick-settings", theme, records, ready)
    press(qmp, "esc")
    agent.call("desktop_ready")

    ready = agent.call("open_app", {"app": "files"})
    capture(qmp, output, f"{theme}-nautilus", theme, records, ready)
    press(qmp, "alt", "f4")
    pause(0.5)
    agent.call("desktop_ready")

    ready = agent.call("open_app", {"app": "terminal"})
    capture(qmp, output, f"{theme}-terminal", theme, records, ready)
    press(qmp, "alt", "f4")
    pause(0.5)
    agent.call("desktop_ready")

    agent.call("notify")
    ready = agent.call("wait_popup", {"popup": "notification"})
    capture(qmp, output, f"{theme}-notifications", theme, records, ready)
    press(qmp, "esc")
    agent.call("desktop_ready")


def check_installed_icons(agent: GuestControl, output: Path) -> None:
    report = agent.call("icon_resolution", timeout=45)
    (output / "icon-resolution.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def check_shell_logs(agent: GuestControl, output: Path) -> None:
    report = agent.call("shell_logs", timeout=25)
    (output / "shell-log-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if not report.get("passed"):
        raise RuntimeError(f"GNOME Shell logged JS errors: {report.get('js_errors')}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iso", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=480)
    parser.add_argument("--accel", choices=("auto", "kvm", "tcg"), default="auto")
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
        control_socket = tmp / "visual-control.sock"
        vnc_socket = tmp / "display.sock"
        accel = choose_acceleration(args.accel)
        cpu = "host" if accel == "kvm" else "max"
        command = [
            qemu, "-machine", "q35", "-accel", accel, "-cpu", cpu,
            "-m", "4096", "-smp", "2", "-nic", "none",
            "-device", f"virtio-vga,xres={WIDTH},yres={HEIGHT},edid=on",
            "-device", "qemu-xhci,id=xhci", "-device", "usb-tablet,bus=xhci.0",
            "-device", "virtio-serial-pci,id=visual-serial",
            "-chardev", f"socket,id=visual-control,path={control_socket},server=on,wait=off",
            "-device", "virtserialport,chardev=visual-control,name=org.localzet.visual-test",
            "-display", f"vnc=unix:{vnc_socket},share=force-shared", "-monitor", "none",
            "-qmp", f"unix:{monitor},server=on,wait=off",
            "-no-reboot", "-boot", "order=d", "-cdrom", str(args.iso.resolve()),
            "-serial", f"file:{serial}",
        ]
        print(
            f"Starting real GNOME 50 Live guest with {accel} "
            f"(requested {args.accel})",
            flush=True,
        )
        stderr_stream = qemu_stderr.open("w", encoding="utf-8")
        process = subprocess.Popen(
            command, stdout=subprocess.DEVNULL, stderr=stderr_stream,
        )
        qmp = None
        agent = None
        try:
            qmp = QMP(monitor, timeout=20)
            agent = GuestControl(control_socket, timeout=20)
            graphical_vt = wait_for_ready(serial, process, args.timeout, qemu_stderr)
            try:
                greeting = agent.wait_ready(
                    timeout=min(args.timeout, GUEST_AGENT_READY_TIMEOUT)
                )
            except TimeoutError as error:
                channels = qmp.execute("query-chardev")
                raise RuntimeError(
                    "guest visual test agent did not open its virtio-serial port; "
                    f"QEMU channel state: {channels}"
                ) from error
            print(f"Guest control ready: {greeting}", flush=True)
            pause(3.0)

            press(qmp, "esc")
            pause(1.0)
            first_login = agent.call("state")
            expected_blue = "file:///usr/share/backgrounds/localzet/aurora-blue.webp"
            if (first_login["icon_theme"] != "Localzet"
                    or first_login["picture_uri"] != expected_blue
                    or first_login["picture_uri_dark"] != expected_blue
                    or first_login["appearance"] != "blue"):
                raise RuntimeError(f"first-login Blue defaults are wrong: {first_login}")
            ready = agent.call("desktop_ready")
            capture(qmp, args.out, "first-login-defaults", "blue", records, ready)
            check_installed_icons(agent, args.out)

            source = agent.call("prime_restore_source")["state"]
            expected_black = "file:///usr/share/backgrounds/localzet/aurora-black.webp"
            if (source["icon_theme"] != "Adwaita"
                    or source["picture_uri"] != expected_black
                    or source["appearance"] != "purple"):
                raise RuntimeError(f"could not prepare restore source: {source}")
            ready = agent.call("desktop_ready")
            capture(qmp, args.out, "restore-source-desktop", "restore-source", records, ready)

            appearance_results = {}
            for theme in ("blue", "purple", "black"):
                agent.call("open_app", {"app": "settings"})
                appearance_page = agent.call("open_page", {"page": "appearance"})
                capture(
                    qmp, args.out, f"{theme}-appearance-page",
                    theme, records, appearance_page,
                )
                applied = agent.call("select_theme", {"theme": theme}, timeout=45)
                state = applied["state"]
                expected_wallpaper = f"file:///usr/share/backgrounds/localzet/aurora-{theme}.webp"
                expected_accent = "blue" if theme == "blue" else "purple"
                if (state["appearance"] != theme
                        or state["icon_theme"] != "Localzet"
                        or state["picture_uri"] != expected_wallpaper
                        or state["picture_uri_dark"] != expected_wallpaper
                        or state["accent_color"] != expected_accent
                        or state["color_scheme"] != "prefer-dark"):
                    raise RuntimeError(f"Aurora {theme} settings did not apply: {state}")
                if state["ptyxis_palette"] not in (None, f"Aurora {theme.title()}"):
                    raise RuntimeError(f"Aurora {theme} terminal palette did not apply: {state}")
                appearance_results[theme] = state
                capture(qmp, args.out, f"{theme}-appearance", theme, records, applied)
                settings_ready = agent.call("open_page", {"page": "system"})
                capture(qmp, args.out, f"{theme}-settings", theme, records, settings_ready)
                press(qmp, "alt", "f4")
                pause(0.5)
                agent.call("desktop_ready")
                capture_shell_scenes(qmp, agent, args.out, theme, records)

            agent.call("open_app", {"app": "settings"})
            agent.call("open_page", {"page": "appearance"})
            restored = agent.call("restore", timeout=45)
            restored_state = restored["state"]
            if (restored_state["appearance"] != "purple"
                    or restored_state["icon_theme"] != "Adwaita"
                    or restored_state["picture_uri"] != expected_black
                    or restored_state["picture_uri_dark"] != expected_black
                    or restored_state["accent_color"] != "blue"
                    or restored_state["color_scheme"] != "default"
                    or restored_state["ptyxis_palette"] != "Aurora Blue"
                    or restored_state["restore_point"]):
                raise RuntimeError(f"Appearance did not restore the source state: {restored_state}")
            capture(qmp, args.out, "restored-appearance", "restored", records, restored)
            press(qmp, "alt", "f4")
            pause(0.5)
            ready = agent.call("desktop_ready")
            capture(qmp, args.out, "restored-desktop", "restored", records, ready)
            check_shell_logs(agent, args.out)

            from PIL import Image, ImageChops

            desktops = {
                theme: Image.open(args.out / f"{theme}-desktop.png").convert("RGB")
                for theme in ("blue", "purple", "black")
            }
            theme_differences = {}
            for left, right in (("blue", "purple"), ("blue", "black"), ("purple", "black")):
                difference = ImageChops.difference(desktops[left], desktops[right])
                max_channel = ImageChops.lighter(
                    ImageChops.lighter(difference.getchannel(0), difference.getchannel(1)),
                    difference.getchannel(2),
                )
                changed = sum(max_channel.histogram()[16:])
                ratio = changed / (WIDTH * HEIGHT)
                theme_differences[f"{left}-{right}"] = ratio
                if ratio < 0.10:
                    raise RuntimeError(
                        f"Aurora {left} and {right} desktops are visually indistinguishable "
                        f"({ratio:.2%} changed pixels)"
                    )

            (args.out / "manifest.json").write_text(json.dumps({
                "captured_at_utc": datetime.now(timezone.utc).isoformat(),
                "capture_method": "QEMU QMP screendump from the Ubuntu 26.04 GNOME 50 Wayland Live session",
                "qemu": qemu_version,
                "guest_resolution": [WIDTH, HEIGHT],
                "active_graphical_vt": graphical_vt,
                "guest_control_protocol": greeting,
                "appearance_states": appearance_results,
                "restored_state": restored_state,
                "desktop_theme_changed_pixel_ratios": theme_differences,
                "records": records,
            }, indent=2) + "\n", encoding="utf-8")
            print(f"Captured {len(records)} real GNOME framebuffer screens in {args.out}", flush=True)
        finally:
            if agent:
                agent.close()
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
