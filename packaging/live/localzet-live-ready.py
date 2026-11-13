#!/usr/bin/env python3
"""Live-only serial readiness probe; never enable on installed systems."""
import os
from pathlib import Path
import subprocess
import time

MARKER = b"LOCALZET_LIVE_READY\n"


def run(*args):
    try:
        result = subprocess.run(args, capture_output=True, text=True,
                                timeout=5, check=True)
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def readiness():
    if "boot=casper" not in Path("/proc/cmdline").read_text().split():
        return "not-casper"
    if run("findmnt", "-n", "-o", "FSTYPE", "/") != "overlay":
        return "root-not-overlay"
    identity = Path("/etc/os-release").read_text().splitlines()
    if not any(line in ("ID=localzet", 'ID="localzet"') for line in identity):
        return "os-identity-mismatch"
    if run("systemctl", "is-active", "display-manager.service") != "active":
        return "display-manager-inactive"
    for row in run("loginctl", "list-sessions", "--no-legend", "--no-pager").splitlines():
        session = row.split()[0] if row.split() else ""
        if not session:
            continue
        props = dict(line.split("=", 1) for line in run(
            "loginctl", "show-session", session, "-p", "Name", "-p", "Active",
            "-p", "Type", "-p", "Class", "-p", "Remote", "-p", "Desktop"
        ).splitlines() if "=" in line)
        if (props.get("Name") == "localzet" and props.get("Active") == "yes"
                and props.get("Type") == "wayland" and props.get("Class") == "user"
                and props.get("Remote") == "no"
                and props.get("Desktop", "").lower() in ("gnome", "ubuntu", "localzet")
                and run("pgrep", "-u", "localzet", "-x", "gnome-shell")):
            return None
    return "active-gnome-wayland-session-not-found"


def serial_write(message: bytes) -> bool:
    try:
        fd = os.open("/dev/ttyS0", os.O_WRONLY | os.O_NOCTTY | os.O_NONBLOCK)
        try:
            return os.write(fd, message) == len(message)
        finally:
            os.close(fd)
    except OSError:
        return False


def main():
    deadline = time.monotonic() + 240
    previous = None
    while time.monotonic() < deadline:
        reason = readiness()
        if reason is None:
            return 0 if serial_write(MARKER) else 1
        if reason != previous:
            print(f"Live readiness: {reason}", flush=True)
            serial_write(f"LOCALZET_LIVE_WAIT {reason}\n".encode())
            previous = reason
        time.sleep(2)
    serial_write(f"LOCALZET_LIVE_TIMEOUT {previous}\n".encode())
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
