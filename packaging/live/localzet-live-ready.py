#!/usr/bin/env python3
"""Live-only serial readiness probe; never enable on installed systems."""
import os
import re
import pwd
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


def session_ready():
    """A shell process alone may be starting, crashing or showing the greeter."""
    try:
        account = pwd.getpwnam("localzet")
        uid = account.pw_uid
    except KeyError:
        return "live-account-not-found"
    runtime = f"/run/user/{uid}"
    if not (Path(runtime) / "bus").exists():
        return "live-session-bus-not-found"
    command = ("setpriv", f"--reuid={uid}", f"--regid={account.pw_gid}",
               "--init-groups", "--", "env", f"HOME={account.pw_dir}",
               f"XDG_RUNTIME_DIR={runtime}",
               f"DBUS_SESSION_BUS_ADDRESS=unix:path={runtime}/bus")
    running = run(*command, "gdbus", "call", "--session",
                  "--dest", "org.gnome.SessionManager",
                  "--object-path", "/org/gnome/SessionManager",
                  "--method", "org.gnome.SessionManager.IsSessionRunning")
    if running != "(true,)":
        return "gnome-session-not-running"
    active = run(*command, "gnome-extensions", "list", "--active").splitlines()
    if "localzet-shell@localzet.com" not in active:
        return "aurora-extension-not-active"
    return None


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
    observations = []
    shell_running = bool(run("pgrep", "-u", "localzet", "-x", "gnome-shell"))
    for row in run("loginctl", "list-sessions", "--no-legend", "--no-pager").splitlines():
        session = row.split()[0] if row.split() else ""
        if not session:
            continue
        props = dict(line.split("=", 1) for line in run(
            "loginctl", "show-session", session, "-p", "Name", "-p", "Active",
            "-p", "Type", "-p", "Class", "-p", "Remote", "-p", "Desktop",
            "-p", "Seat", "-p", "State"
        ).splitlines() if "=" in line)
        observations.append({key: props.get(key, "") for key in
                             ("Name", "Type", "Class", "Seat", "Active", "Desktop", "State", "Remote")})
        # GNOME Shell is the actual compositor. Desktop is informational:
        # logind may leave Desktop blank or report a distribution-specific name.
        if (props.get("Name") == "localzet" and props.get("Active") == "yes"
                and props.get("Type") == "wayland" and props.get("Class") == "user"
                and props.get("Remote") == "no" and props.get("Seat") == "seat0"
                and shell_running):
            return session_ready()
    import json
    return "active-gnome-wayland-session-not-found " + json.dumps(
        {"sessions": observations, "gnome_shell": shell_running},
        ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )



def serial_write(message: bytes) -> bool:
    try:
        fd = os.open("/dev/ttyS0", os.O_WRONLY | os.O_NOCTTY | os.O_NONBLOCK)
        try:
            return os.write(fd, message) == len(message)
        finally:
            os.close(fd)
    except OSError:
        return False


def diagnostic_snapshot():
    """Bounded live-only logs, collected while the guest is still running."""
    commands = (
        ("memory", ("free", "-m")),
        ("gdm", ("journalctl", "-b", "-u", "gdm.service", "--no-pager", "-n", "45", "-o", "short-monotonic")),
        ("logind", ("journalctl", "-b", "-u", "systemd-logind.service", "--no-pager", "-n", "35", "-o", "short-monotonic")),
        ("shell", ("journalctl", "-b", "_COMM=gnome-shell", "--no-pager", "-n", "60", "-o", "short-monotonic")),
        ("session", ("journalctl", "-b", "_COMM=gnome-session-binary", "--no-pager", "-n", "35", "-o", "short-monotonic")),
        ("kernel", ("journalctl", "-k", "-b", "--no-pager", "-n", "120", "-o", "short-monotonic")),
    )
    for label, command in commands:
        try:
            completed = subprocess.run(command, capture_output=True, text=True,
                                       timeout=12, check=True)
            output = completed.stdout
        except (OSError, subprocess.SubprocessError):
            output = "diagnostic unavailable"
        if label == "kernel" and output != "diagnostic unavailable":
            output = "\n".join(line for line in output.splitlines()
                               if re.search(r"oom|out of memory|killed process|segfault|drm|virtio|watchdog",
                                            line, re.IGNORECASE))
        # Limit serial transmission, use bounded writes rather than one
        # nonblocking write of the complete journal.
        for line in output.splitlines()[-60:]:
            serial_write((f"LOCALZET_LIVE_DIAG {label} {line[:512]}\n").encode(errors="replace"))


def main():
    deadline = time.monotonic() + 420
    previous = None
    stable_since = None
    seen_session = False
    regression_logged = False
    while time.monotonic() < deadline:
        reason = readiness()
        if reason is None:
            seen_session = True
            if stable_since is None:
                stable_since = time.monotonic()
            if time.monotonic() - stable_since >= 10:
                return 0 if serial_write(MARKER) else 1
            time.sleep(2)
            continue
        stable_since = None
        if reason in ("gnome-session-not-running", "aurora-extension-not-active"):
            seen_session = True
        if seen_session and not regression_logged and reason.startswith("active-gnome-wayland-session-not-found"):
            regression_logged = True
            diagnostic_snapshot()
        if reason != previous:
            print(f"Live readiness: {reason}", flush=True)
            serial_write(f"LOCALZET_LIVE_WAIT {reason}\n".encode())
            previous = reason
        time.sleep(2)
    if not regression_logged:
        diagnostic_snapshot()
    serial_write(f"LOCALZET_LIVE_TIMEOUT {previous}\n".encode())
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
