"""Experimental network-isolated AI CLI launcher.

Only the fixed local HTTP proxy selected in GNOME is reachable via the relay.
This does not attest proxy ownership, upstream routing, or sandbox security
against a hostile local user. No installation or credential collection.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time

TOOLS = {"codex": "/opt/localzet-ai/bin/codex",
         "claude": "/opt/localzet-ai/bin/claude"}
PORT = 18080
PROXY = f"http://127.0.0.1:{PORT}"


def validate_endpoint(mode, host, port, installed):
    if not installed:
        raise ValueError("UserNet не установлен")
    if mode != "manual" or host not in ("127.0.0.1", "localhost"):
        raise ValueError("Включите локальный системный HTTP-прокси UserNet")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Некорректный порт прокси")
    return port


def usernet_port():
    from gi.repository import Gio
    # UserNet writes the GNOME HTTP proxy when system proxy mode is on.
    # This is a candidate endpoint, not proof of its process ownership.
    try:
        installed = Gio.DesktopAppInfo.new("com.localzet.usernet.desktop") is not None
    except TypeError:
        installed = False
    settings = Gio.Settings.new("org.gnome.system.proxy")
    http = Gio.Settings.new("org.gnome.system.proxy.http")
    return validate_endpoint(settings.get_string("mode"), http.get_string("host"),
                             http.get_int("port"), installed)


def sandbox_command(tool, args, relay, home, cwd):
    if tool not in TOOLS:
        raise ValueError("Unknown AI client")
    # The host relay is the only deliberately exposed networking channel.
    # Hide host runtime sockets, D-Bus, systemd, Docker socket and host /tmp.
    # The home and cwd remain writable for normal developer workflows.
    command = ["/usr/bin/bwrap", "--die-with-parent", "--unshare-net",
               "--unshare-pid", "--unshare-ipc", "--unshare-uts",
               "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc",
               "--tmpfs", "/run", "--tmpfs", "/tmp",
               "--dir", "/run/localzet-ai",
               "--ro-bind", str(relay), "/run/localzet-ai/relay",
               "--bind", str(home), str(home)]
    if not cwd.is_relative_to(home):
        command += ["--bind", str(cwd), str(cwd)]
    command += ["--chdir", str(cwd)]
    for key in ("DBUS_SESSION_BUS_ADDRESS", "DBUS_SYSTEM_BUS_ADDRESS",
                "SSH_AUTH_SOCK", "WAYLAND_DISPLAY", "DISPLAY", "XAUTHORITY",
                "XDG_RUNTIME_DIR", "DOCKER_HOST", "CONTAINER_HOST",
                "BROWSER", "NODE_EXTRA_CA_CERTS"):
        command += ["--unsetenv", key]
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                "http_proxy", "https_proxy", "all_proxy"):
        command += ["--setenv", key, PROXY]
    for key in ("NO_PROXY", "no_proxy"):
        command += ["--setenv", key, ""]
    command += ["--setenv", "BROWSER", "/bin/false",
                "--setenv", "DISABLE_AUTOUPDATER", "1",
                "/usr/bin/localzet-ai",
                "--inside", tool, *args]
    return command


def wait_listener(host, port, process):
    for _ in range(40):
        if process.poll() is not None:
            raise RuntimeError("Proxy relay exited")
        try:
            with socket.create_connection((host, port), timeout=.1):
                return
        except OSError:
            time.sleep(.05)
    raise RuntimeError("Proxy relay unavailable")


def inside(tool, args):
    # Never permit an accidental direct invocation of the internal mode.
    # A newly created network namespace has only loopback.
    # /proc/self/net reflects the process network namespace, unlike a
    # bind-mounted host sysfs.
    interfaces = {line.split(":", 1)[0].strip()
                  for line in Path("/proc/self/net/dev").read_text().splitlines()[2:]
                  if ":" in line}
    if interfaces != {"lo"}:
        raise RuntimeError("Isolated network namespace required")
    relay = subprocess.Popen(["/usr/bin/socat",
        f"TCP4-LISTEN:{PORT},bind=127.0.0.1,reuseaddr,fork",
        "UNIX-CONNECT:/run/localzet-ai/relay"], close_fds=True)
    try:
        wait_listener("127.0.0.1", PORT, relay)
        return subprocess.call([TOOLS[tool], *args], close_fds=True)
    finally:
        relay.terminate()
        relay.wait(timeout=5)


def launch(tool, args):
    if os.geteuid() == 0:
        raise RuntimeError("AI clients must run as a desktop user")
    if not Path(TOOLS[tool]).is_file():
        raise RuntimeError("Официальный AI CLI ещё не установлен")
    port = usernet_port()
    # Refuse startup when the local proxy is not listening.
    with socket.create_connection(("127.0.0.1", port), timeout=2):
        pass
    home, cwd = Path.home().resolve(), Path.cwd().resolve()
    # Never remount host runtime paths into the sandbox via cwd.
    if not cwd.is_relative_to(home) and not cwd.is_relative_to(Path("/workspace")):
        raise RuntimeError("Use a project in your home directory or /workspace")
    if home == Path("/") or not home.is_relative_to(Path("/home")):
        raise RuntimeError("Unsupported desktop home directory")
    with tempfile.TemporaryDirectory(prefix="localzet-ai-") as directory:
        relay_path = Path(directory) / "relay"
        relay = subprocess.Popen(["/usr/bin/socat",
            f"UNIX-LISTEN:{relay_path},fork,mode=0600",
            f"TCP4:127.0.0.1:{port}"], close_fds=True)
        try:
            for _ in range(40):
                if relay.poll() is not None:
                    raise RuntimeError("UserNet relay exited")
                if relay_path.is_socket():
                    break
                time.sleep(.05)
            else:
                raise RuntimeError("UserNet relay unavailable")
            return subprocess.call(sandbox_command(tool, args, relay_path, home, cwd),
                                   close_fds=True)
        finally:
            relay.terminate()
            relay.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inside", action="store_true")
    parser.add_argument("tool", choices=TOOLS)
    parser.add_argument("args", nargs=argparse.REMAINDER)
    ns = parser.parse_args()
    try:
        return inside(ns.tool, ns.args) if ns.inside else launch(ns.tool, ns.args)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        parser.exit(2, f"Localzet AI: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
