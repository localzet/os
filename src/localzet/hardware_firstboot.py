"""Experimental, explicitly installer-authorized first boot orchestration.

No automatic reboot, driver rollback, arbitrary package names or retry of a
failed dpkg transaction. A fresh boot is required between driver and CUDA.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
import sys

from localzet.hardware import inventory, plan
from localzet.hardware_cuda import running_gpus
from localzet.hardware_install import (
    JOURNAL, installed_system, review, apply_reviewed, write_receipt, check_previous_receipt,
)

POLICY = Path("/etc/localzet/hardware-auto")
STATE = "first-boot.json"
TERMINAL = {"not-applicable", "compute-verification-required", "blocked", "recovery-required"}


def read_private(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
            raise ValueError("Unsafe automation state or authorization")
        data = stream.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024:
        raise ValueError("Automation state too large")
    return data


def authorized():
    return read_private(POLICY) == b"nvidia-driver-and-cuda-v1\n"


def identity(devices):
    return sorted([row.address, row.vendor, row.device, row.device_class] for row in devices
                  if row.vendor == "10de" and row.device_class.startswith("03"))


def next_step(previous, devices, boot_id, runtime_ready):
    """Pure state transition; never authorize installation by GPU ID alone."""
    hardware = identity(devices)
    if previous:
        state = previous["state"]
        if state in TERMINAL:
            return state
        if previous["hardware"] != hardware:
            return "blocked"
        if state in ("driver-installing", "cuda-installing"):
            return "recovery-required"
        if state == "awaiting-reboot":
            if previous["boot_id"] == boot_id:
                return state
            return "cuda" if runtime_ready else "blocked"
        if state == "offline":
            if previous.get("phase") == "cuda":
                return "cuda" if runtime_ready else "blocked"
            if previous.get("phase") != "driver":
                return "blocked"
        else:
            return "blocked"
    if not hardware:
        return "not-applicable"
    return "cuda" if runtime_ready else "driver"


def update_cache():
    # Any failed repository prevents use of stale indexes in automatic mode.
    subprocess.run(["/usr/bin/apt-get", "-o", "APT::Update::Error-Mode=any", "update"],
                   check=True, timeout=600, stdin=subprocess.DEVNULL)


def transaction(phase):
    import apt
    import apt_pkg
    apt_pkg.config.set("APT::Get::AllowUnauthenticated", "false")
    apt_pkg.config.set("Acquire::AllowInsecureRepositories", "false")
    apt_pkg.config.set("Acquire::AllowDowngradeToInsecureRepositories", "false")
    filename = "last-cuda-transaction.json" if phase == "cuda" else "last-driver-transaction.json"
    with apt_pkg.SystemLock():
        check_previous_receipt(JOURNAL)
        check_previous_receipt(JOURNAL, "last-cuda-transaction.json")
        def current(cache):
            return review(cache, cuda=phase == "cuda")
        cache = apt.Cache()
        approved = current(cache)
        cache.clear()
        return apply_reviewed(apt.Cache(), approved, review_fn=current,
                              receipt_fn=lambda record: write_receipt(JOURNAL, record, filename=filename))


def run():
    installed_system()
    if not authorized():
        raise ValueError("No explicit installer authorization for automatic NVIDIA setup")
    os.environ.clear()
    os.environ.update(PATH="/usr/sbin:/usr/bin:/sbin:/bin", HOME="/root",
                      LC_ALL="C.UTF-8", DEBIAN_FRONTEND="noninteractive")
    data = read_private(JOURNAL / STATE)
    previous = json.loads(data) if data is not None else None
    devices = inventory()
    boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    hardware = identity(devices)
    try:
        running_gpus(devices)
        runtime_ready = True
    except ValueError:
        runtime_ready = False
    phase = next_step(previous, devices, boot_id, runtime_ready)

    def record(state, reason=None, pending_phase=None):
        entry = {"schema": 1, "state": state, "boot_id": boot_id, "hardware": hardware}
        if reason:
            entry["reason"] = reason
        if pending_phase:
            entry["phase"] = pending_phase
        write_receipt(JOURNAL, entry, filename=STATE)
        print("Hardware setup: " + state, flush=True)

    if phase not in ("driver", "cuda"):
        if not previous or previous["state"] != phase:
            record(phase)
        return
    # Check prior transaction receipts before even refreshing repositories.
    try:
        check_previous_receipt(JOURNAL)
        check_previous_receipt(JOURNAL, "last-cuda-transaction.json")
    except (OSError, ValueError) as error:
        record("recovery-required", str(error))
        raise
    try:
        update_cache()
    except (OSError, subprocess.SubprocessError):
        record("offline", "Archive refresh failed; retry on a later boot or explicit service restart", phase)
        return
    record(phase + "-installing")
    try:
        outcome = transaction(phase)
    except Exception as error:
        record("recovery-required", str(error))
        raise
    if phase == "driver":
        # Even already-installed packages may need a reboot to activate.
        record("awaiting-reboot")
    else:
        record("compute-verification-required")


def main():
    if len(sys.argv) != 1:
        return 2
    try:
        run()
        return 0
    except (OSError, ValueError, RuntimeError, SystemError, ImportError, subprocess.SubprocessError) as error:
        print("Hardware setup stopped: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
