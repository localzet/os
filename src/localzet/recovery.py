"""Read-only installed-system maintenance diagnostics; never repair or upgrade."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
import subprocess

KERNEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+_-]{0,127}")
RECEIPTS = ("last-base-transaction.json", "last-driver-transaction.json",
            "last-cuda-transaction.json")
COMPLETE = {"installed-reboot-verification-required",
            "installed-compute-verification-required"}


def regular_nonempty(path: Path) -> bool:
    try:
        info = path.lstat()
        return stat.S_ISREG(info.st_mode) and info.st_size > 0
    except OSError:
        return False


def kernel_inventory(boot: Path, running: str) -> dict:
    kernels = []
    for path in sorted(boot.glob("vmlinuz-*")):
        version = path.name[len("vmlinuz-"):]
        if not KERNEL.fullmatch(version) or not regular_nonempty(path):
            continue
        if regular_nonempty(boot / ("initrd.img-" + version)):
            kernels.append(version)
    return {"running": running, "complete_pairs": kernels,
            "running_pair_present": running in kernels,
            "fallback_pairs": [version for version in kernels if version != running]}


def grub_inventory(text: str, running: str) -> dict:
    normal, recovery = set(), set()
    # Generated GRUB entries use linux/linuxefi, not arbitrary shell expansion.
    # Count only matching explicit kernel paths, never display the config.
    for line in text.splitlines():
        words = line.split()
        if len(words) < 2 or words[0] not in ("linux", "linuxefi"):
            continue
        kernel = words[1].rsplit("/", 1)[-1]
        if not kernel.startswith("vmlinuz-"):
            continue
        version = kernel[len("vmlinuz-"):]
        if not KERNEL.fullmatch(version):
            continue
        if "recovery" in words[2:]:
            recovery.add(version)
        else:
            normal.add(version)
    return {"status": "inspected", "normal_entries": sorted(normal),
            "recovery_entries": sorted(recovery),
            "running_normal_entry": running in normal,
            "running_recovery_entry": running in recovery}


def package_audit(command=subprocess.run) -> str:
    try:
        result = command(["/usr/bin/dpkg", "--audit"], capture_output=True,
                         text=True, timeout=30, check=False,
                         env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C.UTF-8"})
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if result.returncode:
        return "unknown"
    # dpkg can return zero even if it lists half-configured packages.
    if result.stderr.strip():
        return "unknown"
    return "needs-review" if result.stdout.strip() else "clean"


def hardware_receipts(directory: Path) -> dict:
    result = {}
    for name in RECEIPTS:
        path = directory / name
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            result[name] = "absent"
            continue
        except OSError:
            result[name] = "unknown"
            continue
        try:
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
                    raise ValueError("unsafe receipt")
                data = stream.read(1024 * 1024 + 1)
                if len(data) > 1024 * 1024:
                    raise ValueError("oversized receipt")
                value = json.loads(data)
                state = value.get("state") if isinstance(value, dict) else None
                if not isinstance(state, str):
                    raise ValueError("invalid receipt")
                result[name] = ("verification-required" if state in COMPLETE
                                else "recovery-review-required")
        except (OSError, ValueError, UnicodeError):
            result[name] = "unknown"
    return result


def inspect() -> dict:
    running = os.uname().release
    boot = Path("/boot")
    kernels = kernel_inventory(boot, running)
    try:
        config = boot / "grub/grub.cfg"
        with config.open("r", encoding="utf-8") as stream:
            text = stream.read(4 * 1024 * 1024 + 1)
        if len(text) > 4 * 1024 * 1024:
            raise ValueError("oversized GRUB config")
        grub = grub_inventory(text, running)
    except (OSError, ValueError, UnicodeError):
        grub = {"status": "unknown"}
    try:
        root_type = subprocess.check_output(
            ["/usr/bin/findmnt", "-n", "-o", "FSTYPE", "/"], text=True,
            timeout=5).strip()
        esp_type = subprocess.check_output(
            ["/usr/bin/findmnt", "-n", "-o", "FSTYPE", "--mountpoint", "/boot/efi"],
            text=True, timeout=5).strip()
    except (OSError, subprocess.SubprocessError):
        root_type, esp_type = "unknown", "unknown"
    try:
        live = "boot=casper" in Path("/proc/cmdline").read_text().split()
    except OSError:
        live = None
    receipts = hardware_receipts(Path("/var/lib/localzet/hardware"))
    audit = package_audit()
    issues = []
    if live is not False:
        issues.append("installed-system-not-confirmed")
    if audit != "clean":
        issues.append("package-state-not-confirmed-clean")
    if not kernels["running_pair_present"]:
        issues.append("running-kernel-pair-missing")
    if not kernels["fallback_pairs"]:
        issues.append("no-alternate-kernel-pair")
    if grub.get("running_recovery_entry") is not True:
        issues.append("running-kernel-recovery-entry-not-confirmed")
    if root_type not in ("ext4", "btrfs") or esp_type != "vfat":
        issues.append("installed-uefi-mounts-not-confirmed")
    if any(state in ("unknown", "recovery-review-required") for state in receipts.values()):
        issues.append("hardware-receipts-need-review")
    return {"schema": 1, "operation": "read-only-recovery-diagnostics",
            "live_session": live, "root_filesystem": root_type, "esp_filesystem": esp_type,
            "kernel": kernels, "grub": grub, "package_audit": audit,
            "hardware_receipts": receipts, "issues": issues,
            "writes_performed": False, "rollback_verified": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(inspect(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
