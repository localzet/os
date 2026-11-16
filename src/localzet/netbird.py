"""Read-only local NetBird status, without collecting peer identities."""
from __future__ import annotations

import json
from pathlib import Path
import os
import subprocess
import tempfile

CLIENT = Path("/usr/bin/netbird")
UI = Path("/usr/bin/netbird-ui")
STATES = {"Idle", "Connecting", "Connected", "NeedsLogin", "LoginFailed", "SessionExpired"}
MAX_STATUS = 4 * 1024**2


def installed(path):
    return path.is_file() and os.access(path, os.X_OK)


def parse_status(raw):
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get("daemonStatus") not in STATES:
        raise ValueError("Unrecognized NetBird daemon status")
    state = data["daemonStatus"]
    peers = data.get("peers", {})
    if not isinstance(peers, dict):
        raise ValueError("Invalid NetBird peer summary")
    total, connected = peers.get("total", 0), peers.get("connected", 0)
    if (type(total) is not int or type(connected) is not int
            or not 0 <= connected <= total <= 1000000):
        raise ValueError("Invalid NetBird peer counts")
    # Do not return IP, public keys, profiles, endpoints, DNS or peer details.
    return {"state": state, "total": total, "connected": connected}


def status():
    if not installed(CLIENT):
        return {"state": "not-installed"}
    try:
        with tempfile.TemporaryFile() as output:
            result = subprocess.run([str(CLIENT), "status", "--json"], stdout=output,
                                    stderr=subprocess.DEVNULL, timeout=12, check=False,
                                    env={"PATH": "/usr/bin:/bin", "HOME": str(Path.home()), "LC_ALL": "C.UTF-8"})
            if output.tell() > MAX_STATUS:
                return {"state": "unavailable"}
            output.seek(0)
            report = parse_status(output.read(MAX_STATUS))
            if result.returncode != 0 and report["state"] not in {"NeedsLogin", "LoginFailed", "SessionExpired"}:
                return {"state": "unavailable"}
            return report
    except (OSError, ValueError, subprocess.SubprocessError):
        return {"state": "unavailable"}
