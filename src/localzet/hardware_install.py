"""Experimental, interactive NVIDIA driver transaction for installed Localzet OS.

This entry point accepts no package names, paths or unattended mode.
Run only through the administrator's explicit sudo authorization.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time

from localzet.hardware import inventory, resolve_local, nvidia_driver_targets, simulate_packages


JOURNAL = Path("/var/lib/localzet/hardware")


def installed_system():
    if os.geteuid() != 0:
        raise ValueError("Run as an authorized administrator")
    identity = Path("/etc/os-release").read_text().splitlines()
    if not any(line in ("ID=localzet", 'ID="localzet"') for line in identity):
        raise ValueError("Only installed Localzet OS is supported")
    if "boot=casper" in Path("/proc/cmdline").read_text().split():
        raise ValueError("Driver changes are not allowed in a Live session")
    if not os.path.samestat(os.stat("/"), os.stat("/proc/1/root")):
        raise ValueError("Driver changes are not allowed in a chroot")
    fstype = subprocess.check_output(["/usr/bin/findmnt", "-n", "-o", "FSTYPE", "/"],
                                     text=True, timeout=5).strip()
    if fstype not in ("ext4", "btrfs"):
        raise ValueError("Unsupported installed root filesystem")


def review(cache, *, cuda=False):
    devices = inventory()
    result = resolve_local(devices)
    runtime = []
    if cuda:
        from localzet.hardware_cuda import cuda_transaction
        selected = cuda_transaction(cache, devices, retain_marks=True)
        runtime = selected["runtime"]
        transaction = selected["transaction"]
        targets = tuple(transaction["targets"])
    else:
        targets = nvidia_driver_targets(result)
        if not targets:
            raise ValueError("No NVIDIA GPU detected")
        transaction = simulate_packages(cache, targets, retain_marks=True)
    if transaction["status"] != "simulated":
        raise ValueError("Driver transaction is blocked: " + transaction["status"])
    return {"phase": "cuda" if cuda else "driver", "runtime": runtime,
            "kernel": result["kernel"], "secure_boot": result["secure_boot"],
            "graphics": result["graphics"], "targets": transaction["targets"],
            "target_versions": {name: cache[name].candidate.version for name in targets},
            "changes": transaction["changes"],
            "download_bytes": transaction["download_bytes"],
            "additional_installed_bytes": transaction["additional_installed_bytes"]}


def fingerprint(reviewed):
    # Download size can change when another authorized client fills the cache;
    # identity, version, target and action changes require a new confirmation.
    stable = {key: reviewed[key] for key in ("kernel", "secure_boot", "graphics",
                                            "targets", "target_versions", "changes")}
    stable.update(phase=reviewed.get("phase", "driver"), runtime=reviewed.get("runtime", []))
    return hashlib.sha256(json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def write_receipt(directory, record, *, filename="last-driver-transaction.json"):
    for path in (directory.parent, directory):
        path.mkdir(mode=0o700, exist_ok=True)
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError("Unsafe hardware receipt directory")
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(record, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
            os.replace(temporary, directory / filename)
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        finally:
            temporary.unlink(missing_ok=True)


def apply_reviewed(cache, approved, *, review_fn=review, receipt_fn=None):
    """Commit only the marked cache whose revalidated identity was approved.

    Caller must hold apt_pkg.SystemLock for this cache's whole lifetime.
    """
    current = review_fn(cache)
    if fingerprint(current) != fingerprint(approved):
        cache.clear()
        raise ValueError("Hardware or package plan changed; review again")
    if not current["changes"]:
        cache.clear()
        return "already-installed"
    if receipt_fn is None:
        raise ValueError("Transaction receipt required")
    record = {"schema": 1, "plan": current, "fingerprint": fingerprint(current),
              "started": int(time.time()), "state": "installing"}
    receipt_fn(record)
    try:
        if not cache.commit(allow_unauthenticated=False):
            raise RuntimeError("APT did not confirm transaction completion")
    except BaseException:
        # Never try to undo arbitrary dpkg changes automatically.
        record["state"] = "failed-recovery-required"
        receipt_fn(record)
        raise
    record["state"] = ("installed-compute-verification-required" if current.get("phase") == "cuda"
                       else "installed-reboot-verification-required")
    receipt_fn(record)
    return record["state"]


def check_previous_receipt(directory, filename="last-driver-transaction.json"):
    path = directory / filename
    if not path.exists():
        return
    # Only root-owned, private receipt files are accepted.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
            raise ValueError("Unsafe previous transaction receipt")
        data = stream.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024:
        raise ValueError("Previous transaction receipt is too large")
    record = json.loads(data)
    if record.get("state") not in ("installed-reboot-verification-required", "installed-compute-verification-required"):
        raise ValueError("Previous transaction needs administrator recovery review")


def main():
    if sys.argv[1:] not in ([], ["--cuda"]) or not sys.stdin.isatty() or not sys.stdout.isatty():
        print("Interactive use only; optional --cuda phase", file=sys.stderr)
        return 2
    cuda = sys.argv[1:] == ["--cuda"]
    filename = "last-cuda-transaction.json" if cuda else "last-driver-transaction.json"
    def current_review(cache):
        return review(cache, cuda=cuda)
    try:
        installed_system()
        # Fixed execution environment; do not inherit APT_CONFIG, Python paths,
        # arbitrary PATH, or user-supplied package options.
        os.environ.clear()
        os.environ.update(PATH="/usr/sbin:/usr/bin:/sbin:/bin", HOME="/root",
                          LC_ALL="C.UTF-8", TERM="xterm", DEBIAN_FRONTEND="noninteractive")
        import apt
        import apt_pkg
        apt_pkg.config.set("APT::Get::AllowUnauthenticated", "false")
        apt_pkg.config.set("Acquire::AllowInsecureRepositories", "false")
        apt_pkg.config.set("Acquire::AllowDowngradeToInsecureRepositories", "false")
        with apt_pkg.SystemLock():
            check_previous_receipt(JOURNAL)
            check_previous_receipt(JOURNAL, "last-cuda-transaction.json")
            check_previous_receipt(JOURNAL, "last-base-transaction.json")
            cache = apt.Cache()
            approved = current_review(cache)
            cache.clear()
        print(json.dumps(approved, indent=2, ensure_ascii=False))
        if not approved["changes"]:
            print("The reviewed packages are already installed. Runtime verification remains required.")
            return 0
        token = "INSTALL " + fingerprint(approved)[:16]
        print("This changes system packages. Keep a working recovery kernel. No automatic reboot.")
        if input("Type " + token + " to authorize: ") != token:
            print("Cancelled; no packages changed")
            return 1
        with apt_pkg.SystemLock():
            check_previous_receipt(JOURNAL)
            check_previous_receipt(JOURNAL, "last-cuda-transaction.json")
            check_previous_receipt(JOURNAL, "last-base-transaction.json")
            state = apply_reviewed(apt.Cache(), approved, review_fn=current_review,
                receipt_fn=lambda record: write_receipt(JOURNAL, record, filename=filename))
        print(state)
        return 0
    except (OSError, ValueError, RuntimeError, SystemError, ImportError, EOFError, subprocess.SubprocessError) as error:
        print("Driver setup stopped: " + str(error), file=sys.stderr)
        print("If APT started, inspect the receipt and package-manager state before retrying.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
