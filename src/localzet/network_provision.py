"""Fixed installed-system provisioning actions for reviewed clients."""
from pathlib import Path
import os

ROOT = Path("/usr/lib/localzet")
CLIENTS = {"netbird": "install-netbird", "usernet": "install-usernet"}


def command(kind):
    if kind not in CLIENTS:
        raise ValueError("Unknown network client")
    return ["/usr/bin/pkexec", str(ROOT / CLIENTS[kind])]


def usernet_installed():
    return Path("/opt/UserNet/UserNet").is_file() and os.access("/opt/UserNet/UserNet", os.X_OK)


def available(kind):
    try:
        args = command(kind)
        return (os.geteuid() != 0 and "boot=casper" not in Path("/proc/cmdline").read_text().split()
                and any(line in ("ID=localzet", 'ID="localzet"') for line in Path("/etc/os-release").read_text().splitlines())
                and all(Path(p).is_file() and os.access(p, os.X_OK) for p in args))
    except (OSError, ValueError):
        return False
