"""Public, sanitized status projection of the private hardware transaction state."""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import tempfile
import time

PUBLIC = Path("/var/lib/localzet-hardware-status/status.json")
STATES = frozenset(("not-applicable", "refreshing", "driver-installing", "awaiting-reboot",
                    "cuda-installing", "compute-verification-required", "offline", "blocked",
                    "recovery-required"))


def publish(state, path=PUBLIC):
    if state not in STATES or os.geteuid() != 0:
        raise ValueError("Invalid privileged status publication")
    path.parent.mkdir(mode=0o755, exist_ok=True)
    info = path.parent.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError("Unsafe public hardware status directory")
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temp = Path(stream.name)
        try:
            # Never copy transaction details, repository URLs, hardware IDs,
            # private error messages or credentials into the public projection.
            json.dump({"schema": 1, "state": state, "updated": int(time.time())}, stream)
            stream.flush()
            os.fchmod(stream.fileno(), 0o644)
            os.fsync(stream.fileno())
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)


def read_status(path=PUBLIC):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
                return {"state": "unavailable"}
            raw = stream.read(4097)
        if len(raw) > 4096:
            return {"state": "unavailable"}
        record = json.loads(raw)
        if (not isinstance(record, dict) or set(record) != {"schema", "state", "updated"}
                or record["schema"] != 1 or record["state"] not in STATES
                or type(record["updated"]) is not int or record["updated"] < 0):
            return {"state": "unavailable"}
        return record
    except FileNotFoundError:
        return {"state": "no-record"}
    except (OSError, ValueError, TypeError):
        return {"state": "unavailable"}
