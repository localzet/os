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


def ready():
    if "boot=casper" not in Path("/proc/cmdline").read_text().split():
        return False
    if run("findmnt", "-n", "-o", "FSTYPE", "/") != "overlay":
        return False
    identity = Path("/etc/os-release").read_text().splitlines()
    if not any(line in ("ID=localzet", 'ID="localzet"') for line in identity):
        return False
    if run("systemctl", "is-active", "display-manager.service") != "active":
        return False
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
            return True
    return False


def main():
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        if ready():
            fd = os.open("/dev/ttyS0", os.O_WRONLY | os.O_NOCTTY | os.O_NONBLOCK)
            try:
                if os.write(fd, MARKER) != len(MARKER):
                    return 1
            finally:
                os.close(fd)
            return 0
        time.sleep(2)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
